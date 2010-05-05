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

"""``miro.feed`` -- Holds ``Feed`` class and related things.

FIXME - talk about Feed architecture here
"""

from HTMLParser import HTMLParser, HTMLParseError
from cStringIO import StringIO
from datetime import datetime, timedelta
from miro.gtcache import gettext as _
from miro.feedparser import FeedParserDict
from urlparse import urljoin
from miro.xhtmltools import (unescape, xhtmlify, fix_xml_header,
                             fix_html_header, urlencode, urldecode)
import os
import re
import xml

from miro.database import DDBObject, ObjectNotFoundError
from miro.httpclient import grab_url
from miro import app
from miro import autodler
from miro import config
from miro import iconcache
from miro import databaselog
from miro import dialogs
from miro import download_utils
from miro import eventloop
from miro import feedupdate
from miro import flashscraper
from miro import models
from miro import prefs
from miro.plat import resources
from miro import downloader
from miro.util import (returns_unicode, returns_filename, unicodify, check_u,
                       check_f, quote_unicode_url, escape, to_uni,
                       is_url, stringify)
from miro import fileutil
from miro.plat.utils import filenameToUnicode, make_url_safe, unmake_url_safe
from miro import filetypes
from miro.item import FeedParserValues
from miro import searchengines
import logging
from miro.clock import clock

WHITESPACE_PATTERN = re.compile(r"^[ \t\r\n]*$")

DEFAULT_FEED_ICON = "images/feedicon.png"
DEFAULT_FEED_ICON_TABLIST = "images/icon-rss.png"

@returns_unicode
def default_feed_icon_url():
    return resources.url(DEFAULT_FEED_ICON)

def default_feed_icon_path():
    return resources.path(DEFAULT_FEED_ICON)

def default_tablist_feed_icon_path():
    return resources.path(DEFAULT_FEED_ICON_TABLIST)

# Notes on character set encoding of feeds:
#
# The parsing libraries built into Python mostly use byte strings
# instead of unicode strings.  However, sometimes they get "smart" and
# try to convert the byte stream to a unicode stream automatically.
#
# What does what when isn't clearly documented
#
# We use the function to_uni() to fix those smart conversions
#
# If you run into Unicode crashes, adding that function in the
# appropriate place should fix it.

# Universal Feed Parser http://feedparser.org/
# Licensed under Python license
from miro import feedparser

def add_feed_from_file(fn):
    """Adds a new feed using USM
    """
    check_f(fn)
    d = feedparser.parse(fn)
    if d.feed.has_key('links'):
        for link in d.feed['links']:
            if link['rel'] == 'start' or link['rel'] == 'self':
                Feed(link['href'])
                return
    if d.feed.has_key('link'):
        add_feed_from_web_page(d.feed.link)

def add_feed_from_web_page(url):
    """Adds a new feed based on a link tag in a web page
    """
    check_u(url)
    def callback(info):
        url = HTMLFeedURLParser().get_link(info['updated-url'], info['body'])
        if url:
            Feed(url)
    def errback(error):
        logging.warning ("unhandled error in add_feed_from_web_page: %s", error)
    grab_url(url, callback, errback)

FILE_MATCH_RE = re.compile(r"^file://.")
SEARCH_URL_MATCH_RE = re.compile('^dtv:savedsearch/(.*)\?q=(.*)')

def validate_feed_url(url):
    """URL validitation and normalization
    """
    check_u(url)
    if is_url(url):
        return True
    if FILE_MATCH_RE.match(url) is not None:
        return True
    return False

def normalize_feed_url(url):
    check_u(url)
    # Valid URL are returned as-is
    if validate_feed_url(url):
        return url

    originalURL = url
    url = url.strip()

    # Check valid schemes with invalid separator
    match = re.match(r"^(http|https):/*(.*)$", url)
    if match is not None:
        url = "%s://%s" % match.group(1, 2)

    # Replace invalid schemes by http
    match = re.match(r"^(([A-Za-z]*):/*)*(.*)$", url)
    if match and match.group(2) in ['feed', 'podcast', 'fireant', None]:
        url = "http://%s" % match.group(3)
    elif match and match.group(1) == 'feeds':
        url = "https://%s" % match.group(3)

    # Make sure there is a leading / character in the path
    match = re.match(r"^(http|https)://[^/]*$", url)
    if match is not None:
        url = url + "/"

    url = quote_unicode_url(url)

    if not validate_feed_url(url):
        logging.info ("unable to normalize URL %s", originalURL)
        return originalURL
    else:
        return url

def make_search_url(engine, term):
    """Create a URL for a search feed.
    """
    return u'dtv:savedsearch/%s?q=%s' % (engine, term)

def _config_change(key, value):
    """Handle configuration changes so we can update feed update frequencies
    """
    if key is prefs.CHECK_CHANNELS_EVERY_X_MN.key:
        for feed in Feed.make_view():
            update_freq = 0
            try:
                update_freq = feed.parsed["feed"]["ttl"]
            except (AttributeError, KeyError):
                pass
            feed.set_update_frequency(update_freq)

config.add_change_callback(_config_change)

# Wait X seconds before updating the feeds at startup
INITIAL_FEED_UPDATE_DELAY = 5.0

class FeedImpl(DDBObject):
    """Actual implementation of a basic feed.
    """
    def setup_new(self, url, ufeed, title=None):
        check_u(url)
        if title:
            check_u(title)
        self.url = url
        self.ufeed = ufeed
        self.ufeed_id = ufeed.id
        self.title = title
        self.created = datetime.now()
        self.updating = False
        self.thumbURL = None
        self.initialUpdate = True
        self.updateFreq = config.get(prefs.CHECK_CHANNELS_EVERY_X_MN)*60

    @classmethod
    def orphaned_view(cls):
        table_name = app.db.table_name(cls)
        return cls.make_view("feed.id is NULL",
                joins={'feed': 'feed.feed_impl_id=%s.id' % table_name})

    def _get_items(self):
        return self.ufeed.items
    items = property(_get_items)

    def on_signal_change(self):
        self.ufeed.signal_change()

    @returns_unicode
    def get_base_href(self):
        """Get a URL to use in the <base> tag for this channel.  This is used
        for relative links in this channel's items.
        """
        return escape(self.url)

    def set_update_frequency(self, frequency):
        """Sets the update frequency (in minutes).
        A frequency of -1 means that auto-update is disabled.
        """
        try:
            frequency = int(frequency)
        except ValueError:
            frequency = -1

        if frequency < 0:
            self.cancel_update_events()
            self.updateFreq = -1
        else:
            new_freq = max(config.get(prefs.CHECK_CHANNELS_EVERY_X_MN), frequency) * 60
            if new_freq != self.updateFreq:
                self.updateFreq = new_freq
                self.schedule_update_events(-1)
        self.ufeed.signal_change()

    def schedule_update_events(self, firstTriggerDelay):
        self.cancel_update_events()
        if firstTriggerDelay >= 0:
            self.scheduler = eventloop.add_timeout(firstTriggerDelay, self.update, "Feed update (%s)" % self.get_title())
        else:
            if self.updateFreq > 0:
                self.scheduler = eventloop.add_timeout(self.updateFreq, self.update, "Feed update (%s)" % self.get_title())

    def cancel_update_events(self):
        if hasattr(self, 'scheduler') and self.scheduler is not None:
            self.scheduler.cancel()
            self.scheduler = None

    def update(self):
        """Subclasses should override this
        """
        self.schedule_update_events(-1)

    def default_thumbnail_path(self):
        """Get the path to our thumbnail when there isn't a downloaded icon"""
        return default_feed_icon_path()

    @returns_unicode
    def get_title(self):
        """Returns the title of the feed
        """
        try:
            title = self.title
            if title is None or WHITESPACE_PATTERN.match(title):
                if self.ufeed.baseTitle is not None:
                    title = self.ufeed.baseTitle
                else:
                    title = self.url
            return title
        except AttributeError:
            return u""

    @returns_unicode
    def get_url(self):
        """Returns the URL of the feed
        """
        return self.url

    @returns_unicode
    def get_base_url(self):
        """Returns the URL of the feed
        """
        try:
            return self.url
        except AttributeError:
            return u""

    @returns_unicode
    def get_link(self):
        """Returns a link to a webpage associated with the feed
        """
        return self.ufeed.get_base_href()

    @returns_unicode
    def get_thumbnail_url(self):
        """Returns the URL of a thumbnail associated with the feed
        """
        return self.thumbURL

    @returns_unicode
    def get_license(self):
        """Returns URL of license assocaited with the feed
        """
        return u""

    def setup_restored(self):
        self.updating = False

    def remove(self):
        self.on_remove()
        DDBObject.remove(self)

    def on_remove(self):
        """Called when the feed uses this FeedImpl is removed from the DB.
        subclasses can perform cleanup here."""
        pass

    def __str__(self):
        return "%s - %s" % (self.__class__.__name__, stringify(self.get_title()))

    def clean_old_items(self):
        """
        Called to remove old items which are no longer in the feed.

        Items that are currently in the feed should always be kept.
        """
        pass

