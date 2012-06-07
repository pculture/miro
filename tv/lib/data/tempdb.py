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

"""miro.data.tempdb -- Attach a temporary database to an sqlite connection

We use temporary databases to store statistics for in-progress downloads.
These change often and doesn't need to be saved between miro runs.  We use a
couple PRAGMA statements to improve performance at the expense of durability
and cosistentcy, since we're deleting the file anyways.

We use "mirotemp" as the sqlite name for the tempdb.  We use the same file as
the main miro database with "-temp" appended.
"""

import os
from miro.data import dlstats

def tempdb_path(main_db_path):
    """Get the path for the temporary db

    :param main_db_path: path to the main miro database
    """
    if main_db_path == ':memory:':
        return ':memory:'
    else:
        return main_db_path + "-temp"

def attach_temp_db(connection, main_db_path):
    """Attach a temporary DB to an sqlite connection

    :param connection: sqlite3.Connection object
    :param main_db_path: path to the main miro database
    """
    connection.execute("ATTACH ? as mirotemp", (tempdb_path(main_db_path),))
    connection.execute("PRAGMA mirotemp.synchronous=OFF")
    connection.execute("PRAGMA mirotemp.journal_mode=MEMORY")

def attach_new_temp_db(connection, main_db_path):
    """Attach a temporary DB to an sqlite connection, deleting any old data

    :param connection: sqlite3.Connection object
    :param main_db_path: path to the main miro database
    """
    if main_db_path != ':memory:':
        remove_tempdb(main_db_path)
    attach_temp_db(connection, main_db_path)
    dlstats.create_table(connection)

def remove_tempdb(main_db_path):
    """Remove a tempdb once you're done using it.

    This shouldn't be called unless you know that no other thread/process is
    using the database.
    """
    path = tempdb_path(main_db_path)
    if os.path.exists(path):
        os.remove(path)
