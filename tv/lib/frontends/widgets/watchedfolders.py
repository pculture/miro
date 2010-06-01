# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""watchedsfolders.py -- Manages tracking watched folders.  """

from miro import messages
from miro import signals
from miro.plat.frontends.widgets import widgetset
from miro.plat.utils import filename_to_unicode

class WatchedFolderManager(signals.SignalEmitter):
    """Manages tracking watched folders.

    Attributes:

        model -- TableModel object that contains the current list of watched
            folders.  It has 3 columns: id (integer), path (text) and
            visible (boolean).

    Signals:
        changed -- The list of watched folders has changed
    """

    def __init__(self):
        signals.SignalEmitter.__init__(self, 'changed')
        self.model = widgetset.TableModel('integer', 'text', 'boolean')
        self._iter_map = {}

    def handle_watched_folder_list(self, info_list):
        """Handle the WatchedFolderList message."""
        for info in info_list:
            iter = self.model.append(info.id, filename_to_unicode(info.path),
                    info.visible)
            self._iter_map[info.id] = iter
        self.emit('changed')

    def handle_watched_folders_changed(self, added, changed, removed):
        """Handle the WatchedFoldersChanged message."""
        self.handle_watched_folder_list(added)
        for info in changed:
            iter = self._iter_map[info.id]
            self.model.update_value(iter, 1, filename_to_unicode(info.path))
            self.model.update_value(iter, 2, info.visible)
        for id in removed:
            iter = self._iter_map.pop(id)
            self.model.remove(iter)
        self.emit('changed')

    def change_visible(self, id, visible):
        """Change if a watched folder is visible or not."""
        messages.SetWatchedFolderVisible(id, visible).send_to_backend()

    def remove(self, id):
        """Remove a watched folder."""
        messages.DeleteWatchedFolder(id).send_to_backend()

    def add(self, path):
        """Add a new watched folder.  It will be initially visible."""
        messages.NewWatchedFolder(path).send_to_backend()
