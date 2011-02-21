# Miro - an RSS based video player application
# Copyright (C) 2010 Participatory Culture Foundation
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

"""playlist.py -- Handle displaying a playlist."""

import itertools
import threading

from miro import app
from miro import messages
from miro import signals
from miro.gtcache import gettext as _
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import itemcontextmenu
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import itemtrack
from miro.frontends.widgets import style

class SharingStandardView(itemlistwidgets.StandardView):
    def __init__(self, item_list, scroll_pos, selection, playlist_id):
        itemlistwidgets.StandardView.__init__(self, item_list,
                scroll_pos, selection)
        self.playlist_id = playlist_id

    def build_renderer(self):
        return style.SharingItemRenderer(display_channel=False)

class SharingView(itemlistcontroller.SimpleItemListController):
    image_filename = 'playlist-icon.png'

    def __init__(self, share):
        self.type = u'sharing'
        self.share = share
        self.id = share.id
        self.title = share.name
        itemlistcontroller.SimpleItemListController.__init__(self)

    def make_drag_handler(self):
        return None

    def build_standard_view(self, scroll_pos, selection):
        standard_view = SharingStandardView(self.item_list,
                scroll_pos, selection, self.id)
        return standard_view, standard_view

    def handle_delete(self):
        pass

    def build_item_tracker(self):
        return itemtrack.ItemListTracker.create(self.type, self.share)

    # note: this should never be empty, so we don't have empty view.
    def build_widget(self):
        itemlistcontroller.SimpleItemListController.build_widget(self)
