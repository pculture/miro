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

"""displays.py -- Handle switching the content on the right hand side of the
app.
"""
import functools
import logging

import os

from miro import app
from miro import messages
from miro import signals
from miro import prefs
from miro import filetypes
from miro.data import item
from miro.data import itemtrack
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro.frontends.widgets import browser
from miro.frontends.widgets import downloadscontroller
from miro.frontends.widgets import convertingcontroller
from miro.frontends.widgets import feedcontroller
from miro.frontends.widgets import guidecontroller
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import devicecontroller
from miro.frontends.widgets import sharingcontroller
from miro.frontends.widgets import searchcontroller
from miro.frontends.widgets import tabcontroller
from miro.frontends.widgets import playlist
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets.widgetstatestore import WidgetStateStore

from miro.plat.frontends.widgets.threads import call_on_ui_thread
from miro.plat.frontends.widgets import timer
from miro.plat.frontends.widgets import widgetset

class Display(signals.SignalEmitter):
    """A display is a view that can be shown in the right hand side of the
    app.

    Attributes:

    widget -- Widget to show to the user.
    """

    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.create_signal('removed')

    def on_selected(self):
        """Perform any code that needs to be run every time the display is
        selected.
        """
        pass

    def on_activate(self, is_push):
        """Perform code that needs to be run when the display becomes the
        active display (the one on the top of the display stack).

        :param is_push: are we pushing the display on top (as opposed to
            having a display that was on top of us get popped off)
        """
        pass

    def on_deactivate(self):
        """Perform code that needs to be run when another display gets pushed
        on top of this display.
        """
        pass

    def cleanup(self):
        """Cleanup any resources allocated in create.  This will be called
        after the widget for this display is removed.
        """
        pass

    def get_column_info(self):
        """Get info about the togglable columns for this display.

        By default this returns None, which indicates that the display doesn't
        support togglable columns.

        Subclasses can override this and return the tuple (columns_enabled,
        columns_available) which describes the togglable columns.
        Both should be a list of column names.
        """
        return None

    def toggle_column_enabled(self, name):
        """Change if a column is enabled.

        This method is called after the sorts menu changes.  By default we do
        nothing.  If a display has togglable columns, it should override this
        and update the enabled columns.

        :param name: unicode identifier for the column
        """
        pass

class TabDisplay(Display):
    """Display that displays the selection in the tab list."""

    def __init__(self, tab_type, selected_tabs):
        raise NotImplementedError()

    def on_activate(self, is_push):
        app.menu_manager.update_menus('tab-selection-changed')

    @staticmethod
    def should_display(tab_type, selected_tabs):
        """Test if this display should be shown.  """
        raise NotImplementedError()