class Feed(DDBObject, iconcache.IconCacheOwnerMixin):
    """This class is a magic class that can become any type of feed it wants

    It works by passing on attributes to the actual feed.
    """
    ICON_CACHE_VITAL = True

    def setup_new(self, url, initiallyAutoDownloadable=None,
                 section=u'video', search_term=None):
        check_u(url)
        if initiallyAutoDownloadable == None:
            mode = config.get(prefs.CHANNEL_AUTO_DEFAULT)
            # note that this is somewhat duplicated in
            # set_auto_download_mode
            if mode == u'all':
                self.getEverything = True
                self.autoDownloadable = True
            elif mode == u'new':
                self.getEverything = False
                self.autoDownloadable = True
            elif mode == u'off':
                self.getEverything = False
                self.autoDownloadable = False
            else:
                raise ValueError("Bad auto-download mode: %s" % mode)

        else:
            self.autoDownloadable = initiallyAutoDownloadable
            self.getEverything = False

        self.section = section
        self.maxNew = 3
        self.maxOldItems = None
        self.expire = u"system"
        self.expireTime = None
        self.fallBehind = -1
        self.last_viewed = datetime.min

        self.baseTitle = None
        self.origURL = url
        self.errorState = False
        self.loading = True
        self._actualFeed = None
        self._set_feed_impl(FeedImpl(url, self))
        self.setup_new_icon_cache()
        self.informOnError = True
        self.folder_id = None
        self.searchTerm = search_term
        self.userTitle = None
        self.visible = True
        self.setup_common()

    def setup_restored(self):
        restored_feeds.append(self)
        self._actualFeed = None
        self.informOnError = False
        self.setup_common()

    def setup_common(self):
        self.create_signal('update-finished')
        self.download = None
        self.wasUpdating = False
        self.inlineSearchTerm = None
        self.calc_item_list()

    def _get_actual_feed(self):
        # first try to load from actualFeed from the DB
        if self._actualFeed is None:
            for klass in (FeedImpl, RSSFeedImpl, SavedSearchFeedImpl,
                    ScraperFeedImpl, SearchFeedImpl, DirectoryFeedImpl,
                    DirectoryWatchFeedImpl, SearchDownloadsFeedImpl,
                    ManualFeedImpl, SingleFeedImpl):
                try:
                    self._actualFeed = klass.get_by_id(self.feed_impl_id)
                    self._actualFeed.ufeed = self
                    break
                except ObjectNotFoundError:
                    pass
        # otherwise, make a new FeedImpl
        if self._actualFeed is None:
            self._set_feed_impl(FeedImpl(self.origURL, self))
            self.signal_change()
        return self._actualFeed

    actualFeed = property(_get_actual_feed)

    @classmethod
    def get_by_url(cls, url):
        return cls.make_view('origURL=?', (url,)).get_singleton()

    @classmethod
    def get_by_url_and_search(cls, url, searchTerm):
        if searchTerm is not None:
            view = cls.make_view('origURL=? AND searchTerm=?',
                    (url, searchTerm))
        else:
            view = cls.make_view('origURL=? AND searchTerm IS NULL', (url,))
        return view.get_singleton()

    @classmethod
    def get_manual_feed(cls):
        return cls.get_by_url('dtv:manualFeed')

    @classmethod
    def get_directory_feed(cls):
        return cls.get_by_url('dtv:directoryfeed')

    @classmethod
    def get_search_feed(cls):
        return cls.get_by_url('dtv:search')

    @classmethod
    def get_search_downloads_feed(cls):
        return cls.get_by_url('dtv:searchDownloads')

    @classmethod
    def folder_view(cls, id):
        return cls.make_view('folder_id=?', (id,))

    @classmethod
    def visible_video_view(cls):
        return cls.make_view("visible AND section='video'")

    @classmethod
    def watched_folder_view(cls):
        return cls.make_view("origURL LIKE 'dtv:directoryfeed:%'")

    @classmethod
    def visible_audio_view(cls):
        return cls.make_view("visible AND section='audio'")

    def on_db_insert(self):
        self.generate_feed(True)

    def in_folder(self):
        return self.folder_id is not None

    def _set_feed_impl(self, feed_impl):
        if self._actualFeed is not None:
            self._actualFeed.remove()
        self._actualFeed = feed_impl
        self.feed_impl_id = feed_impl.id

    def signal_change(self, needs_save=True, needs_signal_folder=False):
        if needs_signal_folder:
            folder = self.get_folder()
            if folder:
                folder.signal_change(needs_save=False)
        DDBObject.signal_change (self, needs_save=needs_save)

    def on_signal_change(self):
        is_updating = bool(self.actualFeed.updating)
        if self.wasUpdating and not is_updating:
            self.emit('update-finished')
        self.wasUpdating = is_updating

    def calc_item_list(self):
        self.items = models.Item.feed_view(self.id)
        self.visible_items = models.Item.visible_feed_view(self.id)
        self.downloaded_items = models.Item.feed_downloaded_view(self.id)
        self.downloading_items = models.Item.feed_downloading_view(self.id)
        self.available_items = models.Item.feed_available_view(self.id)
        self.auto_pending_items = models.Item.feed_auto_pending_view(self.id)
        self.unwatched_items = models.Item.feed_unwatched_view(self.id)

    def update_after_restore(self):
        if self.actualFeed.__class__ == FeedImpl:
            # Our initial FeedImpl was never updated, call
            # generate_feed again
            self.loading = True
            eventloop.add_idle(lambda: self.generate_feed(True), "generate_feed")
        else:
            self.schedule_update_events(INITIAL_FEED_UPDATE_DELAY)

    def clean_old_items(self):
        if self.actualFeed:
            return self.actualFeed.clean_old_items()

    def invalidate_counts(self):
        for cached_count_attr in ('_num_available', '_num_unwatched',
                '_num_downloaded', '_num_downloading'):
            if cached_count_attr in self.__dict__:
                del self.__dict__[cached_count_attr]

    def recalc_counts(self):
        self.invalidate_counts()
        self.signal_change(needs_save=False)
        if self.in_folder():
            self.get_folder().signal_change(needs_save=False)

    def num_downloaded(self):
        """Returns the number of downloaded items in the feed.
        """
        try:
            return self._num_downloaded
        except AttributeError:
            self._num_downloaded = self.downloaded_items.count()
            return self._num_downloaded

    def num_downloading(self):
        """Returns the number of downloading items in the feed.
        """
        try:
            return self._num_downloading
        except AttributeError:
            self._num_downloading = self.downloading_items.count()
            return self._num_downloading

    def num_unwatched(self):
        """Returns string with number of unwatched videos in feed
        """
        try:
            return self._num_unwatched
        except AttributeError:
            self._num_unwatched = self.unwatched_items.count()
            return self._num_unwatched

    def num_available(self):
        """Returns string with number of available videos in feed
        """
        try:
            return self._num_available
        except AttributeError:
            self._num_available = (self.available_items.count() -
                    self.auto_pending_items.count())
            return self._num_available

    def get_viewed(self):
        """Returns true iff this feed has been looked at
        """
        return self.last_viewed != datetime.min

    def mark_as_viewed(self):
        """Sets the last time the feed was viewed to now
        """
        self.last_viewed = datetime.now()
        try:
            del self._num_available
        except AttributeError:
            pass
        if self.in_folder():
            self.get_folder().signal_change()
        self.signal_change()

    def start_manual_download(self):
        next_ = None
        for item in self.items:
            if item.is_pending_manual_download():
                if next_ is None:
                    next_ = item
                elif item.get_pub_date_parsed() > next_.get_pub_date_parsed():
                    next_ = item
        if next_ is not None:
            next_.download(autodl=False)

    def start_auto_download(self):
        next = None
        for item in self.items:
            if item.is_eligible_for_auto_download():
                if next is None:
                    next = item
                elif item.get_pub_date_parsed() > next.get_pub_date_parsed():
                    next = item
        if next is not None:
            next.download(autodl = True)

    def expiring_items(self):
        # items in watched folders never expire
        if self.is_watched_folder():
            return []
        if self.expire == u'never':
            return []
        elif self.expire == u'system':
            expire_after_x_days = config.get(prefs.EXPIRE_AFTER_X_DAYS)
            if expire_after_x_days == -1:
                return []
            delta = timedelta(days=expire_after_x_days)
        else:
            delta = self.expireTime
        return models.Item.feed_expiring_view(self.id, datetime.now() - delta)

    def expire_items(self):
        """Expires items from the feed that are ready to expire.
        """
        for item in self.expiring_items():
            item.expire()

    def signal_items(self):
        for item in self.items:
            item.signal_change(needs_save=False)

    def icon_changed(self):
        """See item.get_thumbnail to figure out which items to send
        signals for.
        """
        self.signal_change(needs_save=False)
        for item in self.items:
            if not (item.icon_cache.isValid() or
                    item.screenshot or
                    item.isContainerItem):
                item.signal_change(needs_save=False)

    ## FIXME - this doesn't get used
    ## def getNewItems(self):
    ##     """Returns the number of new items with the feed
    ##     """
    ##     self.confirm_db_thread()
    ##     count = 0
    ##     for item in self.items:
    ##         try:
    ##             if item.get_state() == u'newly-downloaded':
    ##                 count += 1
    ##         except (SystemExit, KeyboardInterrupt):
    ##             raise
    ##         except:
    ##             pass
    ##     return count


    ## FIXME - this doesn't get used
    ## def setInlineSearchTerm(self, term):
    ##     self.inlineSearchTerm = term

    def get_id(self):
        return DDBObject.get_id(self)

    ## FIXME - this doesn't get used
    ## def hasError(self):
    ##     self.confirm_db_thread()
    ##     return self.errorState

    ## FIXME - this doesn't get used
    ## @returns_unicode
    ## def getOriginalURL(self):
    ##     self.confirm_db_thread()
    ##     return self.origURL

    @returns_unicode
    def get_search_term(self):
        self.confirm_db_thread()
        return self.searchTerm

    ## FIXME - this doesn't get used
    ## @returns_unicode
    ## def getError(self):
    ##     return u"Could not load feed"

    def is_updating(self):
        return self.loading or (self.actualFeed and self.actualFeed.updating)

    ## FIXME - this doesn't get used
    ## def isScraped(self):
    ##     return isinstance(self.actualFeed, ScraperFeedImpl)

    @returns_unicode
    def get_title(self):
        if self.userTitle is not None:
            return self.userTitle

        title = self.actualFeed.get_title()
        if self.searchTerm is not None:
            title = u"%s for '%s'" % (title, self.searchTerm)
        return title

    def has_original_title(self):
        return self.userTitle == None

    def set_title(self, title):
        self.confirm_db_thread()
        self.userTitle = title
        self.signal_change()

    def revert_title(self):
        self.set_title(None)

    ## FIXME - this doesn't get used
    ## @returns_unicode
    ## def setBaseTitle(self, title):
    ##     """Set the baseTitle.
    ##     """
    ##     self.baseTitle = title
    ##     self.signal_change()

    ## FIXME - this doesn't get used
    ## def isVisible(self):
    ##     """Returns true iff feed should be visible
    ##     """
    ##     self.confirm_db_thread()
    ##     return self.visible

    def set_visible(self, visible):
        if self.visible == visible:
            return
        self.visible = visible
        self.signal_change()

    @returns_unicode
    def get_autodownload_mode(self):
        self.confirm_db_thread()
        if self.autoDownloadable:
            if self.getEverything:
                return u'all'
            else:
                return u'new'
        else:
            return u'off'

    def set_auto_download_mode(self, mode):
        # note that this is somewhat duplicated in setup_new
        if mode == u'all':
            self.getEverything = True
            self.autoDownloadable = True
        elif mode == u'new':
            self.getEverything = False
            self.autoDownloadable = True
        elif mode == u'off':
            self.autoDownloadable = False
        else:
            raise ValueError("Bad auto-download mode: %s" % mode)
        self.signal_change()
        self.signal_items()

    ## FIXME - doesn't get used
    ## def getCurrentAutoDownloadableItems(self):
    ##     auto = set()
    ##     for item in self.items:
    ##         if item.is_pending_auto_download():
    ##             auto.add(item)
    ##     return auto

    def set_expiration(self, type_, time_):
        """Sets the expiration attributes. Valid types are u'system',
        u'feed' and u'never'.

        Expiration time is in hour(s).
        """
        self.confirm_db_thread()
        self.expire = type_
        self.expireTime = timedelta(hours=time_)

        if self.expire == u"never":
            for item in self.items:
                if item.is_downloaded():
                    item.save()

        self.signal_change()
        self.signal_items()

    def set_max_new(self, max_new):
        """Sets the maxNew attributes. -1 means unlimited.
        """
        self.confirm_db_thread()
        oldMaxNew = self.maxNew
        self.maxNew = max_new
        self.signal_change()
        if self.maxNew >= oldMaxNew or self.maxNew < 0:
            autodler.AUTO_DOWNLOADER.start_downloads()

    def set_max_old_items(self, maxOldItems):
        self.confirm_db_thread()
        oldMaxOldItems = self.maxOldItems
        if maxOldItems == -1:
            maxOldItems = None
        self.maxOldItems = maxOldItems
        self.signal_change()
        if (maxOldItems is not None and
                (oldMaxOldItems is None or oldMaxOldItems > maxOldItems)):
            # the actual feed updating code takes care of expiring the old
            # items
            self.actualFeed.clean_old_items()

    def update(self):
        self.confirm_db_thread()
        if not self.id_exists():
            return
        if self.loading:
            return
        elif self.errorState:
            self.loading = True
            self.errorState = False
            self.signal_change()
            return self.generate_feed()
        self.actualFeed.update()

    def get_folder(self):
        self.confirm_db_thread()
        if self.in_folder():
            return models.ChannelFolder.get_by_id(self.folder_id)
        else:
            return None

    def set_folder(self, new_folder, update_trackers=True):
        self.confirm_db_thread()
        old_folder = self.get_folder()
        if new_folder is old_folder:
            return
        if new_folder is not None:
            self.folder_id = new_folder.get_id()
        else:
            self.folder_id = None
        self.signal_change()
        if update_trackers:
            models.Item.update_folder_trackers()
        if new_folder:
            new_folder.signal_change(needs_save=False)
        if old_folder:
            old_folder.signal_change(needs_save=False)

    @staticmethod
    def bulk_set_folders(folder_assignments):
        """Set the folders for multiple feeds at once.

        This method is optimized to be a bit faster than calling
        set_folder() for each individual folder.
        """
        for child, folder in folder_assignments:
            child.set_folder(folder, update_trackers=False)
        models.Item.update_folder_trackers()

    def generate_feed(self, removeOnError=False):
        newFeed = None
        if self.origURL == u"dtv:directoryfeed":
            newFeed = DirectoryFeedImpl(self)
            self.visible = False
        elif (self.origURL.startswith(u"dtv:directoryfeed:")):
            url = self.origURL[len(u"dtv:directoryfeed:"):]
            dir_ = unmake_url_safe(url)
            newFeed = DirectoryWatchFeedImpl(self, dir_)
        elif self.origURL == u"dtv:search":
            newFeed = SearchFeedImpl(self)
            self.visible = False
        elif self.origURL == u"dtv:searchDownloads":
            newFeed = SearchDownloadsFeedImpl(self)
            self.visible = False
        elif self.origURL == u"dtv:manualFeed":
            newFeed = ManualFeedImpl(self)
            self.visible = False
        elif self.origURL == u"dtv:singleFeed":
            newFeed = SingleFeedImpl(self)
            self.visible = False
        elif SEARCH_URL_MATCH_RE.match(self.origURL):
            newFeed = SavedSearchFeedImpl(self.origURL, self)
        else:
            self.download = grab_url(self.origURL,
                    lambda info: self._generate_feed_callback(info, removeOnError),
                    lambda error: self._generate_feed_errback(error, removeOnError),
                    default_mime_type=u'application/rss+xml')
            logging.debug ("added async callback to create feed %s", self.origURL)
        if newFeed:
            self.finish_generate_feed(newFeed)

    def is_watched_folder(self):
        return self.origURL.startswith("dtv:directoryfeed:")

    def _handle_feed_loading_error(self, errorDescription):
        self.download = None
        self.errorState = True
        self.loading = False
        self.signal_change()
        if self.informOnError:
            title = _('Error loading feed')
            description = _(
                "Couldn't load the feed at %(url)s (%(errordescription)s)."
            ) % { "url": self.url, "errordescription": errorDescription }
            description += "\n\n"
            description += _("Would you like to keep the feed?")
            d = dialogs.ChoiceDialog(title, description, dialogs.BUTTON_KEEP,
                    dialogs.BUTTON_DELETE)
            def callback(dialog):
                if dialog.choice == dialogs.BUTTON_DELETE and self.id_exists():
                    self.remove()
            d.run(callback)
            self.informOnError = False
        delay = config.get(prefs.CHECK_CHANNELS_EVERY_X_MN)
        eventloop.add_timeout(delay, self.update, "update failed feed")

    def _generate_feed_errback(self, error, removeOnError):
        if not self.id_exists():
            return
        logging.info("Warning couldn't load feed at %s (%s)",
                     self.origURL, error)
        self._handle_feed_loading_error(error.getFriendlyDescription())

    def _generate_feed_callback(self, info, removeOnError):
        """This is called by grab_url to generate a feed based on
        the type of data found at the given URL
        """
        # FIXME: This probably should be split up a bit. The logic is
        #        a bit daunting

        # Note that all of the raw XML and HTML in this function is in
        # byte string format

        if not self.id_exists():
            return
        if info['updated-url'] != self.origURL and \
                not self.origURL.startswith('dtv:'): # we got redirected
            f = lookup_feed(info['updated-url'], self.searchTerm)
            if f is not None: # already have this feed, so delete us
                self.remove()
                return
        self.download = None
        modified = unicodify(info.get('last-modified'))
        etag = unicodify(info.get('etag'))
        contentType = unicodify(info.get('content-type', u'text/html'))

        # Some smarty pants serve RSS feeds with a text/html content-type...
        # So let's do some really simple sniffing first.
        apparentlyRSS = filetypes.is_maybe_rss(info['body'])

        # Definitely an HTML feed
        if (((contentType.startswith(u'text/html') or
              contentType.startswith(u'application/xhtml+xml'))
             and not apparentlyRSS)):
            #print "Scraping HTML"
            html = info['body']
            if info.has_key('charset'):
                html = fix_html_header(html, info['charset'])
                charset = unicodify(info['charset'])
            else:
                charset = None
            self.ask_for_scrape(info, html, charset)
        #It's some sort of feed we don't know how to scrape
        elif (contentType.startswith(u'application/rdf+xml')
              or contentType.startswith(u'application/atom+xml')):
            #print "ATOM or RDF"
            html = info['body']
            if info.has_key('charset'):
                xmldata = fix_xml_header(html, info['charset'])
            else:
                xmldata = html
            self.finish_generate_feed(RSSFeedImpl(unicodify(info['updated-url']),
                initialHTML=xmldata,etag=etag,modified=modified, ufeed=self))
            # If it's not HTML, we can't be sure what it is.
            #
            # If we get generic XML, it's probably RSS, but it still could
            # be XHTML.
            #
            # application/rss+xml links are definitely feeds. However, they
            # might be pre-enclosure RSS, so we still have to download them
            # and parse them before we can deal with them correctly.
        elif (apparentlyRSS or
              contentType.startswith(u'application/rss+xml') or
              contentType.startswith(u'application/podcast+xml') or
              contentType.startswith(u'text/xml') or
              contentType.startswith(u'application/xml') or
              (contentType.startswith(u'text/plain') and
               (unicodify(info['updated-url']).endswith(u'.xml') or
                unicodify(info['updated-url']).endswith(u'.rss')))):
            #print " It's doesn't look like HTML..."
            html = info["body"]
            if info.has_key('charset'):
                xmldata = fix_xml_header(html, info['charset'])
                html = fix_html_header(html, info['charset'])
                charset = unicodify(info['charset'])
            else:
                xmldata = html
                charset = None
            # FIXME html and xmldata can be non-unicode at this point
            parser = xml.sax.make_parser()
            parser.setFeature(xml.sax.handler.feature_namespaces, 1)
            parser.setFeature(xml.sax.handler.feature_external_ges, 0)
            handler = RSSLinkGrabber(unicodify(info['redirected-url']), charset)
            parser.setContentHandler(handler)
            parser.setErrorHandler(handler)
            try:
                parser.parse(StringIO(xmldata))
            except UnicodeDecodeError:
                logging.exception ("Unicode issue parsing... %s",
                                   xmldata[0:300])
                self.finish_generate_feed(None)
                if removeOnError:
                    self.remove()
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                #it doesn't parse as RSS, so it must be HTML
                #print " Nevermind! it's HTML"
                self.ask_for_scrape(info, html, charset)
            else:
                #print " It's RSS with enclosures"
                self.finish_generate_feed(RSSFeedImpl(
                    unicodify(info['updated-url']),
                    initialHTML=xmldata, etag=etag, modified=modified,
                    ufeed=self))
        else:
            self._handle_feed_loading_error(_("Bad content-type"))

    def finish_generate_feed(self, feedImpl):
        self.confirm_db_thread()
        self.loading = False
        if feedImpl is not None:
            self._set_feed_impl(feedImpl)
            self.errorState = False
        else:
            self.errorState = True
        self.signal_change()

    def ask_for_scrape(self, info, initialHTML, charset):
        title = _("Channel is not compatible with %(appname)s",
                  {"appname": config.get(prefs.SHORT_APP_NAME)})
        description = _(
            "This channel is not compatible with %(appname)s "
            "but we'll try our best to grab the files.  It may take extra time "
            "to list the videos, and descriptions may look funny.\n"
            "\n"
            "Please contact the publishers of %(url)s and ask if they can supply a "
            "feed in a format that will work with %(appname)s.\n"
            "\n"
            "Do you want to try to load this channel anyway?",
            {"url": info["updated-url"],
             "appname": config.get(prefs.SHORT_APP_NAME)}
        )
        dialog = dialogs.ChoiceDialog(title, description, dialogs.BUTTON_YES,
                dialogs.BUTTON_NO)

        def callback(dialog):
            if not self.id_exists():
                return
            if dialog.choice == dialogs.BUTTON_YES:
                uinfo = unicodify(info)
                impl = ScraperFeedImpl(uinfo['updated-url'],
                    initialHTML=initialHTML, etag=uinfo.get('etag'),
                    modified=uinfo.get('modified'), charset=charset,
                    ufeed=self)
                self.finish_generate_feed(impl)
            else:
                self.remove()
        dialog.run(callback)

    def get_actual_feed(self):
        return self.actualFeed

    # Many attributes come from whatever FeedImpl subclass we're using.
    def attr_from_feed_impl(name):
        def getter(self):
            return getattr(self.actualFeed, name)
        return property(getter)

    for name in ( 'set_update_frequency', 'schedule_update_events',
            'cancel_update_events',
            'get_url', 'get_base_url',
            'get_base_href', 'get_link',
            'get_thumbnail_url', 'get_license', 'url', 'title', 'created',
            'thumbURL', 'dir', 'preserve_downloads', 'lookup', 'reset',
            'engine', 'query',
            ):
        locals()[name] = attr_from_feed_impl(name)

    @returns_unicode
    def get_expiration_type(self):
        """Returns "feed," "system," or "never"
        """
        self.confirm_db_thread()
        return self.expire

    ## FIXME - doesn't get used
    ## def getMaxFallBehind(self):
    ##     """Returns "unlimited" or the maximum number of items this
    ##     feed can fall behind
    ##     """
    ##     self.confirm_db_thread()
    ##     if self.fallBehind < 0:
    ##         return u"unlimited"
    ##     else:
    ##         return self.fallBehind

    def get_max_new(self):
        """Returns "unlimited" or the maximum number of items this
        feed wants
        """
        self.confirm_db_thread()
        if self.maxNew < 0:
            return u"unlimited"
        else:
            return self.maxNew

    def get_max_old_items(self):
        """Returns the number of items to remember past the current
        contents of the feed.  If self.maxOldItems is None, then this
        returns "system" indicating that the caller should look up the
        default in prefs.MAX_OLD_ITEMS_DEFAULT.
        """
        self.confirm_db_thread()
        if self.maxOldItems is None:
            return u"system"

        return self.maxOldItems

    def get_expiration_time(self):
        """Returns the total absolute expiration time in hours.
        WARNING: 'system' and 'never' expiration types return 0
        """
        self.confirm_db_thread()
        expireAfterSetting = config.get(prefs.EXPIRE_AFTER_X_DAYS)
        if ((self.expireTime is None or self.expire == 'never'
             or (self.expire == 'system' and expireAfterSetting <= 0))):
            return 0
        else:
            return (self.expireTime.days * 24 +
                    self.expireTime.seconds / 3600)

    ## FIXME - not used
    ## def getExpireDays(self):
    ##     """Returns the number of days until a video expires
    ##     """
    ##     self.confirm_db_thread()
    ##     try:
    ##         return self.expireTime.days
    ##     except (SystemExit, KeyboardInterrupt):
    ##         raise
    ##     except:
    ##         return timedelta(days=config.get(prefs.EXPIRE_AFTER_X_DAYS)).days

    ## def getExpireHours(self):
    ##     """Returns the number of hours until a video expires
    ##     """
    ##     self.confirm_db_thread()
    ##     try:
    ##         return int(self.expireTime.seconds/3600)
    ##     except (SystemExit, KeyboardInterrupt):
    ##         raise
    ##     except:
    ##         return int(timedelta(days=config.get(prefs.EXPIRE_AFTER_X_DAYS)).seconds/3600)

    ## def getExpires(self):
    ##     expireAfterSetting = config.get(prefs.EXPIRE_AFTER_X_DAYS)
    ##     return (self.expireTime is None or self.expire == 'never' or
    ##             (self.expire == 'system' and expireAfterSetting <= 0))

    def is_autodownloadable(self):
        """Returns true iff item is autodownloadable
        """
        self.confirm_db_thread()
        return self.autoDownloadable

    ## FIXME - not used
    ## def autoDownloadStatus(self):
    ##     status = self.is_autodownloadable()
    ##     if status:
    ##         return u"ON"
    ##     else:
    ##         return u"OFF"

    def remove(self, move_items_to=None):
        """Remove the feed.

        If move_items_to is None (the default), the items in this feed
        will be removed too.  If move_items_to is given, the items in
        this feed will be moved to that feed.
        """
        self.confirm_db_thread()

        if isinstance(self.actualFeed, DirectoryWatchFeedImpl):
            move_items_to = None
        self.cancel_update_events()
        if self.download is not None:
            self.download.cancel()
            self.download = None
        to_remove = []
        for item in self.items:
            if move_items_to is not None and item.is_downloaded():
                item.setFeed(move_items_to.get_id())
            else:
                to_remove.append(item)
        app.bulk_sql_manager.start()
        try:
            for item in to_remove:
                item.remove()
        finally:
            app.bulk_sql_manager.finish()
        self.remove_icon_cache()
        DDBObject.remove(self)
        self.actualFeed.remove()

    def thumbnail_valid(self):
        return self.icon_cache and self.icon_cache.isValid()

    ## FIXME - this is only called in commented out functions 
    ## def calc_thumbnail(self):
    ##  if self.thumbnail_valid():
    ##      return fileutil.expand_filename(self.icon_cache.get_filename())
    ##  else:
    ##      return default_feed_icon_path()

    def calc_tablist_thumbnail(self):
        if self.thumbnail_valid():
            return fileutil.expand_filename(self.icon_cache.get_filename())
        else:
            return default_tablist_feed_icon_path()

    ## FIXME - it looks like this never gets called
    ## @returns_unicode
    ## def get_thumbnail(self):
    ##     self.confirm_db_thread()
    ##     return resources.absoluteUrl(self.calc_thumbnail())

    @returns_filename
    def get_thumbnail_path(self):
        self.confirm_db_thread()
        if self.thumbnail_valid():
            return fileutil.expand_filename(self.icon_cache.get_filename())
        else:
            return self.actualFeed.default_thumbnail_path()

    ## FIXME - it looks like these never get called
    ## @returns_unicode
    ## def getTablistThumbnail(self):
    ##     self.confirm_db_thread()
    ##     return resources.absoluteUrl(self.calc_tablist_thumbnail())

    ## @returns_filename
    ## def getTablistThumbnailPath(self):
    ##     self.confirm_db_thread()
    ##     return resources.path(self.calc_tablist_thumbnail())

    def has_downloaded_items(self):
        return self.num_downloaded() > 0

    def has_downloading_items(self):
        return self.num_downloading() > 0

    ## FIXME - this never gets called
    ## def updateIcons(self):
    ##     iconcache.iconCacheUpdater.clear_vital()
    ##     for item in self.items:
    ##         item.icon_cache.request_update(True)
    ##     for feed in Feed.make_view():
    ##         feed.icon_cache.request_update(True)

    def __str__(self):
        return "Feed - %s" % stringify(self.get_title())

