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

import cmd
import threading
import time
import Queue

from miro import app
from miro import dialogs
from miro import eventloop
from miro import item
from miro import folder
from miro import util
from miro import tabs
from miro.frontends.cli import clidialog
from miro.plat import resources

def run_in_event_loop(func):
    def decorated(*args, **kwargs):
        return_hack = []
        event = threading.Event()
        def runThenSet():
            try:
                return_hack.append(func(*args, **kwargs))
            finally:
                event.set()
        eventloop.add_urgent_call(runThenSet, 'run in event loop')
        event.wait()
        if return_hack:
            return return_hack[0]
    decorated.__doc__ = func.__doc__
    return decorated

class FakeTab:
    def __init__(self, tab_type, tab_template_base):
        self.type = tab_type
        self.tab_template_base = tab_template_base

class MiroInterpreter(cmd.Cmd):
    def __init__(self):
        cmd.Cmd.__init__(self)
        self.quit_flag = False
        self.tab = None
        self.init_database_objects()

    def emptyline(self):
        print "Type \"help\" for help."

    @run_in_event_loop
    def init_database_objects(self):
        self.video_feed_tabs = tabs.TabOrder.video_feed_order()
        self.audio_feed_tabs = tabs.TabOrder.audio_feed_order()
        self.playlist_tabs = tabs.TabOrder.playlist_order()
        self.tab_changed()

    def tab_changed(self):
        """Calculate the current prompt.  This method access database objects,
        so it should only be called from the backend event loop
        """
        if self.tab is None:
            self.prompt = "> "
            self.selection_type = None

        elif self.tab.type == 'feed':
            if isinstance(self.tab, folder.ChannelFolder):
                self.prompt = "channel folder: %s > " % self.tab.get_title()
                self.selection_type = 'channel-folder'
            else:
                self.prompt = "channel: %s > " % self.tab.get_title()
                self.selection_type = 'feed'

        elif self.tab.type == 'playlist':
            self.prompt = "playlist: %s > " % self.tab.get_title()
            self.selection_type = 'playlist'

        elif (self.tab.type == 'statictab' and
              self.tab.tab_template_base == 'downloadtab'):
            self.prompt = "downloads > "
            self.selection_type = 'downloads'
        else:
            raise ValueError("Unknown tab type")

    def postcmd(self, stop, line):
        # HACK
        # If the last command results in a dialog, give it a little time to
        # pop up
        time.sleep(0.1)
        while True:
            try:
                dialog = app.cli_events.dialog_queue.get_nowait()
            except Queue.Empty:
                break
            clidialog.handle_dialog(dialog)

        return self.quit_flag

    def do_help(self, line):
        """help -- Lists commands and help."""
        commands = [m for m in dir(self) if m.startswith("do_")]
        for mem in commands:
            docstring = getattr(self, mem).__doc__
            print "  ", docstring.strip()

    def do_quit(self, line):
        """quit -- Quits Miro cli."""
        self.quit_flag = True

    @run_in_event_loop
    def do_feed(self, line):
        """feed <name> -- Selects a feed by name."""
        for tab in self.video_feed_tabs.get_all_tabs():
            if tab.get_title() == line:
                self.tab = tab
                self.tab.type = "feed"
                self.tab_changed()
                return
        for tab in self.audio_feed_tabs.get_all_tabs():
            if tab.get_title() == line:
                self.tab = tab
                self.tab.type = "feed"
                self.tab_changed()
                return
        print "Error: %s not found." % line

    @run_in_event_loop
    def do_rmfeed(self, line):
        """rmfeed <name> -- Deletes a feed."""
        for tab in self.video_feed_tabs.get_all_tabs():
            if tab.get_title() == line:
                tab.remove()
                return
        for tab in self.audio_feed_tabs.get_all_tabs():
            if tab.get_title() == line:
                tab.remove()
                return
        print "Error: %s not found." % line

    @run_in_event_loop
    def complete_feed(self, text, line, begidx, endidx):
        return self.handle_tab_complete(text, list(self.video_feed_tabs.get_all_tabs()) + list(self.audio_feed_tabs.get_all_tabs()))

    @run_in_event_loop
    def complete_rmfeed(self, text, line, begidx, endidx):
        return self.handle_tab_complete(text, list(self.video_feed_tabs.get_all_tabs()) + list(self.audio_feed_tabs.get_all_tabs()))

    @run_in_event_loop
    def complete_playlist(self, text, line, begidx, endidx):
        return self.handle_tab_complete(text, self.playlist_tabs.get_all_tabs())

    def handle_tab_complete(self, text, view_items):
        text = text.lower()
        matches = []
        for tab in view_items:
            if tab.get_title().lower().startswith(text):
                matches.append(tab.get_title())
        return matches

    def handle_item_complete(self, text, view, filterFunc=lambda i: True):
        text = text.lower()
        matches = []
        for item in view:
            if (item.get_title().lower().startswith(text) and
                    filterFunc(item)):
                matches.append(item.get_title())
        return matches

    def _print_feeds(self, feeds):
        current_folder = None
        for tab in feeds:
            if isinstance(tab, folder.ChannelFolder):
                current_folder = tab
            elif tab.get_folder() is not current_folder:
                current_folder = None
            if current_folder is None:
                print " * " + tab.get_title()
            elif current_folder is tab:
                print " * [Folder] %s" % tab.get_title()
            else:
                print " * - %s" % tab.get_title()

    @run_in_event_loop
    def do_feeds(self, line):
        """feeds -- Lists all feeds."""
        print "VIDEO FEEDS"
        self._print_feeds(self.video_feed_tabs.get_all_tabs())
        print "AUDIO FEEDS"
        self._print_feeds(self.audio_feed_tabs.get_all_tabs())

    @run_in_event_loop
    def do_play(self, line):
        """play <name> -- Plays an item by name in an external player."""
        if self.selection_type is None:
            print "Error: No feed/playlist selected."
            return
        item = self._find_item(line)
        if item is None:
            print "No item named %r" % line
            return
        if item.is_downloaded():
            resources.open_file(item.get_video_filename())
        else:
            print '%s is not downloaded' % item.get_title()

    @run_in_event_loop
    def do_playlists(self, line):
        """playlists -- Lists all playlists."""
        for tab in self.playlistTabs.getView():
            print tab.obj.get_title()

    @run_in_event_loop
    def do_playlist(self, line):
        """playlist <name> -- Selects a playlist."""
        for tab in self.playlistTabs.getView():
            if tab.obj.get_title() == line:
                self.tab = tab
                self.tab_changed()
                return
        print "Error: %s not found." % line

    @run_in_event_loop
    def do_items(self, line):
        """items -- Lists the items in the feed/playlist/tab selected."""
        if self.selection_type is None:
            print "Error: No tab/feed/playlist selected."
            return
        elif self.selection_type == 'feed':
            feed = self.tab
            view = feed.items
            self.printout_item_list(view)
        elif self.selection_type == 'playlist':
            playlist = self.tab.obj
            self.printout_item_list(playlist.getView())
        elif self.selection_type == 'downloads':
            self.printout_item_list(item.Item.downloading_view(),
                                    item.Item.paused_view())
        elif self.selection_type == 'channel-folder':
            folder = self.tab.obj
            allItems = views.items.filterWithIndex(
                    indexes.itemsByChannelFolder, folder)
            allItemsSorted = allItems.sort(folder.itemSort.sort)
            self.printout_item_list(allItemsSorted)
            allItemsSorted.unlink()
        else:
            raise ValueError("Unknown tab type")

    @run_in_event_loop
    def do_downloads(self, line):
        """downloads -- Selects the downloads tab."""
        self.tab = FakeTab("statictab", "downloadtab")
        self.tab_changed()

    def printout_item_list(self, *views):
        totalItems = 0
        for view in views:
            totalItems += view.count()
        if totalItems > 0:
            print "%-20s %-10s %s" % ("State", "Size", "Name")
            print "-" * 70
            for view in views:
                for item in view:
                    state = item.get_state()
                    if state == 'downloading':
                        state += ' (%0.0f%%)' % item.download_progress()
                    print "%-20s %-10s %s" % (state, item.get_size_for_display(),
                            item.get_title())
            print
        else:
            print "No items"

    def _get_item_view(self):
        if self.selection_type == 'feed':
            return item.Item.visible_feed_view(self.tab.id)
        elif self.selection_type == 'playlist':
            return item.Item.playlist_view(self.tab.id)
        elif self.selection_type == 'downloads':
            return item.Item.downloading_view()
        elif self.selection_type == 'channel-folder':
            folder = self.tab
            return item.Item.visible_folder_view(folder.id)
        else:
            raise ValueError("Unknown selection type")

    def _find_item(self, line):
        line = line.lower()
        for item in self._get_item_view():
            if item.get_title().lower() == line:
                return item

    @run_in_event_loop
    def do_stop(self, line):
        """stop <name> -- Stops download by name."""
        if self.selection_type is None:
            print "Error: No feed/playlist selected."
            return
        item = self._find_item(line)
        if item is None:
            print "No item named %r" % line
            return
        if item.get_state() in ('downloading', 'paused'):
            item.expire()
        else:
            print '%s is not being downloaded' % item.get_title()

    @run_in_event_loop
    def complete_stop(self, text, line, begidx, endidx):
        return self.handle_item_complete(text, self._get_item_view(),
                lambda i: i.get_state() in ('downloading', 'paused'))

    @run_in_event_loop
    def do_download(self, line):
        """download <name> -- Downloads an item by name in the feed/playlist selected."""
        if self.selection_type is None:
            print "Error: No feed/playlist selected."
            return
        item = self._find_item(line)
        if item is None:
            print "No item named %r" % line
            return
        if item.get_state() == 'downloading':
            print '%s is currently being downloaded' % item.get_title()
        elif item.is_downloaded():
            print '%s is already downloaded' % item.get_title()
        else:
            item.download()

    @run_in_event_loop
    def complete_download(self, text, line, begidx, endidx):
        return self.handle_item_complete(text, self._get_item_view(),
                lambda i: i.is_downloadable())

    @run_in_event_loop
    def do_pause(self, line):
        """pause <name> -- Pauses a download by name."""
        if self.selection_type is None:
            print "Error: No feed/playlist selected."
            return
        item = self._find_item(line)
        if item is None:
            print "No item named %r" % line
            return
        if item.get_state() == 'downloading':
            item.pause()
        else:
            print '%s is not being downloaded' % item.get_title()

    @run_in_event_loop
    def complete_pause(self, text, line, begidx, endidx):
        return self.handle_item_complete(text, self._get_item_view(),
                lambda i: i.get_state() == 'downloading')

    @run_in_event_loop
    def do_resume(self, line):
        """resume <name> -- Resumes a download by name."""
        if self.selection_type is None:
            print "Error: No feed/playlist selected."
            return
        item = self._find_item(line)
        if item is None:
            print "No item named %r" % line
            return
        if item.get_state() == 'paused':
            item.resume()
        else:
            print '%s is not a paused download' % item.get_title()

    @run_in_event_loop
    def complete_resume(self, text, line, begidx, endidx):
        return self.handle_item_complete(text, self._get_item_view(),
                lambda i: i.get_state() == 'paused')

    @run_in_event_loop
    def do_rm(self, line):
        """rm <name> -- Removes an item by name in the feed/playlist selected."""
        if self.selection_type is None:
            print "Error: No feed/playlist selected."
            return
        item = self._find_item(line)
        if item is None:
            print "No item named %r" % line
            return
        if item.is_downloaded():
            item.expire()
        else:
            print '%s is not downloaded' % item.get_title()

    @run_in_event_loop
    def complete_rm(self, text, line, begidx, endidx):
        return self.handle_item_complete(text, self._get_item_view(),
                lambda i: i.is_downloaded())

    @run_in_event_loop
    def do_testdialog(self, line):
        """testdialog -- Tests the cli dialog system."""
        d = dialogs.ChoiceDialog("Hello", "I am a test dialog",
                dialogs.BUTTON_OK, dialogs.BUTTON_CANCEL)
        def callback(dialog):
            print "TEST CHOICE: %s" % dialog.choice
        d.run(callback)

    @run_in_event_loop
    def do_dumpdatabase(self, line):
        """dumpdatabase -- Dumps the database."""
        from miro import database
        print "Dumping database...."
        database.defaultDatabase.liveStorage.dumpDatabase(database.defaultDatabase)
        print "Done."
