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

from miro import messages
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import itemlist

class ItemReorderer(object):
    """Handles re-ordering items for DnD"""
    def __init__(self):
        self.removed_rows = []

    def calc_drop_id(self, model):
        if self.drop_row_iter is not None:
            self.drop_id = model[self.drop_row_iter][0].id
        else:
            self.drop_id = None

    def reorder(self, model, position, dragged_ids):
        if position >= 0:
            self.drop_row_iter = model.nth_iter(position)
        else:
            self.drop_row_iter = None
        self.calc_drop_id(model)
        self.remove_dragged_rows(model, dragged_ids)
        return self.put_rows_back(model)

    def remove_row(self, model, iter, row):
        self.removed_rows.append(row)
        if row[0].id == self.drop_id:
            self.drop_row_iter = model.next_iter(self.drop_row_iter)
            self.calc_drop_id(model)
        return model.remove(iter)

    def remove_dragged_rows(self, model, dragged_ids):
        # iterating through the entire table seems inefficient, but we have to
        # know the order of dragged rows so we can insert them back in the
        # right order.
        iter = model.first_iter()
        while iter is not None:
            row = model[iter]
            row_dragged = (row[0].id in dragged_ids)
            if row_dragged:
                # need to make a copy of the row data, since we're removing it
                # from the table
                iter = self.remove_row(model, iter, tuple(row))
            else:
                iter = model.next_iter(iter)

    def put_rows_back(self, model):
        if self.drop_row_iter is None:
            def put_back(moved_row):
                return model.append(*moved_row)
        else:
            def put_back(moved_row):
                return model.insert_before(self.drop_row_iter, *moved_row)
        retval = {}
        for removed_row in self.removed_rows:
            iter = put_back(removed_row)
            retval[removed_row[0].id] = iter
        return retval

class DropHandler(object):
    def __init__(self, playlist_id, item_list):
        self.playlist_id = playlist_id
        self.item_list = item_list

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
        try:
            new_iters = ItemReorderer().reorder(model, position, dragged_ids)
            self.item_list.item_iters.update(new_iters)
        finally:
            self.item_list.model_changed()
        self.send_new_order()
        return False

    def send_new_order(self):
        item_ids = [row[0].id for row in self.item_list.model]
        messages.PlaylistReordered(self.playlist_id,
                item_ids).send_to_backend()

class PlaylistView(itemlist.SimpleItemContainer):
    SORT_ITEMS = False
    image_filename = 'playlist-icon.png'

    def __init__(self, playlist_info):
        self.type = 'playlist'
        self.id = playlist_info.id
        self.title = playlist_info.name
        itemlist.SimpleItemContainer.__init__(self)
        self.item_list.set_drag_dest(DropHandler(self.id, self.item_list))
