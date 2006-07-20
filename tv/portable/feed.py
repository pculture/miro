# FIXME import * is really bad practice..  At the very least, lest keep it at
# the top, so it cant overwrite other symbols.
from item import *

from HTMLParser import HTMLParser,HTMLParseError
from cStringIO import StringIO
from copy import copy
from datetime import datetime, timedelta
from gettext import gettext as _
from inspect import isfunction
from new import instancemethod
from urlparse import urlparse, urljoin
from xhtmltools import unescape,xhtmlify,fixXMLHeader, fixHTMLHeader, toUTF8Bytes, urlencode
import os
import string
import re
import traceback 
import xml

from database import defaultDatabase
from httpclient import grabURL, HTTPError
from iconcache import iconCacheUpdater, IconCache
from templatehelper import quoteattr, escape
import app
import config
import dialogs
import eventloop
import prefs
import resource
import util
import views
import indexes
from BitTornado.clock import clock

whitespacePattern = re.compile(r"^[ \t\r\n]*$")

def defaultFeedIconURL():
    return resource.url("images/feedicon.png")

# Notes on character set encoding of feeds:
#
# The parsing libraries built into Python mostly use byte strings
# instead of unicode strings.  However, sometimes they get "smart" and
# try to convert the byte stream to a unicode stream automatically.
#
# What does what when isn't clearly documented
#
# We use the function toUTF8Bytes() to fix those smart conversions
#
# If you run into Unicode crashes, adding that function in the
# appropriate place should fix it.

# Universal Feed Parser http://feedparser.org/
# Licensed under Python license
import feedparser

# Pass in a connection to the frontend
def setDelegate(newDelegate):
    global delegate
    delegate = newDelegate

# Pass in a feed sorting function 
def setSortFunc(newFunc):
    global sortFunc
    sortFunc = newFunc

#
# Adds a new feed using USM
def addFeedFromFile(file):
    d = feedparser.parse(file)
    if d.feed.has_key('links'):
        for link in d.feed['links']:
            if link['rel'] == 'start':
                Feed(link['href'])
                return
    if d.feed.has_key('link'):
        addFeedFromWebPage(d.feed.link)

#
# Adds a new feed based on a link tag in a web page
def addFeedFromWebPage(url):
    def callback(info):
        url = HTMLFeedURLParser().getLink(info['updated-url'],info['body'])
        if url:
            Feed(url)
    def errback(error):
        print "WARNING: unhandled error in addFeedFromWebPage: ", error
    grabURL(url, callback, errback)

# URL validitation and normalization
def validateFeedURL(url):
    return re.match(r"^(http|https)://[^/]+/.*", url) is not None

def normalizeFeedURL(url):
    # Valid URL are returned as-is
    if validateFeedURL(url):
        return url

    originalURL = url
    
    # Check valid schemes with invalid separator
    match = re.match(r"^(http|https):/*(.*)$", url)
    if match is not None:
        url = "%s://%s" % match.group(1,2)

    # Replace invalid schemes by http
    match = re.match(r"^(([A-Za-z]*):/*)*(.*)$", url)
    if match.group(2) in ['feed', 'podcast', None]:
        url = "http://%s" % match.group(3)
    elif match.group(1) == 'feeds':
        url = "https://%s" % match.group(3)

    # Make sure there is a leading / character in the path
    match = re.match(r"^(http|https)://[^/]*$", url)
    if match is not None:
        url = url + "/"

    if not validateFeedURL(url):
        print "DTV: unable to normalize URL %s" % originalURL
        return originalURL
    else:
        print "normalized: %s -> %s" % (originalURL, url)
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
        self.available = 0
        self.unwatched = 0
        self.url = url
        self.ufeed = ufeed
        self.calc_item_list()
        if title == None:
            self.title = url
        else:
            self.title = title
        self.created = datetime.now()
        self.autoDownloadable = ufeed.initiallyAutoDownloadable
        self.startfrom = datetime.max
        self.getEverything = False
        self.maxNew = -1
        self.fallBehind = -1
        self.expire = "system"
        self.visible = visible
        self.updating = False
        self.lastViewed = datetime.min
        self.thumbURL = defaultFeedIconURL()
        self.initialUpdate = True
        self.updateFreq = config.get(prefs.CHECK_CHANNELS_EVERY_X_MN)*60
        self.expireTime = None

    def calc_item_list(self):
        self.items = views.items.filterWithIndex(indexes.itemsByFeed, self.ufeed.id)

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
        if self.updateFreq > 0:
            if firstTriggerDelay >= 0:
                self.scheduler = eventloop.addTimeout(firstTriggerDelay, self.update, "Feed update (%s)" % self.getTitle())
            else:
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
            print "%s has no ufeed" % self

    # Updates the state of unwatched and available items to meet
    # Returns true iff signalChange() is called
    def updateUandA(self, signal = True):
        self.ufeed.confirmDBThread()
        newU = 0
        newA = 0

        for item in self.items:
            # FIXME: I think it's bad style to use the CSS class here.  The
            # problem is that what we want isn't getState() or
            # getChannelCategory(), since we don't want to count new items
            # that are also going to be auto-downloaded.  Maybe make a
            # method called getDisplayState or something?.
            (u, a) = item.getUandA()
            newA += a
            newU += u
        if newU != self.unwatched or newA != self.available:
            self.unwatched = newU
            self.available = newA
            if signal:
                self.ufeed.signalChange(needsSave=False)
            
    # Returns string with number of unwatched videos in feed
    def numUnwatched(self):
        return self.unwatched

    # Returns string with number of available videos in feed
    def numAvailable(self):
        return self.available

    # Returns true iff both unwatched and available numbers should be shown
    def showBothUAndA(self):
        return self.showU() and self.showA()

    # Returns true iff unwatched should be shown 
    def showU(self):
        return self.unwatched > 0

    # Returns true iff available should be shown
    def showA(self):
        return self.available > 0

    ##
    # Sets the last time the feed was viewed to now
    def markAsViewed(self):
        self.lastViewed = datetime.now() 
        self.updateUandA(False)
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

    ##
    # Downloads the next available item taking into account maxNew,
    # fallbehind, and getEverything
    def downloadNextAuto(self, dontUse = []):
        nextAuto = self.getNextAutoDownload()
        if nextAuto is not None:
            nextAuto.download(autodl=True)
            return True
        else:
            return False

    ##
    # Figure out the next available auto download item taking into account
    # maxNew, fallbehind, and getEverything
    def getNextAutoDownload(self, dontUse = []):
        self.ufeed.confirmDBThread()
        if not self.ufeed.isAutoDownloadable():
            return None
        next = None

        #The number of items downloading from this feed
        dling = 0
        #The number of items eligibile to download
        eligibile = 0
        #The number of unwatched, downloaded items
        newitems = 0

        #Find the next item we should get
