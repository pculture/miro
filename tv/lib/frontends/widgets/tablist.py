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

import collections
import itertools
from hashlib import md5
try:
    import cPickle as pickle
except ImportError:
    import pickle
from contextlib import contextmanager
import logging
import os

from miro import app
from miro import prefs
from miro import signals
from miro import messages
from miro import errors
from miro.gtcache import gettext as _
from miro.plat import resources
from miro.frontends.widgets import imagepool
from miro.frontends.widgets import keyboard
from miro.frontends.widgets import playback
from miro.frontends.widgets import statictabs
from miro.frontends.widgets import style
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets.tablistdnd import (FeedListDragHandler,
     FeedListDropHandler, PlaylistListDragHandler, PlaylistListDropHandler,
     MediaTypeDropHandler, DeviceDropHandler)
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets import timer

class TabInfo(object):
    """Simple Info object which holds the data for a top-level tab."""
    type = u'tab'
    is_folder = False # doesn't work like a real folder
    tall = True
    unwatched = available = 0
    autodownload_mode = u'off'
    is_directory_feed = False

    def __init__(self, tab_class, name, icon_name):
        # "type" is overused, so tab_class refers to the type class
        # attribute of the tab.  e.g. "connect", "feed", ...
        self.tab_class = tab_class
        self.name = name
        self.id = u'%s-base-tab' % tab_class
        self.icon_name = icon_name
        self.thumbnail = resources.path('images/%s.png' % icon_name)
        self.icon = widgetutil.make_surface(self.icon_name)
        self.active_icon = widgetutil.make_surface(self.icon_name + '_active')

class TabListView(widgetset.TableView):
    """TableView for a tablist."""
    draws_selection = True

    def __init__(self, name, renderer, table_model_class=None):
        self.name = name
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
        self.set_fixed_height(False)
        self.set_auto_resizes(True)

    def __str__(self):
        return "TabList(%s)" % (self.name)

    def append_tab(self, tab_info):
        """Add a new tab with no parent."""
        return self.model.append(tab_info, False, -1)

    def insert_tab(self, iter_, tab_info):
        """Insert a new tab before iter_."""
        return self.model.insert_before(iter_, tab_info, False, -1)

    def append_child_tab(self, parent_iter, tab_info):
        """Add a new tab with a parent."""
        return self.model.append_child(parent_iter, tab_info, False, -1)

    # XXX: saving height_changed during update_value is an ugly hack for 17178

    def update_tab(self, iter_, tab_info):
        """A TabInfo has changed."""
        height_changed = self.height_changed #17178
        self.model.update_value(iter_, 0, tab_info)
        self.height_changed = height_changed

    def blink_tab(self, iter_):
        """Draw attention to a tab, specified by its Iter."""
        height_changed = self.height_changed #17178
        self.model.update_value(iter_, 1, True)
        self.height_changed = height_changed

    def unblink_tab(self, iter_):
        """Stop drawing attention to tab specified by Iter."""
        height_changed = self.height_changed #17178
        self.model.update_value(iter_, 1, False)
        self.height_changed = height_changed

    def pulse_updating_image(self, iter_):
        frame = self.model[iter_][2]
        height_changed = self.height_changed #17178
        self.model.update_value(iter_, 2, (frame + 1) % 12)
        self.height_changed = height_changed
        self.model_changed()

    def stop_updating_image(self, iter_):
        height_changed = self.height_changed #17178
        self.model.update_value(iter_, 2, -1)
        self.height_changed = height_changed
        self.model_changed()

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
            iter_ = self.iter_map[id_]
        except KeyError:
            # feed was removed
            del self.updating_animations[id_]
            return
        self.view.pulse_updating_image(iter_)
        timer_id = timer.add(0.5, self.pulse_updating_animation, id_)
        self.updating_animations[id_] = timer_id

class TabBlinkerMixin(object):
    def blink_tab(self, tab_id):
        self.show_auto_tab(tab_id)
        self.view.blink_tab(self.iter_map[tab_id])
        timer.add(1, self._unblink_tab, tab_id)

    def _unblink_tab(self, tab_id):
        # double check that the tab still exists
        if tab_id in self.iter_map:
            self.view.unblink_tab(self.iter_map[tab_id])

def _last_iter(view, model):
    """Get an iter for the row will be at the bottom of the table.  """
    last_iter = model.nth_iter(len(model) - 1)
    while view.is_row_expanded(last_iter) and model.has_child(last_iter):
        count = model.children_count(last_iter)
        last_iter = model.nth_child_iter(last_iter, count-1)
    return last_iter