class ThrottledUpdateFeedImpl(FeedImpl):
    """Feed Impl that uses the feedupdate module to schedule it's
    updates.  Only a limited number of ThrottledUpdateFeedImpl objects
    will be updating at any given time.
    """

    def schedule_update_events(self, firstTriggerDelay):
        feedupdate.cancel_update(self.ufeed)
        if firstTriggerDelay >= 0:
            feedupdate.schedule_update(firstTriggerDelay, self.ufeed,
                    self.update)
        else:
            if self.updateFreq > 0:
                feedupdate.schedule_update(self.updateFreq, self.ufeed,
                        self.update)

class RSSFeedImplBase(ThrottledUpdateFeedImpl):
    """
    Base class from which RSSFeedImpl and SavedSearchFeedImpl derive.
    """

    def setup_new(self, url, ufeed, title):
        FeedImpl.setup_new(self, url, ufeed, title)
        self.schedule_update_events(0)

    def _handle_new_entry(self, entry, fp_values, channel_title):
        """Handle getting a new entry from a feed."""
        enclosure = fp_values.first_video_enclosure
        if ((self.url.startswith('file://') and enclosure
             and enclosure['url'].startswith('file://'))):
            path = download_utils.get_file_url_path(enclosure['url'])
            item = models.FileItem(path, fp_values=fp_values,
                    feed_id=self.ufeed.id, channel_title=channel_title)
        else:
            item = models.Item(fp_values, feed_id=self.ufeed.id,
                    eligibleForAutoDownload=not self.initialUpdate,
                    channel_title=channel_title)
            if not item.matches_search(self.ufeed.searchTerm):
                item.remove()

    def remember_old_items(self):
        self.old_items = set(self.items)

    def create_items_for_parsed(self, parsed):
        """Update the feed using parsed XML passed in"""
        app.bulk_sql_manager.start()
        try:
            self._create_items_for_parsed(parsed)
        finally:
            app.bulk_sql_manager.finish()

    def _create_items_for_parsed(self, parsed):
        # This is a HACK for Yahoo! search which doesn't provide
        # enclosures
        for entry in parsed['entries']:
            if 'enclosures' not in entry:
                try:
                    url = entry['link']
                except KeyError:
                    continue
                mimetype = filetypes.guess_mime_type(url)
                if mimetype is not None:
                    entry['enclosures'] = [{'url': to_uni(url),
                                            'type': to_uni(mimetype)}]
                elif flashscraper.is_maybe_flashscrapable(url):
                    entry['enclosures'] = [{'url': to_uni(url),
                                            'type': to_uni("video/flv")}]
                else:
                    logging.info('unknown url type %s, not generating enclosure' % url)

        channelTitle = None
        try:
            channelTitle = parsed["feed"]["title"]
        except KeyError:
            try:
                channelTitle = parsed["channel"]["title"]
            except KeyError:
                pass

        if channelTitle != None and self._allow_feed_to_override_title():
            self.title = channelTitle
        if (parsed.feed.has_key('image') and
                parsed.feed.image.has_key('url') and
                self._allow_feed_to_override_thumbnail()):
            self.thumbURL = parsed.feed.image.url
            self.ufeed.icon_cache.request_update(is_vital=True)

        items_byid = {}
        items_byURLTitle = {}
        items_nokey = []
        for item in self.items:
            try:
                items_byid[item.get_rss_id()] = item
            except KeyError:
                items_nokey.append(item)
            by_url_title_key = (item.url, item.entry_title)
            if by_url_title_key != (None, None):
                items_byURLTitle[by_url_title_key] = item
        for entry in parsed.entries:
            entry = self.add_scraped_thumbnail(entry)
            fp_values = FeedParserValues(entry)
            new = True
            if fp_values.data['rss_id'] is not None:
                id_ = fp_values.data['rss_id']
                if items_byid.has_key(id_):
                    item = items_byid[id_]
                    if not fp_values.compare_to_item(item):
                        item.update_from_feed_parser_values(fp_values)
                    new = False
                    self.old_items.discard(item)
            if new:
                by_url_title_key = (fp_values.data['url'],
                        fp_values.data['entry_title'])
                if by_url_title_key != (None, None):
                    if items_byURLTitle.has_key(by_url_title_key):
                        item = items_byURLTitle[by_url_title_key]
                        if not fp_values.compare_to_item(item):
                            item.update_from_feed_parser_values(fp_values)
                        new = False
                        self.old_items.discard(item)
            if new:
                for item in items_nokey:
                    if fp_values.compare_to_item(item):
                        new = False
                    else:
                        try:
                            if fp_values.compare_to_item_enclosures(item):
                                item.update_from_feed_parser_values(fp_values)
                                new = False
                                self.old_items.discard(item)
                        except (SystemExit, KeyboardInterrupt):
                            raise
                        except:
                            pass
            if new and fp_values.first_video_enclosure is not None:
                self._handle_new_entry(entry, fp_values, channelTitle)

    def _allow_feed_to_override_title(self):
        """Should the RSS feed override the default title?

        Subclasses can override this method to change our behavior when
        parsing feed entries.
        """
        return True

    def _allow_feed_to_override_thumbnail(self):
        """Should the RSS thumbnail override the default thumbnail?

        Subclasses can override this method to change our behavior when
        parsing feed entries.
        """
        return True

    def update_finished(self):
        """
        Called by subclasses to finish the update.
        """
        if self.initialUpdate:
            self.initialUpdate = False
            startfrom = None
            itemToUpdate = None
            for latest in models.Item.latest_in_feed_view(self.ufeed_id):
                latest.eligibleForAutoDownload = True
                latest.signal_change()
            if self.ufeed.is_autodownloadable():
                self.ufeed.mark_as_viewed()
            self.ufeed.signal_change()

        self.ufeed.recalc_counts()
        self.truncate_old_items()
        del self.old_items
        self.signal_change()

    def truncate_old_items(self):
        """Truncate items so that the number of items in this feed doesn't
        exceed self.get_max_old_items()

        Items are only truncated if they don't exist in the feed anymore, and
        if the user hasn't downloaded them.
        """
        limit = self.ufeed.get_max_old_items()
        if limit == u"system":
            limit = config.get(prefs.MAX_OLD_ITEMS_DEFAULT)

        item_count = self.items.count()
        if item_count > config.get(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS):
            truncate = item_count - config.get(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS)
            if truncate > len(self.old_items):
                truncate = 0
            limit = min(limit, truncate)
        extra = len(self.old_items) - limit
        if extra <= 0:
            return

        candidates = []
        for item in self.old_items:
            if item.downloader is None:
                candidates.append((item.creationTime, item))
        candidates.sort()
        for time, item in candidates[:extra]:
            item.remove()

    def add_scraped_thumbnail(self, entry):
        # skip this if the entry already has a thumbnail.
        if entry.has_key('thumbnail'):
            return entry
        if entry.has_key('enclosures'):
            for enc in entry['enclosures']:
                if enc.has_key('thumbnail'):
                    return entry
        return entry

