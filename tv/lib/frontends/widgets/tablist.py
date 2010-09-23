# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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
from miro import signals
from miro import messages
from miro.gtcache import gettext as _
from miro.plat import resources
from miro.frontends.widgets import style
from miro.frontends.widgets import separator
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import statictabs
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets import menus
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets import timer

def send_new_order():
    def append_items(sequence, type):
        for row in sequence:
            info = row[0]
            message.append(info, type)
            for child in row.iterchildren():
                message.append_child(info.id, child[0])
            
    message = messages.TabsReordered()
    append_items(app.tab_list_manager.feed_list.view.model, u'feed')
    append_items(app.tab_list_manager.audio_feed_list.view.model, u'audio-feed')
    append_items(app.tab_list_manager.playlist_list.view.model, u'playlist')
    message.send_to_backend()


class TabListView(widgetset.TableView):
    def __init__(self, renderer, table_model_class=None):
        if table_model_class is None:
            table_model_class = widgetset.TreeTableModel
        table_model = table_model_class('object', 'boolean', 'integer')
        # columns are:
        # - the tab_info object
        # - should the tab should be blinking?
        # - should we draw an uploading icon?  -1: no, 0-7: frame to draw
        widgetset.TableView.__init__(self, table_model)
        self.column = widgetset.TableColumn('tab', renderer, data=0, blink=1,
                updating_frame=2)
        self.column.set_min_width(renderer.MIN_WIDTH)
        self.add_column(self.column)
        self.set_show_headers(False)
        self.set_gradient_highlight(True)
        self.set_background_color(style.TAB_LIST_BACKGROUND_COLOR)
        self.set_fixed_height(True)
        self.set_auto_resizes(True)

    def append_tab(self, tab_info):
        return self.model.append(tab_info, False, -1)

    def append_child_tab(self, parent_iter, tab_info):
        return self.model.append_child(parent_iter, tab_info, False, -1)

    def update_tab(self, iter, tab_info):
        self.model.update_value(iter, 0, tab_info)

    def blink_tab(self, iter):
        self.model.update_value(iter, 1, True)

    def unblink_tab(self, iter):
        self.model.update_value(iter, 1, False)

    def pulse_updating_image(self, iter):
        frame = self.model[iter][2]
        self.model.update_value(iter, 2, (frame + 1) % 12)
        self.model_changed()

    def stop_updating_image(self, iter):
        self.model.update_value(iter, 2, -1)
        self.model_changed()

class TabBlinkerMixin(object):
    def blink_tab(self, id):
        self.view.blink_tab(self.iter_map[id])
        timer.add(1, self._unblink_tab, id)

    def _unblink_tab(self, id):
        # double check that the tab still exists
        if id in self.iter_map:
            self.view.unblink_tab(self.iter_map[id])

class StaticTabListBase(TabBlinkerMixin):

    def __init__(self):
        self.iter_map = {}
        self.doing_change = False 
        # doing_change will be True if we are changing a bunch of tabs.  This
        # will cause us to not try to update things based on the selection
        # changing.

    def add(self, tab):
        iter = self.view.append_tab(tab)
        self.iter_map[tab.id] = iter

    def remove(self, name):
        iter = self.iter_map.pop(name)
        self.view.model.remove(iter)

    def get_tab(self, name):
        return self.view.model[self.iter_map[name]][0]

class StaticTabList(StaticTabListBase):
    """Handles the static tabs (the tabs on top that are always the same)."""
    def __init__(self):
        StaticTabListBase.__init__(self)
        self.type = 'static'
        self.view = TabListView(style.StaticTabRenderer(),
                widgetset.TableModel)
        self.view.allow_multiple_select(False)
        self.view.set_fixed_height(False)

    def build_tabs(self):
        self.add(statictabs.ChannelGuideTab())
        self.add(statictabs.SearchTab())
        self.view.model_changed()