class TabList(signals.SignalEmitter):
    """Handles a list of tabs on the left-side of Miro.
    
    Signals:
        tab-added: a tab has been added to this list; no parameters.
        moved-tabs-to-list(destination): tabs have been moved to destination

    iter_map note - GTK handles invalid iters very badly, so we must avoid them
    carefully (related: 17362). Iters can become invalid when you remove() them
    from the model, or when you remove() their parent from the model. The
    approach to avoiding bad iters is based on trusting the iter_map - if we
    keep only valid iters in iter_map, and only use iters from the map, we will
    only be using valid iters. Toward that end, some rules:

    0. never make an iter invalid without removing it from the iter_map
    1. never make the root invalid or remove it from the map
    2. never assume an ID is a key in iter_map, because of (0)
       - except the root is ok, because of (1)
    3. never assume an ID that isn't in the iter_map is permanently deleted
    4. never keep an iter: use it while you still know it's valid; keep IDs
    """
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.create_signal('tab-added')
        self.create_signal('moved-tabs-to-list')
        self.view = self._make_view()
        self.setup_view()
        self.iter_map = {}
        self._removing = 0
        self._adding = 0
        self.delayed_selection_change = False

    @property
    def changing(self):
        return self._removing or self._adding

    def __len__(self):
        return len(self.iter_map)

    def _make_view(self):
        """Implementations should return a TabListView."""
        raise NotImplementedError

    def _after_change(self, now, was_removing=False):
        """Do anything that needs to be done after a change completes; when all
        changes have completed, signal.
        """
        if now or not self.changing:
            self.view.model_changed()
        if not self.changing and self.delayed_selection_change:
            self.delayed_selection_change = False
            app.tabs.on_selection_changed(self.view, self)
        if not self.changing and not was_removing:
            self.emit('tab-added')

    @contextmanager
    def removing(self, now=False):
        """For removing one or more tabs - delays updates until all changes
        finish.
        """
        self._removing += 1
        try:
            yield
        finally:
            self._removing -= 1
        self._after_change(now, was_removing=True)

    @contextmanager
    def adding(self, now=False):
        """For adding one or more tabs; signals tab-added and updates the model
        when all (potentially nested) tab-add operations are finished. Set
        now=True to update the model immediately.
        """
        self._adding += 1
        try:
            yield
        finally:
            self._adding -= 1
        self._after_change(now)

    def build_tabs(self):
        """Build any standard tabs; for non-static tabs, this is a pass."""

    def add(self, tab):
        with self.adding():
            iter_ = self.view.append_tab(tab)
            self.iter_map[tab.id] = iter_

    def insert_before(self, current_tab, new_tab):
        """Insert current_tab before new_tab."""
        with self.adding():
            sibling_iter = self.iter_map[current_tab.id]
            iter_ = self.view.insert_tab(sibling_iter, new_tab)
            self.iter_map[new_tab.id] = iter_

    def extend(self, tabs):
        with self.adding():
            for tab in tabs:
                self.add(tab)

    def remove(self, name):
        with self.removing():
            iter_ = self.iter_map.pop(name)
            self.view.model.remove(iter_)
        if name in app.tabs.selected_ids:
            # hack for 17653: on OS X, deleting the selected tab doesn't
            # send selection-changed - so if the tab(s) we've 
            # deleted is selected, explicitly change the selection to
            # this list's root. This preempts GTK's handling of this 
            # case, which is behaviorally the same.
            app.tabs._handle_no_tabs_selected(self)

    def get_tab(self, name):
        return self.view.model[self.iter_map[name]][0]

    def setup_view(self):
        self.view.connect_weak('key-press', self.on_key_press)
        self.view.connect_weak('row-activated', self.on_row_activated)

    def on_key_press(self, view, key, mods):
        if key == keyboard.DOWN_ARROW and len(mods) == 0:
            # Test if the user is trying to move down past the last row in the
            # table, if so, select the next tablist.
            if view.is_selected(_last_iter(view, view.model)):
                if self._move_to_next_tablist():
                    return True
            return False
        elif key == keyboard.UP_ARROW and len(mods) == 0:
            # Test if the user is trying to move up past the first row in the
            # table, if so, select the next tablist.
            if view.is_selected(view.model.first_iter()):
                if self._move_to_prev_tablist():
                    return True
            return False

        if app.playback_manager.is_playing:
            return playback.handle_key_press(key, mods)


    def on_row_activated(self, view, iter_):
        if view.model.has_child(iter_):
            view.set_row_expanded(iter_, not view.is_row_expanded(iter_))

    def _move_to_next_tablist(self):
        """Move focus to the next tablist and select the first item

        :returns: True if the operation succeeded.
        """
        all_views = list(app.tabs.tab_list_widgets)
        my_index = all_views.index(self.view)
        try:
            next_view = all_views[my_index+1]
        except IndexError:
            # bail if we're the last tablist displayed
            return False
        self.view.unselect_all(signal=False)
        next_view.focus()
        next_view.select(next_view.model.first_iter(), signal=True)
        return True

    def _move_to_prev_tablist(self):
        """Move focus to the previous tablist and select the last item

        :returns: True if the operation succeeded.
        """
        all_views = list(app.tabs.tab_list_widgets)
        my_index = all_views.index(self.view)
        if my_index == 0:
            return False # bail if we're the first tablist displayed
        prev_view = all_views[my_index-1]
        self.view.unselect_all(signal=False)
        prev_view.unselect_all(signal=False)
        prev_view.select(_last_iter(prev_view, prev_view.model), signal=True)
        prev_view.focus()
        return True

class StaticTabList(TabUpdaterMixin, TabList):
    """Handles the static tabs (the tabs on top that are always the same)."""
    def __init__(self):
        TabUpdaterMixin.__init__(self)
        TabList.__init__(self)
        self.type = u'static'
        app.search_manager.connect('search-started', self._on_search_started)
        app.search_manager.connect('search-complete', self._on_search_complete)

    def _make_view(self):
        view = TabListView('static', style.StaticTabRenderer())
        view.allow_multiple_select = False
        return view

    def build_tabs(self):
        self.add(statictabs.SearchTab())

    def get_default(self):
        """Returns an iter pointing to Video Search."""
        return self.view.model.first_iter()

    def _on_search_started(self, manager):
        self.start_updating(self.iter_map.keys()[0])

    def _on_search_complete(self, manager, count):
        self.stop_updating(self.iter_map.keys()[0])