class RSSFeedImpl(RSSFeedImplBase):

    def setup_new(self, url, ufeed, title=None, initialHTML=None, etag=None,
                  modified=None):
        RSSFeedImplBase.setup_new(self, url, ufeed, title)
        self.initialHTML = initialHTML
        self.etag = etag
        self.modified = modified
        self.download = None

    @returns_unicode
    def get_base_href(self):
        try:
            return escape(self.parsed.link)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return FeedImpl.get_base_href(self)

    @returns_unicode
    def get_link(self):
        """Returns a link to a webpage associated with the feed
        """
        self.ufeed.confirm_db_thread()
        try:
            return self.parsed.link
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return u""

    def feedparser_finished(self):
        self.updating = False
        self.schedule_update_events(-1)
        self.update_finished()

    def feedparser_errback(self, e):
        if not self.ufeed.id_exists():
            return
        logging.info("Error updating feed: %s: %s", self.url, e)
        self.feedparser_finished()

    def feedparser_callback(self, parsed):
        self.ufeed.confirm_db_thread()
        if not self.ufeed.id_exists():
            return
        if len(parsed.entries) == len(parsed.feed) == 0:
            logging.warn("Empty feed, not updating: %s", self.url)
            self.feedparser_finished()
            return
        start = clock()
        parsed = self.parsed = unicodify(parsed)
        self.remember_old_items()
        self.create_items_for_parsed(parsed)

        try:
            updateFreq = self.parsed["feed"]["ttl"]
        except KeyError:
            updateFreq = 0
        self.set_update_frequency(updateFreq)

        self.feedparser_finished()
        end = clock()
        if end - start > 1.0:
            logging.timing("feed update for: %s too slow (%.3f secs)",
                           self.url, end - start)

    def call_feedparser(self, html):
        self.ufeed.confirm_db_thread()
        eventloop.call_in_thread(self.feedparser_callback,
                               self.feedparser_errback,
                               feedparser.parse,
                               "Feedparser callback - %s" % self.url, html)

    def update(self):
        """Updates a feed
        """
        self.ufeed.confirm_db_thread()
        if not self.ufeed.id_exists():
            return
        if self.updating:
            return
        else:
            self.updating = True
            self.ufeed.signal_change(needs_save=False)
        if hasattr(self, 'initialHTML') and self.initialHTML is not None:
            html = self.initialHTML
            self.initialHTML = None
            self.call_feedparser(html)
        else:
            try:
                etag = self.etag
            except AttributeError:
                etag = None
            try:
                modified = self.modified
            except AttributeError:
                modified = None
            logging.info("updating %s", self.url)
            self.download = grab_url(self.url, self._update_callback,
                    self._update_errback, etag=etag, modified=modified,
                                    default_mime_type=u'application/rss+xml')

    def _update_errback(self, error):
        if not self.ufeed.id_exists():
            return
        logging.warn("WARNING: error in Feed.update for %s -- %s", 
            self.ufeed, stringify(error))
        self.schedule_update_events(-1)
        self.updating = False
        self.ufeed.signal_change(needs_save=False)

    def _update_callback(self, info):
        if not self.ufeed.id_exists():
            return
        if info.get('status') == 304:
            self.schedule_update_events(-1)
            self.updating = False
            self.ufeed.signal_change()
            return
        html = info['body']
        if info.has_key('charset'):
            html = fix_xml_header(html, info['charset'])

        # FIXME HTML can be non-unicode here --NN
        self.url = unicodify(info['updated-url'])
        if info.has_key('etag'):
            self.etag = unicodify(info['etag'])
        else:
            self.etag = None
        if info.has_key('last-modified'):
            self.modified = unicodify(info['last-modified'])
        else:
            self.modified = None
        self.call_feedparser (html)

    @returns_unicode
    def get_license(self):
        """Returns the URL of the license associated with the feed
        """
        try:
            return self.parsed["feed"]["license"]
        except (AttributeError, KeyError):
            pass
        return u""

    def on_remove(self):
        if self.download is not None:
            self.download.cancel()
            self.download = None

    def setup_restored(self):
        """Called by pickle during deserialization
        """
        FeedImpl.setup_restored(self)
        self.download = None

    def clean_old_items(self):
        self.modified = None
        self.etag = None
        self.update()

