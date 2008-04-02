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


from HTMLParser import HTMLParser,HTMLParseError
from cStringIO import StringIO
from copy import copy
from datetime import datetime, timedelta
from miro.gtcache import gettext as _
from miro.feedparser import FeedParserDict
from inspect import isfunction
from new import instancemethod
from urlparse import urlparse, urljoin
from miro.xhtmltools import unescape,xhtmlify,fixXMLHeader, fixHTMLHeader, urlencode, urldecode
import os
import string
import re
import traceback
import xml

from miro.database import defaultDatabase, DatabaseConstraintError, DDBObject
from miro.databasehelper import makeSimpleGetSet
from miro.httpclient import grabURL, NetworkError
from string import Template
from miro import app
from miro import config
from miro import iconcache
from miro import dialogs
from miro import eventloop
from miro import filters
from miro import folder
from miro import prefs
from miro.platform import resources
from miro import downloader
from miro.util import (returnsUnicode, unicodify, chatter, checkU, checkF, quoteUnicodeURL, getFirstVideoEnclosure, escape, toUni)
from miro.fileutil import miro_listdir, miro_allfiles
from miro.platform.utils import filenameToUnicode, makeURLSafe, unmakeURLSafe, osFilenameToFilenameType, FilenameType
from miro import filetypes
from miro import item as itemmod
from miro import views
from miro import indexes
from miro import searchengines
from miro import sorts
import logging
import shutil
from miro.clock import clock

whitespacePattern = re.compile(r"^[ \t\r\n]*$")

@returnsUnicode
def defaultFeedIconURL():
    return resources.url(u"images/feedicon.png")

@returnsUnicode
def defaultFeedIconURLTablist():
    return resources.url(u"images/feedicon-tablist.png")

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

#
# Adds a new feed using USM
def addFeedFromFile(file):
    checkF(file)
    d = feedparser.parse(file)
    if d.feed.has_key('links'):
        for link in d.feed['links']:
            if link['rel'] == 'start' or link['rel'] == 'self':
                Feed(link['href'])
                return
    if d.feed.has_key('link'):
        addFeedFromWebPage(d.feed.link)

#
# Adds a new feed based on a link tag in a web page
def addFeedFromWebPage(url):
    checkU(url)
    def callback(info):
        url = HTMLFeedURLParser().getLink(info['updated-url'],info['body'])
        if url:
            Feed(url)
    def errback(error):
        logging.warning ("unhandled error in addFeedFromWebPage: %s", error)
    grabURL(url, callback, errback)

# URL validitation and normalization
def validateFeedURL(url):
    checkU(url)
    for c in url.encode('utf8'):
        if ord(c) > 127:
            return False
    if re.match(r"^(http|https)://[^/ ]+/[^ ]*$", url) is not None:
        return True
    if re.match(r"^file://.", url) is not None:
        return True
    match = re.match(r"^dtv:searchTerm:(.*)\?(.*)$", url)
    if match is not None and validateFeedURL(urldecode(match.group(1))):
        return True
    match = re.match(r"^dtv:multi:", url)
    if match is not None:
        return True
    return False

def normalizeFeedURL(url):
    checkU(url)
    # Valid URL are returned as-is
    if validateFeedURL(url):
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
        url = "%s://%s" % match.group(1,2)

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

    if not validateFeedURL(url):
        logging.info ("unable to normalize URL %s", originalURL)
        return originalURL
    else:
        return url


##
# Handle configuration changes so we can update feed update frequencies

def configDidChange(key, value):
    if key is prefs.CHECK_CHANNELS_EVERY_X_MN.key:
        for feed in views.feeds:
            updateFreq = 0
            try:
                updateFreq = feed.parsed["feed"]["ttl"]
            except:
                pass
            feed.setUpdateFrequency(updateFreq)

config.addChangeCallback(configDidChange)

