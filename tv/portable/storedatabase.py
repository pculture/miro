# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

"""``miro.storedatabase`` -- Handle database storage.

This module does the reading/writing of our database to/from disk.  It
works with the schema module to validate the data that we read/write
and with the upgradedatabase module to upgrade old database storages.

Datastorage is handled through SQLite.  Each DDBObject class is stored
in a separate table.  Each attribute for that class is saved using a
separate column.

Most columns are stored using SQLite datatypes (``INTEGER``, ``REAL``,
``TEXT``, ``DATETIME``, etc.).  However some of our python values,
don't have an equivalent (lists, dicts and timedelta objects).  For
those, we store the python representation of the object.  This makes
the column look similar to a JSON value, although not quite the same.
The hope is that it will be human readable.  We use the type
``pythonrepr`` to label these columns.
"""

import shutil
import cPickle
import itertools
import logging
import datetime
import traceback
import time
import os
from cStringIO import StringIO

try:
    import sqlite3
except ImportError:
    from pysqlite2 import dbapi2 as sqlite3

from miro import app
from miro import config
from miro import convert20database
from miro import databaseupgrade
from miro import dbupgradeprogress
from miro import dialogs
from miro import eventloop
from miro import messages
from miro import schema
from miro import prefs
from miro import util
from miro.download_utils import nextFreeFilename
from miro.gtcache import gettext as _
from miro.plat.utils import FilenameType, filenameToUnicode

class UpgradeDiskSpaceError(Exception):
    """While upgrading the database, we ran out of disk space."""
    pass

# Which SQLITE type should we use to store SchemaItem subclasses?
_sqlite_type_map = {
        schema.SchemaBool: 'integer',
        schema.SchemaFloat: 'real',
        schema.SchemaString: 'text',
        schema.SchemaBinary:  'blob',
        schema.SchemaURL: 'text',
        schema.SchemaInt: 'integer',
        schema.SchemaDateTime: 'timestamp',
        schema.SchemaTimeDelta: 'pythonrepr',
        schema.SchemaReprContainer: 'pythonrepr',
        schema.SchemaDict: 'pythonrepr',
        schema.SchemaList: 'pythonrepr',
        schema.SchemaStatusContainer: 'pythonrepr',
        schema.SchemaFilename: 'text',
}

VERSION_KEY = "Democracy Version"