class RSSMultiFeedBase(RSSFeedImplBase):
    def setup_new(self, url, ufeed, title):
        RSSFeedImplBase.setup_new(self, url, ufeed, title)
        self.etag = {}
        self.modified = {}
        self.download_dc = {}
        self.updating = 0
        self.urls = self.calc_urls()

    def setup_restored(self):
        """Called by pickle during deserialization
        """
        RSSFeedImplBase.setup_restored(self)
        self.download_dc = {}
        self.updating = 0
        self.urls = self.calc_urls()

    def calc_urls(self):
        """Calculate the list of URLs to parse.

        Subclasses must define this method.
        """
        raise NotImplementedError()

    def check_update_finished(self):
        if self.updating == 0:
            self.update_finished()
            self.schedule_update_events(-1)

    def _allow_feed_to_override_title(self):
        return False

    def feedparser_finished(self, url, needs_save=False):
        if not self.ufeed.id_exists():
            return
        self.updating -= 1
        self.check_update_finished()
        del self.download_dc[url]

    def feedparser_errback(self, e, url):
        if not self.ufeed.id_exists() or url not in self.download_dc:
            return
        if e:
            logging.info("Error updating feed: %s (%s): %s", self.url, url, e)
        else:
            logging.info("Error updating feed: %s (%s)", self.url, url)
        self.feedparser_finished(url, True)

    def feedparser_callback(self, parsed, url):
        self.ufeed.confirm_db_thread()
        if not self.ufeed.id_exists() or url not in self.download_dc:
            return
        start = clock()
        parsed = unicodify(parsed)
        self.create_items_for_parsed(parsed)
        self.feedparser_finished(url)
        end = clock()
        if end - start > 1.0:
            logging.timing("feed update for: %s too slow (%.3f secs)",
                           self.url, end - start)

    def call_feedparser(self, html, url):
        self.ufeed.confirm_db_thread()
        in_thread = False
        if in_thread:
            try:
                parsed = feedparser.parse(html)
                self.feedparser_callback(parsed, url)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                self.feedparser_errback(self, None, url)
                raise
        else:
            eventloop.call_in_thread(
                lambda parsed, url=url: self.feedparser_callback(parsed, url),
                lambda e, url=url: self.feedparser_errback(e, url),
                feedparser.parse, "Feedparser callback - %s" % url, html)

    def update(self):
        self.ufeed.confirm_db_thread()
        if not self.ufeed.id_exists():
            return
        if self.updating:
            return
        self.remember_old_items()
        for url in self.urls:
            etag = self.etag.get(url)
            modified = self.modified.get(url)
            self.download_dc[url] = grab_url(
                url,
                lambda x, url=url: self._update_callback(x, url),
                lambda x, url=url: self._update_errback(x, url),
                etag=etag, modified=modified,
                default_mime_type=u'application/rss+xml',)
            self.updating += 1

    def _update_errback(self, error, url):
        if not self.ufeed.id_exists():
            return
        logging.warn("WARNING: error in Feed.update for %s (%s) -- %s",
                     self.ufeed, stringify(url), stringify(error))
        self.schedule_update_events(-1)
        self.updating -= 1
        self.check_update_finished()
        self.ufeed.signal_change(needs_save=False)

    def _update_callback(self, info, url):
        if not self.ufeed.id_exists():
            return
        if info.get('status') == 304:
            self.schedule_update_events(-1)
            self.updating -= 1
            self.check_update_finished()
            self.ufeed.signal_change()
            return
        html = info['body']
        if info.has_key('charset'):
            html = fix_xml_header(html, info['charset'])

        # FIXME HTML can be non-unicode here --NN
        if info.get('updated-url') and url in self.urls:
            index = self.urls.index(url)
            self.urls[index] = unicodify(info['updated-url'])

        if info.has_key('etag'):
            self.etag[url] = unicodify(info['etag'])
        else:
            self.etag[url] = None
        if info.has_key('last-modified'):
            self.modified[url] = unicodify(info['last-modified'])
        else:
            self.modified[url] = None
        self.call_feedparser (html, url)

    def on_remove(self):
        self._cancel_all_downloads()

    def _cancel_all_downloads(self):
        for dc in self.download_dc.values():
            dc.cancel()
        self.download_dc = {}
        self.updating = 0

    def clean_old_items(self):
        self.modified = {}
        self.etag = {}
        self.update()