#        self.items.sort(sortFunc)
        for item in self.items:
            state = item.getState()
            if item.isEligibleForAutoDownload() and not item in dontUse:
                eligibile += 1
                if next == None:
                    next = item
                elif item.getPubDateParsed() > next.getPubDateParsed():
                    next = item
            elif state == "downloading":
                dling += 1
            elif state == 'newly-downloaded':
                newitems += 1

        if self.maxNew >= 0 and newitems + dling >= self.maxNew:
            return None
        elif self.fallBehind>=0 and eligibile > self.fallBehind:
            dontUse.append(next)
            return self.getNextAutoDownload(dontUse)
        elif next != None:
            self.ufeed.confirmDBThread()
            self.startfrom = next.getPubDateParsed()
            return next
        else:
            return None

    def downloadNextManual(self):
        self.ufeed.confirmDBThread()
        next = None
#        self.items.sort(sortFunc)
        for item in self.items:
            if item.isPendingManualDownload():
                if next is None:
                    next = item
                elif item.getPubDateParsed() < next.getPubDateParsed():
                    next = item
        if not next is None:
            next.download(autodl = False)

    ##
    # Returns marks expired items as expired
    def expireItems(self):
        for item in self.items:
            expireTime = item.getExpirationTime()
            if (item.getState() == 'expiring' and expireTime is not None and 
                    expireTime < datetime.now()):
                item.expire()

    ##
    # Returns true iff feed should be visible
    def isVisible(self):
        self.ufeed.confirmDBThread()
        return self.visible

    def signalAutoItems (self, wereAuto):
        for item in self.items:
            if item in wereAuto:
                if not item.isEligibleForAutoDownload():
                    item.signalChange(needsSave=False)
            else:
                if item.isEligibleForAutoDownload():
                    item.signalChange(needsSave=False)

    def signalItems (self):
        for item in self.items:
            item.signalChange(needsSave=False)

    ##
    # Switch the auto-downloadable state
    def setAutoDownloadable(self, automatic):
        self.ufeed.confirmDBThread()
        auto = set()
        for item in self.items:
            if item.isEligibleForAutoDownload():
                auto.add(item)
        self.autoDownloadable = (automatic == "1")
        if self.autoDownloadable:
            self.startfrom = datetime.now()
        else:
            self.startfrom = datetime.max
        for item in self.items:
            if item.isEligibleForAutoDownload() or item in auto:
                item.signalChange(needsSave=False)
        self.ufeed.signalChange()

    ##
    # Sets the 'getEverything' attribute, True or False
    def setGetEverything(self, everything):
        self.ufeed.confirmDBThread()
        wereAuto = set()
        for item in self.items:
            if item.isEligibleForAutoDownload():
                wereAuto.add(item)
        self.getEverything = everything
        self.ufeed.signalChange()
        self.signalAutoItems(wereAuto)

    ##
    # Sets the expiration attributes. Valid types are 'system', 'feed' and 'never'
    # Expiration time is in hour(s).
    def setExpiration(self, type, time):
        self.ufeed.confirmDBThread()
        self.expire = type
        self.expireTime = timedelta(hours=time)

        if self.expire == "never":
            for item in self.items:
                if item.isDownloaded():
                    item.save()

        self.ufeed.signalChange()
        for item in self.items:
            item.signalChange(needsSave=False)

    ##
    # Sets the maxNew attributes. -1 means unlimited.
    def setMaxNew(self, maxNew):
        self.ufeed.confirmDBThread()
        self.maxNew = maxNew
        self.ufeed.signalChange()
        for item in self.items:
            item.signalChange(needsSave=False)

    ##
    # Return the 'system' expiration delay, in days (can be < 1.0)
    def getDefaultExpiration(self):
        return float(config.get(prefs.EXPIRE_AFTER_X_DAYS))

    ##
    # Returns the 'system' expiration delay as a formatted string
    def getFormattedDefaultExpiration(self):
        expiration = self.getDefaultExpiration()
        formattedExpiration = ''
        if expiration < 0:
            formattedExpiration = 'never'
        elif expiration < 1.0:
            formattedExpiration = '%d hours' % int(expiration * 24.0)
        elif expiration == 1:
            formattedExpiration = '%d day' % int(expiration)
        elif expiration > 1 and expiration < 30:
            formattedExpiration = '%d days' % int(expiration)
        elif expiration >= 30:
            formattedExpiration = '%d months' % int(expiration / 30)
        return formattedExpiration

    ##
    # Returns "feed," "system," or "never"
    def getExpirationType(self):
        self.ufeed.confirmDBThread()
        return self.expire

    ##
    # Returns"unlimited" or the maximum number of items this feed can fall behind
    def getMaxFallBehind(self):
        self.ufeed.confirmDBThread()
        if self.fallBehind < 0:
            return "unlimited"
        else:
            return self.fallBehind

    ##
    # Returns "unlimited" or the maximum number of items this feed wants
    def getMaxNew(self):
        self.ufeed.confirmDBThread()
        if self.maxNew < 0:
            return "unlimited"
        else:
            return self.maxNew

    ##
    # Returns the total absolute expiration time in hours.
    # WARNING: 'system' and 'never' expiration types return 0
    def getExpirationTime(self):
        delta = None
        self.ufeed.confirmDBThread()
        expireAfterSetting = config.get(prefs.EXPIRE_AFTER_X_DAYS)
        if (self.expireTime is None or self.expire == 'never' or 
            (self.expire == 'system' and expireAfterSetting <= 0)):
            return 0
        else:
            return (self.expireTime.days * 24 + 
                    self.expireTime.seconds / 3600)

    ##
    # Returns the number of days until a video expires
    def getExpireDays(self):
        ret = 0
        self.ufeed.confirmDBThread()
        try:
            return self.expireTime.days
        except:
            return timedelta(days=config.get(prefs.EXPIRE_AFTER_X_DAYS)).days

    ##
    # Returns the number of hours until a video expires
    def getExpireHours(self):
        ret = 0
        self.ufeed.confirmDBThread()
        try:
            return int(self.expireTime.seconds/3600)
        except:
            return int(timedelta(days=config.get(prefs.EXPIRE_AFTER_X_DAYS)).seconds/3600)
        

    ##
    # Returns true iff item is autodownloadable
    def isAutoDownloadable(self):
        self.ufeed.confirmDBThread()
        return self.autoDownloadable

    def autoDownloadStatus(self):
        status = self.isAutoDownloadable()
        if status:
            return "ON"
        else:
            return "OFF"

    ##
    # Returns the title of the feed
    def getTitle(self):
        try:
            title = self.title
            if whitespacePattern.match(title):
                title = self.url
            return title
        except:
            return ""

    ##
    # Returns the URL of the feed
    def getURL(self):
        try:
            return self.url
        except:
            return ""

    ##
    # Returns the description of the feed
    def getDescription(self):
        return "<span />"

    ##
    # Returns a link to a webpage associated with the feed
    def getLink(self):
        return ""

    ##
    # Returns the URL of the library associated with the feed
    def getLibraryLink(self):
        return ""

    ##
    # Returns the URL of a thumbnail associated with the feed
    def getThumbnailURL(self):
        return self.thumbURL

    ##
    # Returns URL of license assocaited with the feed
    def getLicense(self):
        return ""

    ##
    # Returns the number of new items with the feed
    def getNewItems(self):
        self.ufeed.confirmDBThread()
        count = 0
        for item in self.items:
            try:
                if item.getState() == 'newly-downloaded':
                    count += 1
            except:
                pass
        return count

    def onRestore(self):
        self.updating = False
        self.available = 0
        self.unwatched = 0
        self.calc_item_list()

    def onRemove(self):
        """Called when the feed uses this FeedImpl is removed from the DB.
        subclasses can perform cleanup here."""
        pass


