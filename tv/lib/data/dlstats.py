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

"""miro.data.dlstats -- Manages the dlstats table

The dlstats table is a table in the tempdb that tracks statistics for
in-progress downloads.
"""

from miro import app

def create_table(connection):
    """Create the dlstats table."""
    columns = [
        "id integer PRIMARY KEY",
        "eta integer",
        "rate integer",
        "upload_rate integer",
        "current_size integer",
        "total_size integer",
        "upload_size integer",
        "activity text",
        "seeders integer",
        "leechers integer",
        "connections integer",
    ]
    connection.execute("CREATE TABLE mirotemp.dlstats(%s)" %
                       ", ".join(columns))

def update_stats(downloader_id, new_stats):
    """Update the dlstats table based on new stats from the downloader."""
    stat_names = ( "eta", "rate", "upload_rate", "current_size",
                  "total_size", "upload_size", "activity", "seeders",
                  "leechers", "connections",)
    column_names = ('id',) + stat_names
    values = (downloader_id,) + tuple(new_stats.get(n) for n in stat_names)

    sql = ("INSERT OR REPLACE INTO dlstats (%s) VALUES (%s)" %
           (', '.join(column_names),
            ', '.join('?' for i in xrange(len(values)))))
    # FIXME: We should have a cleaner system for this.
    app.db._execute(sql, values, is_update=True)
