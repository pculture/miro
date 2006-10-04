from copy import copy
from datetime import datetime, timedelta
from gtcache import gettext as _
from math import ceil
from xhtmltools import unescape,xhtmlify
from xml.sax.saxutils import unescape
import locale
import os
import shutil
import traceback

from download_utils import nextFreeFilename
from feedparser import FeedParserDict

from database import DDBObject, defaultDatabase, ObjectNotFoundError
from database import DatabaseConstraintError
from databasehelper import makeSimpleGetSet
from iconcache import IconCache
from templatehelper import escape
import app
import template
import downloader
import config
import dialogs
import eventloop
import feed
import filters
import menu
import prefs
import resource
import views
import random
import indexes
import util
import adscraper

# FIXME add support for onlyBody parameter for static templates so we
#       don't need to strip the outer HTML
import re
HTMLPattern = re.compile("^.*<body.*?>(.*)</body\s*>", re.S)

def updateUandA (feed):
    # Not toplevel to avoid a dependency loop at load time.
    import feed as feed_mod
    feed_mod.updateUandA (feed)

_charset = locale.getpreferredencoding()

class Item(DDBObject):
    """An item corresponds to a single entry in a feed. It has a single url
    associated with it.
    """

    def __init__(self, entry, linkNumber = 0, feed_id=None, parent_id=None):
        self.feed_id = feed_id
        self.parent_id = parent_id
        self.isContainerItem = None
        self.seen = False
        self.autoDownloaded = False
        self.pendingManualDL = False
        self.downloadedTime = None
        self.watchedTime = None
        self.pendingReason = ""
        self.entry = entry
        self.expired = False
        self.keep = False
        self.videoFilename = ""

        self.iconCache = IconCache(self)
        
        # linkNumber is a hack to make sure that scraped items at the
        # top of a page show up before scraped items at the bottom of
        # a page. 0 is the topmost, 1 is the next, and so on
        self.linkNumber = linkNumber
        self.creationTime = datetime.now()
        self.updateReleaseDate()
        self._initRestore()
        self._lookForFinishedDownloader()
        DDBObject.__init__(self)
        self.splitItem()
        updateUandA(self.getFeed())

    ##
    # Called by pickle during serialization
    def onRestore(self):
        if (self.iconCache == None):
            self.iconCache = IconCache (self)
        else:
            self.iconCache.dbItem = self
            self.iconCache.requestUpdate()
        self._initRestore()

    def _initRestore(self):
        """Common code shared between onRestore and __init__."""
        self.selected = False
        self.active = False
        self.childrenSeen = None
        self.downloader = None
        self.expiring = None

    def _lookForFinishedDownloader(self):
        dler = downloader.lookupDownloader(self.getURL())
        if dler and dler.isFinished():
            self.downloader = dler
            dler.addItem(self)

    getSelected, setSelected = makeSimpleGetSet('selected',
            changeNeedsSave=False)
    getActive, setActive = makeSimpleGetSet('active', changeNeedsSave=False)

    def getSelectedState(self, view):
        currentView = app.controller.selection.itemListSelection.currentView
        if not self.selected or view != currentView:
            return 'normal'
        elif not self.active:
            return 'selected-inactive'
        else:
            return 'selected'

    def findChildVideos(self):
        """If this item points to a directory, return the set all video files
        under that directory.
        """

        videos = set()
        filename_root = self.getFilename()
        if os.path.isdir(filename_root):
            for (dirpath, dirnames, filenames) in os.walk(filename_root):
                for name in filenames:
                    filename = os.path.join (dirpath, name)
                    if isAllowedFilename(filename):
                        videos.add(filename)
        return videos

    def findNewChildren(self):
        """If this feed is a container item, walk through its directory and
        find any new children.  Returns True if it found childern and ran
        signalChange().
        """

        if not self.isContainerItem:
            return False
        if self.getState() == 'downloading':
            # don't try to find videos that we're in the middle of
            # re-downloading
            return False
        videos = self.findChildVideos()
        for child in self.getChildren():
            videos.discard(child.getFilename())
        for video in videos:
            FileItem (video, parent_id=self.id)
        if videos:
            self.signalChange(needsUpdateUandA=True)
            return True
        return False

    def splitItem(self):
        """returns True if it ran signalChange()"""
        if self.isContainerItem is not None:
            return self.findNewChildren()
        if not isinstance (self, FileItem) and (self.downloader is None or not self.downloader.isFinished()):
            return False
        filename_root = self.getFilename()
        if os.path.isdir(filename_root):
            videos = self.findChildVideos()
            if len(videos) > 1:
                self.isContainerItem = True
                for video in videos:
                    assert video.startswith(filename_root)
                    FileItem (video, parent_id=self.id)
            elif len(videos) == 1:
                self.isContainerItem = False
                for video in videos:
                    self.videoFilename = video
            else:
                if self.getFeedURL() != "dtv:directoryfeed":
                    target_dir = config.get(prefs.NON_VIDEO_DIRECTORY)
                    if not filename_root.startswith(target_dir):
                        if isinstance(self, FileItem):
                            self.migrate (target_dir)
                        else:
                            self.downloader.migrate (target_dir)
                self.isContainerItem = False
        else:
            self.isContainerItem = False
            self.videoFilename = filename_root
        self.signalChange(needsUpdateUandA=True)
        return True

    def removeFromPlaylists(self):
        itemIDIndex = indexes.playlistsByItemID
        view = views.playlists.filterWithIndex(itemIDIndex, self.getID())
        for playlist in view:
            playlist.removeItem(self)
        view = views.playlistFolders.filterWithIndex(itemIDIndex, self.getID())
        for playlist in view:
            playlist.removeItem(self)

    def updateReleaseDate(self):
        # This should be called whenever we get a new entry
        try:
            self.releaseDateObj = datetime(*self.getFirstVideoEnclosure().updated_parsed[0:7])
        except:
            try:
                self.releaseDateObj = datetime(*self.entry.updated_parsed[0:7])
            except:
                self.releaseDateObj = datetime.min


    def checkConstraints(self):
        if self.feed_id is not None:
            try:
                obj = self.dd.getObjectByID(self.feed_id)
            except ObjectNotFoundError:
                raise DatabaseConstraintError("my feed (%s) is not in database" % self.feed_id)
            else:
                if not isinstance(obj, feed.Feed):
                    msg = "feed_id points to a %s instance" % obj.__class__
                    raise DatabaseConstraintError(msg)
        if self.parent_id is not None:
            try:
                obj = self.dd.getObjectByID(self.parent_id)
            except ObjectNotFoundError:
                raise DatabaseConstraintError("my parent (%s) is not in database" % self.parent_id)
            else:
                if not isinstance(obj, Item):
                    msg = "parent_id points to a %s instance" % obj.__class__
                    raise DatabaseConstraintError(msg)
                # If isContainerItem is None, we may be in the middle of building the children list.
                if obj.isContainerItem is not None and not obj.isContainerItem:
                    msg = "parent_id is not a containerItem"
                    raise DatabaseConstraintError(msg)
        if self.parent_id is None and self.feed_id is None:
            raise DatabaseConstraintError ("feed_id and parent_id both None")
        if self.parent_id is not None and self.feed_id is not None:
            raise DatabaseConstraintError ("feed_id and parent_id both not None")

    # Unfortunately, our database does not scale well with many views,
    # so we have this hack to make sure that unwatched and available
    # get updated when an item changes
    def signalChange(self, needsSave=True, needsUpdateUandA=False, needsUpdateXML=True):
        self.expiring = None
        if hasattr(self, "_state"):
            del self._state
        if hasattr(self, "_size"):
            del self._size
        DDBObject.signalChange(self, needsSave=needsSave)
        if needsUpdateXML:
            try:
                del self._itemXML
            except:
                pass
        if needsUpdateUandA:
            try:
                # If the feed has been deleted, getFeed will throw an exception
                updateUandA(self.getFeed())
            except:
                pass

    # Returns the rendered download-item template, hopefully from the cache
    #
    # viewName is the name of the view we're in. 
    # view is the actual view object that we're in.
    #
    # Almost all of the search string is cached, but there are several pieces
    # of data that must be generated on the fly:
    #  * The name of the view, used for things like action:playNamedView
    #  * The dragdesttype attribute -- it's based on the current selection
    #  * The selected css class -- it's depends on whether the view that this
    #     item is in is the view that's selected.  This matters when an item
    #     is shown multiple times on a page, in different views.
    def getItemXML(self, viewName, view):
        try:
            xml = self._itemXML
        except AttributeError:
            self._calcItemXML(view)
            xml = self._itemXML
        if viewName == 'playlistView':
            dragDestType = 'downloadeditem'
        else:
            dragDestType = ''
        for old, new in [
            (self._XMLViewName, viewName),
            ("---DRAGDESTTYPE---", dragDestType),
            ("---SELECTEDSTATE---", self.getSelectedState(view)),
        ]:
                xml = xml.replace(old, new)
        return xml

    # Regenerates an expired item XML from the download-item template
    # _XMLViewName is a random string we use for the name of the view
    # _itemXML is the rendered XML
    def _calcItemXML(self, view):
        self._XMLViewName = "view%dview" % random.randint(9999999,99999999)
        self._itemXML = HTMLPattern.match(template.fillStaticTemplate('download-item','unknown','noCookie', '', this=self, viewName = self._XMLViewName)).group(1)

    #
    # Returns True iff this item has never been viewed in the interface
    # Note the difference between "viewed" and seen
    def getViewed(self):
        try:
            # optimizing by trying the cached feed
            return self._feed.lastViewed >= self.creationTime
        except:
            return self.creationTime <= self.getFeed().lastViewed 

    ##
    # Returns the first video enclosure in the item
    def getFirstVideoEnclosure(self):
        try:
            return self._firstVidEnc
        except:
            self._calcFirstEnc()
            return self._firstVidEnc

    def _calcFirstEnc(self):
        self._firstVidEnc = getFirstVideoEnclosure(self.entry)
        

    ##
    # Returns mime-type of the first video enclosure in the item
    def getFirstVideoEnclosureType(self):
        enclosure = self.getFirstVideoEnclosure()
        if enclosure and enclosure.has_key('type'):
            return enclosure['type']
        return None


    ##
    # Returns the URL associated with the first enclosure in the item
    def getURL(self):
        self.confirmDBThread()
        videoEnclosure = self.getFirstVideoEnclosure()
        if videoEnclosure is not None and 'url' in videoEnclosure:
            return videoEnclosure['url']
        else:
            return ''

    def hasSharableURL(self):
        """Does this item have a URL that the user can share with others?

        This returns True when the item has a non-file URL.
        """
        url = self.getURL()
        return url != '' and not url.startswith("file:")

    ##
    # Returns the feed this item came from
    def getFeed(self):
        try:
            # optimizing by caching the feed
            return self._feed
        except:
            if self.feed_id is not None:
                self._feed = self.dd.getObjectByID(self.feed_id)
            elif self.parent_id is not None:
                self._feed = self.getParent().getFeed()
            else:
                self._feed = None
            return self._feed

    def getParent(self):
        try:
            return self._parent
        except:
            if self.parent_id is not None:
                self._parent = self.dd.getObjectByID(self.parent_id)
            else:
                self._parent = self
            return self._parent

    def getFeedURL(self):
        return self.getFeed().getURL()

    def feedExists(self):
        return self.feed_id and self.dd.idExists(self.feed_id)

    def getChildren(self):
        if self.isContainerItem:
            return views.items.filterWithIndex(indexes.itemsByParent, self.id)
        else:
            raise ValueError("%s is not a container item" % self)

    ##
    # Moves this item to another feed.
    def setFeed(self, feed_id):
        updateUandA(self.getFeed())
        self.feed_id = feed_id
        del self._feed
        if self.isContainerItem:
            for item in self.getChildren():
                del item._feed
                item.signalChange()
        self.signalChange()
        updateUandA(self.getFeed())

    def executeExpire(self):
        self.confirmDBThread()
        self.removeFromPlaylists()
        UandA = self.getUandA()
        self.deleteFile()
        self.expired = True
        if self.isContainerItem:
            for item in self.getChildren():
                item.remove()
        self.isContainerItem = None
        self.seen = self.keep = self.pendingManualDL = False
        self.watchedTime = None
        if self.getFeedURL() != "dtv:manualFeed":
            self.signalChange(needsUpdateUandA = (UandA != self.getUandA()))
        else:
            self.remove()

    ##
    # Marks this item as expired
    def expire(self):
        if self.isContainerItem:
            title = _("Deleting %s") % (os.path.basename(self.getTitle()))
            description = _("""\
This item is a folder.  When you delete a folder, any items inside that \
folder will also be deleted.""")
            d = dialogs.ChoiceDialog(title, description,
                                     dialogs.BUTTON_DELETE_FILES,
                                     dialogs.BUTTON_CANCEL)
            def callback(dialog):
                if self.idExists() and dialog.choice == dialogs.BUTTON_DELETE_FILES:
                    self.executeExpire()
            d.run(callback)
        else:
            self.executeExpire()


    def getExpirationString(self):
        """Get the expiration time a string to display to the user."""
        expireTime = self.getExpirationTime()
        if expireTime is None:
            return ""
        else:
            exp = expireTime - datetime.now()
            if exp.days > 0:
                time = _("%d days") % exp.days
            elif exp.seconds > 3600:
                time = _("%d hrs") % (ceil(exp.seconds/3600.0))
            else:
                time = _("%d min") % (ceil(exp.seconds/60.0))
        return _('Expires: %s') % time

    def getDragType(self):
        if self.isDownloaded():
            return 'downloadeditem'
        else:
            return 'item'

    def getEmblemCSSClass(self):
        if not self.getViewed():
            return 'new'
        elif self.getState() == 'newly-downloaded':
            return 'newly-downloaded'
        else:
            return ''

    def getEmblemCSSString(self):
        if not self.getViewed():
            return 'NEW'
        elif self.getState() == 'newly-downloaded':
            return 'UNWATCHED'
        else:
            return ''

    def getUandA(self):
        """Get whether this item is new, or newly-downloaded, or neither."""
        state = self.getEmblemCSSClass()
        if state == 'new':
            return (0, 1)
        elif state == 'newly-downloaded':
            return (1, 0)
        else:
            return (0, 0)

    def getExpirationTime(self):
        """Get the time when this item will expire. 
        Returns a datetime object,  or None if it doesn't expire.
        """

        self.confirmDBThread()
        if self.getWatchedTime() is None or not self.isDownloaded():
            return None
        ufeed = self.getFeed()
        if ufeed.expire == 'never' or (ufeed.expire == 'system'
                and config.get(prefs.EXPIRE_AFTER_X_DAYS) <= 0):
            return None
        else:
            if ufeed.expire == "feed":
                expireTime = ufeed.expireTime
            elif ufeed.expire == "system":
                expireTime = timedelta(days=config.get(prefs.EXPIRE_AFTER_X_DAYS))
            return self.getWatchedTime() + expireTime

    def getWatchedTime(self):
        if not self.getSeen():
            return None
        if self.isContainerItem and self.watchedTime == None:
            self.watchedTime = datetime.min
            for item in self.getChildren():
                childTime = item.getWatchedTime()
                if childTime is None:
                    self.watchedTime = None
                    return None
                if childTime > self.watchedTime:
                    self.watchedTime = childTime
            self.signalChange()
        return self.watchedTime

    def getExpiring(self):
        if self.expiring is None:
            if not self.getSeen():
                self.expiring = False
            else:
                ufeed = self.getFeed()
                if (self.keep or ufeed.expire == 'never' or 
                        (ufeed.expire == 'system' and
                            config.get(prefs.EXPIRE_AFTER_X_DAYS) <= 0)):
                    self.expiring = False
                else:
                    self.expiring = True
        return self.expiring

    ##
    # returns true iff video has been seen
    # Note the difference between "viewed" and "seen"
    def getSeen(self):
        self.confirmDBThread()
        if self.isContainerItem:
            if self.childrenSeen is None:
                self.childrenSeen = True
                for item in self.getChildren():
                    if not item.seen:
                        self.childrenSeen = False
                        break
            return self.childrenSeen
        else:
            return self.seen

    ##
    # Marks the item as seen
    def markItemSeen(self):
        self.confirmDBThread()
        if self.seen == False:
            self.seen = True
            if self.watchedTime is None:
                self.watchedTime = datetime.now()
            self.clearParentsChildrenSeen()
            self.signalChange(needsUpdateUandA=True)

    def clearParentsChildrenSeen(self):
        if self.parent_id:
            parent = self.getParent()
            parent.childrenSeen = None
            parent.signalChange(needsUpdateUandA=True)

    def markItemUnseen(self):
        self.confirmDBThread()
        if self.isContainerItem:
            self.childrenSeen = False
            for item in self.getChildren():
                item.seen = False
                item.signalChange()
            self.signalChange()
        else:
            if self.seen == False:
                return
            self.seen = False
            self.watchedTime = None
            self.clearParentsChildrenSeen()
            self.signalChange()
        updateUandA(self.getFeed())

    def getRSSID(self):
        self.confirmDBThread()
        return self.entry["id"]

    def removeRSSID(self):
        self.confirmDBThread()
        if 'id' in self.entry:
            del self.entry['id']
            self.signalChange()

    def setAutoDownloaded(self,autodl = True):
        self.confirmDBThread()
        if autodl != self.autoDownloaded:
            self.autoDownloaded = autodl
            self.signalChange(needsUpdateUandA=True)

    def getPendingReason(self):
        self.confirmDBThread()
        return self.pendingReason

    ##
    # Returns true iff item was auto downloaded
    def getAutoDownloaded(self):
        self.confirmDBThread()
        return self.autoDownloaded

    ##
    # Returns the linkNumber
    def getLinkNumber(self):
        self.confirmDBThread()
        return self.linkNumber

    ##
    # Starts downloading the item
    def download(self,autodl=False):
        self.confirmDBThread()
        manualDownloadCount = views.manualDownloads.len()
        self.expired = self.keep = self.seen = False

        if ((not autodl) and 
                manualDownloadCount >= config.get(prefs.MAX_MANUAL_DOWNLOADS)):
            self.pendingManualDL = True
            self.pendingReason = "queued for download"
            self.signalChange(needsUpdateUandA=True)
            return
        else:
            self.setAutoDownloaded(autodl)
            self.pendingManualDL = False

        if self.downloader is None:
            self.downloader = downloader.getDownloader(self)
        if self.downloader.isFinished():
            self.onDownloadFinished()
        else:
            self.downloader.start()
        self.signalChange(needsUpdateUandA=True)

    def isPendingManualDownload(self):
        self.confirmDBThread()
        return self.pendingManualDL

    def isEligibleForAutoDownload(self):
        self.confirmDBThread()
        if self.getState() not in ('new', 'not-downloaded'):
            return False
        if self.downloader and self.downloader.getState() in ('failed',
                'stopped', 'paused'):
            return False
        ufeed = self.getFeed()
        if ufeed.getEverything:
            return True
        pubDate = self.getPubDateParsed()
        return pubDate >= ufeed.startfrom and pubDate != datetime.max

    def isPendingAutoDownload(self):
        return (self.getFeed().isAutoDownloadable() and
                self.isEligibleForAutoDownload())

    def isFailedDownload(self):
        return self.downloader and self.downloader.getState() == 'failed'

    ##
    # Returns a link to the thumbnail of the video
    def getThumbnailURL(self):
        self.confirmDBThread()
        # Try to get the thumbnail specific to the video enclosure
        videoEnclosure = self.getFirstVideoEnclosure()
        if videoEnclosure is not None:
            try:
                return videoEnclosure["thumbnail"]["url"]
            except:
                pass 
        # Try to get any enclosure thumbnail
        for enclosure in self.entry.enclosures:
            try:
                return enclosure["thumbnail"]["url"]
            except KeyError:
                pass
        # Try to get the thumbnail for our entry
        try:
            return self.entry["thumbnail"]["url"]
        except:
            return None

    def getThumbnail (self):
        self.confirmDBThread()
        if self.iconCache.isValid():
            basename = os.path.basename(self.iconCache.getFilename())
            return resource.iconCacheUrl(basename)
        elif self.isContainerItem:
            return resource.url("images/container-icon.png")
        else:
            return resource.url("images/thumb.png")
    ##
    # returns the title of the item
    def getTitle(self):
        try:
            return self.entry.title
        except:
            try:
                enclosure = self.getFirstVideoEnclosure()
                return enclosure["url"]
            except:
                return ""

    ##
    # Returns the raw description of the video
    def getRawDescription(self):
        self.confirmDBThread()
        try:
            enclosure = self.getFirstVideoEnclosure()
            return enclosure["text"]
        except:
            try:
                return self.entry.description
            except:
                return '<span />'

    ##
    # Returns valid XHTML containing a description of the video
    def getDescription(self):
        rawDescription = self.getRawDescription()
        purifiedDescription = adscraper.purify(rawDescription)
        unescapedDescription = unescape(purifiedDescription)
        description = '<span>%s</span>' % unescapedDescription
        return xhtmlify(description)

    def getAd(self):
        rawDescription = self.getRawDescription()
        rawAd = adscraper.scrape(rawDescription)
        ad = '<span>%s</span>' % unescape(rawAd)
        return xhtmlify(ad)

    def looksLikeTorrent(self):
        """Returns true if we think this item is a torrent.  (For items that
        haven't been downloaded this uses the file extension which isn't
        totally reliable).
        """

        if self.downloader is not None:
            return self.downloader.getType() == 'bittorrent'
        else:
            return self.getURL().endswith('.torrent')

    ##
    # Returns formatted XHTML with release date, duration, format, and size
    def getDetails(self):
        details = []
        reldate = self.getReleaseDate()
        duration = self.getDuration()
        format = self.getFormat()
        size = self.getSizeForDisplay()

        if self.isContainerItem:
            children = self.getChildren()
            details.append('<span class="details-count">%s items</span>' % len(children))
        if len(reldate) > 0:
            details.append('<span class="details-date">%s</span>' % escape(reldate))
        if len(duration) > 0:
            details.append('<span class="details-duration">%s</span>' % escape(duration))
        if len(size) > 0:
            details.append('<span class="details-size">%s</span>' % escape(size))
        if len(format) > 0:
            details.append('<span class="details-format">%s</span>' % escape(format))
        if self.looksLikeTorrent():
            details.append('<span class="details-torrent" il8n:translate="">TORRENT</span>')
        out = '<BR>'.join(details)
        return out

    ##
    # Stops downloading the item
    def deleteFile(self):
        self.confirmDBThread()
        if self.downloader is not None:
            self.downloader.removeItem(self)
            self.downloader = None
            self.signalChange(needsUpdateUandA=True)

    def getState(self):
        """Get the state of this item.  The state will be on of the following:

        * new -- User has never seen this item
        * not-downloaded -- User has seen the item, but not downloaded it
        * downloading -- Item is currently downloading
        * newly-downloaded -- Item has been downoladed, but not played
        * expiring -- Item has been played and is set to expire
        * saved -- Item has been played and has been saved
        * expired -- Item has expired.

        Uses caching to prevent recalculating state over and over
        """
        try:
            return self._state
        except AttributeError:
            self._calcState()
            return self._state

    # Recalculate the state of an item after a change
    def _calcState(self):
        self.confirmDBThread()
        # FIXME, 'failed', and 'paused' should get download icons.  The user
        # should be able to restart or cancel them (put them into the stopped
        # state).
        if (self.downloader is None  or 
                self.downloader.getState() in ('failed', 'stopped', 'paused')):
            if self.pendingManualDL:
                self._state = 'downloading'
            elif self.expired:
                self._state = 'expired'
            elif not self.getViewed():
                self._state = 'new'
            else:
                self._state = 'not-downloaded'
        elif not self.downloader.isFinished():
            self._state = 'downloading'
        elif not self.getSeen():
            self._state = 'newly-downloaded'
        elif self.getExpiring():
            self._state = 'expiring'
        else:
            self._state = 'saved'

    def getChannelCategory(self):
        """Get the category to use for the channel template.  
        
        This method is similar to getState(), but has some subtle differences.
        getState() is used by the download-item template and is usually more
        useful to determine what's actually happening with an item.
        getChannelCategory() is used by by the channel template to figure out
        which heading to put an item under.

        * downloading and not-downloaded are grouped together as
          not-downloaded
        * Newly downloaded and downloading items are always new if
          their feed hasn't been marked as viewed after the item's pub
          date.  This is so that when a user gets a list of items and
          starts downloading them, the list doesn't reorder itself.
          Once they start watching them, then it reorders itself.
        """

        self.confirmDBThread()
        if self.downloader is None or not self.downloader.isFinished():
            if not self.getViewed():
                return 'new'
            if self.expired:
                return 'expired'
            else:
                return 'not-downloaded'
        elif not self.getSeen():
            if not self.getViewed():
                return 'new'
            return 'newly-downloaded'
        elif self.getExpiring():
            return 'expiring'
        else:
            return 'saved'

    def isDownloadable(self):
        return self.getState() in ('new', 'not-downloaded', 'expired')

    def isDownloaded(self):
        return self.getState() in ("newly-downloaded", "expiring", "saved")

    def showSaveButton(self):
        return (self.getState() in ('newly-downloaded', 'expiring') and
                self.getExpirationTime() is not None)

    def showTrashButton(self):
        return self.isDownloaded() or (self.getFeedURL() == 'dtv:manualFeed'
                and self.getState() != 'downloading')

    def getFailureReason(self):
        self.confirmDBThread()
        if self.downloader is not None:
            return self.downloader.getShortReasonFailed()
        else:
            return ""
    
    ##
    # Returns the size of the item to be displayed. If the item has a
    # corresponding downloaded enclosure we use the pysical size of the file,
    # otherwise we use the RSS enclosure tag values.
    def getSizeForDisplay(self):
        if not hasattr(self, "_size"):
            fname = self.getFilename()
            try:
                if os.path.isdir(fname):
                    size = 0
                    for (dirpath, dirnames, filenames) in os.walk(fname):
                        for name in filenames:
                            size += os.path.getsize(os.path.join(dirpath, name))
                        size += os.path.getsize(dirpath)
                else:
                    size = os.path.getsize(fname)
                self._size = util.formatSizeForUser(size)
            except:
                self._size = self.getEnclosuresSize()
        return self._size
    
    ##
    # Returns the total size of all enclosures in bytes
    def getEnclosuresSize(self):
        size = 0
        try:
            size = int(self.getFirstVideoEnclosure()['length'])
        except:
            pass
        return util.formatSizeForUser(size)

    ##
    # returns status of the download in plain text
    def getCurrentSize(self):
        if self.downloader is not None:
            size = self.downloader.getCurrentSize()
        else:
            size = 0
        return util.formatSizeForUser(size)

    ##
    # Returns the download progress in absolute percentage [0.0 - 100.0].
    def downloadProgress(self):
        progress = 0
        self.confirmDBThread()
        if self.downloader is None:
            return 0
        else:
            size = self.downloader.getTotalSize()
            dled = self.downloader.getCurrentSize()
            if size == 0:
                return 0
            else:
                return (100.0*dled) / size

    def gotContentLength(self):
        if self.downloader is None:
            return False
        else:
            return self.downloader.getTotalSize() != -1

    ##
    # Returns the width of the progress bar corresponding to the current
    # download progress. This doesn't really belong here and even forces
    # to use a hardcoded constant, but the templating system doesn't 
    # really leave any other choice.
    def downloadProgressWidth(self):
        fullWidth = 92  # width of resource:channelview-progressbar-bg.png - 2
        progress = self.downloadProgress() / 100.0
        if progress == 0:
            return 0
        return int(progress * fullWidth)

    ##
    # Returns string containing three digit percent finished
    # "000" through "100".
    def threeDigitPercentDone(self):
        return '%03d' % int(self.downloadProgress())

    def downloadInProgress(self):
        return self.downloader is not None and self.downloader.getETA() != 0

    ##
    # Returns string with estimate time until download completes
    def downloadETA(self):
        if self.downloader is not None:
            secs = self.downloader.getETA()
        else:
            secs = 0
        mins, secs = divmod(secs, 60)
        hours, mins = divmod(mins, 60)
        if secs == -1:
            return _('downloading...')
        elif hours > 0:
            time = "%d:%02d:%02d" % (hours, mins, secs)
            return _("%s left") % time
        else:
            time = "%d:%02d" % (mins, secs)
            return _("%s left") % time

    def getStartupActivity(self):
        if self.pendingManualDL:
            return self.pendingReason
        elif self.downloader:
            return self.downloader.getStartupActivity()
        else:
            return _("starting up...")

    ##
    # Returns the download rate
    def downloadRate(self):
        rate = 0
        unit = "k/s"
        if self.downloader is not None:
            rate = self.downloader.getRate()
        else:
            rate = 0
        rate /= 1024
        if rate > 1024:
            rate /= 1024
            unit = "m/s"
        if rate > 1024:
            rate /= 1024
            unit = "g/s"
            
        return "%d%s" % (rate, unit)

    ##
    # Returns the published date of the item
    def getPubDate(self):
        try:
            return self.releaseDateObj.strftime("%b %d %Y").decode(_charset)
        except: 
            return ""
    
    ##
    # Returns the published date of the item as a datetime object
    def getPubDateParsed(self):
        return self.releaseDateObj

    ##
    # returns the date this video was released or when it was published
    def getReleaseDate(self):
        try:
            return self.releaseDateObj.strftime("%b %d %Y").decode(_charset)
        except:
            return ""

    ##
    # returns the date this video was released or when it was published
    def getReleaseDateObj(self):
        return self.releaseDateObj

    ##
    # returns string with the play length of the video
    def getDuration(self, emptyIfZero=True):
        secs = 0
        #FIXME get this from VideoInfo
        if secs == 0:
            if emptyIfZero:
                return ""
            else:
                return "n/a"
        if (secs < 120):
            return '%1.0f secs' % secs
        elif (secs < 6000):
            return '%1.0f mins' % ceil(secs/60.0)
        else:
            return '%1.1f hours' % ceil(secs/3600.0)

    ##
    # returns string with the format of the video
    KNOWN_MIME_TYPES = ('audio', 'video')
    KNOWN_MIME_SUBTYPES = ('mov', 'wmv', 'mp4', 'mp3', 'mpg', 'mpeg', 'avi', 'x-flv', 'x-msvideo')
    def getFormat(self, emptyForUnknown=True):
        try:
            enclosure = self.entry['enclosures'][0]
            try:
                extension = enclosure['url'].split('.')[-1].lower()
            except:
                extension == ''
            # Hack for mp3s, "mpeg audio" isn't clear enough
            if extension.lower() == 'mp3':
                return 'MP3'
            if enclosure.has_key('type') and len(enclosure['type']) > 0:
                mtype, subtype = enclosure['type'].split('/')
                mtype = mtype.lower()
                if mtype in self.KNOWN_MIME_TYPES:
                    format = subtype.split(';')[0].upper()
                    if mtype == 'audio':
                        format += ' AUDIO'
                    if format.startswith('X-'):
                        format = format[2:]
                    return format
            else:
                if extension in self.KNOWN_MIME_SUBTYPES:
                    return extension.upper()
        except:
            pass
        if emptyForUnknown:
            return ""
        else:
            return "unknown"

    ##
    # return keyword tags associated with the video separated by commas
    def getTags(self):
        self.confirmDBThread()
        try:
            return self.entry.categories.join(", ")
        except:
            return ""

    ##
    # return the license associated with the video
    def getLicence(self):
        self.confirmDBThread()
        try:
            return self.entry.license
        except:
            try:
                return self.getFeed().getLicense()
            except:
                return ""

    ##
    # return the people associated with the video, separated by commas
    def getPeople(self):
        ret = []
        self.confirmDBThread()
        try:
            for role in self.getFirstVideoEnclosure().roles:
                for person in self.getFirstVideoEnclosure().roles[role]:
                    ret.append(person)
            for role in self.entry.roles:
                for person in self.entry.roles[role]:
                    ret.append(person)
        except:
            pass
        return ', '.join(ret)

    ##
    # returns the URL of the webpage associated with the item
    def getLink(self):
        self.confirmDBThread()
        try:
            return self.entry.link
        except:
            return ""

    ##
    # returns the URL of the payment page associated with the item
    def getPaymentLink(self):
        self.confirmDBThread()
        try:
            return self.getFirstVideoEnclosure().payment_url
        except:
            try:
                return self.entry.payment_url
            except:
                return ""

    ##
    # returns a snippet of HTML containing a link to the payment page
    # HTML has already been sanitized by feedparser
    def getPaymentHTML(self):
        self.confirmDBThread()
        try:
            ret = self.getFirstVideoEnclosure().payment_html
        except:
            try:
                ret = self.entry.payment_html
            except:
                ret = ""
        # feedparser returns escaped CDATA so we either have to change its
        # behavior when it parses dtv:paymentlink elements, or simply unescape
        # here...
        return '<span>' + unescape(ret) + '</span>'

    def makeContextMenu(self, templateName, view):
        c = app.controller # easier/shorter to type
        if self.isDownloaded():
            if templateName in ('playlist', 'playlist-folder'):
                label = _('Remove From Playlist')
            else:
                label = _('Remove From My Collection')
            items = [
                (lambda: c.playView(view, self.getID()), _('Play')),
                (lambda: c.playView(view, self.getID(), True), 
                    _('Play Just This Video')),
                (c.addToNewPlaylist, _('Add to new playlist')),
                (c.removeCurrentItems, label),
            ]
            if self.getSeen():
                items.append((self.markItemUnseen, _('Mark as Unwatched')))
        elif self.getState() == 'downloading':
            items = [(self.expire, _('Cancel Download'))]
        else:
            items = [(self.download, _('Download'))]
        return menu.makeMenu(items)

    ##
    # Updates an item with new data
    #
    # @param entry a dict object containing the new data
    def update(self, entry):
        UandA = self.getUandA()
        self.confirmDBThread()
        try:
            self.entry = entry
            self.iconCache.requestUpdate()
            self.updateReleaseDate()
            self._calcFirstEnc()
        finally:
            self.signalChange(needsUpdateUandA = (UandA != self.getUandA()))

    def onDownloadFinished(self):
        """Called when the download for this item finishes."""

        self.confirmDBThread()
        self.downloadedTime = datetime.now()
        if not self.splitItem():
            self.signalChange(needsUpdateUandA=True)

        for other in views.items:
            if other.downloader is None and other.getURL() == self.getURL():
                other.downloader = self.downloader
                self.downloader.addItem(other)
                other.signalChange(needsSave=False)
        
        app.delegate.notifyDownloadCompleted(self)

    def save(self):
        self.confirmDBThread()
        if self.keep != True:
            self.keep = True
            self.signalChange(needsUpdateUandA=True)

    ##
    # gets the time the video was downloaded
    # Only valid if the state of this item is "finished"
    def getDownloadedTime(self):
        if self.downloadedTime is None:
            return datetime.min
        else:
            return self.downloadedTime

    ##
    # Returns the filename of the first downloaded video or the empty string
    # NOTE: this will always return the absolute path to the file.
    def getFilename(self):
        self.confirmDBThread()
        try:
            return self.downloader.getFilename()
        except:
            return ""

    ##
    # Returns the filename of the first downloaded video or the empty string
    # NOTE: this will always return the absolute path to the file.
    def getVideoFilename(self):
        self.confirmDBThread()
        return self.videoFilename

    def isNonVideoFile(self):
        return self.isContainerItem != True and self.getVideoFilename() == ""

    def isExternal(self):
        """Returns True iff this item was not downloaded from a Democracy
        channel.
        """
        return False

    def isPlayable(self):
        """Returns True iff this item should have a play button."""
        if not self.isContainerItem:
            return self.isDownloaded() and self.getVideoFilename()
        else:
            return self.isDownloaded() and len(self.getChildren()) > 0

    def getRSSEntry(self):
        self.confirmDBThread()
        return self.entry

    def migrateChildren (self, newdir):
        if self.isContainerItem:
            for item in self.getChildren():
                item.migrate(newdir)
        

    def remove(self):
        if self.downloader is not None:
            self.downloader.removeItem(self)
            self.downloader = None
        if self.iconCache is not None:
            self.iconCache.remove()
            self.iconCache = None
        if self.isContainerItem:
            for item in self.getChildren():
                item.remove()
        DDBObject.remove(self)

    def setupLinks(self):
        """This is called after we restore the database.  Since we don't store
        references between objects, we need a way to reconnect downloaders to
        the items after the restore.
        """
        
        if not isinstance (self, FileItem) and self.downloader is None:
            self.downloader = downloader.getExistingDownloader(self)
            if self.downloader is not None:
                self.signalChange(needsSave=False, needsUpdateUandA=False)
        self.splitItem()
        # Do this here instead of onRestore in case the feed hasn't
        # been loaded yet.
        updateUandA(self.getFeed())
        # This must come after reconnecting the downloader
        if self.isContainerItem is not None and not os.path.exists(self.getFilename()):
            self.executeExpire()

    def __str__(self):
        return "Item - %s" % self.getTitle()