updaterDC = None
updaterSet = set()
def updateUandAs():
    global updaterSet
    global updaterDC
    for feedimpl in updaterSet:
        feedimpl.updateUandA()
    updaterSet = set()
    updaterDC = None

def updateUandA(feed):
    global updaterSet
    global updaterDC
    updaterSet.add (feed.actualFeed)
    if updaterDC is None:
        updaterDC = eventloop.addIdle(updateUandAs, "Update unwatched counts")

##
# This class is a magic class that can become any type of feed it wants
#
# It works by passing on attributes to the actual feed.
class Feed(DDBObject):
    def __init__(self,url, initiallyAutoDownloadable=True):
        self.origURL = url
        self.errorState = False
        self.initiallyAutoDownloadable = initiallyAutoDownloadable
        self.loading = True
        self.actualFeed = FeedImpl(url,self)
        self.download = None
        self.iconCache = IconCache(self, is_vital = True)
        self.informOnError = True
        DDBObject.__init__(self)
        self.generateFeed(True)

    # Returns javascript to mark the feed as viewed
    # FIXME: Using setTimeout is a hack to get around JavaScript bugs
    #        Without the timeout, the view is never completely updated
    def getMarkViewedJS(self):
        return ("function markViewed() {eventURL('action:markFeedViewed?url=%s');} setTimeout(markViewed, 5000);" % 
                urlencode(self.getURL()))

    # Returns the ID of this feed. Deprecated.
    def getFeedID(self):
        return self.getID()

    def getID(self):
        return DDBObject.getID(self)

    def hasError(self):
        self.confirmDBThread()
        return self.errorState

    def getOriginalURL(self):
        self.confirmDBThread()
        return self.origURL

    def getError(self):
        return "Could not load feed"

    def isUpdating(self):
        return self.loading or (self.actualFeed and self.actualFeed.updating)

    def isScraped(self):
        return isinstance(self.actualFeed, ScraperFeedImpl)

    def update(self):
        self.confirmDBThread()
        if self.loading:
            return
        elif self.errorState:
            self.loading = True
            self.errorState = False
            self.signalChange()
            return self.generateFeed()
        self.actualFeed.update()

    def generateFeed(self, removeOnError=False):
        newFeed = None
        if (self.origURL == "dtv:directoryfeed"):
            newFeed = DirectoryFeedImpl(self)
        elif (self.origURL == "dtv:search"):
            newFeed = SearchFeedImpl(self)
        elif (self.origURL == "dtv:searchDownloads"):
            newFeed = SearchDownloadsFeedImpl(self)
        elif (self.origURL == "dtv:manualFeed"):
            newFeed = ManualFeedImpl(self)
        else:
            self.download = grabURL(self.origURL,
                    lambda info:self._generateFeedCallback(info, removeOnError),
                    lambda error:self._generateFeedErrback(error, removeOnError))
            #print "added async callback to create feed %s" % self.origURL
        if newFeed:
            self.actualFeed = newFeed
            self.loading = False

            self.signalChange()

    def _generateFeedErrback(self, error, removeOnError):
        if not self.idExists():
            return
        self.download = None
        print "DTV: Warning couldn't load feed at %s (%s)" % \
                (self.origURL, error)
        self.errorState = True
        self.loading = False
        self.signalChange()
        if self.informOnError:
            title = _('Error loading feed')
            description = _("Couldn't load the feed at %s.") % self.url
            if isinstance(error, HTTPError):
                description += "\n\n"
                description += _("The error was: %s") % \
                        error.getFriendlyDescription()
            else:
                print "WARNING: unknown error in _generateFeedErrback (%s)" \
                        % error
            dialogs.MessageBoxDialog(title, description).run()
            self.informOnError = False
        delay = config.get(prefs.CHECK_CHANNELS_EVERY_X_MN)
        eventloop.addTimeout(delay, self.update, "update failed feed")

    def _generateFeedCallback(self, info, removeOnError):
        """This is called by grabURL to generate a feed based on
        the type of data found at the given URL
        """
        # FIXME: This probably should be split up a bit. The logic is
        #        a bit daunting
        if not self.idExists():
            return
        self.download = None
        modified = info.get('last-modified')
        etag = info.get('etag')
        contentType = info.get('content-type', 'text/html')

        #Definitely an HTML feed
        if (contentType.startswith('text/html') or 
            contentType.startswith('application/xhtml+xml')):
            #print "Scraping HTML"
            html = info['body']
            if info.has_key('charset'):
                html = fixHTMLHeader(html,info['charset'])
                charset = info['charset']
            else:
                charset = None
            self.askForScrape(info, html, charset)
        #It's some sort of feed we don't know how to scrape
        elif (contentType.startswith('application/rdf+xml') or
              contentType.startswith('application/atom+xml')):
            #print "ATOM or RDF"
            html = info['body']
            if info.has_key('charset'):
                xmldata = fixXMLHeader(html,info['charset'])
            else:
                xmldata = html
            self.finishGenerateFeed(RSSFeedImpl(info['updated-url'],
                initialHTML=xmldata,etag=etag,modified=modified, ufeed=self))
            # If it's not HTML, we can't be sure what it is.
            #
            # If we get generic XML, it's probably RSS, but it still could
            # be XHTML.
            #
            # application/rss+xml links are definitely feeds. However, they
            # might be pre-enclosure RSS, so we still have to download them
            # and parse them before we can deal with them correctly.
        elif (contentType.startswith('application/rss+xml') or
              contentType.startswith('application/podcast+xml') or
              contentType.startswith('text/xml') or 
              contentType.startswith('application/xml') or
              (contentType.startswith('text/plain') and
               info['updated-url'].endswith('.xml'))):
            #print " It's doesn't look like HTML..."
            html = info["body"]
            if info.has_key('charset'):
                xmldata = fixXMLHeader(html,info['charset'])
                html = fixHTMLHeader(html,info['charset'])
                charset = info['charset']
            else:
                xmldata = html
                charset = None
            parser = xml.sax.make_parser()
            parser.setFeature(xml.sax.handler.feature_namespaces, 1)
            handler = RSSLinkGrabber(info['redirected-url'],charset)
            parser.setContentHandler(handler)
            try:
                parser.parse(StringIO(xmldata))
            except UnicodeDecodeError:
                print "Unicode issue parsing... %s" % xmldata[0:300]
                traceback.print_exc()
                self.finishGenerateFeed(None)
                if removeOnError:
                    self.remove()
            except:
                #it doesn't parse as RSS, so it must be HTML
                #print " Nevermind! it's HTML"
                self.askForScrape(info, html, charset)
            else:
                if handler.enclosureCount > 0 or handler.itemCount == 0:
                    #print " It's RSS with enclosures"
                    self.finishGenerateFeed(RSSFeedImpl(info['updated-url'],
                        initialHTML=xmldata, etag=etag, modified=modified,
                        ufeed=self))
                else:
                    #print " It's pre-enclosure RSS"
                    self.askForScrape(info, xmldata, charset)
        else:
            print "DTV doesn't know how to deal with "+contentType+" feeds"
            self.finishGenerateFeed(None)
            if removeOnError:
                self.remove()

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
        title = _("Channel is not compatible with Democracy!")
        descriptionTemplate = string.Template(_("""\
But we'll try our best to grab the files. It may take extra time to list the \
videos, and descriptions may look funny.  Please contact the publishers of \
$url and ask if they can supply a feed in a format that will work with \
Democracy.\n\nDo you want to try to load this channel anyway?"""))
        description = descriptionTemplate.substitute(url=info['updated-url'])
        dialog = dialogs.ChoiceDialog(title, description, dialogs.BUTTON_YES,
                dialogs.BUTTON_NO)

        def callback(dialog):
            if dialog.choice == dialogs.BUTTON_YES:
                impl = ScraperFeedImpl(info['updated-url'],
                    initialHTML=initialHTML, etag=info.get('etag'),
                    modified=info.get('modified'), charset=charset,
                    ufeed=self) 
                self.finishGenerateFeed(impl)
            else:
                self.remove()
        dialog.run(callback)

    def getActualFeed(self):
        return self.actualFeed

    def __getattr__(self,attr):
        return getattr(self.getActualFeed(),attr)

    def remove(self, moveItemsTo=None):
        """Remove the feed.  If moveItemsTo is None (the default), the items
        in this feed will be removed too.  If moveItemsTo is given, the items
        in this feed will be moved to that feed.
        """

        self.confirmDBThread()
        self.cancelUpdateEvents()
        if self.download is not None:
            self.download.cancel()
            self.download = None
        for item in self.items:
            if moveItemsTo is None:
                item.remove()
            else:
                item.setFeed(moveItemsTo.getID())
        if self.iconCache is not None:
            self.iconCache.remove()
            self.iconCache = None
        DDBObject.remove(self)
        self.actualFeed.onRemove()

    def getThumbnail(self):
        self.confirmDBThread()
        if self.iconCache.isValid():
            basename = os.path.basename(self.iconCache.getFilename())
            return resource.iconCacheUrl(basename)
        else:
            return defaultFeedIconURL()

    def hasDownloadedItems(self):
        self.confirmDBThread()
        for item in self.items:
            if item.isDownloaded():
                return True
        return False

    def updateIcons(self):
        iconCacheUpdater.clearVital()
        for item in self.items:
            item.iconCache.requestUpdate(True)
        for feed in views.feeds:
            feed.iconCache.requestUpdate(True)

    def onRestore(self):
        if (self.iconCache == None):
            self.iconCache = IconCache (self, is_vital = True)
        else:
            self.iconCache.dbItem = self
            self.iconCache.requestUpdate(True)
        self.informOnError = False
        self.download = None
        if self.actualFeed.__class__ == FeedImpl:
            # Our initial FeedImpl was never updated, call generateFeed again
            self.loading = True
            self.generateFeed(True)

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

    def getBaseHref(self):
        try:
            return escape(self.parsed.link)
        except:
            return FeedImpl.getBaseHref(self)

    ##
    # Returns the description of the feed
    def getDescription(self):
        self.ufeed.confirmDBThread()
        try:
            return xhtmlify('<span>'+unescape(self.parsed.summary)+'</span>')
        except:
            return "<span />"

    ##
    # Returns a link to a webpage associated with the feed
    def getLink(self):
        self.ufeed.confirmDBThread()
        try:
            return self.parsed.link
        except:
            return ""

    ##
    # Returns the URL of the library associated with the feed
    def getLibraryLink(self):
        self.ufeed.confirmDBThread()
        try:
            return self.parsed.libraryLink
        except:
            return ""

    def hasVideoFeed(self, enclosures):
        hasOne = False
        for enclosure in enclosures:
            if isVideoEnclosure(enclosure):
                hasOne = True
                break
        return hasOne

    def feedparser_finished (self):
        self.updateUandA(False)
        self.updating = False
        self.ufeed.signalChange(needsSave=False)
        self.scheduleUpdateEvents(-1)

    def feedparser_errback (self, e):
        if not self.ufeed.idExists():
            return
        print "Error updating feed: %s: %s" % (self.url, e)
        self.updating = False
        self.ufeed.signalChange()
        self.scheduleUpdateEvents(-1)

    def feedparser_callback (self, parsed):
        if not self.ufeed.idExists():
            return
        self.ufeed.confirmDBThread()
        start = clock()
        self.updateUsingParsed(parsed)
        self.feedparser_finished()
        end = clock()
        if end - start > 0.1:
            print "WARNING: feed update for: %s too slow (%.3f secs)" % (self.url, end - start)

    def call_feedparser (self, html):
        self.ufeed.confirmDBThread()
        in_thread = False
        if in_thread:
            try:
                parsed = feedparser.parse(html)
                self.updateUsingParsed(parsed)
            except:
                print "Error updating feed: %s" % (self.url,)
                self.updating = False
                self.ufeed.signalChange(needsSave=False)
                raise
            self.feedparser_finished()
        else:
            eventloop.callInThread (self.feedparser_callback, self.feedparser_errback, feedparser.parse, html)

    ##
    # Updates a feed
    def update(self):
        self.ufeed.confirmDBThread()
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
                    self._updateErrback, etag=etag,modified=modified)

    def _updateErrback(self, error):
        if not self.ufeed.idExists():
            return
        print "WARNING: error in Feed.update for %s -- %s" % (self.ufeed, error)
        self.scheduleUpdateEvents(-1)
        self.updating = False
        self.ufeed.signalChange(needsSave=False)

    def _updateCallback(self,info):
        if not self.ufeed.idExists():
            return
        if info['status'] == 304:
            self.scheduleUpdateEvents(-1)
            self.updating = False
            self.ufeed.signalChange()
            return
        html = info['body']
        if info.has_key('charset'):
            html = fixXMLHeader(html,info['charset'])
        self.url = info['updated-url']
        if info.has_key('etag'):
            self.etag = info['etag']
        if info.has_key('last-modified'):
            self.modified = info['last-modified']
        self.call_feedparser (html)

    def updateUsingParsed(self, parsed):
        """Update the feed using parsed XML passed in"""
        self.parsed = parsed

        try:
            self.title = self.parsed["feed"]["title"]
        except KeyError:
            try:
                self.title = self.parsed["channel"]["title"]
            except KeyError:
                pass
        if (self.parsed.feed.has_key('image') and 
            self.parsed.feed.image.has_key('url')):
            self.thumbURL = self.parsed.feed.image.url
            self.ufeed.iconCache.requestUpdate(is_vital=True)
        items_byid = {}
        items_nokey = []
        for item in self.items:
            try:
                items_byid[item.getRSSID()] = item
            except KeyError:
                items_nokey.append (item)
        for entry in self.parsed.entries:
            entry = self.addScrapedThumbnail(entry)
            new = True
            if entry.has_key("id"):
                id = entry["id"]
                if items_byid.has_key (id):
                    item = items_byid[id]
                    if not _entry_equal(entry, item.getRSSEntry()):
                        item.update(entry)
                    new = False
            if new:
                for item in items_nokey:
                    if _entry_equal(entry, item.getRSSEntry()):
                        new = False
                    else:
                        try:
                            if _entry_equal (entry["enclosures"], item.getRSSEntry()["enclosures"]):
                                item.update(entry)
                                new = False
                        except:
                            pass
            if (new and entry.has_key('enclosures') and
                self.hasVideoFeed(entry.enclosures)):
                Item(self.ufeed.id,entry)
        try:
            updateFreq = self.parsed["feed"]["ttl"]
        except KeyError:
            updateFreq = 0
        self.setUpdateFrequency(updateFreq)
        
        if self.initialUpdate:
            self.initialUpdate = False
            if len(self.items) > 0:
                sortedItems = list(self.items)
                sortedItems.sort(lambda x, y: cmp(x.getPubDateParsed(), y.getPubDateParsed()))
                self.startfrom = sortedItems[-1].getPubDateParsed()
                sortedItems[-1].signalChange(needsSave=False)
            else:
                self.startfrom = datetime.min
        

    def addScrapedThumbnail(self,entry):
        if (entry.has_key('enclosures') and len(entry['enclosures'])>0 and
            entry.has_key('description') and 
            not entry['enclosures'][0].has_key('thumbnail')):
                desc = RSSFeedImpl.firstImageRE.search(unescape(entry['description']))
                if not desc is None:
                    entry['enclosures'][0]['thumbnail'] = FeedParserDict({'url': desc.expand("\\1")})
        return entry

    ##
    # Returns the URL of the license associated with the feed
    def getLicense(self):
        try:
            ret = self.parsed.license
        except:
            ret = ""
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


