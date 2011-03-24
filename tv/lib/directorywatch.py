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

"""directorywatch -- watch directories for changes.  """

from miro import app
from miro import signals

class DirectoryWatcher(signals.SignalEmitter):
    """Base class for watching directories.

    This class is an API to hook into OS notifications for directories.

    Frontends can extend this class and implement it's missing components,
    then call the install() method.  This will make the directory watch feeds
    use it to know when files get added/removed from their folders.

    The API is pretty simple, frontends only need to implement
    startup(), then emit signals whenever files get added/removed.
    """
    def __init__(self, root_directory):
        signals.SignalEmitter.__init__(self, 'added', 'deleted')
        self.startup(root_directory)

    def startup(self, root_directory):
        raise NotImplementedError()

    @classmethod
    def install(cls):
        app.directory_watcher = cls