##
# Actual implementation of a basic feed.
class FeedImpl:
    def __init__(self, url, ufeed, title = None, visible = True):
        checkU(url)
        if title:
            checkU(title)
        self.url = url
        self.ufeed = ufeed
        self.calc_item_list()
        self.title = title
        self.created = datetime.now()
        self.visible = visible
        self.updating = False
        self.lastViewed = datetime.min
        self.thumbURL = defaultFeedIconURL()
        self.initialUpdate = True
        self.updateFreq = config.get(prefs.CHECK_CHANNELS_EVERY_X_MN)*60

    def calc_item_list(self):
        self.items = views.toplevelItems.filterWithIndex(indexes.itemsByFeed, self.ufeed.id)
        self.availableItems = self.items.filter(lambda x: x.getState() == 'new')
        self.unwatchedItems = self.items.filter(lambda x: x.getState() == 'newly-downloaded')
        self.availableItems.addAddCallback(lambda x,y:self.ufeed.signalChange(needsSignalFolder = True))
        self.availableItems.addRemoveCallback(lambda x,y:self.ufeed.signalChange(needsSignalFolder = True))
        self.unwatchedItems.addAddCallback(lambda x,y:self.ufeed.signalChange(needsSignalFolder = True))
        self.unwatchedItems.addRemoveCallback(lambda x,y:self.ufeed.signalChange(needsSignalFolder = True))
        
    def signalChange(self):
        self.ufeed.signalChange()

    @returnsUnicode
    def getBaseHref(self):
        """Get a URL to use in the <base> tag for this channel.  This is used
        for relative links in this channel's items.
        """
        return escape(self.url)

    # Sets the update frequency (in minutes). 
    # - A frequency of -1 means that auto-update is disabled.
    def setUpdateFrequency(self, frequency):
        try:
            frequency = int(frequency)
        except ValueError:
            frequency = -1

        if frequency < 0:
            self.cancelUpdateEvents()
            self.updateFreq = -1
        else:
            newFreq = max(config.get(prefs.CHECK_CHANNELS_EVERY_X_MN),
                          frequency)*60
            if newFreq != self.updateFreq:
                self.updateFreq = newFreq
                self.scheduleUpdateEvents(-1)
        self.ufeed.signalChange()

    def scheduleUpdateEvents(self, firstTriggerDelay):
        self.cancelUpdateEvents()
        if firstTriggerDelay >= 0:
            self.scheduler = eventloop.addTimeout(firstTriggerDelay, self.update, "Feed update (%s)" % self.getTitle())
        else:
            if self.updateFreq > 0:
                self.scheduler = eventloop.addTimeout(self.updateFreq, self.update, "Feed update (%s)" % self.getTitle())

    def cancelUpdateEvents(self):
        if hasattr(self, 'scheduler') and self.scheduler is not None:
            self.scheduler.cancel()
            self.scheduler = None

    # Subclasses should override this
    def update(self):
        self.scheduleUpdateEvents(-1)

    # Returns true iff this feed has been looked at
    def getViewed(self):
        return self.lastViewed != datetime.min

    # Returns the ID of the actual feed, never that of the UniversalFeed wrapper
    def getFeedID(self):
        return self.getID()

    def getID(self):
        try:
            return self.ufeed.getID()
        except:
            logging.info ("%s has no ufeed", self)

    # Returns string with number of unwatched videos in feed
    def numUnwatched(self):
        return len(self.unwatchedItems)

    # Returns string with number of available videos in feed
    def numAvailable(self):
        return len(self.availableItems)

    # Returns true iff both unwatched and available numbers should be shown
    def showBothUAndA(self):
        return self.showU() and self.showA()

    # Returns true iff unwatched should be shown 
    def showU(self):
        return len(self.unwatchedItems) > 0

    # Returns true iff available should be shown
    def showA(self):
        return len(self.availableItems) > 0 and not self.isAutoDownloadable()

    ##
    # Sets the last time the feed was viewed to now
    def markAsViewed(self):
        self.lastViewed = datetime.now() 
        for item in self.items:
            if item.getState() == "new":
                item.signalChange(needsSave=False)

        self.ufeed.signalChange()

    ##
    # Returns true iff the feed is loading. Only makes sense in the
    # context of UniversalFeeds
    def isLoading(self):
        return False

    ##
    # Returns true iff this feed has a library
    def hasLibrary(self):
        return False

    def startManualDownload(self):
        next = None
        for item in self.items:
            if item.isPendingManualDownload():
                if next is None:
                    next = item
                elif item.getPubDateParsed() > next.getPubDateParsed():
                    next = item
        if next is not None:
            next.download(autodl = False)

    def startAutoDownload(self):
        next = None
        for item in self.items:
            if item.isEligibleForAutoDownload():
                if next is None:
                    next = item
                elif item.getPubDateParsed() > next.getPubDateParsed():
                    next = item
        if next is not None:
            next.download(autodl = True)

    ##
    # Returns marks expired items as expired
    def expireItems(self):
        for item in self.items:
            expireTime = item.getExpirationTime()
            if (item.getState() == 'expiring' and expireTime is not None and 
                    expireTime < datetime.now()):
                item.executeExpire()

    ##
    # Returns true iff feed should be visible
    def isVisible(self):
        self.ufeed.confirmDBThread()
        return self.visible

    def signalItems (self):
        for item in self.items:
            item.signalChange(needsSave=False)

    ##
    # Return the 'system' expiration delay, in days (can be < 1.0)
    def getDefaultExpiration(self):
        return float(config.get(prefs.EXPIRE_AFTER_X_DAYS))

    ##
    # Returns the 'system' expiration delay as a formatted string
    @returnsUnicode
    def getFormattedDefaultExpiration(self):
        expiration = self.getDefaultExpiration()
        formattedExpiration = u''
        if expiration < 0:
            formattedExpiration = _('never')
        elif expiration < 1.0:
            formattedExpiration = _('%d hours') % int(expiration * 24.0)
        elif expiration == 1:
            formattedExpiration = _('%d day') % int(expiration)
        elif expiration > 1 and expiration < 30:
            formattedExpiration = _('%d days') % int(expiration)
        elif expiration >= 30:
            formattedExpiration = _('%d months') % int(expiration / 30)
        return formattedExpiration

    ##
    # Returns "feed," "system," or "never"
    @returnsUnicode
    def getExpirationType(self):
        self.ufeed.confirmDBThread()
        return self.ufeed.expire

    ##
    # Returns"unlimited" or the maximum number of items this feed can fall behind
    def getMaxFallBehind(self):
        self.ufeed.confirmDBThread()
        if self.ufeed.fallBehind < 0:
            return u"unlimited"
        else:
            return self.ufeed.fallBehind

    ##
    # Returns "unlimited" or the maximum number of items this feed wants
    def getMaxNew(self):
        self.ufeed.confirmDBThread()
        if self.ufeed.maxNew < 0:
            return u"unlimited"
        else:
            return self.ufeed.maxNew

    ##
    # Returns the total absolute expiration time in hours.
    # WARNING: 'system' and 'never' expiration types return 0
    def getExpirationTime(self):
        delta = None
        self.ufeed.confirmDBThread()
        expireAfterSetting = config.get(prefs.EXPIRE_AFTER_X_DAYS)
        if (self.ufeed.expireTime is None or self.ufeed.expire == 'never' or 
            (self.ufeed.expire == 'system' and expireAfterSetting <= 0)):
            return 0
        else:
            return (self.ufeed.expireTime.days * 24 + 
                    self.ufeed.expireTime.seconds / 3600)

    ##
    # Returns the number of days until a video expires
    def getExpireDays(self):
        ret = 0
        self.ufeed.confirmDBThread()
        try:
            return self.ufeed.expireTime.days
        except:
            return timedelta(days=config.get(prefs.EXPIRE_AFTER_X_DAYS)).days

    ##
    # Returns the number of hours until a video expires
    def getExpireHours(self):
        ret = 0
        self.ufeed.confirmDBThread()
        try:
            return int(self.ufeed.expireTime.seconds/3600)
        except:
            return int(timedelta(days=config.get(prefs.EXPIRE_AFTER_X_DAYS)).seconds/3600)

    def getExpires (self):
        expireAfterSetting = config.get(prefs.EXPIRE_AFTER_X_DAYS)
        return (self.ufeed.expireTime is None or self.ufeed.expire == 'never' or 
                (self.ufeed.expire == 'system' and expireAfterSetting <= 0))

    ##
    # Returns true iff item is autodownloadable
    def isAutoDownloadable(self):
        self.ufeed.confirmDBThread()
        return self.ufeed.autoDownloadable

    def autoDownloadStatus(self):
        status = self.isAutoDownloadable()
        if status:
            return u"ON"
        else:
            return u"OFF"

    ##
    # Returns the title of the feed
    @returnsUnicode
    def getTitle(self):
        try:
            title = self.title
            if title is None or whitespacePattern.match(title):
                if self.ufeed.baseTitle is not None:
                    title = self.ufeed.baseTitle
                else:
                    title = self.url
            return title
        except:
            return u""

    ##
    # Returns the URL of the feed
    @returnsUnicode
    def getURL(self):
        try:
            if self.ufeed.searchTerm is None:
                return self.url
            else:
                return u"dtv:searchTerm:%s?%s" % (urlencode(self.url), urlencode(self.ufeed.searchTerm))
        except:
            return u""

    ##
    # Returns the URL of the feed
    @returnsUnicode
    def getBaseURL(self):
        try:
            return self.url
        except:
            return u""

    ##
    # Returns the description of the feed
    @returnsUnicode
    def getDescription(self):
        return u"<span />"

    ##
    # Returns a link to a webpage associated with the feed
    @returnsUnicode
    def getLink(self):
        return self.ufeed.getBaseHref()

    ##
    # Returns the URL of the library associated with the feed
    @returnsUnicode
    def getLibraryLink(self):
        return u""

    ##
    # Returns the URL of a thumbnail associated with the feed
    @returnsUnicode
    def getThumbnailURL(self):
        return self.thumbURL

    # See item.getThumbnail to figure out which items to send signals for.
    def iconChanged(self, needsSave=True):
        self.ufeed.signalChange(needsSave=needsSave)
        for item in self.items:
            if not (item.iconCache.isValid() or
                    item.screenshot or
                    item.isContainerItem):
                item.signalChange(needsSave=False)

    ##
    # Returns URL of license assocaited with the feed
    @returnsUnicode
    def getLicense(self):
        return u""

    ##
    # Returns the number of new items with the feed
    def getNewItems(self):
        self.ufeed.confirmDBThread()
        count = 0
        for item in self.items:
            try:
                if item.getState() == u'newly-downloaded':
                    count += 1
            except:
                pass
        return count

    def onRestore(self):        
        self.updating = False
        self.calc_item_list()

    def onRemove(self):
        """Called when the feed uses this FeedImpl is removed from the DB.
        subclasses can perform cleanup here."""
        pass

    def __str__(self):
        return "FeedImpl - %s" % self.getTitle()

