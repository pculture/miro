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

"""Displays the list of tabs on the left-hand side of the app."""

from miro import app
from miro import signals
from miro import messages
from miro.gtcache import gettext as _
from miro.plat import resources
from miro import prefs
from miro.frontends.widgets import style
from miro.frontends.widgets import separator
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import statictabs
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets import menus
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets import timer

# this maps guide urls to titles we'd rather they use.
_guide_url_to_title_map = {
    prefs.CHANNEL_GUIDE_URL.default: _("Miro Guide")
    }

# this maps guide urls to icons we'd rather they use.
_guide_url_to_icon_map = {
    prefs.CHANNEL_GUIDE_URL.default: 'icon-guide'
    }

def send_new_order():
    def append_items(sequence, typ):
        parent = sequence[0]
        for row in parent.iterchildren():
            info = row[0]
            message.append(info, typ)
            for child in row.iterchildren():
                message.append_child(info.id, child[0])

    message = messages.TabsReordered()
    append_items(app.tab_list_manager.feed_list.view.model, u'feed')
    append_items(app.tab_list_manager.playlist_list.view.model, u'playlist')
    message.send_to_backend()

class TabInfo(object):
    """
    Simple Info object which holds the data for the top of a tab list.
    """
    type = u'tab'
    is_folder = False # doesn't work like a real folder
    tall = True
    bolded = True
    unwatched = available = 0
    is_directory_feed = False

    def __init__(self, name, icon_name):
        self.name = name
        self.id = u'%s-base-tab' % name
        self.icon_name = icon_name
        self.icon = widgetutil.make_surface(self.icon_name)
        self.active_icon = widgetutil.make_surface(self.icon_name + '_active')


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

class TabUpdaterMixin(object):
    def __init__(self):
        self.updating_animations = {}

    def start_updating(self, id_):
        # The spinning wheel is constantly updating the cell value, between 
        # validating the cell value for the drag and drop and the actual drop
        # the cell value most likely changes, and some GUI toolkits may get
        # confused.
        #
        # We'll let the underlying platform code figure out what's the best
        # thing to do here.
        self.view.set_volatile(True)
        if id_ in self.updating_animations:
            return
        timer_id = timer.add(0, self.pulse_updating_animation, id_)
        self.updating_animations[id_] = timer_id

    def stop_updating(self, id_):
        self.view.set_volatile(False)
        if id_ not in self.updating_animations:
            return
        self.view.stop_updating_image(self.iter_map[id_])
        timer_id = self.updating_animations.pop(id_)
        timer.cancel(timer_id)

    def pulse_updating_animation(self, id_):
        try:
            iter = self.iter_map[id_]
        except KeyError:
            # feed was removed
            del self.updating_animations[id_]
            return
        self.view.pulse_updating_image(iter)
        timer_id = timer.add(0.1, self.pulse_updating_animation, id_)
        self.updating_animations[id_] = timer_id

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
        self.type = u'static'
        self.view = TabListView(style.StaticTabRenderer(),
                widgetset.TableModel)
        self.view.allow_multiple_select(False)
        self.view.set_fixed_height(False)

    def build_tabs(self):
        self.add(statictabs.SearchTab())
        self.view.model_changed()