class SavedSearchFeedImpl(RSSMultiFeedBase):
    def setup_new(self, url, ufeed):
        self.parse_url(url)
        info = searchengines.get_engine_for_name(self.engine)
        title = to_uni(_("%(engine)s for '%(query)s'",
                {'engine': info.title, 'query': self.query}))
        RSSMultiFeedBase.setup_new(self, url, ufeed, title)

    def default_thumbnail_path(self):
        info = searchengines.get_engine_for_name(self.engine)
        return searchengines.icon_path_for_engine(info)

    def setup_restored(self):
        self.parse_url(self.url)
        RSSMultiFeedBase.setup_restored(self)

    def _allow_feed_to_override_thumbnail(self):
        return False

    def parse_url(self, url):
        m = SEARCH_URL_MATCH_RE.match(url)
        self.engine = m.group(1)
        self.query = m.group(2)

    def calc_urls(self):
        return searchengines.get_request_urls(self.engine, self.query)

class ScraperFeedImpl(ThrottledUpdateFeedImpl):
    """A feed based on un unformatted HTML or pre-enclosure RSS
    """
    def setup_new(self, url, ufeed, title=None, initialHTML=None, etag=None,
                  modified=None, charset=None):
        FeedImpl.setup_new(self, url, ufeed, title)
        self.initialHTML = initialHTML
        self.initialCharset = charset
        self.linkHistory = {}
        self.linkHistory[url] = {}
        self.tempHistory = {}
        if not etag is None:
            self.linkHistory[url]['etag'] = unicodify(etag)
        if not modified is None:
            self.linkHistory[url]['modified'] = unicodify(modified)
        self.downloads = set()

        self.set_update_frequency(360)
        self.schedule_update_events(0)

    ## FIXME - not used
    ## @returns_unicode
    ## def getMimeType(self, link):
    ##     raise StandardError, "ScraperFeedImpl.getMimeType not implemented"

    def save_cache_history(self):
        """This puts all of the caching information in tempHistory into the
        linkHistory. This should be called at the end of an updated so that
        the next time we update we don't unnecessarily follow old links
        """
        self.ufeed.confirm_db_thread()
        for url in self.tempHistory.keys():
            self.linkHistory[url] = self.tempHistory[url]
        self.tempHistory = {}

    def get_html(self, urlList, depth=0, linkNumber=0, top=False):
        """Grabs HTML at the given URL, then processes it
        """
        url = urlList.pop(0)
        #print "Grabbing %s" % url
        etag = None
        modified = None
        if self.linkHistory.has_key(url):
            etag = self.linkHistory[url].get('etag', None)
            modified = self.linkHistory[url].get('modified', None)
        def callback(info):
            if not self.ufeed.id_exists():
                return
            self.downloads.discard(download)
            try:
                self.process_downloaded_html(info, urlList, depth, linkNumber,
                                           top)
            finally:
                self.check_done()
        def errback(error):
            if not self.ufeed.id_exists():
                return
            self.downloads.discard(download)
            logging.info("WARNING unhandled error for ScraperFeedImpl.get_html: %s", error)
            self.check_done()
        download = grab_url(url, callback, errback, etag=etag,
                modified=modified, default_mime_type='text/html')
        self.downloads.add(download)

    def process_downloaded_html(self, info, urlList, depth, linkNumber,
                              top=False):
        self.ufeed.confirm_db_thread()
        #print "Done grabbing %s" % info['updated-url']

        if not self.tempHistory.has_key(info['updated-url']):
            self.tempHistory[info['updated-url']] = {}
        if info.has_key('etag'):
            self.tempHistory[info['updated-url']]['etag'] = unicodify(info['etag'])
        if info.has_key('last-modified'):
            self.tempHistory[info['updated-url']]['modified'] = unicodify(info['last-modified'])

        if info['status'] != 304 and info.has_key('body'):
            if info.has_key('charset'):
                subLinks = self.scrape_links(info['body'], info['redirected-url'], charset=info['charset'], setTitle=top)
            else:
                subLinks = self.scrape_links(info['body'], info['redirected-url'], setTitle=top)
            if top:
                self.process_links(subLinks, 0, linkNumber)
            else:
                self.process_links(subLinks, depth+1, linkNumber)
        if len(urlList) > 0:
            self.get_html(urlList, depth, linkNumber)

    def check_done(self):
        if len(self.downloads) == 0:
            self.save_cache_history()
            self.updating = False
            self.ufeed.signal_change()
            self.schedule_update_events(-1)

    def add_video_item(self, link, dict_, linkNumber):
        link = unicodify(link.strip())
        if dict_.has_key('title'):
            title = dict_['title']
        else:
            title = link
        for item in self.items:
            if item.get_url() == link:
                return
        # Anywhere we call this, we need to convert the input back to unicode
        title = feedparser.sanitizeHTML(title, "utf-8").decode('utf-8')
        if dict_.has_key('thumbnail') > 0:
            fp_dict = FeedParserDict({'title': title,
                'enclosures': [FeedParserDict({'url': link,
                    'thumbnail': FeedParserDict({'url': dict_['thumbnail']})
                    })]
                })
        else:
            fp_dict = FeedParserDict({'title': title,
                'enclosures': [FeedParserDict({'url': link})]
                })
        i = models.Item(FeedParserValues(fp_dict),
                             linkNumber=linkNumber, feed_id=self.ufeed.id,
                             eligibleForAutoDownload=False)
        if ((self.ufeed.searchTerm is not None
             and not i.matches_search(self.ufeed.searchTerm))):
            i.remove()
            return

    def process_links(self, links, depth=0, linkNumber=0):
        # FIXME: compound names for titles at each depth??
        maxDepth = 2
        urls = links[0]
        links = links[1]
        # List of URLs that should be downloaded
        newURLs = []

        if depth < maxDepth:
            for link in urls:
                if depth == 0:
                    linkNumber += 1
                #print "Processing %s (%d)" % (link,linkNumber)

                # FIXME: Using file extensions totally breaks the
                # standard and won't work with Broadcast Machine or
                # Blog Torrent. However, it's also a hell of a lot
                # faster than checking the mime type for every single
                # file, so for now, we're being bad boys. Uncomment
                # the elif to make this use mime types for HTTP GET URLs

                mimetype = filetypes.guess_mime_type(link)
                if mimetype is None:
                    mimetype = 'text/html'

                #This is text of some sort: HTML, XML, etc.
                if ((mimetype.startswith('text/html') or
                     mimetype.startswith('application/xhtml+xml') or
                     mimetype.startswith('text/xml')  or
                     mimetype.startswith('application/xml') or
                     mimetype.startswith('application/rss+xml') or
                     mimetype.startswith('application/podcast+xml') or
                     mimetype.startswith('application/atom+xml') or
                     mimetype.startswith('application/rdf+xml') ) and
                    depth < maxDepth -1):
                    newURLs.append(link)

                #This is a video
                elif (mimetype.startswith('video/') or
                      mimetype.startswith('audio/') or
                      mimetype == "application/ogg" or
                      mimetype == "application/x-annodex" or
                      mimetype == "application/x-bittorrent"):
                    self.add_video_item(link, links[link], linkNumber)
            if len(newURLs) > 0:
                self.get_html(newURLs, depth, linkNumber)

    def on_remove(self):
        for download in self.downloads:
            logging.info("canceling download: %s", download.url)
            download.cancel()
        self.downloads = set()

    def update(self):
        # FIXME: go through and add error handling
        self.ufeed.confirm_db_thread()
        if not self.ufeed.id_exists():
            return
        if self.updating:
            return
        else:
            self.updating = True
            self.ufeed.signal_change(needs_save=False)

        if not self.initialHTML is None:
            html = self.initialHTML
            self.initialHTML = None
            redirURL = self.url
            status = 200
            charset = self.initialCharset
            self.initialCharset = None
            subLinks = self.scrape_links(html, redirURL, charset=charset,
                                        setTitle=True)
            self.process_links(subLinks, 0, 0)
            self.check_done()
        else:
            self.get_html([self.url], top=True)

    def scrape_links(self, html, baseurl, setTitle=False, charset=None):
        try:
            if not charset is None:
                html = fix_html_header(html, charset)
            xmldata = html
            parser = xml.sax.make_parser()
            parser.setFeature(xml.sax.handler.feature_namespaces, 1)
            try:
                parser.setFeature(xml.sax.handler.feature_external_ges, 0)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass
            if charset is not None:
                handler = RSSLinkGrabber(baseurl, charset)
            else:
                handler = RSSLinkGrabber(baseurl)
            parser.setContentHandler(handler)
            try:
                parser.parse(StringIO(xmldata))
            except IOError:
                pass
            except AttributeError:
                # bug in the python standard library causes this to be raised
                # sometimes.  See #3201.
                pass
            links = handler.links
            linkDict = {}
            for link in links:
                if ((link[0].startswith('http://')
                     or link[0].startswith('https://'))):
                    if not linkDict.has_key(to_uni(link[0], charset)):
                        linkDict[to_uni(link[0], charset)] = {}
                    if not link[1] is None:
                        linkDict[to_uni(link[0], charset)]['title'] = to_uni(link[1], charset).strip()
                    if not link[2] is None:
                        linkDict[to_uni(link[0], charset)]['thumbnail'] = to_uni(link[2], charset)
            if setTitle and not handler.title is None:
                self.ufeed.confirm_db_thread()
                try:
                    self.title = to_uni(handler.title, charset)
                finally:
                    self.ufeed.signal_change()
            return ([x[0] for x in links if x[0].startswith('http://') or x[0].startswith('https://')], linkDict)
        except (xml.sax.SAXException, ValueError, IOError, xml.sax.SAXNotRecognizedException):
            (links, linkDict) = self.scrape_html_links(html, baseurl,
                                                     setTitle=setTitle,
                                                     charset=charset)
            return (links, linkDict)

    def scrape_html_links(self, html, baseurl, setTitle=False, charset=None):
        """Given a string containing an HTML file, return a dictionary of
        links to titles and thumbnails
        """
        lg = HTMLLinkGrabber()
        links = lg.get_links(html, baseurl)
        if setTitle and not lg.title is None:
            self.ufeed.confirm_db_thread()
            try:
                self.title = to_uni(lg.title, charset)
            finally:
                self.ufeed.signal_change()

        linkDict = {}
        for link in links:
            if link[0].startswith('http://') or link[0].startswith('https://'):
                if not linkDict.has_key(to_uni(link[0], charset)):
                    linkDict[to_uni(link[0], charset)] = {}
                if not link[1] is None:
                    linkDict[to_uni(link[0], charset)]['title'] = to_uni(link[1], charset).strip()
                if not link[2] is None:
                    linkDict[to_uni(link[0], charset)]['thumbnail'] = to_uni(link[2], charset)
        return ([x[0] for x in links
                 if x[0].startswith('http://') or x[0].startswith('https://')],
                linkDict)

    def setup_restored(self):
        """Called by pickle during deserialization
        """
        FeedImpl.setup_restored(self)
        self.downloads = set()
        self.tempHistory = {}