class DisplayManager(object):
    """Handles managing the display in the right-side of miro.

    DisplayManagers keep a stack of Displays that are currently is use.  This
    is used to allow us to switch to a new display, but still keep the old
    display's state.  For example, when we switch to a video display, we want
    to keep around the channel display that we switched from and go back to it
    when the playback is finished.
    """
    def __init__(self):
        # displays that we construct when the user clicks on them
        self.on_demand_display_classes = [
                VideoItemsDisplay,
                AudioItemsDisplay,
                FeedDisplay,
                AllFeedsDisplay,
                PlaylistDisplay,
                SiteDisplay,
                SearchDisplay,
                OtherItemsDisplay,
                DownloadingDisplay,
                ConvertingDisplay,
                GuideDisplay,
                MultipleSelectionDisplay,
                DeviceDisplay,
                DeviceItemDisplay,
                SharingDisplay,
                ConnectDisplay,
                SourcesDisplay,
                PlaylistsDisplay,
                StoresDisplay,

                # DummyDisplay should be last because it's a
                # catch-all.
                DummyDisplay,
        ]
        # _select_display_for_tabs_args holds the arguments passed to
        # select_display_for_tabs()
        self._select_display_for_tabs_args = None
        # displays that we keep alive all the time
        self.permanent_displays = set()
        self.display_stack = []
        self.selected_tab_list = self.selected_tabs = None
        app.info_updater.connect('sites-removed', SiteDisplay.on_sites_removed)

    def add_permanent_display(self, display):
        self.permanent_displays.add(display)

    def get_current_display(self):
        try:
            return self.display_stack[-1]
        except IndexError:
            return None
    current_display = property(get_current_display)

    def select_display_for_tabs(self, selected_tab_list, selected_tabs):
        """Select a display to show in the right-hand side.  """
        if self._select_display_for_tabs_args is None:
            # First call to select_display_for_tabs(), we need to schedule
            # _select_display_for_tabs() to be called.
            timer.add(0.01, self._select_display_for_tabs)
        # For all cases, we want to store these arguments in
        # _select_display_for_tabs_args so that when
        # _select_display_for_tabs() is called it uses them.
        self._select_display_for_tabs_args = (selected_tab_list,
                                              selected_tabs)

    def _select_display_for_tabs(self):
        """Call that does the work for select_display_for_tabs()

        select_display_for_tabs() defers action in case the user is quickly
        switching between tabs.  In that case, we only need to select the last
        tab that was switched to.  This method does the actual work.
        """
        if self._select_display_for_tabs_args is None:
            app.widgetapp.handle_soft_failure(
                "_select_display_for_tabs():",
                "_select_display_for_tabs_args is None")
            return
        selected_tab_list, selected_tabs = self._select_display_for_tabs_args
        self._select_display_for_tabs_args = None

        if (selected_tab_list is self.selected_tab_list and
                selected_tabs == self.selected_tabs and
                len(self.display_stack) > 0 and
                isinstance(self.display_stack[-1], TabDisplay)):
            logging.warn('not reselecting')
            return

        self.selected_tab_list = selected_tab_list
        self.selected_tabs = selected_tabs
        # parents always come first, so using the type of the last item handles
        # the case where a root item and its child(ren) are selected
        if hasattr(selected_tabs[-1], 'type'):
            tab_type = selected_tabs[-1].type
        else:
            tab_type = selected_tab_list.type

        for display in self.permanent_displays:
            if display.should_display(tab_type, selected_tabs):
                self.change_non_video_displays(display)
                return
        for klass in self.on_demand_display_classes:
            if klass.should_display(tab_type, selected_tabs):
                self.change_non_video_displays(klass(tab_type, selected_tabs))
                return
        raise AssertionError(
            "Can't find display for %s %s" % (tab_type, selected_tabs))

    def select_display(self, display):
        """Select a display and clear out the current display stack."""
        self.deselect_all_displays()
        self.push_display(display)

    def change_non_video_displays(self, display):
        """Like select_display(), but don't replace the VideoDisplay

        Mostly this will work like select_display().  However, if there is a
        VideoDisplay on top of the display, it will stay on top.

        The main reason for this method is when we are playing video and the
        current tab gets removed (#16225).  In this case, we want to select a
        new tab and make a display for that tab, but not show that display
        until video stops.

        Normally this is called as part of a deferred call by
        change_non_video_displays().  We do this because loading a display
        is a relatively expensive process and we want to be able to cancel
        the operation if the display is going to be extremely transient,
        e.g. during a continued keypress event as part of navigation.
        """

        if (len(self.display_stack) == 0 or
                not isinstance(self.display_stack[-1], VideoDisplay)):
            # no video displays are on the stack, just call select_display
            self.select_display(display)
            return
        # save the video display object
        video_display = self.display_stack.pop()
        # unselect displays below it
        for old_display in self.display_stack:
            self._unselect_display(old_display, on_top=False)
        # re-create the display stack with the new display and the video
        # display on top of it
        self.display_stack = [display, video_display]
        # call on_selected() if we are creating the display.  Don't call
        # on_activate() or show the display because it's still below other
        # displays
        if display not in self.permanent_displays:
            display.on_selected()

    def deselect_all_displays(self):
        """Deselect all displays."""
        top_display = True
        while self.display_stack:
            old_display = self.display_stack.pop()
            self._unselect_display(old_display, on_top=top_display)
            top_display = False

    def push_display(self, display):
        """Select a display and push it on top of the display stack"""
        if len(self.display_stack) > 0:
            self.current_display.on_deactivate()
        self.display_stack.append(display)
        if display not in self.permanent_displays:
            display.on_selected()
        display.on_activate(is_push=True)
        app.widgetapp.window.set_main_area(display.widget)

    def pop_display(self, unselect=True):
        """Remove the current display, then select the next one in the display
        stack.
        """
        display = self.display_stack.pop()
        if unselect:
            self._unselect_display(display, on_top=True)
        current_display = self.current_display
        if current_display:
            current_display.on_activate(is_push=False)
            app.widgetapp.window.set_main_area(current_display.widget)

    def _unselect_display(self, display, on_top):
        if on_top:
            display.on_deactivate()
        if display not in self.permanent_displays:
            display.cleanup()
        display.emit("removed")

    def push_folder_contents_display(self, folder_info, start_playing=False):
        self.push_display(FolderContentsDisplay(folder_info, start_playing))