##
# A DTV Collection of items -- similar to a playlist
class Collection(FeedImpl):
    def __init__(self,ufeed,title = None):
        FeedImpl.__init__(self,ufeed,url = "dtv:collection",title = title,visible = False)

    ##
    # Adds an item to the collection
    def addItem(self,item):
        if isinstance(item,Item):
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
            self.linkHistory[url]['etag'] = etag
        if not modified is None:
            self.linkHistory[url]['modified'] = modified
        self.downloads = set()
        self.setUpdateFrequency(360)
        self.scheduleUpdateEvents(0)

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
            print "WARNING unhandled error for ScraperFeedImpl.getHTML: ", error
            self.checkDone()
        download = grabURL(url, callback, errback, etag=etag,
                modified=modified)
        self.downloads.add(download)

    def processDownloadedHTML(self, info, urlList, depth, linkNumber, top = False):
        self.ufeed.confirmDBThread()
        #print "Done grabbing %s" % info['updated-url']

        if not self.tempHistory.has_key(info['updated-url']):
            self.tempHistory[info['updated-url']] = {}
        if info.has_key('etag'):
            self.tempHistory[info['updated-url']]['etag'] = info['etag']
        if info.has_key('last-modified'):
            self.tempHistory[info['updated-url']]['modified'] = info['last-modified']

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
        link = link.strip()
        if dict.has_key('title'):
            title = dict['title']
        else:
            title = link
        for item in self.items:
            if item.getURL() == link:
                return
        if dict.has_key('thumbnail') > 0:
            i=Item(self.ufeed.id, FeedParserDict({'title':title,'enclosures':[FeedParserDict({'url':link,'thumbnail':FeedParserDict({'url':dict['thumbnail']})})]}),linkNumber = linkNumber)
        else:
            i=Item(self.ufeed.id, FeedParserDict({'title':title,'enclosures':[FeedParserDict({'url':link})]}),linkNumber = linkNumber)
        updateUandA(self.ufeed)

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

                if ((link[-4:].lower() in 
                    ['.mov','.wmv','.mp4','.m4v','.mp3','.ogg','.anx','.mpg','.avi']) or
                    (link[-5:].lower() in ['.mpeg'])):
                    mimetype = 'video/unknown'
                elif link[-8:].lower() == '.torrent':
                    mimetype = "application/x-bittorrent"
                #elif link.find('?') > 0 and link.lower().find('.htm') == -1:
                #    mimetype = self.getMimeType(link)
                #    #print " mimetype is "+mimetype
                else:
                    mimetype = 'text/html'
                if mimetype != None:
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
            print "cancling download: ", download.url
            download.cancel()
        self.downloads = set()

    #FIXME: go through and add error handling
    def update(self):
        self.ufeed.confirmDBThread()
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
            if not charset is None:
                handler = RSSLinkGrabber(baseurl,charset)
            else:
                handler = RSSLinkGrabber(baseurl)
            parser.setContentHandler(handler)
            try:
                parser.parse(StringIO(xmldata))
            except IOError, e:
                pass
            links = handler.links
            linkDict = {}
            for link in links:
                if link[0].startswith('http://') or link[0].startswith('https://'):
                    if not linkDict.has_key(toUTF8Bytes(link[0],charset)):
                        linkDict[toUTF8Bytes(link[0])] = {}
                    if not link[1] is None:
                        linkDict[toUTF8Bytes(link[0])]['title'] = toUTF8Bytes(link[1],charset).strip()
                    if not link[2] is None:
                        linkDict[toUTF8Bytes(link[0])]['thumbnail'] = toUTF8Bytes(link[2],charset)
            if setTitle and not handler.title is None:
                self.ufeed.confirmDBThread()
                try:
                    self.title = toUTF8Bytes(handler.title)
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
                self.title = toUTF8Bytes(lg.title)
            finally:
                self.ufeed.signalChange()
            
        linkDict = {}
        for link in links:
            if link[0].startswith('http://') or link[0].startswith('https://'):
                if not linkDict.has_key(toUTF8Bytes(link[0],charset)):
                    linkDict[toUTF8Bytes(link[0])] = {}
                if not link[1] is None:
                    linkDict[toUTF8Bytes(link[0])]['title'] = toUTF8Bytes(link[1],charset).strip()
                if not link[2] is None:
                    linkDict[toUTF8Bytes(link[0])]['thumbnail'] = toUTF8Bytes(link[2],charset)
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