class LibraryTabList(StaticTabListBase):
    """Handles all Library related tabs - Video, Audio, Downloading..."""
    def __init__(self):
        StaticTabListBase.__init__(self)
        self.type = 'library'
        self.view = TabListView(style.StaticTabRenderer())
        self.view.allow_multiple_select(False)
        self.view.set_fixed_height(False)
        self.view.set_drag_dest(MediaTypeDropHandler())
        self.view.connect('selection-changed', self.on_selection_changed)
        self.auto_tabs = None
        self.auto_tabs_to_show = set()

    def build_tabs(self):
        self.add(statictabs.VideoLibraryTab())
        self.add(statictabs.AudioLibraryTab())
        self.add(statictabs.OtherLibraryTab())
        self.auto_tabs = {'downloading': statictabs.DownloadsTab(),
                          'conversions': statictabs.VideoConversionsTab()}
        self.view.model_changed()

    def update_auto_tab_count(self, name, count):
        if count > 0:
            self.auto_tabs_to_show.add(name)
            self.show_auto_tab(name)
        else:
            self.auto_tabs_to_show.discard(name)
            self.remove_auto_tab_if_not_selected(name)

    def show_auto_tab(self, name):
        try:
            tab = self.get_tab(name)
        except KeyError, e:
            self.add(self.auto_tabs[name])
    
    def remove_auto_tab_if_not_selected(self, name):
        if name not in self.iter_map:
            return
        # Don't remove the tab if it's currently selected.
        for iter in self.view.get_selection():
            info = self.view.model[iter][0]
            if info.id == name:
                return
        self.remove(name)

    def on_selection_changed(self, view):
        for name in self.auto_tabs:
            if name in self.iter_map and name not in self.auto_tabs_to_show:
                self.remove_auto_tab_if_not_selected(name)
                self.view.model_changed()

    def update_download_count(self, count, non_downloading_count):
        self.update_count('downloading', 'downloading', count, non_downloading_count)

    def update_conversions_count(self, running_count, other_count):
        self.update_count('conversions', 'downloading', running_count, other_count)

    def update_new_video_count(self, count):
        self.update_count('videos', 'unwatched', count)

    def update_new_audio_count(self, count):
        self.update_count('audios', 'unwatched', count)
    
    def update_count(self, key, attr, count, other_count=0):
        if key in self.auto_tabs:
            self.update_auto_tab_count(key, count+other_count)
        try:
            iter = self.iter_map[key]
        except KeyError, e:
            pass
        else:
            tab = self.view.model[iter][0]
            setattr(tab, attr, count)
            self.view.update_tab(iter, tab)
        self.view.model_changed()

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

    def reorder(self, source_model, dest_model, parent, position, dragged_ids):
        if position >= 0:
            self.drop_row_iter = dest_model.nth_child_iter(parent, position)
        else:
            self.drop_row_iter = None
        self.calc_drop_id(dest_model)
        self.remove_dragged_rows(source_model, dragged_ids)
        return self.put_rows_back(dest_model, parent)

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

class MediaTypeDropHandler(object):
    """Drop Handler that changes the media type (audio/video/other) of items
    that get dropped on it.
    """

    def allowed_types(self):
        return ('downloaded-item',)

    def allowed_actions(self):
        return widgetset.DRAG_ACTION_COPY

    def validate_drop(self, table_view, model, type, source_actions, parent,
            position):
        if (type == 'downloaded-item' and parent is not None
            and position == -1):
            return widgetset.DRAG_ACTION_COPY
        return widgetset.DRAG_ACTION_NONE

    def accept_drop(self, table_view, model, type, source_actions, parent,
            position, data):
        if type == 'downloaded-item':
            if parent is not None and position == -1:
                video_ids = [int(id) for id in data.split('-')]
                media_type = model[parent][0].media_type
                m = messages.SetItemMediaType(media_type, video_ids)
                m.send_to_backend()
                return True
        # We shouldn't get here, because don't allow it in validate_drop.
        # Return False just in case
        return False