class DirectoryScannerImplBase(FeedImpl):
    """Base class for FeedImpls that scan directories for items."""

    def expire_items(self):
        """Directory Items shouldn't automatically expire
        """
        pass

    def set_update_frequency(self, frequency):
        newFreq = frequency*60
        if newFreq != self.updateFreq:
            self.updateFreq = newFreq
            self.schedule_update_events(-1)

    # the following methods much be implemented by subclasses
    def _scan_dir(self):
        raise NotImplementedError()

    # the following methods may be implemented by subclasses if they need to
    def _before_update(self):
        pass

    def _after_update(self):
        pass

    def _add_known_files(self, known_files):
        pass

    def _make_child(self, file_):
        models.FileItem(file_, feed_id=self.ufeed.id)

    def update(self):
        self.ufeed.confirm_db_thread()

        self._before_update()

        # Calculate files known about by feeds other than the directory feed
        # Using a select statement is good here because we don't want to
        # construct all the Item objects if we don't need to.
        known_files = set(os.path.normcase(row[0]) for row in
                models.Item.select(['filename'],
                    'filename IS NOT NULL AND '
                    '(feed_id is NULL or feed_id != ?)', (self.ufeed_id,)))
        self._add_known_files(known_files)

        # Remove items with deleted files or that that are in feeds
        to_remove = []
        for item in self.items:
            filename = item.get_filename()
            if (filename is None or
                not fileutil.isfile(filename) or
                os.path.normcase(filename) in known_files):
                to_remove.append(item)
        app.bulk_sql_manager.start()
        try:
            for item in to_remove:
                item.remove()
        finally:
            app.bulk_sql_manager.finish()

        # now that we've checked for items that need to be removed, we
        # add our items to known_files so that they don't get added
        # multiple times to this feed.
        for x in self.items:
            known_files.add(os.path.normcase(x.get_filename()))

        # adds any files we don't know about
        # files on the filesystem
        to_add = []
        scan_dir = self._scan_dir()
        if fileutil.isdir(scan_dir):
            all_files = fileutil.miro_allfiles(scan_dir)
            for file_ in all_files:
                file_ = os.path.normcase(file_)
                ufile = filenameToUnicode(file_)
                if (file_ not in known_files and
                        filetypes.is_media_filename(ufile)):
                    to_add.append(file_)

        app.bulk_sql_manager.start()
        try:
            for file_ in to_add:
                self._make_child(file_)
        finally:
            app.bulk_sql_manager.finish()

        self._after_update()
        self.schedule_update_events(-1)

class DirectoryWatchFeedImpl(DirectoryScannerImplBase):
    def setup_new(self, ufeed, directory):
        # calculate url and title arguments to FeedImpl's constructor
        if directory is not None:
            url = u"dtv:directoryfeed:%s" % make_url_safe(directory)
        else:
            url = u"dtv:directoryfeed"
        title = directory
        if title[-1] == '/':
            title = title[:-1]
        title = filenameToUnicode(os.path.basename(title)) + "/"

        FeedImpl.setup_new(self, url=url, ufeed=ufeed, title=title)
        self.dir = directory
        self.firstUpdate = True
        self.set_update_frequency(5)
        self.schedule_update_events(0)

    def _scan_dir(self):
        return self.dir

    def _make_child(self, file_):
        models.FileItem(file_, feed_id=self.ufeed.id,
                mark_seen=self.firstUpdate)

    def _after_update(self):
        if self.firstUpdate:
            self.firstUpdate = False
            self.signal_change()

class DirectoryFeedImpl(DirectoryScannerImplBase):
    """A feed of all of the Movies we find in the movie folder that don't
    belong to a "real" feed.  If the user changes her movies folder, this feed
    will continue to remember movies in the old folder.
    """
    def setup_new(self, ufeed):
        FeedImpl.setup_new(self, url=u"dtv:directoryfeed", ufeed=ufeed, title=None)
        self.set_update_frequency(5)
        self.schedule_update_events(0)

    def _before_update(self):
        # Make sure container items have created FileItems for their contents
        for container in models.Item.containers_view():
            container.find_new_children()

    def _calc_known_files(self):
        pass

    def _add_known_files(self, known_files):
        movies_dir = config.get(prefs.MOVIES_DIRECTORY)
        incomplete_dir = os.path.join(movies_dir, "Incomplete Downloads")
        known_files.add(os.path.normcase(incomplete_dir))

    def _scan_dir(self):
        return config.get(prefs.MOVIES_DIRECTORY)

    @returns_unicode
    def get_title(self):
        return _(u'Local Files')

