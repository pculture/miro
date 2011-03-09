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

"""Drag aNd Drop handlers for TabLists."""

from miro import app
from miro import messages
from miro.plat.frontends.widgets import widgetset

def send_new_order():
    def append_items(sequence, typ):
        parent = sequence[sequence.first_iter()]
        for row in parent.iterchildren():
            info = row[0]
            message.append(info, typ)
            for child in row.iterchildren():
                message.append_child(info.id, child[0])

    message = messages.TabsReordered()
    append_items(app.tab_list_manager.feed_list.view.model, u'feed')
    append_items(app.tab_list_manager.playlist_list.view.model, u'playlist')
    message.send_to_backend()

class TabListDragHandler(object):
    def allowed_actions(self):
        return widgetset.DRAG_ACTION_MOVE

    def allowed_types(self):
        return (self.item_type, self.folder_type)

    def begin_drag(self, tableview, rows):
        typ = self.item_type
        for r in rows:
            if r[0].is_folder:
                typ = self.folder_type
                break
        typ = typ.encode('ascii', 'replace')
        return { typ: '-'.join(str(r[0].id) for r in rows)}

class TabDnDReorder(object):
    """Handles re-ordering tabs for doing drag and drop
    reordering.
    """
    def __init__(self):
        self.removed_rows = []
        self.removed_children = {}

    def calc_drop_id(self, model):
        if self.drop_row_iter is not None:
            self.drop_id = model[self.drop_row_iter][0].id
        else:
            self.drop_id = None

    def reorder(self, source_model, dest_model, parent, position, dragged_ids):
        if position >= 0:
            self.drop_row_iter = dest_model.nth_child_iter(parent, position)
        else:
            self.drop_row_iter = None
        self.calc_drop_id(dest_model)
        self.remove_dragged_rows(source_model, dragged_ids)
        return self.put_rows_back(dest_model, parent)

    def remove_row(self, model, iter_, row):
        self.removed_rows.append(row)
        if row[0].id == self.drop_id:
            self.drop_row_iter = model.next_iter(self.drop_row_iter)
            self.calc_drop_id(model)
        return model.remove(iter_)

    def remove_dragged_rows(self, model, dragged_ids):
        # iterating through the entire table seems inefficient, but we have to
        # know the order of dragged rows so we can insert them back in the
        # right order.
        iter_ = model.first_iter()
        if iter_ is None:
            return
        iter_ = model.child_iter(iter_)
        while iter_ is not None:
            row = model[iter_]
            row_dragged = (row[0].id in dragged_ids)
            if row_dragged:
                # need to make a copy of the row data, since we're removing it
                # from the table
                children = [tuple(r) for r in row.iterchildren()]
                self.removed_children[row[0].id] = children
                iter_ = self.remove_row(model, iter_, tuple(row))
            else:
                child_iter = model.child_iter(iter_)
                while child_iter is not None:
                    row = model[child_iter]
                    if row[0].id in dragged_ids:
                        child_iter = self.remove_row(model, child_iter,
                                tuple(row))
                    else:
                        child_iter = model.next_iter(child_iter)
                iter_ = model.next_iter(iter_)

    def put_rows_back(self, model, parent):
        if self.drop_row_iter is None:
            def put_back(moved_row):
                return model.append_child(parent, *moved_row)
        else:
            def put_back(moved_row):
                return model.insert_before(self.drop_row_iter, *moved_row)
        retval = {}
        for removed_row in self.removed_rows:
            iter_ = put_back(removed_row)
            retval[removed_row[0].id] = iter_
            children = self.removed_children.get(removed_row[0].id, [])
            for child_row in children:
                child_iter = model.append_child(iter_, *child_row)
                retval[child_row[0].id] = child_iter
        return retval

class MediaTypeDropHandler(object):
    """Drop Handler that changes the media type (audio/video/other) of items
    that get dropped on it.
    """

    def allowed_types(self):
        return ('downloaded-item', 'device-video-item', 'device-audio-item')

    def allowed_actions(self):
        return widgetset.DRAG_ACTION_COPY

    def validate_drop(self, table_view, model, typ, source_actions, parent,
            position):
        if parent is None or position != -1:
            return widgetset.DRAG_ACTION_NONE
        if typ == 'downloaded-item':
            return widgetset.DRAG_ACTION_COPY
        media_type = model[parent][0].media_type
        if typ == ('device-%s-item' % media_type):
            return widgetset.DRAG_ACTION_COPY
        return widgetset.DRAG_ACTION_NONE

    def accept_drop(self, table_view, model, typ, source_actions, parent,
            position, data):
        if parent is not None and position != -1:
            media_type = model[parent][0].media_type
            if typ == 'downloaded-item':
                video_ids = [int(id_) for id_ in data.split('-')]
                m = messages.SetItemMediaType(media_type, video_ids)
                m.send_to_backend()
                return True
            elif typ == ('device-%s-item' % media_type):
                # copying media from the device
                item_infos = pickle.loads(data)
                m = messages.DownloadDeviceItems(item_infos)
                m.send_to_backend
        # We shouldn't get here, because don't allow it in validate_drop.
        # Return False just in case
        return False