##
# This class is a magic class that can become any type of feed it wants
#
# It works by passing on attributes to the actual feed.
class Feed(DDBObject):
    ICON_CACHE_SIZES = [
        (20, 20),
        (76, 76),
    ]

    def __init__(self,url, initiallyAutoDownloadable=None):
        DDBObject.__init__(self, add=False)
        checkU(url)
        if initiallyAutoDownloadable == None:
            mode = config.get(prefs.CHANNEL_AUTO_DEFAULT)
            # note that this is somewhat duplicated in setAutoDownloadMode
            logging.info ("wbg: setting autodownload stuff initially to %s" % mode)
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

        self.maxNew = 3
        self.expire = u"system"
        self.expireTime = None
        self.fallBehind = -1

        self.baseTitle = None
        self.origURL = url
        self.errorState = False
        self.loading = True
        self.actualFeed = FeedImpl(url,self)
        self.iconCache = iconcache.IconCache(self, is_vital = True)
        self.informOnError = True
        self.folder_id = None
        self.searchTerm = None
        self.userTitle = None
        self._initRestore()
        self.dd.addAfterCursor(self)
        self.generateFeed(True)

    def signalChange (self, needsSave=True, needsSignalFolder=False):
        if needsSignalFolder:
            folder = self.getFolder()
            if folder:
                folder.signalChange(needsSave=False)
        DDBObject.signalChange (self, needsSave=needsSave)

    def _initRestore(self):
        self.download = None
        self.blinking = False
        self.itemSort = sorts.ItemSort()
        self.itemSortDownloading = sorts.ItemSort()
        self.itemSortWatchable = sorts.ItemSortUnwatchedFirst()
        self.inlineSearchTerm = None

    isBlinking, setBlinking = makeSimpleGetSet('blinking',
            changeNeedsSave=False)

    def setInlineSearchTerm(self, term):
        self.inlineSearchTerm = term

    def blink(self):
        self.setBlinking(True)
        def timeout():
            if self.idExists():
                self.setBlinking(False)
        eventloop.addTimeout(0.5, timeout, 'unblink feed')

    # Returns the ID of this feed. Deprecated.
    def getFeedID(self):
        return self.getID()

    def getID(self):
        return DDBObject.getID(self)

    def hasError(self):
        self.confirmDBThread()
        return self.errorState

    @returnsUnicode
    def getOriginalURL(self):
        self.confirmDBThread()
        return self.origURL

    @returnsUnicode
    def getSearchTerm(self):
        self.confirmDBThread()
        return self.searchTerm

    @returnsUnicode
    def getError(self):
        return u"Could not load feed"

    def isUpdating(self):
        return self.loading or (self.actualFeed and self.actualFeed.updating)

    def isScraped(self):
        return isinstance(self.actualFeed, ScraperFeedImpl)

    @returnsUnicode
    def getTitle(self):
        if self.userTitle is not None:
            return self.userTitle
        else:
            title = self.actualFeed.getTitle()
            if self.searchTerm is not None:
                title = u"'%s' on %s" % (self.searchTerm, title)
            return title

    def setTitle(self, title):
        self.confirmDBThread()
        self.userTitle = title
        self.signalChange()

    def unsetTitle(self):
        self.setTitle(None)

    ##
    # Set the baseTitle.
    @returnsUnicode
    def setBaseTitle(self, title):
        self.baseTitle = title
        self.signalChange()

    @returnsUnicode
    def getAutoDownloadMode(self):
        self.confirmDBThread()
        if self.autoDownloadable:
            if self.getEverything:
                return u'all'
            else:
                return u'new'
        else:
            return u'off'

    def setAutoDownloadMode(self, mode):
        # note that this is somewhat duplicated in __init__
        if mode == u'all':
            self.setGetEverything(True)
            self.setAutoDownloadable(True)
        elif mode == u'new':
            self.setGetEverything(False)
            self.setAutoDownloadable(True)
        elif mode == u'off':
            self.setAutoDownloadable(False)
        else:
            raise ValueError("Bad auto-download mode: %s" % mode)

    def getCurrentAutoDownloadableItems(self):
        auto = set()
        for item in self.items:
            if item.isPendingAutoDownload():
                auto.add(item)
        return auto

    ##
    # Switch the auto-downloadable state
    def setAutoDownloadable(self, automatic):
        self.confirmDBThread()
        if self.autoDownloadable == automatic:
            return
        self.autoDownloadable = automatic

        if self.autoDownloadable:
            # When turning on auto-download, existing items shouldn't be
            # considered "new"
            for item in self.items:
                if item.eligibleForAutoDownload:
                    item.eligibleForAutoDownload = False
                    item.signalChange()

        for item in self.items:
            if item.isEligibleForAutoDownload():
                item.signalChange(needsSave=False)

        self.signalChange()

    ##
    # Sets the 'getEverything' attribute, True or False
    def setGetEverything(self, everything):
        self.confirmDBThread()
        if everything == self.getEverything:
            return
        if not self.autoDownloadable:
            self.getEverything = everything
            self.signalChange()
            return

        updates = set()
        if everything:
            for item in self.items:
                if not item.isEligibleForAutoDownload():
                    updates.add(item)
        else:
            for item in self.items:
                if item.isEligibleForAutoDownload():
                    updates.add(item)

        self.getEverything = everything
        self.signalChange()

        if everything:
            for item in updates:
                if item.isEligibleForAutoDownload():
                    item.signalChange(needsSave=False)
        else:
            for item in updates:
                if not item.isEligibleForAutoDownload():
                    item.signalChange(needsSave=False)

    ##
    # Sets the expiration attributes. Valid types are 'system', 'feed' and 'never'
    # Expiration time is in hour(s).
    def setExpiration(self, type, time):
        self.confirmDBThread()
        self.expire = type
        self.expireTime = timedelta(hours=time)

        if self.expire == "never":
            for item in self.items:
                if item.isDownloaded():
                    item.save()

        self.signalChange()
        for item in self.items:
            item.signalChange(needsSave=False)

    ##
    # Sets the maxNew attributes. -1 means unlimited.
    def setMaxNew(self, maxNew):
        self.confirmDBThread()
        oldMaxNew = self.maxNew
        self.maxNew = maxNew
        self.signalChange()