class LiveStorage:
    """Handles the storage of DDBObjects.

    This class does basically two things:

    1. Loads the initial object list (and runs database upgrades)
    2. Handles updating the database based on changes to DDBObjects.
    """
    def __init__(self, path=None, object_schemas=None, schema_version=None):
        if path is None:
            path = config.get(prefs.SQLITE_PATHNAME)
        if object_schemas is None:
            object_schemas = schema.object_schemas
        if schema_version is None:
            schema_version = schema.VERSION

        # version of sqlite3
        try:
            logging.info("Sqlite3 version:   %s", sqlite3.sqlite_version)
        except AttributeError:
            logging.info("sqlite3 has no sqlite_version attribute.")

        # version of the sqlite python bindings
        try:
            logging.info("Pysqlite version:  %s", sqlite3.version)
        except AttributeError:
            logging.info("sqlite3 has no version attribute.")

        db_existed = os.path.exists(path)
        self._dc = None
        self._query_times = {}
        self.path = path
        self.open_connection()
        self._quitting_from_operational_error = False
        self._object_schemas = object_schemas
        self._schema_version = schema_version
        self._schema_map = {}
        self._all_schemas = []
        self._object_map = {} # maps object id -> DDBObjects in memory
        self._ids_loaded = set()
        for oschema in object_schemas:
            self._all_schemas.append(oschema)
            for klass in oschema.ddb_object_classes():
                self._schema_map[klass] = oschema
                for field_name, schema_item in oschema.fields:
                    klass.track_attribute_changes(field_name)
        self._converter = SQLiteConverter()

        if not db_existed:
            self._init_database()

    def open_connection(self):            
        self.connection = sqlite3.connect(self.path,
                isolation_level=None,
                detect_types=sqlite3.PARSE_DECLTYPES)
        self.cursor = self.connection.cursor()

    def close(self):
        if self._dc:
            self._dc.cancel()
            self._dc = None

        # the unittests run in memory and vacuum causes a segfault if
        # the db is in memory.
        if self.path != ":memory:" and self.connection and self.cursor:
            logging.info("Vacuuming the db before shutting down.")
            try:
                self.cursor.execute("vacuum")
            except sqlite3.DatabaseError, sdbe:
                logging.info("... Vacuuming failed with DatabaseError: %s", sdbe)
        self.connection.close()

    def upgrade_database(self):
        """Run any database upgrades that haven't been run."""
        try:
            self._upgrade_database()
        except (KeyError, SystemError,
                databaseupgrade.DatabaseTooNewError):
            raise
        except sqlite3.OperationalError, e:
            logging.exception('OperationalError when upgrading database: %s', e)
            raise UpgradeDiskSpaceError()
        except UpgradeDiskSpaceError:
            raise
        except:
            self._handle_load_error("Error upgrading database")
            self.startup_version = self.current_version = self._get_version()

    def _backup_database(self, ver):
        """Backs up the database file.

        :param ver: the current version (as string)
        """
        logging.info("path of database: %s", self.path)
        # close database
        self.close()

        # copy file over
        try:
            shutil.copyfile(self.path, "%s_backup_%s" % (self.path, ver))
        except IOError, e:
            logging.exception('Error when backing up database')

        # re-open database
        self.open_connection()

    def _upgrade_database(self):
        self.startup_version = current_version = self._get_version()

        if current_version > self._schema_version:
            msg = _("Database was created by a newer version of Miro " +
                    "(db version is %(version)s)",
                    {"version": current_version})
            raise databaseupgrade.DatabaseTooNewError(msg)

        if current_version < self._schema_version:
            dbupgradeprogress.upgrade_start()
            try:
                self._upgrade_20_database()
                # need to pull the variable again here because
                # _upgrade_20_database will have done an upgrade
                current_version = self._get_version()
                self._backup_database(current_version)
                databaseupgrade.new_style_upgrade(self.cursor,
                                                  current_version,
                                                  self._schema_version)
                self._set_version()
            finally:
                dbupgradeprogress.upgrade_end()
        self.current_version = self._schema_version

    def _upgrade_20_database(self):
        self.cursor.execute("SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' and name = 'dtv_objects'")
        if self.cursor.fetchone()[0] > 0:
            current_version = self._get_version()
            if current_version >= 80:
                # we have a dtv_objects table, but we also have a database
                # that's been converted to the new-style.  What happened was
                # that the user ran a new version of Miro, than re-ran and old
                # version.  Just deleted dtv_objects.
                if util.chatter:
                    logging.info("deleting dtv_objects table")
                self.cursor.execute("DROP TABLE dtv_objects")
            else:
                # Need to update an old-style database
                self._backup_database("pre80")
                dbupgradeprogress.doing_20_upgrade()

                if util.chatter:
                    logging.info("converting pre 2.1 database")
                convert20database.convert(self.cursor)
                self._set_version(80)

    def _get_variable(self, name):
        self.cursor.execute("SELECT serialized_value FROM dtv_variables "
                "WHERE name=?", (name,))
        row = self.cursor.fetchone()
        return cPickle.loads(str(row[0]))

    def _set_variable(self, name, value):
        # we only store one variable and it's easier to deal with if we store
        # it using ASCII-base protocol.
        db_value = buffer(cPickle.dumps(value, 0))
        self.cursor.execute("REPLACE INTO dtv_variables "
                "(name, serialized_value) VALUES (?,?)", (name, db_value))

    def _create_variables_table(self):
        self.cursor.execute("""CREATE TABLE dtv_variables(
        name TEXT PRIMARY KEY NOT NULL,
        serialized_value BLOB NOT NULL);""")

    def remember_object(self, obj):
        self._object_map[obj.id] = obj
        self._ids_loaded.add(obj.id)

    def forget_object(self, obj):
        del self._object_map[obj.id]
        self._ids_loaded.remove(obj.id)

    def insert_obj(self, obj):
        """Add a new DDBObject to disk."""

        obj_schema = self._schema_map[obj.__class__]
        column_names = []
        values = []
        for name, schema_item in obj_schema.fields:
            column_names.append(name)
            value = getattr(obj, name)
            try:
                schema_item.validate(value)
            except schema.ValidationError:
                if util.chatter:
                    logging.warn("error validating %s for %s", name, obj)
                raise
            values.append(self._converter.to_sql(obj_schema, name,
                schema_item, value))
        sql = "INSERT INTO %s (%s) VALUES(%s)" % (obj_schema.table_name,
                ', '.join(column_names),
                ', '.join('?' for i in xrange(len(column_names))))
        self._execute(sql, values, is_update=True)
        self.remember_object(obj)

    def update_obj(self, obj):
        """Update a DDBObject on disk."""

        obj_schema = self._schema_map[obj.__class__]
        setters = []
        values = []
        for name, schema_item in obj_schema.fields:
            if (isinstance(schema_item, schema.SchemaSimpleItem) and
                    name not in obj.changed_attributes):
                continue
            setters.append('%s=?' % name)
            value = getattr(obj, name)
            try:
                schema_item.validate(value)
            except schema.ValidationError:
                if util.chatter:
                    logging.warn("error validating %s for %s", name, obj)
                raise
            values.append(self._converter.to_sql(obj_schema, name,
                schema_item, value))
        obj.reset_changed_attributes()
        if values:
            sql = "UPDATE %s SET %s WHERE id=%s" % (obj_schema.table_name,
                    ', '.join(setters), obj.id)
            self._execute(sql, values)
        self.remember_object(obj)

    def remove_obj(self, obj):
        """Remove a DDBObject from disk."""

        schema = self._schema_map[obj.__class__]
        sql = "DELETE FROM %s WHERE id=?" % (schema.table_name)
        self._execute(sql, (obj.id,), is_update=True)
        self.forget_object(obj)

    def get_last_id(self):
        try:
            return self._get_last_id()
        except (KeyError, SystemError,
                databaseupgrade.DatabaseTooNewError):
            raise
        except:
            self._handle_load_error("Error calculating last id")
            return self._get_last_id()

    def _get_last_id(self):
        max_id = 0
        for schema in self._object_schemas:
            self.cursor.execute("SELECT MAX(id) FROM %s" % schema.table_name)
            max_id = max(max_id, self.cursor.fetchone()[0])
        return max_id

    def get_obj_by_id(self, id):
        """Get a particular DDBObject.

        This will throw a KeyError if id is not in the database, or if the
        object for id has not been loaded yet.
        """
        return self._object_map[id]

    def table_name(self, klass):
        return self._schema_map[klass].table_name

    def object_from_class_table(self, obj, klass):
        return self._schema_map[klass] is self._schema_map[obj.__class__]

    def _get_query_bottom(self, table_name, where, joins):
        sql = StringIO()
        sql.write("FROM %s\n" % table_name)
        if joins is not None:
            for join_table, join_where in joins.items():
                sql.write('LEFT JOIN %s ON %s\n' % (join_table, join_where))
        if where is not None:
            sql.write("WHERE %s" % where)
        return sql.getvalue()

    def query(self, klass, where, values=None, order_by=None, joins=None):
        for id in self.query_ids(klass, where, values, order_by, joins):
            yield self._object_map[id]

    def query_ids(self, klass, where, values=None, order_by=None, joins=None):
        schema = self._schema_map[klass]
        sql = StringIO()
        sql.write("SELECT %s.id " % schema.table_name)
        sql.write(self._get_query_bottom(schema.table_name, where, joins))
        if order_by is not None:
            sql.write(" ORDER BY %s" % order_by)

        self.cursor.execute(sql.getvalue(), values)
        rv = [row[0] for row in self.cursor.fetchall()]
        unrestored_ids = set(rv).difference(self._ids_loaded)
        if unrestored_ids:
            # restore any objects that we don't already have in memory.
            # query() calls query_ids() and expects that for all the object
            # ids returned, it can look them up in self._object_map
            self._restore_objects(schema, unrestored_ids)

            # sometimes objects will call remove() in setup_restored().
            # We need to filter those out.
            rv = [id for id in rv if id in self._object_map]
        return rv

    def _restore_objects(self, schema, id_set):
        column_names = ['%s.%s' % (schema.table_name, f[0])
                for f in schema.fields]

        # we can only feed sqlite so many variables at once, send it chunks of
        # 900 ids at once
        id_list = tuple(id_set)
        for start in xrange(0, len(id_list), 900):
            id_list_chunk = id_list[start:start+900]

            sql = StringIO()
            sql.write("SELECT %s " % (', '.join(column_names),))
            sql.write("FROM %s WHERE id IN (%s)" % (schema.table_name, 
                ', '.join('?' for i in xrange(len(id_list_chunk)))))

            self.cursor.execute(sql.getvalue(), id_list_chunk)
            for row in self.cursor.fetchall():
                self._restore_object_from_row(schema, row)

    def _restore_object_from_row(self, schema, db_row):
        restored_data = {}
        for (name, schema_item), value in \
                itertools.izip(schema.fields, db_row):
            try:
                value = self._converter.from_sql(schema, name, schema_item,
                        value)
            except:
                if util.chatter:
                    logging.warn("error converting %s (%r)", name,
                            value)
                raise
            restored_data[name] = value
        klass = schema.get_ddb_class(restored_data)
        return klass(restored_data=restored_data)

    def persistent_object_count(self):
        return len(self._object_map)

    def query_count(self, klass, where, values=None, joins=None):
        schema = self._schema_map[klass]
        sql = StringIO()
        sql.write('SELECT COUNT(*) ')
        sql.write(self._get_query_bottom(schema.table_name, where, joins))
        return self._execute(sql.getvalue(), values)[0][0]

    def delete(self, klass, where, values):
        schema = self._schema_map[klass]
        sql = StringIO()
        sql.write('DELETE FROM %s' % schema.table_name)
        if where is not None:
            sql.write('\nWHERE %s' % where)
        self._execute(sql.getvalue(), values, is_update=True)

    def select(self, klass, columns, where, values):
        schema = self._schema_map[klass]
        sql = StringIO()
        sql.write('SELECT %s ' % columns)
        sql.write(self._get_query_bottom(schema.table_name, where, None))
        return self._execute(sql.getvalue(), values)

    def _execute(self, sql, values, is_update=False):
        if is_update and self._quitting_from_operational_error:
            # We want to avoid updating the database at this point.
            return

        if values is None:
            values = ()

        failed = False
        while True:
            try:
                self._time_execute(sql, values)
            except sqlite3.OperationalError, e:
                # printing the traceback here in whole rather than doing
                # a logging.exception which seems to show the traceback
                # up to the try/except handler.
                logging.exception("OperationalError\n"
                                  "statement: %s\n\n"
                                  "values: %s\n\n"
                                  "full stack:\n%s\n", sql, values,
                                  "".join(traceback.format_stack()))
                if not is_update and self._quitting_from_operational_error:
                    # This is a very bad state to be in because code calling
                    # us expects a return value.  I think the best we can do
                    # is re-raise the exception (BDK)
                    raise
                failed = True
                self._handle_operational_error(str(e))
                if self._quitting_from_operational_error:
                    break
            else:
                break
        if failed and not self._quitting_from_operational_error:
            title = _("%(appname)s database save succeeded",
                      {"appname": config.get(prefs.SHORT_APP_NAME)})
            description = _("The database has been successfully saved. "
                    "It is now safe to quit without losing any data.")
            dialogs.MessageBoxDialog(title, description).run()
        if is_update:
            return None
        else:
            return self.cursor.fetchall()

    def _time_execute(self, sql, values):
        start = time.time()
        self.cursor.execute(sql, values)
        end = time.time()
        self._check_time(sql, end-start)

    def _handle_operational_error(self, error_text):
        title = _("%(appname)s database save failed",
                  {"appname": config.get(prefs.SHORT_APP_NAME)})
        description = _(
            "%(appname)s was unable to save its database.\n\n"
            "If your disk is full, we suggest freeing up some space and "
            "retrying.  If your disk is not full, it's possible that "
            "retrying will work.\n\n"
            "If retrying did not work, please quit %(appname)s and restart.  "
            "Recent changes may be lost.\n\n"
            "If you see this error often while downloading, we suggest "
            "you reduce the number of simultaneous downloads in the Options "
            "dialog in the Download tab.\n\n"
            "Error: %(error_text)s\n\n",
            {"appname": config.get(prefs.SHORT_APP_NAME),
             "error_text": error_text}
            )
        d = dialogs.ChoiceDialog(title, description,
                dialogs.BUTTON_RETRY, dialogs.BUTTON_QUIT)
        choice = d.run_blocking()
        if choice == dialogs.BUTTON_QUIT:
            self._quitting_from_operational_error = True
            messages.FrontendQuit().send_to_frontend()
        else:
            logging.warn("Re-running SQL statement")

    def _check_time(self, sql, query_time):
        SINGLE_QUERY_LIMIT = 0.5
        CUMULATIVE_LIMIT = 1.0
        if query_time > SINGLE_QUERY_LIMIT:
            logging.timing("query slow (%0.3f seconds): %s", query_time, sql)

        return # comment out to test cumulative query times

        # more than half a second in the last
        old_times = self._query_times.setdefault(sql, [])
        now = time.time()
        dropoff_time = now - 5
        cumulative = query_time
        for i in reversed(xrange(len(old_times))):
            old_time, old_query_time = old_times[i]
            if old_time < dropoff_time:
                old_times = old_times[i+1:]
                break
            cumulative += old_query_time
        old_times.append((now, query_time))
        if cumulative > CUMULATIVE_LIMIT:
            logging.timing('query cumulatively slow: %0.2f '
                    '(%0.03f): %s', cumulative, query_time, sql)

    def _init_database(self):
        """Create a new empty database."""

        for schema in self._object_schemas:
            self.cursor.execute("CREATE TABLE %s (%s)" %
                    (schema.table_name, self._calc_sqlite_types(schema)))
            for name, columns in schema.indexes:
                self.cursor.execute("CREATE INDEX %s ON %s (%s)" %
                        (name, schema.table_name, ', '.join(columns)))
        self._create_variables_table()
        self._set_version()

    def _get_version(self):
        return self._get_variable(VERSION_KEY)

    def _set_version(self, version=None):
        """Set the database version to the current schema version."""

        if version is None:
            version = self._schema_version
        self._set_variable(VERSION_KEY, version)

    def _calc_sqlite_types(self, object_schema):
        """What datatype should we use for the attributes of an object schema?
        """

        types = []
        for name, schema_item in object_schema.fields:
            type = _sqlite_type_map[schema_item.__class__]
            if name != 'id':
                types.append('%s %s' % (name, type))
            else:
                types.append('%s %s PRIMARY KEY' % (name, type))
        return ', '.join(types)

    def _handle_load_error(self, message):
        """Handle errors happening when we try to load the database.  Our
        basic strategy is to log the error, save the current database then
        start fresh with an empty database.
        """
        if util.chatter:
            logging.exception(message)
        self.connection.close()
        self.save_invalid_db()
        self.open_connection()
        self._init_database()

    def save_invalid_db(self):
        dir = os.path.dirname(self.path)
        save_name = "corrupt_database"
        i = 0
        while os.path.exists(os.path.join(dir, save_name)):
            i += 1
            save_name = "corrupt_database.%d" % i

        os.rename(self.path, os.path.join(dir, save_name))

    def dumpDatabase(self):
        output = open (nextFreeFilename (os.path.join (config.get(prefs.SUPPORT_DIRECTORY), "database-dump.xml")), 'w')
        def indent(level):
            output.write('    ' * level)
        def output_object(table_name, values):
            indent(1)
            if 'id' in values:
                output.write('<%s id="%s">\n' % (table_name, values['id']))
            else:
                output.write('<%s>\n' % (table_name,))
            for key, value in values.items():
                if key == 'id':
                    continue
                indent(2)
                output.write('<%s>' % (key,))
                if isinstance (value, unicode):
                    output.write (value.encode('ascii', 'xmlcharrefreplace'))
                else:
                    output.write (str(value))
                output.write ('</%s>\n' % (key,))
            indent(1)
            output.write ('</%s>\n' % (table_name))
        output.write ('<?xml version="1.0"?>\n')
        output.write ('<database schema="%d">\n' % (self._schema_version,))
        for schema in self._object_schemas:
            self.cursor.execute("SELECT * FROM %s" % schema.table_name)
            column_names = [d[0] for d in self.cursor.description]
            for row in self.cursor:
                output_object(schema.table_name.replace('_', '-'),
                        dict(zip(column_names, row)))
        output.write ('</database>\n')
        output.close()

