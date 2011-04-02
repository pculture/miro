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

import logging

from miro import app
from miro import messages
from miro.plat.frontends.widgets import widgetset

class TabListDragHandler(object):
    item_type = NotImplemented
    folder_type = NotImplemented
    def allowed_actions(self):
        return widgetset.DRAG_ACTION_MOVE

    def allowed_types(self):
        return (self.item_type, self.folder_type)

    def begin_drag(self, _tableview, rows):
        """Returns (tablist.type as a str, drag_data)"""
        typ = self.item_type
        for row in rows:
            if row[0].type == 'tab':
                return None
            if row[0].is_folder:
                typ = self.folder_type
                break
        typ = typ.encode('ascii', 'replace')
        return { typ: '-'.join(str(r[0].id) for r in rows)}

class TabDnDReorder(object):
    """Handles re-ordering tabs for doing drag and drop reordering."""
    def __init__(self):
        self.removed_rows = []
        self.removed_children = {}
        self.drop_row_iter = None
        self.drop_id = None

    def reorder(self, model, parent, position, dragged_ids):
        self.drop_row_iter = None
        if position >= 0 and parent:
            try:
                self.drop_row_iter = model.nth_child_iter(parent, position)
            except LookupError:
                # 16834 - invalid drop position, that's past the end.
                pass
        self.drop_id = self._calc_drop_id(model)
        self._remove_dragged_rows(model, dragged_ids)
        return self._put_rows_back(model, parent)

    def _calc_drop_id(self, model):
        if self.drop_row_iter is not None:
            return model[self.drop_row_iter][0].id

    def _remove_dragged_rows(self, model, dragged_ids):
        """Part of reorder, separated for clarity."""
        # iterating through the entire table seems inefficient, but we have to
        # know the order of dragged rows so we can insert them back in the
        # right order.
        iter_ = model.first_iter()
        if not iter_:
            app.widgetapp.handle_soft_failure('_remove_dragged_rows',
                "tried to drag no rows?",
                with_exception=False)
            return
        iter_ = model.child_iter(iter_)
        while iter_:
            row = model[iter_]
            if row[0].id in dragged_ids:
                # need to make a copy of the row data, since we're removing it
                # from the table
                children = [tuple(r) for r in row.iterchildren()]
                self.removed_children[row[0].id] = children
                iter_ = self._remove_row(model, iter_, tuple(row))
            else:
                child_iter = model.child_iter(iter_)
                while child_iter:
                    row = model[child_iter]
                    if row[0].id in dragged_ids:
                        child_iter = self._remove_row(model, child_iter,
                                tuple(row))
                    else:
                        child_iter = model.next_iter(child_iter)
                iter_ = model.next_iter(iter_)

    def _put_rows_back(self, model, parent):
        """Part of reorder, separated for clarity."""
        retval = {}
        for removed_row in self.removed_rows:
            if self.drop_row_iter is None:
                iter_ = model.append_child(parent, *removed_row)
            else:
                iter_ = model.insert_before(self.drop_row_iter, *removed_row)
            retval[removed_row[0].id] = iter_
            children = self.removed_children.get(removed_row[0].id, [])
            for child_row in children:
                child_iter = model.append_child(iter_, *child_row)
                retval[child_row[0].id] = child_iter
        return retval

    def _remove_row(self, model, iter_, row):
        """Part of _remove_dragged_rows."""
        self.removed_rows.append(row)
        if row[0].id == self.drop_id:
            self.drop_row_iter = model.next_iter(self.drop_row_iter)
            self.drop_id = self._calc_drop_id(model)
        return model.remove(iter_)

