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


from HTMLParser import HTMLParser, HTMLParseError
from cStringIO import StringIO
from datetime import datetime, timedelta
from miro.gtcache import gettext as _
from miro.feedparser import FeedParserDict
from urlparse import urljoin
from miro.xhtmltools import unescape, xhtmlify, fix_xml_header, fix_html_header, urlencode, urldecode
import os
import re
import xml

from miro.database import DDBObject, ObjectNotFoundError
from miro.httpclient import grabURL
from miro import app
from miro import config
from miro import iconcache
from miro import dialogs
from miro import eventloop
from miro import feedupdate
from miro import flashscraper
from miro import models
from miro import prefs
from miro.plat import resources
from miro import downloader
from miro.util import returnsUnicode, returnsFilename, unicodify, checkU, checkF, quoteUnicodeURL, getFirstVideoEnclosure, escape, toUni
from miro import fileutil
from miro.plat.utils import filenameToUnicode, makeURLSafe, unmakeURLSafe
from miro import filetypes
from miro import item as itemmod
from miro import search
from miro import searchengines
from miro import sorts
import logging
from miro.clock import clock

whitespacePattern = re.compile(r"^[ \t\r\n]*$")
youtubeURLPattern = re.compile(r"^https?://(?:(?:www|gdata).)?youtube.com(?:/.*)?$")
youtubeTitlePattern = re.compile(r"(?:YouTube :: )?Videos (?:uploaded )?by (?P<name>\w*)")

DEFAULT_FEED_ICON = "images/feedicon.png"
DEFAULT_FEED_ICON_TABLIST = "images/icon-rss.png"

@returnsUnicode
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
# We use the function toUni() to fix those smart conversions
#
# If you run into Unicode crashes, adding that function in the
# appropriate place should fix it.

# Universal Feed Parser http://feedparser.org/
# Licensed under Python license
from miro import feedparser

def add_feed_from_file(fn):
    """Adds a new feed using USM
    """
    checkF(fn)
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
    checkU(url)
    def callback(info):
        url = HTMLFeedURLParser().get_link(info['updated-url'], info['body'])
        if url:
            Feed(url)
    def errback(error):
        logging.warning ("unhandled error in add_feed_from_web_page: %s", error)
    grabURL(url, callback, errback)

def validate_feed_url(url):
    """URL validitation and normalization
    """
    checkU(url)
    for c in url.encode('utf8'):
        if ord(c) > 127:
            return False
    if re.match(r"^(http|https)://[^/ ]+/[^ ]*$", url) is not None:
        return True
    if re.match(r"^file://.", url) is not None:
        return True
    match = re.match(r"^dtv:searchTerm:(.*)\?(.*)$", url)
    if match is not None and validate_feed_url(urldecode(match.group(1))):
        return True
    match = re.match(r"^dtv:multi:", url)
    if match is not None:
        return True
    return False

def normalize_feed_url(url):
    checkU(url)
    # Valid URL are returned as-is
    if validate_feed_url(url):
        return url

    searchTerm = None
    m = re.match(r"^dtv:searchTerm:(.*)\?([^?]+)$", url)
    if m is not None:
        searchTerm = urldecode(m.group(2))
        url = urldecode(m.group(1))

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

    if searchTerm is not None:
        url = "dtv:searchTerm:%s?%s" % (urlencode(url), urlencode(searchTerm))
    else:
        url = quoteUnicodeURL(url)

    if not validate_feed_url(url):
        logging.info ("unable to normalize URL %s", originalURL)
        return originalURL
    else:
        return url

def _config_change(key, value):
    """Handle configuration changes so we can update feed update frequencies
    """
    if key is prefs.CHECK_CHANNELS_EVERY_X_MN.key:
        for feed in Feed.make_view():
            updateFreq = 0
            try:
                updateFreq = feed.parsed["feed"]["ttl"]
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass
            feed.setUpdateFrequency(updateFreq)

config.add_change_callback(_config_change)

# Wait X seconds before updating the feeds at startup
INITIAL_FEED_UPDATE_DELAY = 5.0

