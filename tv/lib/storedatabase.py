# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

import glob
import shutil
import cPickle
import itertools
import logging
import datetime
import traceback
import time
import os
import sys
from cStringIO import StringIO

try:
    import sqlite3
except ImportError:
    from pysqlite2 import dbapi2 as sqlite3

from miro import app
from miro import crashreport
from miro import convert20database
from miro import databaseupgrade
from miro import dbupgradeprogress
from miro import dialogs
from miro import eventloop
from miro import fileutil
from miro import messages
from miro import schema
from miro import signals
from miro import prefs
from miro import util
from miro.data import fulltextsearch
from miro.data import item
from miro.gtcache import gettext as _
from miro.plat.utils import PlatformFilenameType, filename_to_unicode

class UpgradeError(StandardError):
    """While upgrading the database, we ran out of disk space."""
    pass

class UpgradeErrorSendCrashReport(UpgradeError):
    def __init__(self, report):
        UpgradeError.__init__(self)
        self.report = report

# Which SQLITE type should we use to store SchemaItem subclasses?
_sqlite_type_map = {
        schema.SchemaBool: 'integer',
        schema.SchemaFloat: 'real',
        schema.SchemaString: 'text',
        schema.SchemaBinary:  'blob',
        schema.SchemaURL: 'text',
        schema.SchemaInt: 'integer',
        schema.SchemaDateTime: 'timestamp',
        schema.SchemaTimeDelta: 'text',
        schema.SchemaReprContainer: 'pythonrepr',
        schema.SchemaTuple: 'pythonrepr',
        schema.SchemaDict: 'pythonrepr',
        schema.SchemaList: 'pythonrepr',
        schema.SchemaFilename: 'text',
        schema.SchemaStringSet: 'text',
}

VERSION_KEY = "Democracy Version"

class DatabaseObjectCache(object):
    """Handles caching objects for a database.

    This class implements a generic caching system for DDBObjects.  Other
    components can use it reduce the number of database queries they run.
    """
    def __init__(self):
        # map (category, cache_key) to objects
        self._objects = {}

    def set(self, category, cache_key, obj):
        """Add an object to the cache

        category is an arbitrary name used to separate different caches.  Each
        component that uses DatabaseObjectCache should use a different
        category.

        :param category: unique string
        :param key: key to retrieve the object with
        :param obj: object to add
        """
        self._objects[(category, cache_key)] = obj

    def get(self, category, cache_key):
        """Get an object from the cache

        :param category: category from set
        :param key: key from set
        :returns: object passed in with set
        :raises KeyError: object not in cache
        """
        return self._objects[(category, cache_key)]

    def key_exists(self, category, cache_key):
        """Test if an object is in the cache

        :param category: category from set
        :param key: key from set
        :returns: if an object is present with that key
        """
        return (category, cache_key) in self._objects

    def remove(self, category, cache_key):
        """Remove an object from the cache

        :param category: category from set
        :param key: key from set
        :raises KeyError: object not in cache
        """
        del self._objects[(category, cache_key)]

    def clear(self, category):
        """Clear all objects in a category.

        :param category: category to clear
        """
        for key in self._objects.keys():
            if key[0] == category:
                del self._objects[key]

    def clear_all(self):
        """Clear all objects in the cache"""
        self._objects = {}

class LiveStorageErrorHandler(object):
    """Handle database errors for LiveStorage.
    """

    ( ACTION_QUIT, ACTION_SUBMIT_REPORT, ACTION_START_FRESH, ACTION_RETRY,
     ACTION_USE_TEMPORARY, ACTION_RERAISE, ) = range(6)

    def handle_load_error(self):
        """Handle an error loading the database.

        When LiveStorage hits a load error, it always deletes the database and
        starts fresh.  The only thing to to here is inform the user
        """
        title = _("%(appname)s database corrupt.",
                  {"appname": app.config.get(prefs.SHORT_APP_NAME)})
        description = _(
            "Your %(appname)s database is corrupt.  It will be "
            "backed up in your Miro database directory and a new "
            "database will be created now.",
            {"appname": app.config.get(prefs.SHORT_APP_NAME)})
        dialogs.MessageBoxDialog(title, description).run_blocking()

    def handle_open_error(self):
        """Handle an error opening a new database

        This method should return one of the following:
        - ACTION_RERAISE -- Just re-raise the error
        - ACTION_USE_TEMPORARY -- Use an in-memory database for now and try to
        save the database to disk every so often.
        """
        return self.ACTION_RERAISE

    def handle_upgrade_error(self):
        """Handle an error upgrading the database.

        Returns one of the class attribute constants:
        - ACTION_QUIT -- close miro immediately
        - ACTION_SUBMIT_REPORT -- send a crash report, then close
        - ACTION_START_FRESH -- start with a fresh database
        """
        title = _("%(appname)s database upgrade failed",
                  {"appname": app.config.get(prefs.SHORT_APP_NAME)})
        description = _(
            "We're sorry, %(appname)s was unable to upgrade your database "
            "due to errors.\n\n"
            "Check to see if your disk is full.  If it is full, then quit "
            "%(appname)s, free up some space, and start %(appname)s "
            "again.\n\n"
            "If your disk is not full, help us understand the problem by "
            "reporting a bug to our crash database.\n\n"
            "Finally, you can start fresh and your damaged database will be "
            "removed, but you will have to re-add your podcasts and media "
            "files.", {"appname": app.config.get(prefs.SHORT_APP_NAME)}
            )
        d = dialogs.ThreeChoiceDialog(title, description,
                dialogs.BUTTON_QUIT, dialogs.BUTTON_SUBMIT_REPORT,
                dialogs.BUTTON_START_FRESH)
        choice = d.run_blocking()
        if choice == dialogs.BUTTON_START_FRESH:
            return self.ACTION_START_FRESH
        elif choice == dialogs.BUTTON_SUBMIT_REPORT:
            return self.ACTION_SUBMIT_REPORT
        else:
            return self.ACTION_QUIT

    def handle_save_error(self, error_text, integrity_check_passed):
        """Handle an error when trying to save the database.

        Returns one of the class attribute constants:
        - ACTION_QUIT -- close miro immediately
        - ACTION_RETRY -- try running the statement again
        - ACTION_USE_TEMPORARY -- start fresh using a temporary database
        """

        title = _("%(appname)s database save failed",
                  {"appname": app.config.get(prefs.SHORT_APP_NAME)})
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
            {"appname": app.config.get(prefs.SHORT_APP_NAME),
             "error_text": error_text}
            )
        d = dialogs.DatabaseErrorDialog(title, description)
        if d.run_blocking() == dialogs.BUTTON_RETRY:
            return self.ACTION_RETRY
        else:
            return self.ACTION_QUIT

    def handle_save_succeeded(self):
        """Handle a successful save after retrying

        This will only be called if handle_save_error return ACTION_RETRY.
        """

        title = _("%(appname)s database save succeeded",
                  {"appname": app.config.get(prefs.SHORT_APP_NAME)})
        description = _("The database has been successfully saved. "
                "It is now safe to quit without losing any data.")
        dialogs.MessageBoxDialog(title, description).run()

