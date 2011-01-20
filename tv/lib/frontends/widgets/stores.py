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

"""stores.py -- Manages tracking music stores.  """

from miro import messages
from miro import signals
from miro.plat.frontends.widgets import widgetset

class StoreManager(signals.SignalEmitter):
    """Manages tracking audio/video stores.

    Attributes:

        model -- TableModel object that contains the current list of watched
            folders.  It has 3 columns: id (integer), name (text) and
            visible (boolean).

    Signals:
        changed -- The list of stores has changed
    """

    def __init__(self):
        signals.SignalEmitter.__init__(self, 'changed')
        self.model = widgetset.TableModel('integer', 'text', 'boolean')
        self._iter_map = {}

    def handle_guide_list(self, added_guides):
        """Handle the GuideList message."""
        for info in added_guides:
            if not info.store:
                continue
            iter = self.model.append(info.id, info.name, info.visible)
            self._iter_map[info.id] = iter
        self.emit('changed')

    def handle_guides_changed(self, added, changed, removed):
        self.handle_guide_list(added)
        for info in changed:
            if not info.store:
                continue
            iter = self._iter_map[info.id]
            self.model.update_value(iter, 1, info.name)
            self.model.update_value(iter, 2, info.visible)
        for id_ in removed:
            if id_ in self._iter_map:
                iter = self._iter_map.pop(id_)
                self.model.remove(iter)
        self.emit('changed')

    def change_visible(self, id_, visible):
        """Change if a watched folder is visible or not."""
        messages.SetGuideVisible(id_, visible).send_to_backend()