class FeedImpl(DDBObject):
    """Actual implementation of a basic feed.
    """
    def setup_new(self, url, ufeed, title=None):
        checkU(url)
        if title:
            checkU(title)
        self.url = url
        self.ufeed = ufeed
        self.ufeed_id = ufeed.id
        self.title = title
        self.created = datetime.now()
        self.updating = False
        self.thumbURL = default_feed_icon_url()
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

    @returnsUnicode
    def get_base_href(self):
        """Get a URL to use in the <base> tag for this channel.  This is used
        for relative links in this channel's items.
        """
        return escape(self.url)

    def setUpdateFrequency(self, frequency):
        """Sets the update frequency (in minutes).
        A frequency of -1 means that auto-update is disabled.
        """
        try:
            frequency = int(frequency)
        except ValueError:
            frequency = -1

        if frequency < 0:
            self.cancelUpdateEvents()
            self.updateFreq = -1
        else:
            newFreq = max(config.get(prefs.CHECK_CHANNELS_EVERY_X_MN), frequency)*60
            if newFreq != self.updateFreq:
                self.updateFreq = newFreq
                self.scheduleUpdateEvents(-1)
        self.ufeed.signal_change()

    def scheduleUpdateEvents(self, firstTriggerDelay):
        self.cancelUpdateEvents()
        if firstTriggerDelay >= 0:
            self.scheduler = eventloop.addTimeout(firstTriggerDelay, self.update, "Feed update (%s)" % self.get_title())
        else:
            if self.updateFreq > 0:
                self.scheduler = eventloop.addTimeout(self.updateFreq, self.update, "Feed update (%s)" % self.get_title())

    def cancelUpdateEvents(self):
        if hasattr(self, 'scheduler') and self.scheduler is not None:
            self.scheduler.cancel()
            self.scheduler = None

    def update(self):
        """Subclasses should override this
        """
        self.scheduleUpdateEvents(-1)


    def isLoading(self):
        """Returns true iff the feed is loading. Only makes sense in the
        context of UniversalFeeds
        """
        return False

    def hasLibrary(self):
        """Returns true iff this feed has a library
        """
        return False

    @returnsUnicode
    def get_title(self):
        """Returns the title of the feed
        """
        try:
            title = self.title
            if title is None or whitespacePattern.match(title):
                if self.ufeed.baseTitle is not None:
                    title = self.ufeed.baseTitle
                else:
                    title = self.url
            return title
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return u""

    @returnsUnicode
    def get_url(self):
        """Returns the URL of the feed
        """
        try:
            if self.ufeed.searchTerm is None:
                return self.url
            else:
                return u"dtv:searchTerm:%s?%s" % (urlencode(self.url), urlencode(self.ufeed.searchTerm))
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return u""

    @returnsUnicode
    def getBaseURL(self):
        """Returns the URL of the feed
        """
        try:
            return self.url
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return u""

    @returnsUnicode
    def get_description(self):
        """Returns the description of the feed
        """
        return u"<span />"

    @returnsUnicode
    def get_link(self):
        """Returns a link to a webpage associated with the feed
        """
        return self.ufeed.get_base_href()

    @returnsUnicode
    def getLibraryLink(self):
        """Returns the URL of the library associated with the feed
        """
        return u""

    @returnsUnicode
    def get_thumbnail_url(self):
        """Returns the URL of a thumbnail associated with the feed
        """
        return self.thumbURL

    @returnsUnicode
    def get_license(self):
        """Returns URL of license assocaited with the feed
        """
        return u""

    def setup_restored(self):
        self.updating = False

    def remove(self):
        self.onRemove()
        DDBObject.remove(self)

    def onRemove(self):
        """Called when the feed uses this FeedImpl is removed from the DB.
        subclasses can perform cleanup here."""
        pass

    def __str__(self):
        return "%s - %s" % (self.__class__.__name__, self.get_title())

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

    def setup_new(self, url,
                 initiallyAutoDownloadable=None, section=u'video'):
        checkU(url)
        if initiallyAutoDownloadable == None:
            mode = config.get(prefs.CHANNEL_AUTO_DEFAULT)
            # note that this is somewhat duplicated in set_auto_download_mode
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
        self.searchTerm = None
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
        self.itemSort = sorts.ItemSort()
        self.itemSortDownloading = sorts.ItemSort()
        self.itemSortWatchable = sorts.ItemSortUnwatchedFirst()
        self.inlineSearchTerm = None
        self.calc_item_list()

    def _get_actual_feed(self):
        # first try to load from actualFeed from the DB
        if self._actualFeed is None:
            for klass in (FeedImpl, RSSFeedImpl, RSSMultiFeedImpl,
                    ScraperFeedImpl, SearchFeedImpl, DirectoryFeedImpl,
                    DirectoryWatchFeedImpl, SearchDownloadsFeedImpl,):
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
    def get_manual_feed(cls):
        return cls.get_by_url('dtv:manualFeed')

    @classmethod
    def get_single_feed(cls):
        return cls.get_by_url('dtv:singleFeed')

    @classmethod
    def get_directory_feed(cls):
        return cls.get_by_url('dtv:directoryfeed')

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
        self.generateFeed(True)

    def in_folder(self):
        return self.folder_id is not None

    def _set_feed_impl(self, feed_impl):
        if self._actualFeed is not None:
            self._actualFeed.remove()
        self._actualFeed = feed_impl
        self.feed_impl_id = feed_impl.id

    def signal_change(self, needsSave=True, needsSignalFolder=False):
        if needsSignalFolder:
            folder = self.get_folder()
            if folder:
                folder.signal_change(needsSave=False)
        DDBObject.signal_change (self, needsSave=needsSave)

    def on_signal_change(self):
        isUpdating = bool(self.actualFeed.updating)
        if self.wasUpdating and not isUpdating:
            self.emit('update-finished')
        self.wasUpdating = isUpdating

    def calc_item_list(self):
        self.items = itemmod.Item.feed_view(self.id)
        self.visible_items = itemmod.Item.visible_feed_view(self.id)
        self.downloaded_items = itemmod.Item.feed_downloaded_view(self.id)
        self.downloading_items = itemmod.Item.feed_downloading_view(self.id)
        self.available_items = itemmod.Item.feed_available_view(self.id)
        self.auto_pending_items = itemmod.Item.feed_auto_pending_view(self.id)
        self.unwatched_items = itemmod.Item.feed_unwatched_view(self.id)

    def update_after_restore(self):
        if self.actualFeed.__class__ == FeedImpl:
            # Our initial FeedImpl was never updated, call generateFeed again
            self.loading = True
            eventloop.addIdle(lambda:self.generateFeed(True), "generateFeed")
        else:
            self.scheduleUpdateEvents(INITIAL_FEED_UPDATE_DELAY)

    def clean_old_items(self):
        if self.actualFeed:
            return self.actualFeed.clean_old_items()

    def recalc_counts(self):
        for cached_count_attr in ('_num_available', '_num_unwatched',
                '_num_downloaded', '_num_downloading'):
            if cached_count_attr in self.__dict__:
                del self.__dict__[cached_count_attr]
        self.signal_change(needsSave=False)
        if self.in_folder():
            self.get_folder().signal_change(needsSave=False)

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
        self.signal_change()

    def startManualDownload(self):
        next = None
        for item in self.items:
            if item.is_pending_manual_download():
                if next is None:
                    next = item
                elif item.get_pub_date_parsed() > next.get_pub_date_parsed():
                    next = item
        if next is not None:
            next.download(autodl = False)

    def startAutoDownload(self):
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
        if self.expire == u'never':
            return []
        elif self.expire == u'system':
            expire_after_x_days = config.get(prefs.EXPIRE_AFTER_X_DAYS)
            if expire_after_x_days == -1:
                return []
            delta = timedelta(days=expire_after_x_days)
        else:
            delta = self.expireTime
        return itemmod.Item.feed_expiring_view(self.id, datetime.now() - delta)

    def expire_items(self):
        """Returns marks expired items as expired
        """
        for item in self.expiring_items():
            item.expire()

    def signalItems (self):
        for item in self.items:
            item.signal_change(needsSave=False)

    def icon_changed(self):
        """See item.get_thumbnail to figure out which items to send signals for.
        """
        self.signal_change(needsSave=False)
        for item in self.items:
            if not (item.icon_cache.isValid() or
                    item.screenshot or
                    item.isContainerItem):
                item.signal_change(needsSave=False)

    def getNewItems(self):
        """Returns the number of new items with the feed
        """
        self.confirm_db_thread()
        count = 0
        for item in self.items:
            try:
                if item.get_state() == u'newly-downloaded':
                    count += 1
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass
        return count


    def setInlineSearchTerm(self, term):
        self.inlineSearchTerm = term

    def getID(self):
        return DDBObject.getID(self)

    def hasError(self):
        self.confirm_db_thread()
        return self.errorState

    @returnsUnicode
    def getOriginalURL(self):
        self.confirm_db_thread()
        return self.origURL

    @returnsUnicode
    def getSearchTerm(self):
        self.confirm_db_thread()
        return self.searchTerm

    @returnsUnicode
    def getError(self):
        return u"Could not load feed"

    def isUpdating(self):
        return self.loading or (self.actualFeed and self.actualFeed.updating)

    def isScraped(self):
        return isinstance(self.actualFeed, ScraperFeedImpl)

    @returnsUnicode
    def get_title(self):
        if self.userTitle is not None:
            return self.userTitle

        title = self.actualFeed.get_title()
        if self.searchTerm is not None:
            title = u"%s: %s" % (title, self.searchTerm)
        return title

    def has_original_title(self):
        return self.userTitle == None

    def set_title(self, title):
        self.confirm_db_thread()
        self.userTitle = title
        self.signal_change()

    def revert_title(self):
        self.set_title(None)

    @returnsUnicode
    def setBaseTitle(self, title):
        """Set the baseTitle.
        """
        self.baseTitle = title
        self.signal_change()

    def isVisible(self):
        """Returns true iff feed should be visible
        """
        self.confirm_db_thread()
        return self.visible

    def setVisible(self, visible):
        if self.visible == visible:
            return
        self.visible = visible
        self.signal_change()

    @returnsUnicode
    def getAutoDownloadMode(self):
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
        # need to call signal_related_change() because items may have
        # entered/left the pending autodownload view
        self.signal_related_change()

    def getCurrentAutoDownloadableItems(self):
        auto = set()
        for item in self.items:
            if item.is_pending_auto_download():
                auto.add(item)
        return auto

    def setExpiration(self, type_, time_):
        """Sets the expiration attributes. Valid types are u'system', u'feed' and
        u'never'.

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
        for item in self.items:
            item.signal_change(needsSave=False)

    def set_max_new(self, max_new):
        """Sets the maxNew attributes. -1 means unlimited.
        """
        self.confirm_db_thread()
        oldMaxNew = self.maxNew
        self.maxNew = max_new
        self.signal_change()
        if self.maxNew >= oldMaxNew or self.maxNew < 0:
            from miro import autodler
            autodler.auto_downloader.start_downloads()

    def setMaxOldItems(self, maxOldItems):
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
        if not self.idExists():
            return
        if self.loading:
            return
        elif self.errorState:
            self.loading = True
            self.errorState = False
            self.signal_change()
            return self.generateFeed()
        self.actualFeed.update()

    def get_folder(self):
        self.confirm_db_thread()
        if self.in_folder():
            return models.ChannelFolder.get_by_id(self.folder_id)
        else:
            return None

    def set_folder(self, newFolder):
        self.confirm_db_thread()
        oldFolder = self.get_folder()
        if newFolder is not None:
            self.folder_id = newFolder.getID()
        else:
            self.folder_id = None
        self.signal_change()
        for item in self.items:
            item.signal_change(needsSave=False)
        if newFolder:
            newFolder.signal_change(needsSave=False)
        if oldFolder:
            oldFolder.signal_change(needsSave=False)

    def generateFeed(self, removeOnError=False):
        newFeed = None
        if self.origURL == u"dtv:directoryfeed":
            newFeed = DirectoryFeedImpl(self)
            self.visible = False
        elif (self.origURL.startswith(u"dtv:directoryfeed:")):
            url = self.origURL[len(u"dtv:directoryfeed:"):]
            dir_ = unmakeURLSafe(url)
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
        elif self.origURL.startswith(u"dtv:multi:"):
            newFeed = RSSMultiFeedImpl(self.origURL, self)
        elif self.origURL.startswith(u"dtv:searchTerm:"):
            url = self.origURL[len(u"dtv:searchTerm:"):]
            (url, search) = url.rsplit("?", 1)
            url = urldecode(url)
            # search terms encoded as utf-8, but our URL attribute is then
            # converted to unicode.  So we need to:
            #  - convert the unicode to a raw string
            #  - urldecode that string
            #  - utf-8 decode the result.
            search = urldecode(search.encode('ascii')).decode('utf-8')
            self.searchTerm = search
            if url.startswith(u"dtv:multi:"):
                newFeed = RSSMultiFeedImpl(url, self)
            else:
                self.download = grabURL(url,
                        lambda info:self._generateFeedCallback(info, removeOnError),
                        lambda error:self._generateFeedErrback(error, removeOnError),
                        defaultMimeType=u'application/rss+xml')
        else:
            self.download = grabURL(self.origURL,
                    lambda info:self._generateFeedCallback(info, removeOnError),
                    lambda error:self._generateFeedErrback(error, removeOnError),
                    defaultMimeType=u'application/rss+xml')
            logging.debug ("added async callback to create feed %s", self.origURL)
        if newFeed:
            self.finishGenerateFeed(newFeed)

    def is_watched_folder(self):
        return self.origURL.startswith("dtv:directoryfeed:")

    def _handleFeedLoadingError(self, errorDescription):
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
                if dialog.choice == dialogs.BUTTON_DELETE and self.idExists():
                    self.remove()
            d.run(callback)
            self.informOnError = False
        delay = config.get(prefs.CHECK_CHANNELS_EVERY_X_MN)
        eventloop.addTimeout(delay, self.update, "update failed feed")

    def _generateFeedErrback(self, error, removeOnError):
        if not self.idExists():
            return
        logging.info("Warning couldn't load feed at %s (%s)",
                     self.origURL, error)
        self._handleFeedLoadingError(error.getFriendlyDescription())

    def _generateFeedCallback(self, info, removeOnError):
        """This is called by grabURL to generate a feed based on
        the type of data found at the given URL
        """
        # FIXME: This probably should be split up a bit. The logic is
        #        a bit daunting


        # Note that all of the raw XML and HTML in this function is in
        # byte string format

        if not self.idExists():
            return
        if info['updated-url'] != self.origURL and \
                not self.origURL.startswith('dtv:'): # we got redirected
            f = get_feed_by_url(info['updated-url'])
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

        #Definitely an HTML feed
        if (contentType.startswith(u'text/html') or
                contentType.startswith(u'application/xhtml+xml')) and not apparentlyRSS:
            #print "Scraping HTML"
            html = info['body']
            if info.has_key('charset'):
                html = fix_html_header(html, info['charset'])
                charset = unicodify(info['charset'])
            else:
                charset = None
            self.askForScrape(info, html, charset)
        #It's some sort of feed we don't know how to scrape
        elif (contentType.startswith(u'application/rdf+xml') or
              contentType.startswith(u'application/atom+xml')):
            #print "ATOM or RDF"
            html = info['body']
            if info.has_key('charset'):
                xmldata = fix_xml_header(html, info['charset'])
            else:
                xmldata = html
            self.finishGenerateFeed(RSSFeedImpl(unicodify(info['updated-url']),
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
            try:
                parser.setFeature(xml.sax.handler.feature_external_ges, 0)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass
            handler = RSSLinkGrabber(unicodify(info['redirected-url']), charset)
            parser.setContentHandler(handler)
            parser.setErrorHandler(handler)
            try:
                parser.parse(StringIO(xmldata))
            except UnicodeDecodeError:
                logging.exception ("Unicode issue parsing... %s", xmldata[0:300])
                self.finishGenerateFeed(None)
                if removeOnError:
                    self.remove()
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                #it doesn't parse as RSS, so it must be HTML
                #print " Nevermind! it's HTML"
                self.askForScrape(info, html, charset)
            else:
                #print " It's RSS with enclosures"
                self.finishGenerateFeed(RSSFeedImpl(
                    unicodify(info['updated-url']),
                    initialHTML=xmldata, etag=etag, modified=modified,
                    ufeed=self))
        else:
            self._handleFeedLoadingError(_("Bad content-type"))

    def finishGenerateFeed(self, feedImpl):
        self.confirm_db_thread()
        self.loading = False
        if feedImpl is not None:
            self._set_feed_impl(feedImpl)
            self.errorState = False
        else:
            self.errorState = True
        self.signal_change()

    def askForScrape(self, info, initialHTML, charset):
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
            {"url": info["updated-url"], "appname": config.get(prefs.SHORT_APP_NAME)}
        )
        dialog = dialogs.ChoiceDialog(title, description, dialogs.BUTTON_YES,
                dialogs.BUTTON_NO)

        def callback(dialog):
            if not self.idExists():
                return
            if dialog.choice == dialogs.BUTTON_YES:
                uinfo = unicodify(info)
                impl = ScraperFeedImpl(uinfo['updated-url'],
                    initialHTML=initialHTML, etag=uinfo.get('etag'),
                    modified=uinfo.get('modified'), charset=charset,
                    ufeed=self)
                self.finishGenerateFeed(impl)
            else:
                self.remove()
        dialog.run(callback)

    def getActualFeed(self):
        return self.actualFeed

    # Many attributes come from whatever FeedImpl subclass we're using.
    def attr_from_feed_impl(name):
        def getter(self):
            return getattr(self.actualFeed, name)
        return property(getter)

    for name in ( 'setUpdateFrequency', 'scheduleUpdateEvents',
            'cancelUpdateEvents', 'update', 'isLoading',
            'hasLibrary', 'get_url', 'getBaseURL',
            'get_base_href', 'get_description', 'get_link', 'getLibraryLink',
            'get_thumbnail_url', 'get_license', 'url', 'title', 'created',
            'thumbURL', 'lastEngine', 'lastQuery', 'dir',
            'preserveDownloads', 'lookup', 'set_info', 'reset',
            ):
        locals()[name] = attr_from_feed_impl(name)

    @returnsUnicode
    def get_expiration_type(self):
        """Returns "feed," "system," or "never"
        """
        self.confirm_db_thread()
        return self.expire

    def getMaxFallBehind(self):
        """Returns"unlimited" or the maximum number of items this feed can fall
        behind
        """
        self.confirm_db_thread()
        if self.fallBehind < 0:
            return u"unlimited"
        else:
            return self.fallBehind

    def get_max_new(self):
        """Returns "unlimited" or the maximum number of items this feed wants
        """
        self.confirm_db_thread()
        if self.maxNew < 0:
            return u"unlimited"
        else:
            return self.maxNew

    def get_max_old_items(self):
        """Returns the number of items to remember past the current contents of
        the feed.  If self.maxOldItems is None, then this returns "system"
        indicating that the caller should look up the default in
        prefs.MAX_OLD_ITEMS_DEFAULT.
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
        if (self.expireTime is None or self.expire == 'never' or
                (self.expire == 'system' and expireAfterSetting <= 0)):
            return 0
        else:
            return (self.expireTime.days * 24 +
                    self.expireTime.seconds / 3600)

    def getExpireDays(self):
        """Returns the number of days until a video expires
        """
        self.confirm_db_thread()
        try:
            return self.expireTime.days
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return timedelta(days=config.get(prefs.EXPIRE_AFTER_X_DAYS)).days

    def getExpireHours(self):
        """Returns the number of hours until a video expires
        """
        self.confirm_db_thread()
        try:
            return int(self.expireTime.seconds/3600)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return int(timedelta(days=config.get(prefs.EXPIRE_AFTER_X_DAYS)).seconds/3600)

    def getExpires(self):
        expireAfterSetting = config.get(prefs.EXPIRE_AFTER_X_DAYS)
        return (self.expireTime is None or self.expire == 'never' or
                (self.expire == 'system' and expireAfterSetting <= 0))

    def isAutoDownloadable(self):
        """Returns true iff item is autodownloadable
        """
        self.confirm_db_thread()
        return self.autoDownloadable

    def autoDownloadStatus(self):
        status = self.isAutoDownloadable()
        if status:
            return u"ON"
        else:
            return u"OFF"

    def remove(self, moveItemsTo=None):
        """Remove the feed.  If moveItemsTo is None (the default), the items
        in this feed will be removed too.  If moveItemsTo is given, the items
        in this feed will be moved to that feed.
        """

        self.confirm_db_thread()

        if isinstance(self.actualFeed, DirectoryWatchFeedImpl):
            moveItemsTo = None
        self.cancelUpdateEvents()
        if self.download is not None:
            self.download.cancel()
            self.download = None
        for item in self.items:
            if moveItemsTo is not None and item.is_downloaded():
                item.setFeed(moveItemsTo.getID())
            else:
                item.remove()
        self.remove_icon_cache()
        DDBObject.remove(self)
        self.actualFeed.remove()

    def thumbnailValid(self):
        return self.icon_cache and self.icon_cache.isValid()

    def calcThumbnail(self):
        if self.thumbnailValid():
            return fileutil.expand_filename(self.icon_cache.get_filename())
        else:
            return default_feed_icon_path()

    def calcTablistThumbnail(self):
        if self.thumbnailValid():
            return fileutil.expand_filename(self.icon_cache.get_filename())
        else:
            return default_tablist_feed_icon_path()

    @returnsUnicode
    def get_thumbnail(self):
        # FIXME - it looks like this never gets called
        self.confirm_db_thread()
        return resources.absoluteUrl(self.calcThumbnail())

    @returnsFilename
    def get_thumbnail_path(self):
        self.confirm_db_thread()
        return resources.path(self.calcThumbnail())

    @returnsUnicode
    def getTablistThumbnail(self):
        self.confirm_db_thread()
        return resources.absoluteUrl(self.calcTablistThumbnail())

    @returnsFilename
    def getTablistThumbnailPath(self):
        self.confirm_db_thread()
        return resources.path(self.calcTablistThumbnail())

    def hasDownloadedItems(self):
        return self.num_downloaded() > 0

    def hasDownloadingItems(self):
        return self.num_downloading() > 0

    def updateIcons(self):
        iconcache.iconCacheUpdater.clear_vital()
        for item in self.items:
            item.icon_cache.request_update(True)
        for feed in Feed.make_view():
            feed.icon_cache.request_update(True)

    def __str__(self):
        return "Feed - %s" % self.get_title()

