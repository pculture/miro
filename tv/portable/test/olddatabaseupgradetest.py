import os
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

from miro import convert20database
from miro import database
from miro import feed
from miro import ddblinks
from miro import olddatabaseupgrade
from miro import schemav79
from miro import storedatabase
from miro import databaseupgrade
from miro import databasesanity
from miro.plat import resources
from miro.plat.utils import FilenameType

from miro.test.framework import EventLoopTest, MiroTestCase

class Test20DatabaseConvert(MiroTestCase):
    """Test converting from a 2.0 database to a 2.1 database."""

    def setUp(self):
        MiroTestCase.setUp(self)
        self.tmp_path = tempfile.mktemp()
        self.connection = None

    def tearDown(self):
        if self.connection is not None:
            self.connection.close()
        MiroTestCase.tearDown(self)

    def check_tables_created(self):
        self.cursor.execute("""SELECT name FROM sqlite_master
            WHERE type='table'""")
        db_table_names = set(row[0] for row in self.cursor)
        for os in schemav79.objectSchemas:
            table_name = os.classString.replace('-', '_')
            self.assert_(table_name in db_table_names)

    def _get_column_names(self, table_name):
        self.cursor.execute('pragma table_info(%s)' % table_name)
        return [r[1] for r in self.cursor.fetchall()]

    def check_new_columns(self):
        for os in schemav79.objectSchemas:
            table_name = os.classString.replace('-', '_')
            db_columns = set(self._get_column_names(table_name))
            columns = set(f[0] for f in os.fields)
            self.assertEquals(db_columns, columns)

    def check_version(self):
        self.cursor.execute("""SELECT version FROM miro_version""")
        self.assertEquals(self.cursor.fetchone()[0], 80)

    def check_old_table_removed(self):
        self.cursor.execute("""SELECT name FROM sqlite_master
            WHERE type='table' AND
            (name = 'dtv_objects' or name = 'dtv_variables')""")
        self.assertEquals(len(self.cursor.fetchall()), 0)

    def _get_new_object(self, savable):
        table_name = savable.classString.replace("-", '_')
        id = savable.savedData['id']
        self.cursor.execute("SELECT * from %s where id=%s" % (table_name, id))
        row = self.cursor.fetchone()
        if row is None:
            raise ValueError("No row in %s with id %s" % (table_name, id))
        new_values = {}
        for value, description in zip(row, self.cursor.description):
            new_values[description[0]] = value
        return new_values

    def check_data_migrated(self):
        klass_count = {}
        for savable in self.old_savables:
            old_count = klass_count.get(savable.classString, 0)
            klass_count[savable.classString] = old_count + 1

        for klass, count in klass_count.items():
            table_name = klass.replace("-", '_')
            self.cursor.execute("SELECT COUNT(*) FROM %s" % table_name)
            self.assertEquals(self.cursor.fetchone()[0], count)

        schema_map = dict((os.classString, os) for os in
                schemav79.objectSchemas)
        for savable in self.old_savables:
            new_data = self._get_new_object(savable)
            old_data = savable.savedData
            schema = schema_map[savable.classString]
            for name, schema_item in schema.fields:
                new = new_data[name]
                old = old_data[name]
                # handle the ways data gets converted in the sqlite db
                if new is not None:
                    if isinstance(schema_item, schemav79.SchemaReprContainer):
                        new = str(new)
                    elif isinstance(schema_item, schemav79.SchemaBool):
                        new = bool(new)
                    elif isinstance(schema_item, schemav79.SchemaFilename):
                        if FilenameType != unicode:
                            new = new.encode("utf-8")
                if isinstance(new, datetime):
                    # Converting to a UTC timestamp sometimes causes rounding
                    # errors of a microsecond.  Don't worry about it.
                    if new > old:
                        same = abs((new - old).microseconds) <= 1
                    else:
                        same = abs((old - new).microseconds) <= 1
                else:
                    same = (new == old)
                if not same or type(new) != type(old):
                    raise AssertionError("%r != %r (name: %s)" %
                            (new, old, name))

    def one_test(self, db_file):
        old_db_path = resources.path("testdata/%s" % db_file)
        shutil.copyfile(old_db_path, self.tmp_path)
        self.connection = sqlite3.connect(self.tmp_path,
                detect_types=sqlite3.PARSE_DECLTYPES)
        self.cursor = self.connection.cursor()
        self.old_savables = convert20database._get_old_savables(self.cursor)
        convert20database._upgrate_old_savables(self.cursor,
                self.old_savables)
        convert20database.convert(self.cursor)

        self.check_tables_created()
        self.check_new_columns()
        self.check_version()
        self.check_old_table_removed()
        self.check_data_migrated()

    def test_conversion(self):
        self.one_test("olddatabase.v79")

    def test_conversion_with_upgrade(self):
        self.one_test("olddatabase.v78")

    def test_live_storage_converts(self):
        old_db_path = resources.path("testdata/olddatabase.v79")
        shutil.copyfile(old_db_path, self.tmp_path)
        live_storage = storedatabase.LiveStorage(self.tmp_path)
        self.cursor = live_storage.cursor
        self.old_savables = convert20database._get_old_savables(self.cursor)
        live_storage.upgrade_database()

        self.check_tables_created()
        self.check_new_columns()
        self.check_version()
        self.check_old_table_removed()
        self.check_data_migrated()

    def test_left_over_data(self):
        """Test what happens if the SavableObjects have keys around that
        aren't used anymore.
        """
        self.one_test("olddatabase.v71")