class MediaTypeDropHandler(object):
    """Drop Handler that changes the media type (audio/video/other) of items
    that get dropped on it.
    """

    def allowed_types(self):
        return ('downloaded-item', 'device-video-item', 'device-audio-item')

    def allowed_actions(self):
        return widgetset.DRAG_ACTION_COPY

    def _is_valid_drop(self, model, typ, parent, position):
        if parent is None or position != -1:
            return False
        if typ == 'downloaded-item':
            return model[parent][0].id in ('videos', 'music', 'others')
        media_type = model[parent][0].media_type
        if typ == ('device-%s-item' % media_type):
            return True

    def validate_drop(self, _table_view, model, typ, _source_actions, parent,
            position):
        if self._is_valid_drop(model, typ, parent, position):
            return widgetset.DRAG_ACTION_COPY
        return widgetset.DRAG_ACTION_NONE

    def accept_drop(self, _table_view, model, typ, _source_actions, parent,
            position, data):
        if self._is_valid_drop(model, typ, parent, position):
            video_ids = [int(id_) for id_ in data.split('-')]
            media_type = model[parent][0].media_type
            m = messages.SetItemMediaType(media_type, video_ids)
            m.send_to_backend()
            return True
        app.widgetapp.handle_soft_failure('accept_drop',
            "tried to accept a drop that shouldn't have validated!",
            with_exception=False)
        return False

class NestedTabListDropHandler(object):
    item_types = NotImplemented
    folder_types = NotImplemented

    def __init__(self, tablist):
        self.tablist = tablist

    def allowed_actions(self):
        return widgetset.DRAG_ACTION_COPY

    def allowed_types(self):
        return self.item_types + self.folder_types

    def validate_drop(self, _table_view, model, typ, _source_actions, parent,
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

    def accept_drop(self, _table_view, model, typ, _source_actions, parent,
            position, data):
        dragged_ids = set(int(id_) for id_ in data.split('-'))
        view = self.tablist.view
        # NOTE: combine 'with' statements in python2.7+
        with self.tablist.preserving_expanded_rows():
            with self.tablist.adding():
                with self.tablist.removing():
                    new_iters = TabDnDReorder().reorder(
                        view.model, parent, position, dragged_ids)
                    self.tablist.iter_map.update(new_iters)
        view.unselect_all(signal=False)
        for iter_ in new_iters.itervalues():
            try:
                view.select(iter_)
            except ValueError:
                parent = view.model.parent_iter(iter_)
                view.set_row_expanded(parent, True)
                view.select(iter_)
            except LookupError:
                logging.error('lookup error in accept_drop')
                view.select(view.model.first_iter())
        view._save_selection()
        view.emit('selection-changed')
        message = messages.TabsReordered()

        parent = view.model[view.model.first_iter()]
        for row in parent.iterchildren():
            message.append(row[0], self.tablist.type)
            for child in row.iterchildren():
                message.append_child(row[0].id, child[0])

        message.send_to_backend()
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
        if parent is None:
            return widgetset.DRAG_ACTION_NONE
        if model[parent][0].type == 'tab' and position == -1:
            return widgetset.DRAG_ACTION_NONE
        if typ == 'downloaded-item':
            if position == -1 and not model[parent][0].is_folder:
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
            app.widgetapp.handle_soft_failure('accept_drop',
                "tried to accept a drop that shouldn't have validated!",
                with_exception=False)
            return False
        return NestedTabListDropHandler.accept_drop(self, table_view, model, typ,
                source_actions, parent, position, data)

class PlaylistListDragHandler(TabListDragHandler):
    item_type = u'playlist'
    folder_type = u'playlist-with-folder'

class DeviceDropHandler(object):
    def __init__(self, tablist):
        self.tablist = tablist

    def allowed_actions(self):
        return widgetset.DRAG_ACTION_COPY

    def allowed_types(self):
        return ('downloaded-item',)

    def validate_drop(self, _widget, model, typ, _source_actions, parent,
                      position):
        if position == -1 and parent and typ in self.allowed_types():
            device = model[parent][0]
            if not isinstance(device, messages.DeviceInfo):
                # DAAP share
                return widgetset.DRAG_ACTION_NONE
            if device.mount and not getattr(device, 'fake', False):
                return widgetset.DRAG_ACTION_COPY
        return widgetset.DRAG_ACTION_NONE

    def accept_drop(self, _widget, model, _type, _source_actions, parent,
                    _position, data):
        video_ids = [int(id_) for id_ in data.split('-')]
        device = model[parent][0]
        messages.DeviceSyncMedia(device, video_ids).send_to_backend()
        return True