class TabListDropHandler(object):
    def __init__(self, tablist):
        self.tablist = tablist

    def allowed_actions(self):
        return widgetset.DRAG_ACTION_COPY

    def allowed_types(self):
        return self.item_types + self.folder_types

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
        if (type in self.folder_types and
                ((position == -1 and is_folder) or parent is not None)):
            # Don't allow folders to be dropped in other folders
            return widgetset.DRAG_ACTION_NONE
        elif type not in self.item_types + self.folder_types:
            return widgetset.DRAG_ACTION_NONE
        return widgetset.DRAG_ACTION_MOVE

    def accept_drop(self, table_view, model, type, source_actions, parent,
            position, data):
        if (type in ('feed', 'feed-with-folder')
                and self.tablist == app.tab_list_manager.audio_feed_list):
            source_tablist = app.tab_list_manager.feed_list
            dest_tablist = self.tablist
        elif (type in ('audio-feed', 'audio-feed-with-folder')
                and self.tablist == app.tab_list_manager.feed_list):
            source_tablist = app.tab_list_manager.audio_feed_list
            dest_tablist = self.tablist
        else:
            source_tablist = dest_tablist = self.tablist
        selected_infos = app.tab_list_manager.get_selection()[1]
        selected_rows = [info.id for info in selected_infos]
        source_tablist.doing_change = dest_tablist.doing_change = True
        source_tablist.view.unselect_all()
        dest_tablist.view.unselect_all()
        dragged_ids = set([int(id) for id in data.split('-')])
        expanded_rows = [id for id in dragged_ids if \
                source_tablist.view.is_row_expanded(source_tablist.iter_map[id])]
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
        for id in expanded_rows:
            dest_tablist.view.set_row_expanded(dest_tablist.iter_map[id], True)
        try:
            for id in selected_rows:
                iter = dest_tablist.iter_map[id]
                parent = model.parent_iter(iter)
                if parent is None or dest_tablist.view.is_row_expanded(parent):
                    dest_tablist.view.select(iter)
        except KeyError:
            pass

        send_new_order()
        source_tablist.doing_change = False
        dest_tablist.doing_change = False
        app.tab_list_manager.handle_moved_tabs_to_list(dest_tablist)
        return True

class FeedListDropHandler(TabListDropHandler):
    item_types = ('feed', 'audio-feed')
    folder_types = ('feed-with-folder', 'audio-feed-with-folder')

class FeedListDragHandler(TabListDragHandler):
    item_type = 'feed'
    folder_type = 'feed-with-folder'

class AudioFeedListDragHandler(TabListDragHandler):
    item_type = 'audio-feed'
    folder_type = 'audio-feed-with-folder'

class PlaylistListDropHandler(TabListDropHandler):
    item_types = ('playlist',)
    folder_types = ('playlist-with-folder',)

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

class TabList(signals.SignalEmitter, TabBlinkerMixin):
    """Handles a list of tabs on the left-side of Miro.

    signals:

    tab-name-changed (tablist, old_name, new_new) -- The name of a tab
        changed.
    """

    ALLOW_MULTIPLE = True

    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.create_signal('tab-name-changed')
        self.view = TabListView(style.TabRenderer())
        self.view.allow_multiple_select(self.ALLOW_MULTIPLE)
        self.view.connect_weak('key-press', self.on_key_press)
        self.view.connect('row-expanded', self.on_row_expanded_change, True)
        self.view.connect('row-collapsed', self.on_row_expanded_change, False)
        self.iter_map = {}
        self.doing_change = False
        self.view.set_context_menu_callback(self.on_context_menu)

    def reset_list(self, message):
        self.doing_change = True
        selected_ids = set(self.view.model[iter][0].id for iter in
                self.view.get_selection())
        iter = self.view.model.first_iter()
        while iter is not None:
            iter = self.view.model.remove(iter)
        self.iter_map = {}
        for info in message.toplevels:
            self.add(info)
            if info.is_folder:
                for child_info in message.folder_children[info.id]:
                    self.add(child_info, info.id)
        self.model_changed()
        for info in message.toplevels:
            if info.is_folder:
                expanded = (info.id in message.expanded_folders)
                self.set_folder_expanded(info.id, expanded)
        for id in selected_ids:
            self.view.select(self.iter_map[id])
        self.doing_change = False

    def on_key_press(self, view, key, mods):
        if key == menus.DELETE:
            self.on_delete_key_pressed()
            return True

    def on_row_expanded_change(self, view, iter, expanded):
        id = self.view.model[iter][0].id
        message = messages.FolderExpandedChange(self.type, id, expanded)
        message.send_to_backend()

    def add(self, info, parent_id=None):
        self.init_info(info)
        if parent_id:
            parent_iter = self.iter_map[parent_id]
            iter = self.view.append_child_tab(parent_iter, info)
        else:
            iter = self.view.append_tab(info)
        self.iter_map[info.id] = iter

    def set_folder_expanded(self, id, expanded):
        self.view.set_row_expanded(self.iter_map[id], expanded)

    def update(self, info):
        self.init_info(info)
        old_name = self.view.model[self.iter_map[info.id]][0].name
        self.view.update_tab(self.iter_map[info.id], info)
        if old_name != info.name:
            self.emit('tab-name-changed', old_name, info.name)

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

    def has_info(self, id):
        return id in self.iter_map

    def get_child_count(self, id):
        count = 0
        child_iter = self.view.model.child_iter(self.iter_map[id])
        while child_iter is not None:
            count += 1
            child_iter = self.view.model.next_iter(child_iter)
        return count

    def on_delete_key_pressed(self):
        """For subclasses to override."""
        pass

