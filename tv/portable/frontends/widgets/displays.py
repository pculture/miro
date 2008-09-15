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

"""displays.py -- Handle switching the content on the right hand side of the
app.
"""

from miro import app
from miro import messages
from miro import signals
from miro.frontends.widgets import browser
from miro.frontends.widgets import downloadscontroller
from miro.frontends.widgets import feedcontroller
from miro.frontends.widgets import itemlistcontroller
from miro.frontends.widgets import playlist
from miro.frontends.widgets import widgetutil
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

    def on_activate(self):
        """Perform code that needs to be run when the display becomes the
        active display (the one on the top of the display stack).
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

class TabDisplay(Display):
    """Display that displays the selection in the tab list."""

    def __init__(self, type, selected_tabs):
        raise NotImplementedError()

    @staticmethod
    def should_display(type, selected_tabs):
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
        self.display_classes = [
                FeedDisplay,
                PlaylistDisplay,
                SiteDisplay,
                SearchDisplay,
                LibraryDisplay,
                IndividualDownloadsDisplay,
                NewVideosDisplay,
                DownloadingDisplay,
                GuideDisplay,
                DummyDisplay,
        ]
        self.display_stack = []
        self.selected_tab_list = self.selected_tabs = None

    def get_current_display(self):
        try:
            return self.display_stack[-1]
        except IndexError:
            return None
    current_display = property(get_current_display)

    def select_display_for_tabs(self, selected_tab_list, selected_tabs):
        """Select a display to show in the right-hand side.  """
        if (selected_tab_list is self.selected_tab_list and 
                selected_tabs == self.selected_tabs and 
                len(self.display_stack) > 0 and
                isinstance(self.display_stack[-1], TabDisplay)):
            print 'not reselecting'
            return

        self.selected_tab_list = selected_tab_list
        self.selected_tabs = selected_tabs
        type = selected_tab_list.type

        for klass in self.display_classes:
            if klass.should_display(type, selected_tabs):
                self.select_display(klass(type, selected_tabs))
                return
        raise AssertionError("Can't find display for %s %s" % (tabs,
            selected_tabs))

    def select_display(self, display):
        """Select a display and clear out the current display stack."""
        self.deselect_all_displays()
        self.push_display(display)

    def deselect_all_displays(self):
        """Deselect all displays."""
        for old_display in self.display_stack:
            self._unselect_display(old_display)
        self.display_stack = []

    def push_display(self, display):
        """Select a display and push it on top of the display stack"""
        if len(self.display_stack) > 0:
            self.current_display.on_deactivate()
        self.display_stack.append(display)
        display.on_selected()
        display.on_activate()
        app.widgetapp.window.set_main_area(display.widget)

    def pop_display(self):
        """Remove the current display, then select the next one in the display
        stack.
        """
        self._unselect_display(self.display_stack.pop())
        self.current_display.on_activate()
        app.widgetapp.window.set_main_area(self.current_display.widget)

    def _unselect_display(self, display):
        display.on_deactivate()
        display.cleanup()
        display.emit("removed")

class GuideDisplay(TabDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'static' and selected_tabs[0].id == 'guide'

    def __init__(self, type, selected_tabs):
        Display.__init__(self)
        self.widget = selected_tabs[0].browser

class SiteDisplay(TabDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'site' and len(selected_tabs) == 1

    def __init__(self, type, selected_tabs):
        Display.__init__(self)
        self.widget = browser.Browser(selected_tabs[0])

class ItemListDisplay(TabDisplay):
    def __init__(self, type, selected_tabs):
        Display.__init__(self)
        tab = selected_tabs[0]
        self.controller = self.make_controller(tab)
        self.widget = self.controller.widget

    def on_selected(self):
        app.item_list_controller_manager.controller_created(self.controller)
        self.controller.start_tracking()

    def on_activate(self):
        app.item_list_controller_manager.controller_displayed(self.controller)

    def on_deactivate(self):
        app.item_list_controller_manager.controller_no_longer_displayed(
                self.controller)

    def cleanup(self):
        self.controller.stop_tracking()
        app.item_list_controller_manager.controller_destroyed(self.controller)

    def make_controller(self, tab):
        raise NotImplementedError()

class FeedDisplay(ItemListDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'feed' and len(selected_tabs) == 1


    def cleanup(self):
        ItemListDisplay.cleanup(self)
        if widgetutil.feed_exists(self.feed_id):
            messages.MarkChannelSeen(self.feed_id).send_to_backend()

    def make_controller(self, tab):
        self.feed_id = tab.id
        return feedcontroller.FeedController(tab.id, tab.is_folder)

class PlaylistDisplay(ItemListDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'playlist' and len(selected_tabs) == 1

    def make_controller(self, playlist_info):
        return playlist.PlaylistView(playlist_info)

class DownloadingDisplay(ItemListDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'static' and selected_tabs[0].id == 'downloading'

    def make_controller(self, tab):
        return downloadscontroller.DownloadsController()

class NewVideosDisplay(ItemListDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'static' and selected_tabs[0].id == 'new'

    def make_controller(self, tab):
        return itemlistcontroller.NewController()

class SearchDisplay(ItemListDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'static' and selected_tabs[0].id == 'search'

    def make_controller(self, tab):
        return itemlistcontroller.SearchController()

class LibraryDisplay(ItemListDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'static' and selected_tabs[0].id == 'library'

    def make_controller(self, tab):
        return itemlistcontroller.LibraryController()

class IndividualDownloadsDisplay(ItemListDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'static' and selected_tabs[0].id == 'individual_downloads'

    def make_controller(self, tab):
        return itemlistcontroller.IndividualDownloadsController()

class VideoDisplay(Display):
    def __init__(self):
        Display.__init__(self)
        self.widget = widgetset.VideoRenderer()
        self.in_fullscreen = False

    def setup(self, item_info, volume):
        self.widget.set_movie_item(item_info)
        self.set_volume(volume)

    def set_volume(self, volume):
        self.widget.set_volume(volume)

    def get_elapsed_playback_time(self):
        return self.widget.get_elapsed_playback_time()

    def get_total_playback_time(self):
        return self.widget.get_total_playback_time()

    def play(self):
        self.widget.play()

    def play_from_time(self, resume_time=0):
        self.widget.play_from_time(resume_time)

    def pause(self):
        self.widget.pause()

    def stop(self):
        self.widget.stop()

    def set_playback_rate(self, rate):
        self.widget.set_playback_rate(rate)

    def seek_to(self, position):
        self.widget.seek_to(position)

    def enter_fullscreen(self):
        self.widget.enter_fullscreen()
        self.in_fullscreen = True
    
    def exit_fullscreen(self):
        self.widget.exit_fullscreen()
        self.in_fullscreen = False

    def cleanup(self):
        if self.in_fullscreen:
            self.exit_fullscreen()
        self.widget.stop()
        self.widget.teardown()

class DummyDisplay(TabDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return True

    def __init__(self, type, selected_tabs):
        Display.__init__(self)
        text = '\n'.join(tab.name for tab in selected_tabs)
        label = widgetset.Label(text)
        label.set_size(3)
        label.set_bold(True)
        label.set_color((1.0, 0, 0))
        alignment = widgetset.Alignment(xalign=0.5, yalign=0.0)
        alignment.add(label)
        self.widget = alignment
