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

"""playlist.py -- Handle displaying a playlist."""

import itertools

from miro import messages
from miro import signals
from miro.gtcache import gettext as _
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import itemcontextmenu
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import style

class DropHandler(signals.SignalEmitter):
    def __init__(self, playlist_id, item_list, item_views, sorter):
        signals.SignalEmitter.__init__(self)
        self.create_signal('new-order')
        self.playlist_id = playlist_id
        self.item_list = item_list
        self.item_views = item_views
        self.sorter = sorter

    def allowed_actions(self):
        return widgetset.DRAG_ACTION_MOVE

    def allowed_types(self):
        return ('downloaded-item',)

    def validate_drop(self, table_view, model, typ, source_actions, parent,
            position):
        if position != -1 and typ == 'downloaded-item':
            return widgetset.DRAG_ACTION_MOVE
        return widgetset.DRAG_ACTION_NONE

    def accept_drop(self, table_view, model, typ, source_actions, parent,
            position, data):
        dragged_ids = [int(id) for id in data.split('-')]
        if 0 <= position < len(model):
            insert_id = model.nth_row(position)[0].id
        else:
            insert_id = None
        new_order = self.sorter.move_ids_before(insert_id, dragged_ids)
        self.item_list.resort()
        for item_view in self.item_views:
            item_view.model_changed()
        self.emit('new-order', new_order)
        return True

class PlaylistSort(itemlist.ItemSort):
    """Sort that orders items by their order in the playlist.
    """
    KEY = 'playlist'

    def __init__(self, initial_items=None):
        itemlist.ItemSort.__init__(self, True)
        self.reset_current_position()
        self.positions = {}
        if initial_items:
            for item in initial_items:
                self.positions[item.id] = self.current_postion.next()

    def reset_current_position(self):
        self.current_postion = itertools.count()

    def set_ascending(self, ascending):
        self.reverse = not ascending

    def add_items(self, item_list):
        for item in item_list:
            if item.id not in self.positions:
                self.positions[item.id] = self.current_postion.next()

    def forget_items(self, id_list):
        for id in id_list:
            del self.positions[id]
        new_items = self.positions.items()
        new_items.sort(key=lambda row: row[1])
        self.reset_current_position()
        self.positions = {}
        for id, old_position in new_items:
            self.positions[id] = self.current_postion.next()

    def set_new_order(self, id_order):
        self.reset_current_position()
        self.positions = dict((id, self.current_postion.next())
            for id in id_order)

    def move_ids_before(self, before_id, id_list):
        """Move ids around in the position list

        The ids in id_list will be placed before before_id.  If before_id is
        None, then they will be placed at the end of the list.

        :returns: new sort order as a list of ids
        """

        # calculate order of ids not in id_list
        moving = set(id_list)
        new_order = [id_ for id_ in self.positions if id_ not in moving]
        new_order.sort(key=lambda id_: self.positions[id_])
        # insert id_list into new_order
        if before_id is not None:
            insert_pos = new_order.index(before_id)
            new_order[insert_pos:insert_pos] = id_list
        else:
            new_order.extend(id_list)
        self.set_new_order(new_order)
        return new_order

    def sort_key(self, item):
        return self.positions[item.id]

    def items_will_change(self, added, changed, removed):
        self.add_items(added)
        self.forget_items(removed)

class PlaylistItemController(itemlistcontroller.SimpleItemListController):
    def __init__(self, playlist_info):
        self.type = u'playlist'
        self.id = playlist_info.id
        self.is_folder = playlist_info.is_folder
        self.playlist_sorter = PlaylistSort()
        self.populated_sorter = False
        itemlistcontroller.SimpleItemListController.__init__(self)

    def build_column_renderers(self):
        column_renderers = itemlistwidgets.ListViewColumnRendererSet()
        playlist_renderer = style.PlaylistOrderRenderer(self.playlist_sorter)
        column_renderers.add_renderer('playlist', playlist_renderer)
        return column_renderers

    def _init_widget(self):
        itemlistcontroller.SimpleItemListController._init_widget(self)
        self.make_drop_handler()

    def ensure_playlist_sorter_populated(self):
        """Enusre that self.playlist_sorter is a valid object.

        We create playlist_sorter lazily so that we can pass it the list of
        initial items.
        """
        if not self.populated_sorter:
            self.playlist_sorter.add_items(self.item_list.get_items())
            self.populated_sorter = True

    def make_sorter(self, column, ascending):
        if column == 'playlist':
            self.ensure_playlist_sorter_populated()
            self.playlist_sorter.set_ascending(ascending)
            # slight bit of a hack here.  We enable/disable reordering based
            # on the sort we return here.  The assumption is that we are going
            # to use the sort we return, which seems reasonable.
            if ascending:
                self.enable_reorder()
            else:
                self.disable_reorder()
            return self.playlist_sorter
        else:
            self.disable_reorder()
            return itemlistcontroller.SimpleItemListController.make_sorter(
                    self, column, ascending)

    def build_renderer(self):
        return style.PlaylistItemRenderer(self.playlist_sorter)

    def make_drop_handler(self):
        self.drop_handler = DropHandler(self.id, self.item_list,
                self.views.values(), self.playlist_sorter)
        self.drop_handler.connect('new-order', self._on_new_order)

    def enable_reorder(self):
        for view in self.all_item_views():
            view.set_drag_dest(self.drop_handler)

    def disable_reorder(self):
        for view in self.all_item_views():
            view.set_drag_dest(None)

    def make_context_menu_handler(self):
        if self.is_folder:
            return itemcontextmenu.ItemContextMenuHandlerPlaylistFolder()
        else:
            return itemcontextmenu.ItemContextMenuHandlerPlaylist(self.id)

    def handle_delete(self):
        selected = [info.id for info in self.get_selection()]
        m = messages.RemoveVideosFromPlaylist(self.id, selected)
        m.send_to_backend()
        return True

    def build_widget(self):
        itemlistcontroller.SimpleItemListController.build_widget(self)
        text = _('This Playlist is Empty')
        self.widget.list_empty_mode_vbox.pack_start(
                itemlistwidgets.EmptyListHeader(text))
        text = _('To add an item, drag it onto the name of this playlist '
                'in the sidebar.')
        self.widget.list_empty_mode_vbox.pack_start(
                itemlistwidgets.EmptyListDescription(text))

    def build_header_toolbar(self):
        return itemlistwidgets.PlaylistHeaderToolbar()

    def check_for_empty_list(self):
        list_empty = (self.item_list.get_count() == 0)
        self.widget.set_list_empty_mode(list_empty)

    def _on_new_order(self, drop_handler, order):
        messages.PlaylistReordered(self.id, order).send_to_backend()
