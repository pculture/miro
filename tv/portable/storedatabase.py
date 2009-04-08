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

"""storedatabase.py -- Handle database storage.

This module does the reading/writing of our database to/from disk.  It works
with the schema module to validate the data that we read/write and with the
upgradedatabase module to upgrade old database storages.

Datastorage is handled through SQLite.  Each DDBObject class is stored in a
separate table.  Each attribute for that class is saved using a separate
column.

Most columns are stored using SQLite datatypes (INTEGER, REAL, TEXT, DATETIME,
etc.).  However some of our python values, don't have an equivalent (lists,
dicts and timedelta objects).  For those, we store the python representation
of the object.  This makes the column look similar to a JSON value, although
not quite the same.  The hope is that it will be human readable.  We use the
type "pythonrepr" to label these columns.
"""

import cPickle
import itertools
import logging
import datetime
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
from miro import eventloop
from miro import schema
from miro import prefs
from miro import util
from miro.download_utils import nextFreeFilename
from miro.plat.utils import FilenameType, filenameToUnicode

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
      1) Loads the initial object list (and runs database upgrades)
      2) Handles updating the database based on changes to DDBObjects.
    """

    def __init__(self, path=None, object_schemas=None, schema_version=None):
        if path is None:
            path = config.get(prefs.SQLITE_PATHNAME)
        if object_schemas is None:
            object_schemas = schema.object_schemas
        if schema_version is None:
            schema_version = schema.VERSION

        db_existed = os.path.exists(path)
        self._dc = None
        self.path = path
        self.open_connection()
        self._object_schemas = object_schemas
        self._schema_version = schema_version
        self._schema_map = {}
        for oschema in object_schemas:
            table_name = oschema.classString.replace('-', '_')
            self._schema_map[oschema.klass] = (oschema, table_name)
        self._converter = SQLiteConverter()

        if not db_existed:
            self._init_database()

    def open_connection(self):
        self.connection = sqlite3.connect(self.path,
                detect_types=sqlite3.PARSE_DECLTYPES)
        self.cursor = self.connection.cursor()

    def close(self):
        self.commit_transaction()
        if self._dc:
            self._dc.cancel()
            self._dc = None
        self.connection.close()

    def upgrade_database(self):
        """Run any database upgrades that haven't been run."""
        try:
            self._version_table_hack()
            self._upgrade_database()
        except (KeyError, SystemError,
                databaseupgrade.DatabaseTooNewError):
            raise
        except:
            self._handle_load_error("Error upgrading database")

    def _version_table_hack(self):
        """Fix people who have been running the nightly builds and have a
        miro_version table instead of a dtv_variables table (see #11688).
        Delete this function before releasing!
        """
        self.cursor.execute("SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' and name = 'miro_version'")
        if self.cursor.fetchone()[0] > 0:
            logging.warn("fixing dev versions table.")
            self._create_variables_table()
            self.cursor.execute("SELECT version FROM miro_version")
            current_version = self.cursor.fetchone()[0]
            self._set_variable(VERSION_KEY, current_version)
            self.cursor.execute("DROP TABLE miro_version")

    def _upgrade_database(self):
        self._upgrade_20_database()
        current_version = self._get_variable(VERSION_KEY)
        databaseupgrade.new_style_upgrade(self.cursor,
                current_version, self._schema_version)
        self._set_version()

    def _upgrade_20_database(self):
        self.cursor.execute("SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' and name = 'dtv_objects'")
        if self.cursor.fetchone()[0] > 0:
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
        db_value = buffer(cPickle.dumps(value, cPickle.HIGHEST_PROTOCOL))
        self.cursor.execute("REPLACE INTO dtv_variables "
                "(name, serialized_value) VALUES (?,?)", (name, db_value))

    def _create_variables_table(self):
        self.cursor.execute("""CREATE TABLE dtv_variables(
        name TEXT PRIMARY KEY NOT NULL,
        serialized_value BLOB NOT NULL);""")

    def load_objects(self):
        """Get the list of DDBObjects stored on disk."""
        try:
            return self._load_objects()
        except (KeyError, SystemError):
            raise
        except:
            self._handle_load_error("Error loading database")
            return []

    def _load_objects(self):
        retval = []
        for klass, (schema, table_name) in self._schema_map.items():
            column_names = [f[0] for f in schema.fields]
            self.cursor.execute("SELECT %s from %s" % 
                    (', '.join(column_names), table_name))
            for row in self.cursor:
                restored_data = {}
                for (name, schema_item), value in \
                        itertools.izip(schema.fields, row):
                    value = self._converter.from_sql(schema_item, value)
                    restored_data[name] = value
                restored = klass(restored_data=restored_data)
                retval.append(restored)
        return retval

    def commit_transaction(self):
        self.connection.commit()

    def update(self, obj):
        """Update a DDBObject on disk."""

        obj_schema, table_name = self._schema_map[obj.__class__]
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
            values.append(self._converter.to_sql(schema_item, value))
        sql = "REPLACE INTO %s (%s) VALUES(%s)" % (table_name,
                ', '.join(column_names),
                ', '.join('?' for i in xrange(len(column_names))))
        self.cursor.execute(sql, values)
        self._schedule_commit()

    def remove(self, obj):
        """Remove a DDBObject from disk."""

        schema, table_name = self._schema_map[obj.__class__]
        sql = "DELETE FROM %s WHERE id=?" % (table_name)
        self.cursor.execute(sql, (obj.id,))
        self._schedule_commit()

    def table_name(self, klass):
        return self._schema_map[klass][1]

    def _get_query_bottom(self, table_name, where, joins):
        sql = StringIO()
        sql.write("FROM %s\n" % table_name)
        if joins is not None:
            for join_table, join_where in joins.items():
                sql.write('LEFT JOIN %s ON %s\n' % (join_table, join_where))
        sql.write("WHERE %s" % where)
        return sql.getvalue()

    def query(self, klass, where, values=None, order_by=None, joins=None):
        for id in self.query_ids(klass, where, values, order_by, joins):
            yield app.db.getObjectByID(id)

    def query_ids(self, klass, where, values=None, order_by=None, joins=None):
        schema, table_name = self._schema_map[klass]
        sql = StringIO()
        sql.write("SELECT %s.id " % table_name)
        sql.write(self._get_query_bottom(table_name, where, joins))
        if order_by is not None:
            sql.write(" ORDER BY %s" % order_by)
        for row in self._execute(sql.getvalue(), values):
            yield row[0]

    def query_count(self, klass, where, values=None, joins=None):
        schema, table_name = self._schema_map[klass]
        sql = StringIO()
        sql.write('SELECT COUNT(*) ')
        sql.write(self._get_query_bottom(table_name, where, joins))
        return self._execute(sql.getvalue(), values)[0][0]

    def _execute(self, sql, values):
        self.cursor.execute(sql, values)
        start = time.time()
        rows = self.cursor.fetchall()
        end = time.time()
        if (end - start) > 0.1:
            logging.timing("query slow (%0.3f seconds) :%s", end-start, sql)
        return rows

    def _schedule_commit(self):
        """Schedule a commit to run as an idle callback sometime soon."""
        if self._dc is None:
            self._dc = eventloop.addIdle(self._delayed_commit,
                    'commit database')

    def _delayed_commit(self):
        self.commit_transaction()
        self._dc = None

    def _init_database(self):
        """Create a new empty database."""

        for schema in self._object_schemas:
            table_name = schema.classString.replace('-', '_')
            self.cursor.execute("CREATE TABLE %s (%s)" %
                    (table_name, self._calc_sqlite_types(schema)))
        self._create_variables_table()
        self._set_version()

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

    def _calc_obj_values(self, obj):
        schema = self._schema_map[obj.__class__]
        retval = []
        for name, schema_item in schema.fields:
            column_names.append(name)
            value = getattr(obj, name)
            value = self._converter.to_sql(schema_item, value)
            retval.append((name, value))
        return retval

    def dumpDatabase(self, db):
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
            table_name = schema.classString.replace('-', '_')
            self.cursor.execute("SELECT * FROM %s" % table_name)
            column_names = [d[0] for d in self.cursor.description]
            for row in self.cursor:
                output_object(table_name, dict(zip(column_names, row)))
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
            self._from_sql_converters[schema_class] = eval
        # bools get stored as integers in sqlite
        self._from_sql_converters[schema.SchemaBool] = bool
        # filenames are always stored in sqlite as unicode
        if FilenameType != unicode:
            self._to_sql_converters[schema.SchemaFilename] = filenameToUnicode
            self._from_sql_converters[schema.SchemaFilename] = \
                    self._unicode_to_filename

    def to_sql(self, schema_item, value):
        if value is None:
            return None
        converter = self._to_sql_converters.get(schema_item.__class__,
                self._null_convert)
        return converter(value)

    def from_sql(self, schema_item, value):
        if value is None:
            return None
        converter = self._from_sql_converters.get(schema_item.__class__,
                self._null_convert)
        return converter(value)

    def _unicode_to_filename(self, value):
        return value.encode('utf-8')

    def _null_convert(self, value):
        return value