class DeviceLiveStorageErrorHandler(LiveStorageErrorHandler):
    """Handle database errors for LiveStorage on a device.
    """
    def __init__(self, name):
        self.name = name

    def handle_open_error(self):
        return self.ACTION_USE_TEMPORARY

    def handle_load_error(self):
        title = _("database for device %(name)s corrupt.",
                  {'name' : self.name})
        description = _(
            "The %(appname)s database on your device is corrupt and a "
            "new one will be created.",
            {"appname": app.config.get(prefs.SHORT_APP_NAME)})
        dialogs.MessageBoxDialog(title, description).run_blocking()

    def handle_upgrade_error(self):
        self.handle_load_error()
        return self.ACTION_START_FRESH

    def handle_save_error(self, error_text, integrity_check_passed):
        if not integrity_check_passed:
            # If the database is corrupt, just start over
            logging.warn("Database for %s is corrupt.  Using temporary "
                         "database", self.name)
            return self.ACTION_USE_TEMPORARY


        title = _("Database save failed for device %(name)s.",
                  {'name' : self.name})
        description = _(
            "%(appname)s was unable to save its database on %(device)s.\n\n"
            "If your device is full, we suggest freeing up some space and "
            "retrying.  If your disk is not full, it's possible that "
            "retrying will work.\n\n"
            "If retrying does not work select start fresh to reset the "
            "database to a new one.", {
                "appname": app.config.get(prefs.SHORT_APP_NAME),
                "device": self.name,
            })
        d = dialogs.ChoiceDialog(title, description,
                dialogs.BUTTON_RETRY, dialogs.BUTTON_START_FRESH)
        if d.run_blocking() == dialogs.BUTTON_START_FRESH:
            # we return ACTION_USE_TEMPORARY because we will create a
            # temporary database to start fresh, since it's very likely that
            # loading a new database will fail.  With a temporary database we
            # will try to save it to the disk every so often anyways.
            return self.ACTION_USE_TEMPORARY
        else:
            return self.ACTION_RETRY

    def handle_save_succeeded(self):
        title = _("Device database save succeeded")
        description = _("The database for %(device)s has been successfully "
                        "saved. ", {'device': self.name})
        dialogs.MessageBoxDialog(title, description).run()

class SharingLiveStorageErrorHandler(LiveStorageErrorHandler):
    """Handle database errors for LiveStorage on for a share.

    We always create a new database for shares, so there shouldn't be any
    errors.  If there are, we always start fresh
    """
    def __init__(self, name):
        self.name = name

    def handle_open_error(self):
        return self.ACTION_RERAISE

    def handle_load_error(self):
        return

    def handle_upgrade_error(self):
        return self.ACTION_START_FRESH

    def handle_save_error(self, error_text, integrity_check_passed):
        # FIXME: we should handle this.
        #
        # We shouldn't ever get save errors, so I think the best way to deal
        # with it is simply throw up an error dialog and remove the share tab
        raise NotImplementedError()

    def handle_save_succeeded(self):
        pass

