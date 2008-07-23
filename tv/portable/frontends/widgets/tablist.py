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

"""Displays the list of tabs on the left-hand side of the app."""

from miro import app
from miro import messages
from miro.gtcache import gettext as _
from miro.plat import resources
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import statictabs
from miro.frontends.widgets import style
from miro.frontends.widgets import widgetutil
from miro.plat.frontends.widgets import widgetset

class TabListView(widgetset.TableView):
    def __init__(self, renderer):
        widgetset.TableView.__init__(self, 
                widgetset.TreeTableModel('object'))
        self.add_column('tab', 0, renderer, renderer.MIN_WIDTH)
        self.set_show_headers(False)
        self.set_background_color(style.TAB_LIST_BACKGROUND_COLOR)
        self.set_fixed_height(True)

class StaticTabList(object):
    """Handles the static tabs (the tabs on top that are always the same)."""
    def __init__(self):
        self.type = 'static'
        self.view = TabListView(style.StaticTabRenderer())
        self.view.allow_multiple_select(False)
        self.iter_map = {}
        self.add(statictabs.ChannelGuideTab())
        self.add(statictabs.SearchTab())
        self.add(statictabs.LibraryTab())
        self.add(statictabs.NewVideosTab())
        self.add(statictabs.DownloadsTab())
        self.view.model_changed()
        self.doing_change = False 
        # doing_change will be True if we are changing a bunch of tabs.  This
        # will cause us to not try to update things based on the selection
        # changing.

    def add(self, tab):
        iter = self.view.model.append(tab)
        self.iter_map[tab.id] = iter

    def update_download_count(self, count):
        iter = self.iter_map['downloading']
        tab = self.view.model[iter][0]
        tab.downloading = count
        self.view.model.update(iter, tab)

    def update_new_count(self, count):
        iter = self.iter_map['new']
        tab = self.view.model[iter][0]
        tab.unwatched = count
        self.view.model.update(iter, tab)

    def get_tab(self, name):
        return self.view.model[self.iter_map[name]][0]

class TabListDragHandler(object):
    def allowed_actions(self):
        return widgetset.DRAG_ACTION_MOVE

    def allowed_types(self):
        return (self.item_type, self.folder_type)

    def begin_drag(self, tableview, rows):
        type = self.item_type
        for r in rows:
            if r[0].is_folder:
                type = self.folder_type
                break
        return { type: '-'.join(str(r[0].id) for r in rows)}

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

    def reorder(self, model, parent, position, dragged_ids):
        if position >= 0:
            self.drop_row_iter = model.nth_child_iter(parent, position)
        else:
            self.drop_row_iter = None
        self.calc_drop_id(model)
        self.remove_dragged_rows(model, dragged_ids)
        return self.put_rows_back(model, parent)

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
                children = [tuple(r) for r in row.iterchildren()]
                self.removed_children[row[0].id] = children
                iter = self.remove_row(model, iter, tuple(row))
            else:
                child_iter = model.child_iter(iter)
                while child_iter is not None:
                    row = model[child_iter]
                    if row[0].id in dragged_ids:
                        child_iter = self.remove_row(model, child_iter,
                                tuple(row))
                    else:
                        child_iter = model.next_iter(child_iter)
                iter = model.next_iter(iter)

    def put_rows_back(self, model, parent):
        if self.drop_row_iter is None:
            def put_back(moved_row):
                return model.append_child(parent, *moved_row)
        else:
            def put_back(moved_row):
                return model.insert_before(self.drop_row_iter, *moved_row)
        retval = {}
        for removed_row in self.removed_rows:
            iter = put_back(removed_row)
            retval[removed_row[0].id] = iter
            children = self.removed_children.get(removed_row[0].id, [])
            for child_row in children:
                child_iter = model.append_child(iter, *child_row)
                retval[child_row[0].id] = child_iter
        return retval

