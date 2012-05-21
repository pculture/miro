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

"""miro.data.connectionpool -- SQLite connection pool """
import contextlib
import sqlite3

class ConnectionLimitError(StandardError):
    """We've hit our connection limits."""

class ConnectionPool(object):
    def __init__(self, db_path, min_connections=2, max_connections=4):
        """Create a new ConnectionPool

        :param db_path: path to the database to connect to
        :param min_connections: Minimum number of connections to maintain
        :param max_connections: Maximum number of connections to the database
        """
        self.db_path = db_path
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.all_connections = set()
        self.free_connections = []
        for i in xrange(min_connections):
            self._make_new_connection()

    def _make_new_connection(self):
        # TODO: should have error handling here, but what should we do?
        connection = sqlite3.connect(self.db_path,
                                     isolation_level=None,
                                     detect_types=sqlite3.PARSE_DECLTYPES)
        connection.execute("PRAGMA journal_mode=wal");
        self.free_connections.append(connection)
        self.all_connections.add(connection)

    def get_connection(self):
        """Get a new connection to the database

        When you're finished with the connection, call release_connection() to
        put it back into the pool.

        If there are max_connections checked out and get_connection() is
        called again, ConnectionLimitError will be raised.

        :returns sqlite3.Connection object
        """
        if not self.free_connections:
            if len(self.all_connections) < self.max_connections:
                self._make_new_connection()
            else:
                raise ConnectionLimitError()
        return self.free_connections.pop()

    def release_connection(self, connection):
        """Put a connection back into the pool."""

        if connection not in self.all_connections:
            raise ValueError("%s not from this pool" % connection)
        if len(self.all_connections) > self.min_connections:
            connection.close()
            self.all_connections.remove(connection)
        else:
            self.free_connections.append(connection)

    @contextlib.contextmanager
    def connection_context(self):
        """ContextManager used to get a connection.

        Usage:
            with connection_pool.connection_context() as connection:
                cursor = connection.cursor()
                cursor.execute("blah blah blah")
        """
        connection = self.get_connection()
        yield connection
        # Rollback any changes not committed
        connection.rolback()
        self.release_connection(connection)