class LiveStorage(signals.SignalEmitter):
    """Handles the storage of DDBObjects.

    This class does basically two things:

    - Loads the initial object list (and runs database upgrades)
    - Handles updating the database based on changes to DDBObjects.

    Attributes:

    - cache -- DatabaseObjectCache object

    Signals:

    - transaction-finished(success) -- We committed or rolled back a
    transaction
    """
    def __init__(self, path=None, error_handler=None, preallocate=None,
                 object_schemas=None, schema_version=None,
                 start_in_temp_mode=False):
        """Create a LiveStorage for a database

        :param path: path to the database (or ":memory:")
        :param error_handler: LiveStorageErrorHandler to use
        :param preallocate: Ensure that approximately at least this much space
            is allocated for the database file
        :param object_schemas: list of schemas to use.  Defaults to
           schema.object_schemas
        :param schema_version: current version of the schema for upgrading
           purposes.  Defaults to schema.VERSION.
        :param start_in_temp_mode: True if this database should start in
                                   temporary mode (running in memory, but
                                   checking if it can write to the disk)
        """
        signals.SignalEmitter.__init__(self)
        self.create_signal("transaction-finished")
        if path is None:
            path = app.config.get(prefs.SQLITE_PATHNAME)
        if error_handler is None:
            error_handler = LiveStorageErrorHandler()
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

        self.temp_mode = False
        self.preallocate = preallocate
        self.error_handler = error_handler
        self.cache = DatabaseObjectCache()
        self.raise_load_errors = False # only gets set in unittests
        self.force_directory_creation = True # False for device databases
        self._query_times = {}
        self.path = path
        self._quitting_from_operational_error = False
        self._object_schemas = object_schemas
        self._schema_version = schema_version
        self._schema_map = {}
        self._schema_column_map = {}
        self._all_schemas = []
        self._object_map = {} # maps object id -> DDBObjects in memory
        self._ids_loaded = set()
        self._statements_in_transaction = []
        eventloop.connect("event-finished", self.on_event_finished)
        for oschema in object_schemas:
            self._all_schemas.append(oschema)
            for klass in oschema.ddb_object_classes():
                self._schema_map[klass] = oschema
                for field_name, schema_item in oschema.fields:
                    klass.track_attribute_changes(field_name)
            for name, schema_item in oschema.fields:
                self._schema_column_map[oschema, name] = schema_item
        self._converter = SQLiteConverter()

        self.open_connection(start_in_temp_mode=start_in_temp_mode)

        self.created_new = self._calc_created_new()
        if self.created_new:
            self._init_database()
        if self.preallocate:
            self._preallocate_space()

    def open_connection(self, path=None, start_in_temp_mode=False):
        if path is None:
            path = self.path
        if start_in_temp_mode:
            self._switch_to_temp_mode()
        else:
            self._ensure_database_directory_exists(path)
            logging.info("opening database %s", path)
            try:
                self.connection = sqlite3.connect(path,
                        isolation_level=None,
                        detect_types=sqlite3.PARSE_DECLTYPES)
            except sqlite3.DatabaseError, e:
                logging.warn("Error opening sqlite database: %s", e)
                action = self.error_handler.handle_open_error()
                if action == LiveStorageErrorHandler.ACTION_RERAISE:
                    raise
                elif action == LiveStorageErrorHandler.ACTION_USE_TEMPORARY:
                    logging.warn("Error opening database %s.  Opening an "
                                 "in-memory database instead", path)
                    self._switch_to_temp_mode()
                else:
                    logging.warn("Bad return value for handle_open_error: %s",
                                 action)
                    raise

        self.cursor = self.connection.cursor()
        if path != ':memory:' and not self.temp_mode:
            self._switch_to_wal_mode()

    def _switch_to_wal_mode(self):
        """Switch to write-ahead logging mode for our connection

        WAL mode allows for better concurency between readers and writers and
        is generally faster than other modes.  See:
        http://www.sqlite.org/wal.html
        """
        try:
            self.cursor.execute("PRAGMA journal_mode=wal");
        except sqlite3.DatabaseError:
            msg = "Error running 'PRAGMA journal_mode=wal'"
            self.error_handler.handle_load_error()
            self._handle_load_error(msg, init_schema=False)
            # rerun the command with our fresh database
            self.cursor.execute("PRAGMA journal_mode=wal");
        # check that we actually succesfully switch to wal mode
        actual_mode = self.cursor.fetchall()[0][0]
        if actual_mode != u'wal' and not hasattr(app, 'in_unit_tests'):
            logging.warn("PRAGMA journal_mode=wal didn't change the "
                         "mode.  journal_mode=%s", actual_mode)

    def _ensure_database_directory_exists(self, path):
        if not self.force_directory_creation:
            return
        if path != ':memory:' and not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

    def _switch_to_temp_mode(self):
        """Switch to temporary mode.

        In temporary mode, we use an in-memory database and try to save it to
        disk every 5 minutes.  Temporary mode is used to handle errors when
        trying to open a database file.
        """
        self.connection = sqlite3.connect(':memory:',
                                          isolation_level=None,
                                          detect_types=sqlite3.PARSE_DECLTYPES)
        self.temp_mode = True
        eventloop.add_timeout(300,
                              self._try_save_temp_to_disk,
                              "write in-memory sqlite database to disk")

    def _try_save_temp_to_disk(self):
        if not self.temp_mode: # already fixed, move along
            return
        try:
            self._change_path(self.path)
        except StandardError, e:
            logging.warn("_try_save_temp_to_disk failed: %s (path: %s)", e,
                         self.path, exc_info=True)
            eventloop.add_timeout(300,
                                  self._try_save_temp_to_disk,
                                  "write in-memory sqlite database to disk")
        else:
            logging.warn("Sucessfully wrote database to %s.  Changes "
                         "will now be saved as normal.", self.path)

    def _copy_data_to_path(self, new_path):
        """Copy the contents of our database to a new file.  """
        self.finish_transaction()
        # add the database at new_path to our current connection
        self._ensure_database_directory_exists(new_path)
        # delete any data currently at new_path
        if os.path.exists(new_path):
            os.remove(new_path)
        self.cursor.execute("ATTACH ? as newdb",
                            (filename_to_unicode(new_path),))
        self.cursor.execute("BEGIN TRANSACTION")
        try:
            self._copy_data_to_newdb()
        finally:
            self.cursor.execute("COMMIT TRANSACTION")
            self.cursor.execute("DETACH newdb")

    def _copy_data_to_newdb(self):
        # copy current schema
        self.cursor.execute("SELECT name, sql FROM main.sqlite_master "
                            "WHERE type='table'")
        def should_recreate_table(table_name):
            if (table_name.endswith("fts_content") or
                table_name.endswith("fts_segments") or
                table_name.endswith("fts_stat") or
                table_name.endswith("fts_docsize") or
                table_name.endswith("fts_segdir") or
                table_name.startswith("sqlite_")):
                # these tables are auto-generated by sqlite
                return False
            return True
        table_info = [(table, sql) for (table, sql) in self.cursor.fetchall()
                      if should_recreate_table(table)]

        for table, sql in table_info:
            sql = sql.replace("TABLE %s" % table,
                              "TABLE newdb.%s" % table)
            self.cursor.execute(sql)
            self.cursor.execute("SELECT name, sql FROM sqlite_master "
                                "WHERE type='index' AND tbl_name=?",
                                (table,))
            for index, sql in self.cursor.fetchall():
                if index.startswith('sqlite_'):
                    continue
                sql = sql.replace("INDEX %s" % index,
                                  "INDEX newdb.%s" % index)
                self.cursor.execute(sql)
        # preallocate space now.  We want to fail fast if the disk is full
        if self.preallocate:
            self._preallocate_space(db_name='newdb')

        # copy data
        for table, sql in table_info:
            self.cursor.execute("INSERT INTO newdb.%s SELECT * FROM main.%s" %
                                (table, table))

        # create triggers
        self.cursor.execute("SELECT name, sql FROM sqlite_master "
                            "WHERE type='trigger'")
        for (name, sql,) in self.cursor.fetchall():
            self.cursor.execute(sql.replace(name, "newdb." + name))

    def _change_path(self, new_path):
        """Change the path of our database.

        This method copies the entire current database to new_path, then opens
        a connection to it.
        """
        self._copy_data_to_path(new_path)
        # Looks like everything worked.  Change to using a connection to the
        # new database
        self.path = new_path
        self.connection.close()
        self.open_connection()
        self.temp_mode = False

    def check_integrity(self):
        """Run an integrity check on our database

        :returns True if the integrity check passed.
        """

        try:
            self.cursor.execute("PRAGMA integrity_check")
            return self.cursor.fetchall() == [
                ('ok',),
            ]
        except sqlite3.DatabaseError:
            logging.warn("error running PRAGMA integrity_check: %s",
                         exc_info=True)
            return False

    def close(self):
        if self.connection is not None:
            logging.info("closing database")
            self.finish_transaction()
            self.connection.close()
            self.connection = None

    def is_closed(self):
        return self.connection is None

    def get_backup_directory(self):
        """This returns the backup directory path.

        It has the side effect of creating the directory, too, if it
        doesn't already exist.  If the dbbackups directory doesn't exist
        and it can't build a new one, then it returns the directory the
        database is in.
        """
        path = os.path.join(os.path.dirname(self.path), "dbbackups")
        if not os.path.exists(path):
            try:
                fileutil.makedirs(path)
            except OSError:
                # if we can't make the backups dir, we just stick it in
                # the same directory
                path = os.path.dirname(self.path)
        return path

    backup_filename_prefix = "sqlitedb_backup"

    def get_backup_databases(self):
        return glob.glob(os.path.join(
            self.get_backup_directory(),
            LiveStorage.backup_filename_prefix + "*"))

    def upgrade_database(self, context='main'):
        """Run any database upgrades that haven't been run.

        :param context: context for the upgrade, either "main" for the main
        database or "device" for the device database.
        """
        try:
            self._upgrade_database(context)
        except StandardError, e:
            logging.exception('error when upgrading database: %s', e)
            self._handle_upgrade_error()

    def _backup_failed_upgrade_db(self):
        save_name = self._find_unused_db_name(self.path, "failed_upgrade_database")
        path = os.path.join(os.path.dirname(self.path), save_name)
        self._copy_data_to_path(path)
        logging.warn("upgrade failed. Backing up database to %s", path)

    def _handle_upgrade_error(self):
        # commit any unsaved changes that the upgrade was in the process of
        # making
        self.cursor.execute("COMMIT TRANSACTION")
        self._backup_failed_upgrade_db()
        action = self.error_handler.handle_upgrade_error()
        if action == LiveStorageErrorHandler.ACTION_START_FRESH:
            self._handle_load_error("Error upgrading database")
            self.startup_version = self.current_version = self.get_version()
        elif action == LiveStorageErrorHandler.ACTION_SUBMIT_REPORT:
            report = crashreport.format_crash_report("Upgrading Database",
                    exc_info=sys.exc_info(), details=None)
            raise UpgradeErrorSendCrashReport(report)
        elif action == LiveStorageErrorHandler.ACTION_QUIT:
            raise UpgradeError()
        else:
            logging.warn("Bad return value for handle_upgrade_error: %s",
                         action)
            raise

    def _change_database_file(self, ver):
        """Switches the sqlitedb file that we have open

        This is called before doing a database upgrade.  This allows
        us to keep the database file unmodified in case the upgrade
        fails.

        It also creates a backup in the backups/ directory of the
        database.

        :param ver: the current version (as string)
        """
        logging.info("database path: %s", self.path)

        # copy the db to a backup file for posterity
        target_path = self.get_backup_directory()
        save_name = self._find_unused_db_name(
            target_path, "%s_%s" % (LiveStorage.backup_filename_prefix, ver))
        self._copy_data_to_path(os.path.join(target_path, save_name))

        # copy the db to the file we're going to operate on
        target_path = os.path.dirname(self.path)
        save_name = self._find_unused_db_name(
            target_path, "upgrading_database_%s" % ver)
        self._copy_data_to_path(os.path.join(target_path, save_name))

        self._changed_db_path = os.path.join(target_path, save_name)
        self.connection.close()
        self.open_connection(self._changed_db_path)

    def _change_database_file_back(self):
        """Switches the sqlitedb file back to our regular one.

        This works together with _change_database_file() to handle database
        upgrades.  Once the upgrade is finished, this method copies the
        database we were using to the normal place, and switches our sqlite
        connection to use that file
        """
        # _changed_db_path uses the default journal mode instead of WAL mode,
        # so we can do a simple move here instead of using
        # _copy_data_to_path()
        self.connection.close()
        shutil.move(self._changed_db_path, self.path)
        self.open_connection()
        del self._changed_db_path

    def show_upgrade_progress(self):
        return True

    def _upgrade_database(self, context):
        self.startup_version = current_version = self.get_version()

        if current_version > self._schema_version:
            msg = _("Database was created by a newer version of %(appname)s "
                    "(db version is %(version)s)",
                    {"appname": app.config.get(prefs.SHORT_APP_NAME),
                     "version": current_version})
            raise databaseupgrade.DatabaseTooNewError(msg)

        if current_version < self._schema_version:
            self._upgrade_20_database()
            # need to pull the variable again here because
            # _upgrade_20_database will have done an upgrade
            if self.show_upgrade_progress():
                dbupgradeprogress.doing_new_style_upgrade()
            current_version = self.get_version()
            self._change_database_file(current_version)
            databaseupgrade.new_style_upgrade(self.cursor,
                                              current_version,
                                              self._schema_version,
                                              context,
                                              self.show_upgrade_progress())
            self.set_version()
            self._change_database_file_back()
        self.current_version = self._schema_version

    def _upgrade_20_database(self):
        self.cursor.execute("SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' and name = 'dtv_objects'")
        if self.cursor.fetchone()[0] > 0:
            current_version = self.get_version()
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
                self._change_database_file("pre80")
                if self.show_upgrade_progress():
                    dbupgradeprogress.doing_20_upgrade()

                if util.chatter:
                    logging.info("converting pre 2.1 database")
                convert20database.convert(self.cursor,
                                          self.show_upgrade_progress())
                self.set_version(80)
                self._change_database_file_back()

    def get_variable(self, name):
        self.cursor.execute("SELECT serialized_value FROM dtv_variables "
                "WHERE name=?", (name,))
        row = self.cursor.fetchone()
        if row is None:
            raise KeyError(name)
        return cPickle.loads(str(row[0]))

    def set_variable(self, name, value, db_name='main'):
        # we only store one variable and it's easier to deal with if we store
        # it using ASCII-base protocol.
        db_value = buffer(cPickle.dumps(value, 0))
        self.execute("REPLACE INTO %s.dtv_variables "
                      "(name, serialized_value) VALUES (?,?)" % db_name,
                      (name, db_value),
                      is_update=True)
        self.finish_transaction()

    def unset_variable(self, name, db_name='main'):
        self.execute("DELETE FROM %s.dtv_variables "
                      "WHERE name=?" % db_name,
                      (name,), is_update=True)
        self.finish_transaction()

    def _create_variables_table(self):
        self.cursor.execute("""CREATE TABLE dtv_variables(
        name TEXT PRIMARY KEY NOT NULL,
        serialized_value BLOB NOT NULL);""")

    def simulate_db_save_error(self):
        """Simulate trying to save something to the database and getting an
        Operational Error.
        """
        # The below code is fairly dirty, but it's only executed from a devel
        # menu item, so it should be okay
        # Make it so that the next attempt (and only that attempt) to execute
        # a query results in an error.
        old_time_execute = self._time_execute
        def time_execute_intercept(*args, **kwargs):
            self._time_execute = old_time_execute
            raise sqlite3.DatabaseError()
        self._time_execute = time_execute_intercept
        # force the db to execute sql
        self.execute("REPLACE INTO dtv_variables "
                      "(name, serialized_value) VALUES (?,?)",
                      ('simulate_db_save_error', 1), is_update=True)

    def remember_object(self, obj):
        key = (obj.id, obj.db_info.db.table_name(obj.__class__))
        self._object_map[key] = obj
        self._ids_loaded.add(key)

    def forget_object(self, obj):
        key = (obj.id, obj.db_info.db.table_name(obj.__class__))
        try:
            del self._object_map[key]
        except KeyError:
            details = ('storedatabase.forget_object: '
                       'key error in forget_object: %s (obj: %s)' %
                       (obj.id, obj))
            logging.error(details)
        self._ids_loaded.discard(key)

    def forget_all_objects(self):
        self._object_map = {}
        self._ids_loaded = set()

    def _insert_sql_for_schema(self, obj_schema):
        return "INSERT INTO %s (%s) VALUES(%s)" % (obj_schema.table_name,
                ', '.join(name for name, schema_item in obj_schema.fields),
                ', '.join('?' for i in xrange(len(obj_schema.fields))))

    def _values_for_obj(self, obj_schema, obj):
        values = []
        for name, schema_item in obj_schema.fields:
            value = getattr(obj, name)
            try:
                schema_item.validate(value)
            except schema.ValidationError, e:
                logging.warn("error validating %s for %s (%s)", name, obj, e)
                raise
            values.append(self._converter.to_sql(obj_schema, name,
                schema_item, value))
        return values

    def insert_obj(self, obj):
        """Add a new DDBObject to disk."""

        obj_schema = self._schema_map[obj.__class__]
        values = self._values_for_obj(obj_schema, obj)
        sql = self._insert_sql_for_schema(obj_schema)
        self.execute(sql, values, is_update=True)
        obj.reset_changed_attributes()

    def bulk_insert(self, objects):
        """Insert a list of objects in one go.

        Throws a ValueError if the objects don't all use the same database
        table.
        """
        if len(objects) == 0:
            return
        obj_schema = self._schema_map[objects[0].__class__]
        value_list = []
        for obj in objects:
            if obj_schema != self._schema_map[obj.__class__]:
                raise ValueError("Incompatible types for bulk insert")
            value_list.append(self._values_for_obj(obj_schema, obj))
        sql = self._insert_sql_for_schema(obj_schema)
        self.execute(sql, value_list, is_update=True, many=True)
        for obj in objects:
            obj.reset_changed_attributes()

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
                logging.warn("error validating %s for %s", name, obj)
                raise
            values.append(self._converter.to_sql(obj_schema, name,
                schema_item, value))
        obj.reset_changed_attributes()
        if values:
            sql = "UPDATE %s SET %s WHERE id=%s" % (obj_schema.table_name,
                    ', '.join(setters), obj.id)
            self.execute(sql, values, is_update=True)
            if (self.cursor.rowcount != 1 and not
                    self._quitting_from_operational_error):
                if self.cursor.rowcount == 0:
                    raise KeyError("Updating non-existent row (id: %s)" %
                            obj.id)
                else:
                    raise ValueError("Update changed multiple rows "
                            "(id: %s, count: %s)" %
                            (obj.id, self.cursor.rowcount))

    def remove_obj(self, obj):
        """Remove a DDBObject from disk."""

        schema = self._schema_map[obj.__class__]
        sql = "DELETE FROM %s WHERE id=?" % (schema.table_name)
        self.execute(sql, (obj.id,), is_update=True)
        self.forget_object(obj)

    def bulk_remove(self, objects):
        """Remove a list of objects in one go.

        Throws a ValueError if the objects don't all use the same database
        table.
        """

        if len(objects) == 0:
            return
        obj_schema = self._schema_map[objects[0].__class__]
        for obj in objects:
            if obj_schema != self._schema_map[obj.__class__]:
                raise ValueError("Incompatible types for bulk remove")
        # we can only feed sqlite so many variables at once, send it chunks of
        # 900 ids at once
        for objects_chunk in util.split_values_for_sqlite(objects):
            commas = ','.join('?' for x in xrange(len(objects_chunk)))
            sql = "DELETE FROM %s WHERE id IN (%s)" % (obj_schema.table_name,
                    commas)
            self.execute(sql, [o.id for o in objects_chunk], is_update=True)
        for obj in objects:
            self.forget_object(obj)

    def get_last_id(self):
        try:
            return self._get_last_id()
        except StandardError:
            self.error_handler.handle_load_error()
            self._handle_load_error("Error calculating last id")
            return self._get_last_id()

    def _get_last_id(self):
        max_id = 0
        for schema in self._object_schemas:
            self.cursor.execute("SELECT MAX(id) FROM %s" % schema.table_name)
            max_id = max(max_id, self.cursor.fetchone()[0])
        return max_id

    def get_obj_by_id(self, id_, klass):
        """Get a particular DDBObject.

        This will throw a KeyError if id is not in the database, or if the
        object for id has not been loaded yet.
        """
        return self._object_map[(id_, self.table_name(klass))]

    def id_alive(self, id_, klass):
        """Check if an id exists and is loaded in the database."""
        return (id_, self.table_name(klass)) in self._object_map

    def fetch_item_infos(self, item_ids):
        return item.fetch_item_infos(self.connection, item_ids)

    def table_name(self, klass):
        return self._schema_map[klass].table_name

    def schema_fields(self, klass):
        return self._schema_map[klass].fields

    def object_from_class_table(self, obj, klass):
        return self._schema_map[klass] is self._schema_map[obj.__class__]

    def _get_query_bottom(self, table_name, where, joins, order_by, limit):
        sql = StringIO()
        sql.write("FROM %s\n" % table_name)
        if joins is not None:
            for join_table, join_where in joins.items():
                sql.write('LEFT JOIN %s ON %s\n' % (join_table, join_where))
        if where is not None:
            sql.write("WHERE %s" % where)
        if order_by is not None:
            sql.write(" ORDER BY %s" % order_by)
        if limit is not None:
            sql.write(" LIMIT %s" % limit)
        return sql.getvalue()

    def ensure_objects_loaded(self, klass, id_list, db_info):
        """Ensure that a list of ids are loaded into memory.

        :returns: True iff we needed to load objects
        """
        table_name = self.table_name(klass)
        unrestored_ids = []
        for id_ in id_list:
            if (id_, table_name) not in self._ids_loaded:
                unrestored_ids.append(id_)
        if unrestored_ids:
            # restore any objects that we don't already have in memory.
            schema = self._schema_map[klass]
            self._restore_objects(schema, unrestored_ids, db_info)
            return True
        return False

    def query_ids(self, table_name, where, values=None, order_by=None,
            joins=None, limit=None):
        sql = StringIO()
        sql.write("SELECT %s.id " % table_name)
        sql.write(self._get_query_bottom(table_name, where, joins,
            order_by, limit))
        self.cursor.execute(sql.getvalue(), values)
        return (row[0] for row in self.cursor.fetchall())

    def _restore_objects(self, schema, id_set, db_info):
        column_names = ['%s.%s' % (schema.table_name, f[0])
                for f in schema.fields]

        # we can only feed sqlite so many variables at once, send it chunks of
        # 900 ids at once
        id_list = tuple(id_set)
        for id_list_chunk in util.split_values_for_sqlite(id_list):
            sql = StringIO()
            sql.write("SELECT %s " % (', '.join(column_names),))
            sql.write("FROM %s WHERE id IN (%s)" % (schema.table_name, 
                ', '.join('?' for i in xrange(len(id_list_chunk)))))

            self.cursor.execute(sql.getvalue(), id_list_chunk)
            for row in self.cursor.fetchall():
                self._restore_object_from_row(schema, row, db_info)

    def _restore_object_from_row(self, schema, db_row, db_info):
        restored_data = {}
        columns_to_update = []
        values_to_update = []
        for (name, schema_item), value in \
                itertools.izip(schema.fields, db_row):
            try:
                value = self._converter.from_sql(schema, name, schema_item,
                        value)
            except StandardError:
                logging.exception('self._converter.from_sql failed.')
                handler = self._converter.get_malformed_data_handler(schema,
                        name, schema_item, value)
                if handler is None:
                    if util.chatter:
                        logging.warn("error converting %s (%r)", name, value)
                    raise
                try:
                    value = handler(value)
                except StandardError:
                    if util.chatter:
                        logging.warn("error converting %s (%r)", name, value)
                    raise
                columns_to_update.append(name)
                values_to_update.append(self._converter.to_sql(schema, name,
                    schema_item, value))
            restored_data[name] = value
        if columns_to_update:
            # We are using some values that are different than what's stored
            # in disk.  Update the database to make things match.
            setters = ['%s=?' % c for c in columns_to_update]
            sql = "UPDATE %s SET %s WHERE id=%s" % (schema.table_name,
                    ', '.join(setters), restored_data['id'])
            self.execute(sql, values_to_update)
        klass = schema.get_ddb_class(restored_data)
        return klass(restored_data=restored_data, db_info=db_info)

    def persistent_object_count(self):
        return len(self._object_map)

    def query_count(self, table_name, where, values=None, joins=None,
            limit=None):
        sql = StringIO()
        sql.write('SELECT COUNT(*) ')
        sql.write(self._get_query_bottom(table_name, where, joins,
            None, limit))
        return self.execute(sql.getvalue(), values)[0][0]

    def delete(self, klass, where, values):
        schema = self._schema_map[klass]
        sql = StringIO()
        sql.write('DELETE FROM %s' % schema.table_name)
        if where is not None:
            sql.write('\nWHERE %s' % where)
        self.execute(sql.getvalue(), values, is_update=True)

    def select(self, klass, columns, where, values, joins=None, limit=None,
            convert=True):
        schema = self._schema_map[klass]
        sql = StringIO()
        sql.write('SELECT %s ' % ', '.join(columns))
        sql.write(self._get_query_bottom(schema.table_name, where, joins, None,
            limit))
        results = self.execute(sql.getvalue(), values)
        if not convert:
            return results
        schema_items = [self._schema_column_map[schema, c] for c in columns]
        rows = []
        for row in results:
            converted_row = []
            for name, schema_item, value in itertools.izip(columns,
                    schema_items, row):
                converted_row.append(self._converter.from_sql(schema, name,
                    schema_item, value))
            rows.append(converted_row)
        return rows

    def on_event_finished(self, eventloop, success):
        self.finish_transaction(commit=success)

    def finish_transaction(self, commit=True):
        if len(self._statements_in_transaction) == 0:
            return
        if not self._quitting_from_operational_error:
            if commit:
                self.cursor.execute("COMMIT TRANSACTION")
            else:
                self.cursor.execute("ROLLBACK TRANSACTION")
        self._statements_in_transaction = []
        self.emit("transaction-finished", commit)

    def execute(self, sql, values=None, is_update=False, many=False):
        """Execute an sql statement and return the results.

        :param sql: sql to execute
        :param values: positional arguments for the sql statement
        :param is_update: is this an update rather than a select?
        :param many: use the execute_many() method instead of execute().
        values should be a list of argument tuples if this is true.
        :returns: list of result rows, or None if the statement is an update.
        """

        if is_update and self._quitting_from_operational_error:
            # We want to avoid updating the database at this point.
            return

        if is_update and len(self._statements_in_transaction) == 0:
            self.cursor.execute("BEGIN TRANSACTION")

        if values is None:
            values = ()

        if is_update:
            self._statements_in_transaction.append((sql, values, many))
        try:
            self._time_execute(sql, values, many)
        except sqlite3.DatabaseError, e:
            self._log_error(sql, values, many, e)
            if is_update:
                self._current_select_statement = None
            else:
                # Make sure we re-run our SELECT statement so that the call to
                # fetchall() at the end of this method works. (#12885)
                self._current_select_statement = (sql, values, many)
            self._handle_operational_error(e, is_update)
        except StandardError, e:
            self._log_error(sql, values, many, e)
            raise

        if is_update:
            return None
        else:
            return self.cursor.fetchall()

    def _time_execute(self, sql, values, many):
        start = time.time()
        if many:
            self.cursor.executemany(sql, values)
        else:
            self.cursor.execute(sql, values)
        end = time.time()
        self._check_time(sql, end-start)

    def _log_error(self, sql, values, many, e):
            # printing the traceback here in whole rather than doing
            # a logging.exception which seems to show the traceback
            # up to the try/except handler.
            logging.error("%s while executing SQL\n"
                          "statement: %s\n\n"
                          "values: %s\n\n"
                          "many: %s\n\n", e, sql, values, many, exc_info=True)

    def _try_rerunning_transaction(self):
        if self._statements_in_transaction:
            # We may have only been trying to execute SELECT statements.  If
            # that's true, don't start a transaction. (#12885)
            self.cursor.execute("BEGIN TRANSACTION")
        to_run = self._statements_in_transaction[:]
        if self._current_select_statement:
            to_run.append(self._current_select_statement)
        for (sql, values, many) in to_run:
            try:
                self._time_execute(sql, values, many)
            except sqlite3.DatabaseError, e:
                self._log_error(sql, values, many, e)
                return False
        return True

    def _handle_operational_error(self, e, is_update):
        if self._quitting_from_operational_error:
            return
        succeeded = False
        while True:
            # try to rollback our old transaction if SQLite hasn't done it
            # automatically
            try:
                self.cursor.execute("ROLLBACK TRANSACTION")
            except sqlite3.DatabaseError:
                pass
            retry = self._handle_query_error(str(e))
            if not retry:
                break
            if self._try_rerunning_transaction():
                succeeded = True
                break

        if not succeeded and not is_update:
            logging.warn("re-raising SQL error because it was not an update")
            # This is a very bad state to be in because code calling
            # us expects a return value.  I think the best we can do
            # is re-raise the exception (BDK)
            raise

        if succeeded:
            self.error_handler.handle_save_succeeded()

    def _handle_query_error(self, error_text):
        """Handle an error running an SQL query.

        :returns: True if we should try to re-run the query
        """
        integrity_check_passed = self.check_integrity()
        action = self.error_handler.handle_save_error(error_text,
                                                      integrity_check_passed)
        if action == LiveStorageErrorHandler.ACTION_QUIT:
            self._quitting_from_operational_error = True
            return False
        elif action == LiveStorageErrorHandler.ACTION_RETRY:
            logging.warn("Re-running SQL statement")
            return True
        elif action == LiveStorageErrorHandler.ACTION_USE_TEMPORARY:
            self._switch_to_temp_mode()
            # reset _statements_in_transaction.  The data for the old DB is
            # now lost
            self._statements_in_transaction = []
            self.cursor = self.connection.cursor()
            self._init_database()
            return False
        else:
            logging.warn("Bad return value for handle_save_error: %s", action)
            raise

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

    def _calc_created_new(self):
        """Decide if the database that we just opened is new."""
        self.cursor.execute("SELECT COUNT(*) FROM sqlite_master "
                            "WHERE type='table'")
        return self.cursor.fetchone()[0] == 0

    def _init_database(self):
        """Create a new empty database."""

        for schema in self._object_schemas:
            type_specs = [self._create_sql_for_column(name, schema_item)
                          for (name, schema_item) in schema.fields]
            self.cursor.execute("CREATE TABLE %s (%s)" %
                    (schema.table_name, ', '.join(type_specs)))
            for name, columns in schema.indexes:
                self.cursor.execute("CREATE INDEX %s ON %s (%s)" %
                        (name, schema.table_name, ', '.join(columns)))
            for name, columns in schema.unique_indexes:
                self.cursor.execute("CREATE UNIQUE INDEX %s ON %s (%s)" %
                        (name, schema.table_name, ', '.join(columns)))
        self._create_variables_table()
        self.set_version()
        self.setup_fulltext_search()

    def setup_fulltext_search(self):
        fulltextsearch.setup_fulltext_search(self.connection)

    def _get_size_info(self):
        """Get info about the database size

        :returns: (page_size, page_count, freelist_count) tuple or None if
        there's an error getting the size info
        """
        rv = []
        for name in ('page_size', 'page_count', 'freelist_count'):
            sql = 'PRAGMA %s' % name
            self.cursor.execute(sql)
            row = self.cursor.fetchone()
            if row is None:
                # not sure why this happens, but it does #18633
                logging.warn("_get_size_info(): error running %s", sql)
                return None
            rv.append(row[0])
        return rv

    def _preallocate_space(self, db_name='main'):
        if db_name == 'main':
            size_info = self._get_size_info()
            if size_info is None:
                logging.warn("_get_size_info() returned None.  Not "
                             "preallocating space for: %s", self.path)
                return
            page_size, page_count, freelist_count = size_info
            current_size = page_size * (page_count + freelist_count)
        else:
            # HACK: We can't get size counts for attached databases so we just
            # assume that the database is empty of content
            current_size = 0
        size = self.preallocate - current_size
        if size > 0:
            # make a row that's big enough so that our database will be
            # approximately preallocate bytes large
            self.cursor.execute("REPLACE INTO %s.dtv_variables "
                                "(name, serialized_value) "
                                "VALUES ('preallocate', zeroblob(%s))" %
                                (db_name, size))
            # delete the row, sqlite will keep the space allocate until the
            # VACUUM command.  And we won't ever send a VACUUM.
            self.cursor.execute("DELETE FROM %s.dtv_variables "
                                "WHERE name='preallocate'" % (db_name,))

    def get_version(self):
        return self.get_variable(VERSION_KEY)

    def set_version(self, version=None, db_name='main'):
        """Set the database version to the current schema version."""

        if version is None:
            version = self._schema_version
        self.set_variable(VERSION_KEY, version, db_name)

    def get_sqlite_type(self, item_schema):
        """Get sqlite type to use for a schema item_schema
        """

        return _sqlite_type_map[item_schema.__class__]

    def _create_sql_for_column(self, column_name, item_schema):
        typ = self.get_sqlite_type(item_schema)
        if column_name != 'id':
            return '%s %s' % (column_name, typ)
        else:
            return '%s %s PRIMARY KEY' % (column_name, typ)

    def reset_database(self, init_schema=True):
        """Saves the current database then starts fresh with an empty
        database.

        :param init_schema: should we create tables for our schema?
        """
        self.connection.close()
        self.save_invalid_db()
        self.open_connection()
        if init_schema:
            self._init_database()

    def _handle_load_error(self, message, init_schema=True):
        """Handle errors happening when we try to load the database.  Our
        basic strategy is to log the error, save the current database then
        start fresh with an empty database.
        """
        if self.raise_load_errors:
            raise
        if util.chatter:
            logging.exception(message)
        self.reset_database(init_schema)

    def save_invalid_db(self):
        target_path = os.path.dirname(self.path)
        save_name = self._find_unused_db_name(
            target_path, "corrupt_database")
        os.rename(self.path, os.path.join(target_path, save_name))

    def _find_unused_db_name(self, target_path, save_name):
        org_save_name = save_name
        i = 0
        while os.path.exists(os.path.join(target_path, save_name)):
            i += 1
            save_name = "%s.%d" % (org_save_name, i)
        return save_name

