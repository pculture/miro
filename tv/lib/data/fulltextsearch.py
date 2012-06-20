# Miro - an RSS based video player application
# Copyright (C) 2012
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

"""miro.data.fulltextsearch -- Set up full text search in our SQLite DB
"""
from miro import app

def setup_fulltext_search(connection):
    """Set up fulltext search on a newly created database."""
    if hasattr(app, 'in_unit_tests') and _no_item_table(connection):
        # handle unittests not defining the item table in their schemas
        return

    # FIXME: should include source name here.  Also description should also
    # match entry_description
    columns = ['title', 'description', 'artist', 'album', 'genre',
               'filename', ]
    column_list = ', '.join(c for c in columns)
    column_list_for_new = ', '.join("new.%s" % c for c in columns)
    column_list_with_types = ', '.join('%s text' % c for c in columns)
    connection.execute("CREATE VIRTUAL TABLE item_fts USING fts4"
                       "(content='item', %s)" % column_list_with_types)
    connection.execute("INSERT INTO item_fts(docid, %s)"
                       "SELECT item.id, %s FROM item" %
                       (column_list, column_list))
    # make triggers to keep item_fts up to date
    connection.execute("CREATE TRIGGER item_bu "
                       "BEFORE UPDATE ON item BEGIN "
                       "DELETE FROM item_fts WHERE docid=old.id; "
                       "END;")

    connection.execute("CREATE TRIGGER item_bd "
                       "BEFORE DELETE ON item BEGIN "
                       "DELETE FROM item_fts WHERE docid=old.id; "
                       "END;")

    connection.execute("CREATE TRIGGER item_au "
                       "AFTER UPDATE ON item BEGIN "
                       "INSERT INTO item_fts(docid, %s) "
                       "VALUES(new.id, %s); "
                       "END;" % (column_list, column_list_for_new))

    connection.execute("CREATE TRIGGER item_ai "
                       "AFTER INSERT ON item BEGIN "
                       "INSERT INTO item_fts(docid, %s) "
                       "VALUES(new.id, %s); "
                       "END;" % (column_list, column_list_for_new))

def _no_item_table(connection):
    cursor = connection.execute("SELECT COUNT(*) FROM sqlite_master "
                                "WHERE type='table' and name='item'")
    return (cursor.fetchone()[0] == 0)