def reconnectDownloaders():
    reconnected = set()
    for item in views.items:
        item.setupLinks()
        reconnected.add(item.downloader)
    for downloader in views.remoteDownloads:
        if downloader not in reconnected:
            print "removing orphaned downloader: ", downloader.url
            downloader.remove()
    manualFeed = util.getSingletonDDBObject(views.manualFeed)
    manualItems = views.items.filterWithIndex(indexes.itemsByFeed,
            manualFeed.getID())
    for item in manualItems:
        if item.downloader is None:
            print "removing cancelled external torrent: ", item
            item.remove()

def getEntryForFile(filename):
    return FeedParserDict({'title':os.path.basename(filename),
            'enclosures':[{'url': 'file://%s' % filename}]})

##
# An Item that exists as a local file
class FileItem(Item):

    def __init__(self,filename, feed_id=None, parent_id=None, shortFilename=None):
        filename = os.path.abspath(filename)
        self.filename = filename
        self.deleted = False
        if shortFilename:
            self.shortFilename = shortFilename
        else:
            self.shortFilename = os.path.basename(self.filename)
        Item.__init__(self, getEntryForFile(filename), feed_id=feed_id, parent_id=parent_id)

    def getState(self):
        if self.deleted:
            return "expired"
        elif self.getSeen():
            return "saved"
        else:
            return "newly-downloaded"

    def getChannelCategory(self):
        """Get the category to use for the channel template.  
        
        This method is similar to getState(), but has some subtle differences.
        getState() is used by the download-item template and is usually more
        useful to determine what's actually happening with an item.
        getChannelCategory() is used by by the channel template to figure out
        which heading to put an item under.

        * downloading and not-downloaded are grouped together as
          not-downloaded
        * Items are always new if their feed hasn't been marked as viewed
          after the item's pub date.  This is so that when a user gets a list
          of items and starts downloading them, the list doesn't reorder
          itself.
        * Child items match their parents for expiring, where in
          getState, they always act as not expiring.
        """

        self.confirmDBThread()
        if self.deleted:
            return 'expired'
        elif not self.getSeen():
            return 'newly-downloaded'
        else:
            if self.parent_id and self.getParent().getExpiring():
                return 'expiring'
            else:
                return 'saved'

    def getExpiring(self):
        return False

    def showSaveButton(self):
        return False

    def getViewed(self):
        return True

    def isExternal(self):
        return self.parent_id is None

    def executeExpire(self):
        self.confirmDBThread()
        self.removeFromPlaylists()
        if self.isContainerItem:
            for item in self.getChildren():
                item.remove()
        if self.feed_id is None: 
            # child of a container item
            self.remove()
            dler = self.getParent().downloader
            if dler:
                dler.stop(False)
            self.deleteFiles()
        elif not os.path.exists (self.filename): 
            # external item whose file has been deleted outside of DP
            self.remove()
        else:
            # external item that the user deleted in DP
            self.deleted = True
            self.signalChange(needsUpdateUandA=True)

    def expire(self):
        if not self.isExternal():
            self.executeExpire()
            return
        title = _("Removing %s") % (os.path.basename(self.filename))
        if self.isContainerItem:
            description = _("""\
Would you like to delete this folder and all of its videos or just remove \
its entry from My Collection?""")
            button = dialogs.BUTTON_DELETE_FILES
        else:
            description = _("""\
Would you like to delete this file or just remove its entry from My \
Collection?""")
            button = dialogs.BUTTON_DELETE_FILE
        d = dialogs.ThreeChoiceDialog(title, description,
                dialogs.BUTTON_REMOVE_ENTRY, button,
                dialogs.BUTTON_CANCEL)
        def callback(dialog):
            if not self.idExists():
                return
            if dialog.choice == button:
                self.deleteFiles()
            if dialog.choice in (button, dialogs.BUTTON_REMOVE_ENTRY):
                self.executeExpire()

        d.run(callback)

    def deleteFiles(self):
        try:
            if os.path.isfile(self.filename):
                os.remove(self.filename)
            elif os.path.isdir(self.filename):
                shutil.rmtree(self.filename)
        except:
            print "WARNING: error deleting files"
            traceback.print_exc()

    def getDownloadedTime(self):
        self.confirmDBThread()
        try:
            return datetime.fromtimestamp(os.getctime(self.filename))
        except:
            return datetime.min

    def getFilename(self):
        try:
            return self.filename
        except:
            return ""

    def migrate(self, newDir):
        self.confirmDBThread()
        if self.shortFilename is None:
            print """\
WARNING: can't migrate download because we don't have a shortFilename!
filename was %s""" % self.filename
            return
        newFilename = os.path.join(newDir, self.shortFilename)
        if self.filename == newFilename:
            return
        if os.path.exists(self.filename):
            newFilename = nextFreeFilename(newFilename)
            try:
                shutil.move(self.filename, newFilename)
            except Exception, e:
                print "WARNING: Error moving %s to %s (%s)" % (self.filename,
                        newFilename, e)
            else:
                self.filename = newFilename
                self.signalChange()
        elif os.path.exists(newFilename):
            self.filename = newFilename
            self.signalChange()
        self.migrateChildren(newDir)

    def setupLinks(self):
        if self.shortFilename is None:
            if self.parent_id is None:
                self.shortFilename = os.path.basename(self.filename)
            else:
                parent_file = self.getParent().getFilename()
                if self.filename.startswith(parent_file):
                    self.shortFilename = self.filename[len(parent_file):]
                else:
                    print "WARNING: %s is not a subdirectory of %s" % (self.filename, parent_file)
        Item.setupLinks(self)

