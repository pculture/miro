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

from datetime import datetime, timedelta
from miro.gtcache import gettext as _
from math import ceil
from miro.xhtmltools import unescape,xhtmlify
from xml.sax.saxutils import unescape
from miro.util import checkU, returnsUnicode, checkF, returnsFilename, quoteUnicodeURL, stringify, getFirstVideoEnclosure
from miro.plat.utils import FilenameType, filenameToUnicode, unicodeToFilename
import locale
import os
import os.path
import urllib
import urlparse
import shutil
import traceback

from miro.download_utils import cleanFilename, nextFreeFilename
from miro.feedparser import FeedParserDict

from miro.database import DDBObject, defaultDatabase, ObjectNotFoundError
from miro.database import DatabaseConstraintError
from miro.databasehelper import makeSimpleGetSet
from miro.iconcache import IconCache
import types
from miro import app
from miro import downloader
from miro import config
from miro import dialogs
from miro import eventloop
from miro import filters
from miro import prefs
from miro.plat import resources
from miro import views
import random
from miro import indexes
from miro import util
from miro import adscraper
from miro import autodler
from miro import moviedata
import logging
from miro import filetypes
from miro import searchengines
from miro import fileutil
from miro import signals
from miro import license

_charset = locale.getpreferredencoding()

class Item(DDBObject):
    """An item corresponds to a single entry in a feed. It has a single url
    associated with it.
    """

    def __init__(self, entry, linkNumber=0, feed_id=None, parent_id=None):
        self.feed_id = feed_id
        self.parent_id = parent_id
        self.isContainerItem = None
        self.isVideo = False
        self.seen = False
        self.autoDownloaded = False
        self.pendingManualDL = False
        self.downloadedTime = None
        self.watchedTime = None
        self.pendingReason = u""
        self.title = u""
        self.entry = entry
        self.expired = False
        self.keep = False
        self.videoFilename = FilenameType("")
        self.eligibleForAutoDownload = True
        self.duration = None
        self.screenshot = None
        self.resized_screenshots = {}
        self.resumeTime = 0
        self.channelTitle = None

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

    def onRestore(self):
        """Called by pickle during serialization.
        """
        DDBObject.onRestore(self)
        if (self.iconCache == None):
            self.iconCache = IconCache (self)
        else:
            self.iconCache.dbItem = self
            self.iconCache.requestUpdate()
        # For unknown reason(s), some users still have databases with item 
        # objects missing the isContainerItem attribute even after
        # a db upgrade (#8819).
        if not hasattr(self, 'isContainerItem'):
            self.isContainerItem = None
        self._initRestore()

    def _initRestore(self):
        """Common code shared between onRestore and __init__."""
        self.selected = False
        self.active = False
        self.childrenSeen = None
        self.downloader = None
        self.expiring = None
        self.showMoreInfo = False
        self.updating_movie_info = False

    def _lookForFinishedDownloader(self):
        dler = downloader.lookupDownloader(self.getURL())
        if dler and dler.isFinished():
            self.downloader = dler
            dler.addItem(self)

    getSelected, setSelected = makeSimpleGetSet(u'selected',
            changeNeedsSave=False)
    getActive, setActive = makeSimpleGetSet(u'active', changeNeedsSave=False)

    @returnsUnicode
    def getSelectedState(self, view):
        currentView = app.selection.itemListSelection.currentView
        if not self.selected or view != currentView:
            return u'normal'
        elif not self.active:
            return u'selected-inactive'
        else:
            return u'selected'

    def toggleShowMoreInfo(self):
        self.showMoreInfo = not self.showMoreInfo
        self.signalChange(needsSave=False, needsUpdateXML=True)

    @returnsUnicode
    def getMoreInfoState(self):
        if self.showMoreInfo:
            return u'more-info'
        return u''

    def findChildVideos(self):
        """If this item points to a directory, return the set all video files
        under that directory.
        """

        videos = set()
        filename_root = self.getFilename()
        if fileutil.isdir(filename_root):
            files = fileutil.miro_allfiles(filename_root)
            for filename in files:
                if filetypes.isVideoFilename(filename) or filetypes.isAudioFilename(filename):
                    videos.add(filename)
        return videos

    def findNewChildren(self):
        """If this feed is a container item, walk through its directory and
        find any new children.  Returns True if it found childern and ran
        signalChange().
        """

        filename_root = self.getFilename()
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
            assert video.startswith(filename_root)
            offsetPath = video[len(filename_root):]
            while offsetPath[0] == '/' or offsetPath[0] == '\\':
                offsetPath = offsetPath[1:]
            FileItem (video, parent_id=self.id, offsetPath=offsetPath)
        if videos:
            self.signalChange()
            return True
        return False

    def splitItem(self):
        """returns True if it ran signalChange()"""
        if self.isContainerItem is not None:
            return self.findNewChildren()
        if not isinstance (self, FileItem) and (self.downloader is None or not self.downloader.isFinished()):
            return False
        filename_root = self.getFilename()
        if fileutil.isdir(filename_root):
            videos = self.findChildVideos()
            if len(videos) > 1:
                self.isContainerItem = True
                for video in videos:
                    assert video.startswith(filename_root)
                    offsetPath = video[len(filename_root):]
                    while offsetPath[0] in ('/', '\\'):
                        offsetPath = offsetPath[1:]
                    FileItem (video, parent_id=self.id, offsetPath=offsetPath)
            elif len(videos) == 1:
                self.isContainerItem = False
                for video in videos:
                    assert video.startswith(filename_root)
                    self.videoFilename = video[len(filename_root):]
                    while self.videoFilename[0] in ('/', '\\'):
                        self.videoFilename = self.videoFilename[1:]
                    self.isVideo = True
            else:
                if not self.getFeedURL().startswith ("dtv:directoryfeed"):
                    target_dir = config.get(prefs.NON_VIDEO_DIRECTORY)
                    if not filename_root.startswith(target_dir):
                        if isinstance(self, FileItem):
                            self.migrate (target_dir)
                        else:
                            self.downloader.migrate (target_dir)
                self.isContainerItem = False
        else:
            self.isContainerItem = False
            self.videoFilename = FilenameType("")
            self.isVideo = True
        self.signalChange()
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
        from miro import feed
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

    def signalChange(self, needsSave=True, needsUpdateXML=True):
        self.expiring = None
        try:
            del self._state
        except:
            pass
        try:
            del self._size
        except:
            pass
        if needsUpdateXML:
            try:
                del self._itemXML
            except:
                pass
        DDBObject.signalChange(self, needsSave=needsSave)

    def getItemXML(self, viewName):
        """Returns the rendered download-item template, hopefully from the cache

        viewName - name of the view we're in.
        view - actual view object that we're in.

        Almost all of the search string is cached, but there are several pieces
        of data that must be generated on the fly:
         * The name of the view, used for things like action:playNamedView
         * The dragdesttype attribute -- it's based on the current selection
         * The selected css class -- it's depends on whether the view that this
            item is in is the view that's selected.  This matters when an item
            is shown multiple times on a page, in different views.
         * The channel name -- it's not displayed in the channel template.
        """
        try:
            xml = self._itemXML
        except AttributeError:
            self._calcItemXML()
            xml = self._itemXML
        return xml.replace(self._XMLViewName, viewName)

    def _calcItemXML(self):
        """Regenerates an expired item XML from the download-item template.

        _XMLViewName - random string we use for the name of the view
        _itemXML - rendered XML
        """
        from miro.frontends.html import template
        self._XMLViewName = "view%dview" % random.randint(9999999,99999999)
        self._itemXML = template.fillStaticTemplate(
            'download-item-inner', onlyBody=True, this=self,
            viewName=self._XMLViewName,templateState='unknown')
        checkU(self._itemXML)

    def getViewed(self):
        """Returns True iff this item has never been viewed in the interface.

        Note the difference between "viewed" and seen.
        """
        try:
            # optimizing by trying the cached feed
            return self._feed.lastViewed >= self.creationTime
        except:
            return self.creationTime <= self.getFeed().lastViewed 

    def getFirstVideoEnclosure(self):
        """Returns the first video enclosure in the item.
        """
        try:
            return self._firstVidEnc
        except:
            self._calcFirstEnc()
            return self._firstVidEnc

    def _calcFirstEnc(self):
        self._firstVidEnc = getFirstVideoEnclosure(self.entry)
        
    @returnsUnicode
    def getFirstVideoEnclosureType(self):
        """Returns mime-type of the first video enclosure in the item.
        """
        enclosure = self.getFirstVideoEnclosure()
        if enclosure and enclosure.has_key('type'):
            return enclosure['type']
        return None

    @returnsUnicode
    def getURL(self):
        """Returns the URL associated with the first enclosure in the item.
        """
        self.confirmDBThread()
        videoEnclosure = self.getFirstVideoEnclosure()
        if videoEnclosure is not None and 'url' in videoEnclosure:
            return quoteUnicodeURL(videoEnclosure['url'].replace('+', '%20'))
        else:
            return u''

    @returnsUnicode
    def getQuotedURL(self):
        """Returns the title of the item quoted for inclusion in URLs.
        """
        return urllib.quote_plus(urllib.unquote(self.getURL().encode('ascii'))).decode('ascii')

    def hasSharableURL(self):
        """Does this item have a URL that the user can share with others?

        This returns True when the item has a non-file URL.
        """
        url = self.getURL()
        return url != u'' and not url.startswith(u"file:")

    def getFeed(self):
        """Returns the feed this item came from.
        """
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

    @returnsUnicode
    def getFeedURL(self):
        return self.getFeed().getURL()

    def feedExists(self):
        return self.feed_id and self.dd.idExists(self.feed_id)

    def getChildren(self):
        if self.isContainerItem:
            return views.items.filterWithIndex(indexes.itemsByParent, self.id)
        else:
            raise ValueError("%s is not a container item" % self)

    def setFeed(self, feed_id):
        """Moves this item to another feed.
        """
        self.feed_id = feed_id
        del self._feed
        if self.isContainerItem:
            for item in self.getChildren():
                del item._feed
                item.signalChange()
        self.signalChange()

    def expire(self):
        self.confirmDBThread()
        self.removeFromPlaylists()
        UandA = self.getUandA()
        if not self.isExternal():
            self.deleteFiles()
        self.expired = True
        if self.isContainerItem:
            for item in self.getChildren():
                item.remove()
        self.isContainerItem = None
        self.isVideo = False
        self.videoFilename = FilenameType("")
        self.seen = self.keep = self.pendingManualDL = False
        self.watchedTime = None
        self.duration = None
        if self.screenshot:
            try:
                fileutil.remove(self.screenshot)
            except:
                pass
        # This should be done even if screenshot = ""
        self.screenshot = None
        if self.isExternal():
            if self.isDownloaded():
                new_item = FileItem (self.getVideoFilename(), feed_id=self.feed_id, parent_id=self.parent_id, deleted=True)
                if self.downloader is not None:
                    self.downloader.setDeleteFiles(False)
            self.remove()
        else:
            self.signalChange()

    def stopUpload(self):
        if self.downloader:
            self.downloader.stopUpload()

    def pauseUpload(self):
        if self.downloader:
            self.downloader.pauseUpload()

    def startUpload(self):
        if self.downloader:
            self.downloader.startUpload()

    @returnsUnicode
    def getString(self, when):
        """Get the expiration time a string to display to the user."""
        offset = when - datetime.now()
        if offset.days == 1:
            result = _("1 day")
        elif offset.days > 0:
            result = _("%d days") % offset.days
        elif offset.seconds > 3600:
            result = _("%d hours") % (ceil(offset.seconds/3600.0))
        else:
            result = _("%d minutes") % (ceil(offset.seconds/60.0))
        return result

    @returnsUnicode
    def getExpirationString(self):
        """Get the expiration time a string to display to the user."""
        expireTime = self.getExpirationTime()
        if expireTime is None:
            return u""
        else:
            return _('Expires in %s') % self.getString (expireTime)

    @returnsUnicode
    def getPausedString(self):
        """Get the expiration time a string to display to the user."""
        retryTime = None
        if self.downloader:
            if self.downloader.getState() == u'offline':
                retryTime = self.downloader.status['retryTime']
                if retryTime is None:
                    return ""
                else:
                    return _('Will retry in %s') % self.getString (retryTime)
            else:
                return _('Paused')
        else:
            return u""

    @returnsUnicode
    def getDragType(self):
        if self.isDownloaded():
            return u'downloadeditem'
        else:
            return u'item'

    @returnsUnicode
    def getEmblemCSSClass(self):
        if self.getState() == u'newly-downloaded':
            return u'newly-downloaded'
        elif self.getState() == u'new':
            return u'new'
        elif self.getState() == u'downloading':
            return u'downloading'
        else:
            return u''

    @returnsUnicode
    def getEmblemCSSString(self):
        if self.getState() == u'newly-downloaded':
            return u'Unwatched'
        elif self.getState() == u'new':
            return u'New'
        else:
            return u''

    def getUandA(self):
        """Get whether this item is new, or newly-downloaded, or neither."""
        state = self.getState()
        if state == u'new':
            return (0, 1)
        elif state == u'newly-downloaded':
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
        if ufeed.expire == u'never' or (ufeed.expire == u'system'
                and config.get(prefs.EXPIRE_AFTER_X_DAYS) <= 0):
            return None
        else:
            if ufeed.expire == u"feed":
                expireTime = ufeed.expireTime
            elif ufeed.expire == u"system":
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
                if (self.keep or ufeed.expire == u'never' or 
                        (ufeed.expire == u'system' and
                            config.get(prefs.EXPIRE_AFTER_X_DAYS) <= 0)):
                    self.expiring = False
                else:
                    self.expiring = True
        return self.expiring

    def getSeen(self):
        """Returns true iff video has been seen.

        Note the difference between "viewed" and "seen".
        """
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

    def markItemSeen(self, markOtherItems=True):
        """Marks the item as seen.
        """
        self.confirmDBThread()
        if self.seen == False:
            self.seen = True
            if self.watchedTime is None:
                self.watchedTime = datetime.now()
            self.clearParentsChildrenSeen()
            self.signalChange()
            if markOtherItems and self.downloader:
                for item in self.downloader.itemList:
                    if item != self:
                        item.markItemSeen(False)

    def clearParentsChildrenSeen(self):
        if self.parent_id:
            parent = self.getParent()
            parent.childrenSeen = None
            parent.signalChange()

    def markItemUnseen(self, markOtherItems=True):
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
            if markOtherItems and self.downloader:
                for item in self.downloader.itemList:
                    if item != self:
                        item.markItemUnseen(False)

    @returnsUnicode
    def getRSSID(self):
        self.confirmDBThread()
        return self.entry["id"]

    def removeRSSID(self):
        self.confirmDBThread()
        if 'id' in self.entry:
            del self.entry['id']
            self.signalChange()

    def setAutoDownloaded(self, autodl=True):
        self.confirmDBThread()
        if autodl != self.autoDownloaded:
            self.autoDownloaded = autodl
            self.signalChange()

    @eventloop.asIdle
    def setResumeTime(self, position):
        if not self.idExists():
            return
        position = int(position)
        if self.resumeTime != position:
            self.resumeTime = position
            self.signalChange()

    @returnsUnicode
    def getPendingReason(self):
        self.confirmDBThread()
        return self.pendingReason

    def getAutoDownloaded(self):
        """Returns true iff item was auto downloaded.
        """
        self.confirmDBThread()
        return self.autoDownloaded

    def getLinkNumber(self):
        """Returns the linkNumber.
        """
        self.confirmDBThread()
        return self.linkNumber

    def download(self, autodl=False):
        """Starts downloading the item.
        """
        autodler.resumeDownloader()
        self.confirmDBThread()
        manualDownloadCount = views.manualDownloads.len()
        self.expired = self.keep = self.seen = False

        if ((not autodl) and 
                manualDownloadCount >= config.get(prefs.MAX_MANUAL_DOWNLOADS)):
            self.pendingManualDL = True
            # FIXME - should this be translated --NN
            self.pendingReason = u"queued for download"
            self.signalChange()
            return
        else:
            self.setAutoDownloaded(autodl)
            self.pendingManualDL = False

        if self.downloader is None:
            self.downloader = downloader.getDownloader(self)
        if self.downloader is not None:
            self.downloader.setChannelName (unicodeToFilename(self.getChannelTitle(True)))
            if self.downloader.isFinished():
                self.onDownloadFinished()
            else:
                self.downloader.start()
        self.signalChange()

    def pause(self):
        if self.downloader:
            self.downloader.pause()

    def resume(self):
        self.download(self.getAutoDownloaded())

    def isPendingManualDownload(self):
        self.confirmDBThread()
        return self.pendingManualDL

    def isEligibleForAutoDownload(self):
        self.confirmDBThread()
        if self.getState() not in (u'new', u'not-downloaded'):
            return False
        if self.downloader and self.downloader.getState() in (u'failed',
                u'stopped', u'paused'):
            return False
        ufeed = self.getFeed()
        if ufeed.getEverything:
            return True
        return self.eligibleForAutoDownload

    def isPendingAutoDownload(self):
        return (self.getFeed().isAutoDownloadable() and
                self.isEligibleForAutoDownload())

    def isFailedDownload(self):
        return self.downloader and self.downloader.getState() == u'failed'

    @returnsUnicode
    def getThumbnailURL(self):
        """Returns a link to the thumbnail of the video.
        """
        self.confirmDBThread()
        # Try to get the thumbnail specific to the video enclosure
        videoEnclosure = self.getFirstVideoEnclosure()
        if videoEnclosure is not None:
            try:
                return videoEnclosure["thumbnail"]["url"].decode("ascii","replace")
            except:
                pass 
        # Try to get any enclosure thumbnail
        for enclosure in self.entry.enclosures:
            try:
                return enclosure["thumbnail"]["url"].decode('ascii','replace')
            except KeyError:
                pass
        # Try to get the thumbnail for our entry
        try:
            return self.entry["thumbnail"]["url"].decode('ascii','replace')
        except:
            return None

    @returnsFilename
    def getThumbnail(self):
        """NOTE: When changing this function, change feed.iconChanged to signal
        the right set of items.
        """
        self.confirmDBThread()
        if self.iconCache is not None and self.iconCache.isValid():
            path = self.iconCache.getFilename()
            return resources.path(fileutil.expand_filename(path))
        elif self.screenshot:
            path = self.screenshot
            return resources.path(fileutil.expand_filename(path))
        elif self.isContainerItem:
            return resources.path("wimages/container-icon.png")
        else:
            feed = self.getFeed()
            if feed.thumbnailValid():
                return feed.getThumbnailPath()
            else:
                return resources.path("wimages/thumb-default_large.png")

    @returnsUnicode
    def getTitle(self):
        """Returns the title of the item.
        """
        if not self.title:
            if hasattr(self.entry, "title"):
                self.title = self.entry.title
            else:
                enc = self.getFirstVideoEnclosure()
                self.title = enc.get("url", _("no title")).decode("ascii", "replace")
        return self.title

    def setTitle(self, s):
        self.confirmDBThread()
        self.title = s
        self.signalChange()

    def revertTitle(self):
        """Reverts the item title back to the data we got from RSS or the url.
        """
        self.confirmDBThread()
        if hasattr(self.entry, "title"):
            self.title = self.entry.title
        else:
            enc = self.getFirstVideoEnclosure()
            self.title = enc.get("url", _("no title")).decode("ascii", "replace")
        self.signalChange()

    @returnsUnicode
    def getQuotedTitle(self):
        """Returns the title of the item quoted for inclusion in URLs.
        """
        return urllib.quote_plus(self.getTitle().encode('utf8')).decode('ascii', 'replace')

    def setChannelTitle(self, title):
        checkU(title)
        self.channelTitle = title

    @returnsUnicode
    def getChannelTitle(self, allowSearchFeedTitle=False):
        from miro import feed
        implClass = self.getFeed().actualFeed.__class__
        if implClass in (feed.RSSFeedImpl, feed.ScraperFeedImpl):
            return self.getFeed().getTitle()
        elif implClass == feed.SearchFeedImpl and allowSearchFeedTitle:
            return searchengines.get_last_engine_title()
        elif self.channelTitle:
            return self.channelTitle
        else:
            return u''

    @returnsUnicode
    def getRawDescription(self):
        """Returns the raw description of the video (unicode).
        """
        self.confirmDBThread()

        try:
            enclosure = self.getFirstVideoEnclosure()
            if "text" in enclosure:
                return enclosure["text"]

            if hasattr(self.entry, "description"):
                return self.entry.description

        except Exception:
            logging.exception("getRawDescription threw exception:")

        return u''

    @returnsUnicode
    def getDescription(self):
        """Returns valid XHTML containing a description of the video (str).
        """
        rawDescription = self.getRawDescription()

        # FIXME - clean this up in regards to exception handling.
        try:
            purifiedDescription = adscraper.purify(rawDescription)
            return xhtmlify (u'<span>%s</span>' % (unescape(purifiedDescription),), filterFontTags=True)

        except Exception:
            logging.exception("getDescription threw error.")
            try:
                return xhtmlify (u'<span>%s</span>' % (unescape(rawDescription),))
            except Exception:
                logging.exception("getDescription threw error.")
                return u'<span />'

    def getAd(self):
        """Returns valid XHTML containing the ad (str).
        """
        rawDescription = self.getRawDescription()

        # FIXME - clean this up in regards to exception handling.
        try:
            rawAd = adscraper.scrape(rawDescription)
            return xhtmlify (u'<span>%s</span>' % (unescape(rawAd),))

        except Exception:
            logging.exception("getAd threw error.")
            return u'<span />'

    def looksLikeTorrent(self):
        """Returns true if we think this item is a torrent.  (For items that
        haven't been downloaded this uses the file extension which isn't
        totally reliable).
        """

        if self.downloader is not None:
            return self.downloader.getType() == u'bittorrent'
        else:
            return filetypes.isTorrentFilename(self.getURL())

    @returnsUnicode
    def getDetails(self):
        """Returns formatted XHTML with release date, duration, format, and size.
        """
        details = []
        reldate = self.getReleaseDate()
        format = self.getFormat()
        size = self.getSizeForDisplay()
        link = self.getLink()

        if self.isContainerItem:
            children = self.getChildren()
            details.append(u'<span class="details-count">%s items</span>' % len(children))
        if len(reldate) > 0:
            details.append(u'<span class="details-date">%s</span>' % util.escape(reldate))
        if len(size) > 0:
            details.append(u'<span class="details-size">%s</span>' % util.escape(size))
        if len(format) > 0:
            details.append(u'<span class="details-format">%s</span>' % util.escape(format))
        if self.looksLikeTorrent():
            details.append(u'<span class="details-torrent">%s</span>' % _("TORRENT"))
        if len(link) > 0 and link != self.getURL():
            details.append(u'<a class="details-link" href="%s">%s</span>' % (util.quoteattr(link), _("WEB PAGE")))
        out = u'<BR>'.join(details)
        return out

    def isTransferring(self):
        return self.downloader and self.downloader.getState() in (u'uploading', u'downloading')

    def getDownloadDetails(self):
        status = self.downloader.status
        details = [
            (_('Total Down:'), formatSizeForDetails(status.get('currentSize', 0))),
        ]
        if status.get("reasonFailed"):
            details.append((_('Error:'), status['reasonFailed']))
        return details

    def getTorrentDetails(self):
        status = self.downloader.status
        retval = []
        seeders = status.get('seeders', -1)
        leechers = status.get('leechers', -1)
        if seeders != -1:
            retval.append((_('Seeders:'), seeders))
        if leechers != -1:
            retval.append((_('Leechers:'), leechers))
        retval.extend ([
            (_('Down Rate:'), formatRateForDetails(status.get('rate', 0))),
            (_('Down Total:'), formatSizeForDetails(
                status.get('currentSize', 0))),
            (_('Up Rate:'), formatRateForDetails(status.get('upRate', 0))),
            (_('Up Total:'), formatSizeForDetails(status.get('uploaded', 0))),
        ])

        return retval

    def getItemDetails(self):
        rv = []
        
        # prefer a comments link if it exists; if not, use the permalink
        comments = self.getCommentsLink()
        if comments:
            rv.append((_('Web page:'), util.makeAnchor(_('comments'), comments)))

        else:
            link = self.getLink()
            if link:
                rv.append((_('Web page:'), util.makeAnchor(_('permalink'), link)))

        url = self.getURL()
        if url and not url.startswith("file:"):
            rv.append((_('File link:'), util.makeAnchor(_('direct link to file'),
                                              url)))
        rv.append((_('File type:'), self.getFormat()))

        if self.getLicence():
            # check the license to see if it's a url by seeing if it has a 
            # protocol
            if urlparse.urlparse(self.getLicence())[0]:
                ln = license.license_name(self.getLicence())
                rv.append((_('License:'), util.makeAnchor(ln,
                                                          self.getLicence())))
            else:
                rv.append((_('License:'), _('see permalink')))
        else:
            rv.append((_('License:'), _('see permalink')))
 
        if self.isDownloaded():
            basename = os.path.basename(self.getFilename())
            basename = util.clampText(basename, 20)
            linkEventURL = u'revealItem?item=%d' % self.getID()
            if self.isContainerItem:
                label = _("SHOW LOCAL FOLDER")
            else:
                label = _("SHOW LOCAL FILE")
            link = util.makeEventURL(label, linkEventURL)
            rv.append((_('Filename:'), u"%s<BR />%s" % (filenameToUnicode(basename), link)))
        return rv

    def getTorrentDetailsFinished(self):
        status = self.downloader.status
        return [
            (_('Down Total'), formatSizeForDetails(
                status.get('currentSize', 0))),
            (_('Up Total'), formatSizeForDetails(status.get('uploaded', 0))),
        ]

    def makeMoreInfoTable(self, title, moreInfoData):
        lines = []
        #lines.append(u'<h3>%s</h3>' % title)
        #lines.append(u'<table cellpadding="0" cellspacing="0">')
        for label, text in moreInfoData:
            lines.append(u'<tr><td class="col1">%s</td>'
                    u'<td><b>%s</b></td></tr>' % (label, text))
        #lines.append(u'</table>')
        return u'\n'.join(lines)

    @returnsUnicode
    def getMoreInfo(self):
        """Returns formatted XHTML with download info.
        """
        details = [
            self.makeMoreInfoTable(_('Item Details'), self.getItemDetails()),
        ]
        # helper function to keep things from getting too verbose below
        def addTable(label, data):
            details.append(self.makeMoreInfoTable(label, data))
        if self.looksLikeTorrent():
            if self.isTransferring():
                addTable(_('Torrent Details'), self.getTorrentDetails())
            elif self.downloader and self.downloader.isFinished():
                addTable(_('Torrent Details <i>stopped</i>'),
                        self.getTorrentDetailsFinished())
        elif ((self.getState() == u'downloading' and not self.pendingManualDL)
                or self.isFailedDownload()):
            addTable(_('Download Details'), self.getDownloadDetails())
        return u'\n'.join(details)

    def deleteFiles(self):
        """Stops downloading the item.
        """
        self.confirmDBThread()
        if self.downloader is not None:
            self.downloader.removeItem(self)
            self.downloader = None
            self.signalChange()

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

    @returnsUnicode
    def _calcState(self):
        """Recalculate the state of an item after a change
        """
        self.confirmDBThread()
        # FIXME, 'failed', and 'paused' should get download icons.  The user
        # should be able to restart or cancel them (put them into the stopped
        # state).
        if (self.downloader is None  or 
                self.downloader.getState() in (u'failed', u'stopped')):
            if self.pendingManualDL:
                self._state = u'downloading'
            elif self.expired:
                self._state = u'expired'
            elif (self.getViewed() or
                    (self.downloader and
                        self.downloader.getState() in (u'failed', u'stopped'))):
                self._state = u'not-downloaded'
            else:
                self._state = u'new'
        elif self.downloader.getState() in (u'offline', u'paused'):
            if self.pendingManualDL:
                self._state = u'downloading'
            else:
                self._state = u'paused'
        elif not self.downloader.isFinished():
            self._state = u'downloading'
        elif not self.getSeen():
            self._state = u'newly-downloaded'
        elif self.getExpiring():
            self._state = u'expiring'
        else:
            self._state = u'saved'

    @returnsUnicode    
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
                return u'new'
            if self.expired:
                return u'expired'
            else:
                return u'not-downloaded'
        elif not self.getSeen():
            if not self.getViewed():
                return u'new'
            return u'newly-downloaded'
        elif self.getExpiring():
            return u'expiring'
        else:
            return u'saved'

    def isDownloadable(self):
        return self.getState() in (u'new', u'not-downloaded', u'expired')

    def isDownloaded(self):
        return self.getState() in (u"newly-downloaded", u"expiring", u"saved")

    def showSaveButton(self):
        return self.getState() in (u'newly-downloaded', u'expiring') and not self.keep

    def showSaved(self):
        return self.getState() in (u'saved',) or (self.getState() in (u'newly-downloaded', u'expiring') and self.keep)

    def showTrashButton(self):
        return self.isDownloaded() or (self.getFeedURL() == u'dtv:manualFeed'
                and self.getState() not in (u'downloading', u'paused'))

    @returnsUnicode
    def getFailureReason(self):
        self.confirmDBThread()
        if self.downloader is not None:
            return self.downloader.getShortReasonFailed()
        else:
            return u""
    
    def getSizeForDisplay(self):
        """Returns the size of the item to be displayed.
        """
        return util.formatSizeForUser(self.getSize())

    def getSize(self):
        if not hasattr(self, "_size"):
            self._size = self._getSize()
        return self._size

    def _getSize(self):
        """Returns the size of the item. We use the following methods to get the
        size:

        1. Physical size of a downloaded file
        2. HTTP content-length
        3. RSS enclosure tag value
        """
        if self.isDownloaded():
            try:
                fname = self.getFilename()
                return util.getsize(fname)
            except OSError:
                return 0
        elif self.downloader is not None:
            return self.downloader.getTotalSize()
        else:
            try:
                return int(self.getFirstVideoEnclosure()['length'])
            except:
                return 0

    @returnsUnicode
    def getCurrentSize(self):
        """Returns status of the download in plain text.
        """
        if self.downloader is not None:
            size = self.downloader.getCurrentSize()
        else:
            size = 0
        return util.formatSizeForUser(size)

    def downloadProgress(self):
        """Returns the download progress in absolute percentage [0.0 - 100.0].
        """
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

    def downloadProgressWidth(self):
        """Returns the width of the progress bar corresponding to the current
        download progress. This doesn't really belong here and even forces
        to use a hardcoded constant, but the templating system doesn't
        really leave any other choice.
        """
        fullWidth = 131  # width of resource:channelview-progressbar-bg.png
        progress = self.downloadProgress() / 100.0
        if progress == 0:
            return 0
        return int(progress * fullWidth)

    @returnsUnicode
    def threeDigitPercentDone(self):
        """Returns string containing three digit percent finished
        "000" through "100".
        """
        return u'%03d' % int(self.downloadProgress())

    def twoDigitPercentDone(self):
        if int(self.downloadProgress()) < 10:
          out = u'%d' % int(self.downloadProgress())
        else:
          out = u'%02d' % int(self.downloadProgress())
        return out + u'%'
          
    def downloadInProgress(self):
        return self.downloader is not None and self.downloader.getETA() != 0

    @returnsUnicode
    def downloadETA(self):
        """Returns string with estimate time until download completes.
        """
        if self.downloader is not None:
            totalSecs = self.downloader.getETA()
            if totalSecs <= 0:
                return _('downloading...')
        else:
            totalSecs = 0
        mins, secs = divmod(totalSecs, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            time = u"%d:%02d:%02d" % (hours, mins, secs)
            return _("%s left") % time
        else:
            time = u"%d:%02d" % (mins, secs)
            return _("%s left") % time

    @returnsUnicode
    def getStartupActivity(self):
        if self.pendingManualDL:
            return self.pendingReason
        elif self.downloader:
            return self.downloader.getStartupActivity()
        else:
            return _("starting up...")

    @returnsUnicode
    def downloadRate(self):
        """Returns the download rate.
        """
        rate = 0
        unit = u"KB/s"
        if self.downloader is not None:
            rate = self.downloader.getRate()
        else:
            rate = 0
        rate /= 1024
        if rate > 1024:
            rate /= 1024
            unit = u"MB/s"
        if rate > 1024:
            rate /= 1024
            unit = u"GB/s"
            
        return u"%d%s" % (rate, unit)

    @returnsUnicode
    def getPubDate(self):
        """Returns the published date of the item.
        """
        return getReleaseDate()
    
    def getPubDateParsed(self):
        """Returns the published date of the item as a datetime object.
        """
        return self.getReleaseDateObj()

    @returnsUnicode
    def getReleaseDate(self):
        """Returns the date this video was released or when it was published.
        """
        try:
            return self.getReleaseDateObj().strftime("%b %d %Y").decode(_charset)
        except:
            return u""

    def getReleaseDateObj(self):
        """Returns the date this video was released or when it was published.
        """
        return self.releaseDateObj

    def getDurationValue(self):
        """Returns the length of the video in seconds.
        """
        secs = 0
        if self.duration not in (-1, None):
            secs = self.duration / 1000
        return secs

    @returnsUnicode
    def getDuration(self, emptyIfZero=True):
        """Returns string with the play length of the video.
        """
        secs = self.getDurationValue()
        if secs == 0:
            if emptyIfZero:
                return u""
            else:
                return "n/a"
        return u"%02d:%02d" % (secs/60, secs % 60)

    KNOWN_MIME_TYPES = (u'audio', u'video')
    KNOWN_MIME_SUBTYPES = (u'mov', u'wmv', u'mp4', u'mp3', u'mpg', u'mpeg', u'avi', u'x-flv', u'x-msvideo', u'm4v', u'mkv', u'm2v', u'ogg')
    MIME_SUBSITUTIONS = {
        u'QUICKTIME': u'MOV',
    }
    @returnsUnicode
    def getFormat(self, emptyForUnknown=True):
        """Returns string with the format of the video.
        """
        if self.looksLikeTorrent():
            return u'.torrent'
        try:
            enclosure = self.getFirstVideoEnclosure()
            try:
                extension = enclosure['url'].split('.')[-1].lower().decode('ascii','replace')
            except:
                extension == u''
            # Hack for mp3s, "mpeg audio" isn't clear enough
            if extension.lower() == u'mp3':
                return u'.mp3'
            if enclosure.has_key('type') and len(enclosure['type']) > 0:
                mtype, subtype = enclosure['type'].decode('ascii','replace').split('/')
                mtype = mtype.lower()
                if mtype in self.KNOWN_MIME_TYPES:
                    format = subtype.split(';')[0].upper()
                    if mtype == u'audio':
                        format += u' AUDIO'
                    if format.startswith(u'X-'):
                        format = format[2:]
                    return u'.%s' % self.MIME_SUBSITUTIONS.get(format, format).lower()
            if extension in self.KNOWN_MIME_SUBTYPES:
                return u'.%s' % extension
        except:
            pass
        if emptyForUnknown:
            return u""
        else:
            return u"unknown"

    @returnsUnicode
    def getTags(self):
        """Return keyword tags associated with the video separated by commas.
        """
        self.confirmDBThread()
        try:
            return self.entry.categories.join(u", ")
        except:
            return u""

    @returnsUnicode
    def getLicence(self):
        """Return the license associated with the video.
        """
        self.confirmDBThread()
        try:
            return self.entry.license
        except:
            try:
                return self.getFeed().getLicense()
            except:
                pass
        return u""

    @returnsUnicode
    def getCommentsLink(self):
        """Returns the comments link if it exists in the feed item.
        """
        self.confirmDBThread()
        try:
            return self.entry.comments
        except:
            pass

        return u""

    @returnsUnicode
    def getPeople(self):
        """Return the people associated with the video, separated by commas.
        """
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
        return u', '.join(ret)

    def getLink(self):
        """Returns the URL of the webpage associated with the item.
        """
        self.confirmDBThread()
        try:
            return self.entry.link.decode('ascii','replace')
        except:
            return u""

    def getPaymentLink(self):
        """Returns the URL of the payment page associated with the item.
        """
        self.confirmDBThread()
        try:
            return self.getFirstVideoEnclosure().payment_url.decode('ascii','replace')
        except:
            try:
                return self.entry.payment_url.decode('ascii','replace')
            except:
                return u""

    @returnsUnicode
    def getPaymentHTML(self):
        """returns a snippet of HTML containing a link to the payment page
        HTML has already been sanitized by feedparser.
        """
        self.confirmDBThread()
        try:
            ret = self.getFirstVideoEnclosure().payment_html
        except:
            try:
                ret = self.entry.payment_html
            except:
                ret = u""
        # feedparser returns escaped CDATA so we either have to change its
        # behavior when it parses dtv:paymentlink elements, or simply unescape
        # here...
        return u'<span>' + unescape(ret) + u'</span>'

    def update(self, entry):
        """Updates an item with new data

        entry - dict containing the new data
        """
        UandA = self.getUandA()
        self.confirmDBThread()
        try:
            self.entry = entry
            self.iconCache.requestUpdate()
            self.updateReleaseDate()
            self._calcFirstEnc()
        finally:
            self.signalChange()

    def onDownloadFinished(self):
        """Called when the download for this item finishes."""

        self.confirmDBThread()
        self.downloadedTime = datetime.now()
        if not self.splitItem():
            self.signalChange()
        moviedata.movieDataUpdater.requestUpdate (self)

        for other in views.items:
            if other.downloader is None and other.getURL() == self.getURL():
                other.downloader = self.downloader
                self.downloader.addItem(other)
                other.signalChange(needsSave=False)
        
        signals.system.downloadComplete(self)

    def save(self):
        self.confirmDBThread()
        if self.keep != True:
            self.keep = True
            self.signalChange()

    def getDownloadedTime(self):
        """Gets the time the video was downloaded.

        Only valid if the state of this item is "finished".
        """
        if self.downloadedTime is None:
            return datetime.min
        else:
            return self.downloadedTime

    @returnsFilename
    def getFilename(self):
        """Returns the filename of the first downloaded video or the empty string.

        NOTE: this will always return the absolute path to the file.
        """
        self.confirmDBThread()
        try:
            return self.downloader.getFilename()
        except:
            return FilenameType("")

    @returnsFilename
    def getVideoFilename(self):
        """Returns the filename of the first downloaded video or the empty string.

        NOTE: this will always return the absolute path to the file.
        """
        self.confirmDBThread()
        if self.videoFilename:
            return os.path.join (self.getFilename(), self.videoFilename)
        else:
            return self.getFilename()

    def isNonVideoFile(self):
        # isContainerItem can be False or None.
        return self.isContainerItem != True and not self.isVideo

    def isExternal(self):
        """Returns True iff this item was not downloaded from a Democracy
        channel.
        """
        return self.feed_id is not None and self.getFeedURL() == 'dtv:manualFeed'

    def isPlayable(self):
        """Returns True iff this item should have a play button."""
        if not self.isContainerItem:
            return self.isDownloaded() and self.getVideoFilename()
        else:
            return self.isDownloaded() and len(self.getChildren()) > 0

    def getIsPlayable(self):
        if self.isPlayable():
            return u'playable'
        else:
            return u''
        
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
            self.fixIncorrectTorrentSubdir()
            if self.downloader is not None:
                self.signalChange(needsSave=False)
        self.splitItem()
        # This must come after reconnecting the downloader
        if self.isContainerItem is not None and not fileutil.exists(self.getFilename()):
            self.expire()
            return
        if self.screenshot and not fileutil.exists(self.screenshot):
            self.screenshot = None
            self.signalChange()
        if self.duration is None or self.screenshot is None:
            moviedata.movieDataUpdater.requestUpdate (self)

    def fixIncorrectTorrentSubdir(self):
        """Up to revision 6257, torrent downloads were incorrectly being created in
        an extra subdirectory.  This method "migrates" those torrent downloads to
        the correct layout.

        from: /path/to/movies/foobar.mp4/foobar.mp4
        to:   /path/to/movies/foobar.mp4
        """
        filenamePath = self.getFilename()
        if (fileutil.isdir(filenamePath)):
            enclosedFile = os.path.join(filenamePath, os.path.basename(filenamePath))
            if (fileutil.exists(enclosedFile)):
                logging.info("Migrating incorrect torrent download: %s" % enclosedFile)
                try:
                    temp = filenamePath + ".tmp"
                    fileutil.move(enclosedFile, temp)
                    for turd in os.listdir(fileutil.expand_filename(filenamePath)):
                        os.remove(turd)
                    fileutil.rmdir(filenamePath)
                    fileutil.rename(temp, filenamePath)
                except:
                    pass
                self.videoFilename = FilenameType("")

    def __str__(self):
        return "Item - %s" % self.getTitle()

def reconnectDownloaders():
    reconnected = set()
    for item in views.items:
        item.setupLinks()
        reconnected.add(item.downloader)
    for downloader in views.remoteDownloads:
        if downloader not in reconnected:
            logging.warn("removing orphaned downloader: %s", downloader.url)
            downloader.remove()
    manualFeed = util.getSingletonDDBObject(views.manualFeed)
    manualItems = views.items.filterWithIndex(indexes.itemsByFeed,
            manualFeed.getID())
    for item in manualItems:
        if item.downloader is None and item.__class__ == Item:
            logging.warn("removing cancelled external torrent: %s", item)
            item.remove()

def getEntryForFile(filename):
    return FeedParserDict({'title':filenameToUnicode(os.path.basename(filename)),
            'enclosures':[{'url': resources.url(filename)}]})

def getEntryForURL(url, contentType=None):
    if contentType is None:
        contentType = u'video/x-unknown'
    else:
        contentType = unicode(contentType)
        
    _, _, urlpath, _, _, _ = urlparse.urlparse(url)
    title = os.path.basename(urlpath)

    return FeedParserDict({'title' : title,
            'enclosures':[{'url' : url, 'type' : contentType}]})

class FileItem(Item):
    """An Item that exists as a local file
    """

    def __init__(self, filename, feed_id=None, parent_id=None, offsetPath=None, deleted=False):
        checkF(filename)
        filename = fileutil.abspath(filename)
        self.filename = filename
        self.deleted = deleted
        self.offsetPath = offsetPath
        self.shortFilename = cleanFilename(os.path.basename(self.filename))
        Item.__init__(self, getEntryForFile(filename), feed_id=feed_id, parent_id=parent_id)
        moviedata.movieDataUpdater.requestUpdate (self)

    @returnsUnicode
    def getState(self):
        if self.deleted:
            return u"expired"
        elif self.getSeen():
            return u"saved"
        else:
            return u"newly-downloaded"

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
            return u'expired'
        elif not self.getSeen():
            return u'newly-downloaded'
        else:
            if self.parent_id and self.getParent().getExpiring():
                return u'expiring'
            else:
                return u'saved'

    def getExpiring(self):
        return False

    def showSaveButton(self):
        return False

    def getViewed(self):
        return True

    def isExternal(self):
        return self.parent_id is None

    def expire(self):
        self.confirmDBThread()
        self.removeFromPlaylists()
        if self.isContainerItem:
            for item in self.getChildren():
                item.remove()
        if not fileutil.exists (self.filename):
            # item whose file has been deleted outside of DP
            self.remove()
        elif self.feed_id is None: 
            self.deleted = True
            self.signalChange()
        else:
            # external item that the user deleted in DP
            url = self.getFeedURL()
            if url.startswith ("dtv:manualFeed") or url.startswith ("dtv:singleFeed"):
                self.remove()
            else:
                self.deleted = True
                self.signalChange()

    def deleteFiles(self):
        try:
            if self.getParent():
                dler = self.getParent().downloader
                if dler:
                    dler.stop(False)
            if fileutil.isfile(self.filename):
                fileutil.remove(self.filename)
            elif fileutil.isdir(self.filename):
                fileutil.rmtree(self.filename)
        except:
            logging.warn("WARNING: error deleting files:\n%s",
                    traceback.format_exc())

    def getDownloadedTime(self):
        self.confirmDBThread()
        try:
            return datetime.fromtimestamp(fileutil.getctime(self.filename))
        except:
            return datetime.min

    @returnsFilename
    def getFilename(self):
        try:
            return self.filename
        except:
            return FilenameType("")

    def download(self, autodl=False):
        self.deleted = False
        self.signalChange()

    def updateReleaseDate(self):
        # This should be called whenever we get a new entry
        try:
            self.releaseDateObj = datetime.fromtimestamp(fileutil.getmtime(self.filename))
        except:
            self.releaseDateObj = datetime.min

    def getReleaseDateObj(self):
        if self.parent_id:
            return self.getParent().releaseDateObj
        else:
            return self.releaseDateObj

    def migrate(self, newDir):
        self.confirmDBThread()
        if self.parent_id:
            parent = self.getParent()
            self.filename = os.path.join (parent.getFilename(), self.offsetPath)
            return
        if self.shortFilename is None:
            logging.warn("""\
can't migrate download because we don't have a shortFilename!
filename was %s""", stringify(self.filename))
            return
        newFilename = os.path.join(newDir, self.shortFilename)
        if self.filename == newFilename:
            return
        if fileutil.exists(self.filename):
            newFilename = nextFreeFilename(newFilename)
            def callback():
                self.filename = newFilename
                self.signalChange()
            fileutil.migrate_file(self.filename, newFilename, callback)
        elif fileutil.exists(newFilename):
            self.filename = newFilename
            self.signalChange()
        self.migrateChildren(newDir)

    def setupLinks(self):
        if self.shortFilename is None:
            if self.parent_id is None:
                self.shortFilename = cleanFilename(os.path.basename(self.filename))
            else:
                parent_file = self.getParent().getFilename()
                if self.filename.startswith(parent_file):
                    self.shortFilename = cleanFilename(self.filename[len(parent_file):])
                else:
                    logging.warn("%s is not a subdirectory of %s",
                            self.filename, parent_file)
        self.updateReleaseDate()
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
entries from the Library?""")
    else:
        description = u"Are you sure you want to delete all %s videos?" % \
                len(items)

    if hasContainers:
        description += u"\n\n" + _("""\
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
                if item.idExists() and isinstance (item, FileItem):
                    item.deleteFiles()
        if dialog.choice in (dialogs.BUTTON_OK, dialogs.BUTTON_REMOVE_ENTRY,
                dialogs.BUTTON_DELETE_FILES):
            for item in items:
                if item.idExists():
                    item.expire()
    d.run(callback)

@returnsUnicode
def formatRateForDetails(bytes):
    """Format a download/upload rate for the more-details view."""
    sizeFmt = util.formatSizeForUser(bytes, zeroString=u"-")
    if bytes > 0:
        return sizeFmt + u"/s"
    else:
        return sizeFmt

@returnsUnicode
def formatSizeForDetails(bytes):
    """Format a disk size for the more-details view."""
    return util.formatSizeForUser(bytes, zeroString=u"-")