class TabListDropHandler(object):
    def __init__(self, tablist):
        self.tablist = tablist

    def allowed_actions(self):
        return widgetset.DRAG_ACTION_COPY

    def allowed_types(self):
        return (self.item_type, self.folder_type)

    def validate_drop(self, table_view, model, type, source_actions, parent,
            position):
        if parent is None:
            is_folder = False
        elif position < 0:
            is_folder = model[parent][0].is_folder
        elif position < model.children_count(parent):
            iter = model.nth_child_iter(parent, position)
            is_folder = model[iter][0].is_folder
        else:
            is_folder = False
        if position == -1 and not is_folder:
            # Only folders can be dropped on
            return widgetset.DRAG_ACTION_NONE
        if (type == self.folder_type and
                ((position == -1 and is_folder) or parent is not None)):
            # Don't allow folders to be dropped in other folders
            return widgetset.DRAG_ACTION_NONE
        return widgetset.DRAG_ACTION_MOVE

    def accept_drop(self, table_view, model, type, source_actions, parent,
            position, data):
        self.tablist.doing_change = True
        selected_rows = [model[iter][0].id for iter in \
                table_view.get_selection()]
        table_view.unselect_all()
        dragged_ids = set([int(id) for id in data.split('-')])
        expanded_rows = [id for id in dragged_ids if \
                table_view.is_row_expanded(self.tablist.iter_map[id])]
        reorderer = TabDnDReorder()
        try:
            new_iters = reorderer.reorder(model, parent, position,
                    dragged_ids)
            self.tablist.iter_map.update(new_iters)
        finally:
            self.tablist.model_changed()
        for id in expanded_rows:
            table_view.set_row_expanded(self.tablist.iter_map[id], True)
        for id in selected_rows:
            iter = self.tablist.iter_map[id]
            parent = model.parent_iter(iter)
            if parent is None or table_view.is_row_expanded(parent):
                table_view.select(iter)
        self.tablist.send_new_order()
        self.tablist.doing_change = False
        return True

class FeedListDropHandler(TabListDropHandler):
    item_type = 'feed'
    folder_type = 'feed-with-folder'

class FeedListDragHandler(TabListDragHandler):
    item_type = 'feed'
    folder_type = 'feed-with-folder'

class PlaylistListDropHandler(TabListDropHandler):
    item_type = 'playlist'
    folder_type = 'playlist-with-folder'

    def allowed_actions(self):
        return (TabListDropHandler.allowed_actions(self) | 
                widgetset.DRAG_ACTION_COPY)

    def allowed_types(self):
        return TabListDropHandler.allowed_types(self) + ('downloaded-item',)

    def validate_drop(self, table_view, model, type, source_actions, parent,
            position):
        if type == 'downloaded-item':
            if (parent is not None and position == -1 and
                    not model[parent][0].is_folder):
                return widgetset.DRAG_ACTION_COPY
            else:
                return widgetset.DRAG_ACTION_NONE
        return TabListDropHandler.validate_drop(self, table_view, model, type,
                source_actions, parent, position)

    def accept_drop(self, table_view, model, type, source_actions, parent,
            position, data):
        if type == 'downloaded-item':
            if parent is not None and position == -1:
                playlist_id = model[parent][0].id
                video_ids = [int(id) for id in data.split('-')]
                messages.AddVideosToPlaylist(playlist_id,
                        video_ids).send_to_backend()
                return True
            # We shouldn't get here, because don't allow it in validate_drop.
            # Return False just in case
            return False
        return TabListDropHandler.accept_drop(self, table_view, model, type,
                source_actions, parent, position, data)

class PlaylistListDragHandler(TabListDragHandler):
    item_type = 'playlist'
    folder_type = 'playlist-with-folder'

class TabList(object):
    def __init__(self):
        self.view = TabListView(style.TabRenderer())
        self.view.allow_multiple_select(True)
        self.view.connect('row-expanded', self.on_row_expanded_change, True)
        self.view.connect('row-collapsed', self.on_row_expanded_change, False)
        self.iter_map = {}
        self.doing_change = False
        self.view.set_context_menu_callback(self.on_context_menu)

    def on_row_expanded_change(self, view, iter, expanded):
        id = self.view.model[iter][0].id
        message = messages.FolderExpandedChange(self.type, id, expanded)
        message.send_to_backend()

    def add(self, info, parent_id=None):
        self.init_info(info)
        if parent_id:
            parent_iter = self.iter_map[parent_id]
            iter = self.view.model.append_child(parent_iter, info)
        else:
            iter = self.view.model.append(info)
        self.iter_map[info.id] = iter

    def set_folder_expanded(self, id, expanded):
        self.view.set_row_expanded(self.iter_map[id], expanded)

    def update(self, info):
        self.init_info(info)
        self.view.model.update(self.iter_map[info.id], info)

    def remove(self, id_list):
        self.doing_change = True
        for id in id_list:
            try:
                iter = self.iter_map.pop(id)
            except KeyError:
                # child of a tab we already deleted
                continue
            self.forget_child_iters(iter)
            self.view.model.remove(iter)
        self.doing_change = False
        self.view.model_changed()
        app.tab_list_manager.recalc_selection()

    def forget_child_iters(self, parent_iter):
        model = self.view.model
        iter = model.child_iter(parent_iter)
        while iter is not None:
            id = model[iter][0].id
            del self.iter_map[id]
            iter = model.next_iter(iter)

    def model_changed(self):
        self.view.model_changed()

    def get_info(self, id):
        return self.view.model[self.iter_map[id]][0]

    def send_new_order(self):
        message = messages.TabsReordered(self.type)
        for row in self.view.model:
            info = row[0]
            message.append(info)
            for child in row.iterchildren():
                message.append_child(info.id, child[0])
        message.send_to_backend()