##
# A feed of all of the Movies we find in the movie folder that don't
# belong to a "real" feed.  If the user changes her movies folder, this feed
# will continue to remember movies in the old folder.
#
class DirectoryFeedImpl(FeedImpl):

    def __init__(self,ufeed):
        FeedImpl.__init__(self,url = "dtv:directoryfeed",ufeed=ufeed,title = "Feedless Videos",visible = False)

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
        # Files known about by real feeds
        knownFiles = set()
        for item in views.items:
            if not item.feed_id is self.ufeed.id:
                knownFiles.add(os.path.normcase(item.getFilename()))

        # Remove items that are in feeds, but we have in our list
        for item in self.items:
            if item.getFilename() in knownFiles:
                item.remove()

        myFiles = set(x.getFilename() for x in self.items)

        #Adds any files we don't know about
        #Files on the filesystem
        moviesDir = config.get(prefs.MOVIES_DIRECTORY)
        if os.path.isdir(moviesDir):
            existingFiles = [os.path.normcase(os.path.join(moviesDir, f)) 
                    for f in os.listdir(moviesDir)]
            for file in existingFiles:
                if (os.path.isfile(file) and os.path.basename(file)[0] != '.' and 
                        not file in knownFiles and not file in myFiles):
                    FileItem(self.ufeed.id, file)
        self.scheduleUpdateEvents(-1)

    def onRestore(self):
        FeedImpl.onRestore(self)
        #FIXME: the update dies if all of the items aren't restored, so we 
        # wait a little while before we start the update
        self.scheduleUpdateEvents(.1)

