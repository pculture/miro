# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

from miro import messages
from miro import signals
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import itemcontextmenu
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import itemlistcontroller

class DropHandler(signals.SignalEmitter):
    def __init__(self, playlist_id, item_view):
        signals.SignalEmitter.__init__(self)
        self.create_signal('new-order')
        self.playlist_id = playlist_id
        self.item_view = item_view

    def allowed_actions(self):
        return widgetset.DRAG_ACTION_MOVE

    def allowed_types(self):
        return ('downloaded-item',)

    def validate_drop(self, table_view, model, type, source_actions, parent,
            position):
        if position != -1 and type == 'downloaded-item':
            return widgetset.DRAG_ACTION_MOVE
        return widgetset.DRAG_ACTION_NONE

    def accept_drop(self, table_view, model, type, source_actions, parent,
            position, data):
        dragged_ids = set([int(id) for id in data.split('-')])
        if position >= 0:
            insert_iter = model.nth_iter(position)
        else:
            insert_iter = None
        try:
            self.item_view.item_list.move_items(insert_iter, dragged_ids)
        finally:
            self.item_view.model_changed()
        self.emit('new-order', [row[0].id for row in model])
        return True

class PlaylistSort(itemlist.ItemSort):
    """Sort that orders items by their order in the playlist.
    """

    def __init__(self):
        itemlist.ItemSort.__init__(self, True)
        self.positions = {}
        self.current_postion = itertools.count()

    def add_items(self, item_list):
        for item in item_list:
            self.positions[item.id] = self.current_postion.next()

    def forget_items(self, id_list):
        for id in id_list:
            del self.positions[id]

    def set_new_order(self, id_order):
        self.positions = dict((id, self.current_postion.next())
            for id in id_order)

    def sort_key(self, item):
        return self.positions[item.id]

class PlaylistView(itemlistcontroller.SimpleItemListController):
    image_filename = 'playlist-icon.png'

    def __init__(self, playlist_info):
        self.type = 'playlist'
        self.id = playlist_info.id
        self.title = playlist_info.name
        self.is_folder = playlist_info.is_folder
        self._sorter = PlaylistSort()
        itemlistcontroller.SimpleItemListController.__init__(self)
        self.item_list_group.set_sort(self._sorter)

    def make_drop_handler(self):
        handler = DropHandler(self.id, self.item_view)
        handler.connect('new-order', self._on_new_order)
        return handler

    def make_context_menu_handler(self):
        if self.is_folder:
            return itemcontextmenu.ItemContextMenuHandlerPlaylistFolder()
        else:
            return itemcontextmenu.ItemContextMenuHandlerPlaylist(self.id)

    def handle_item_list(self, message):
        self._sorter.add_items(message.items)
        itemlistcontroller.SimpleItemListController.handle_item_list(self,
                message)

    def handle_items_changed(self, message):
        self._sorter.add_items(message.added)
        self._sorter.forget_items(message.removed)
        itemlistcontroller.SimpleItemListController.handle_items_changed(self,
                message)

    def _on_new_order(self, drop_handler, order):
        self._sorter.set_new_order(order)
        messages.PlaylistReordered(self.id, order).send_to_backend()
