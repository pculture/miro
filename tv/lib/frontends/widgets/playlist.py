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

import logging

from miro import app
from miro import messages
from miro import signals
from miro.data import mappings
from miro.gtcache import gettext as _
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import itemcontextmenu
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import itemrenderer
from miro.frontends.widgets import itemsort
from miro.frontends.widgets import style
from miro.frontends.widgets.widgetstatestore import WidgetStateStore

class PlaylistOrder(object):
    """Tracks the order of items in a playlist."""
    def __init__(self, playlist_id):
        self.playlist_id = playlist_id
        self.update_positions()
        self.ascending = True

    def update_positions(self):
        connection_pool = app.connection_pools.main_pool
        connection = connection_pool.get_connection()
        try:
            self.playlist_items = mappings.get_playlist_items(connection,
                                                              self.playlist_id)
        finally:
            connection_pool.release_connection(connection)

    def item_position(self, item_info):
        """Get the position of an item inside the list.

        :returns: position as an int, with the count starting at 1
        """
        try:
            return self.playlist_items.index(item_info.id) + 1
        except ValueError:
            logging.warn("PlaylistOrder.item_position(): item not found (%s)",
                         item_info.title)
            return -1

    def set_sort_ascending(self, ascending):
        """Set if the sort is ascending or not.

        This changes how we calculate the new list order after a DnD
        operation.
        """
        self.ascending = ascending

    def get_new_list_order(self, insert_id, dragged):
        """Get the list order after some items gets re-ordered.

        :param insert_id: item to insert before, or None to insert the items
        at the end of the list
        :param dragged: list of ids that got dragged
        """
        dragged = set(dragged)
        new_order = []
        if self.ascending:
            source_list = self.playlist_items
        else:
            source_list = list(self.playlist_items)
            source_list.reverse()
        for item_id in source_list:
            if item_id == insert_id:
                new_order.extend(dragged)
            if item_id not in dragged:
                new_order.append(item_id)
        if insert_id is None:
            new_order.extend(dragged)
        if not self.ascending:
            new_order.reverse()
        return new_order

class DropHandler(signals.SignalEmitter):
    def __init__(self, playlist_order):
        signals.SignalEmitter.__init__(self)
        self.create_signal('new-order')
        self.playlist_order = playlist_order

    def allowed_actions(self):
        return widgetset.DRAG_ACTION_MOVE

    def allowed_types(self):
        return ('downloaded-item',)

    def validate_drop(self,
            table_view, model, typ, source_actions, parent, position):
        if position != -1 and typ == 'downloaded-item':
            return widgetset.DRAG_ACTION_MOVE
        return widgetset.DRAG_ACTION_NONE

    def accept_drop(self,
            table_view, model, typ, source_actions, parent, position, dragged):
        if 0 <= position < len(model):
            insert_id =  model.item_list.get_row(position).id
        else:
            insert_id = None
        new_order = self.playlist_order.get_new_list_order(insert_id, dragged)
        self.emit('new-order', new_order)
        return True

class PlaylistItemController(itemlistcontroller.SimpleItemListController):
    def __init__(self, playlist_info):
        self.type = u'playlist'
        self.id = playlist_info.id
        self.is_folder = playlist_info.is_folder
        self.populated_sorter = False
        self.playlist_order = PlaylistOrder(playlist_info.id)
        itemlistcontroller.SimpleItemListController.__init__(self)

    def build_column_renderers(self):
        column_renderers = itemlistwidgets.ListViewColumnRendererSet()
        playlist_renderer = style.PlaylistOrderRenderer(self.playlist_order)
        column_renderers.add_renderer('playlist', playlist_renderer)
        return column_renderers

    def _init_widget(self):
        itemlistcontroller.SimpleItemListController._init_widget(self)
        standard_view = WidgetStateStore.get_standard_view_type()
        # 17408: the hotspot handler in the standard view need access to the
        # playlist id to be able to ditch an item.
        self.views[standard_view].playlist_id = self.id
        self.make_drop_handler()

    def make_sorter(self, column, ascending):
        # slight bit of a hack here.  We enable/disable reordering based
        # on the sort we return here.  The assumption is that we are going
        # to use the sort we return, which seems reasonable.
        if column == 'playlist':
            self.playlist_order.set_sort_ascending(ascending)
            self.enable_reorder()
        else:
            self.disable_reorder()
        return itemlistcontroller.SimpleItemListController.make_sorter(
                self, column, ascending)

    def _init_item_views(self):
        itemlistcontroller.SimpleItemListController._init_item_views(self)
        if isinstance(self.item_list.sorter, itemsort.PlaylistSort):
            self.enable_reorder()

    def build_renderer(self):
        return itemrenderer.PlaylistItemRenderer(self.playlist_order)

    def handle_item_list_changes(self):
        itemlistcontroller.SimpleItemListController.handle_item_list_changes(self)
        self.playlist_order.update_positions()

    def make_drop_handler(self):
        self.drop_handler = DropHandler(self.playlist_order)
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

    def _on_new_order(self, drop_handler, order):
        sort_key = app.widget_state.get_sort_state(self.type, self.id)
        column, ascending = self.parse_sort_key(sort_key)
        messages.PlaylistReordered(self.id, order).send_to_backend()