def expireItems(items):
    if len(items) == 1:
        return items[0].expire()

    hasContainers = False
    hasExternalItems = False
    for item in items:
        if item.isContainerItem:
            hasContainers = True
        elif item.isExternal():
            hasExternalItems = True
        if hasContainers and hasExternalItems:
            break

    title = _("Removing %s items") % len(items)
    if hasExternalItems:
        description = _("""One or more of these videos was not downloaded \
from a channel.  Would you like to delete these items or just remove their \
entries from My Collection?""")
    else:
        description = "Are you sure you want to delete all %s videos?" % \
                len(items)

    if hasContainers:
        description += "\n\n" + _("""\
One or more of these items is a folder.  When you remove or delete a folder, \
any items inside that folder will also be removed or deleted.""")

    if hasExternalItems:
        d = dialogs.ThreeChoiceDialog(title, description,
                dialogs.BUTTON_REMOVE_ENTRY, dialogs.BUTTON_DELETE_FILES,
                dialogs.BUTTON_CANCEL)
    else:
        d = dialogs.ChoiceDialog(title, description, dialogs.BUTTON_OK,
                dialogs.BUTTON_CANCEL)

    def callback(dialog):
        if dialog.choice == dialogs.BUTTON_DELETE_FILES:
            for item in items:
                if item.idExists():
                    item.deleteFiles()
        if dialog.choice in (dialogs.BUTTON_OK, dialogs.BUTTON_REMOVE_ENTRY,
                dialogs.BUTTON_DELETE_FILES):
            for item in items:
                if item.idExists():
                    item.executeExpire()
    d.run(callback)