class SiteList(TabList):
    type = 'site'

    def init_info(self, info):
        thumb_path = resources.path('wimages/icon-site.png')
        info.icon = imagepool.get_surface(thumb_path)
        info.unwatched = info.available = 0

    def on_context_menu(self, table_view):
        return [
            (_('Copy URL to clipboard'), app.widgetapp.copy_site_url),
            (_('Rename Site'), app.widgetapp.rename_something),
            (_('Remove Site'), app.widgetapp.remove_current_site),
        ]

class NestedTabList(TabList):
    """Tablist for tabs that can be put into folders (playlists and feeds)."""

    def on_context_menu(self, table_view):
        selected_rows = [table_view.model[iter][0] for iter in \
                table_view.get_selection()]
        if len(selected_rows) == 1:
            if selected_rows[0].is_folder:
                return self.make_folder_context_menu()
            else:
                return self.make_single_context_menu()
        else:
            return self.make_multiple_context_menu()

class FeedList(NestedTabList):
    type = 'feed'

    def __init__(self):
        TabList.__init__(self)
        self.view.set_drag_source(FeedListDragHandler())
        self.view.set_drag_dest(FeedListDropHandler(self))

    def init_info(self, info):
        info.icon = imagepool.get_surface(info.tab_icon)

    def find_feed_with_url(self, url):
        for iter in self.iter_map.values():
            info = self.view.model[iter][0]
            if info.url == url:
                return info
        return None

    def make_folder_context_menu(self):
        return [
            (_('Update Channel Now'), app.widgetapp.update_selected_channels),
            (_('Rename Channel Folder'), app.widgetapp.rename_something),
            (_('Remove'), app.widgetapp.remove_current_feed)
        ]

    def make_single_context_menu(self):
        return [
            (_('Update Channel Now'), app.widgetapp.update_selected_channels),
            (_('Rename Channel'), app.widgetapp.rename_something),
            (_('Copy URL to clipboard'), app.widgetapp.copy_channel_url),
            (_('Remove'), app.widgetapp.remove_current_feed)
        ]

    def make_multiple_context_menu(self):
        return [
            (_('Update Channels Now'), app.widgetapp.update_selected_channels),
            (_('Remove'), app.widgetapp.remove_current_feed)
        ]

class PlaylistList(NestedTabList):
    type = 'playlist'

    def __init__(self):
        TabList.__init__(self)
        self.view.set_drag_source(PlaylistListDragHandler())
        self.view.set_drag_dest(PlaylistListDropHandler(self))

    def init_info(self, info):
        if info.is_folder:
            thumb_path = resources.path('wimages/icon-folder.png')
        else:
            thumb_path = resources.path('wimages/icon-playlist.png')
        info.icon = imagepool.get_surface(thumb_path)
        info.unwatched = info.available = 0

    def make_folder_context_menu(self):
        return [
            (_('Rename Playlist Folder'), app.widgetapp.rename_something),
            (_('Remove'), app.widgetapp.remove_current_playlist)
        ]

    def make_single_context_menu(self):
        return [
            (_('Rename Playlist'), app.widgetapp.rename_something),
            (_('Remove'), app.widgetapp.remove_current_playlist)
        ]

    def make_multiple_context_menu(self):
        return [
            (_('Remove'), app.widgetapp.remove_current_playlist)
        ]

class TabListBox(widgetset.Scroller):
    def __init__(self):
        widgetset.Scroller.__init__(self, False, True)
        background = widgetset.SolidBackground()
        background.set_background_color((style.TAB_LIST_BACKGROUND_COLOR))
        background.add(self.build_vbox())
        self.add(background)

    def build_vbox(self):
        tlm = app.tab_list_manager
        self.header_left_pad = tlm.feed_list.view.get_left_offset()
        vbox = widgetset.VBox()
        vbox.pack_start(tlm.static_tab_list.view)
        vbox.pack_start(self.build_header(_('SITES')))
        vbox.pack_start(tlm.site_list.view)
        vbox.pack_start(self.build_header(_('FEEDS')))
        vbox.pack_start(tlm.feed_list.view)
        vbox.pack_start(self.build_header(_('PLAYLISTS')))
        vbox.pack_start(tlm.playlist_list.view)
        return vbox

    def build_header(self, text):
        separator = widgetset.HThinSeparator(style.TAB_LIST_SEPARATOR_COLOR)

        label = widgetset.Label(text)
        label.set_bold(True)
        label.set_size(0.92)
        label.set_color(style.TAB_LIST_HEADER_COLOR)

        vbox = widgetset.VBox()
        vbox.pack_start(widgetutil.pad(separator, top=5, bottom=10))
        vbox.pack_start(widgetutil.align_left(label, 0, 5, self.header_left_pad))

        return vbox