class RecentlyActiveTracker(object):
    """Used by GuideDisplay to track recently downloaded/played items."""

    # maximum number of items to track for each of the lists
    ITEM_LIMIT = 6

    def __init__(self, guide_tab):
        # map ItemTracker objects to the GuideTab method we should call to set
        # the list for
        self.trackers = {
            self._recently_downloaded_tracker():
                guide_tab.set_recently_downloaded,
            self._recently_played_tracker('video'):
                guide_tab.set_recently_watched,
            self._recently_played_tracker('audio'):
                guide_tab.set_recently_listened,
        }

        for (tracker, set_recent_method) in self.trackers.items():
            list_callback = functools.partial(self.on_list_changed,
                                              set_recent_method)
            change_callback = functools.partial(self.on_items_changed,
                                                set_recent_method)
            tracker.connect('list-changed', list_callback)
            tracker.connect('items-changed', change_callback)
            app.item_tracker_updater.add_tracker(tracker)
            set_recent_method(tracker.get_items())

    def destroy(self):
        for (tracker, set_recent_method) in self.trackers:
            app.item_tracker_updater.remove_tracker(tracker)

    def _recently_downloaded_tracker(self):
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('downloaded_time', 'IS NOT', None)
        query.add_condition('expired', '=', False)
        query.add_condition('parent_id', 'IS', None)
        query.add_condition('watched_time', 'IS', None)
        query.set_order_by(['-downloaded_time'])
        query.set_limit(self.ITEM_LIMIT)
        return itemtrack.ItemTracker(call_on_ui_thread, query,
                                     item.ItemSource())

    def _recently_played_tracker(self, file_type):
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('file_type', '=', file_type)
        query.add_condition('watched_time', 'IS NOT', None)
        query.set_order_by(['-last_watched'])
        query.set_limit(self.ITEM_LIMIT)
        return itemtrack.ItemTracker(call_on_ui_thread, query,
                                     item.ItemSource())

    def on_list_changed(self, set_recent_method, tracker):
        set_recent_method(tracker.get_items())

    def on_items_changed(self, set_recent_method, tracker, changed_ids):
        set_recent_method(tracker.get_items())