def isVideoEnclosure(enclosure):
    """
    Pass an enclosure dictionary to this method and it will return a boolean
    saying if the enclosure is a video or not.
    """
    return (_hasVideoType(enclosure) or
            _hasVideoExtension(enclosure, 'url') or
            _hasVideoExtension(enclosure, 'href'))

def getFirstVideoEnclosure(entry):
    """Find the first video enclosure in a feedparser entry.  Returns the
    enclosure, or None if no video enclosure is found.
    """

    try:
        enclosures = entry.enclosures
    except (KeyError, AttributeError):
        return None
    for enclosure in enclosures:
        if isVideoEnclosure(enclosure):
            return enclosure
    return None

def _hasVideoType(enclosure):
    return ('type' in enclosure and
            (enclosure['type'].startswith('video/') or
             enclosure['type'].startswith('audio/') or
             enclosure['type'] == "application/ogg" or
             enclosure['type'] == "application/x-annodex" or
             enclosure['type'] == "application/x-bittorrent" or
             enclosure['type'] == "application/x-shockwave-flash"))

def _hasVideoExtension(enclosure, key):
    return (key in enclosure and isAllowedFilename(enclosure[key]))

def isAllowedFilename(filename):
    return (isVideoFilename(filename) or
            isAudioFilename(filename) or
            isTorrentFilename(filename))

def isVideoFilename(filename):
    return ((len(filename) > 4 and
             filename[-4:].lower() in ['.mov', '.wmv', '.mp4', '.m4v',
                                       '.ogg', '.anx', '.mpg', '.avi', 
                                       '.flv']) or
            (len(filename) > 5 and
             filename[-5:].lower() == '.mpeg'))

def isAudioFilename(filename):
    return len(filename) > 4 and filename[-4:].lower() in ['.mp3', '.m4a']

def isTorrentFilename(filename):
    return filename.endswith('.torrent')