class LibraryTabList(TabBlinkerMixin, TabUpdaterMixin, TabList):
    """Handles all Library related tabs - Video, Audio, Downloading..."""
    def __init__(self):
        TabList.__init__(self)
        TabBlinkerMixin.__init__(self)
        TabUpdaterMixin.__init__(self)
        self.type = u'library'
        self.auto_tabs = {}
        self.auto_tabs_to_show = set()

    def _make_view(self):
        view = TabListView('library', style.StaticTabRenderer())
        view.allow_multiple_select = False
        view.set_drag_dest(MediaTypeDropHandler())
        view.connect('selection-changed', self.on_selection_changed)
        view.connect('deselected', self.on_deselected)
        return view

    def build_tabs(self):
        self.extend([
            statictabs.ChannelGuideTab(),
            statictabs.VideoLibraryTab(),
            statictabs.AudioLibraryTab(),
        ])
        self.auto_tabs.update({'downloading': statictabs.DownloadsTab(),
                               'converting': statictabs.ConvertingTab(),
                               'others': statictabs.OthersTab()})
        self.auto_tab_order = ['others', 'downloading', 'converting']

    def get_default(self):
        """Returns an iter pointing to the channel guide tab."""
        return self.view.model.first_iter()

    def update_auto_tab_count(self, name, count):
        if count > 0:
            self.auto_tabs_to_show.add(name)
            self.show_auto_tab(name)
        elif name in self.iter_map:
            self.auto_tabs_to_show.discard(name)
            self.remove_auto_tab_if_not_selected(name)

    def show_auto_tab(self, name):
        if name not in self.iter_map:
            new_tab = self.auto_tabs[name]
            # we need to keep the auto-tabs in the currect order.  First try
            # to insert the new tab below the one that's below it.
            for other in self._auto_tabs_after(name):
                if other in self.iter_map:
                    self.insert_before(self.auto_tabs[other], new_tab)
                    break
            else:
                # if we didn't break, append the new tab to the bottom
                self.add(new_tab)

    def _auto_tabs_after(self, name):
        """Get the auto-tabs that should be below name."""
        pos = self.auto_tab_order.index(name)
        return self.auto_tab_order[pos+1:]

    def remove_auto_tab_if_not_selected(self, name):
        # can't query app.tabs.selection here without changing it (#16914#c4)
        if name not in (self.view.model[iter_][0].id
                for iter_ in self.view.get_selection()):
            self.remove(name)

    def on_deselected(self, view):
        """deselected is a more specific signal that selection-changed, to
        simplify sending selection signals while handling selection-changed."""
        for name in (set(self.auto_tabs).intersection(self.iter_map) -
                     self.auto_tabs_to_show):
            self.remove_auto_tab_if_not_selected(name)

    def on_selection_changed(self, view):
        self.on_deselected(view)
        if not app.config.get(prefs.MUSIC_TAB_CLICKED):
            try:
                iters = view.get_selection()
            except errors.ActionUnavailableError, error:
                logging.debug("not checking first music tab click: %s",
                        error.reason)
            else:
                for iter_ in iters:
                    if view.model[iter_][0].id == 'music':
                        app.widgetapp.music_tab_clicked()

    def update_download_count(self, count, non_downloading_count):
        self.update_count('downloading', 'downloading', count,
                          non_downloading_count)

    def update_converting_count(self, running_count, other_count):
        self.update_count('converting', 'converting', running_count,
                          other_count)

    def update_others_count(self, count):
        self.update_count('others', 'others', count) # second param no special
                                                     # meaning for this
                                                     # case... ?

    def update_new_video_count(self, count):
        self.update_count('videos', 'unwatched', count)

    def update_new_audio_count(self, count):
        self.update_count('music', 'unwatched', count)

    def update_count(self, key, attr, count, other_count=0):
        if key in self.auto_tabs:
            self.update_auto_tab_count(key, count+other_count)
        if key in self.iter_map:
            iter_ = self.iter_map[key]
            tab = self.view.model[iter_][0]
            setattr(tab, attr, count)
            self.view.update_tab(iter_, tab)
        self.view.model_changed()