class LibraryTabList(StaticTabListBase):
    """Handles all Library related tabs - Video, Audio, Downloading..."""
    def __init__(self):
        StaticTabListBase.__init__(self)
        self.type = u'library'
        self.view = TabListView(style.StaticTabRenderer(),
                                widgetset.TableModel)
        self.view.allow_multiple_select(False)
        self.view.set_fixed_height(False)
        self.view.set_drag_dest(MediaTypeDropHandler())
        self.view.connect('selection-changed', self.on_selection_changed)
        self.auto_tabs = None
        self.auto_tabs_to_show = set()

    def build_tabs(self):
        self.add(statictabs.VideoLibraryTab())
        self.add(statictabs.AudioLibraryTab())
        self.auto_tabs = {'downloading': statictabs.DownloadsTab(),
                          'conversions': statictabs.ConversionsTab(),
                          'others': statictabs.OthersTab()}
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
        self.update_count('downloading', 'downloading', count,
                          non_downloading_count)

    def update_conversions_count(self, running_count, other_count):
        self.update_count('conversions', 'downloading', running_count,
                          other_count)

    def update_others_count(self, count):
        self.update_count('others', 'others', count) # second param no special
                                                     # meaning for this case... ?

    def update_new_video_count(self, count):
        self.update_count('videos', 'unwatched', count)

    def update_new_audio_count(self, count):
        self.update_count('music', 'unwatched', count)
    
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
        if iter is None:
            return
        iter = model.child_iter(iter)
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

    def validate_drop(self, table_view, model, typ, source_actions, parent,
            position):
        if (typ == 'downloaded-item' and parent is not None
            and position == -1):
            return widgetset.DRAG_ACTION_COPY
        return widgetset.DRAG_ACTION_NONE

    def accept_drop(self, table_view, model, typ, source_actions, parent,
            position, data):
        if typ == 'downloaded-item':
            if parent is not None and position == -1:
                video_ids = [int(id) for id in data.split('-')]
                media_type = model[parent][0].media_type
                m = messages.SetItemMediaType(media_type, video_ids)
                m.send_to_backend()
                return True
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
            iter = model.nth_child_iter(parent, position)
            is_folder = model[iter][0].is_folder
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
        dragged_ids = set([int(id) for id in data.split('-')])
        expanded_rows = [id for id in dragged_ids if \
                source_tablist.view.is_row_expanded(
                source_tablist.iter_map[id])]
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
                video_ids = [int(id) for id in data.split('-')]
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
        video_ids = [int(id) for id in data.split('-')]
        device = model[parent][0]
        messages.DeviceSyncMedia(device, video_ids).send_to_backend()

class PlaylistListDragHandler(TabListDragHandler):
    item_type = u'playlist'
    folder_type = u'playlist-with-folder'

class TabList(signals.SignalEmitter, TabBlinkerMixin):
    """Handles a list of tabs on the left-side of Miro.

    signals:

    tab-name-changed (tablist, old_name, new_new) -- The name of a tab
        changed.
    """

    ALLOW_MULTIPLE = True

    render_class = style.TabRenderer

    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.create_signal('tab-name-changed')
        self.view = TabListView(self.render_class())
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
        self._clear_list()
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

    def _clear_list(self):
        iter = self.view.model.first_iter()
        while iter is not None:
            iter = self.view.model.remove(iter)
        self.iter_map = {}

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

    def set_folder_expanded(self, id_, expanded):
        self.view.set_row_expanded(self.iter_map[id_], expanded)

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


class DeviceTabListHandler(object):
    def __init__(self, tablist):
        self.tablist = tablist

    def _fake_info(self, info, name):
        new_data = {
            'fake': True,
            'tab_type': name.lower(),
            'id': '%s-%s' % (info.id, name.lower()),
            'name': name,
            'icon': imagepool.get_surface(
                resources.path('images/icon-%s.png' % name.lower()))
            }

        # hack to create a DeviceInfo without dealing with __init__
        di = messages.DeviceInfo.__new__(messages.DeviceInfo)
        di.__dict__ = info.__dict__.copy()
        di.__dict__.update(new_data)
        return di

    def _add_fake_tabs(self, info):
        self.doing_change = True
        HideableTabList.add(self.tablist, self._fake_info(info, 'Video'), info.id)
        HideableTabList.add(self.tablist, self._fake_info(info, 'Audio'), info.id)
        self.tablist.model_changed()
        self.tablist.set_folder_expanded(info.id, True)
        self.doing_change = False

    def add(self, info):
        HideableTabList.add(self.tablist, info)
        if info.mount and not info.info.has_multiple_devices:
            self._add_fake_tabs(info)

    def update(self, info):
        if not self.tablist.has_info(info.id):
            # this gets called if a sync is in progress when the device
            # disappears
            return
        if info.mount and not info.info.has_multiple_devices and \
                not self.tablist.get_child_count(info.id):
            self._add_fake_tabs(info)
        elif not info.mount and self.tablist.get_child_count(info.id):
            parent_iter = self.tablist.iter_map[info.id]
            model = self.tablist.view.model
            next_iter = model.child_iter(parent_iter)
            while next_iter is not None:
                iter = next_iter
                next_iter = model.next_iter(next_iter)
                model.remove(iter)
        HideableTabList.update(self.tablist, info)

    def init_info(self, info):
        info.type = u'device'
        info.unwatched = info.available = 0
        if not getattr(info, 'fake', False):
            thumb_path = resources.path('images/phone.png')
            info.icon = imagepool.get_surface(thumb_path)
            if getattr(info, 'is_updating', False):
                self.tablist.start_updating(info.id)
            else:
                self.tablist.stop_updating(info.id)

    def on_hotspot_clicked(self, view, hotspot, iter):
        if hotspot == 'eject-device':
            info = view.model[iter][0]
            messages.DeviceEject(info).send_to_backend()