class DeviceLiveStorage(LiveStorage):
    """Version of LiveStorage used for a device."""
    def setup_fulltext_search(self):
        fulltextsearch.setup_fulltext_search(self.connection, 'device_item')

    def show_upgrade_progress(self):
        return False

class SharingLiveStorage(LiveStorage):
    """Version of LiveStorage used for a device."""

    def __init__(self, path, share_name, object_schemas):
        error_handler = SharingLiveStorageErrorHandler(share_name)
        if os.path.exists(path):
            raise ValueError("SharingLiveStorage should only be created with "
                             "a non-existent path")
        LiveStorage.__init__(self, path, error_handler,
                             object_schemas=object_schemas)

    def open_connection(self, path=None, start_in_temp_mode=False):
        LiveStorage.open_connection(self, path, start_in_temp_mode)
        # execute a bunch of PRAGMA statements that make things faster at the
        # expense of reliability in case of a crash.  Since we open a new DB
        # every time there's no risk.
        self.cursor.execute("PRAGMA synchronous=OFF")
        self.cursor.execute("PRAGMA temp_store=MEMORY")
        self.cursor.execute("PRAGMA journal_mode=MEMORY")

    def setup_fulltext_search(self):
        fulltextsearch.setup_fulltext_search(self.connection, 'sharing_item',
                                             path_column='video_path',
                                             has_entry_description=False)