class HideableTabList(TabList):
    """A type of tablist which nests under a base tab.  Connect,
    Sources/Sites/Guides, Stores, Feeds, and Playlists are all of this type.
    """

    ALLOW_MULTIPLE = True

    render_class = style.TabRenderer
    type = NotImplemented
    name = NotImplemented
    icon_name = NotImplemented

    def __init__(self):
        TabList.__init__(self)
        self._set_up = False
        self.create_signal('tab-name-changed')
        # the type here is the "tab_class" in TabInfo because "type"
        # is overused.  "type" here is u'connect', u'feed', ...
        self.info = TabInfo(self.type, self.name, self.icon_name)
        TabList.add(self, self.info)
        self.view.model_changed()
        self.expand_after_add_child = set()

    @contextmanager
    def preserving_expanded_rows(self):
        """Prevent expanded rows from being collapsed by
        changes. Implementation does not currently handle nesting.
        """
        expanded_rows = (id_ for id_, iter_ in self.iter_map.iteritems() if
            id_ == self.info.id or self.view.is_row_expanded(iter_))
        try:
            yield
        finally:
            for id_ in expanded_rows:
                self.expand(id_)

    @property
    def changing(self):
        return super(HideableTabList, self).changing or not self._set_up

    def _make_view(self):
        view = TabListView(self.name, self.render_class())
        view.allow_multiple_select = self.ALLOW_MULTIPLE
        view.connect('row-clicked', self.on_row_clicked)
        view.connect('row-expanded', self.on_row_expanded_change, True)
        view.connect('row-collapsed', self.on_row_expanded_change, False)
        view.set_context_menu_callback(self.on_context_menu)
        return view

    def on_context_menu(self, table_view):
        raise NotImplementedError

    def init_info(self, info):
        raise NotImplementedError

    def setup_list(self, message):
        """Called during startup to set up a newly-created list."""
        if message.root_expanded:
            self.expand(self.info.id)
        if not hasattr(message, 'toplevels'):
            # setting up a non-nestable list
            self._set_up = True
            return
        model = self.view.model
        iter_ = model.first_iter()
        for c, info in zip(itertools.count(), message.toplevels):
            try:
                # HACK: bz:16780.  There is currently no way to reload
                # a list that has been reordered somehow by the backend,
                # e.g. due to addition of a folder with existing playlists
                # put into it.  So, add some crappy code so that things don't
                # get duplicated.
                old_iter = model.nth_child_iter(iter_, c)
                old_info = model[old_iter][0]
                if old_info.id == info.id:
                    continue
            except (IndexError, LookupError, TypeError):
                # Catch IndexError, LookupError.  TypeError for Linux on
                # startup when this stuff's not been populated yet, see #16934.
                pass
            with self.adding():
                self.add(info)
            if info.is_folder:
                with self.adding():
                    for child_info in message.folder_children[info.id]:
                        self.add(child_info, info.id)
                if info.id in message.expanded_folders:
                    self.expand(info.id)
        self._set_up = True
        self._after_change(True)

    def on_key_press(self, view, key, mods):
        if key == keyboard.DELETE or key == keyboard.BKSPACE:
            self.on_delete_key_pressed()
            return True
        elif key == keyboard.F5:
            app.widgetapp.update_selected_feeds()
            return True
        return TabList.on_key_press(self, view, key, mods)

    def on_delete_key_pressed(self):
        app.widgetapp.remove_something()

    def on_row_clicked(self, view, iter_):
        if view.model[iter_][0] is self.info:
            if not view.is_row_expanded(iter_):
                self.expand(self.info.id)
                self.view.model_changed()

    def on_row_expanded_change(self, view, iter_, expanded):
        info = self.view.model[iter_][0]
        if info == self.info:
            message = messages.TabExpandedChange(self.type, expanded)
            message.send_to_backend()
        else:
            # non-nestable tabs don't have tablist states, so we put their root
            # nodes all in one table
            message = messages.FolderExpandedChange(self.type, info.id,
                                                    expanded)
            message.send_to_backend()

    def add(self, info, parent_id=None):
        """Add a TabInfo to the list, with an optional parent (by id)."""
        with self.adding(now=True):
            if parent_id is None:
                parent_id = self.info.id
            self.init_info(info)
            if parent_id:
                parent_iter = self.iter_map[parent_id]
                iter_ = self.view.append_child_tab(parent_iter, info)
            else:
                iter_ = self.view.append_tab(info)
            self.iter_map[info.id] = iter_
        if parent_id in self.expand_after_add_child:
            self.expand(parent_id)
            self.expand_after_add_child.remove(parent_id)

    def expand(self, id_):
        if self.get_child_count(id_):
            iter_ = self.iter_map[id_]
            try:
                self.view.set_row_expanded(iter_, True)
            except errors.WidgetActionError:
                # root is not expanded
                pass
        else:
            self.expand_after_add_child.add(id_)

    def update(self, info):
        self.init_info(info)
        old_name = self.view.model[self.iter_map[info.id]][0].name
        self.view.update_tab(self.iter_map[info.id], info)
        if old_name != info.name:
            self.emit('tab-name-changed', old_name, info.name)

    def remove(self, id_list):
        deleted_ids = set(id_list)
        with self.removing():
            for id_ in id_list:
                try:
                    iter_ = self.iter_map.pop(id_)
                except KeyError:
                    # child of a tab we already deleted
                    continue
                # override default of nil
                deleted_ids.update(self.forget_child_iters(iter_))
                self.view.model.remove(iter_)
        if deleted_ids.intersection(set(app.tabs.selected_ids)):
            # hack for 17653: on OS X, deleting the selected tab doesn't
            # send selection-changed - so if the tab(s) we've 
            # deleted is selected, explicitly change the selection to
            # this list's root. This preempts GTK's handling of this 
            # case, which is behaviorally the same.
            app.tabs._handle_no_tabs_selected(self)

    def forget_child_iters(self, parent_iter):
        model = self.view.model
        iter_ = model.child_iter(parent_iter)
        deleted_ids = set()
        while iter_ is not None:
            # No need to wrap these around a try...except.  If we can get
            # the child iter (from above) then this must exist.  If it doesn't
            # then there is some sort of internal inconsistency.
            id_ = model[iter_][0].id
            del self.iter_map[id_]
            deleted_ids.update(self.forget_child_iters(iter_))
            iter_ = self.view.model.remove(iter_)
            deleted_ids.add(id_)
        return deleted_ids

    def model_changed(self):
        self.view.model_changed()

    def get_info(self, id_):
        return self.view.model[self.iter_map[id_]][0]

    def has_info(self, id_):
        return id_ in self.iter_map

    def get_child_count(self, id_):
        count = 0
        iter_ = self.iter_map[id_]
        child_iter = self.view.model.child_iter(iter_)
        while child_iter is not None:
            count += 1
            child_iter = self.view.model.next_iter(child_iter)
        return count

