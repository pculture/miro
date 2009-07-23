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

"""convert20database.py -- Convert version 2.0 (and before) databases.

In this module "old-style" means before version 80, where objects were are
stored in pickled form in a single table.  "new-style" means version 80, where
objects were separated into different tables based on their class and each
attribute was stored in a separate column.
"""

# Some of the code is duplicated between this module and storedatabase.py.
# This is intentional, it allows us to make changes to storedatabase
# without worrying about old databases.

import cPickle
from cStringIO import StringIO
import logging
import sys

try:
    import sqlite3
except ImportError:
    from pysqlite2 import dbapi2 as sqlite3

from miro import databaseupgrade
from miro import databasesanity
from miro import feedparser
from miro import schemav79 as schema_mod
from miro import util
from miro.plat.utils import filenameToUnicode

def _loads(str):
    """Version of cPickle.loads() that can handle the SavableObject class."""
    unpickler = cPickle.Unpickler(StringIO(str))
    unpickler.find_global = _find_global
    return unpickler.load()

def _find_global(module, name):
    """Does the work required for _loads."""
    if module == 'storedatabase' and name == 'SavableObject':
        return SavableObject
    elif module == 'feedparser' and name == 'FeedParserDict':
        return feedparser.FeedParserDict
    else:
        __import__(module)
        mod = sys.modules[module]
        klass = getattr(mod, name)
        return klass

def convert(cursor):
    """Convert an old-style database to a new-style one.

    cursor is an SQLite cursor.
    """

    savable_objects = _get_old_savables(cursor)
    _upgrate_old_savables(cursor, savable_objects)
    _run_databasesanity(savable_objects)
    _create_db_schema(cursor)
    _migrate_old_data(cursor, savable_objects)
    cursor.execute("DROP TABLE dtv_objects")

def _get_old_savables(cursor):
    """Get a list of SavableObjects given a cursor pointing to an old-style
    database.
    """
    cursor.execute("SELECT serialized_object FROM dtv_objects")
    return [_loads(str(r[0])) for r in cursor]

def _upgrate_old_savables(cursor, savables):
    cursor.execute("SELECT serialized_value FROM dtv_variables "
            "WHERE name=?", ("Democracy Version",))
    row = cursor.fetchone()
    version = cPickle.loads(str(row[0]))
    databaseupgrade.upgrade(savables, version, schema_mod.VERSION)

def _run_databasesanity(objects):
    try:
        databasesanity.checkSanity(objects, quiet=True,
                reallyQuiet=(not util.chatter))
    except databasesanity.DatabaseInsaneError, e:
        logging.warn("Old database fails sanity test: %s", e)
        objects[:] = []

def _create_db_schema(cursor):
    for schema in schema_mod.objectSchemas:
        table_name = schema.classString.replace('-', '_')
        cursor.execute("SELECT COUNT(*) FROM sqlite_master "
                "WHERE name=? and type='table'", (table_name,))
        if cursor.fetchone()[0] > 0:
            logging.warn("dropping %s in 2.0 upgrade", table_name)
            cursor.execute("DROP TABLE %s " % table_name)
        cursor.execute("CREATE TABLE %s (%s)" %
                (table_name, _calc_sqlite_types(schema)))

def _calc_sqlite_types(object_schema):
    types = []
    for name, schema_item in object_schema.fields:
        type = _sqlite_type_map[schema_item.__class__]
        if name != 'id':
            types.append('%s %s' % (name, type))
        else:
            types.append('%s %s PRIMARY KEY' % (name, type))
    return ', '.join(types)

def _execute_insert_sql(cursor, savable):
    table_name = savable.classString.replace("-", "_")
    column_names = []
    values = []
    schema = _class_to_schema[savable.classString]
    for name, schema_item in schema.fields:
        value = savable.savedData[name]
        column_names.append(name)
        if value is not None:
            if isinstance(schema_item, schema_mod.SchemaBinary):
                value = sqlite3.Binary(value)
            elif isinstance(schema_item, schema_mod.SchemaTimeDelta):
                value = repr(value)
            elif isinstance(schema_item, schema_mod.SchemaFilename):
                value = filenameToUnicode(value)
        values.append(value)
    sql = "REPLACE INTO %s (%s) VALUES(%s)" % (table_name,
            ', '.join(column_names),
            ', '.join('?' for i in xrange(len(column_names))))
    cursor.execute(sql, values)

def _migrate_old_data(cursor, savable_objects):
    for savable in savable_objects:
        _execute_insert_sql(cursor, savable)

# Figure out which SQLITE type to use for SchemaItem classes.
_sqlite_type_map = {
        schema_mod.SchemaBool: 'integer',
        schema_mod.SchemaFloat: 'real',
        schema_mod.SchemaString: 'text',
        schema_mod.SchemaBinary:  'blob',
        schema_mod.SchemaURL: 'text',
        schema_mod.SchemaInt: 'integer',
        schema_mod.SchemaDateTime: 'timestamp',
        schema_mod.SchemaTimeDelta: 'pythonrepr',
        schema_mod.SchemaReprContainer: 'pythonrepr',
        schema_mod.SchemaDict: 'pythonrepr',
        schema_mod.SchemaList: 'pythonrepr',
        schema_mod.SchemaStatusContainer: 'pythonrepr',
        schema_mod.SchemaFilename: 'text',
        # we always store the unicode version of filenames
}

_class_to_schema = {}
for schema in schema_mod.objectSchemas:
    _class_to_schema[schema.classString] = schema

class SavableObject:
    """Holdover from 2.0 databases.

    Member variables:

    classString -- specifies the class this object was converted from.
    savedData -- dict that stores the data we've saved.

    The SavableObject class is guaranteed to never change.  This means we can
    always safely unpickle them.
    """

    # This is a complete hack to prevent problems if data is saved with a
    # newer version of Miro and an older version of Miro tries to open it.
    # Now adays the name of this module is "miro.storedatabase", but for older
    # versions it's just "storedatabase".  Hacking the module name here
    # changes where pickle tries to unpickle it from.
    #
    # In both cases "storedatabase" works, because we try to unpickle it from
    # inside the miro directory.
    __module__ = 'storedatabase'

    def __init__(self, classString):
        self.classString = classString
        self.savedData = {}

    def __str__(self):
        return '<SavableObject: %s>' % self.classString


class SavableObject:
    """Holdover from previous database versions.  We need this around to be
    able to unpickle it.

    Member variables:

    classString -- specifies the class this object was converted from.
    savedData -- dict that stores the data we've saved.

    The SavableObject class is guaranteed to never change.  This means we can
    always safely unpickle them.
    """

    def __init__(self, classString):
        self.classString = classString
        self.savedData = {}

    def __str__(self):
        return '<SavableObject: %s>' % self.classString
