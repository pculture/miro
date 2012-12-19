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

"""miro.data.maps -- Handle map tables for the database.
"""

def get_playlist_items(connection, playlist_id):
    """Get the order of items in a playlist.

    :returns: list of item ids
    """
    cursor = connection.execute("SELECT item_id "
                                "FROM playlist_item_map "
                                "WHERE playlist_id=? "
                                "ORDER BY position",
                                (playlist_id,))
    return [row[0] for row in cursor.fetchall()]

class SharingItemPlaylistMap(object):
    """Map playlist ids to the items in them.  """
    def __init__(self, connection):
        self.connection = connection

    def get_map(self):
        """Get a map of playlist ids to item ids.

        :returns: dict mapping playlist ids to sets of item ids
        """
        rv = {}
        cursor = self.connection.execute("SELECT playlist_id, item_id "
                                         "FROM sharing_item_playlist_map")
        for playlist_id, item_id in cursor:
            if playlist_id not in rv:
                rv[playlist_id] = set()
            rv[playlist_id].add(item_id)
        return rv

    def remove_playlist(self, playlist_id):
        """Remove all entries for a playlist """
        self.connection.execute("DELETE FROM sharing_item_playlist_map "
                                "WHERE playlist_id=?", (playlist_id,))

    def set_playlist_items(self, playlist_id, item_ids):
        """Set the items in a playlist."""
        self.remove_playlist(playlist_id)
        self.connection.executemany(
            "INSERT INTO sharing_item_playlist_map(playlist_id, item_id) "
            "VALUES (?, ?)",
            [(playlist_id, item_id) for item_id in item_ids])