class DeviceTabListHandler(object):
    def __init__(self, tablist):
        self.tablist = tablist
        # map device ids to the fake tabs that we created for them.
        self.fake_tabs_created = {}

    def _fake_info(self, info, typ, name):
        new_data = {
            'fake': True,
            'tab_type': typ,
            'id': u'%s-%s' % (info.id, typ),
            'name': name,
            'device_name': info.name,
            'icon': imagepool.get_surface(
                resources.path('images/icon-device-%s.png' % typ)),
            'active_icon': imagepool.get_surface(
                resources.path('images/icon-device-%s_active.png' % typ))
            }

        # hack to create a DeviceInfo without dealing with __init__
        di = messages.DeviceInfo.__new__(messages.DeviceInfo)
        di.__dict__ = info.__dict__.copy()
        di.__dict__.update(new_data)
        return di

    def _get_fake_infos(self, info):
        return [self._fake_info(info, 'video', _('Video')),
                self._fake_info(info, 'audio', _('Music'))]

    def _add_fake_tabs(self, info):
        if info.id in self.fake_tabs_created:
            # fake tabs already added
            return

        fake_tabs = self._get_fake_infos(info)
        self.fake_tabs_created[info.id] = fake_tabs
        with self.tablist.adding():
            for fake in fake_tabs:
                HideableTabList.add(self.tablist, fake, info.id)
            try:
                self.tablist.expand(info.id)
            except errors.WidgetActionError:
                pass # if the Connect Tab isn't open, we can't expand the tab

    def _remove_fake_tabs(self, info):
        if info.id not in self.fake_tabs_created:
            # fake tabs already removed
            return
        fake_tabs = self.fake_tabs_created[info.id]
        self.tablist.remove([fake_tab.id for fake_tab in fake_tabs])
        del self.fake_tabs_created[info.id]

    def add(self, info, parent_id):
        HideableTabList.add(self.tablist, info)
        if info.mount and not info.info.has_multiple_devices:
            self._add_fake_tabs(info)

    def extend(self, tabs):
        self.tablist.extend(tabs)

    def update(self, info):
        tablist = self.tablist
        model = tablist.view.model
        if not tablist.has_info(info.id):
            # this gets called if a sync is in progress when the device
            # disappears
            return
        if (info.mount and not info.info.has_multiple_devices and
                not tablist.get_child_count(info.id)):
            self._add_fake_tabs(info)
        elif tablist.get_child_count(info.id):
            if not info.mount:
                parent_iter = tablist.iter_map[info.id]
                next_iter = model.child_iter(parent_iter)
                while next_iter is not None:
                    iter_ = next_iter
                    next_iter = model.next_iter(next_iter)
                    model.remove(iter_)
            else: # also update the subtabs
                for fake in self._get_fake_infos(info):
                    HideableTabList.update(tablist, fake)
                    messages.DeviceChanged(fake).send_to_frontend()
        HideableTabList.update(self.tablist, info)

    def init_info(self, info):
        info.type = u'device'
        info.unwatched = info.available = 0
        if not getattr(info, 'fake', False):
            if getattr(info.info, 'generic', False):
                info.icon = imagepool.get_surface(resources.path(
                    'images/icon-device-hd.png'))
                info.active_icon = imagepool.get_surface(
                    resources.path('images/icon-device-hd_active.png'))
            else:
                info.icon = imagepool.get_surface(
                    resources.path('images/icon-device.png'))
                info.active_icon = imagepool.get_surface(
                    resources.path('images/icon-device_active.png'))
            if getattr(info, 'is_updating', False):
                self.tablist.start_updating(info.id)
            else:
                self.tablist.stop_updating(info.id)

    def on_hotspot_clicked(self, view, hotspot, iter_):
        if hotspot == 'eject-device':
            self.eject_device(view.model[iter_][0])

    def eject_device(self, device_info):
        # stop playback from the device
        currently_playing = app.playback_manager.get_playing_item()
        if currently_playing and currently_playing.device == device_info:
            app.playback_manager.stop()
        # navigate away from the audio/video tabs and remove them
        self._remove_fake_tabs(device_info)
        messages.DeviceEject(device_info).send_to_backend()

class FakeSharingInfo(object):
    """TabInfo that we use for the "fake" tabs under a share

    This includes the audio, video, podcast, and playlist tabs.
    """
    def __init__(self, share_id, tab_name, label):
        self.id = u"sharing-%s-%s" % (share_id, tab_name)
        self.share_id = share_id
        self.name = label
        self.type = u'sharing-fake-playlist'
        self.icon = widgetutil.make_surface("icon-%s" % tab_name)
        self.active_icon = widgetutil.make_surface("icon-%s_active" % tab_name)

