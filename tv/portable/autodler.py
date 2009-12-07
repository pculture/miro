# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

from miro import item as itemmod
from miro import feed as feedmod
from miro import config
from miro import prefs
from miro import eventloop
from datetime import datetime

def pending_sort(a, b):
    return cmp((a[1], a[2]), (b[1], b[2]))

class Downloader:
    def __init__(self, is_auto):
        self.dc = None
        self.paused = False
        self.running_count = 0
        self.pending_count = 0
        self.feed_pending_count = {}
        self.feed_running_count = {}
        self.feed_time = {}
        self.is_auto = is_auto
        if is_auto:
            pending_items = itemmod.Item.auto_pending_view()
            running_items = itemmod.Item.auto_downloads_view()
            self.MAX = config.get(prefs.DOWNLOADS_TARGET)
        else:
            pending_items = itemmod.Item.manual_pending_view()
            running_items = itemmod.Item.manual_downloads_view()
            self.MAX = config.get(prefs.MAX_MANUAL_DOWNLOADS)

        for item in pending_items:
            self.pending_on_add(None, item)
        for item in running_items:
            self.running_on_add(None, item)

        self.pending_items_tracker = pending_items.make_tracker()
        self.pending_items_tracker.connect('added', self.pending_on_add)
        self.pending_items_tracker.connect('removed', self.pending_on_remove)

        self.running_items_tracker = running_items.make_tracker()
        self.running_items_tracker.connect('added', self.running_on_add)
        self.running_items_tracker.connect('removed', self.running_on_remove)

        if is_auto:
            self.new_count = 0
            self.feed_new_count = {}
            new_items = itemmod.Item.unwatched_downloaded_items()
            for item in new_items:
                self.new_on_add(None, item)
            self.new_items_tracker = new_items.make_tracker()
            self.new_items_tracker.connect('added', self.new_on_add)
            self.new_items_tracker.connect('removed', self.new_on_remove)

    def update_max_downloads(self):
        if self.is_auto:
            newmax = config.get(prefs.DOWNLOADS_TARGET)
        else:
            newmax = config.get(prefs.MAX_MANUAL_DOWNLOADS)
        if newmax != self.MAX:
            self.MAX = newmax
            self.start_downloads()

    def start_downloads_idle(self):
        if self.paused:
            return
        last_count = 0
        while self.running_count < self.MAX and self.pending_count > 0 and self.pending_count != last_count:
            last_count = self.pending_count
            candidate_feeds = []
            for feed in feedmod.Feed.make_view():
                key = self._key_for_feed(feed)
                if self.is_auto:
                    max_new = feed.get_max_new()
                    if max_new != "unlimited":
                        count = (self.feed_new_count.get(feed, 0) +
                                self.feed_running_count.get(key, 0) +
                                feed.num_unwatched())
                        if count >= max_new:
                            continue
                if self.feed_pending_count.get(key, 0) <= 0:
                    continue
                candidate_feeds.append((feed, self.feed_running_count.get(key, 0), self.feed_time.get(feed, datetime.min)))
            candidate_feeds.sort(pending_sort)

            for feed, count, time in candidate_feeds:
                if self.is_auto:
                    feed.startAutoDownload()
                else:
                    feed.startManualDownload()
                self.feed_time[feed] = datetime.now()
                if self.running_count >= self.MAX:
                    break
        self.dc = None

    def start_downloads(self):
        if self.dc or self.paused:
            return
        self.dc = eventloop.addIdle(self.start_downloads_idle, "Start Downloads")

    def _key_for_feed(self, feed):
        """Get the key to use for feed_pending_count and feed_running_count
        dicts.  Normally this is the feed URL, but the search downloads feed
        gets combined with the search feed (ss #11778)
        """
        if feed.origURL == u'dtv:searchDownloads':
            return u"dtv:search"
        else:
            return feed.origURL

    def pending_on_add(self, tracker, obj):
        feed = obj.get_feed()
        key = self._key_for_feed(feed)
        self.pending_count = self.pending_count + 1
        self.feed_pending_count[key] = self.feed_pending_count.get(key, 0) + 1
        self.start_downloads()
    
    def pending_on_remove(self, tracker, obj):
        feed = obj.get_feed()
        key = self._key_for_feed(feed)
        self.pending_count = self.pending_count - 1
        self.feed_pending_count[key] = self.feed_pending_count.get(key, 0) - 1
    
    def running_on_add(self, tracker, obj):
        feed = obj.get_feed()
        key = self._key_for_feed(feed)
        self.running_count = self.running_count + 1
        self.feed_running_count[key] = self.feed_running_count.get(key, 0) + 1
    
    def running_on_remove(self, tracker, obj):
        feed = obj.get_feed()
        key = self._key_for_feed(feed)
        self.running_count = self.running_count - 1
        self.feed_running_count[key] = self.feed_running_count.get(key, 0) - 1
        self.start_downloads()
    
    def new_on_add(self, tracker, obj):
        feed = obj.get_feed()
        key = self._key_for_feed(feed)
        self.new_count = self.new_count + 1
        self.feed_new_count[key] = self.feed_new_count.get(key, 0) + 1
    
    def new_on_remove(self, tracker, obj):
        feed = obj.get_feed()
        key = self._key_for_feed(feed)
        self.new_count = self.new_count - 1
        self.feed_new_count[key] = self.feed_new_count.get(key, 0) - 1
        self.start_downloads()

    def pause(self):
        if self.dc:
            self.dc.cancel()
            self.dc = None
        self.paused = True

    def resume(self):
        if self.paused:
            self.paused = False
            eventloop.addTimeout(5, self.start_downloads, "delayed start downloads")

# these are both Downloader instances
MANUAL_DOWNLOADER = None
AUTO_DOWNLOADER = None

def start_downloader():
    global MANUAL_DOWNLOADER
    global AUTO_DOWNLOADER
    MANUAL_DOWNLOADER = Downloader(False)
    AUTO_DOWNLOADER = Downloader(True)

def _update_prefs(key, value):
    if key == prefs.DOWNLOADS_TARGET.key:
        AUTO_DOWNLOADER.update_max_downloads()
    elif key == prefs.MAX_MANUAL_DOWNLOADS.key:
        MANUAL_DOWNLOADER.update_max_downloads()

config.add_change_callback(_update_prefs)
