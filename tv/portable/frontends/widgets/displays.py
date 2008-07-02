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
from miro.frontends.widgets import feedview
from miro.frontends.widgets import itemlist
from miro.plat.frontends.widgets import widgetset

class Display(object):
    """A display is a view that can be shown in the right hand side of the
    app.

    Attributes:

    widget -- Widget to show to the user.
    """

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
    def __init__(self):
        self.display_classes = [
                FeedDisplay,
                LibraryDisplay,
                NewVideosDisplay,
                DownloadingDisplay,
                StaticTabDisplay,
                DummyDisplay,
        ]
        self.current_display = None
        self.selected_tab_list = self.selected_tabs = None

    def select_display_for_tabs(self, selected_tab_list, selected_tabs):
        """Select a display to show in the right-hand side.  """
        if (selected_tab_list is self.selected_tab_list and 
                selected_tabs == self.selected_tabs):
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
        if self.current_display:
            self.current_display.cleanup()
        self.current_display = display
        app.widgetapp.window.set_main_area(display.widget)

class StaticTabDisplay(TabDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'static'

    def __init__(self, type, selected_tabs):
        # There is always exactly 1 selected static tab
        self.widget = selected_tabs[0].view

class ItemListDisplay(TabDisplay):
    def __init__(self, type, selected_tabs):
        tab = selected_tabs[0]
        self.view = self.make_view(tab)
        self.feed_id = self.view.feed_id
        self.view.connect('play-video', self.on_play_video)
        self.widget = self.view.widget

    def on_play_video(self, view, video_path):
        app.menu_manager.handle_playing_selection()
        video_display = VideoDisplay(video_path)
        app.display_manager.select_display(video_display)

    def handle_item_list(self, message):
        if message.feed_id != self.feed_id:
            raise ValueError("Wrong feed id")
        self.view.handle_item_list(message)

    def handle_items_changed(self, message):
        if message.feed_id != self.feed_id:
            raise ValueError("Wrong feed id")
        self.view.handle_item_list(message)

    def cleanup(self):
        self.view.stop_tracking()

    def make_view(self, tab):
        pass

class FeedDisplay(ItemListDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'feed' and len(selected_tabs) == 1

    def make_view(self, tab):
        return feedview.FeedView(tab.id, tab.is_folder)

class DownloadingDisplay(ItemListDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'static' and selected_tabs[0].id == 'downloading'

    def make_view(self, tab):
        return itemlist.DownloadsView()

class NewVideosDisplay(ItemListDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'static' and selected_tabs[0].id == 'new'

    def make_view(self, tab):
        return itemlist.NewView()

class LibraryDisplay(ItemListDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return type == 'static' and selected_tabs[0].id == 'library'

    def make_view(self, tab):
        return itemlist.LibraryView()

class VideoDisplay(Display):
    def __init__(self, path):
        import os
        self.widget = widgetset.Label("Now playing: %s" %
                os.path.basename(path)[:30])

    def cleanup(self):
        # Should cleanup resources here
        pass

class DummyDisplay(TabDisplay):
    @staticmethod
    def should_display(type, selected_tabs):
        return True

    def __init__(self, type, selected_tabs):
        text = '\n'.join(tab.name for tab in selected_tabs)
        label = widgetset.Label(text)
        label.set_size(3)
        label.set_bold(True)
        label.set_color((1.0, 0, 0))
        alignment = widgetset.Alignment(xalign=0.5, yalign=0.0)
        alignment.add(label)
        self.widget = alignment