class SharingTabListHandler(object):
    """Handles all of the sharing tabs """
    def __init__(self, tablist):
        self.tablist = tablist
        # map share ids to the fake tabs for them
        self.fake_tabs_created = {}
        # before the fake tabs are created, we can't add any playlist tabs.
        # pending_playlist_tabs maps share ids to those playlist tabs.
        self.pending_playlist_tabs = collections.defaultdict(list)

    def _make_fake_tabs(self, info):
        return [
            FakeSharingInfo(info.share_id, u'video', _('Video')),
            FakeSharingInfo(info.share_id, u'audio', _('Audio')),
            FakeSharingInfo(info.share_id, u'playlist', _('Playlists')),
            FakeSharingInfo(info.share_id, u'podcast', _('Podcasts')),
        ]

    def _add_fake_tabs(self, info):
        """Add the psuedo-tabs below the share tabs.

        This includes the audio, video, playlists, and podcasts tabs.
        """
        if info.share_id in self.fake_tabs_created:
            # fake tabs already added
            return
        self.fake_tabs_created[info.share_id] = []
        with self.tablist.adding():
            for tab in self._make_fake_tabs(info):
                self.tablist.add(tab, info.id)
                self.fake_tabs_created[info.share_id].append(tab)
        self._add_pending_playlist_tabs(info.share_id)
        try:
            self.tablist.expand(info.id)
        except errors.WidgetActionError:
            pass # if the Connect Tab isn't open, we can't expand the tab

    def _remove_fake_tabs(self, info):
        if info.share_id not in self.fake_tabs_created:
            # fake tabs already removed
            return
        fake_tabs = self.fake_tabs_created[info.share_id]
        self.tablist.remove([fake_tab.id for fake_tab in fake_tabs])
        del self.fake_tabs_created[info.share_id]

    def _add_pending_playlist_tabs(self, share_id):
        if share_id not in self.pending_playlist_tabs:
            return

        pending_tabs = self.pending_playlist_tabs.pop(share_id)
        with self.tablist.adding():
            for tab in pending_tabs:
                self.add_playlist_tab(tab)

    def add(self, info, parent_id):
        # Need to avoid calling ConnectList.add since that will result in an
        # infinite loop.
        if isinstance(info, messages.SharingInfo):
            self.add_sharing_tab(info)
        else:
            self.add_playlist_tab(info)

    def add_sharing_tab(self, info):
        HideableTabList.add(self.tablist, info)
        self._handle_sharing_info_change(info)

    def add_playlist_tab(self, info):
        if info.share_id in self.fake_tabs_created:
            # fake tabs are created, we can add this info now
            parent_id = info.share_id
            if info.podcast:
                parent_id = "sharing-%s-podcast" % (info.share_id,)
            else:
                parent_id = "sharing-%s-playlist" % (info.share_id,)
            HideableTabList.add(self.tablist, info, parent_id)
        else:
            # fake tabs not created yet, wait to add the info
            self.pending_playlist_tabs[info.share_id].append(info)

    def update(self, info):
        # Need to avoid calling ConnectList.update since that will result in an
        # infinite loop.
        HideableTabList.update(self.tablist, info)
        if isinstance(info, messages.SharingInfo):
            self._handle_sharing_info_change(info)

    def _handle_sharing_info_change(self, info):
        if info.is_updating:
            self.tablist.start_updating(info.id)
        else:
            self.tablist.stop_updating(info.id)
        if info.mount:
            self._add_fake_tabs(info)
        else:
            self._remove_fake_tabs(info)

    def on_hotspot_clicked(self, view, hotspot, iter_):
        if hotspot == 'eject-device':
            # Don't track this tab anymore for music.
            info = view.model[iter_][0]
            # We must stop the playback if we are playing from the same
            # share that we are ejecting from.
            host = info.host
            port = info.port
            item = app.playback_manager.get_playing_item()
            remote_item = False
            if item and item.remote:
                remote_item = True
            if remote_item and item.host == host and item.port == port:
                app.playback_manager.stop()
            # Default to select the guide.  There's nothing more to see here.
            typ, selected_tabs = app.tabs.selection
            if typ == u'connect' and (info == selected_tabs[0] or
              getattr(selected_tabs[0], 'parent_id', None) == info.id):
                app.tabs.select_guide()
            messages.StopTrackingShare(info.share_id).send_to_backend()

    def init_info(self, info):
        info.unwatched = info.available = 0
        if isinstance(info, messages.SharingInfo):
            self.init_share_info(info)
        else:
            self.init_playlist_info(info)

    def init_share_info(self, info):
        info.type = u'sharing'
        info.icon = imagepool.get_surface(
            resources.path('images/sharing.png'))

    def init_playlist_info(self, info):
        info.type = u'sharing-playlist'
        if info.podcast:
            thumb_path = resources.path('images/icon-podcast-small.png')
            active = resources.path('images/icon-podcast-small_active.png')
        else:
            thumb_path = resources.path('images/icon-playlist-small.png')
            active = resources.path('images/icon-playlist-small_active.png')
        info.icon = imagepool.get_surface(thumb_path)
        info.active_icon = imagepool.get_surface(active)

