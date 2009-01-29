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

from datetime import datetime, timedelta
from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from math import ceil
from miro.xhtmltools import unescape, xhtmlify
from xml.sax.saxutils import unescape
from miro.util import checkU, returnsUnicode, checkF, returnsFilename, quoteUnicodeURL, stringify, getFirstVideoEnclosure, getSingletonDDBObject
from miro.plat.utils import FilenameType, filenameToUnicode, unicodeToFilename
import locale
import os
import os.path
import urlparse
import traceback

from miro.download_utils import cleanFilename, nextFreeFilename
from miro.feedparser import FeedParserDict

from miro.database import DDBObject, ObjectNotFoundError
from miro.database import DatabaseConstraintError
from miro.databasehelper import makeSimpleGetSet
from miro.iconcache import IconCache
from miro import downloader
from miro import config
from miro import eventloop
from miro import prefs
from miro.plat import resources
from miro import views
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
        self._update_release_date()
        self._init_restore()
        self._look_for_downloader()
        DDBObject.__init__(self)
        self.split_item()

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
        self._init_restore()

    def _init_restore(self):
        """Common code shared between onRestore and __init__."""
        self.selected = False
        self.active = False
        self.childrenSeen = None
        self.downloader = None
        self.expiring = None
        self.showMoreInfo = False
        self.updating_movie_info = False

    def _look_for_downloader(self):
        self.downloader = downloader.lookupDownloader(self.getURL())
        if self.downloader is not None:
            self.downloader_id = self.downloader.id
            self.downloader.addItem(self)
        else:
            self.downloader_id = None

    getSelected, setSelected = makeSimpleGetSet(u'selected',
            changeNeedsSave=False)
    getActive, setActive = makeSimpleGetSet(u'active', changeNeedsSave=False)

    def _find_child_videos(self):
        """If this item points to a directory, return the set all video files
        under that directory.
        """
        videos = set()
        filename_root = self.get_filename()
        if fileutil.isdir(filename_root):
            files = fileutil.miro_allfiles(filename_root)
            for filename in files:
                if filetypes.is_video_filename(filename) or filetypes.is_audio_filename(filename):
                    videos.add(filename)
        return videos

    def find_new_children(self):
        """If this feed is a container item, walk through its directory and
        find any new children.  Returns True if it found childern and ran
        signalChange().
        """
        filename_root = self.get_filename()
        if not self.isContainerItem:
            return False
        if self.get_state() == 'downloading':
            # don't try to find videos that we're in the middle of
            # re-downloading
            return False
        videos = self._find_child_videos()
        for child in self.getChildren():
            videos.discard(child.get_filename())
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

    def split_item(self):
        """returns True if it ran signalChange()"""
        if self.isContainerItem is not None:
            return self.find_new_children()
        if not isinstance(self, FileItem) and (self.downloader is None or not self.downloader.isFinished()):
            return False
        filename_root = self.get_filename()
        if fileutil.isdir(filename_root):
            videos = self._find_child_videos()
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

    def _remove_from_playlists(self):
        itemIDIndex = indexes.playlistsByItemID
        view = views.playlists.filterWithIndex(itemIDIndex, self.getID())
        for playlist in view:
            playlist.removeItem(self)
        view = views.playlistFolders.filterWithIndex(itemIDIndex, self.getID())
        for playlist in view:
            playlist.removeItem(self)

    def _update_release_date(self):
        # This should be called whenever we get a new entry
        try:
            self.releaseDateObj = datetime(*self.getFirstVideoEnclosure().updated_parsed[0:7])
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            try:
                self.releaseDateObj = datetime(*self.entry.updated_parsed[0:7])
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                self.releaseDateObj = datetime.min

    def check_constraints(self):
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

    def signalChange(self, needsSave=True):
        self.expiring = None
        if hasattr(self, "_state"):
            del self._state
        if hasattr(self, "_size"):
            del self._size
        DDBObject.signalChange(self, needsSave=needsSave)

    def get_viewed(self):
        """Returns True iff this item has never been viewed in the interface.

        Note the difference between "viewed" and seen.
        """
        try:
            # optimizing by trying the cached feed
            return self._feed.lastViewed >= self.creationTime
        except AttributeError:
            return self.getFeed().lastViewed >= self.creationTime

    def getFirstVideoEnclosure(self):
        """Returns the first video enclosure in the item.
        """
        if hasattr(self, "_firstVidEnc") and self._firstVidEnc:
            return self._firstVidEnc

        self._calc_first_enc()
        return self._firstVidEnc

    def _calc_first_enc(self):
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

    def hasSharableURL(self):
        """Does this item have a URL that the user can share with others?

        This returns True when the item has a non-file URL.
        """
        url = self.getURL()
        return url != u'' and not url.startswith(u"file:")

    def getFeed(self):
        """Returns the feed this item came from.
        """
        if hasattr(self, "_feed"):
            return self._feed

        if self.feed_id is not None:
            self._feed = self.dd.getObjectByID(self.feed_id)
        elif self.parent_id is not None:
            self._feed = self.getParent().getFeed()
        else:
            self._feed = None
        return self._feed

    def getParent(self):
        if hasattr(self, "_parent"):
            return self._parent

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
        self._remove_from_playlists()
        UandA = self.getUandA()
        if not self.is_external():
            self.delete_files()
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
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass
        # This should be done even if screenshot = ""
        self.screenshot = None
        if self.is_external():
            if self.is_downloaded():
                new_item = FileItem(self.get_video_filename(), feed_id=self.feed_id, parent_id=self.parent_id, deleted=True)
                if self.downloader is not None:
                    self.downloader.set_delete_files(False)
            self.remove()
        else:
            self.signalChange()
        self.getFeed().signalChange()

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
        if offset.days > 0:
            result = ngettext("%(count)d day",
                              "%(count)d days",
                              offset.days,
                              {"count": offset.days})
        elif offset.seconds > 3600:
            result = ngettext("%(count)d hour",
                              "%(count)d hours",
                              ceil(offset.seconds/3600.0),
                              {"count": ceil(offset.seconds/3600.0)})
        else:
            result = ngettext("%(count)d minute",
                              "%(count)d minutes",
                              ceil(offset.seconds/60.0),
                              {"count": ceil(offset.seconds/60.0)})
        return result

    def getUandA(self):
        """Get whether this item is new, or newly-downloaded, or neither."""
        state = self.get_state()
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
        if self.getWatchedTime() is None or not self.is_downloaded():
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

    def get_expiring(self):
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
        try:
            position = int(position)
        except TypeError:
            logging.exception("setResumeTime: not-saving!  given non-int %s", position)
            return
        if self.resumeTime != position:
            self.resumeTime = position
            self.signalChange()

    def getAutoDownloaded(self):
        """Returns true iff item was auto downloaded.
        """
        self.confirmDBThread()
        return self.autoDownloaded

    def download(self, autodl=False):
        """Starts downloading the item.
        """
        autodler.resume_downloader()
        self.confirmDBThread()
        manualDownloadCount = views.manualDownloads.len()
        self.expired = self.keep = self.seen = False

        if ((not autodl) and
                manualDownloadCount >= config.get(prefs.MAX_MANUAL_DOWNLOADS)):
            self.pendingManualDL = True
            self.pendingReason = _("queued for download")
            self.signalChange()
            return
        else:
            self.setAutoDownloaded(autodl)
            self.pendingManualDL = False

        dler = downloader.getDownloader(self)
        if dler is not None:
            self.set_downloader(dler)
            self.downloader.setChannelName(unicodeToFilename(self.get_channel_title(True)))
            if self.downloader.isFinished():
                self.on_download_finished()
            else:
                self.downloader.start()
        self.signalChange()
        self.getFeed().signalChange()

    def pause(self):
        if self.downloader:
            self.downloader.pause()

    def resume(self):
        self.download(self.getAutoDownloaded())

    def is_pending_manual_download(self):
        self.confirmDBThread()
        return self.pendingManualDL

    def isEligibleForAutoDownload(self):
        self.confirmDBThread()
        if self.get_state() not in (u'new', u'not-downloaded'):
            return False
        if self.downloader and self.downloader.get_state() in (u'failed',
                u'stopped', u'paused'):
            return False
        ufeed = self.getFeed()
        if ufeed.getEverything:
            return True
        return self.eligibleForAutoDownload

    def is_pending_auto_download(self):
        return (self.getFeed().isAutoDownloadable() and
                self.isEligibleForAutoDownload())

    @returnsUnicode
    def getThumbnailURL(self):
        """Returns a link to the thumbnail of the video.
        """
        self.confirmDBThread()
        # Try to get the thumbnail specific to the video enclosure
        videoEnclosure = self.getFirstVideoEnclosure()
        if videoEnclosure is not None:
            url = self.getElementThumbnail(videoEnclosure)
            if url is not None:
                return url

        # Try to get any enclosure thumbnail
        if hasattr(self.entry, "enclosures"):
            for enclosure in self.entry.enclosures:
                url = self.getElementThumbnail(enclosure)
                if url is not None:
                    return url

        # Try to get the thumbnail for our entry
        return self.getElementThumbnail(self.entry)

    @returnsUnicode
    def getElementThumbnail(self, element):
        try:
            thumb = element["thumbnail"]
        except KeyError:
            return None
        if isinstance(thumb, str):
            return thumb
        elif isinstance(thumb, unicode):
            return thumb.decode('ascii', 'replace')
        try:
            return thumb["url"].decode('ascii', 'replace')
        except KeyError:
            return None

    @returnsFilename
    def getThumbnail(self):
        """NOTE: When changing this function, change feed.iconChanged to signal
        the right set of items.
        """
        self.confirmDBThread()
        if self.iconCache is not None and self.iconCache.isValid():
            path = self.iconCache.get_filename()
            return resources.path(fileutil.expand_filename(path))
        elif self.screenshot:
            path = self.screenshot
            return resources.path(fileutil.expand_filename(path))
        elif self.isContainerItem:
            return resources.path("images/container-icon.png")
        else:
            feed = self.getFeed()
            if feed.thumbnailValid():
                return feed.getThumbnailPath()
            elif (self.get_video_filename()
                     and filetypes.is_audio_filename(self.get_video_filename())):
                return resources.path("images/thumb-default-audio.png")
            else:
                return resources.path("images/thumb-default-video.png")

    @returnsUnicode
    def get_title(self):
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

    def has_original_title(self):
        """Returns True if this is the original title and False if the user
        has retitled the item.
        """
        if hasattr(self.entry, "title"):
            t = self.entry.title
        else:
            enc = self.getFirstVideoEnclosure()
            t = enc.get("url", _("no title")).decode("ascii", "replace")

        return self.title == t

    def revert_title(self):
        """Reverts the item title back to the data we got from RSS or the url.
        """
        self.confirmDBThread()
        if hasattr(self.entry, "title"):
            self.title = self.entry.title
        else:
            enc = self.getFirstVideoEnclosure()
            self.title = enc.get("url", _("no title")).decode("ascii", "replace")
        self.signalChange()

    def set_channel_title(self, title):
        checkU(title)
        self.channelTitle = title

    @returnsUnicode
    def get_channel_title(self, allowSearchFeedTitle=False):
        from miro import feed
        implClass = self.getFeed().actualFeed.__class__
        if implClass in (feed.RSSFeedImpl, feed.ScraperFeedImpl):
            return self.getFeed().get_title()
        elif implClass == feed.SearchFeedImpl and allowSearchFeedTitle:
            e = searchengines.get_last_engine()
            if e:
                return e.title
            else:
                return u''
        elif self.channelTitle:
            return self.channelTitle
        else:
            return u''

    @returnsUnicode
    def get_raw_description(self):
        """Returns the raw description of the video (unicode).
        """
        self.confirmDBThread()

        try:
            enclosure = self.getFirstVideoEnclosure()
            if hasattr(enclosure, "text"):
                return enclosure["text"]

            if hasattr(self.entry, "description"):
                return self.entry.description

        except Exception:
            logging.exception("get_raw_description threw exception:")

        return u''

    @returnsUnicode
    def get_description(self):
        """Returns valid XHTML containing a description of the video (str).
        """
        rawDescription = self.get_raw_description()

        purifiedDescription = adscraper.purify(rawDescription)
        ret = xhtmlify(u'<span>%s</span>' % unescape(purifiedDescription), filterFontTags=True)
        if ret:
            return ret

        return u'<span />'

    def looks_like_torrent(self):
        """Returns true if we think this item is a torrent.  (For items that
        haven't been downloaded this uses the file extension which isn't
        totally reliable).
        """

        if self.downloader is not None:
            return self.downloader.getType() == u'bittorrent'
        else:
            return filetypes.is_torrent_filename(self.getURL())

    def is_transferring(self):
        return self.downloader and self.downloader.get_state() in (u'uploading', u'downloading')

    def delete_files(self):
        """Stops downloading the item.
        """
        self.confirmDBThread()
        if self.downloader is not None:
            self.set_downloader(None)

    def get_state(self):
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
            self._calc_state()
            return self._state

    def add_to_library(self):
        pass

    @returnsUnicode
    def _calc_state(self):
        """Recalculate the state of an item after a change
        """
        self.confirmDBThread()
        # FIXME, 'failed', and 'paused' should get download icons.  The user
        # should be able to restart or cancel them (put them into the stopped
        # state).
        if (self.downloader is None  or
                self.downloader.get_state() in (u'failed', u'stopped')):
            if self.pendingManualDL:
                self._state = u'downloading'
            elif self.expired:
                self._state = u'expired'
            elif (self.get_viewed() or
                    (self.downloader and
                        self.downloader.get_state() in (u'failed', u'stopped'))):
                self._state = u'not-downloaded'
            else:
                self._state = u'new'
        elif self.downloader.get_state() in (u'offline', u'paused'):
            if self.pendingManualDL:
                self._state = u'downloading'
            else:
                self._state = u'paused'
        elif not self.downloader.isFinished():
            self._state = u'downloading'
        elif not self.getSeen():
            self._state = u'newly-downloaded'
        elif self.get_expiring():
            self._state = u'expiring'
        else:
            self._state = u'saved'

    @returnsUnicode
    def get_channel_category(self):
        """Get the category to use for the channel template.

        This method is similar to get_state(), but has some subtle differences.
        get_state() is used by the download-item template and is usually more
        useful to determine what's actually happening with an item.
        get_channel_category() is used by by the channel template to figure out
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
            if not self.get_viewed():
                return u'new'
            if self.expired:
                return u'expired'
            else:
                return u'not-downloaded'
        elif not self.getSeen():
            if not self.get_viewed():
                return u'new'
            return u'newly-downloaded'
        elif self.get_expiring():
            return u'expiring'
        else:
            return u'saved'

    def is_uploading(self):
        """Returns true if this item is currently uploading.  This only
        happens for torrents.
        """
        return self.downloader and self.downloader.get_state() == u'uploading'

    def is_uploading_paused(self):
        """Returns true if this item is uploading but paused.  This only
        happens for torrents.
        """
        return self.downloader and self.downloader.get_state() == u'uploading-paused'

    def is_downloadable(self):
        return self.get_state() in (u'new', u'not-downloaded', u'expired')

    def is_downloaded(self):
        return self.get_state() in (u"newly-downloaded", u"expiring", u"saved")

    def show_save_button(self):
        return self.get_state() in (u'newly-downloaded', u'expiring') and not self.keep

    def get_size_for_display(self):
        """Returns the size of the item to be displayed.
        """
        return util.formatSizeForUser(self.get_size())

    def get_size(self):
        if not hasattr(self, "_size"):
            self._size = self._get_size()
        return self._size

    def _get_size(self):
        """Returns the size of the item. We use the following methods to get the
        size:

        1. Physical size of a downloaded file
        2. HTTP content-length
        3. RSS enclosure tag value
        """
        if self.is_downloaded():
            try:
                fname = self.get_filename()
                return os.path.getsize(fname)
            except OSError:
                return 0
        elif self.downloader is not None:
            return self.downloader.getTotalSize()
        else:
            enc = self.getFirstVideoEnclosure()
            if enc is not None and "torrent" not in enc.get("type", ""):
                try:
                    return int(enc['length'])
                except (KeyError, ValueError):
                    pass
        return 0

    def download_progress(self):
        """Returns the download progress in absolute percentage [0.0 - 100.0].
        """
        progress = 0
        self.confirmDBThread()
        if self.downloader is None:
            return 0
        else:
            size = self.get_size()
            dled = self.downloader.get_current_size()
            if size == 0:
                return 0
            else:
                return (100.0*dled) / size

    @returnsUnicode
    def get_startup_activity(self):
        if self.pendingManualDL:
            return self.pendingReason
        elif self.downloader:
            return self.downloader.get_startup_activity()
        else:
            return _("starting up...")

    def get_pub_date_parsed(self):
        """Returns the published date of the item as a datetime object.
        """
        return self.get_release_date_obj()

    def get_release_date_obj(self):
        """Returns the date this video was released or when it was published.
        """
        return self.releaseDateObj

    def get_duration_value(self):
        """Returns the length of the video in seconds.
        """
        secs = 0
        if self.duration not in (-1, None):
            secs = self.duration / 1000
        return secs

    KNOWN_MIME_TYPES = (u'audio', u'video')
    KNOWN_MIME_SUBTYPES = (u'mov', u'wmv', u'mp4', u'mp3', u'mpg', u'mpeg', u'avi', u'x-flv', u'x-msvideo', u'm4v', u'mkv', u'm2v', u'ogg')
    MIME_SUBSITUTIONS = {
        u'QUICKTIME': u'MOV',
    }

    @returnsUnicode
    def get_format(self, emptyForUnknown=True):
        """Returns string with the format of the video.
        """
        if self.looks_like_torrent():
            return u'.torrent'

        if self.downloader:
            if self.downloader.contentType and "/" in self.downloader.contentType:
                mtype, subtype = self.downloader.contentType.split('/', 1)
                mtype = mtype.lower()
                if mtype in self.KNOWN_MIME_TYPES:
                    format = subtype.split(';')[0].upper()
                    if mtype == u'audio':
                        format += u' AUDIO'
                    if format.startswith(u'X-'):
                        format = format[2:]
                    return u'.%s' % self.MIME_SUBSITUTIONS.get(format, format).lower()

        enclosure = self.getFirstVideoEnclosure()
        if enclosure:
            try:
                extension = enclosure['url'].split('.')[-1]
                extension = extension.lower().encode('ascii', 'replace')
            except (SystemExit, KeyboardInterrupt):
                raise
            except KeyError:
                extension = u''
            # Hack for mp3s, "mpeg audio" isn't clear enough
            if extension.lower() == u'mp3':
                return u'.mp3'
            if enclosure.get('type'):
                enc = enclosure['type'].decode('ascii', 'replace')
                if "/" in enc:
                    mtype, subtype = enc.split('/', 1)
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

        if emptyForUnknown:
            return u""
        return u"unknown"

    @returnsUnicode
    def get_license(self):
        """Return the license associated with the video.
        """
        self.confirmDBThread()
        if hasattr(self.entry, "license"):
            return self.entry.license

        return self.getFeed().get_license()

    @returnsUnicode
    def get_comments_link(self):
        """Returns the comments link if it exists in the feed item.
        """
        self.confirmDBThread()
        if hasattr(self.entry, "comments"):
            return self.entry.comments

        return u""

    def get_link(self):
        """Returns the URL of the webpage associated with the item.
        """
        self.confirmDBThread()
        if hasattr(self.entry, "link"):
            link = self.entry.link
            if isinstance(link, unicode):
                return link
            try:
                return link.decode('ascii', 'replace')
            except UnicodeDecodeError:
                return link.decode('ascii', 'ignore')

        return u""

    def get_payment_link(self):
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

    def update(self, entry):
        """Updates an item with new data

        entry - dict containing the new data
        """
        UandA = self.getUandA()
        self.confirmDBThread()
        try:
            self.entry = entry
            self.iconCache.requestUpdate()
            self._update_release_date()
            self._calc_first_enc()
        finally:
            self.signalChange()

    def on_download_finished(self):
        """Called when the download for this item finishes."""

        self.confirmDBThread()
        self.downloadedTime = datetime.now()
        if not self.split_item():
            self.signalChange()
        moviedata.movieDataUpdater.requestUpdate(self)

        for other in views.items:
            if other.downloader is None and other.getURL() == self.getURL():
                other.set_downloader(self.downloader)

    def set_downloader(self, downloader):
        if downloader is self.downloader:
            return
        if self.downloader is not None:
            self.downloader.removeItem(self)
        self.downloader = downloader
        if downloader is not None:
            self.downloader_id = downloader.id
            downloader.addItem(self)
        else:
            self.downloader_id = None
        self.signalChange()

    def save(self):
        self.confirmDBThread()
        if self.keep != True:
            self.keep = True
            self.signalChange()

    @returnsFilename
    def get_filename(self):
        """Returns the filename of the first downloaded video or the empty string.

        NOTE: this will always return the absolute path to the file.
        """
        self.confirmDBThread()
        if self.downloader and hasattr(self.downloader, "get_filename"):
            return self.downloader.get_filename()

        return FilenameType("")

    @returnsFilename
    def get_video_filename(self):
        """Returns the filename of the first downloaded video or the empty string.

        NOTE: this will always return the absolute path to the file.
        """
        self.confirmDBThread()
        if self.videoFilename:
            return os.path.join(self.get_filename(), self.videoFilename)
        else:
            return self.get_filename()

    def is_nonvideo_file(self):
        # isContainerItem can be False or None.
        return self.isContainerItem != True and not self.isVideo

    def is_external(self):
        """Returns True iff this item was not downloaded from a Democracy
        channel.
        """
        return self.feed_id is not None and self.getFeedURL() == 'dtv:manualFeed'

    def is_single(self):
        """Returns True iff the item is in the singleFeed and thus was created
        by the "open" menu.
        """
        return self.getFeedURL() == 'dtv:singleFeed'

    def get_rss_entry(self):
        self.confirmDBThread()
        return self.entry

    def migrate_children(self, newdir):
        if self.isContainerItem:
            for item in self.getChildren():
                item.migrate(newdir)

    def remove(self):
        if self.downloader is not None:
            self.set_downloader(None)
        if self.iconCache is not None:
            self.iconCache.remove()
            self.iconCache = None
        if self.isContainerItem:
            for item in self.getChildren():
                item.remove()
        DDBObject.remove(self)

    def setup_links(self):
        """This is called after we restore the database.  Since we don't store
        references between objects, we need a way to reconnect downloaders to
        the items after the restore.
        """

        if not isinstance (self, FileItem) and self.downloader is None:
            dler = downloader.getExistingDownloader(self)
            if dler is not None:
                self.set_downloader(dler)
            self.fix_incorrect_torrent_subdir()
            if self.downloader is not None:
                self.signalChange(needsSave=False)
        self.split_item()
        # This must come after reconnecting the downloader
        if self.isContainerItem is not None and not fileutil.exists(self.get_filename()):
            self.expire()
            return
        if self.screenshot and not fileutil.exists(self.screenshot):
            self.screenshot = None
            self.signalChange()
        if self.duration is None or self.screenshot is None:
            moviedata.movieDataUpdater.requestUpdate (self)

    def fix_incorrect_torrent_subdir(self):
        """Up to revision 6257, torrent downloads were incorrectly being created in
        an extra subdirectory.  This method "migrates" those torrent downloads to
        the correct layout.

        from: /path/to/movies/foobar.mp4/foobar.mp4
        to:   /path/to/movies/foobar.mp4
        """
        filenamePath = self.get_filename()
        if fileutil.isdir(filenamePath):
            enclosedFile = os.path.join(filenamePath, os.path.basename(filenamePath))
            if fileutil.exists(enclosedFile):
                logging.info("Migrating incorrect torrent download: %s" % enclosedFile)
                try:
                    temp = filenamePath + ".tmp"
                    fileutil.move(enclosedFile, temp)
                    for turd in os.listdir(fileutil.expand_filename(filenamePath)):
                        os.remove(turd)
                    fileutil.rmdir(filenamePath)
                    fileutil.rename(temp, filenamePath)
                except (SystemExit, KeyboardInterrupt):
                    raise
                except:
                    logging.warn("fix_incorrect_torrent_subdir error:\n%s", traceback.format_exc())
                self.videoFilename = FilenameType("")

    def __str__(self):
        return "Item - %s" % self.get_title()

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
        Item.__init__(self, get_entry_for_file(filename), feed_id=feed_id, parent_id=parent_id)
        moviedata.movieDataUpdater.requestUpdate (self)

    @returnsUnicode
    def get_state(self):
        if self.deleted:
            return u"expired"
        elif self.getSeen():
            return u"saved"
        else:
            return u"newly-downloaded"

    def add_to_library(self):
        """Adds a file to the library."""
        manualFeed = getSingletonDDBObject(views.manualFeed)
        self.setFeed(manualFeed.getID())
        self.signalChange(needsSave=True)

    def get_channel_category(self):
        """Get the category to use for the channel template.

        This method is similar to get_state(), but has some subtle differences.
        get_state() is used by the download-item template and is usually more
        useful to determine what's actually happening with an item.
        get_channel_category() is used by by the channel template to figure out
        which heading to put an item under.

        * downloading and not-downloaded are grouped together as
          not-downloaded
        * Items are always new if their feed hasn't been marked as viewed
          after the item's pub date.  This is so that when a user gets a list
          of items and starts downloading them, the list doesn't reorder
          itself.
        * Child items match their parents for expiring, where in
          get_state, they always act as not expiring.
        """

        self.confirmDBThread()
        if self.deleted:
            return u'expired'
        elif not self.getSeen():
            return u'newly-downloaded'

        if self.parent_id and self.getParent().get_expiring():
            return u'expiring'
        else:
            return u'saved'

    def get_expiring(self):
        return False

    def show_save_button(self):
        return False

    def get_viewed(self):
        return True

    def is_external(self):
        return self.parent_id is None

    def expire(self):
        self.confirmDBThread()
        self._remove_from_playlists()
        if self.isContainerItem:
            for item in self.getChildren():
                item.remove()
        if not fileutil.exists(self.filename):
            # item whose file has been deleted outside of Miro
            self.remove()
        elif self.feed_id is None:
            self.deleted = True
            self.signalChange()
        else:
            # external item that the user deleted in Miro
            url = self.getFeedURL()
            if url.startswith("dtv:manualFeed") or url.startswith("dtv:singleFeed"):
                self.remove()
            else:
                self.deleted = True
                self.signalChange()

    def delete_files(self):
        if self.getParent():
            dler = self.getParent().downloader
            if dler:
                dler.stop(False)
        try:
            if fileutil.isfile(self.filename):
                fileutil.remove(self.filename)
            elif fileutil.isdir(self.filename):
                fileutil.rmtree(self.filename)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.warn("delete_files error:\n%s", traceback.format_exc())

    @returnsFilename
    def get_filename(self):
        if hasattr(self, "filename"):
            return self.filename

        return FilenameType("")

    def download(self, autodl=False):
        self.deleted = False
        self.signalChange()

    def _update_release_date(self):
        # This should be called whenever we get a new entry
        try:
            self.releaseDateObj = datetime.fromtimestamp(fileutil.getmtime(self.filename))
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            self.releaseDateObj = datetime.min

    def get_release_date_obj(self):
        if self.parent_id:
            return self.getParent().releaseDateObj
        else:
            return self.releaseDateObj

    def migrate(self, newDir):
        self.confirmDBThread()
        if self.parent_id:
            parent = self.getParent()
            self.filename = os.path.join (parent.get_filename(), self.offsetPath)
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
        self.migrate_children(newDir)

    def setup_links(self):
        if self.shortFilename is None:
            if self.parent_id is None:
                self.shortFilename = cleanFilename(os.path.basename(self.filename))
            else:
                parent_file = self.getParent().get_filename()
                if self.filename.startswith(parent_file):
                    self.shortFilename = cleanFilename(self.filename[len(parent_file):])
                else:
                    logging.warn("%s is not a subdirectory of %s",
                            self.filename, parent_file)
        self._update_release_date()
        Item.setup_links(self)

def reconnect_downloaders():
    reconnected = set()
    for item in views.items:
        item.setup_links()
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

def get_entry_for_file(filename):
    return FeedParserDict({'title':filenameToUnicode(os.path.basename(filename)),
            'enclosures':[{'url': resources.url(filename)}]})

def get_entry_for_url(url, contentType=None):
    if contentType is None:
        contentType = u'video/x-unknown'
    else:
        contentType = unicode(contentType)

    _, _, urlpath, _, _, _ = urlparse.urlparse(url)
    title = os.path.basename(urlpath)

    return FeedParserDict({'title' : title,
            'enclosures':[{'url' : url, 'type' : contentType}]})