class GuideDisplay(TabDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return tab_type == 'static' and selected_tabs[0].id == 'guide'

    def __init__(self, tab_type, selected_tabs):
        Display.__init__(self)
        self.widget = guidecontroller.GuideTab(selected_tabs[0].browser)
        self.recently_active_tracker = RecentlyActiveTracker(self.widget)
        app.display_manager.add_permanent_display(self) # once we're loaded,
                                                        # stay loaded

    def cleanup(self):
        self.recently_active_tracker.destroy()

class SiteDisplay(TabDisplay):
    _open_sites = {} # maps site ids -> BrowserNav objects for them

    @classmethod
    def on_sites_removed(cls, info_updater, id_list):
        for id_ in id_list:
            try:
                browser = cls._open_sites[id_]
            except KeyError:
                pass
            else:
                # explicitly destroy the browser.  Some platforms need this
                # call to cleanup.
                browser.destroy()

    @staticmethod
    def should_display(tab_type, selected_tabs):
        return tab_type in ('site', 'store') and len(selected_tabs) == 1 and \
               hasattr(selected_tabs[0], 'url')

    def __init__(self, tab_type, selected_tabs):
        Display.__init__(self)
        guide_info = selected_tabs[0]
        if guide_info.id not in self._open_sites:
            self._open_sites[guide_info.id] = browser.BrowserNav(guide_info)
        self.widget = self._open_sites[guide_info.id]

class ItemListDisplayMixin(object):
    def on_selected(self):
        app.item_list_controller_manager.controller_created(self.controller)

    def on_activate(self, is_push):
        app.item_list_controller_manager.controller_displayed(self.controller)
        if not is_push:
            # Focus the item list when we pop the video display from being on
            # top of us.
            #
            # FIXME: call_on_ui_thread is a bit weird here.  It's needed
            # because on OS X we can't call focus() yet on our tableview.
            call_on_ui_thread(self.controller.focus_view)
        super(ItemListDisplayMixin, self).on_activate(is_push)

    def on_deactivate(self):
        app.item_list_controller_manager.controller_no_longer_displayed(
                self.controller)

    def cleanup(self):
        self.controller.cleanup()
        app.item_list_controller_manager.controller_destroyed(self.controller)

    def toggle_column_enabled(self, name):
        app.widget_state.toggle_column_enabled(self.type, self.id,
                self.controller.selected_view, name)
        self.controller.update_columns_enabled()

class ItemListDisplay(ItemListDisplayMixin, TabDisplay):
    def __init__(self, tab_type, selected_tabs):
        Display.__init__(self)
        tab = selected_tabs[0]
        self.controller = self.make_controller(tab)
        self.widget = self.controller.widget
        self.type = tab_type
        self.id = tab.id

    def make_controller(self, tab):
        raise NotImplementedError()

    def get_column_info(self):
        available = WidgetStateStore.get_columns_available(self.type, self.id,
                self.controller.selected_view)
        enabled = app.widget_state.get_columns_enabled(self.type, self.id,
                self.controller.selected_view)
        return enabled, available

class FeedDisplay(ItemListDisplay):
    TAB_TYPE = u'feed'
    UPDATER_SIGNAL_NAME = 'feeds-changed'

    @classmethod
    def should_display(cls, tab_type, selected_tabs):
        return tab_type == cls.TAB_TYPE and len(selected_tabs) == 1 and \
               selected_tabs[0].type != u'tab'

    def cleanup(self):
        ItemListDisplay.cleanup(self)
        if widgetutil.feed_exists(self.feed_id):
            messages.MarkFeedSeen(self.feed_id).send_to_backend()

    def make_controller(self, tab):
        self.feed_id = tab.id
        return feedcontroller.FeedController(tab.id, tab.is_folder,
                                             tab.is_directory_feed)

class AllFeedsDisplay(FeedDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return (tab_type == u'tab' and len(selected_tabs) == 1 and
               selected_tabs[0].tab_class == u'feed')

    def make_controller(self, tab):
        return feedcontroller.AllFeedsController()

    def cleanup(self):
        ItemListDisplay.cleanup(self)

class PlaylistDisplay(ItemListDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return tab_type == 'playlist' and len(selected_tabs) == 1 and \
               selected_tabs[0].type != u'tab'

    def make_controller(self, playlist_info):
        return playlist.PlaylistItemController(playlist_info)

class DeviceDisplayMixin(object):
    def __init__(self, tab_type, selected_tabs):
        Display.__init__(self)
        device = selected_tabs[0]
        if getattr(device, 'fake', False):
            self.controller = devicecontroller.DeviceItemController(device)
            self.type = self.controller.type
            self.id = device.id
        else:
            self.controller = devicecontroller.DeviceController(device)
        self.widget = self.controller.widget

    def handle_current_sync_information(self, message):
        return

    def handle_device_sync_changed(self, message):
        pass

class DeviceDisplay(DeviceDisplayMixin, TabDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return tab_type == u'device' and len(selected_tabs) == 1 and \
               isinstance(selected_tabs[0], messages.DeviceInfo) and \
               not getattr(selected_tabs[0], 'fake', False)

    def handle_current_sync_information(self, message):
        if not getattr(self.controller.device, 'fake', False):
            self.controller.handle_current_sync_information(message)

    def handle_device_sync_changed(self, message):
        if not getattr(self.controller.device, 'fake', False):
            self.controller.handle_device_sync_changed(message)

    def on_activate(self, is_push):
        if self.controller.device.mount:
            message = messages.QuerySyncInformation(self.controller.device)
            message.send_to_backend()

class DeviceItemDisplay(DeviceDisplayMixin, ItemListDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        # FIXME: re-implement DeviceItemController with the new ItemList code
        return tab_type == u'device' and len(selected_tabs) == 1 and \
               isinstance(selected_tabs[0], messages.DeviceInfo) and \
               getattr(selected_tabs[0], 'fake', False)

class SharingDisplay(ItemListDisplay):
    def __init__(self, tab_type, selected_tabs):
        # our type is always 'sharing', regardless if the tab type is
        # 'sharing' or 'sharing-playlist'
        ItemListDisplay.__init__(self, u'sharing', selected_tabs)

    @staticmethod
    def should_display(tab_type, selected_tabs):
        return tab_type.startswith(u'sharing') and len(selected_tabs) == 1

    def make_controller(self, tab):
        return sharingcontroller.SharingController(tab)

class SearchDisplay(ItemListDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return tab_type == 'search' and selected_tabs[0].id == 'search'

    def make_controller(self, tab):
        return searchcontroller.SearchController()

class AudioVideoItemsDisplay(ItemListDisplay):
    @classmethod
    def should_display(cls, tab_type, selected_tabs):
        return (hasattr(selected_tabs[0], 'type') and selected_tabs[0].type ==
            cls.tab_type)

class VideoItemsDisplay(AudioVideoItemsDisplay):
    tab_type = u'videos'
    tab_id = u'videos'

    def make_controller(self, tab):
        return itemlistcontroller.VideoItemsController()

class AudioItemsDisplay(AudioVideoItemsDisplay):
    tab_type = u'music'
    tab_id = u'music'

    def make_controller(self, tab):
        return itemlistcontroller.AudioItemsController()

class OtherItemsDisplay(ItemListDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return tab_type == 'others'

    def make_controller(self, tab):
        return itemlistcontroller.OtherItemsController()

class DownloadingDisplay(ItemListDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return tab_type == 'downloading'

    def make_controller(self, tab):
        return downloadscontroller.DownloadsController()

class ConvertingDisplay(TabDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return tab_type == 'converting'

    def __init__(self, tab_type, selected_tabs):
        Display.__init__(self)
        self.controller = convertingcontroller.ConvertingController()
        self.widget = self.controller.widget

class FolderContentsDisplay(ItemListDisplayMixin, Display):
    def __init__(self, info, start_playing):
        self.type = u'folder-contents'
        self.id = info.id
        self.controller = itemlistcontroller.FolderContentsController(info,
                play_initial_list=start_playing)
        self.widget = self.controller.widget
        Display.__init__(self)

class CantPlayWidget(widgetset.SolidBackground):
    def __init__(self):
        widgetset.SolidBackground.__init__(self, (0, 0, 0))
        vbox = widgetset.VBox()
        label = widgetset.Label(_(
            "%(appname)s can't play this file.  You may "
            "be able to open it with a different program",
            {"appname": app.config.get(prefs.SHORT_APP_NAME)}
            ))
        label.set_color((1, 1, 1))
        vbox.pack_start(label)
        table = widgetset.Table(2, 2)
        table.set_column_spacing(6)
        self.filename_label = self._make_label('')
        self.filetype_label  = self._make_label('')
        table.pack(widgetutil.align_left(self._make_heading(_('Filename:'))),
                0, 0)
        table.pack(widgetutil.align_left(self.filename_label), 1, 0)
        table.pack(widgetutil.align_left(self._make_heading(_('File type:'))),
                0, 1)
        table.pack(widgetutil.align_left(self.filetype_label), 1, 1)
        vbox.pack_start(widgetutil.align_left(table, top_pad=12))
        hbox = widgetset.HBox(spacing=12)
        reveal_button = widgetset.Button(_('Reveal File'))
        self.play_externally_button = widgetset.Button(_('Play Externally'))
        self.play_externally_button.connect('clicked',
                                            self._on_play_externally)
        skip_button = widgetset.Button(_('Skip'))
        reveal_button.connect('clicked', self._on_reveal)
        skip_button.connect('clicked', self._on_skip)

        self.reveal_button_holder = widgetutil.HideableWidget(reveal_button)
        self.play_externally_button_holder = widgetutil.HideableWidget(
                                          self.play_externally_button)

        hbox.pack_start(self.reveal_button_holder)
        hbox.pack_start(self.play_externally_button_holder)
        hbox.pack_start(skip_button)
        vbox.pack_start(widgetutil.align_center(hbox, top_pad=24))
        alignment = widgetset.Alignment(xalign=0.5, yalign=0.5)
        alignment.add(vbox)
        self.add(alignment)

    def _make_label(self, text):
        label = widgetset.Label(text)
        label.set_color((1, 1, 1))
        return label

    def _make_heading(self, text):
        label = self._make_label(text)
        label.set_bold(True)
        return label

    def _on_reveal(self, button):
        app.widgetapp.reveal_file(self.filename)

    def _on_play_externally(self, button):
        app.widgetapp.open_file(self.filename)

    def _on_skip(self, button):
        app.playback_manager.play_next_item()

    def set_filename(self, filename):
        self.filename = filename
        self.filename_label.set_text(os.path.split(filename)[-1])
        self.filetype_label.set_text(os.path.splitext(filename)[1])
        if filetypes.is_playable_filename(filename):
            self.play_externally_button.set_text(_('Play Externally'))
        else:
            self.play_externally_button.set_text(_('Open Externally'))

    def set_remote(self, remote):
        widgets = [self.reveal_button_holder,
                   self.play_externally_button_holder]
        m = 'hide' if remote else 'show'
        for w in widgets:
            getattr(w, m)()

class VideoDisplay(Display):
    def __init__(self, renderer):
        Display.__init__(self)
        self.create_signal('cant-play')
        self.create_signal('ready-to-play')
        self.renderer = renderer
        self.widget = widgetset.VBox()
        self.widget.pack_start(self.renderer, expand=True)
        self.cant_play_widget = CantPlayWidget()
        self._showing_renderer = True
        self.in_fullscreen = False

    def show_renderer(self):
        if not self._showing_renderer:
            self.widget.remove(self.cant_play_widget)
            self.widget.pack_start(self.renderer, expand=True)
            self._showing_renderer = True

    def show_play_external(self):
        if self._showing_renderer:
            self._prepare_remove_renderer()
            self.widget.remove(self.renderer)
            self.widget.pack_start(self.cant_play_widget, expand=True)
            self._showing_renderer = False

    def _open_success(self):
        self.emit('ready-to-play')

    def _open_error(self):
        if not self.item_info.video_watched:
            messages.MarkItemWatched(self.item_info).send_to_backend()
        self.show_play_external()
        self.emit('cant-play')

    def setup(self, item_info, item_type, volume):
        self.show_renderer()
        self.cant_play_widget.set_remote(item_info.remote)
        self.cant_play_widget.set_filename(item_info.filename)
        self.item_info = item_info
        if item_type != 'video':
            self._open_error()
        else:
            self.renderer.set_item(item_info, self._open_success,
                                   self._open_error)
            self.renderer.set_volume(volume)

    def enter_fullscreen(self):
        self.renderer.enter_fullscreen()
        self.in_fullscreen = True

    def exit_fullscreen(self):
        self.renderer.exit_fullscreen()
        self.in_fullscreen = False

    def prepare_switch_to_attached_playback(self):
        self.renderer.prepare_switch_to_attached_playback()

    def prepare_switch_to_detached_playback(self):
        self.renderer.prepare_switch_to_detached_playback()

    def _prepare_remove_renderer(self):
        if self.in_fullscreen:
            self.exit_fullscreen()
        if self.renderer:
            self.renderer.stop()

    def cleanup(self):
        if self._showing_renderer:
            self._prepare_remove_renderer()
        # FIXME
        #
        # This isn't just feel-good defensive programming.
        #
        # When the tab disappears abnormally and it is a video display it
        # is destroyed.  That's fine.  However, it will happily try to
        # select a new tab, which tries to remove the video display again
        # because it is connected to 'removed' signal and calls
        # on_display_removed.  So we may end up calling the cleanup
        # twice.  I think the proper fix is to ensure that cleanup can only
        # be called once, but right now it's not too bad hopefully.
        if self.renderer:
            self.renderer.teardown()
        self.renderer = None

class MultipleSelectionDisplay(TabDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return len(selected_tabs) > 1

    def __init__(self, tab_type, selected_tabs):
        Display.__init__(self)
        self.type = tab_type
        self.child_count = self.folder_count = self.folder_child_count = 0
        tab_list = app.tabs[tab_type]
        for tab in selected_tabs:
            if hasattr(tab, "is_folder") and tab.is_folder:
                self.folder_count += 1
                self.folder_child_count += tab_list.get_child_count(tab.id)
            else:
                self.child_count += 1
        vbox = widgetset.VBox(spacing=20)
        label = self._make_label(tab_type, selected_tabs)
        label.set_size(widgetutil.font_scale_from_osx_points(30))
        label.set_bold(True)
        label.set_color((0.3, 0.3, 0.3))
        vbox.pack_start(widgetutil.align_center(label))
        vbox.pack_start(widgetutil.align_center(
            self._make_buttons(tab_type)))
        self.widget = widgetutil.align_middle(vbox)

    def _make_label(self, tab_type, selected_tabs):
        label_parts = []
        # NOTE: we need to use ngettext because some languages have multiple
        # plural forms.
        if self.folder_count > 0:
            if tab_type == 'feed':
                label_parts.append(ngettext(
                        '%(count)d Podcast Folder Selected',
                        '%(count)d Podcast Folders Selected',
                        self.folder_count,
                        {"count": self.folder_count}))
                label_parts.append(ngettext(
                        '(contains %(count)d podcast)',
                        '(contains %(count)d podcasts)',
                        self.folder_child_count,
                        {"count": self.folder_child_count}))
            else:
                label_parts.append(ngettext(
                        '%(count)d Playlist Folder Selected',
                        '%(count)d Playlist Folders Selected',
                        self.folder_count,
                        {"count": self.folder_count}))
                label_parts.append(ngettext(
                        '(contains %(count)d playlist)',
                        '(contains %(count)d playlists)',
                        self.folder_child_count,
                        {"count": self.folder_child_count}))

        if self.child_count > 0 and self.folder_count > 0:
            label_parts.append('')
        if self.child_count > 0:
            if tab_type == 'feed':
                label_parts.append(ngettext(
                        '%(count)d Podcast Selected',
                        '%(count)d Podcasts Selected',
                        self.child_count,
                        {"count": self.child_count}))
            elif tab_type == "site":
                label_parts.append(ngettext(
                        '%(count)d Source Selected',
                        '%(count)d Sources Selected',
                        self.child_count,
                        {"count": self.child_count}))
            else:
                label_parts.append(ngettext(
                        '%(count)d Playlist Selected',
                        '%(count)d Playlists Selected',
                        self.child_count,
                        {"count": self.child_count}))
        return widgetset.Label('\n'.join(label_parts))

    def _make_buttons(self, tab_type):
        delete_button = widgetset.Button(_('Delete All'))
        delete_button.connect('clicked', self._on_delete_clicked)
        if self.folder_count > 0 or tab_type == "site":
            return delete_button
        create_folder_button = widgetset.Button(_('Put Into a New Folder'))
        create_folder_button.connect('clicked', self._on_new_folder_clicked)
        hbox = widgetset.HBox(spacing=12)
        hbox.pack_start(delete_button)
        hbox.pack_start(create_folder_button)
        return hbox

    def _on_delete_clicked(self, button):
        app.widgetapp.remove_something()
        iter_ = app.tabs[self.type].view.model.first_iter()
        row = app.tabs[self.type].view.model[iter_]
        root = app.tabs[self.type].get_tab(row[0].id)
        app.display_manager.select_display_for_tabs(self.type, [root])

    def _on_new_folder_clicked(self, button):
        if self.type == 'feed':
            app.widgetapp.add_new_feed_folder(add_selected=True)
        else:
            app.widgetapp.add_new_playlist_folder(add_selected=True)

class ConnectDisplay(TabDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return tab_type == u'tab' and len(selected_tabs) == 1 and \
               selected_tabs[0].tab_class == u'connect'

    def __init__(self, tab_type, selected_tabs):
        Display.__init__(self)

        self.widget = widgetset.Scroller(False, True)
        alignment = widgetset.Alignment(xalign=0.5, yalign=0.0, xscale=1)
        alignment.add(tabcontroller.ConnectTab())
        self.widget.add(alignment)

class SourcesDisplay(TabDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return (tab_type == u'tab' and len(selected_tabs) == 1 and
                selected_tabs[0].tab_class == u'site')

    def __init__(self, tab_type, selected_tabs):
        Display.__init__(self)

        self.widget = widgetset.Scroller(False, True)
        alignment = widgetset.Alignment(xalign=0.5, yalign=0.0, xscale=1)
        alignment.add(tabcontroller.SourcesTab())
        self.widget.add(alignment)

class PlaylistsDisplay(TabDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return (tab_type == u'tab' and len(selected_tabs) == 1 and
                selected_tabs[0].tab_class == u'playlist')

    def __init__(self, tab_type, selected_tabs):
        Display.__init__(self)

        self.widget = widgetset.Scroller(False, True)
        alignment = widgetset.Alignment(xalign=0.5, yalign=0.0, xscale=1)
        alignment.add(tabcontroller.PlaylistsTab())
        self.widget.add(alignment)

class StoresDisplay(TabDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return (tab_type == u'tab' and len(selected_tabs) == 1 and
                selected_tabs[0].tab_class == u'store')

    def __init__(self, tab_type, selected_tabs):
        Display.__init__(self)

        self.widget = widgetset.Scroller(False, True)
        alignment = widgetset.Alignment(xalign=0.5, yalign=0.0, xscale=1)
        alignment.add(tabcontroller.StoresTab())
        self.widget.add(alignment)

class DummyDisplay(TabDisplay):
    @staticmethod
    def should_display(tab_type, selected_tabs):
        return True

    def __init__(self, tab_type, selected_tabs):
        Display.__init__(self)
        text = '\n'.join(tab.name for tab in selected_tabs)
        label = widgetset.Label(text)
        label.set_size(3)
        label.set_bold(True)
        label.set_color((1.0, 0, 0))
        alignment = widgetset.Alignment(xalign=0.5, yalign=0.0)
        alignment.add(label)
        self.widget = alignment