class SharingPlaylistTabListHandler(object):
    def __init__(self, tablist):
        self.tablist = tablist

    def add(self, info, parent_id):
        parent_id = info.share_id
        if info.podcast:
            parent_id = "sharing-%s-podcast" % (info.share_id,)
        else:
            parent_id = "sharing-%s-playlist" % (info.share_id,)
        HideableTabList.add(self.tablist, info, parent_id)

class ConnectList(TabUpdaterMixin, HideableTabList):
    name = _('Connect')
    icon_name = 'icon-connect'
    type = u'connect'

    ALLOW_MULTIPLE = False

    render_class = style.ConnectTabRenderer

    def __init__(self):
        HideableTabList.__init__(self)
        TabUpdaterMixin.__init__(self)
        self._set_up = True # setup_list is never called?

        sharing_tab_list_handler = SharingTabListHandler(self)
        self.info_class_map = {
            messages.DeviceInfo: DeviceTabListHandler(self),
            messages.SharingInfo: sharing_tab_list_handler,
            messages.SharingPlaylistInfo: sharing_tab_list_handler,
            TabInfo: None,
            }
        self.view.connect_weak('hotspot-clicked', self.on_hotspot_clicked)
        self.view.set_drag_dest(DeviceDropHandler(self))

    def on_row_expanded_change(self, view, iter_, path, expanded):
        info = self.view.model[iter_][0]
        if info is self.info:
            HideableTabList.on_row_expanded_change(self, view, iter_, path,
                                                   expanded)

    def on_delete_key_pressed(self):
        # neither handler deals with this
        return

    def on_context_menu(self, view):
        # neither handle deals with this
        return []

    def on_hotspot_clicked(self, view, hotspot, iter_):
        info = self.view.model[iter_][0]
        handler = self.info_class_map.get(type(info))
        if hasattr(handler, 'on_hotspot_clicked'):
            return handler.on_hotspot_clicked(view, hotspot, iter_)

    def init_info(self, info):
        if info is self.info:
            return
        handler = self.info_class_map.get(type(info))
        if hasattr(handler, 'init_info'):
            handler.init_info(info)

    def add(self, info, parent_id=None):
        handler = self.info_class_map.get(type(info))
        if hasattr(handler, 'add'):
            handler.add(info, parent_id) # device doesn't use the parent_id
        else:
            HideableTabList.add(self, info, parent_id)

    def update(self, info):
        handler = self.info_class_map.get(type(info))
        if hasattr(handler, 'update'):
            handler.update(info)
        else:
            HideableTabList.update(self, info)

class SiteList(HideableTabList):
    type = u'site'
    name = _('Sources')
    icon_name = 'icon-source'

    ALLOW_MULTIPLE = True

    def __init__(self):
        # FIXME - we redo the translation here so we're doing it at
        # instantiation time and NOT at import time which is stupid.
        SiteList.name = _("Sources")
        HideableTabList.__init__(self)
        self.default_info = None

    def default_icon_path(self):
        icon = resources.path('images/icon-source-small.png')
        icon_active = resources.path('images/icon-source-small_active.png')
        return (icon, icon_active)

    def init_info(self, info):
        if info is self.info:
            return
        fallback, fallback_active = self.default_icon_path()
        if info.favicon:
            thumb_path = info.favicon
        else:
            thumb_path = fallback
        # we don't use the ImagePool because 'favicon.ico' is a name with too
        # many hits (#16573).
        try:
            image = widgetset.Image(thumb_path)
            if image.width > 16 or image.height > 16:
                image = imagepool.resize_image(image, 16, 16)
            info.icon = widgetset.ImageSurface(image)
            if not info.favicon:
                info.active_icon = imagepool.get_surface(fallback_active,
                                                         size=(16, 16))
        except ValueError:
            # 16842 - if we ever get sent an invalid icon - don't crash with
            # ValueError.
            info.icon = imagepool.get_surface(fallback, size=(16, 16))
            info.active_icon = imagepool.get_surface(fallback_active,
                                                     size=(16, 16))
        info.unwatched = info.available = 0
        info.type = self.type

    def on_context_menu(self, table_view):
        tablist_type, selected_rows = app.tabs.selection
        if len(selected_rows) == 1:
            if selected_rows[0].type == u'tab':
                return []
            return [(_('Copy URL to clipboard'), app.widgetapp.copy_site_url),
                    (_('Rename Source'), app.widgetapp.rename_something),
                    (_('Remove Source'), app.widgetapp.remove_something)]
        else:
            return [
                (_('Remove Sources'), app.widgetapp.remove_something),
                ]

    def get_default(self):
        """Return the iter pointing to this list's default tab."""
        return self.iter_map[self.default_info.id]

class StoreList(SiteList):
    type = u'store'
    name = _('Stores')
    icon_name = 'icon-store'

    ALLOW_MULTIPLE = False

    def __init__(self):
        # FIXME - we redo the translation here so we're doing it at
        # instantiation time and NOT at import time which is stupid.
        StoreList.name = _("Stores")
        SiteList.__init__(self)

    def on_delete_key_pressed(self):
        pass # XXX: can't delete stores(?)

    def default_icon_path(self):
        icon = resources.path('images/icon-store-small.png')
        icon_active = resources.path('images/icon-store-small_active.png')
        return (icon, icon_active)

    def on_context_menu(self, table_view):
        tablist_type, selected_rows = app.tabs.selection
        if len(selected_rows) == 1 and selected_rows[0].type != u'tab':
            return [
                (_('Copy URL to clipboard'), app.widgetapp.copy_site_url),
            ]
        else:
            return []