class SharingTabListHandler(object):
    def __init__(self, tablist):
        self.tablist = tablist

    def on_row_clicked(self, view, iter):
        info = view.model[iter][0]
        if info.type == u'sharing':
            # Only display disconnect icon for the share entry not the playlists.
            if not info.parent_id:
                info.mount = True
            view.model_changed()
        else:
            HideableTabList.on_row_clicked(self.tablist, view, iter)

    def on_hotspot_clicked(self, view, hotspot, iter):
        if hotspot == 'eject-device':
            # Don't track this tab anymore for music.
            info = view.model[iter][0]
            info.mount = False
            # We must stop the playback if we are playing from the same
            # share that we are ejecting from.
            host = info.host
            port = info.port
            item = app.playback_manager.get_playing_item()
            remote_item = False
            if item and item.remote:
                remote_item = True
            if remote_item and item.host == host and item.port == port:
                app.playback_manager.stop(save_resume_time=False)
            # Default to select the guide.  There's nothing more to see here.
            typ, selected_tabs = app.tab_list_manager.get_selection()
            if typ == u'sharing' and (info == selected_tabs[0] or
              getattr(selected_tabs[0], 'parent_id', None) == info.id):
                app.tab_list_manager.select_guide()
            messages.SharingEject(info).send_to_backend()

    def init_info(self, info):
        info.type = u'sharing'
        info.unwatched = info.available = 0
        if info.is_folder:
            thumb_path = resources.path('images/phone.png')
        else:
            thumb_path = resources.path('images/icon-playlist.png')
        info.icon = imagepool.get_surface(thumb_path)

class HideableTabList(TabList):
    """
    A type of tablist which nests under a base tab.  Connect,
    Sources/Sites/Guides, Stores, Feeds, and Playlists are all of this type.
    """
    def __init__(self):
        TabList.__init__(self)
        self.added_children = False
        self.info = TabInfo(self.name, self.icon_name)
        self.view.connect('selection-changed', self.on_selection_changed)
        TabList.add(self, self.info)

    def add(self, info, parent_id=None):
        if parent_id is None:
            parent_id = self.info.id
        TabList.add(self, info, parent_id)
        if not self.added_children:
            self.view.model_changed()
            self.set_folder_expanded(self.info.id, True)
            self.added_children = True

    def _clear_list(self):
        iter = self.view.model.first_iter()
        if iter is None:
            return
        iter = self.view.model.child_iter(iter)
        while iter is not None:
            iter = self.view.model.remove(iter)
        self.iter_map = {self.info.id: self.iter_map[self.info.id]}

    def on_selection_changed(self, view):
        for iter in view.get_selection():
            if view.model[iter][0] is self.info:
                if not view.is_row_expanded(iter):
                    self.set_folder_expanded(self.info.id, True)
                return

    def on_row_expanded_change(self, view, iter, expanded):
        info = self.view.model[iter][0]
        if info is not self.info:
            TabList.on_row_expanded_change(self, view, iter, expanded)