##
# Search and Search Results feeds

class SearchFeedImpl (RSSFeedImpl):
    
    def __init__(self, ufeed):
        RSSFeedImpl.__init__(self, url='', ufeed=ufeed, title='dtv:search', visible=False)
        self.setUpdateFrequency(-1)
        self.setAutoDownloadable(False)
        self.searching = False
        self.lastEngine = 'yahoo'
        self.lastQuery = ''

    def quoteLastQuery(self):
        return escape(self.lastQuery)

    def getURL(self):
        return 'dtv:search'

    def getStatus(self):
        status = 'idle-empty'
        if self.searching:
            status =  'searching'
        elif len(self.items) > 0:
            status =  'idle-with-results'
        return status

    def reset(self, url='', searchState=False):
        self.ufeed.confirmDBThread()
        try:
            for item in self.items:
                item.remove()
            self.url = url
            self.searching = searchState
        finally:
            self.ufeed.signalChange()
    
    def preserveDownloads(self, downloadsFeed):
        self.ufeed.confirmDBThread()
        for item in self.items:
            if item.getState() not in ('new', 'not-downloaded'):
                item.setFeed(downloadsFeed.id)
        
    def lookup(self, engine, query):
        url = self.getRequestURL(engine, query)
        self.reset(url, True)
        self.lastQuery = query
        self.update()
        self.ufeed.signalChange()

    def getRequestURL(self, engine, query, filterAdultContents=True, limit=50):
        if query == "LET'S TEST DTV'S CRASH REPORTER TODAY":
            someVariable = intentionallyUndefinedVariableToTestCrashReporter

        if engine == 'yahoo':
            url =  "http://api.search.yahoo.com/VideoSearchService/rss/videoSearch.xml"
            url += "?appid=dtv_search"
            url += "&adult_ok=%d" % int(not filterAdultContents)
            url += "&results=%d" % limit
            url += "&format=any"
            url += "&query=%s" % urlencode(query)
        elif engine == 'blogdigger':
            url =  "http://blogdigger.com/media/rss.jsp"
            url += "?q=%s" % urlencode(query)
            url += "&media=video"
            url += "&media=torrent"
            url += "&sortby=date"
        return url

    def updateUsingParsed(self, parsed):
        self.searching = False
        RSSFeedImpl.updateUsingParsed(self, parsed)

    def update(self):
        if self.url is not None and self.url != '':
            RSSFeedImpl.update(self)

