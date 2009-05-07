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
from miro.util import checkU, returnsUnicode, checkF, returnsFilename, quoteUnicodeURL, stringify, getFirstVideoEnclosure, getSingletonDDBObject, entity_replace
from miro.plat.utils import FilenameType, filenameToUnicode, unicodeToFilename
import locale
import os
import os.path
import urlparse
import traceback

from miro.download_utils import cleanFilename, nextFreeFilename
from miro.feedparser import FeedParserDict
from miro.feedparserutil import normalize_feedparser_dict

from miro.database import DDBObject, ObjectNotFoundError
from miro.database import DatabaseConstraintError
from miro.databasehelper import make_simple_get_set
from miro import app
from miro import iconcache
from miro import downloader
from miro import config
from miro import eventloop
from miro import prefs
from miro.plat import resources
from miro import util
from miro import adscraper
from miro import moviedata
import logging
from miro import filetypes
from miro import searchengines
from miro import fileutil
from miro import search
from miro import signals
from miro import playlist
from miro import models

_charset = locale.getpreferredencoding()

KNOWN_MIME_TYPES = (u'audio', u'video')
KNOWN_MIME_SUBTYPES = (
    u'mov', u'wmv', u'mp4', u'mp3',
    u'mpg', u'mpeg', u'avi', u'x-flv',
    u'x-msvideo', u'm4v', u'mkv', u'm2v', u'ogg'
    )
MIME_SUBSITUTIONS = {
    u'QUICKTIME': u'MOV',
}

class FeedParserValues(object):
    """Helper class to get values from feedparser entries

    FeedParserValues objects inspect the FeedParserDict for the entry
    attribute for various attributes using in Item (entry_title, rss_id, url,
    etc...).
    """
    def __init__(self, entry):
        self.entry = entry
        self.normalized_entry = normalize_feedparser_dict(entry)
        self.first_video_enclosure = getFirstVideoEnclosure(entry)

        self.data = {
            'license': entry.get("license"),
            'rss_id': entry.get('id'),
            'entry_title': self._calc_title(),
            'thumbnail_url': self._calc_thumbnail_url(),
            'raw_descrption': self._calc_raw_description(),
            'link': self._calc_link(),
            'payment_link': self._calc_payment_link(),
            'comments_link': self._calc_comments_link(),
            'url': self._calc_url(),
            'enclosure_size': self._calc_enclosure_size(),
            'enclosure_type': self._calc_enclosure_type(),
            'enclosure_format': self._calc_enclosure_format(),
            'releaseDateObj': self._calc_release_date(),
        }

    def update_item(self, item):
        for key, value in self.data.items():
            setattr(item, key, value)
        item.feedparser_output = self.normalized_entry

    def compare_to_item(self, item):
        for key, value in self.data.items():
            if getattr(item, key) != value:
                return False
        return True

    def compare_to_item_enclosures(self, item):
        compare_keys = (
            'url', 'enclosure_size', 'enclosure_type',
            'enclosure_format'
            )
        for key in compare_keys:
            if getattr(item, key) != self.data[key]:
                return False
        return True

    def _calc_title(self):
        if hasattr(self.entry, "title"):
            # The title attribute shouldn't use entities, but some in the
            # wild do (#11413).  In that case, try to fix them.
            return entity_replace(self.entry.title)
        else:
            if (self.first_video_enclosure and
                    'url' in self.first_video_enclosure):
                    return self.first_video_enclosure['url'].decode("ascii", "replace")
            return None

    def _calc_thumbnail_url(self):
        """Returns a link to the thumbnail of the video.  """

        # Try to get the thumbnail specific to the video enclosure
        if self.first_video_enclosure is not None:
            url = self._get_element_thumbnail(self.first_video_enclosure)
            if url is not None:
                return url

        # Try to get any enclosure thumbnail
        if hasattr(self.entry, "enclosures"):
            for enclosure in self.entry.enclosures:
                url = self._get_element_thumbnail(enclosure)
                if url is not None:
                    return url

        # Try to get the thumbnail for our entry
        return self._get_element_thumbnail(self.entry)

    def _get_element_thumbnail(self, element):
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
        except (KeyError, AttributeError):
            return None

    def _calc_raw_description(self):
        rv = None
        try:
            if hasattr(self.first_video_enclosure, "text"):
                rv = self.first_video_enclosure["text"]
            elif hasattr(self.entry, "description"):
                rv = self.entry.description
        except Exception:
            logging.exception("_calc_raw_description threw exception:")
        if rv is None:
            return u''
        else:
            return rv

    def _calc_link(self):
        if hasattr(self.entry, "link"):
            link = self.entry.link
            if isinstance(link, dict):
                try:
                    link = link['href']
                except KeyError:
                    return u""
            if isinstance(link, unicode):
                return link
            try:
                return link.decode('ascii', 'replace')
            except UnicodeDecodeError:
                return link.decode('ascii', 'ignore')
        return u""

    def _calc_payment_link(self):
        try:
            return self.first_video_enclosure.payment_url.decode('ascii','replace')
        except:
            try:
                return self.entry.payment_url.decode('ascii','replace')
            except:
                return u""

    def _calc_comments_link(self):
        return self.entry.get('comments', u"")

    def _calc_url(self):
        if (self.first_video_enclosure is not None and
                'url' in self.first_video_enclosure):
            url = self.first_video_enclosure['url'].replace('+', '%20')
            return quoteUnicodeURL(url)
        else:
            return u''

    def _calc_enclosure_size(self):
        enc = self.first_video_enclosure
        if enc is not None and "torrent" not in enc.get("type", ""):
            try:
                return int(enc['length'])
            except (KeyError, ValueError):
                return None

    def _calc_enclosure_type(self):
        if self.first_video_enclosure and self.first_video_enclosure.has_key('type'):
            return self.first_video_enclosure['type']
        else:
            return None

    def _calc_enclosure_format(self):
        enclosure = self.first_video_enclosure
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
                    if mtype in KNOWN_MIME_TYPES:
                        format = subtype.split(';')[0].upper()
                        if mtype == u'audio':
                            format += u' AUDIO'
                        if format.startswith(u'X-'):
                            format = format[2:]
                        return u'.%s' % MIME_SUBSITUTIONS.get(format, format).lower()

            if extension in KNOWN_MIME_SUBTYPES:
                return u'.%s' % extension
        return None

    def _calc_release_date(self):
        try:
            return datetime(*self.first_video_enclosure.updated_parsed[0:7])
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            try:
                return datetime(*self.entry.updated_parsed[0:7])
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                return datetime.min