class NestedTabListMixin(object):
    """Tablist for tabs that can be put into folders (playlists and feeds)."""
    def on_context_menu(self, table_view):
        tablist_type, selected_rows = app.tabs.selection
        if len(selected_rows) == 1:
            if selected_rows[0].type == u'tab':
                return []
            if selected_rows[0].is_folder:
                return self.make_folder_context_menu(selected_rows[0])
            else:
                return self.make_single_context_menu(selected_rows[0])
        else:
            return self.make_multiple_context_menu()

class FeedList(TabUpdaterMixin, NestedTabListMixin, HideableTabList):
    type = u'feed'
    name = _('Podcasts')
    icon_name = 'icon-podcast'

    def __init__(self):
        # FIXME - we redo the translation here so we're doing it at
        # instantiation time and NOT at import time which is stupid.
        FeedList.name = _('Podcasts')
        HideableTabList.__init__(self)
        TabUpdaterMixin.__init__(self)
        self.setup_dnd()

    def setup_dnd(self):
        self.view.set_drag_source(FeedListDragHandler())
        self.view.set_drag_dest(FeedListDropHandler(self))

    def init_info(self, info):
        if info is self.info:
            return
        info.type = self.type
        info.icon = imagepool.get_surface(info.tab_icon, size=(16, 16))
        active_path = info.tab_icon.replace('.png', '_active.png')
        if os.path.exists(active_path):
            info.active_icon = imagepool.get_surface(active_path,
                                                     size=(16, 16))
        if info.is_updating:
            self.start_updating(info.id)
        else:
            self.stop_updating(info.id)

    def get_feeds(self):
        return (self.view.model[i][0] for k, i in self.iter_map.iteritems()
                if k != self.info.id)

    def find_feed_with_url(self, url):
        for iter_ in self.iter_map.itervalues():
            info = self.view.model[iter_][0]
            if info is self.info:
                continue
            if info.url == url:
                return info
        return None

    def make_folder_context_menu(self, obj):
        return [
            (_('Update Podcasts In Folder'),
             app.widgetapp.update_selected_feeds),
            (_('Rename Podcast Folder'), app.widgetapp.rename_something),
            (_('Remove'), app.widgetapp.remove_something)
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
        menu.append((_('Remove'), app.widgetapp.remove_something))
        return menu

    def make_multiple_context_menu(self):
        return [
            (_('Update Podcasts Now'), app.widgetapp.update_selected_feeds),
            (_('Remove'), app.widgetapp.remove_something)
        ]

class PlaylistList(NestedTabListMixin, HideableTabList):
    type = u'playlist'
    name = _('Playlists')
    icon_name = 'icon-playlist'

    def __init__(self):
        # FIXME - we redo the translation here so we're doing it at
        # instantiation time and NOT at import time which is stupid.
        PlaylistList.name = _("Playlists")
        HideableTabList.__init__(self)
        self.view.set_drag_source(PlaylistListDragHandler())
        self.view.set_drag_dest(PlaylistListDropHandler(self))

    def init_info(self, info):
        if info is self.info:
            return
        if info.is_folder:
            info.icon = imagepool.get_surface(
                resources.path('images/icon-folder.png'))
        else:
            info.icon = imagepool.get_surface(
                resources.path('images/icon-playlist-small.png'))
            info.active_icon = imagepool.get_surface(
                resources.path('images/icon-playlist-small_active.png'))
        info.type = self.type
        info.unwatched = info.available = 0

    def get_playlists(self):
        return (self.view.model[i][0] for k, i in self.iter_map.iteritems()
                if k != self.info.id)

    def find_playlist_with_name(self, name):
        for iter_ in self.iter_map.itervalues():
            info = self.view.model[iter_][0]
            if info is self:
                continue
            if info.name == name:
                return info
        return None

    def make_folder_context_menu(self, obj):
        return [
            (_('Rename Playlist Folder'), app.widgetapp.rename_something),
            (_('Remove'), app.widgetapp.remove_something)
        ]

    def make_single_context_menu(self, obj):
        return [
            (_('Rename Playlist'), app.widgetapp.rename_something),
            (_('Remove'), app.widgetapp.remove_something)
        ]

    def make_multiple_context_menu(self):
        return [
            (_('Remove'), app.widgetapp.remove_something)
        ]

class TabListBox(widgetset.Scroller):
    """The widget displaying the full tab list."""
    def __init__(self):
        widgetset.Scroller.__init__(self, False, True)
        background = widgetset.SolidBackground()
        background.set_background_color((style.TAB_LIST_BACKGROUND_COLOR))
        background.add(self.build_vbox())
        self.add(background)
        self.set_background_color((style.TAB_LIST_BACKGROUND_COLOR))

    def build_vbox(self):
        vbox = widgetset.VBox()
        for widget in app.tabs.tab_list_widgets:
            vbox.pack_start(widget)
        return vbox

def all_tab_lists():
    """Return an iterable of all the tablist instances TabListManager should
    own, in no particular order.
    """
    return (StaticTabList(), LibraryTabList(), ConnectList(), SiteList(),
            StoreList(), FeedList(), PlaylistList())