class SiteList(TabList):
    type = 'site'

    ALLOW_MULTIPLE = True

    def on_delete_key_pressed(self):
        app.widgetapp.remove_current_site()

    def init_info(self, info):
        if info.favicon:
            thumb_path = info.favicon
        else:
            thumb_path = resources.path('images/icon-site.png')
        surface = imagepool.get_surface(thumb_path)
        if surface.width > 16 or surface.height > 16:
            info.icon = imagepool.get_surface(thumb_path, size=(16, 16))
        else:
            info.icon = imagepool.get_surface(thumb_path)
        info.unwatched = info.available = 0

    def on_context_menu(self, table_view):
        selected_rows = [table_view.model[iter][0] for iter in \
                table_view.get_selection()]
        if len(selected_rows) == 1:
            return [
                (_('Copy URL to clipboard'), app.widgetapp.copy_site_url),
                (_('Rename Website'), app.widgetapp.rename_something),
                (_('Remove Website'), app.widgetapp.remove_current_site),
            ]
        else:
            return [
                (_('Remove Websites'), app.widgetapp.remove_current_site),
            ]

class NestedTabList(TabList):
    """Tablist for tabs that can be put into folders (playlists and feeds)."""

    def on_context_menu(self, table_view):
        selected_rows = [table_view.model[iter][0] for iter in \
                table_view.get_selection()]
        if len(selected_rows) == 1:
            if selected_rows[0].is_folder:
                return self.make_folder_context_menu(selected_rows[0])
            else:
                return self.make_single_context_menu(selected_rows[0])
        else:
            return self.make_multiple_context_menu()