class Item(DDBObject, iconcache.IconCacheOwnerMixin):
    """An item corresponds to a single entry in a feed. It has a single url
    associated with it.
    """

    ICON_CACHE_VITAL = False

    def setup_new(self, entry, linkNumber=0, feed_id=None, parent_id=None):
        self.is_file_item = False
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
        FeedParserValues(entry).update_item(self)
        self.expired = False
        self.keep = False
        self.set_video_filename(None)
        self.eligibleForAutoDownload = True
        self.duration = None
        self.screenshot = None
        self.resumeTime = 0
        self.channelTitle = None
        self.downloader_id = None
        self.was_downloaded = False
        self.setup_new_icon_cache()
        # Initalize FileItem attributes to None
        self.filename = self.deleted = self.shortFilename = \
                self.offsetPath = None

        # linkNumber is a hack to make sure that scraped items at the
        # top of a page show up before scraped items at the bottom of
        # a page. 0 is the topmost, 1 is the next, and so on
        self.linkNumber = linkNumber
        self.creationTime = datetime.now()
        self._update_release_date()
        self._look_for_downloader()
        self.setup_common()

    def setup_restored(self):
        # For unknown reason(s), some users still have databases with item
        # objects missing the isContainerItem attribute even after
        # a db upgrade (#8819).

        if not hasattr(self, 'isContainerItem'):
            self.isContainerItem = None
        self.setup_common()
        self.setup_links()

    def setup_common(self):
        self.selected = False
        self.active = False
        self.expiring = None
        self.showMoreInfo = False
        self.updating_movie_info = False

    def on_db_insert(self):
        self.split_item()

    @classmethod
    def auto_pending_view(cls):
        return cls.make_view('feed.autoDownloadable AND '
                'NOT item.was_downloaded AND '
                '(item.eligibleForAutoDownload OR feed.getEverything)',
                joins={'feed': 'item.feed_id=feed.id'})

    @classmethod
    def manual_pending_view(cls):
        return cls.make_view('pendingManualDL')

    @classmethod
    def auto_downloads_view(cls):
        return cls.make_view("item.autoDownloaded AND "
                "rd.state in ('downloading', 'paused')",
                joins={'remote_downloader rd': 'item.downloader_id=rd.id'})

    @classmethod
    def manual_downloads_view(cls):
        return cls.make_view("NOT item.autoDownloaded AND "
                "NOT item.pendingManualDL AND "
                "rd.state in ('downloading', 'paused')",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def downloading_paused_view(cls):
        return cls.make_view("rd.state in ('downloading', 'paused', "
                "'uploading', 'uploading-paused') AND rd.main_item_id=item.id",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def downloading_view(cls):
        return cls.make_view("rd.state in ('downloading', 'uploading') AND "
                "rd.main_item_id=item.id",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def paused_view(cls):
        return cls.make_view("rd.state in ('paused', 'uploading-paused') AND "
                "rd.main_item_id=item.id",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def newly_downloaded_view(cls):
        return cls.make_view("NOT item.seen AND "
                "item.parent_id IS NULL AND "
                "rd.state in ('finished', 'uploading', 'uploading-paused')",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def downloaded_view(cls):
        return cls.make_view("rd.state in ('finished', 'uploading', "
                "'uploading-paused')",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def unique_new_video_view(cls):
        return cls.make_view("NOT item.seen AND "
                "item.parent_id IS NULL AND "
                "rd.main_item_id=item.id AND "
                "item.file_type='video' AND "
                "rd.state in ('finished', 'uploading', 'uploading-paused')",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def unique_new_audio_view(cls):
        return cls.make_view("NOT item.seen AND "
                "item.parent_id IS NULL AND "
                "rd.main_item_id=item.id AND "
                "item.file_type='audio' AND "
                "rd.state in ('finished', 'uploading', 'uploading-paused')",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def toplevel_view(cls):
        return cls.make_view('feed_id IS NOT NULL')

    @classmethod
    def feed_view(cls, feed_id):
        return cls.make_view('feed_id=?', (feed_id,))

    @classmethod
    def visible_feed_view(cls, feed_id):
        return cls.make_view('feed_id=? AND (deleted IS NULL or not deleted)',
                (feed_id,))

    @classmethod
    def visible_folder_view(cls, folder_id):
        return cls.make_view('folder_id=? AND (deleted IS NULL or not deleted)',
                (folder_id,),
                joins={'feed': 'item.feed_id=feed.id'})

    @classmethod
    def feed_downloaded_view(cls, feed_id):
        return cls.make_view("feed_id=? AND "
                "rd.state in ('finished', 'uploading', 'uploading-paused')",
                (feed_id,),
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def feed_downloading_view(cls, feed_id):
        return cls.make_view("feed_id=? AND "
                "rd.state in ('downloading', 'uploading') AND "
                "rd.main_item_id=item.id",
                (feed_id,),
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def feed_available_view(cls, feed_id):
        return cls.make_view("feed_id=? AND "
                "feed.last_viewed <= item.creationTime",
                (feed_id,),
                joins={'feed': 'item.feed_id=feed.id'})

    @classmethod
    def feed_auto_pending_view(cls, feed_id):
        return cls.make_view('feed_id=? AND feed.autoDownloadable AND '
                'NOT item.was_downloaded AND '
                '(item.eligibleForAutoDownload OR feed.getEverything)',
                (feed_id,),
                joins={'feed': 'item.feed_id=feed.id'})

    @classmethod
    def feed_unwatched_view(cls, feed_id):
        return cls.make_view("feed_id=? AND not seen AND "
                "(is_file_item OR rd.state in ('finished', 'uploading', "
                "'uploading-paused'))",
                (feed_id,),
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def children_view(cls, parent_id):
        return cls.make_view('parent_id=?', (parent_id,))

    @classmethod
    def playlist_view(cls, playlist_id):
        return cls.make_view("pim.playlist_id=?", (playlist_id,),
                joins={'playlist_item_map AS pim': 'item.id=pim.item_id'},
                order_by='pim.position')

    @classmethod
    def playlist_folder_view(cls, playlist_folder_id):
        return cls.make_view("pim.playlist_id=?", (playlist_folder_id,),
                joins={'playlist_folder_item_map AS pim': 'item.id=pim.item_id'},
                order_by='pim.position')

    @classmethod
    def search_item_view(cls):
        return cls.make_view("feed.origURL == 'dtv:search'",
                joins={'feed': 'item.feed_id=feed.id'})

    @classmethod
    def watchable_video_view(cls):
        return cls.make_view("not isContainerItem AND "
                "(deleted IS NULL or not deleted) AND "
                "(is_file_item OR rd.main_item_id=item.id) AND "
                "feed.origURL != 'dtv:singleFeed' AND "
                "item.file_type='video'",
                joins={'feed': 'item.feed_id=feed.id',
                    'remote_downloader as rd': 'item.downloader_id=rd.id'})

    @classmethod
    def watchable_audio_view(cls):
        return cls.make_view("not isContainerItem AND "
                "(deleted IS NULL or not deleted) AND "
                "(is_file_item OR rd.main_item_id=item.id) AND "
                "feed.origURL != 'dtv:singleFeed' AND "
                "item.file_type='audio'",
                joins={'feed': 'item.feed_id=feed.id',
                    'remote_downloader as rd': 'item.downloader_id=rd.id'})

    @classmethod
    def feed_expiring_view(cls, feed_id, watched_before):
        return cls.make_view("watchedTime is not NULL AND "
                "watchedTime < ? AND feed_id = ?",
                (watched_before, feed_id),
                joins={'feed': 'item.feed_id=feed.id'})

    def get_expiring(self):
        if self.expiring is None:
            if not self.getSeen():
                self.expiring = False
            else:
                ufeed = self.get_feed()
                if (self.keep or ufeed.expire == u'never' or
                        (ufeed.expire == u'system' and
                            config.get(prefs.EXPIRE_AFTER_X_DAYS) <= 0)):
                    self.expiring = False
                else:
                    self.expiring = True
        return self.expiring

    def _look_for_downloader(self):
        self.set_downloader(downloader.lookup_downloader(self.get_url()))

    getSelected, setSelected = make_simple_get_set(u'selected',
            changeNeedsSave=False)
    getActive, setActive = make_simple_get_set(u'active', changeNeedsSave=False)

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
        signal_change().
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
            self.signal_change()
            return True
        return False

    def split_item(self):
        """returns True if it ran signal_change()"""
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
                    new_video_filename = video[len(filename_root):]
                    while new_video_filename[0] in ('/', '\\'):
                        new_video_filename = new_video_filename[1:]
                    self.set_video_filename(new_video_filename)
                    self.isVideo = True
            else:
                if not self.get_feed_url().startswith ("dtv:directoryfeed"):
                    target_dir = config.get(prefs.NON_VIDEO_DIRECTORY)
                    if not filename_root.startswith(target_dir):
                        if isinstance(self, FileItem):
                            self.migrate (target_dir)
                        else:
                            self.downloader.migrate (target_dir)
                self.isContainerItem = False
        else:
            self.isContainerItem = False
            self.isVideo = True
        self.signal_change()
        return True

    def set_video_filename(self, filename):
        if filename is None:
            self.videoFilename = FilenameType("")
            self.file_type = None
        else:
            self.videoFilename = filename
            self.file_type = self._file_type_for_filename(filename)

    def _file_type_for_filename(self, filename):
        for ext in filetypes.VIDEO_EXTENSIONS:
            if filename.endswith(ext):
                return u'video'
        for ext in filetypes.AUDIO_EXTENSIONS:
            if filename.endswith(ext):
                return u'audio'
        return u'other'

    def _check_file_type(self):
        current_type = self._file_type_for_filename

    def matches_search(self, searchString):
        if searchString is None:
            return True
        searchString = searchString.lower()
        title = self.get_title() or u''
        desc = self.get_raw_description() or u''
        filename = filenameToUnicode(self.get_filename()) or u''
        if search.match(searchString, [title.lower(), desc.lower(), filename.lower()]):
            return True
        if not self.isContainerItem:
            parent = self.get_parent()
        if parent != self:
            return matchingItems(parent, searchString)
        return False

    def _remove_from_playlists(self):
        models.PlaylistItemMap.remove_item_from_playlists(self)
        models.PlaylistFolderItemMap.remove_item_from_playlists(self)

    def _update_release_date(self):
        # FeedParserValues sets up the releaseDateObj attribute
        pass

    def check_constraints(self):
        if self.feed_id is not None:
            try:
                obj = models.Feed.get_by_id(self.feed_id)
            except ObjectNotFoundError:
                raise DatabaseConstraintError("my feed (%s) is not in database" % self.feed_id)
            else:
                if not isinstance(obj, models.Feed):
                    msg = "feed_id points to a %s instance" % obj.__class__
                    raise DatabaseConstraintError(msg)
        if self.parent_id is not None:
            try:
                obj = Item.get_by_id(self.parent_id)
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

    def on_signal_change(self):
        self.expiring = None
        if hasattr(self, "_state"):
            del self._state
        if hasattr(self, "_size"):
            del self._size
        self.get_feed().on_item_changed()

    def get_viewed(self):
        """Returns True iff this item has never been viewed in the interface.

        Note the difference between "viewed" and seen.
        """
        try:
            # optimizing by trying the cached feed
            return self._feed.last_viewed >= self.creationTime
        except AttributeError:
            return self.get_feed().last_viewed >= self.creationTime

    @returnsUnicode
    def get_url(self):
        """Returns the URL associated with the first enclosure in the item.
        """
        return self.url

    def has_shareable_url(self):
        """Does this item have a URL that the user can share with others?

        This returns True when the item has a non-file URL.
        """
        url = self.get_url()
        return url != u'' and not url.startswith(u"file:")

    def get_feed(self):
        """Returns the feed this item came from.
        """
        if hasattr(self, "_feed"):
            return self._feed

        if self.feed_id is not None:
            self._feed = models.Feed.get_by_id(self.feed_id)
        elif self.parent_id is not None:
            self._feed = self.get_parent().get_feed()
        else:
            self._feed = None
        return self._feed

    def get_parent(self):
        if hasattr(self, "_parent"):
            return self._parent

        if self.parent_id is not None:
            self._parent = Item.get_by_id(self.parent_id)
        else:
            self._parent = self
        return self._parent

    @returnsUnicode
    def get_feed_url(self):
        return self.get_feed().get_url()

    def getChildren(self):
        if self.isContainerItem:
            return Item.children_view(self.id)
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
                item.signal_change()
        self.signal_change()

    def expire(self):
        self.confirm_db_thread()
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
        self.set_video_filename(None)
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
            self.signal_change()
        self.get_feed().signal_change()

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

    def get_expiration_time(self):
        """Returns the time when this item should expire.

        Returns a datetime.datetime object,  or None if it doesn't expire.
        """
        self.confirm_db_thread()
        if self.get_watched_time() is None or not self.is_downloaded():
            return None
        ufeed = self.get_feed()
        if ufeed.expire == u'never' or (ufeed.expire == u'system'
                and config.get(prefs.EXPIRE_AFTER_X_DAYS) <= 0):
            return None
        else:
            if ufeed.expire == u"feed":
                expireTime = ufeed.expireTime
            elif ufeed.expire == u"system":
                expireTime = timedelta(days=config.get(prefs.EXPIRE_AFTER_X_DAYS))
            return self.get_watched_time() + expireTime

    def get_watched_time(self):
        """Returns the most recent watched time of this item or any
        of its child items.

        Returns a datetime.datetime instance or None if the item and none
        of its children have been watched.
        """
        if not self.getSeen():
            return None
        if self.isContainerItem and self.watchedTime == None:
            self.watchedTime = datetime.min
            for item in self.getChildren():
                childTime = item.get_watched_time()
                if childTime is None:
                    self.watchedTime = None
                    return None
                if childTime > self.watchedTime:
                    self.watchedTime = childTime
            self.signal_change()
        return self.watchedTime

    def get_expiring(self):
        if self.expiring is None:
            if not self.getSeen():
                self.expiring = False
            else:
                ufeed = self.get_feed()
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
        self.confirm_db_thread()
        return self.seen

    def markItemSeen(self, markOtherItems=True):
        """Marks the item as seen.
        """
        self.confirm_db_thread()
        if self.seen == False:
            self.seen = True
            if self.watchedTime is None:
                self.watchedTime = datetime.now()
            self.signal_change()
            self.update_parent_seen()
            if markOtherItems and self.downloader:
                for item in self.downloader.itemList:
                    if item != self:
                        item.markItemSeen(False)

    def update_parent_seen(self):
        if self.parent_id:
            unseen_children = self.make_view('parent_id=? AND NOT seen',
                    (self.parent_id,))
            self.get_parent().seen = (unseen_children.count() == 0)

    def markItemUnseen(self, markOtherItems=True):
        self.confirm_db_thread()
        if self.isContainerItem:
            for item in self.getChildren():
                item.seen = False
                item.signal_change()
            self.signal_change()
        else:
            if self.seen == False:
                return
            self.seen = False
            self.watchedTime = None
            self.signal_change()
            self.update_parent_seen()
            if markOtherItems and self.downloader:
                for item in self.downloader.itemList:
                    if item != self:
                        item.markItemUnseen(False)

    @returnsUnicode
    def getRSSID(self):
        self.confirm_db_thread()
        return self.rss_id

    def removeRSSID(self):
        self.confirm_db_thread()
        self.rss_id = None
        self.signal_change()

    def setAutoDownloaded(self, autodl=True):
        self.confirm_db_thread()
        if autodl != self.autoDownloaded:
            self.autoDownloaded = autodl
            self.signal_change()

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
            self.signal_change()

    def getAutoDownloaded(self):
        """Returns true iff item was auto downloaded.
        """
        self.confirm_db_thread()
        return self.autoDownloaded

    def download(self, autodl=False):
        """Starts downloading the item.
        """
        self.confirm_db_thread()
        manual_dl_count = Item.manual_downloads_view().count()
        self.expired = self.keep = self.seen = False
        self.was_downloaded = True

        if ((not autodl) and
                manual_dl_count >= config.get(prefs.MAX_MANUAL_DOWNLOADS)):
            self.pendingManualDL = True
            self.pendingReason = _("queued for download")
            self.signal_change()
            return
        else:
            self.setAutoDownloaded(autodl)
            self.pendingManualDL = False

        dler = downloader.get_downloader_for_item(self)
        if dler is not None:
            self.set_downloader(dler)
            self.downloader.set_channel_name(unicodeToFilename(self.get_channel_title(True)))
            if self.downloader.isFinished():
                self.on_download_finished()
            else:
                self.downloader.start()
        self.signal_change()
        self.get_feed().signal_change()

    def pause(self):
        if self.downloader:
            self.downloader.pause()

    def resume(self):
        self.download(self.getAutoDownloaded())

    def is_pending_manual_download(self):
        self.confirm_db_thread()
        return self.pendingManualDL

    def is_eligible_for_auto_download(self):
        self.confirm_db_thread()
        if self.was_downloaded:
            return False
        ufeed = self.get_feed()
        if ufeed.getEverything:
            return True
        return self.eligibleForAutoDownload

    def is_pending_auto_download(self):
        return (self.get_feed().isAutoDownloadable() and
                self.is_eligible_for_auto_download())

    @returnsUnicode
    def get_thumbnail_url(self):
        return self.thumbnail_url

    @returnsFilename
    def getThumbnail(self):
        """NOTE: When changing this function, change feed.icon_changed to signal
        the right set of items.
        """
        self.confirm_db_thread()
        if self.icon_cache is not None and self.icon_cache.isValid():
            path = self.icon_cache.get_filename()
            return resources.path(fileutil.expand_filename(path))
        elif self.screenshot:
            path = self.screenshot
            return resources.path(fileutil.expand_filename(path))
        elif self.isContainerItem:
            return resources.path("images/container-icon.png")
        else:
            feed = self.get_feed()
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
        if self.title:
            return self.title
        else:
            if self.entry_title is not None:
                return self.entry_title
            else: return _('no title')

    def set_title(self, s):
        self.confirm_db_thread()
        self.title = s
        self.signal_change()

    def has_original_title(self):
        """Returns True if this is the original title and False if the user
        has retitled the item.
        """
        return self.title == self.entry_title

    def revert_title(self):
        """Reverts the item title back to the data we got from RSS or the url.
        """
        self.confirm_db_thread()
        self.title = self.entry_title
        self.signal_change()

    def set_channel_title(self, title):
        checkU(title)
        self.channelTitle = title

    @returnsUnicode
    def get_channel_title(self, allowSearchFeedTitle=False):
        implClass = self.get_feed().actualFeed.__class__
        if implClass in (models.RSSFeedImpl, models.ScraperFeedImpl):
            return self.get-feed().get_title()
        elif implClass == models.SearchFeedImpl and allowSearchFeedTitle:
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
        return self.raw_descrption

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
            return self.downloader.get_type() == u'bittorrent'
        else:
            return filetypes.is_torrent_filename(self.get_url())

    def is_transferring(self):
        return self.downloader and self.downloader.get_state() in (u'uploading', u'downloading')

    def delete_files(self):
        """Stops downloading the item.
        """
        self.confirm_db_thread()
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

    @returnsUnicode
    def _calc_state(self):
        """Recalculate the state of an item after a change
        """
        self.confirm_db_thread()
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

        self.confirm_db_thread()
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
            if self.enclosure_size is not None:
                return self.enclosure_size
        return 0

    def download_progress(self):
        """Returns the download progress in absolute percentage [0.0 - 100.0].
        """
        progress = 0
        self.confirm_db_thread()
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
                if mtype in KNOWN_MIME_TYPES:
                    format = subtype.split(';')[0].upper()
                    if mtype == u'audio':
                        format += u' AUDIO'
                    if format.startswith(u'X-'):
                        format = format[2:]
                    return u'.%s' % MIME_SUBSITUTIONS.get(format, format).lower()

        if self.enclosure_format is not None:
            return self.enclosure_format

        if emptyForUnknown:
            return u""
        return u"unknown"

    @returnsUnicode
    def get_license(self):
        """Return the license associated with the video.
        """
        self.confirm_db_thread()
        if self.license:
            return self.license
        return self.get_feed().get_license()

    @returnsUnicode
    def get_comments_link(self):
        """Returns the comments link if it exists in the feed item.
        """
        return self.comments_link

    def get_link(self):
        """Returns the URL of the webpage associated with the item.
        """
        return self.link

    def get_payment_link(self):
        """Returns the URL of the payment page associated with the item.
        """
        return self.payment_link

    def update(self, entry):
        """Updates an item with new data

        entry - dict containing the new data
        """
        self.update_from_feed_parser_values(FeedParserValues(entry))

    def update_from_feed_parser_values(self, fp_values):
        fp_values.update_item(self)
        print 'updated: ', self.link
        print fp_values.data
        self.icon_cache.request_update()
        self._update_release_date()
        self.signal_change()

    def on_download_finished(self):
        """Called when the download for this item finishes."""

        self.confirm_db_thread()
        self.downloadedTime = datetime.now()
        self.set_video_filename(self.downloader.get_filename())
        self.split_item()
        self.signal_change()
        moviedata.movieDataUpdater.request_update(self)

        for other in Item.make_view('downloader_id IS NULL AND url=?',
                (self.url,)):
            other.set_downloader(self.downloader)

    def set_downloader(self, downloader):
        if self.downloader_id is not None:
            if downloader is self._downloader:
                return
            self.downloader.removeItem(self)
        self._downloader = downloader
        if downloader is not None:
            self.downloader_id = downloader.id
            downloader.addItem(self)
        else:
            self.downloader_id = None
        self.signal_change()

    def save(self):
        self.confirm_db_thread()
        if self.keep != True:
            self.keep = True
            self.signal_change()

    @returnsFilename
    def get_filename(self):
        """Returns the filename of the first downloaded video or the empty string.

        NOTE: this will always return the absolute path to the file.
        """
        self.confirm_db_thread()
        if self.downloader and hasattr(self.downloader, "get_filename"):
            return self.downloader.get_filename()

        return FilenameType("")

    @returnsFilename
    def get_video_filename(self):
        """Returns the filename of the first downloaded video or the empty string.

        NOTE: this will always return the absolute path to the file.
        """
        self.confirm_db_thread()
        if self.videoFilename:
            return os.path.join(self.get_filename(), self.videoFilename)
        else:
            return self.get_filename()

    def is_video_file(self):
        return self.isContainerItem != True and filetypes.is_video_filename(self.get_filename())
        
    def is_audio_file(self):
        return self.isContainerItem != True and filetypes.is_audio_filename(self.get_filename())

    def is_nonvideo_file(self):
        # isContainerItem can be False or None.
        return self.isContainerItem != True and not self.isVideo

    def is_external(self):
        """Returns True iff this item was not downloaded from a Democracy
        channel.
        """
        return self.feed_id is not None and self.get_feed_url() == 'dtv:manualFeed'

    def is_single(self):
        """Returns True iff the item is in the singleFeed and thus was created
        by the "open" menu.
        """
        return self.get_feed_url() == 'dtv:singleFeed'

    def migrate_children(self, newdir):
        if self.isContainerItem:
            for item in self.getChildren():
                item.migrate(newdir)

    def remove(self):
        if self.downloader is not None:
            self.set_downloader(None)
        self.remove_icon_cache()
        if self.isContainerItem:
            for item in self.getChildren():
                item.remove()
        self._remove_from_playlists()
        DDBObject.remove(self)

    def setup_links(self):
        self.split_item()
        if (self.isContainerItem is not None and
                not fileutil.exists(self.get_filename()) and
                not hasattr(app, 'in_unit_tests')):
            self.expire()
            return
        if self.screenshot and not fileutil.exists(self.screenshot):
            self.screenshot = None
            self.signal_change()

    def _get_downloader(self):
        try:
            return self._downloader
        except AttributeError:
            dler = downloader.get_existing_downloader(self)
            if dler is not None:
                dler.addItem(self)
            self._downloader = dler
            return dler
    downloader = property(_get_downloader)

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
                self.set_video_filename(none)

    def __str__(self):
        return "Item - %s" % self.get_title()

class FileItem(Item):
    """An Item that exists as a local file
    """

    def setup_new(self, filename, feed_id=None, parent_id=None, offsetPath=None, deleted=False):
        Item.setup_new(self, get_entry_for_file(filename), feed_id=feed_id, parent_id=parent_id)
        self.is_file_item = True
        checkF(filename)
        filename = fileutil.abspath(filename)
        self.filename = filename
        self.set_video_filename(filename)
        self.deleted = deleted
        self.offsetPath = offsetPath
        self.shortFilename = cleanFilename(os.path.basename(self.filename))
        self.was_downloaded = False
        moviedata.movieDataUpdater.request_update (self)

    # FileItem downloaders are always None
    downloader = property(lambda self: None)

    @returnsUnicode
    def get_state(self):
        if self.deleted:
            return u"expired"
        elif self.getSeen():
            return u"saved"
        else:
            return u"newly-downloaded"

    def is_eligible_for_auto_download(self):
        return False

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

        self.confirm_db_thread()
        if self.deleted:
            return u'expired'
        elif not self.getSeen():
            return u'newly-downloaded'

        if self.parent_id and self.get_parent().get_expiring():
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
        self.confirm_db_thread()
        self._remove_from_playlists()
        if self.isContainerItem:
            for item in self.getChildren():
                item.remove()
        if not fileutil.exists(self.filename):
            # item whose file has been deleted outside of Miro
            self.remove()
        elif self.feed_id is None:
            self.deleted = True
            self.signal_change()
        else:
            # external item that the user deleted in Miro
            url = self.get_feed_url()
            if url.startswith("dtv:manualFeed") or url.startswith("dtv:singleFeed"):
                self.remove()
            else:
                self.deleted = True
                self.signal_change()

    def delete_files(self):
        if self.get_parent():
            dler = self.get_parent().downloader
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
        self.signal_change()

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
            return self.get_parent().releaseDateObj
        else:
            return self.releaseDateObj

    def migrate(self, newDir):
        self.confirm_db_thread()
        if self.parent_id:
            parent = self.get_parent()
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
                self.signal_change()
            fileutil.migrate_file(self.filename, newFilename, callback)
        elif fileutil.exists(newFilename):
            self.filename = newFilename
            self.signal_change()
        self.migrate_children(newDir)

    def setup_links(self):
        if self.shortFilename is None:
            if self.parent_id is None:
                self.shortFilename = cleanFilename(os.path.basename(self.filename))
            else:
                parent_file = self.get_parent().get_filename()
                if self.filename.startswith(parent_file):
                    self.shortFilename = cleanFilename(self.filename[len(parent_file):])
                else:
                    logging.warn("%s is not a subdirectory of %s",
                            self.filename, parent_file)
        self._update_release_date()
        Item.setup_links(self)

def get_entry_for_file(filename):
    return FeedParserDict({'title':filenameToUnicode(os.path.basename(filename)),
            'enclosures':[{'url': resources.url(filename)}]})

def update_incomplete_movie_data():
    for item in Item.downloaded_view():
        if item.duration is None or item.screenshot is None:
            moviedata.movieDataUpdater.request_update(item)
