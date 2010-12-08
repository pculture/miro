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
from miro.frontends.widgets import style

import libdaap

class SharingItemView(itemlistwidgets.ItemView):
    def __init__(self, item_list, playlist_id):
        itemlistwidgets.ItemView.__init__(self, item_list)
        self.playlist_id = playlist_id

    def build_renderer(self):
        return style.PlaylistItemRenderer(display_channel=True)

class SharingView(itemlistcontroller.SimpleItemListController):
    image_filename = 'playlist-icon.png'

    def __init__(self, tab):
        self.type = 'sharing'
        self.tab = tab
        self.id = tab.id
        print 'SELF.id = ', self.id
        self.title = tab.name
        #self.is_folder = tab.is_folder
        itemlistcontroller.SimpleItemListController.__init__(self)

    def build_item_view(self):
        return SharingItemView(self.item_list, self.id)

    def build_list_item_view(self):
        return itemlistwidgets.ListItemView(self.item_list,
                self.enabled_columns, self.column_widths,
                display_download_info=False)

    def handle_delete(self):
        pass

    # XXX this should never be empty
    def build_widget(self):
        itemlistcontroller.SimpleItemListController.build_widget(self)

    def handle_item_list(self, message):
        print 'handle item list'
        print 'length of message = ', len(message.items)
        if len(message.items) > 0:
            print 'type', type(message.items[0])
        itemlistcontroller.SimpleItemListController.handle_item_list(self,
                message)

    def handle_items_changed(self, message):
        print 'handle items changed'
        itemlistcontroller.SimpleItemListController.handle_items_changed(self,
                                                                      message)

    def mdns_callback(added, fullname, host, port):
        print 'Status: Added = %s name = %s host = %s port = %s' % (added, fullname, host, port)

    def server_thread(self):
        libdaap.browse_mdns(self.mdns_callback)

    def start_tracking(self):
        # Note: Track items is done on tab clicked, which connects to the
        # share.  See tablist.py
        app.info_updater.item_list_callbacks.add('sharing', self.tab.id,
                                                 self.handle_item_list)
        app.info_updater.item_changed_callbacks.add('sharing', self.tab.id,
                                                 self.handle_items_changed)

    def stop_tracking(self):
        app.info_updater.item_list_callbacks.remove('sharing', self.tab.id,
                                                 self.handle_item_list)
        app.info_updater.item_changed_callbacks.remove('sharing', self.tab.id,
                                                 self.handle_items_changed)