class SQLiteConverter(object):
    def __init__(self):
        self._to_sql_converters = {}
        self._from_sql_converters = {}

        repr_types = (schema.SchemaTimeDelta,
                schema.SchemaReprContainer,
                schema.SchemaDict,
                schema.SchemaList,
                schema.SchemaStatusContainer,
                )
        for schema_class in repr_types:
            self._to_sql_converters[schema_class] = repr
            self._from_sql_converters[schema_class] = self._convert_repr
        # bools get stored as integers in sqlite
        self._from_sql_converters[schema.SchemaBool] = bool
        # filenames are always stored in sqlite as unicode
        if FilenameType != unicode:
            self._to_sql_converters[schema.SchemaFilename] = filenameToUnicode
            self._from_sql_converters[schema.SchemaFilename] = \
                    self._unicode_to_filename
        # make sure SchemaBinary is always restored as a byte-string
        self._to_sql_converters[schema.SchemaBinary] = buffer
        self._from_sql_converters[schema.SchemaBinary] = self._convert_binary

    def to_sql(self, schema, name, schema_item, value):
        if value is None:
            return None
        converter = self._to_sql_converters.get(schema_item.__class__,
                self._null_convert)
        return converter(value)

    def from_sql(self, schema, name, schema_item, value):
        if value is None:
            return None
        converter = self._from_sql_converters.get(schema_item.__class__,
                self._null_convert)
        try:
            return converter(value)
        except Exception, e:
            handler_name = 'handle_malformed_%s' % name
            if hasattr(schema, handler_name):
                handler = getattr(schema, handler_name)
            else:
                raise
            return handler(value)

    def _unicode_to_filename(self, value):
        return value.encode('utf-8')

    def _null_convert(self, value):
        return value

    def _convert_binary(self, value):
        if isinstance(value, unicode):
            return value.encode('utf-8')
        elif isinstance(value, buffer):
            return str(value)
        else:
            raise TypeError("Unknown type in _convert_binary")

    def _convert_repr(self, value):
        return eval(value, __builtins__, {'datetime': datetime, 'time': _TIME_MODULE_SHADOW})

class TimeModuleShadow:
    """In Python 2.6, time.struct_time is a named tuple and evals poorly,
    so we have struct_time_shadow which takes the arguments that struct_time
    should have and returns a 9-tuple
    """
    def struct_time(self, tm_year=0, tm_mon=0, tm_mday=0, tm_hour=0, tm_min=0, tm_sec=0, tm_wday=0, tm_yday=0, tm_isdst=0):
        return (tm_year, tm_mon, tm_mday, tm_hour, tm_min, tm_sec, tm_wday, tm_yday, tm_isdst)

_TIME_MODULE_SHADOW = TimeModuleShadow()