class SearchDownloadsFeedImpl(FeedImpl):
    def __init__(self, ufeed):
        FeedImpl.__init__(self, url='dtv:searchDownloads', ufeed=ufeed, 
                title=None, visible=False)
        self.setUpdateFrequency(-1)

class ManualFeedImpl(FeedImpl):
    """Videos/Torrents that have been added using by the user opening them
    with democracy.
    """

    def __init__(self, ufeed):
        FeedImpl.__init__(self, url='dtv:manualFeed', ufeed=ufeed, 
                title=None, visible=False)
        self.expire = 'never'
        self.setUpdateFrequency(-1)

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
                print "WARNING: scraped URL is non-ascii (%s)-- discarding" \
                        % match.group(3)
            else:
                link = urljoin(baseurl, linkURL)
                desc = match.group(4)
                imgMatch = HTMLLinkGrabber.imgPattern.match(desc)
                if imgMatch:
                    try:
                        thumb = urljoin(baseurl,
                                imgMatch.group(1).encode('ascii'))
                    except UnicodeError:
                        print ("WARNING: scraped thumbnail url is non-ascii "
                        "(%s) -- discarding"  % imgMatch.group(1))
                        thumb = None
                else:
                    thumb = None
                desc =  HTMLLinkGrabber.tagPattern.sub(' ',desc)
                self.links.append((link, desc, thumb))
            match = HTMLLinkGrabber.linkPattern.search(match.group(5))
        return self.links

class RSSLinkGrabber(xml.sax.handler.ContentHandler):
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

    def startElementNS(self, name, qname, attrs):
        uri = name[0]
        tag = name[1]
        if self.firstTag:
            self.firstTag = False
            if tag != 'rss':
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
                print "DTV: bad HTML in description for %s" % self.baseurl
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

# Grabs the feed link from the given webpage
class HTMLFeedURLParser(HTMLParser):
    def getLink(self,baseurl,data):
        self.baseurl = baseurl
        self.link = None
        try:
            self.feed(data)
        except HTMLParseError:
            print "DTV: error parsing "+str(baseurl)
        try:
            self.close()
        except HTMLParseError:
            print "DTV: error closing "+str(baseurl)
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