class ThrottledUpdateFeedImpl(FeedImpl):
    """Feed Impl that uses the feedupdate module to schedule it's updates.
    Only a limited number of ThrottledUpdateFeedImpl objects will be updating at
    any given time.
    """

    def scheduleUpdateEvents(self, firstTriggerDelay):
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
    Base class from which RSSFeedImpl and RSSMultiFeedImpl derive.
    """

    def setup_new(self, url, ufeed, title):
        FeedImpl.setup_new(self, url, ufeed, title)
        self.scheduleUpdateEvents(0)

    def _handleNewEntry(self, entry, channelTitle):
        """Handle getting a new entry from a feed."""
        item = itemmod.Item(entry, feed_id=self.ufeed.id)
        if not item.matches_search(self.ufeed.searchTerm):
            item.remove()
        item.set_channel_title(channelTitle)

    def createItemsForParsed(self, parsed):
        """Update the feed using parsed XML passed in"""

        # This is a HACK for Yahoo! search which doesn't provide
        # enclosures
        for entry in parsed['entries']:
            if 'enclosures' not in entry:
                try:
                    url = entry['link']
                except (SystemExit, KeyboardInterrupt):
                    raise
                except:
                    continue
                mimetype = filetypes.guess_mime_type(url)
                if mimetype is not None:
                    entry['enclosures'] = [{'url':toUni(url), 'type':toUni(mimetype)}]
                elif flashscraper.is_maybe_flashscrapable(url):
                    entry['enclosures'] = [{'url':toUni(url), 'type':toUni("video/flv")}]
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
        if not self.url.startswith("dtv:multi:"):
            if channelTitle != None:
                if youtubeURLPattern.match(self.url):
                    titleMatch = youtubeTitlePattern.match(channelTitle)
                    if titleMatch:
                        channelTitle = titleMatch.groups('name')[0]
                self.title = channelTitle
            if (parsed.feed.has_key('image') and
                    parsed.feed.image.has_key('url')):
                self.thumbURL = parsed.feed.image.url
                self.ufeed.icon_cache.request_update(is_vital=True)

        items_byid = {}
        items_byURLTitle = {}
        items_nokey = []
        old_items = set()
        for item in self.items:
            old_items.add(item)
            try:
                items_byid[item.getRSSID()] = item
            except KeyError:
                items_nokey.append(item)
            by_url_title_key = (item.url, item.entry_title)
            if by_url_title_key != (None, None):
                items_byURLTitle[by_url_title_key] = item
        for entry in parsed.entries:
            entry = self.addScrapedThumbnail(entry)
            fp_values = itemmod.FeedParserValues(entry)
            new = True
            if entry.has_key("id"):
                id_ = entry["id"]
                if items_byid.has_key(id_):
                    item = items_byid[id_]
                    if not fp_values.compare_to_item(item):
                        item.update_from_feed_parser_values(fp_values)
                    new = False
                    old_items.discard(item)
            if new:
                by_url_title_key = (fp_values.data['url'],
                        fp_values.data['entry_title'])
                if by_url_title_key != (None, None):
                    if items_byURLTitle.has_key(by_url_title_key):
                        item = items_byURLTitle[by_url_title_key]
                        if not fp_values.compare_to_item(item):
                            item.update_from_feed_parser_values(fp_values)
                        new = False
                        old_items.discard(item)
            if new:
                for item in items_nokey:
                    if fp_values.compare_to_item(item):
                        new = False
                    else:
                        try:
                            if fp_values.compare_to_item_enclosures(item):
                                item.update_from_feed_parser_values(fp_values)
                                new = False
                                old_items.discard(item)
                        except (SystemExit, KeyboardInterrupt):
                            raise
                        except:
                            pass
            if (new and entry.has_key('enclosures') and
                    getFirstVideoEnclosure(entry) != None):
                self._handleNewEntry(entry, channelTitle)
        return old_items

    def update_finished(self, old_items):
        """
        Called by subclasses to finish the update.
        """
        if self.initialUpdate:
            self.initialUpdate = False
            startfrom = None
            itemToUpdate = None
            for item in self.items:
                itemTime = item.get_pub_date_parsed()
                if startfrom is None or itemTime > startfrom:
                    startfrom = itemTime
                    itemToUpdate = item
            for item in self.items:
                if item == itemToUpdate:
                    item.eligibleForAutoDownload = True
                else:
                    item.eligibleForAutoDownload = False
                item.signal_change()
            if self.ufeed.isAutoDownloadable():
                self.ufeed.mark_as_viewed()
            self.ufeed.signal_change()

        self.ufeed.recalc_counts()
        self.truncateOldItems(old_items)
        self.signal_change()

    def truncateOldItems(self, old_items):
        """Truncate items so that the number of items in this feed doesn't
        exceed self.get_max_old_items()

        old_items should be an iterable that contains items that aren't in the
        feed anymore.

        Items are only truncated if they don't exist in the feed anymore, and
        if the user hasn't downloaded them.
        """
        limit = self.ufeed.get_max_old_items()
        if limit == u"system":
            limit = config.get(prefs.MAX_OLD_ITEMS_DEFAULT)

        item_count = self.items.count()
        if item_count > config.get(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS):
            truncate = item_count - config.get(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS)
            if truncate > len(old_items):
                truncate = 0
            limit = min(limit, truncate)
        extra = len(old_items) - limit
        if extra <= 0:
            return

        candidates = []
        for item in old_items:
            if item.downloader is None:
                candidates.append((item.creationTime, item))
        candidates.sort()
        for time, item in candidates[:extra]:
            item.remove()

    def addScrapedThumbnail(self, entry):
        # skip this if the entry already has a thumbnail.
        if entry.has_key('thumbnail'):
            return entry
        if entry.has_key('enclosures'):
            for enc in entry['enclosures']:
                if enc.has_key('thumbnail'):
                    return entry
        return entry

class RSSFeedImpl(RSSFeedImplBase):

    def setup_new(self, url, ufeed, title=None, initialHTML=None, etag=None, modified=None):
        RSSFeedImplBase.setup_new(self, url, ufeed, title)
        self.initialHTML = initialHTML
        self.etag = etag
        self.modified = modified
        self.download = None

    @returnsUnicode
    def get_base_href(self):
        try:
            return escape(self.parsed.link)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return FeedImpl.get_base_href(self)

    @returnsUnicode
    def get_description(self):
        """Returns the description of the feed
        """
        self.ufeed.confirm_db_thread()
        try:
            return xhtmlify(u'<span>'+unescape(self.parsed.feed.description)+u'</span>')
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return u"<span />"

    @returnsUnicode
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

    @returnsUnicode
    def getLibraryLink(self):
        """Returns the URL of the library associated with the feed
        """
        self.ufeed.confirm_db_thread()
        try:
            return self.parsed.libraryLink
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return u""

    def feedparser_finished(self):
        self.updating = False
        self.ufeed.signal_change(needsSave=False)
        self.scheduleUpdateEvents(-1)

    def feedparser_errback(self, e):
        if not self.ufeed.idExists():
            return
        logging.info("Error updating feed: %s: %s", self.url, e)
        self.feedparser_finished()

    def feedparser_callback(self, parsed):
        self.ufeed.confirm_db_thread()
        if not self.ufeed.idExists():
            return
        start = clock()
        parsed = self.parsed = unicodify(parsed)
        old_items = self.createItemsForParsed(parsed)

        try:
            updateFreq = self.parsed["feed"]["ttl"]
        except KeyError:
            updateFreq = 0
        self.setUpdateFrequency(updateFreq)

        self.update_finished(old_items)
        self.feedparser_finished()
        end = clock()
        if end - start > 1.0:
            logging.timing("feed update for: %s too slow (%.3f secs)", self.url, end - start)

    def call_feedparser(self, html):
        self.ufeed.confirm_db_thread()
        eventloop.callInThread(self.feedparser_callback, self.feedparser_errback, feedparser.parse, "Feedparser callback - %s" % self.url, html)

    def update(self):
        """Updates a feed
        """
        self.ufeed.confirm_db_thread()
        if not self.ufeed.idExists():
            return
        if self.updating:
            return
        else:
            self.updating = True
            self.ufeed.signal_change(needsSave=False)
        if hasattr(self, 'initialHTML') and self.initialHTML is not None:
            html = self.initialHTML
            self.initialHTML = None
            self.call_feedparser(html)
        else:
            try:
                etag = self.etag
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                etag = None
            try:
                modified = self.modified
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                modified = None
            logging.info("updating %s", self.url)
            self.download = grabURL(self.url, self._updateCallback,
                    self._updateErrback, etag=etag, modified=modified, defaultMimeType=u'application/rss+xml')

    def _updateErrback(self, error):
        if not self.ufeed.idExists():
            return
        logging.info("WARNING: error in Feed.update for %s -- %s", self.ufeed, error)
        self.scheduleUpdateEvents(-1)
        self.updating = False
        self.ufeed.signal_change(needsSave=False)

    def _updateCallback(self, info):
        if not self.ufeed.idExists():
            return
        if info.get('status') == 304:
            self.scheduleUpdateEvents(-1)
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

    @returnsUnicode
    def get_license(self):
        """Returns the URL of the license associated with the feed
        """
        if hasattr(self, "parsed"):
            try:
                return self.parsed["feed"]["license"]
            except KeyError:
                pass
        return u""

    def onRemove(self):
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

class RSSMultiFeedImpl(RSSFeedImplBase):
    def setup_new(self, url, ufeed, title=None):
        RSSFeedImplBase.setup_new(self, url, ufeed, title)
        self.oldItems = None
        self.etag = {}
        self.modified = {}
        self.download_dc = {}
        self.updating = 0
        self.query = None
        self.splitURLs()

    def get_title(self):
        if self.query:
            return _("Search All: %(text)s", {"text": self.query})
        return RSSFeedImplBase.get_title(self)

    def splitURLs(self):
        if self.url.startswith("dtv:multi:"):
            url = self.url[len("dtv:multi:"):]
            urls = [urldecode (x) for x in url.split(",")]
            self.urls = urls[:-1]
            if u"http" in urls[-1]:
                self.urls.append(urls[-1])
            else:
                self.query = urls[-1]
        else:
            self.urls = [self.url]

    @returnsUnicode
    def get_description(self):
        """Returns the description of the feed
        """
        self.ufeed.confirm_db_thread()
        try:
            return u'<span>Search All</span>'
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            return u"<span />"

    def checkUpdateFinished(self):
        if self.updating == 0:
            self.update_finished(self.oldItems)
            self.oldItems = None
            self.scheduleUpdateEvents(-1)

    def feedparser_finished(self, url, needsSave=False):
        if not self.ufeed.idExists():
            return
        self.updating -= 1
        self.checkUpdateFinished()
        del self.download_dc[url]

    def feedparser_errback(self, e, url):
        if not self.ufeed.idExists() or url not in self.download_dc:
            return
        if e:
            logging.info("Error updating feed: %s (%s): %s", self.url, url, e)
        else:
            logging.info("Error updating feed: %s (%s)", self.url, url)
        self.feedparser_finished(url, True)

    def feedparser_callback(self, parsed, url):
        self.ufeed.confirm_db_thread()
        if not self.ufeed.idExists() or url not in self.download_dc:
            return
        start = clock()
        parsed = unicodify(parsed)
        old_items = self.createItemsForParsed(parsed)
        self.oldItems.update(old_items)
        self.feedparser_finished(url)
        end = clock()
        if end - start > 1.0:
            logging.timing("feed update for: %s too slow (%.3f secs)", self.url, end - start)

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
            eventloop.callInThread(lambda parsed, url=url: self.feedparser_callback(parsed, url),
                                   lambda e, url=url: self.feedparser_errback(e, url),
                                   feedparser.parse, "Feedparser callback - %s" % url, html)

    def update(self):
        self.ufeed.confirm_db_thread()
        if not self.ufeed.idExists():
            return
        if self.updating:
            return
        self.oldItems = set()
        for url in self.urls:
            etag = self.etag.get(url)
            modified = self.modified.get(url)
            self.download_dc[url] = grabURL(url,
                                            lambda x, url=url: self._updateCallback(x, url),
                                            lambda x, url=url: self._updateErrback(x, url),
                                            etag=etag, modified=modified,
                                            defaultMimeType=u'application/rss+xml',)
            self.updating += 1

    def _updateErrback(self, error, url):
        if not self.ufeed.idExists():
            return
        logging.info("WARNING: error in Feed.update for %s (%s) -- %s", self.ufeed, url, error)
        self.scheduleUpdateEvents(-1)
        self.updating -= 1
        self.checkUpdateFinished()
        self.ufeed.signal_change(needsSave=False)

    def _updateCallback(self, info, url):
        if not self.ufeed.idExists():
            return
        if info.get('status') == 304:
            self.scheduleUpdateEvents(-1)
            self.updating -= 1
            self.checkUpdateFinished()
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

    def onRemove(self):
        for dc in self.download_dc.values():
            if dc is not None:
                dc.cancel()
        self.download_dc = {}

    def setup_restored(self):
        """Called by pickle during deserialization
        """
        #FIXME: the update dies if all of the items aren't restored, so we
        # wait a little while before we start the update
        FeedImpl.setup_restored(self)
        self.download_dc = {}
        self.updating = 0
        self.splitURLs()

    def clean_old_items(self):
        self.modified = {}
        self.etag = {}
        self.update()


class ScraperFeedImpl(ThrottledUpdateFeedImpl):
    """A feed based on un unformatted HTML or pre-enclosure RSS
    """
    def setup_new(self, url, ufeed, title=None, initialHTML=None, etag=None, modified=None, charset=None):
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

        self.setUpdateFrequency(360)
        self.scheduleUpdateEvents(0)

    @returnsUnicode
    def getMimeType(self, link):
        raise StandardError, "ScraperFeedImpl.getMimeType not implemented"

    def saveCacheHistory(self):
        """This puts all of the caching information in tempHistory into the
        linkHistory. This should be called at the end of an updated so that
        the next time we update we don't unnecessarily follow old links
        """
        self.ufeed.confirm_db_thread()
        for url in self.tempHistory.keys():
            self.linkHistory[url] = self.tempHistory[url]
        self.tempHistory = {}

    def getHTML(self, urlList, depth=0, linkNumber=0, top=False):
        """Grabs HTML at the given URL, then processes it
        """
        url = urlList.pop(0)
        #print "Grabbing %s" % url
        etag = None
        modified = None
        if self.linkHistory.has_key(url):
            if self.linkHistory[url].has_key('etag'):
                etag = self.linkHistory[url]['etag']
            if self.linkHistory[url].has_key('modified'):
                modified = self.linkHistory[url]['modified']
        def callback(info):
            if not self.ufeed.idExists():
                return
            self.downloads.discard(download)
            try:
                self.processDownloadedHTML(info, urlList, depth, linkNumber, top)
            finally:
                self.checkDone()
        def errback(error):
            if not self.ufeed.idExists():
                return
            self.downloads.discard(download)
            logging.info("WARNING unhandled error for ScraperFeedImpl.getHTML: %s", error)
            self.checkDone()
        download = grabURL(url, callback, errback, etag=etag,
                modified=modified,defaultMimeType='text/html',)
        self.downloads.add(download)

    def processDownloadedHTML(self, info, urlList, depth, linkNumber, top=False):
        self.ufeed.confirm_db_thread()
        #print "Done grabbing %s" % info['updated-url']

        if not self.tempHistory.has_key(info['updated-url']):
            self.tempHistory[info['updated-url']] = {}
        if info.has_key('etag'):
            self.tempHistory[info['updated-url']]['etag'] = unicodify(info['etag'])
        if info.has_key('last-modified'):
            self.tempHistory[info['updated-url']]['modified'] = unicodify(info['last-modified'])

        if (info['status'] != 304) and (info.has_key('body')):
            if info.has_key('charset'):
                subLinks = self.scrapeLinks(info['body'], info['redirected-url'], charset=info['charset'], setTitle=top)
            else:
                subLinks = self.scrapeLinks(info['body'], info['redirected-url'], setTitle=top)
            if top:
                self.processLinks(subLinks, 0, linkNumber)
            else:
                self.processLinks(subLinks, depth+1, linkNumber)
        if len(urlList) > 0:
            self.getHTML(urlList, depth, linkNumber)

    def checkDone(self):
        if len(self.downloads) == 0:
            self.saveCacheHistory()
            self.updating = False
            self.ufeed.signal_change()
            self.scheduleUpdateEvents(-1)

    def addVideoItem(self, link, dict_, linkNumber):
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
            i = itemmod.Item(FeedParserDict({'title': title,
                                             'enclosures': [FeedParserDict({'url': link,
                                                                            'thumbnail': FeedParserDict({'url': dict_['thumbnail']})
                                                                          })]
                                           }),
                             linkNumber=linkNumber, feed_id=self.ufeed.id)
        else:
            i = itemmod.Item(FeedParserDict({'title': title,
                                             'enclosures': [FeedParserDict({'url': link})]
                                           }),
                             linkNumber=linkNumber, feed_id=self.ufeed.id)
        if (self.ufeed.searchTerm is not None and 
                not i.matches_search(self.ufeed.searchTerm)):
            i.remove()
            return

    def processLinks(self, links, depth=0, linkNumber=0):
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
                    self.addVideoItem(link, links[link], linkNumber)
            if len(newURLs) > 0:
                self.getHTML(newURLs, depth, linkNumber)

    def onRemove(self):
        for download in self.downloads:
            logging.info("canceling download: %s", download.url)
            download.cancel()
        self.downloads = set()

    def update(self):
        # FIXME: go through and add error handling
        self.ufeed.confirm_db_thread()
        if not self.ufeed.idExists():
            return
        if self.updating:
            return
        else:
            self.updating = True
            self.ufeed.signal_change(needsSave=False)

        if not self.initialHTML is None:
            html = self.initialHTML
            self.initialHTML = None
            redirURL = self.url
            status = 200
            charset = self.initialCharset
            self.initialCharset = None
            subLinks = self.scrapeLinks(html, redirURL, charset=charset, setTitle=True)
            self.processLinks(subLinks, 0, 0)
            self.checkDone()
        else:
            self.getHTML([self.url], top=True)

    def scrapeLinks(self, html, baseurl, setTitle=False, charset=None):
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
            except IOError, e:
                pass
            except AttributeError:
                # bug in the python standard library causes this to be raised
                # sometimes.  See #3201.
                pass
            links = handler.links
            linkDict = {}
            for link in links:
                if link[0].startswith('http://') or link[0].startswith('https://'):
                    if not linkDict.has_key(toUni(link[0], charset)):
                        linkDict[toUni(link[0], charset)] = {}
                    if not link[1] is None:
                        linkDict[toUni(link[0], charset)]['title'] = toUni(link[1], charset).strip()
                    if not link[2] is None:
                        linkDict[toUni(link[0], charset)]['thumbnail'] = toUni(link[2], charset)
            if setTitle and not handler.title is None:
                self.ufeed.confirm_db_thread()
                try:
                    self.title = toUni(handler.title, charset)
                finally:
                    self.ufeed.signal_change()
            return ([x[0] for x in links if x[0].startswith('http://') or x[0].startswith('https://')], linkDict)
        except (xml.sax.SAXException, ValueError, IOError, xml.sax.SAXNotRecognizedException):
            (links, linkDict) = self.scrapeHTMLLinks(html, baseurl, setTitle=setTitle, charset=charset)
            return (links, linkDict)

    def scrapeHTMLLinks(self, html, baseurl, setTitle=False, charset=None):
        """Given a string containing an HTML file, return a dictionary of
        links to titles and thumbnails
        """
        lg = HTMLLinkGrabber()
        links = lg.get_links(html, baseurl)
        if setTitle and not lg.title is None:
            self.ufeed.confirm_db_thread()
            try:
                self.title = toUni(lg.title, charset)
            finally:
                self.ufeed.signal_change()

        linkDict = {}
        for link in links:
            if link[0].startswith('http://') or link[0].startswith('https://'):
                if not linkDict.has_key(toUni(link[0], charset)):
                    linkDict[toUni(link[0], charset)] = {}
                if not link[1] is None:
                    linkDict[toUni(link[0], charset)]['title'] = toUni(link[1], charset).strip()
                if not link[2] is None:
                    linkDict[toUni(link[0], charset)]['thumbnail'] = toUni(link[2], charset)
        return ([x[0] for x in links if x[0].startswith('http://') or x[0].startswith('https://')], linkDict)

    def setup_restored(self):
        """Called by pickle during deserialization
        """
        FeedImpl.setup_restored(self)
        self.downloads = set()
        self.tempHistory = {}

class DirectoryWatchFeedImpl(FeedImpl):
    def setup_new(self, ufeed, directory):
        # calculate url and title arguments to FeedImpl's constructor
        if directory is not None:
            url = u"dtv:directoryfeed:%s" % makeURLSafe(directory)
        else:
            url = u"dtv:directoryfeed"
        title = directory
        if title[-1] == '/':
            title = title[:-1]
        title = filenameToUnicode(os.path.basename(title)) + "/"

        FeedImpl.setup_new(self, url=url, ufeed=ufeed, title=title)
        self.dir = directory
        self.firstUpdate = True
        self.setUpdateFrequency(5)
        self.scheduleUpdateEvents(0)

    def expire_items(self):
        """Directory Items shouldn't automatically expire
        """
        pass

    def setUpdateFrequency(self, frequency):
        newFreq = frequency*60
        if newFreq != self.updateFreq:
            self.updateFreq = newFreq
            self.scheduleUpdateEvents(-1)

    def update(self):
        self.ufeed.confirm_db_thread()

        # Files known about by real feeds (other than other directory
        # watch feeds)
        known_files = set()
        for item in itemmod.Item.toplevel_view():
            if not item.get_feed().get_url().startswith("dtv:directoryfeed"):
                known_files.add(item.get_filename())

        # Remove items that are in feeds, but we have in our list
        for item in self.items:
            if item.get_filename() in known_files:
                item.remove()

        # Now that we've checked for items that need to be removed, we
        # add our items to known_files so that they don't get added
        # multiple times to this feed.
        for x in self.items:
            known_files.add(x.get_filename())

        # adds any files we don't know about on the filesystem
        if fileutil.isdir(self.dir):
            all_files = fileutil.miro_allfiles(self.dir)
            for file_ in all_files:
                ufile = filenameToUnicode(file_)
                if (file_ not in known_files
                        and (filetypes.is_video_filename(ufile) or filetypes.is_audio_filename(ufile))):
                    itemmod.FileItem(file_, feed_id=self.ufeed.id)

        for item in self.items:
            if not fileutil.isfile(item.get_filename()):
                item.remove()
        if self.firstUpdate:
            for item in self.items:
                item.mark_item_seen()
            self.firstUpdate = False

        self.scheduleUpdateEvents(-1)

class DirectoryFeedImpl(FeedImpl):
    """A feed of all of the Movies we find in the movie folder that don't
    belong to a "real" feed.  If the user changes her movies folder, this feed
    will continue to remember movies in the old folder.
    """
    def setup_new(self, ufeed):
        FeedImpl.setup_new(self, url=u"dtv:directoryfeed", ufeed=ufeed,title=u"Feedless Videos")

        self.setUpdateFrequency(5)
        self.scheduleUpdateEvents(0)

    def expire_items(self):
        """Directory Items shouldn't automatically expire
        """
        pass

    def setUpdateFrequency(self, frequency):
        newFreq = frequency*60
        if newFreq != self.updateFreq:
            self.updateFreq = newFreq
            self.scheduleUpdateEvents(-1)

    def update(self):
        # FIXME - this method and the fileutils.miro_allfiles methods
        # should be re-written to better handle U3/PortableApps-style 
        # pathnames, case-insensitive file-systems, and file-systems 
        # that do 8.3 paths.  what we have here is a veritable mess.
        self.ufeed.confirm_db_thread()
        movies_dir = config.get(prefs.MOVIES_DIRECTORY)
        # files known about by real feeds
        known_files = set()
        for item in itemmod.Item.toplevel_view():
            if item.feed_id is not self.ufeed.id:
                known_files.add(item.get_filename())
            if item.isContainerItem:
                item.find_new_children()

        incomplete_dir = os.path.join(movies_dir, "Incomplete Downloads")
        known_files.add(incomplete_dir)

        known_files = set([os.path.normcase(k) for k in known_files])

        # remove items that are in feeds, but we have in our list
        for item in self.items:
            if os.path.normcase(item.get_filename()) in known_files:
                item.remove()

        # now that we've checked for items that need to be removed, we
        # add our items to known_files so that they don't get added
        # multiple times to this feed.
        for x in self.items:
            known_files.add(os.path.normcase(x.get_filename()))

        # adds any files we don't know about
        # files on the filesystem
        if fileutil.isdir(movies_dir):
            all_files = fileutil.miro_allfiles(movies_dir)
            for file_ in all_files:
                file_ = os.path.normcase(file_)
                # FIXME - this prevents files from ANY Incomplete Downloads
                # directory which isn't quite right.
                if (file_ not in known_files
                        and not "incomplete downloads" in file_.lower()
                        and filetypes.is_video_filename(filenameToUnicode(file_))):
                    itemmod.FileItem(file_, feed_id=self.ufeed.id)

        for item in self.items:
            if not fileutil.exists(item.get_filename()):
                item.remove()

        self.scheduleUpdateEvents(-1)

class SearchFeedImpl(RSSMultiFeedImpl):
    """Search and Search Results feeds
    """
    def setup_new(self, ufeed):
        RSSMultiFeedImpl.setup_new(self, url=u'', ufeed=ufeed, title=u'dtv:search')
        self.initialUpdate = True
        self.searching = False
        self.lastEngine = searchengines.get_search_engines()[0].name
        self.lastQuery = u''
        self.query = u''
        self.setUpdateFrequency(-1)
        self.ufeed.autoDownloadable = False
        self.ufeed.signal_change()

    @returnsUnicode
    def quoteLastQuery(self):
        return escape(self.lastQuery)

    @returnsUnicode
    def get_url(self):
        return u'dtv:search'

    @returnsUnicode
    def get_title(self):
        return _(u'Search')

    @returnsUnicode
    def getStatus(self):
        status = u'idle-empty'
        if self.searching:
            status =  u'searching'
        elif len(self.items) > 0:
            status =  u'idle-with-results'
        elif self.url:
            status = u'idle-no-results'
        return status

    def _reset_downloads(self):
        for dc in self.download_dc.values():
            dc.cancel()
        self.download_dc = {}
        self.updating = 0

    def reset(self, url=u'', searchState=False):
        self.ufeed.confirm_db_thread()
        was_searching = self.searching
        try:
            self._reset_downloads()
            self.initialUpdate = True
            for item in self.items:
                item.remove()
            self.url = url
            self.splitURLs()
            self.searching = searchState
            self.etag = {}
            self.modified = {}
            self.title = self.url
            self.ufeed.icon_cache.reset()
            self.thumbURL = default_feed_icon_url()
            self.ufeed.icon_cache.request_update(is_vital=True)
        finally:
            self.ufeed.signal_change()
        if was_searching:
            self.ufeed.emit('update-finished')

    def preserveDownloads(self, downloadsFeed):
        self.ufeed.confirm_db_thread()
        for item in self.items:
            if item.get_state() not in ('new', 'not-downloaded'):
                item.setFeed(downloadsFeed.id)

    def set_info(self, engine, query):
        self.lastEngine = engine
        self.lastQuery = query

    def lookup(self, engine, query):
        checkU(engine)
        checkU(query)
        url = searchengines.get_request_url(engine, query)
        self.reset(url, True)
        self.lastQuery = query
        self.lastEngine = engine
        self.update()
        self.ufeed.signal_change()

    def _handleNewEntry(self, entry, channelTitle):
        """Handle getting a new entry from a feed."""
        fp_values = itemmod.FeedParserValues(entry)
        url = fp_values.data['url']
        if url is not None:
            dl = downloader.get_existing_downloader_by_url(url)
            if dl is not None:
                for item in dl.itemList:
                    if item.get_feed_url() == 'dtv:searchDownloads' and item.get_url() == url:
                        try:
                            if entry["id"] == item.getRSSID():
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
        RSSMultiFeedImpl._handleNewEntry(self, entry, channelTitle)

    def update_finished(self, old_items):
        self.searching = False
        # keeps the items from being seen as 'newly available'
        self.ufeed.mark_as_viewed()
        RSSMultiFeedImpl.update_finished(self, old_items)

    def update(self):
        if self.url is not None and self.url != u'':
            RSSMultiFeedImpl.update(self)
        else:
            self.ufeed.emit('update-finished')

class SearchDownloadsFeedImpl(FeedImpl):
    def setup_new(self, ufeed):
        FeedImpl.setup_new(self, url=u'dtv:searchDownloads', ufeed=ufeed,
                title=None)
        self.setUpdateFrequency(-1)

    @returnsUnicode
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
        self.setUpdateFrequency(-1)

    def setup_common(self):
        FeedImpl.setup_common()
        self.ufeed.last_viewed = datetime.max

    @returnsUnicode
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
        self.setUpdateFrequency(-1)

    @returnsUnicode
    def get_title(self):
        return _(u'Playing File')

class HTMLLinkGrabber(HTMLParser):
    """Parse HTML document and grab all of the links and their title
    """
    # FIXME: Grab link title from ALT tags in images
    # FIXME: Grab document title from TITLE tags
    linkPattern = re.compile("<(a|embed)\s[^>]*(href|src)\s*=\s*\"([^\"]*)\"[^>]*>(.*?)</a(.*)", re.S)
    imgPattern = re.compile(".*<img\s.*?src\s*=\s*\"(.*?)\".*?>", re.S)
    tagPattern = re.compile("<.*?>")
    def get_links(self, data, baseurl):
        self.links = []
        self.lastLink = None
        self.inLink = False
        self.inObject = False
        self.baseurl = baseurl
        self.inTitle = False
        self.title = None
        self.thumbnailUrl = None

        match = HTMLLinkGrabber.linkPattern.search(data)
        while match:
            try:
                linkURL = match.group(3).encode('ascii')
            except UnicodeError:
                linkURL = match.group(3)
                i = len (linkURL) - 1
                while (i >= 0):
                    if 127 < ord(linkURL[i]) <= 255:
                        linkURL = linkURL[:i] + "%%%02x" % (ord(linkURL[i])) + linkURL[i+1:]
                    i = i - 1

            link = urljoin(baseurl, linkURL)
            desc = match.group(4)
            imgMatch = HTMLLinkGrabber.imgPattern.match(desc)
            if imgMatch:
                try:
                    thumb = urljoin(baseurl, imgMatch.group(1).encode('ascii'))
                except UnicodeError:
                    thumb = None
            else:
                thumb = None
            desc =  HTMLLinkGrabber.tagPattern.sub(' ', desc)
            self.links.append((link, desc, thumb))
            match = HTMLLinkGrabber.linkPattern.search(match.group(5))
        return self.links

class RSSLinkGrabber(xml.sax.handler.ContentHandler, xml.sax.handler.ErrorHandler):
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
                html = xhtmlify(unescape(self.descHTML), addTopTags=True)
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
        eventloop.addTimeout(300, expire_items, "Expire Items")

def get_feed_by_url(url):
    try:
        return Feed.get_by_url(url)
    except ObjectNotFoundError:
        return None

def remove_orphaned_feed_impls():
    for klass in (FeedImpl, RSSFeedImpl, RSSMultiFeedImpl,
            ScraperFeedImpl, SearchFeedImpl, DirectoryFeedImpl,
            DirectoryWatchFeedImpl, SearchDownloadsFeedImpl,):
        for feed_impl in klass.orphaned_view():
            logging.warn("No feed for FeedImpl: %s.  Discarding", feed_impl)
            feed_impl.remove()

restored_feeds = []
def start_updates():
    global restored_feeds
    if config.get(prefs.CHECK_CHANNELS_EVERY_X_MN) == -1:
        return
    for feed in restored_feeds:
        if feed.idExists():
            feed.update_after_restore()
    restored_feeds = []
