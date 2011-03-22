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

from miro import app
from miro import messages
from miro import signals
from miro.gtcache import gettext as _
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import itemcontextmenu
from miro.frontends.widgets import itemlist
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import itemlistwidgets
from miro.frontends.widgets import itemrenderer
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
            insert_id =  model.nth_row(position)[0].id
            # If we try to insert before an ID that iself is being
            # dragged we get an error
            while insert_id in dragged_ids:
                position += 1
                # If we iterate to the end of the playlist
                # we cancel the iteration
                if position > len(model):
                    insert_id = None
                    break
                insert_id = model.nth_row(position)[0].id
        else:
            insert_id = None
        new_order = self.sorter.move_ids_before(insert_id, dragged_ids)
        self.item_list.resort()
        for item_view in self.item_views:
            item_view.model_changed()
        self.emit('new-order', new_order)
        return True

class PlaylistItemController(itemlistcontroller.SimpleItemListController):
    def __init__(self, playlist_info):
        self.type = u'playlist'
        self.id = playlist_info.id
        self.is_folder = playlist_info.is_folder
        self.populated_sorter = False
        itemlistcontroller.SimpleItemListController.__init__(self)

    def build_column_renderers(self):
        column_renderers = itemlistwidgets.ListViewColumnRendererSet()
        playlist_renderer = style.PlaylistOrderRenderer(
                self.item_tracker.playlist_sort)
        column_renderers.add_renderer('playlist', playlist_renderer)
        return column_renderers

    def _init_widget(self):
        itemlistcontroller.SimpleItemListController._init_widget(self)
        self.make_drop_handler()


    def make_sorter(self, column, ascending):
        if column == 'playlist':
            # take the playlist sorter from our item tracker
            playlist_sort = self.item_tracker.playlist_sort
            playlist_sort.set_ascending(ascending)
            # slight bit of a hack here.  We enable/disable reordering based
            # on the sort we return here.  The assumption is that we are going
            # to use the sort we return, which seems reasonable.
            if ascending:
                self.enable_reorder()
            else:
                self.disable_reorder()
            return playlist_sort
        else:
            self.disable_reorder()
            return itemlistcontroller.SimpleItemListController.make_sorter(
                    self, column, ascending)

    def build_renderer(self):
        return itemrenderer.PlaylistItemRenderer(
                self.item_tracker.playlist_sort)

    def make_drop_handler(self):
        self.drop_handler = DropHandler(self.id, self.item_list,
                self.views.values(), self.item_tracker.playlist_sort)
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

    def _on_new_order(self, drop_handler, order):
        messages.PlaylistReordered(self.id, order).send_to_backend()
