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

from miro import views
from miro import config
from miro import prefs
from miro import eventloop
from datetime import datetime
from miro.fasttypes import SortedList

# filter functions we use to create views.

def manual_pending_filter(x):
    """Returns true iff x is a manual download item that's pending"""
    return x.is_pending_manual_download()

def auto_pending_filter(x):
    """Returns true iff x is an automatic download item that's pending"""
    if not x.getFeed().isAutoDownloadable():
        return False
    return x.isEligibleForAutoDownload()

def pending_sort(a, b):
    if a[1] < b[1]:
        return True
    if a[1] > b[1]:
        return False
    return a[2] < b[2]

class Downloader:
    def __init__(self, is_auto):
        self.dc = None
        self.inDownloads = False
        self.paused = False
        self.running_count = 0
        self.pending_count = 0
        self.feed_pending_count = {}
        self.feed_running_count = {}
        self.feed_time = {}
        self.is_auto = is_auto
        if is_auto:
            self.pendingItems = views.items.filter(auto_pending_filter)
            self.runningItems = views.autoDownloads
            self.MAX = config.get(prefs.DOWNLOADS_TARGET)
        else:
            self.pendingItems = views.items.filter(manual_pending_filter)
            self.runningItems = views.manualDownloads
            self.MAX = config.get(prefs.MAX_MANUAL_DOWNLOADS)

        for item in self.pendingItems:
            self.pending_on_add(item, item.id)
        for item in self.runningItems:
            self.running_on_add(item, item.id)
        self.pendingItems.addAddCallback(self.pending_on_add)
        self.pendingItems.addRemoveCallback(self.pending_on_remove)
        self.runningItems.addAddCallback(self.running_on_add)
        self.runningItems.addRemoveCallback(self.running_on_remove)

        if is_auto:
            self.new_count = 0
            self.feed_new_count = {}
            self.newItems = views.newlyDownloadedItems
            for item in self.newItems:
                self.new_on_add(item, item.id)
            self.newItems.addAddCallback(self.new_on_add)
            self.newItems.addRemoveCallback(self.new_on_remove)

    def update_max_downloads(self):
        if self.is_auto:
            newmax = config.get(prefs.DOWNLOADS_TARGET)
        else:
            newmax = config.get(prefs.MAX_MANUAL_DOWNLOADS)
        if newmax != self.MAX:
            self.MAX = newmax
            self.startDownloads()

    def start_downloads_idle(self):
        if self.paused:
            return
        last_count = 0
        while self.running_count < self.MAX and self.pending_count > 0 and self.pending_count != last_count:
            last_count = self.pending_count
            sorted = SortedList(pending_sort)
            for feed in views.feeds:
                if self.is_auto:
                    max_new = feed.get_max_new()
                    if max_new != "unlimited" and max_new <= self.feed_new_count.get(feed, 0) + self.feed_running_count.get(feed, 0):
                        continue
                if self.feed_pending_count.get(feed, 0) <= 0:
                    continue
                sorted.append((feed, self.feed_running_count.get(feed, 0), self.feed_time.get(feed, datetime.min)))
            for feed, count, time in sorted:
                if self.is_auto:
                    feed.startAutoDownload()
                else:
                    feed.startManualDownload()
                self.feed_time[feed] = datetime.now()
                if self.running_count >= self.MAX:
                    break
        self.dc = None

    def startDownloads(self):
        if self.dc or self.paused:
            return
        self.dc = eventloop.addIdle(self.start_downloads_idle, "Start Downloads")

    def pending_on_add(self, obj, id):
        feed = obj.getFeed()
        self.pending_count = self.pending_count + 1
        self.feed_pending_count[feed] = self.feed_pending_count.get(feed, 0) + 1
        self.startDownloads()
    
    def pending_on_remove(self, obj, id):
        feed = obj.getFeed()
        self.pending_count = self.pending_count - 1
        self.feed_pending_count[feed] = self.feed_pending_count.get(feed, 0) - 1
    
    def running_on_add(self, obj, id):
        feed = obj.getFeed()
        self.running_count = self.running_count + 1
        self.feed_running_count[feed] = self.feed_running_count.get(feed, 0) + 1
    
    def running_on_remove(self, obj, id):
        feed = obj.getFeed()
        self.running_count = self.running_count - 1
        self.feed_running_count[feed] = self.feed_running_count.get(feed, 0) - 1
        self.startDownloads()
    
    def new_on_add(self, obj, id):
        feed = obj.getFeed()
        self.new_count = self.new_count + 1
        self.feed_new_count[feed] = self.feed_new_count.get(feed, 0) + 1
    
    def new_on_remove(self, obj, id):
        feed = obj.getFeed()
        self.new_count = self.new_count - 1
        self.feed_new_count[feed] = self.feed_new_count.get(feed, 0) - 1
        self.startDownloads()

    def pause(self):
        if self.dc:
            self.dc.cancel()
            self.dc = None
        self.paused = True

    def resume(self):
        if self.paused:
            self.paused = False
            eventloop.addTimeout(5, self.startDownloads, "delayed start downloads")

# These are both Downloader instances.
manual_downloader = None
auto_downloader = None

def start_downloader():
    global manual_downloader
    global auto_downloader
    manual_downloader = Downloader(False)
    auto_downloader = Downloader(True)

# FIXME - doesn't seem to be used
# def pauseDownloader():
#     manual_downloader.pause()
#     auto_downloader.pause()

def resume_downloader():
    manual_downloader.resume()
    auto_downloader.resume()

def _update_prefs(key, value):
    if key == prefs.DOWNLOADS_TARGET.key:
        auto_downloader.update_max_downloads()
    elif key == prefs.MAX_MANUAL_DOWNLOADS.key:
        manual_downloader.update_max_downloads()

config.add_change_callback(_update_prefs)