class SQLiteConverter(object):
    def __init__(self):
        self._to_sql_converters = {
                schema.SchemaBinary: self._binary_to_sql,
                schema.SchemaFilename: self._filename_to_sql,
                schema.SchemaStringSet: self._string_set_to_sql,
                schema.SchemaTimeDelta: self._timedelta_to_sql,
        }

        self._from_sql_converters = {
                schema.SchemaBool: self._bool_from_sql,
                schema.SchemaBinary: self._binary_from_sql,
                schema.SchemaFilename: self._filename_from_sql,
                schema.SchemaStringSet: self._string_set_from_sql,
                schema.SchemaTimeDelta: self._timedelta_from_sql,
        }

        repr_types = ( schema.SchemaReprContainer,
                schema.SchemaTuple,
                schema.SchemaDict,
                schema.SchemaList,
                )
        for schema_class in repr_types:
            self._to_sql_converters[schema_class] = self._repr_to_sql
            self._from_sql_converters[schema_class] = self._repr_from_sql

    def to_sql(self, schema, name, schema_item, value):
        if value is None:
            return None
        converter = self._to_sql_converters.get(schema_item.__class__,
                self._null_convert)
        return converter(value, schema_item)

    def from_sql(self, schema, name, schema_item, value):
        if value is None:
            return None
        converter = self._from_sql_converters.get(schema_item.__class__,
                self._null_convert)
        return converter(value, schema_item)

    def get_malformed_data_handler(self, schema, name, schema_item, value):
        handler_name = 'handle_malformed_%s' % name
        if hasattr(schema, handler_name):
            return getattr(schema, handler_name)
        else:
            return None

    def _unicode_to_filename(self, value):
        # reverses filename_to_unicode().  We can't use the platform
        # unicode_to_filename() because that also cleans out the filename.
        # This code is not very good and should be replaces as part of #13182
        if value is not None and PlatformFilenameType != unicode:
            return value.encode('utf-8')
        else:
            return value

    def _null_convert(self, value, schema_item):
        return value

    def _bool_from_sql(self, value, schema_item):
        # bools are stored as integers in the DB.
        return bool(value)

    def _binary_to_sql(self, value, schema_item):
        return buffer(value)

    def _binary_from_sql(self, value, schema_item):
        if isinstance(value, unicode):
            return value.encode('utf-8')
        elif isinstance(value, buffer):
            return str(value)
        else:
            raise TypeError("Unknown type in _convert_binary")

    def _filename_from_sql(self, value, schema_item):
        return self._unicode_to_filename(value)

    def _filename_to_sql(self, value, schema_item):
        return filename_to_unicode(value)

    def _repr_to_sql(self, value, schema_item):
        return repr(value)

    def _repr_from_sql(self, value, schema_item):
        return eval(value, __builtins__, {'datetime': datetime, 'time': _TIME_MODULE_SHADOW})

    def _string_set_to_sql(self, value, schema_item):
        return schema_item.delimiter.join(value)

    def _string_set_from_sql(self, value, schema_item):
        return set(value.split(schema_item.delimiter))

    def _timedelta_to_sql(self, value, schema_item):
        return ':'.join((str(value.days), str(value.seconds),
                         str(value.microseconds)))

    def _timedelta_from_sql(self, value, schema_item):
        return datetime.timedelta(*(int(c) for c in value.split(":")))

class TimeModuleShadow:
    """In Python 2.6, time.struct_time is a named tuple and evals poorly,
    so we have struct_time_shadow which takes the arguments that struct_time
    should have and returns a 9-tuple
    """
    def struct_time(self, tm_year=0, tm_mon=0, tm_mday=0, tm_hour=0, tm_min=0, tm_sec=0, tm_wday=0, tm_yday=0, tm_isdst=0):
        return (tm_year, tm_mon, tm_mday, tm_hour, tm_min, tm_sec, tm_wday, tm_yday, tm_isdst)

_TIME_MODULE_SHADOW = TimeModuleShadow()