class NestedTabListDropHandler(object):
    def __init__(self, tablist):
        self.tablist = tablist

    def allowed_actions(self):
        return widgetset.DRAG_ACTION_COPY

    def allowed_types(self):
        return self.item_types + self.folder_types

    def validate_drop(self, table_view, model, typ, source_actions, parent,
            position):
        if parent is None:
            # can't drag above the root
            return widgetset.DRAG_ACTION_NONE
        if position < 0:
            is_folder = model[parent][0].is_folder
        elif position < model.children_count(parent):
            iter_ = model.nth_child_iter(parent, position)
            is_folder = model[iter_][0].is_folder
        else:
            is_folder = False
        parent_info = model[parent][0]
        if position == -1 and not is_folder:
            # Only folders can be dropped on
            return widgetset.DRAG_ACTION_NONE
        if (typ in self.folder_types and (
            (position == -1 and is_folder) or parent_info.is_folder)):
            # Don't allow folders to be dropped in other folders
            return widgetset.DRAG_ACTION_NONE
        elif typ not in self.item_types + self.folder_types:
            return widgetset.DRAG_ACTION_NONE
        return widgetset.DRAG_ACTION_MOVE

    def accept_drop(self, table_view, model, typ, source_actions, parent,
            position, data):
        source_tablist = dest_tablist = self.tablist
        selected_infos = app.tab_list_manager.get_selection()[1]
        selected_rows = [info.id for info in selected_infos]
        source_tablist.doing_change = dest_tablist.doing_change = True
        source_tablist.view.unselect_all()
        dest_tablist.view.unselect_all()
        dragged_ids = set([int(id_) for id_ in data.split('-')])
        expanded_rows = [id_ for id_ in dragged_ids if
                source_tablist.view.is_row_expanded(
                source_tablist.iter_map[id_])]
        if source_tablist.view.is_row_expanded(
            source_tablist.iter_map[source_tablist.info.id]):
            # keep the root expanded, if it was before
            expanded_rows.append(source_tablist.info.id)
        reorderer = TabDnDReorder()
        try:
            new_iters = reorderer.reorder(
                source_tablist.view.model, dest_tablist.view.model,
                parent, position, dragged_ids)

            # handle deletions for the source... delete the keys on
            # what's returned from the source_tablist's iter_map
            if source_tablist != dest_tablist:
                for key in new_iters.keys():
                    source_tablist.iter_map.pop(key)
            dest_tablist.iter_map.update(new_iters)
        finally:
            if source_tablist != dest_tablist:
                source_tablist.model_changed()
            dest_tablist.model_changed()
        for id_ in expanded_rows:
            dest_tablist.view.set_row_expanded(dest_tablist.iter_map[id_], True)
        try:
            for id_ in selected_rows:
                iter_ = dest_tablist.iter_map[id_]
                parent = model.parent_iter(iter_)
                if parent is None or dest_tablist.view.is_row_expanded(parent):
                    dest_tablist.view.select(iter_)
        except KeyError:
            pass

        send_new_order()
        source_tablist.doing_change = False
        dest_tablist.doing_change = False
        app.tab_list_manager.handle_moved_tabs_to_list(dest_tablist)
        return True

class FeedListDropHandler(NestedTabListDropHandler):
    item_types = ('feed',)
    folder_types = ('feed-with-folder',)

class FeedListDragHandler(TabListDragHandler):
    item_type = u'feed'
    folder_type = u'feed-with-folder'

class PlaylistListDropHandler(NestedTabListDropHandler):
    item_types = ('playlist',)
    folder_types = ('playlist-with-folder',)

    def allowed_actions(self):
        return (NestedTabListDropHandler.allowed_actions(self) |
                widgetset.DRAG_ACTION_COPY)

    def allowed_types(self):
        return NestedTabListDropHandler.allowed_types(self) + ('downloaded-item',)

    def validate_drop(self, table_view, model, typ, source_actions, parent,
            position):
        if typ == 'downloaded-item':
            if (parent is not None and position == -1 and
                    not model[parent][0].is_folder):
                return widgetset.DRAG_ACTION_COPY
            else:
                return widgetset.DRAG_ACTION_NONE
        return NestedTabListDropHandler.validate_drop(self, table_view, model, typ,
                source_actions, parent, position)

    def accept_drop(self, table_view, model, typ, source_actions, parent,
            position, data):
        if typ == 'downloaded-item':
            if parent is not None and position == -1:
                playlist_id = model[parent][0].id
                video_ids = [int(id_) for id_ in data.split('-')]
                messages.AddVideosToPlaylist(playlist_id,
                        video_ids).send_to_backend()
                return True
            # We shouldn't get here, because don't allow it in validate_drop.
            # Return False just in case
            return False
        return NestedTabListDropHandler.accept_drop(self, table_view, model, typ,
                source_actions, parent, position, data)

class DeviceDropHandler(object):
    def __init__(self, tablist):
        self.tablist = tablist

    def allowed_actions(self):
        return widgetset.DRAG_ACTION_COPY

    def allowed_types(self):
        return ('downloaded-item',)

    def validate_drop(self, widget, model, type, source_actions, parent,
                      position):
        if position == -1 and parent and type in self.allowed_types():
            device = model[parent][0]
            if not isinstance(device, messages.DeviceInfo):
                # DAAP share
                return widgetset.DRAG_ACTION_NONE
            if device.mount and not getattr(device, 'fake', False):
                return widgetset.DRAG_ACTION_COPY
        return widgetset.DRAG_ACTION_NONE

    def accept_drop(self, widget, model, type, source_actions, parent,
                    position, data):
        video_ids = [int(id_) for id_ in data.split('-')]
        device = model[parent][0]
        messages.DeviceSyncMedia(device, video_ids).send_to_backend()

class PlaylistListDragHandler(TabListDragHandler):
    item_type = u'playlist'
    folder_type = u'playlist-with-folder'