class ConnectList(HideableTabList, TabUpdaterMixin):
    name = _('Connect')
    icon_name = 'icon-connect'
    type = u'connect'

    ALLOW_MULTIPLE = False

    render_class = style.ConnectTabRenderer

    def __init__(self):
        HideableTabList.__init__(self)
        TabUpdaterMixin.__init__(self)
        self.info_class_map = {
            messages.DeviceInfo: DeviceTabListHandler(self),
            messages.SharingInfo: SharingTabListHandler(self),
            TabInfo: None,
            }
        self.view.connect_weak('hotspot-clicked', self.on_hotspot_clicked)
        self.view.connect_weak('row-clicked', self.on_row_clicked)
        self.view.set_drag_dest(DeviceDropHandler(self))

    def on_row_expanded_change(self, view, iter, expanded):
        info = self.view.model[iter][0]
        if info is self.info:
            HideableTabList.on_row_expanded_change(self, view, iter, expanded)

    def on_delete_key_pressed(self):
        # neither handler deals with this
        return

    def on_context_menu(self, view):
        # neither handle deals with this
        return []

    def on_row_clicked(self, view, iter):
        info = self.view.model[iter][0]
        handler = self.info_class_map[type(info)]
        if hasattr(handler, 'on_row_clicked'):
            return handler.on_row_clicked(view, iter)

    def on_hotspot_clicked(self, view, hotspot, iter):
        info = self.view.model[iter][0]
        handler = self.info_class_map[type(info)]
        return handler.on_hotspot_clicked(view, hotspot, iter)

    def init_info(self, info):
        if info is self.info:
            return
        handler = self.info_class_map[type(info)]
        return handler.init_info(info)

    def add(self, info, parent_id=None):
        handler = self.info_class_map[type(info)]
        if hasattr(handler, 'add'):
            handler.add(info) # device doesn't use the parent_id
        else:
            HideableTabList.add(self, info, parent_id)

    def update(self, info):
        handler = self.info_class_map[type(info)]
        if hasattr(handler, 'update'):
            handler.update(info)
        else:
            HideableTabList.update(self, info)

class SiteList(HideableTabList):
    type = u'site'
    name = _('Sources')
    icon_name = 'icon-site'

    ALLOW_MULTIPLE = True

    def on_delete_key_pressed(self):
        selected_rows = [self.view.model[iter][0] for iter in \
                         self.view.get_selection()]
        if len(selected_rows) == 1 and selected_rows[0].default:
            return # don't delete the default
        app.widgetapp.remove_current_site()

    def init_info(self, info):
        if info is self.info:
            return
        if info.default: # default guide has some special rules
            self.default_info = info
            if info.url in _guide_url_to_title_map:
                info.name = _guide_url_to_title_map[info.url]
            if info.url in _guide_url_to_icon_map:
                # one of our default guides
                info.icon_name = _guide_url_to_icon_map[info.url]
                info.icon = widgetutil.make_surface(info.icon_name)
            elif info.faviconIsDefault:
                # theme guide with the default favicon
                info.icon = widgetutil.make_surface('icon-guide')
            else:
                # theme guide with a favicon
                surface = imagepool.get_surface(info.favicon)
                if surface.width != 25 or surface.height != 25:
                    self.icon = imagepool.get_surface(info.favicon,
                                                      size=(25, 25))
                else:
                    self.icon = surface
        else:
            if info.favicon:
                thumb_path = info.favicon
            else:
                thumb_path = resources.path('images/icon-site.png')
                info.active_icon = imagepool.get_surface(
                    resources.path('image/icon-site_active.png'))
            surface = imagepool.get_surface(thumb_path)
            if surface.width > 16 or surface.height > 16:
                info.icon = imagepool.get_surface(thumb_path, size=(16, 16))
            else:
                info.icon = surface
        info.unwatched = info.available = 0
        info.type = self.type

    def on_context_menu(self, table_view):
        selected_rows = [table_view.model[iter][0] for iter in \
                table_view.get_selection()]
        editable = not bool([True for info in selected_rows if info.default])
        if len(selected_rows) == 1:
            rows = [(_('Copy URL to clipboard'), app.widgetapp.copy_site_url)]
            if editable:
                rows.extend([
                    (_('Rename Website'), app.widgetapp.rename_something),
                    (_('Remove Website'), app.widgetapp.remove_current_site)])
            return rows
        elif editable:
            return [
                (_('Remove Websites'), app.widgetapp.remove_current_site),
            ]
        else:
            return []