class FeedList(NestedTabList):
    type = 'feed'

    def __init__(self):
        TabList.__init__(self)
        self.setup_dnd()
        self.updating_animations = {}

    def setup_dnd(self):
        self.view.set_drag_source(FeedListDragHandler())
        self.view.set_drag_dest(FeedListDropHandler(self))

    def on_delete_key_pressed(self):
        app.widgetapp.remove_current_feed()

    def feed_is_updating(self, info):
        if info.id in self.updating_animations:
            return
        timer_id = timer.add(0, self.pulse_updating_animation, info.id)
        self.updating_animations[info.id] = timer_id

    def feed_not_updating(self, info):
        if info.id not in self.updating_animations:
            return
        self.view.stop_updating_image(self.iter_map[info.id])
        timer_id = self.updating_animations.pop(info.id)
        timer.cancel(timer_id)

    def pulse_updating_animation(self, id):
        try:
            iter = self.iter_map[id]
        except KeyError:
            # feed was removed
            del self.updating_animations[id]
            return
        self.view.pulse_updating_image(iter)
        timer_id = timer.add(0.1, self.pulse_updating_animation, id)
        self.updating_animations[id] = timer_id

    def init_info(self, info):
        info.icon = imagepool.get_surface(info.tab_icon, size=(16, 16))
        if info.is_updating:
            self.feed_is_updating(info)
        else:
            self.feed_not_updating(info)

    def get_feeds(self):
        infos = [self.view.model[i][0] for i in self.iter_map.values()]
        return infos

    def find_feed_with_url(self, url):
        for iter in self.iter_map.values():
            info = self.view.model[iter][0]
            if info.url == url:
                return info
        return None

    def make_folder_context_menu(self, obj):
        return [
            (_('Update Feeds In Folder'), app.widgetapp.update_selected_feeds),
            (_('Rename Feed Folder'), app.widgetapp.rename_something),
            (_('Remove'), app.widgetapp.remove_current_feed)
        ]

    def make_single_context_menu(self, obj):
        menu = [
            (_('Update Feed Now'), app.widgetapp.update_selected_feeds)
        ]

        menu.append((_('Rename'), app.widgetapp.rename_something))
        if not obj.has_original_title:
            menu.append((_('Revert Feed Name'), app.widgetapp.revert_feed_name))
        menu.append((_('Copy URL to clipboard'), app.widgetapp.copy_feed_url))
        menu.append((_('Remove'), app.widgetapp.remove_current_feed))
        return menu

    def make_multiple_context_menu(self):
        return [
            (_('Update Feeds Now'), app.widgetapp.update_selected_feeds),
            (_('Remove'), app.widgetapp.remove_current_feed)
        ]

class AudioFeedList(FeedList):
    def setup_dnd(self):
        self.view.set_drag_source(AudioFeedListDragHandler())
        self.view.set_drag_dest(FeedListDropHandler(self))

    type = 'audio-feed'

class PlaylistList(NestedTabList):
    type = 'playlist'

    def __init__(self):
        TabList.__init__(self)
        self.view.set_drag_source(PlaylistListDragHandler())
        self.view.set_drag_dest(PlaylistListDropHandler(self))

    def on_delete_key_pressed(self):
        app.widgetapp.remove_current_playlist()

    def init_info(self, info):
        if info.is_folder:
            thumb_path = resources.path('images/icon-folder.png')
        else:
            thumb_path = resources.path('images/icon-playlist.png')
        info.icon = imagepool.get_surface(thumb_path)
        info.unwatched = info.available = 0

    def get_playlists(self):
        infos = [self.view.model[i][0] for i in self.iter_map.values()]
        return infos

    def make_folder_context_menu(self, obj):
        return [
            (_('Rename Playlist Folder'), app.widgetapp.rename_something),
            (_('Remove'), app.widgetapp.remove_current_playlist)
        ]

    def make_single_context_menu(self, obj):
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
        self.set_background_color((style.TAB_LIST_BACKGROUND_COLOR))

    def build_vbox(self):
        tlm = app.tab_list_manager
        self.header_left_pad = 10
        vbox = widgetset.VBox()
        vbox.pack_start(tlm.static_tab_list.view)
        vbox.pack_start(self.build_header(_('LIBRARY')))
        vbox.pack_start(tlm.library_tab_list.view)
        vbox.pack_start(self.build_header(_('WEBSITES')))
        vbox.pack_start(tlm.site_list.view)
        vbox.pack_start(self.build_header(_('VIDEO FEEDS')))
        vbox.pack_start(tlm.feed_list.view)
        vbox.pack_start(self.build_header(_('AUDIO FEEDS')))
        vbox.pack_start(tlm.audio_feed_list.view)
        vbox.pack_start(self.build_header(_('PLAYLISTS')))
        vbox.pack_start(tlm.playlist_list.view)
        return vbox

    def build_header(self, text):
        label = widgetset.Label(text)
        label.set_bold(True)
        label.set_size(0.85)
        label.set_color(style.TAB_LIST_HEADER_COLOR)

        vbox = widgetset.VBox()
        vbox.pack_start(widgetutil.align_left(label, 
                top_pad=5, bottom_pad=5, left_pad=self.header_left_pad))

        return vbox
