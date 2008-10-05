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

import cmd
import threading
import time
import Queue

from miro import app
from miro import dialogs
from miro import eventloop
from miro import folder
from miro import indexes
from miro import util
from miro import views
from miro.frontends.cli import clidialog

def runInEventLoop(func):
    def decorated(*args, **kwargs):
        return_hack = []
        event = threading.Event()
        def runThenSet():
            try:
                return_hack.append(func(*args, **kwargs))
            finally:
                event.set()
        eventloop.addUrgentCall(runThenSet, 'run in event loop')
        event.wait()
        if return_hack:
            return return_hack[0]
    return decorated

class MiroInterpreter(cmd.Cmd):
    def __init__(self):
        cmd.Cmd.__init__(self)
        self.quit_flag = False
        self.tab = None
        self.init_database_objects()

    @runInEventLoop
    def init_database_objects(self):
        self.channelTabs = util.getSingletonDDBObject(views.channelTabOrder)
        self.playlistTabs = util.getSingletonDDBObject(views.playlistTabOrder)
        self.tab_changed()

    def tab_changed(self):
        """Calculate the current prompt.  This method access database objects,
        so it should only be called from the backend event loop
        """
        if self.tab is None:
            self.prompt = "> "
            self.selection_type = None
        elif self.tab.type == 'feed':
            if isinstance(self.tab.obj, folder.ChannelFolder):
                self.prompt = "channel folder: %s > " % self.tab.obj.get_title()
                self.selection_type = 'channel-folder'
            else:
                self.prompt = "channel: %s > " % self.tab.obj.get_title()
                self.selection_type = 'feed'
        elif self.tab.type == 'playlist':
            self.prompt = "playlist: %s > " % self.tab.obj.get_title()
            self.selection_type = 'playlist'
        elif (self.tab.type == 'statictab' and 
                self.tab.tabTemplateBase == 'downloadtab'):
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

    def do_quit(self, line):
        self.quit_flag = True

    @runInEventLoop
    def do_feed(self, line):
        for tab in self.channelTabs.getView():
            if tab.obj.get_title() == line:
                self.tab = tab
                self.tab_changed()
                return
        print "Error: %s not found" % line

    @runInEventLoop
    def do_rmfeed(self, line):
        for tab in self.channelTabs.getView():
            if tab.obj.get_title() == line:
                tab.obj.remove()
                return
        print "Error: %s not found" % line

    @runInEventLoop
    def complete_feed(self, text, line, begidx, endidx):
        return self.handle_tab_complete(text, self.channelTabs.getView())

    @runInEventLoop
    def complete_rmfeed(self, text, line, begidx, endidx):
        return self.handle_tab_complete(text, self.channelTabs.getView())

    @runInEventLoop
    def complete_playlist(self, text, line, begidx, endidx):
        return self.handle_tab_complete(text, self.playlistTabs.getView())

    def handle_tab_complete(self, text, view):
        text = text.lower()
        matches = []
        for tab in view:
            if tab.obj.get_title().lower().startswith(text):
                matches.append(tab.obj.get_title())
        return matches

    def handle_item_complete(self, text, view, filterFunc=lambda i: True):
        text = text.lower()
        matches = []
        for item in view:
            if (item.get_title().lower().startswith(text) and 
                    filterFunc(item)):
                matches.append(item.get_title())
        return matches

    @runInEventLoop
    def do_feeds(self, line):
        current_folder = None
        for tab in self.channelTabs.getView():
            if isinstance(tab.obj, folder.ChannelFolder):
                current_folder = tab.obj
            elif tab.obj.getFolder() is not current_folder:
                current_folder = None
            if current_folder is None:
                print tab.obj.get_title()
            elif current_folder is tab.obj:
                print "[Folder] %s" % tab.obj.get_title()
            else:
                print " - %s" % tab.obj.get_title()

    @runInEventLoop
    def do_playlists(self, line):
        for tab in self.playlistTabs.getView():
            print tab.obj.get_title()

    @runInEventLoop
    def do_playlist(self, line):
        for tab in self.playlistTabs.getView():
            if tab.obj.get_title() == line:
                self.tab = tab
                self.tab_changed()
                return
        print "Error: %s not found" % line

    @runInEventLoop
    def do_items(self, line):
        if self.selection_type is None:
            print "Error: No feed/playlist selected"
            return
        elif self.selection_type == 'feed':
            feed = self.tab.obj
            view = feed.items.sort(feed.itemSort.sort)
            self.printout_item_list(view)
            view.unlink()
        elif self.selection_type == 'playlist':
            playlist = self.tab.obj
            self.printout_item_list(playlist.getView())
        elif self.selection_type == 'downloads':
            self.printout_item_list(views.downloadingItems, views.pausedItems)
        elif self.selection_type == 'channel-folder':
            folder = self.tab.obj
            allItems = views.items.filterWithIndex(
                    indexes.itemsByChannelFolder, folder)
            allItemsSorted = allItems.sort(folder.itemSort.sort)
            self.printout_item_list(allItemsSorted)
            allItemsSorted.unlink()
        else:
            raise ValueError("Unknown tab type")

    @runInEventLoop
    def do_downloads(self, line):
        for tab in views.staticTabs:
            if tab.tabTemplateBase == 'downloadtab':
                self.tab = tab
                self.tab_changed()
                return
        raise ValueError("Couldn't find download tab")

    def printout_item_list(self, *views):
        totalItems = 0
        for view in views:
            totalItems += len(view)
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
            feed = self.tab.obj
            return feed.items
        elif self.selection_type == 'playlist':
            playlist = self.tab.obj
            return playlist.getView()
        elif self.selection_type == 'downloads':
            return views.downloadingItems
        elif self.selection_type == 'channel-folder':
            folder = self.tab.obj
            return views.items.filterWithIndex(indexes.itemsByChannelFolder,
                    folder)
        else:
            raise ValueError("Unkown selection type")


    def _find_item(self, line):
        line = line.lower()
        for item in self._get_item_view():
            if item.get_title().lower() == line:
                return item

    @runInEventLoop
    def do_stop(self, line):
        if self.selection_type is None:
            print "Error: No feed/playlist selected"
            return
        item = self._find_item(line)
        if item is None:
            print "No item named %r" % line
            return
        if item.get_state() in ('downloading', 'paused'):
            item.expire()
        else:
            print '%s is not being downloaded' % item.get_title()

    @runInEventLoop
    def complete_stop(self, text, line, begidx, endidx):
        return self.handle_item_complete(text, self._get_item_view(),
                lambda i: i.get_state() in ('downloading', 'paused'))

    @runInEventLoop
    def do_download(self, line):
        if self.selection_type is None:
            print "Error: No feed/playlist selected"
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

    @runInEventLoop
    def complete_download(self, text, line, begidx, endidx):
        return self.handle_item_complete(text, self._get_item_view(),
                lambda i: i.is_downloadable())

    @runInEventLoop
    def do_pause(self, line):
        if self.selection_type is None:
            print "Error: No feed/playlist selected"
            return
        item = self._find_item(line)
        if item is None:
            print "No item named %r" % line
            return
        if item.get_state() == 'downloading':
            item.pause()
        else:
            print '%s is not being downloaded' % item.get_title()

    @runInEventLoop
    def complete_pause(self, text, line, begidx, endidx):
        return self.handle_item_complete(text, self._get_item_view(),
                lambda i: i.get_state() == 'downloading')

    @runInEventLoop
    def do_resume(self, line):
        if self.selection_type is None:
            print "Error: No feed/playlist selected"
            return
        item = self._find_item(line)
        if item is None:
            print "No item named %r" % line
            return
        if item.get_state() == 'paused':
            item.resume()
        else:
            print '%s is not a paused download' % item.get_title()

    @runInEventLoop
    def complete_resume(self, text, line, begidx, endidx):
        return self.handle_item_complete(text, self._get_item_view(),
                lambda i: i.get_state() == 'paused')

    @runInEventLoop
    def do_rm(self, line):
        if self.selection_type is None:
            print "Error: No feed/playlist selected"
            return
        item = self._find_item(line)
        if item is None:
            print "No item named %r" % line
            return
        if item.is_downloaded():
            item.expire()
        else:
            print '%s is not downloaded' % item.get_title()

    @runInEventLoop
    def complete_rm(self, text, line, begidx, endidx):
        return self.handle_item_complete(text, self._get_item_view(),
                lambda i: i.is_downloaded())

    @runInEventLoop
    def do_testdialog(self, line):
        d = dialogs.ChoiceDialog("Hello", "I am a test dialog",
                dialogs.BUTTON_OK, dialogs.BUTTON_CANCEL)
        def callback(dialog):
            print "TEST CHOICE: %s" % dialog.choice
        d.run(callback)

    @runInEventLoop
    def do_dumpdatabase(self, line):
        from miro import database
        print "Dumping database...."
        database.defaultDatabase.liveStorage.dumpDatabase(database.defaultDatabase)
        print "Done."