class StoreList(SiteList):
    type = u'store'
    name = _('Stores')
    icon_name = 'icon-store'

    ALLOW_MULTIPLE = False

    def on_delete_key_pressed(self):
        pass # XXX: can't delete stores(?)

    def on_context_menu(self, table_view):
        selected_rows = [table_view.model[iter][0] for iter in \
                table_view.get_selection()]
        if len(selected_rows) == 1:
            return [
                (_('Copy URL to clipboard'), app.widgetapp.copy_site_url),
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

class FeedList(HideableTabList, NestedTabList, TabUpdaterMixin):
    type = u'feed'
    name = _('Podcasts')
    icon_name = 'icon-podcast'

    def __init__(self):
        HideableTabList.__init__(self)
        TabUpdaterMixin.__init__(self)
        self.setup_dnd()

    def setup_dnd(self):
        self.view.set_drag_source(FeedListDragHandler())
        self.view.set_drag_dest(FeedListDropHandler(self))

    def on_delete_key_pressed(self):
        app.widgetapp.remove_current_feed()

    def init_info(self, info):
        if info is self.info:
            return
        info.type = self.type
        info.icon = imagepool.get_surface(info.tab_icon, size=(16, 16))
        if info.is_updating:
            self.start_updating(info.id)
        else:
            self.stop_updating(info.id)

    def get_feeds(self):
        infos = [self.view.model[i][0] for (k, i) in self.iter_map.items()
                 if k != self.info.id]
        return infos

    def find_feed_with_url(self, url):
        for iter in self.iter_map.values():
            info = self.view.model[iter][0]
            if info is self:
                continue
            if info.url == url:
                return info
        return None

    def make_folder_context_menu(self, obj):
        return [
            (_('Update Podcasts In Folder'), app.widgetapp.update_selected_feeds),
            (_('Rename Podcast Folder'), app.widgetapp.rename_something),
            (_('Remove'), app.widgetapp.remove_current_feed)
        ]

    def make_single_context_menu(self, obj):
        menu = [
            (_('Update Podcast Now'), app.widgetapp.update_selected_feeds)
        ]

        menu.append((_('Rename'), app.widgetapp.rename_something))
        if not obj.has_original_title:
            menu.append((_('Revert Podcast Name'),
                         app.widgetapp.revert_feed_name))
        menu.append((_('Settings'), app.widgetapp.feed_settings))
        menu.append((_('Copy URL to clipboard'), app.widgetapp.copy_feed_url))
        menu.append((_('Remove'), app.widgetapp.remove_current_feed))
        return menu

    def make_multiple_context_menu(self):
        return [
            (_('Update Podcasts Now'), app.widgetapp.update_selected_feeds),
            (_('Remove'), app.widgetapp.remove_current_feed)
        ]


class PlaylistList(HideableTabList, NestedTabList):
    type = u'playlist'
    name = _('Playlists')
    icon_name = 'icon-playlist'

    def __init__(self):
        HideableTabList.__init__(self)
        self.view.set_drag_source(PlaylistListDragHandler())
        self.view.set_drag_dest(PlaylistListDropHandler(self))

    def on_delete_key_pressed(self):
        app.widgetapp.remove_current_playlist()

    def init_info(self, info):
        if info is self.info:
            return
        if info.is_folder:
            info.icon = imagepool.get_surface(
                resources.path('images/icon-folder.png'))
        else:
            info.icon = imagepool.get_surface(
                resources.path('images/icon-playlist.png'))
            info.active_icon = imagepool.get_surface(
                resources.path('images/icon-playlist_active.png'))
        info.type = self.type
        info.unwatched = info.available = 0

    def get_playlists(self):
        infos = [self.view.model[i][0] for (k, i) in self.iter_map.items()
                 if k != self.info.id]
        return infos

    def find_playlist_with_name(self, name):
        for iter in self.iter_map.values():
            info = self.view.model[iter][0]
            if info is self:
                continue
            if info.name == name:
                return info
        return None

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
        vbox.pack_start(tlm.library_tab_list.view)
        vbox.pack_start(tlm.static_tab_list.view)
        vbox.pack_start(tlm.connect_list.view)
        vbox.pack_start(tlm.site_list.view)
        vbox.pack_start(tlm.store_list.view)
        vbox.pack_start(tlm.feed_list.view)
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