class SearchFeedImpl(RSSMultiFeedBase):
    """Search and Search Results feeds
    """
    def setup_new(self, ufeed):
        self.engine = searchengines.get_search_engines()[0].name
        self.query = u''
        RSSMultiFeedBase.setup_new(self, url=u'dtv:search', ufeed=ufeed,
                                   title=_(u'Search'))
        self.initialUpdate = True
        self.searching = False
        self.set_update_frequency(-1)
        self.ufeed.autoDownloadable = False
        # keeps the items from being seen as 'newly available'
        self.ufeed.last_viewed = datetime.max
        self.ufeed.signal_change()

    def setup_restored(self):
        self.searching = False
        RSSMultiFeedBase.setup_restored(self)

    def calc_urls(self):
        if self.engine and self.query:
            return searchengines.get_request_urls(self.engine, self.query)
        else:
            return []

    def reset(self, set_engine=None):
        self.ufeed.confirm_db_thread()
        was_searching = self.searching
        self._cancel_all_downloads()
        self.initialUpdate = True
        app.bulk_sql_manager.start()
        try:
            for item in self.items:
                item.remove()
        finally:
            app.bulk_sql_manager.finish()
        self.urls = []
        self.searching = False
        if set_engine is not None:
            self.engine = set_engine
        self.etag = {}
        self.modified = {}
        self.ufeed.icon_cache.reset()
        self.thumbURL = None
        self.ufeed.icon_cache.request_update(is_vital=True)
        if was_searching:
            self.ufeed.emit('update-finished')

    def preserve_downloads(self, downloads_feed):
        self.ufeed.confirm_db_thread()
        for item in self.items:
            if item.get_state() not in ('new', 'not-downloaded'):
                item.setFeed(downloads_feed.id)

    def set_engine(self, engine):
        self.engine = engine

    def lookup(self, engine, query):
        check_u(engine)
        check_u(query)
        self.reset()
        self.searching = True
        self.engine = engine
        self.query = query
        self.urls = self.calc_urls()
        self.update()
        self.ufeed.signal_change()

    def _handle_new_entry(self, entry, fp_values, channelTitle):
        """Handle getting a new entry from a feed."""
        url = fp_values.data['url']
        if url is not None:
            dl = downloader.get_existing_downloader_by_url(url)
            if dl is not None:
                for item in dl.item_list:
                    if ((item.get_feed_url() == 'dtv:searchDownloads'
                         and item.get_url() == url)):
                        try:
                            if entry["id"] == item.get_rss_id():
                                item.setFeed(self.ufeed.id)
                                if not fp_values.compare_to_item(item):
                                    item.update_from_feed_parser_values(fp_values)
                                return
                        except KeyError:
                            pass
                        title = entry.get("title")
                        oldtitle = item.entry_title
                        if title == oldtitle:
                            item.setFeed(self.ufeed.id)
                            if not fp_values.compare_to_item(item):
                                item.update_from_feed_parser_values(fp_values)
                            return
        RSSMultiFeedBase._handle_new_entry(self, entry, fp_values, channelTitle)

    def update_finished(self):
        self.searching = False
        RSSMultiFeedBase.update_finished(self)

    def update(self):
        if self.urls:
            RSSMultiFeedBase.update(self)
        else:
            self.ufeed.emit('update-finished')

class SearchDownloadsFeedImpl(FeedImpl):
    def setup_new(self, ufeed):
        FeedImpl.setup_new(self, url=u'dtv:searchDownloads', ufeed=ufeed,
                title=None)
        self.set_update_frequency(-1)

    @returns_unicode
    def get_title(self):
        return _(u'Search')

class ManualFeedImpl(FeedImpl):
    """Downloaded Videos/Torrents that have been added using by the
    user opening them with democracy.
    """
    def setup_new(self, ufeed):
        FeedImpl.setup_new(self, url=u'dtv:manualFeed', ufeed=ufeed,
                title=None)
        self.ufeed.expire = u'never'
        self.set_update_frequency(-1)
        self.ufeed.last_viewed = datetime.max

    @returns_unicode
    def get_title(self):
        return _(u'Local Files')

class SingleFeedImpl(FeedImpl):
    """Single Video that is playing that has been added by the user
    opening them with democracy.
    """
    def setup_new(self, ufeed):
        FeedImpl.setup_new(self, url=u'dtv:singleFeed', ufeed=ufeed,
                title=None)
        self.ufeed.expire = u'never'
        self.set_update_frequency(-1)

    @returns_unicode
    def get_title(self):
        return _(u'Playing File')

LINK_PATTERN = re.compile("<(a|embed)\s[^>]*(href|src)\s*=\s*\"([^\"]*)\"[^>]*>(.*?)</a(.*)", re.S)
IMG_PATTERN = re.compile(".*<img\s.*?src\s*=\s*\"(.*?)\".*?>", re.S)
TAG_PATTERN = re.compile("<.*?>")

class HTMLLinkGrabber(HTMLParser):
    """Parse HTML document and grab all of the links and titles.
    """
    # FIXME: Grab link title from ALT tags in images
    # FIXME: Grab document title from TITLE tags
    def get_links(self, data, baseurl):
        self.links = []
        self.lastLink = None
        self.inLink = False
        self.inObject = False
        self.baseurl = baseurl
        self.inTitle = False
        self.title = None
        self.thumbnailUrl = None

        match = LINK_PATTERN.search(data)
        while match:
            try:
                link_url = match.group(3).encode('ascii')
            except UnicodeError:
                link_url = match.group(3)
                i = len(link_url) - 1
                while (i >= 0):
                    if 127 < ord(link_url[i]) <= 255:
                        link_url = (link_url[:i] +
                                    "%%%02x" % (ord(link_url[i])) +
                                    link_url[i+1:])
                    i = i - 1

            link = urljoin(baseurl, link_url)
            desc = match.group(4)
            img_match = IMG_PATTERN.match(desc)
            if img_match:
                try:
                    thumb = urljoin(baseurl, img_match.group(1).encode('ascii'))
                except UnicodeError:
                    thumb = None
            else:
                thumb = None
            desc =  TAG_PATTERN.sub(' ', desc)
            self.links.append((link, desc, thumb))
            match = LINK_PATTERN.search(match.group(5))
        return self.links

class RSSLinkGrabber(xml.sax.handler.ContentHandler,
                     xml.sax.handler.ErrorHandler):
    def __init__(self, baseurl, charset=None):
        self.baseurl = baseurl
        self.charset = charset

    def startDocument(self):
        #print "Got start document"
        self.enclosureCount = 0
        self.itemCount = 0
        self.links = []
        self.inLink = False
        self.inDescription = False
        self.inTitle = False
        self.inItem = False
        self.descHTML = ''
        self.theLink = ''
        self.title = None
        self.firstTag = True
        self.errors = 0
        self.fatal_errors = 0

    def startElementNS(self, name, qname, attrs):
        uri = name[0]
        tag = name[1]
        if self.firstTag:
            self.firstTag = False
            if tag not in ['rss', 'feed']:
                raise xml.sax.SAXNotRecognizedException, "Not an RSS file"
        if tag.lower() == 'enclosure' or tag.lower() == 'content':
            self.enclosureCount += 1
        elif tag.lower() == 'link':
            self.inLink = True
            self.theLink = ''
        elif tag.lower() == 'description':
            self.inDescription = True
            self.descHTML = ''
        elif tag.lower() == 'item':
            self.itemCount += 1
            self.inItem = True
        elif tag.lower() == 'title' and not self.inItem:
            self.inTitle = True

    def endElementNS(self, name, qname):
        uri = name[0]
        tag = name[1]
        if tag.lower() == 'description':
            lg = HTMLLinkGrabber()
            try:
                html = xhtmlify(unescape(self.descHTML), add_top_tags=True)
                if not self.charset is None:
                    html = fix_html_header(html, self.charset)
                self.links[:0] = lg.get_links(html, self.baseurl)
            except HTMLParseError: # Don't bother with bad HTML
                logging.info ("bad HTML in description for %s", self.baseurl)
            self.inDescription = False
        elif tag.lower() == 'link':
            self.links.append((self.theLink, None, None))
            self.inLink = False
        elif tag.lower() == 'item':
            self.inItem = False
        elif tag.lower() == 'title' and not self.inItem:
            self.inTitle = False

    def characters(self, data):
        if self.inDescription:
            self.descHTML += data
        elif self.inLink:
            self.theLink += data
        elif self.inTitle:
            if self.title is None:
                self.title = data
            else:
                self.title += data

    def error(self, exception):
        self.errors += 1

    def fatalError(self, exception):
        self.fatal_errors += 1

class HTMLFeedURLParser(HTMLParser):
    """Grabs the feed link from the given webpage
    """
    def get_link(self, baseurl, data):
        self.baseurl = baseurl
        self.link = None
        try:
            self.feed(data)
        except HTMLParseError:
            logging.info ("error parsing %s", baseurl)
        try:
            self.close()
        except HTMLParseError:
            logging.info ("error closing %s", baseurl)
        return self.link

    def handle_starttag(self, tag, attrs):
        attrdict = {}
        for (key, value) in attrs:
            attrdict[key.lower()] = value
        if (tag.lower() == 'link' and attrdict.has_key('rel') and
                attrdict.has_key('type') and attrdict.has_key('href') and
                attrdict['rel'].lower() == 'alternate' and
                attrdict['type'].lower() in ['application/rss+xml',
                                             'application/podcast+xml',
                                             'application/rdf+xml',
                                             'application/atom+xml',
                                             'text/xml',
                                             'application/xml']):
            self.link = urljoin(self.baseurl, attrdict['href'])

def expire_items():
    try:
        for feed in Feed.make_view():
            feed.expire_items()
    finally:
        eventloop.add_timeout(300, expire_items, "Expire Items")

def lookup_feed(url, search_term=None):
    try:
        return Feed.get_by_url_and_search(url, search_term)
    except ObjectNotFoundError:
        return None

def remove_orphaned_feed_impls():
    removed_impls = []
    for klass in (FeedImpl, RSSFeedImpl, SavedSearchFeedImpl,
            ScraperFeedImpl, SearchFeedImpl, DirectoryFeedImpl,
            DirectoryWatchFeedImpl, SearchDownloadsFeedImpl,):
        for feed_impl in klass.orphaned_view():
            logging.warn("No feed for FeedImpl: %s.  Discarding", feed_impl)
            feed_impl.remove()
            removed_impls.append(feed_impl.url)
    if removed_impls:
        databaselog.info("Removed FeedImpl objects without a feed: %s",
                ','.join(removed_impls))

restored_feeds = []
def start_updates():
    global restored_feeds
    if config.get(prefs.CHECK_CHANNELS_EVERY_X_MN) == -1:
        return
    for feed in restored_feeds:
        if feed.id_exists():
            feed.update_after_restore()
    restored_feeds = []