#        for item in self.items:
#            item.signalChange(needsSave=False)
        if self.maxNew >= oldMaxNew or self.maxNew < 0:
            from miro import autodler
            autodler.autoDownloader.startDownloads()

    def rename(self):
        title = _("Rename Channel")
        text = _("Enter a new name for the channel %s" % self.getTitle())
        def callback(dialog):
            if self.idExists() and dialog.choice == dialogs.BUTTON_OK:
                self.setTitle(dialog.value)
        dialogs.TextEntryDialog(title, text, dialogs.BUTTON_OK,
            dialogs.BUTTON_CANCEL, prefillCallback=lambda:self.getTitle()).run(callback)

    def update(self):
        self.confirmDBThread()
        if not self.idExists():
            return
        if self.loading:
            return
        elif self.errorState:
            self.loading = True
            self.errorState = False
            self.signalChange()
            return self.generateFeed()
        self.actualFeed.update()

    def getFolder(self):
        self.confirmDBThread()
        if self.folder_id is not None:
            return self.dd.getObjectByID(self.folder_id)
        else:
            return None

    def setFolder(self, newFolder):
        self.confirmDBThread()
        oldFolder = self.getFolder()
        if newFolder is not None:
            self.folder_id = newFolder.getID()
        else:
            self.folder_id = None
        self.signalChange()
        for item in self.items:
            item.signalChange(needsSave=False, needsUpdateXML=False)
        if newFolder:
            newFolder.signalChange(needsSave=False)
        if oldFolder:
            oldFolder.signalChange(needsSave=False)

    def generateFeed(self, removeOnError=False):
        newFeed = None
        if (self.origURL == u"dtv:directoryfeed"):
            newFeed = DirectoryFeedImpl(self)
        elif (self.origURL.startswith(u"dtv:directoryfeed:")):
            url = self.origURL[len(u"dtv:directoryfeed:"):]
            dir = unmakeURLSafe(url)
            newFeed = DirectoryWatchFeedImpl(self, dir)
        elif (self.origURL == u"dtv:search"):
            newFeed = SearchFeedImpl(self)
        elif (self.origURL == u"dtv:searchDownloads"):
            newFeed = SearchDownloadsFeedImpl(self)
        elif (self.origURL == u"dtv:manualFeed"):
            newFeed = ManualFeedImpl(self)
        elif (self.origURL == u"dtv:singleFeed"):
            newFeed = SingleFeedImpl(self)
        elif (self.origURL.startswith (u"dtv:multi:")):
            newFeed = RSSMultiFeedImpl(self.origURL, self)
        elif (self.origURL.startswith (u"dtv:searchTerm:")):

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
            if url.startswith (u"dtv:multi:"):
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
            self.actualFeed = newFeed
            self.loading = False

            self.signalChange()

    def _handleFeedLoadingError(self, errorDescription):
        self.download = None
        self.errorState = True
        self.loading = False
        self.signalChange()
        if self.informOnError:
            title = _('Error loading feed')
            description = _("Couldn't load the feed at %s (%s).") % (
                    self.url, errorDescription)
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
        logging.info ("Warning couldn't load feed at %s (%s)",
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
        if info['updated-url'] != self.origURL: # we got redirected
            f = getFeedByURL(info['updated-url'])
            if f is not None: # already have this feed, so delete us
                self.remove()
                return
        self.download = None
        modified = unicodify(info.get('last-modified'))
        etag = unicodify(info.get('etag'))
        contentType = unicodify(info.get('content-type', u'text/html'))
        
        # Some smarty pants serve RSS feeds with a text/html content-type...
        # So let's do some really simple sniffing first.
        apparentlyRSS = re.compile(r'<\?xml.*\?>\s*<rss').match(info['body']) is not None

        #Definitely an HTML feed
        if (contentType.startswith(u'text/html') or 
            contentType.startswith(u'application/xhtml+xml')) and not apparentlyRSS:
            #print "Scraping HTML"
            html = info['body']
            if info.has_key('charset'):
                html = fixHTMLHeader(html,info['charset'])
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
                xmldata = fixXMLHeader(html,info['charset'])
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
                xmldata = fixXMLHeader(html,info['charset'])
                html = fixHTMLHeader(html,info['charset'])
                charset = unicodify(info['charset'])
            else:
                xmldata = html
                charset = None
            # FIXME html and xmldata can be non-unicode at this point
            parser = xml.sax.make_parser()
            parser.setFeature(xml.sax.handler.feature_namespaces, 1)
            try: parser.setFeature(xml.sax.handler.feature_external_ges, 0)
            except: pass
            handler = RSSLinkGrabber(unicodify(info['redirected-url']),charset)
            parser.setContentHandler(handler)
            parser.setErrorHandler(handler)
            try:
                parser.parse(StringIO(xmldata))
            except UnicodeDecodeError:
                logging.exception ("Unicode issue parsing... %s", xmldata[0:300])
                self.finishGenerateFeed(None)
                if removeOnError:
                    self.remove()
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
        self.confirmDBThread()
        self.loading = False
        if feedImpl is not None:
            self.actualFeed = feedImpl
            self.errorState = False
        else:
            self.errorState = True
        self.signalChange()

    def askForScrape(self, info, initialHTML, charset):
        title = Template(_("Channel is not compatible with $shortAppName!")).substitute(shortAppName=config.get(prefs.SHORT_APP_NAME))
        descriptionTemplate = Template(_("""\
But we'll try our best to grab the files. It may take extra time to list the \
videos, and descriptions may look funny.  Please contact the publishers of \
$url and ask if they can supply a feed in a format that will work with \
$shortAppName.\n\nDo you want to try to load this channel anyway?"""))
        description = descriptionTemplate.substitute(url=info['updated-url'],
                                shortAppName=config.get(prefs.SHORT_APP_NAME))
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

    def __getattr__(self,attr):
        return getattr(self.actualFeed,attr)

    def remove(self, moveItemsTo=None):
        """Remove the feed.  If moveItemsTo is None (the default), the items
        in this feed will be removed too.  If moveItemsTo is given, the items
        in this feed will be moved to that feed.
        """

        self.confirmDBThread()

        if isinstance (self.actualFeed, DirectoryWatchFeedImpl):
            moveItemsTo = None
        self.cancelUpdateEvents()
        if self.download is not None:
            self.download.cancel()
            self.download = None
        for item in self.items:
            if moveItemsTo is not None and item.isDownloaded():
                item.setFeed(moveItemsTo.getID())
            else:
                item.remove()
        if self.iconCache is not None:
            self.iconCache.remove()
            self.iconCache = None
        DDBObject.remove(self)
        self.actualFeed.onRemove()

    @returnsUnicode
    def getThumbnail(self):
        self.confirmDBThread()
        if self.iconCache and self.iconCache.isValid():
            path = self.iconCache.getResizedFilename(76, 76)
            return resources.absoluteUrl(path)
        else:
            return defaultFeedIconURL()

    @returnsUnicode
    def getTablistThumbnail(self):
        self.confirmDBThread()
        if self.iconCache and self.iconCache.isValid():
            path = self.iconCache.getResizedFilename(20, 20)
            return resources.absoluteUrl(path)
        else:
            return defaultFeedIconURLTablist()

    @returnsUnicode
    def getItemThumbnail(self, width, height):
        self.confirmDBThread()
        if self.iconCache and self.iconCache.isValid():
            path = self.iconCache.getResizedFilename(width, height)
            return resources.absoluteUrl(path)
        else:
            return None

    def hasDownloadedItems(self):
        self.confirmDBThread()
        for item in self.items:
            if item.isDownloaded():
                return True
        return False

    def hasDownloadingItems(self):
        self.confirmDBThread()
        for item in self.items:
            if item.getState() in (u'downloading', u'paused'):
                return True
        return False

    def updateIcons(self):
        iconcache.iconCacheUpdater.clearVital()
        for item in self.items:
            item.iconCache.requestUpdate(True)
        for feed in views.feeds:
            feed.iconCache.requestUpdate(True)

    @returnsUnicode
    def getDragDestType(self):
        self.confirmDBThread()
        if self.folder_id is not None:
            return u'channel'
        else:
            return u'channel:channelfolder'

    def onRestore(self):
        if (self.iconCache == None):
            self.iconCache = iconcache.IconCache (self, is_vital = True)
        else:
            self.iconCache.dbItem = self
            self.iconCache.requestUpdate(True)
        self.informOnError = False
        self._initRestore()
        if self.actualFeed.__class__ == FeedImpl:
            # Our initial FeedImpl was never updated, call generateFeed again
            self.loading = True
            eventloop.addIdle(lambda:self.generateFeed(True), "generateFeed")

    def __str__(self):
        return "Feed - %s" % self.getTitle()

def _entry_equal(a, b):
    if type(a) == list and type(b) == list:
        if len(a) != len(b):
            return False
        for i in xrange (len(a)):
            if not _entry_equal(a[i], b[i]):
                return False
        return True
    try:
        return a.equal(b)
    except:
        try:
            return b.equal(a)
        except:
            return a == b

class RSSFeedImpl(FeedImpl):
    firstImageRE = re.compile('\<\s*img\s+[^>]*src\s*=\s*"(.*?)"[^>]*\>',re.I|re.M)
    
    def __init__(self,url,ufeed,title = None,initialHTML = None, etag = None, modified = None, visible=True):
        FeedImpl.__init__(self,url,ufeed,title,visible=visible)
        self.initialHTML = initialHTML
        self.etag = etag
        self.modified = modified
        self.download = None
        self.scheduleUpdateEvents(0)

    @returnsUnicode
    def getBaseHref(self):
        try:
            return escape(self.parsed.link)
        except:
            return FeedImpl.getBaseHref(self)

    ##
    # Returns the description of the feed
    @returnsUnicode
    def getDescription(self):
        self.ufeed.confirmDBThread()
        try:
            return xhtmlify(u'<span>'+unescape(self.parsed.feed.description)+u'</span>')
        except:
            return u"<span />"

    ##
    # Returns a link to a webpage associated with the feed
    @returnsUnicode
    def getLink(self):
        self.ufeed.confirmDBThread()
        try:
            return self.parsed.link
        except:
            return u""

    ##
    # Returns the URL of the library associated with the feed
    @returnsUnicode
    def getLibraryLink(self):
        self.ufeed.confirmDBThread()
        try:
            return self.parsed.libraryLink
        except:
            return u""

    def feedparser_finished (self):
        self.updating = False
        self.ufeed.signalChange(needsSave=False)
        self.scheduleUpdateEvents(-1)

    def feedparser_errback (self, e):
        if not self.ufeed.idExists():
            return
        logging.info ("Error updating feed: %s: %s", self.url, e)
        self.updating = False
        self.ufeed.signalChange()
        self.scheduleUpdateEvents(-1)

    def feedparser_callback (self, parsed):
        self.ufeed.confirmDBThread()
        if not self.ufeed.idExists():
            return
        start = clock()
        self.updateUsingParsed(parsed)
        self.feedparser_finished()
        end = clock()
        if end - start > 1.0:
            logging.timing ("feed update for: %s too slow (%.3f secs)", self.url, end - start)

    def call_feedparser (self, html):
        self.ufeed.confirmDBThread()
        in_thread = False
        if in_thread:
            try:
                parsed = feedparser.parse(html)
                self.updateUsingParsed(parsed)
            except:
                logging.warning ("Error updating feed: %s", self.url)
                self.updating = False
                self.ufeed.signalChange(needsSave=False)
                raise
            self.feedparser_finished()
        else:
            eventloop.callInThread (self.feedparser_callback, self.feedparser_errback, feedparser.parse, "Feedparser callback - %s" % self.url, html)

    ##
    # Updates a feed
    def update(self):
        self.ufeed.confirmDBThread()
        if not self.ufeed.idExists():
            return
        if self.updating:
            return
        else:
            self.updating = True
            self.ufeed.signalChange(needsSave=False)
        if hasattr(self, 'initialHTML') and self.initialHTML is not None:
            html = self.initialHTML
            self.initialHTML = None
            self.call_feedparser (html)
        else:
            try:
                etag = self.etag
            except:
                etag = None
            try:
                modified = self.modified
            except:
                modified = None
            self.download = grabURL(self.url, self._updateCallback,
                    self._updateErrback, etag=etag,modified=modified,defaultMimeType=u'application/rss+xml',)

    def _updateErrback(self, error):
        if not self.ufeed.idExists():
            return
        logging.info ("WARNING: error in Feed.update for %s -- %s", self.ufeed, error)
        self.scheduleUpdateEvents(-1)
        self.updating = False
        self.ufeed.signalChange(needsSave=False)

    def _updateCallback(self,info):
        if not self.ufeed.idExists():
            return
        if info.get('status') == 304:
            self.scheduleUpdateEvents(-1)
            self.updating = False
            self.ufeed.signalChange()
            return
        html = info['body']
        if info.has_key('charset'):
            html = fixXMLHeader(html,info['charset'])

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

    def _handleNewEntryForItem(self, item, entry, channelTitle):
        """Handle when we get a different entry for an item.

        This happens when the feed sets the RSS GUID attribute, then changes
        the entry for it.  Most of the time we will just update the item, but
        if the user has already downloaded the item then we need to make sure
        that we don't throw away the download.
        """

        videoEnc = getFirstVideoEnclosure(entry)
        if videoEnc is not None:
            entryURL = videoEnc.get('url')
        else:
            entryURL = None
        if item.isDownloaded() and item.getURL() != entryURL:
            item.removeRSSID()
            self._handleNewEntry(entry, channelTitle)
        else:
            item.update(entry)

    def _handleNewEntry(self, entry, channelTitle):
        """Handle getting a new entry from a feed."""
        item = itemmod.Item(entry, feed_id=self.ufeed.id)
        if not filters.matchingItems(item, self.ufeed.searchTerm):
            item.remove()
        item.setChannelTitle(channelTitle)

    def updateUsingParsed(self, parsed):
        """Update the feed using parsed XML passed in"""
        self.parsed = unicodify(parsed)

        # This is a HACK for Yahoo! search which doesn't provide
        # enclosures
        for entry in parsed['entries']:
            if 'enclosures' not in entry:
                try:
                    url = entry['link']
                except:
                    continue
                mimetype = filetypes.guessMimeType(url)
                if mimetype is not None:
                    entry['enclosures'] = [{'url':toUni(url), 'type':toUni(mimetype)}]
                else:
                    logging.info('unknown url type %s, not generating enclosure' % url)

        channelTitle = None
        try:
            channelTitle = self.parsed["feed"]["title"]
        except KeyError:
            try:
                channelTitle = self.parsed["channel"]["title"]
            except KeyError:
                pass
        if channelTitle != None:
            self.title = channelTitle
        if (self.parsed.feed.has_key('image') and 
            self.parsed.feed.image.has_key('url')):
            self.thumbURL = self.parsed.feed.image.url
            self.ufeed.iconCache.requestUpdate(is_vital=True)
        items_byid = {}
        items_byURLTitle = {}
        items_nokey = []
        old_items = set()
        for item in self.items:
            old_items.add(item)
            try:
                items_byid[item.getRSSID()] = item
            except KeyError:
                items_nokey.append (item)
            entry = item.getRSSEntry()
            videoEnc = getFirstVideoEnclosure(entry)
            if videoEnc is not None:
                entryURL = videoEnc.get('url')
            else:
                entryURL = None
            title = entry.get("title")
            if title is not None or entryURL is not None:
                items_byURLTitle[(entryURL, title)] = item
        for entry in self.parsed.entries:
            entry = self.addScrapedThumbnail(entry)
            new = True
            if entry.has_key("id"):
                id = entry["id"]
                if items_byid.has_key (id):
                    item = items_byid[id]
                    if not _entry_equal(entry, item.getRSSEntry()):
                        self._handleNewEntryForItem(item, entry, channelTitle)
                    new = False
                    old_items.discard(item)
            if new:
                videoEnc = getFirstVideoEnclosure(entry)
                if videoEnc is not None:
                    entryURL = videoEnc.get('url')
                else:
                    entryURL = None
                title = entry.get("title")
                if title is not None or entryURL is not None:
                    if items_byURLTitle.has_key ((entryURL, title)):
                        item = items_byURLTitle[(entryURL, title)]
                        if not _entry_equal(entry, item.getRSSEntry()):
                            self._handleNewEntryForItem(item, entry, channelTitle)
                        new = False
                        old_items.discard(item)
            if new:
                for item in items_nokey:
                    if _entry_equal(entry, item.getRSSEntry()):
                        new = False
                    else:
                        try:
                            if _entry_equal (entry["enclosures"], item.getRSSEntry()["enclosures"]):
                                self._handleNewEntryForItem(item, entry, channelTitle)
                                new = False
                                old_items.discard(item)
                        except:
                            pass
            if (new and entry.has_key('enclosures') and
                    getFirstVideoEnclosure(entry) != None):
                self._handleNewEntry(entry, channelTitle)
        try:
            updateFreq = self.parsed["feed"]["ttl"]
        except KeyError:
            updateFreq = 0
        self.setUpdateFrequency(updateFreq)
        
        if self.initialUpdate:
            self.initialUpdate = False
            startfrom = None
            itemToUpdate = None
            for item in self.items:
                itemTime = item.getPubDateParsed()
                if startfrom is None or itemTime > startfrom:
                    startfrom = itemTime
                    itemToUpdate = item
            for item in self.items:
                if item == itemToUpdate:
                    item.eligibleForAutoDownload = True
                else:
                    item.eligibleForAutoDownload = False
                item.signalChange()
            self.ufeed.signalChange()

        self.truncateOldItems(old_items)

    def truncateOldItems(self, old_items):
        """Truncate items so that the number of items in this feed doesn't
        exceed prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS.

        old_items should be an iterable that contains items that aren't in the
        feed anymore.

        Items are only truncated if they don't exist in the feed anymore, and
        if the user hasn't downloaded them.
        """
        limit = config.get(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS)
        extra = len(self.items) - limit
        if extra <= 0:
            return

        candidates = []
        for item in old_items:
            if item.downloader is None:
                candidates.append((item.creationTime, item))
        candidates.sort()
        for time, item in candidates[:extra]:
            item.remove()

    def addScrapedThumbnail(self,entry):
        # skip this if the entry already has a thumbnail.
        if entry.has_key('thumbnail'):
            return entry
        if entry.has_key('enclosures'):
            for enc in entry['enclosures']:
                if enc.has_key('thumbnail'):
                    return entry
        # try to scape the thumbnail from the description.
        if not entry.has_key('description'):
            return entry
        desc = RSSFeedImpl.firstImageRE.search(unescape(entry['description']))
        if not desc is None:
            entry['thumbnail'] = FeedParserDict({'url': desc.expand("\\1")})
        return entry

    ##
    # Returns the URL of the license associated with the feed
    @returnsUnicode
    def getLicense(self):
        try:
            ret = self.parsed.license
        except:
            ret = u""
        return ret

    def onRemove(self):
        if self.download is not None:
            self.download.cancel()
            self.download = None

    ##
    # Called by pickle during deserialization
    def onRestore(self):
        #self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.feed is self)
        #FIXME: the update dies if all of the items aren't restored, so we 
        # wait a little while before we start the update
        FeedImpl.onRestore(self)
        self.download = None
        self.scheduleUpdateEvents(0.1)

# FIXME: Derive from RSSFeedImpl, but that requires changing RSSFeedImpl some.
class RSSMultiFeedImpl(FeedImpl):
    firstImageRE = re.compile('\<\s*img\s+[^>]*src\s*=\s*"(.*?)"[^>]*\>',re.I|re.M)
    
    def __init__(self,url,ufeed,title = None, visible=True):
        FeedImpl.__init__(self,url,ufeed,title,visible=visible)
        self.etag = {}
        self.modified = {}
        self.download_dc = {}
        self.updating = 0
        self.splitURLs()
        self.scheduleUpdateEvents(0)

    def splitURLs(self):
        if self.url.startswith("dtv:multi:"):
            url = self.url[len("dtv:multi:"):]
            self.urls = [urldecode (x) for x in url.split(",")]
        else:
            self.urls = [self.url]

    ##
    # Returns the description of the feed
    @returnsUnicode
    def getDescription(self):
        self.ufeed.confirmDBThread()
        try:
            return u'<span>Search All</span>'
        except:
            return u"<span />"

    def checkUpdateFinished(self):
        if self.updating == 0:
            self.updateFinished()

    def updateFinished(self):
        if self.initialUpdate:
            self.initialUpdate = False
            startfrom = None
            itemToUpdate = None
            for item in self.items:
                itemTime = item.getPubDateParsed()
                if startfrom is None or itemTime > startfrom:
                    startfrom = itemTime
                    itemToUpdate = item
            for item in self.items:
                if item == itemToUpdate:
                    item.eligibleForAutoDownload = True
                else:
                    item.eligibleForAutoDownload = False
                item.signalChange()
            self.ufeed.signalChange()
        self.ufeed.signalChange(needsSave=False)

    def feedparser_finished (self, url, needsSave = False):
        if not self.ufeed.idExists():
            return
        self.updating -= 1
        self.checkUpdateFinished()
        self.scheduleUpdateEvents(-1)
        del self.download_dc[url]

    def feedparser_errback (self, e, url):
        if not self.ufeed.idExists():
            return
        if e:
            logging.info ("Error updating feed: %s (%s): %s", self.url, url, e)
        else:
            logging.info ("Error updating feed: %s (%s)", self.url, url)
        self.feedparser_finished(url, True)

    def feedparser_callback (self, parsed, url):
        self.ufeed.confirmDBThread()
        if not self.ufeed.idExists():
            return
        start = clock()
        parsed = unicodify(parsed)
        self.updateUsingParsed(parsed)
        self.feedparser_finished(url)
        end = clock()
        if end - start > 1.0:
            logging.timing ("feed update for: %s too slow (%.3f secs)", self.url, end - start)

    def call_feedparser (self, html, url):
        self.ufeed.confirmDBThread()
        in_thread = False
        if in_thread:
            try:
                parsed = feedparser.parse(html)
                feedparser_callback(parsed, url)
            except:
                self.feedparser_errback(self, None, url)
                raise
        else:
            eventloop.callInThread (lambda parsed, url=url: self.feedparser_callback(parsed, url),
                                    lambda e, url=url: self.feedparser_errback(e, url),
                                    feedparser.parse, "Feedparser callback - %s" % url, html)

    ##
    # Updates a feed
    def update(self):
        self.ufeed.confirmDBThread()
        if not self.ufeed.idExists():
            return
        if self.updating:
            return
        for url in self.urls:
            try:
                etag = self.etag[url]
            except:
                etag = None
            try:
                modified = self.modified[url]
            except:
                modified = None
            self.download_dc[url] = grabURL(url,
                                            lambda x, url=url:self._updateCallback(x, url),
                                            lambda x, url=url:self._updateErrback(x, url),
                                            etag=etag, modified=modified,
                                            defaultMimeType=u'application/rss+xml',)
            self.updating += 1

    def _updateErrback(self, error, url):
        if not self.ufeed.idExists():
            return
        logging.info ("WARNING: error in Feed.update for %s (%s) -- %s", self.ufeed, url, error)
        self.scheduleUpdateEvents(-1)
        self.updating -= 1
        self.checkUpdateFinished()
        self.ufeed.signalChange(needsSave=False)

    def _updateCallback(self,info, url):
        if not self.ufeed.idExists():
            return
        if info.get('status') == 304:
            self.scheduleUpdateEvents(-1)
            self.updating -= 1 
            self.checkUpdateFinished()
            self.ufeed.signalChange()
            return
        html = info['body']
        if info.has_key('charset'):
            html = fixXMLHeader(html,info['charset'])

        # FIXME HTML can be non-unicode here --NN
        # FIXME How to update this properly
        #self.url = unicodify(info['updated-url'])
        if info.has_key('etag'):
            self.etag[url] = unicodify(info['etag'])
        else:
            self.etag[url] = None
        if info.has_key('last-modified'):
            self.modified[url] = unicodify(info['last-modified'])
        else:
            self.modified[url] = None
        self.call_feedparser (html, url)

    def _handleNewEntryForItem(self, item, entry, channelTitle):
        """Handle when we get a different entry for an item.

        This happens when the feed sets the RSS GUID attribute, then changes
        the entry for it.  Most of the time we will just update the item, but
        if the user has already downloaded the item then we need to make sure
        that we don't throw away the download.
        """

        videoEnc = getFirstVideoEnclosure(entry)
        if videoEnc is not None:
            entryURL = videoEnc.get('url')
        else:
            entryURL = None
        if item.isDownloaded() and item.getURL() != entryURL:
            item.removeRSSID()
            self._handleNewEntry(entry, channelTitle)
        else:
            item.update(entry)

    def _handleNewEntry(self, entry, channelTitle):
        """Handle getting a new entry from a feed."""
        item = itemmod.Item(entry, feed_id=self.ufeed.id)
        if not filters.matchingItems(item, self.ufeed.searchTerm):
            item.remove()
        item.setChannelTitle(channelTitle)

    def updateUsingParsed(self, parsed):
        """Update the feed using parsed XML passed in"""

        # This is a HACK for Yahoo! search which doesn't provide
        # enclosures
        for entry in parsed['entries']:
            if 'enclosures' not in entry:
                try:
                    url = entry['link']
                except:
                    continue
                mimetype = filetypes.guessMimeType(url)
                if mimetype is not None:
                    entry['enclosures'] = [{'url':toUni(url), 'type':toUni(mimetype)}]
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
                self.title = channelTitle
            if (parsed.feed.has_key('image') and 
                parsed.feed.image.has_key('url')):
                self.thumbURL = parsed.feed.image.url
                self.ufeed.iconCache.requestUpdate(is_vital=True)

        items_byid = {}
        items_byURLTitle = {}
        items_nokey = []
        old_items = set()
        for item in self.items:
            old_items.add(item)
            try:
                items_byid[item.getRSSID()] = item
            except KeyError:
                items_nokey.append (item)
            entry = item.getRSSEntry()
            videoEnc = getFirstVideoEnclosure(entry)
            if videoEnc is not None:
                entryURL = videoEnc.get('url')
            else:
                entryURL = None
            title = entry.get("title")
            if title is not None or entryURL is not None:
                items_byURLTitle[(entryURL, title)] = item
        for entry in parsed.entries:
            entry = self.addScrapedThumbnail(entry)
            new = True
            if entry.has_key("id"):
                id = entry["id"]
                if items_byid.has_key (id):
                    item = items_byid[id]
                    if not _entry_equal(entry, item.getRSSEntry()):
                        self._handleNewEntryForItem(item, entry, channelTitle)
                    new = False
                    old_items.discard(item)
            if new:
                videoEnc = getFirstVideoEnclosure(entry)
                if videoEnc is not None:
                    entryURL = videoEnc.get('url')
                else:
                    entryURL = None
                title = entry.get("title")
                if title is not None or entryURL is not None:
                    if items_byURLTitle.has_key ((entryURL, title)):
                        item = items_byURLTitle[(entryURL, title)]
                        if not _entry_equal(entry, item.getRSSEntry()):
                            self._handleNewEntryForItem(item, entry, channelTitle)
                        new = False
                        old_items.discard(item)
            if new:
                for item in items_nokey:
                    if _entry_equal(entry, item.getRSSEntry()):
                        new = False
                    else:
                        try:
                            if _entry_equal (entry["enclosures"], item.getRSSEntry()["enclosures"]):
                                self._handleNewEntryForItem(item, entry, channelTitle)
                                new = False
                                old_items.discard(item)
                        except:
                            pass
            if (new and entry.has_key('enclosures') and
                    getFirstVideoEnclosure(entry) != None):
                self._handleNewEntry(entry, channelTitle)
#        try:
#            updateFreq = parsed["feed"]["ttl"]
#        except KeyError:
#            updateFreq = 0
#        self.setUpdateFrequency(updateFreq)
        
        self.truncateOldItems(old_items)

    def truncateOldItems(self, old_items):
        """Truncate items so that the number of items in this feed doesn't
        exceed prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS.

        old_items should be an iterable that contains items that aren't in the
        feed anymore.

        Items are only truncated if they don't exist in the feed anymore, and
        if the user hasn't downloaded them.
        """
        limit = config.get(prefs.TRUNCATE_CHANNEL_AFTER_X_ITEMS)
        extra = len(self.items) - limit
        if extra <= 0:
            return

        candidates = []
        for item in old_items:
            if item.downloader is None:
                candidates.append((item.creationTime, item))
        candidates.sort()
        for time, item in candidates[:extra]:
            item.remove()

    def addScrapedThumbnail(self,entry):
        # skip this if the entry already has a thumbnail.
        if entry.has_key('thumbnail'):
            return entry
        if entry.has_key('enclosures'):
            for enc in entry['enclosures']:
                if enc.has_key('thumbnail'):
                    return entry
        # try to scape the thumbnail from the description.
        if not entry.has_key('description'):
            return entry
        desc = RSSMultiFeedImpl.firstImageRE.search(unescape(entry['description']))
        if not desc is None:
            entry['thumbnail'] = FeedParserDict({'url': desc.expand("\\1")})
        return entry

    def onRemove(self):
        for dc in self.download_dc.values():
            if dc is not None:
                dc.cancel()
        self.download_dc = {}

    ##
    # Called by pickle during deserialization
    def onRestore(self):
        #self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.feed is self)
        #FIXME: the update dies if all of the items aren't restored, so we 
        # wait a little while before we start the update
        FeedImpl.onRestore(self)
        self.download_dc = {}
        self.updating = 0
        self.splitURLs()
        self.scheduleUpdateEvents(0.1)


##
# A DTV Collection of items -- similar to a playlist
class Collection(FeedImpl):
    def __init__(self,ufeed,title = None):
        FeedImpl.__init__(self,ufeed,url = "dtv:collection",title = title,visible = False)

    ##
    # Adds an item to the collection
    def addItem(self,item):
        if isinstance(item, itemmod.Item):
            self.ufeed.confirmDBThread()
            self.removeItem(item)
            self.items.append(item)
            return True
        else:
            return False

    ##
    # Moves an item to another spot in the collection
    def moveItem(self,item,pos):
        self.ufeed.confirmDBThread()
        self.removeItem(item)
        if pos < len(self.items):
            self.items[pos:pos] = [item]
        else:
            self.items.append(item)

    ##
    # Removes an item from the collection
    def removeItem(self,item):
        self.ufeed.confirmDBThread()
        for x in range(0,len(self.items)):
            if self.items[x] == item:
                self.items[x:x+1] = []
                break
        return True

##
# A feed based on un unformatted HTML or pre-enclosure RSS
class ScraperFeedImpl(FeedImpl):
    def __init__(self,url,ufeed, title = None, visible = True, initialHTML = None,etag=None,modified = None,charset = None):
        FeedImpl.__init__(self,url,ufeed,title,visible)
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
    def getMimeType(self,link):
        raise StandardError, "ScraperFeedImpl.getMimeType not implemented"

    ##
    # This puts all of the caching information in tempHistory into the
    # linkHistory. This should be called at the end of an updated so that
    # the next time we update we don't unnecessarily follow old links
    def saveCacheHistory(self):
        self.ufeed.confirmDBThread()
        for url in self.tempHistory.keys():
            self.linkHistory[url] = self.tempHistory[url]
        self.tempHistory = {}
    ##
    # grabs HTML at the given URL, then processes it
    def getHTML(self, urlList, depth = 0, linkNumber = 0, top = False):
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
                self.processDownloadedHTML(info, urlList, depth,linkNumber, top)
            finally:
                self.checkDone()
        def errback(error):
            if not self.ufeed.idExists():
                return
            self.downloads.discard(download)
            logging.info ("WARNING unhandled error for ScraperFeedImpl.getHTML: %s", error)
            self.checkDone()
        download = grabURL(url, callback, errback, etag=etag,
                modified=modified,defaultMimeType='text/html',)
        self.downloads.add(download)

    def processDownloadedHTML(self, info, urlList, depth, linkNumber, top = False):
        self.ufeed.confirmDBThread()
        #print "Done grabbing %s" % info['updated-url']
        
        if not self.tempHistory.has_key(info['updated-url']):
            self.tempHistory[info['updated-url']] = {}
        if info.has_key('etag'):
            self.tempHistory[info['updated-url']]['etag'] = unicodify(info['etag'])
        if info.has_key('last-modified'):
            self.tempHistory[info['updated-url']]['modified'] = unicodify(info['last-modified'])

        if (info['status'] != 304) and (info.has_key('body')):
            if info.has_key('charset'):
                subLinks = self.scrapeLinks(info['body'], info['redirected-url'],charset=info['charset'], setTitle = top)
            else:
                subLinks = self.scrapeLinks(info['body'], info['redirected-url'], setTitle = top)
            if top:
                self.processLinks(subLinks,0,linkNumber)
            else:
                self.processLinks(subLinks,depth+1,linkNumber)
        if len(urlList) > 0:
            self.getHTML(urlList, depth, linkNumber)

    def checkDone(self):
        if len(self.downloads) == 0:
            self.saveCacheHistory()
            self.updating = False
            self.ufeed.signalChange()
            self.scheduleUpdateEvents(-1)

    def addVideoItem(self,link,dict,linkNumber):
        link = unicodify(link.strip())
        if dict.has_key('title'):
            title = dict['title']
        else:
            title = link
        for item in self.items:
            if item.getURL() == link:
                return
        # Anywhere we call this, we need to convert the input back to unicode
        title = feedparser.sanitizeHTML (title, "utf-8").decode('utf-8')
        if dict.has_key('thumbnail') > 0:
            i=itemmod.Item(FeedParserDict({'title':title,'enclosures':[FeedParserDict({'url':link,'thumbnail':FeedParserDict({'url':dict['thumbnail']})})]}),linkNumber = linkNumber, feed_id=self.ufeed.id)
        else:
            i=itemmod.Item(FeedParserDict({'title':title,'enclosures':[FeedParserDict({'url':link})]}),linkNumber = linkNumber, feed_id=self.ufeed.id)
        if self.ufeed.searchTerm is not None and not filters.matchingItems(i, self.ufeed.searchTerm):
            i.remove()
            return

    #FIXME: compound names for titles at each depth??
    def processLinks(self,links, depth = 0,linkNumber = 0):
        maxDepth = 2
        urls = links[0]
        links = links[1]
        # List of URLs that should be downloaded
        newURLs = []
        
        if depth<maxDepth:
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

                mimetype = filetypes.guessMimeType(link)
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
                    self.addVideoItem(link, links[link],linkNumber)
            if len(newURLs) > 0:
                self.getHTML(newURLs, depth, linkNumber)

    def onRemove(self):
        for download in self.downloads:
            logging.info ("cancling download: %s", download.url)
            download.cancel()
        self.downloads = set()

    #FIXME: go through and add error handling
    def update(self):
        self.ufeed.confirmDBThread()
        if not self.ufeed.idExists():
            return
        if self.updating:
            return
        else:
            self.updating = True
            self.ufeed.signalChange(needsSave=False)

        if not self.initialHTML is None:
            html = self.initialHTML
            self.initialHTML = None
            redirURL=self.url
            status = 200
            charset = self.initialCharset
            self.initialCharset = None
            subLinks = self.scrapeLinks(html, redirURL, charset=charset, setTitle = True)
            self.processLinks(subLinks,0,0)
            self.checkDone()
        else:
            self.getHTML([self.url], top = True)

    def scrapeLinks(self,html,baseurl,setTitle = False,charset = None):
        try:
            if not charset is None:
                html = fixHTMLHeader(html,charset)
            xmldata = html
            parser = xml.sax.make_parser()
            parser.setFeature(xml.sax.handler.feature_namespaces, 1)
            try: parser.setFeature(xml.sax.handler.feature_external_ges, 0)
            except: pass
            if charset is not None:
                handler = RSSLinkGrabber(baseurl,charset)
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
                    if not linkDict.has_key(toUni(link[0],charset)):
                        linkDict[toUni(link[0],charset)] = {}
                    if not link[1] is None:
                        linkDict[toUni(link[0],charset)]['title'] = toUni(link[1],charset).strip()
                    if not link[2] is None:
                        linkDict[toUni(link[0],charset)]['thumbnail'] = toUni(link[2],charset)
            if setTitle and not handler.title is None:
                self.ufeed.confirmDBThread()
                try:
                    self.title = toUni(handler.title,charset)
                finally:
                    self.ufeed.signalChange()
            return ([x[0] for x in links if x[0].startswith('http://') or x[0].startswith('https://')], linkDict)
        except (xml.sax.SAXException, ValueError, IOError, xml.sax.SAXNotRecognizedException):
            (links, linkDict) = self.scrapeHTMLLinks(html,baseurl,setTitle=setTitle, charset=charset)
            return (links, linkDict)

    ##
    # Given a string containing an HTML file, return a dictionary of
    # links to titles and thumbnails
    def scrapeHTMLLinks(self,html, baseurl,setTitle=False, charset = None):
        lg = HTMLLinkGrabber()
        links = lg.getLinks(html, baseurl)
        if setTitle and not lg.title is None:
            self.ufeed.confirmDBThread()
            try:
                self.title = toUni(lg.title, charset)
            finally:
                self.ufeed.signalChange()
            
        linkDict = {}
        for link in links:
            if link[0].startswith('http://') or link[0].startswith('https://'):
                if not linkDict.has_key(toUni(link[0],charset)):
                    linkDict[toUni(link[0],charset)] = {}
                if not link[1] is None:
                    linkDict[toUni(link[0],charset)]['title'] = toUni(link[1],charset).strip()
                if not link[2] is None:
                    linkDict[toUni(link[0],charset)]['thumbnail'] = toUni(link[2],charset)
        return ([x[0] for x in links if x[0].startswith('http://') or x[0].startswith('https://')],linkDict)
        
    ##
    # Called by pickle during deserialization
    def onRestore(self):
        FeedImpl.onRestore(self)
        #self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.feed is self)

        #FIXME: the update dies if all of the items aren't restored, so we 
        # wait a little while before we start the update
        self.downloads = set()
        self.tempHistory = {}
        self.scheduleUpdateEvents(.1)

class DirectoryWatchFeedImpl(FeedImpl):
    def __init__(self,ufeed, directory, visible = True):
        self.dir = directory
        self.firstUpdate = True
        if directory is not None:
            url = u"dtv:directoryfeed:%s" % (makeURLSafe (directory),)
        else:
            url = u"dtv:directoryfeed"
        title = directory
        if title[-1] == '/':
            title = title[:-1]
        title = filenameToUnicode(os.path.basename(title)) + "/"
        FeedImpl.__init__(self,url = url,ufeed=ufeed,title = title,visible = visible)

        self.setUpdateFrequency(5)
        self.scheduleUpdateEvents(0)

    ##
    # Directory Items shouldn't automatically expire
    def expireItems(self):
        pass

    def setUpdateFrequency(self, frequency):
        newFreq = frequency*60
        if newFreq != self.updateFreq:
            self.updateFreq = newFreq
            self.scheduleUpdateEvents(-1)

    def setVisible(self, visible):
        if self.visible == visible:
            return
        self.visible = visible
        self.signalChange()

    def update(self):
        def isBasenameHidden(filename):
            if filename[-1] == os.sep:
                filename = filename[:-1]
            return os.path.basename(filename)[0] == FilenameType('.')
        self.ufeed.confirmDBThread()

        # Files known about by real feeds (other than other directory
        # watch feeds)
        knownFiles = set()
        for item in views.toplevelItems:
            if not item.getFeed().getURL().startswith("dtv:directoryfeed"):
                knownFiles.add(os.path.normcase(item.getFilename()))

        # Remove items that are in feeds, but we have in our list
        for item in self.items:
            if item.getFilename() in knownFiles:
                item.remove()

        # Now that we've checked for items that need to be removed, we
        # add our items to knownFiles so that they don't get added
        # multiple times to this feed.
        for x in self.items:
            knownFiles.add(os.path.normcase (x.getFilename()))

        #Adds any files we don't know about
        #Files on the filesystem
        if os.path.isdir(self.dir):
            all_files = []
            files, dirs = miro_listdir(self.dir)
            for file in files:
                all_files.append(file)
            for dir in dirs:
                subfiles, subdirs = miro_listdir(dir)
                for subfile in subfiles:
                    all_files.append(subfile)
            for file in all_files:
                if file not in knownFiles and filetypes.isVideoFilename(filenameToUnicode(file)):
                    itemmod.FileItem(file, feed_id=self.ufeed.id)

        for item in self.items:
            if not os.path.isfile(item.getFilename()):
                item.remove()
        if self.firstUpdate:
            for item in self.items:
                item.markItemSeen()
            self.firstUpdate = False

        self.scheduleUpdateEvents(-1)

    def onRestore(self):
        FeedImpl.onRestore(self)
        #FIXME: the update dies if all of the items aren't restored, so we 
        # wait a little while before we start the update
        self.scheduleUpdateEvents(.1)

##
# A feed of all of the Movies we find in the movie folder that don't
# belong to a "real" feed.  If the user changes her movies folder, this feed
# will continue to remember movies in the old folder.
#
class DirectoryFeedImpl(FeedImpl):
    def __init__(self,ufeed):
        FeedImpl.__init__(self,url = u"dtv:directoryfeed",ufeed=ufeed,title = u"Feedless Videos",visible = False)

        self.setUpdateFrequency(5)
        self.scheduleUpdateEvents(0)

    ##
    # Directory Items shouldn't automatically expire
    def expireItems(self):
        pass

    def setUpdateFrequency(self, frequency):
        newFreq = frequency*60
        if newFreq != self.updateFreq:
                self.updateFreq = newFreq
                self.scheduleUpdateEvents(-1)

    def update(self):
        self.ufeed.confirmDBThread()
        moviesDir = config.get(prefs.MOVIES_DIRECTORY)
        # Files known about by real feeds
        knownFiles = set()
        for item in views.toplevelItems:
            if item.feed_id is not self.ufeed.id:
                knownFiles.add(os.path.normcase(item.getFilename()))
            if item.isContainerItem:
                item.findNewChildren()

        knownFiles.add(os.path.normcase(os.path.join(moviesDir, "Incomplete Downloads")))

        # Remove items that are in feeds, but we have in our list
        for item in self.items:
            if item.getFilename() in knownFiles:
                item.remove()

        # Now that we've checked for items that need to be removed, we
        # add our items to knownFiles so that they don't get added
        # multiple times to this feed.
        for x in self.items:
            knownFiles.add(os.path.normcase (x.getFilename()))

        #Adds any files we don't know about
        #Files on the filesystem
        if os.path.isdir(moviesDir):
            all_files = miro_allfiles(moviesDir)
            for file in all_files:
                if file not in knownFiles and filetypes.isVideoFilename(filenameToUnicode(file)):
                    itemmod.FileItem(file, feed_id=self.ufeed.id)

        for item in self.items:
            if not os.path.exists(item.getFilename()):
                item.remove()

        self.scheduleUpdateEvents(-1)

    def onRestore(self):
        FeedImpl.onRestore(self)
        #FIXME: the update dies if all of the items aren't restored, so we 
        # wait a little while before we start the update
        self.scheduleUpdateEvents(.1)

##
# Search and Search Results feeds

class SearchFeedImpl (RSSMultiFeedImpl):
    
    def __init__(self, ufeed):
        RSSMultiFeedImpl.__init__(self, url=u'', ufeed=ufeed, title=u'dtv:search', visible=False)
        self.initialUpdate = True
        self.setUpdateFrequency(-1)
        self.searching = False
        self.lastEngine = u'all'
        self.lastQuery = u''
        self.ufeed.autoDownloadable = False
        self.ufeed.signalChange()

    @returnsUnicode
    def quoteLastQuery(self):
        return escape(self.lastQuery)

    @returnsUnicode
    def getURL(self):
        return u'dtv:search'

    @returnsUnicode
    def getTitle(self):
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

    def reset(self, url=u'', searchState=False):
        self.ufeed.confirmDBThread()
        try:
            self.initialUpdate = True
            for item in self.items:
                item.remove()
            self.url = url
            self.splitURLs()
            self.searching = searchState
            self.etag = {}
            self.modified = {}
            self.title = self.url
            self.ufeed.iconCache.reset()
            self.thumbURL = defaultFeedIconURL()
            self.ufeed.iconCache.requestUpdate(is_vital=True)
        finally:
            self.ufeed.signalChange()
    
    def preserveDownloads(self, downloadsFeed):
        self.ufeed.confirmDBThread()
        for item in self.items:
            if item.getState() not in ('new', 'not-downloaded'):
                item.setFeed(downloadsFeed.id)

    def lookup(self, engine, query):
        checkU(engine)
        checkU(query)
        url = searchengines.getRequestURL(engine, query)
        self.reset(url, True)
        self.lastQuery = query
        self.lastEngine = engine
        self.update()
        self.ufeed.signalChange()

    def _handleNewEntry(self, entry, channelTitle):
        """Handle getting a new entry from a feed."""
        videoEnc = getFirstVideoEnclosure(entry)
        if videoEnc is not None:
            url = videoEnc.get('url')
            if url is not None:
                dl = downloader.getExistingDownloaderByURL(url)
                if dl is not None:
                    for item in dl.itemList:
                        if item.getFeedURL() == 'dtv:searchDownloads' and item.getURL() == url:
                            try:
                                if entry["id"] == item.getRSSID():
                                    item.setFeed(self.ufeed.id)
                                    if not _entry_equal(entry, item.getRSSEntry()):
                                        self._handleNewEntryForItem(item, entry, channelTitle)
                                    return
                            except KeyError:
                                pass
                            title = entry.get("title")
                            oldtitle = item.entry.get("title")
                            if title == oldtitle:
                                item.setFeed(self.ufeed.id)
                                if not _entry_equal(entry, item.getRSSEntry()):
                                    self._handleNewEntryForItem(item, entry, channelTitle)
                                return
        RSSMultiFeedImpl._handleNewEntry(self, entry, channelTitle)

    def updateFinished(self):
        self.searching = False
        RSSMultiFeedImpl.updateFinished(self)

    def update(self):
        if self.url is not None and self.url != u'':
            RSSMultiFeedImpl.update(self)

class SearchDownloadsFeedImpl(FeedImpl):
    def __init__(self, ufeed):
        FeedImpl.__init__(self, url=u'dtv:searchDownloads', ufeed=ufeed, 
                title=None, visible=False)
        self.setUpdateFrequency(-1)

    @returnsUnicode
    def getTitle(self):
        return _(u'Search')

class ManualFeedImpl(FeedImpl):
    """Downloaded Videos/Torrents that have been added using by the
    user opening them with democracy.
    """
    def __init__(self, ufeed):
        FeedImpl.__init__(self, url=u'dtv:manualFeed', ufeed=ufeed, 
                title=None, visible=False)
        self.ufeed.expire = u'never'
        self.setUpdateFrequency(-1)

    @returnsUnicode
    def getTitle(self):
        return _(u'Local Files')

class SingleFeedImpl(FeedImpl):
    """Single Video that is playing that has been added by the user
    opening them with democracy.
    """
    def __init__(self, ufeed):
        FeedImpl.__init__(self, url=u'dtv:singleFeed', ufeed=ufeed, 
                title=None, visible=False)
        self.ufeed.expire = u'never'
        self.setUpdateFrequency(-1)

    @returnsUnicode
    def getTitle(self):
        return _(u'Playing File')

##
# Parse HTML document and grab all of the links and their title
# FIXME: Grab link title from ALT tags in images
# FIXME: Grab document title from TITLE tags
class HTMLLinkGrabber(HTMLParser):
    linkPattern = re.compile("<(a|embed)\s[^>]*(href|src)\s*=\s*\"([^\"]*)\"[^>]*>(.*?)</a(.*)", re.S)
    imgPattern = re.compile(".*<img\s.*?src\s*=\s*\"(.*?)\".*?>", re.S)
    tagPattern = re.compile("<.*?>")
    def getLinks(self,data, baseurl):
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
            desc =  HTMLLinkGrabber.tagPattern.sub(' ',desc)
            self.links.append((link, desc, thumb))
            match = HTMLLinkGrabber.linkPattern.search(match.group(5))
        return self.links

class RSSLinkGrabber(xml.sax.handler.ContentHandler, xml.sax.handler.ErrorHandler):
    def __init__(self,baseurl,charset=None):
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
        self.fatalErrors = 0

    def startElementNS(self, name, qname, attrs):
        uri = name[0]
        tag = name[1]
        if self.firstTag:
            self.firstTag = False
            if tag not in ['rss','feed']:
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
                html = xhtmlify(unescape(self.descHTML),addTopTags=True)
                if not self.charset is None:
                    html = fixHTMLHeader(html,self.charset)
                self.links[:0] = lg.getLinks(html,self.baseurl)
            except HTMLParseError: # Don't bother with bad HTML
                logging.info ("bad HTML in description for %s", self.baseurl)
            self.inDescription = False
        elif tag.lower() == 'link':
            self.links.append((self.theLink,None,None))
            self.inLink = False
        elif tag.lower() == 'item':
            self.inItem == False
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
        self.fatalErrors += 1

# Grabs the feed link from the given webpage
class HTMLFeedURLParser(HTMLParser):
    def getLink(self,baseurl,data):
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
            self.link = urljoin(self.baseurl,attrdict['href'])

def expireItems():
    try:
        for feed in views.feeds:
            feed.expireItems()
    finally:
        eventloop.addTimeout(300, expireItems, "Expire Items")

def getFeedByURL(url):
    return views.feeds.getItemWithIndex(indexes.feedsByURL, url)
