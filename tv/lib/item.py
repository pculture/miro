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

"""``miro.item`` -- Holds ``Item`` class and related things.
"""

from datetime import datetime, timedelta
from miro.gtcache import gettext as _
from miro.util import (check_u, returns_unicode, check_f, returns_filename,
                       quote_unicode_url, stringify, get_first_video_enclosure,
                       entity_replace)
from miro.plat.utils import (filename_to_unicode, unicode_to_filename,
                             utf8_to_filename)
import locale
import os.path
import shutil
import traceback

from miro.download_utils import clean_filename, next_free_filename
from miro.feedparser import FeedParserDict

from miro.database import (DDBObject, ObjectNotFoundError,
                           DatabaseConstraintError)
from miro.databasehelper import make_simple_get_set
from miro import app
from miro import iconcache
from miro import databaselog
from miro import downloader
from miro import eventloop
from miro import prefs
from miro.plat import resources
from miro import util
from miro import moviedata
import logging
from miro import filetypes
from miro import searchengines
from miro import fileutil
from miro import search
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
    attribute for various attributes using in Item (entry_title,
    rss_id, url, etc...).
    """
    def __init__(self, entry):
        self.entry = entry
        self.first_video_enclosure = get_first_video_enclosure(entry)

        self.data = {
            'license': entry.get("license"),
            'rss_id': entry.get('id'),
            'entry_title': self._calc_title(),
            'thumbnail_url': self._calc_thumbnail_url(),
            'entry_description': self._calc_raw_description(),
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
            # The title attribute shouldn't use entities, but some in
            # the wild do (#11413).  In that case, try to fix them.
            return entity_replace(self.entry.title)

        if ((self.first_video_enclosure
             and 'url' in self.first_video_enclosure)):
            return self.first_video_enclosure['url'].decode("ascii",
                                                                "replace")
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
        try:
            if isinstance(thumb, unicode):
                return thumb.encode('utf-8')
            # We can't get the type??  What to do ....
            return thumb["url"].decode('ascii', 'replace')
        except (KeyError, AttributeError, UnicodeEncodeError,
                UnicodeDecodeError):
            return None

    def _calc_raw_description(self):
        """Check the enclosure to see if it has a description first.
        If not, then grab the description from the entry.

        Both first_video_enclosure and entry are FeedParserDicts,
        which does some fancy footwork with normalizing feed entry
        data.
        """
        rv = None
        if self.first_video_enclosure:
            rv = self.first_video_enclosure.get("text", None)
        if not rv and self.entry:
            rv = self.entry.get("description", None)
        if not rv:
            return u''
        return rv

    def _calc_link(self):
        if hasattr(self.entry, "link"):
            link = self.entry.link
            if isinstance(link, dict):
                try:
                    link = link['href']
                except KeyError:
                    return u""
            if link is None:
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
            return self.first_video_enclosure.payment_url.decode('ascii',
                                                                 'replace')
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
            return quote_unicode_url(url)
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
        if ((self.first_video_enclosure
             and self.first_video_enclosure.has_key('type'))):
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
                        return (u'.%s' %
                                MIME_SUBSITUTIONS.get(format, format).lower())

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
    """An item corresponds to a single entry in a feed.  It has a
    single url associated with it.
    """

    ICON_CACHE_VITAL = False

    def setup_new(self, fp_values, linkNumber=0, feed_id=None, parent_id=None,
            eligibleForAutoDownload=True, channel_title=None):
        self.is_file_item = False
        self.feed_id = feed_id
        self.parent_id = parent_id
        self.channelTitle = channel_title
        self.isContainerItem = None
        self.seen = False
        self.autoDownloaded = False
        self.pendingManualDL = False
        self.downloadedTime = None
        self.watchedTime = None
        self.pendingReason = u""
        self.title = u""
        self.description = u""
        fp_values.update_item(self)
        self.expired = False
        self.keep = False
        self.filename = self.file_type = None
        self.eligibleForAutoDownload = eligibleForAutoDownload
        self.duration = None
        self.screenshot = None
        self.media_type_checked = False
        self.resumeTime = 0
        self.channelTitle = None
        self.downloader_id = None
        self.was_downloaded = False
        self.subtitle_encoding = None
        self.setup_new_icon_cache()
        # Initalize FileItem attributes to None
        self.deleted = self.shortFilename = self.offsetPath = None

        # linkNumber is a hack to make sure that scraped items at the
        # top of a page show up before scraped items at the bottom of
        # a page. 0 is the topmost, 1 is the next, and so on
        self.linkNumber = linkNumber
        self.creationTime = datetime.now()
        self._look_for_downloader()
        self.setup_common()
        self.split_item()
        app.item_info_cache.item_created(self)

    def setup_restored(self):
        self.setup_common()
        self.setup_links()

    def setup_common(self):
        self.selected = False
        self.active = False
        self.expiring = None
        self.showMoreInfo = False
        self.updating_movie_info = False

    def signal_change(self, needs_save=True):
        app.item_info_cache.item_changed(self)
        DDBObject.signal_change(self, needs_save)

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
    def download_tab_view(cls):
        return cls.make_view("(item.pendingManualDL OR "
                "(rd.state in ('downloading', 'paused', 'uploading', "
                "'uploading-paused', 'offline') OR "
                "(rd.state == 'failed' AND "
                "feed.origURL == 'dtv:manualFeed')) AND "
                "rd.main_item_id=item.id)",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id',
                    'feed': 'item.feed_id=feed.id'})

    @classmethod
    def downloading_view(cls):
        return cls.make_view("rd.state in ('downloading', 'uploading') AND "
                "rd.main_item_id=item.id",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def only_downloading_view(cls):
        return cls.make_view("rd.state='downloading' AND "
                "rd.main_item_id=item.id",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def paused_view(cls):
        return cls.make_view("rd.state in ('paused', 'uploading-paused') AND "
                "rd.main_item_id=item.id",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def unwatched_downloaded_items(cls):
        return cls.make_view("NOT item.seen AND "
                "item.parent_id IS NULL AND "
                "rd.state in ('finished', 'uploading', 'uploading-paused')",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def newly_downloaded_view(cls):
        return cls.make_view("NOT item.seen AND "
                "(item.file_type != 'other') AND "
                "(is_file_item OR "
                "rd.state in ('finished', 'uploading', 'uploading-paused'))",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def downloaded_view(cls):
        return cls.make_view("rd.state in ('finished', 'uploading', "
                "'uploading-paused')",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def next_10_incomplete_movie_data_view(cls):
        return cls.make_view("(is_file_item OR (rd.state in ('finished', "
                "'uploading', 'uploading-paused'))) AND "
                '(duration IS NULL OR '
                'screenshot IS NULL OR '
                'NOT item.media_type_checked)',
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'},
                limit=10)

    @classmethod
    def unique_new_video_view(cls):
        return cls.make_view("NOT item.seen AND "
                "item.file_type='video' AND "
                "((is_file_item AND NOT deleted) OR "
                "(rd.main_item_id=item.id AND "
                "rd.state in ('finished', 'uploading', 'uploading-paused')))",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def unique_new_audio_view(cls):
        return cls.make_view("NOT item.seen AND "
                "item.file_type='audio' AND "
                "((is_file_item AND NOT deleted) OR "
                "(rd.main_item_id=item.id AND "
                "rd.state in ('finished', 'uploading', 'uploading-paused')))",
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
        return cls.make_view(
            'folder_id=? AND (deleted IS NULL or not deleted)',
            (folder_id,),
            joins={'feed': 'item.feed_id=feed.id'})

    @classmethod
    def folder_contents_view(cls, folder_id):
        return cls.make_view('parent_id=?', (folder_id,))

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
        return cls.make_view("feed_id=? AND NOT autoDownloaded "
                "AND downloadedTime IS NULL AND "
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
        return cls.make_view(
            "pim.playlist_id=?", (playlist_folder_id,),
            joins={'playlist_folder_item_map AS pim': 'item.id=pim.item_id'},
            order_by='pim.position')

    @classmethod
    def search_item_view(cls):
        return cls.make_view("feed.origURL == 'dtv:search'",
                joins={'feed': 'item.feed_id=feed.id'})

    @classmethod
    def watchable_video_view(cls):
        return cls.make_view(
            "not isContainerItem AND "
            "(deleted IS NULL or not deleted) AND "
            "(is_file_item OR rd.main_item_id=item.id) AND "
            "(feed.origURL IS NULL OR feed.origURL!= 'dtv:singleFeed') AND "
            "item.file_type='video'",
            joins={'feed': 'item.feed_id=feed.id',
                   'remote_downloader as rd': 'item.downloader_id=rd.id'})

    @classmethod
    def watchable_audio_view(cls):
        return cls.make_view(
            "not isContainerItem AND "
            "(deleted IS NULL or not deleted) AND "
            "(is_file_item OR rd.main_item_id=item.id) AND "
            "(feed.origURL IS NULL OR feed.origURL!= 'dtv:singleFeed') AND "
            "item.file_type='audio'",
            joins={'feed': 'item.feed_id=feed.id',
                   'remote_downloader as rd': 'item.downloader_id=rd.id'})

    @classmethod
    def watchable_other_view(cls):
        return cls.make_view(
            "(deleted IS NULL OR not deleted) AND "
            "(is_file_item OR rd.id IS NOT NULL) AND "
            "(parent_id IS NOT NULL or feed.origURL != 'dtv:singleFeed') AND "
            "item.file_type='other'",
            joins={'feed': 'item.feed_id=feed.id',
                   'remote_downloader as rd': 'rd.main_item_id=item.id'})

    @classmethod
    def feed_expiring_view(cls, feed_id, watched_before):
        return cls.make_view("watchedTime is not NULL AND "
                "watchedTime < ? AND feed_id = ? AND keep = 0",
                (watched_before, feed_id),
                joins={'feed': 'item.feed_id=feed.id'})

    @classmethod
    def latest_in_feed_view(cls, feed_id):
        return cls.make_view("feed_id=?", (feed_id,),
                order_by='releaseDateObj DESC', limit=1)

    @classmethod
    def media_children_view(cls, parent_id):
        return cls.make_view("parent_id=? AND "
                "file_type IN ('video', 'audio')", (parent_id,))

    @classmethod
    def containers_view(cls):
        return cls.make_view("isContainerItem")

    @classmethod
    def file_items_view(cls):
        return cls.make_view("is_file_item")

    @classmethod
    def orphaned_from_feed_view(cls):
        return cls.make_view('feed_id IS NOT NULL AND '
                'feed_id NOT IN (SELECT id from feed)')

    @classmethod
    def orphaned_from_parent_view(cls):
        return cls.make_view('parent_id IS NOT NULL AND '
                'parent_id NOT IN (SELECT id from item)')

    @classmethod
    def update_folder_trackers(cls):
        """Update each view tracker that care's about the item's
        folder (both playlist and channel folders).
        """

        for tracker in app.view_tracker_manager.trackers_for_ddb_class(cls):
            # bit of a hack here.  We only need to update ViewTrackers
            # that care about the item's folder.  This seems like a
            # safe way to check if that's true.
            if 'folder_id' in tracker.where:
                tracker.check_all_objects()

    @classmethod
    def downloader_view(cls, dler_id):
        return cls.make_view("downloader_id=?", (dler_id,))

    def _look_for_downloader(self):
        self.set_downloader(downloader.lookup_downloader(self.get_url()))
        if self.has_downloader() and self.downloader.is_finished():
            self.set_filename(self.downloader.get_filename())

    getSelected, setSelected = make_simple_get_set(
        u'selected', change_needs_save=False)
    getActive, setActive = make_simple_get_set(
        u'active', change_needs_save=False)

    def _find_child_paths(self):
        """If this item points to a directory, return the set all files
        under that directory.
        """
        filename_root = self.get_filename()
        if fileutil.isdir(filename_root):
            return set(fileutil.miro_allfiles(filename_root))
        else:
            return set()

    def _make_new_children(self, paths):
        filename_root = self.get_filename()
        if filename_root is None:
            logging.error("Item._make_new_children: get_filename here is None")
            return
        for path in paths:
            assert path.startswith(filename_root)
            offsetPath = path[len(filename_root):]
            while offsetPath[0] in ('/', '\\'):
                offsetPath = offsetPath[1:]
            FileItem(path, parent_id=self.id, offsetPath=offsetPath)

    def find_new_children(self):
        """If this feed is a container item, walk through its
        directory and find any new children.  Returns True if it found
        children and ran signal_change().
        """
        if not self.isContainerItem:
            return False
        if self.get_state() == 'downloading':
            # don't try to find videos that we're in the middle of
            # re-downloading
            return False
        child_paths = self._find_child_paths()
        for child in self.get_children():
            child_paths.discard(child.get_filename())
        self._make_new_children(child_paths)
        if child_paths:
            self.signal_change()
            return True
        return False

    def split_item(self):
        """returns True if it ran signal_change()"""
        if self.isContainerItem is not None:
            return self.find_new_children()
        if ((not isinstance(self, FileItem)
             and (self.downloader is None
                  or not self.downloader.is_finished()))):
            return False
        filename_root = self.get_filename()
        if filename_root is None:
            return False
        if fileutil.isdir(filename_root):
            child_paths = self._find_child_paths()
            if len(child_paths) > 0:
                self.isContainerItem = True
                self._make_new_children(child_paths)
            else:
                if not self.get_feed_url().startswith ("dtv:directoryfeed"):
                    target_dir = app.config.get(prefs.NON_VIDEO_DIRECTORY)
                    if not filename_root.startswith(target_dir):
                        if isinstance(self, FileItem):
                            self.migrate (target_dir)
                        else:
                            self.downloader.migrate (target_dir)
                self.isContainerItem = False
        else:
            self.isContainerItem = False
        self.signal_change()
        return True

    def set_subtitle_encoding(self, encoding):
        if encoding is not None:
            self.subtitle_encoding = unicode(encoding)
            config_value = encoding
        else:
            self.subtitle_encoding = None
            config_value = ''
        app.config.set(prefs.SUBTITLE_ENCODING, config_value)
        self.signal_change()

    def set_filename(self, filename):
        self.filename = filename
        if not self.media_type_checked:
            self.file_type = self._file_type_for_filename(filename)

    def set_file_type(self, file_type):
        self.file_type = file_type
        self.signal_change()

    def _file_type_for_filename(self, filename):
        filename = filename.lower()
        for ext in filetypes.VIDEO_EXTENSIONS:
            if filename.endswith(ext):
                return u'video'
        for ext in filetypes.AUDIO_EXTENSIONS:
            if filename.endswith(ext):
                return u'audio'
        return u'other'

    def matches_search(self, search_string):
        if search_string is None:
            return True
        search_string = search_string.lower()
        title = self.get_title() or u''
        desc = self.get_description() or u''
        if self.get_filename():
            filename = filename_to_unicode(self.get_filename())
        else:
            filename = u''
        if search.match(search_string, [title.lower(), desc.lower(),
                                       filename.lower()]):
            return True
        else:
            return False

    def _remove_from_playlists(self):
        models.PlaylistItemMap.remove_item_from_playlists(self)
        models.PlaylistFolderItemMap.remove_item_from_playlists(self)

    def check_constraints(self):
        if self.feed_id is not None:
            try:
                obj = models.Feed.get_by_id(self.feed_id)
            except ObjectNotFoundError:
                raise DatabaseConstraintError(
                    "my feed (%s) is not in database" % self.feed_id)
            else:
                if not isinstance(obj, models.Feed):
                    msg = "feed_id points to a %s instance" % obj.__class__
                    raise DatabaseConstraintError(msg)
        if self.has_parent():
            try:
                obj = Item.get_by_id(self.parent_id)
            except ObjectNotFoundError:
                raise DatabaseConstraintError(
                    "my parent (%s) is not in database" % self.parent_id)
            else:
                if not isinstance(obj, Item):
                    msg = "parent_id points to a %s instance" % obj.__class__
                    raise DatabaseConstraintError(msg)
                # If isContainerItem is None, we may be in the middle
                # of building the children list.
                if obj.isContainerItem is not None and not obj.isContainerItem:
                    msg = "parent_id is not a containerItem"
                    raise DatabaseConstraintError(msg)
        if self.parent_id is None and self.feed_id is None:
            raise DatabaseConstraintError("feed_id and parent_id both None")
        if self.parent_id is not None and self.feed_id is not None:
            raise DatabaseConstraintError(
                "feed_id and parent_id both not None")

    def on_signal_change(self):
        self.expiring = None
        self._sync_title()
        if hasattr(self, "_state"):
            del self._state
        if hasattr(self, "_size"):
            del self._size

    def _sync_title(self):
        # for torrents that aren't from a feed, we use the filename
        # as the title.
        if ((self.is_external()
             and self.has_downloader()
             and self.downloader.get_type() == "bittorrent"
             and self.downloader.get_state() == "downloading")):
            filename = os.path.basename(self.downloader.get_filename())
            if self.title != filename:
                self.set_title(filename_to_unicode(filename))

    def recalc_feed_counts(self):
        self.get_feed().recalc_counts()

    def get_viewed(self):
        """Returns True iff this item has never been viewed in the
        interface.

        Note the difference between "viewed" and seen.
        """
        try:
            # optimizing by trying the cached feed
            return self._feed.last_viewed >= self.creationTime
        except AttributeError:
            return self.get_feed().last_viewed >= self.creationTime

    @returns_unicode
    def get_url(self):
        """Returns the URL associated with the first enclosure in the
        item.
        """
        return self.url

    def has_shareable_url(self):
        """Does this item have a URL that the user can share with
        others?

        This returns True when the item has a non-file URL.
        """
        url = self.get_url()
        return url != u'' and not url.startswith(u"file:")

    def get_feed(self):
        """Returns the feed this item came from.
        """
        try:
            return self._feed
        except AttributeError:
            pass

        if self.feed_id is not None:
            self._feed = models.Feed.get_by_id(self.feed_id)
        elif self.has_parent():
            self._feed = self.get_parent().get_feed()
        else:
            self._feed = None
        return self._feed

    def get_parent(self):
        if hasattr(self, "_parent"):
            return self._parent

        if self.has_parent():
            self._parent = Item.get_by_id(self.parent_id)
        else:
            self._parent = self
        return self._parent

    @returns_unicode
    def get_feed_url(self):
        return self.get_feed().origURL

    @returns_unicode
    def get_source(self):
        if self.feed_id is not None:
            feed_ = self.get_feed()
            if feed_.origURL != 'dtv:manualFeed':
                return feed_.get_title()
        if self.has_parent():
            try:
                return self.get_parent().get_title()
            except ObjectNotFoundError:
                return None
        return None

    def get_children(self):
        if self.isContainerItem:
            return Item.children_view(self.id)
        else:
            raise ValueError("%s is not a container item" % self)

    def children_signal_change(self):
        for child in self.get_children():
            child.signal_change(needs_save=False)

    def is_playable(self):
        """Is this a playable item?"""

        if self.isContainerItem:
            return Item.media_children_view(self.id).count() > 0
        else:
            return self.file_type in ('audio', 'video')

    def set_feed(self, feed_id):
        """Moves this item to another feed.
        """
        self.feed_id = feed_id
        # _feed is created by get_feed which caches the result
        if hasattr(self, "_feed"):
            del self._feed
        if self.isContainerItem:
            for item in self.get_children():
                if hasattr(item, "_feed"):
                    del item._feed
                item.signal_change()
        self.signal_change()

    def expire(self):
        self.confirm_db_thread()
        self._remove_from_playlists()
        if not self.is_external():
            self.delete_files()
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
                if self.isContainerItem:
                    for item in self.get_children():
                        item.make_deleted()
                elif self.get_filename():
                    FileItem(self.get_filename(), feed_id=self.feed_id,
                             parent_id=self.parent_id, deleted=True)
                if self.has_downloader():
                    self.downloader.set_delete_files(False)
            self.remove()
        else:
            self.expired = True
            self.seen = self.keep = self.pendingManualDL = False
            self.filename = None
            self.file_type = self.watchedTime = self.duration = None
            self.isContainerItem = None
            self.signal_change()
        self.recalc_feed_counts()

    def has_downloader(self):
        return self.downloader_id is not None and self.downloader is not None

    def has_parent(self):
        return self.parent_id is not None

    def is_main_item(self):
        return (self.has_downloader() and
                self.downloader.main_item_id == self.id)

    def downloader_state(self):
        if not self.has_downloader():
            return None
        else:
            return self.downloader.state

    def stop_upload(self):
        if self.downloader:
            self.downloader.stop_upload()
            if self.isContainerItem:
                self.children_signal_change()

    def pause_upload(self):
        if self.downloader:
            self.downloader.pause_upload()
            if self.isContainerItem:
                self.children_signal_change()

    def start_upload(self):
        if self.downloader:
            self.downloader.start_upload()
            if self.isContainerItem:
                self.children_signal_change()

    def get_expiration_time(self):
        """Returns the time when this item should expire.

        Returns a datetime.datetime object or None if it doesn't expire.
        """
        self.confirm_db_thread()
        if self.get_watched_time() is None or not self.is_downloaded():
            return None
        if self.keep:
            return None
        ufeed = self.get_feed()
        if ufeed.expire == u'never' or (ufeed.expire == u'system'
                and app.config.get(prefs.EXPIRE_AFTER_X_DAYS) <= 0):
            return None
        else:
            if ufeed.expire == u"feed":
                expire_time = ufeed.expireTime
            elif ufeed.expire == u"system":
                expire_time = timedelta(
                    days=app.config.get(prefs.EXPIRE_AFTER_X_DAYS))
            return self.get_watched_time() + expire_time

    def get_watched_time(self):
        """Returns the most recent watched time of this item or any
        of its child items.

        Returns a datetime.datetime instance or None if the item and none
        of its children have been watched.
        """
        if not self.get_seen():
            return None
        if self.isContainerItem and self.watchedTime == None:
            self.watchedTime = datetime.min
            for item in self.get_children():
                child_time = item.get_watched_time()
                if child_time is None:
                    self.watchedTime = None
                    return None
                if child_time > self.watchedTime:
                    self.watchedTime = child_time
            self.signal_change()
        return self.watchedTime

    def get_expiring(self):
        if self.expiring is None:
            if not self.get_seen():
                self.expiring = False
            elif self.keep:
                self.expiring = False
            else:
                ufeed = self.get_feed()
                if ufeed.expire == u'never':
                    self.expiring = False
                elif (ufeed.expire == u'system'
                      and app.config.get(prefs.EXPIRE_AFTER_X_DAYS) <= 0):
                    self.expiring = False
                else:
                    self.expiring = True
        return self.expiring

    def get_seen(self):
        """Returns true iff video has been seen.

        Note the difference between "viewed" and "seen".
        """
        self.confirm_db_thread()
        return self.seen

    def mark_item_seen(self, mark_other_items=True):
        """Marks the item as seen.
        """
        self.confirm_db_thread()
        if self.isContainerItem:
            for child in self.get_children():
                child.seen = True
                child.signal_change()
        if self.seen == False:
            self.seen = True
            if self.subtitle_encoding is None:
                config_value = app.config.get(prefs.SUBTITLE_ENCODING)
                if config_value:
                    self.subtitle_encoding = unicode(config_value)
            if self.watchedTime is None:
                self.watchedTime = datetime.now()
            self.signal_change()
            self.update_parent_seen()
            if mark_other_items and self.downloader:
                for item in self.downloader.item_list:
                    if item != self:
                        item.mark_item_seen(False)
            self.recalc_feed_counts()

    def update_parent_seen(self):
        if self.parent_id:
            unseen_children = self.make_view('parent_id=? AND NOT seen AND '
                    "file_type in ('audio', 'video')", (self.parent_id,))
            new_seen = (unseen_children.count() == 0)
            parent = self.get_parent()
            if parent.seen != new_seen:
                parent.seen = new_seen
                parent.signal_change()

    def mark_item_unseen(self, mark_other_items=True):
        self.confirm_db_thread()
        if self.isContainerItem:
            for item in self.get_children():
                item.seen = False
                item.signal_change()
        if self.seen:
            self.seen = False
            self.watchedTime = None
            self.resumeTime = 0
            self.signal_change()
            self.update_parent_seen()
            if mark_other_items and self.downloader:
                for item in self.downloader.item_list:
                    if item != self:
                        item.mark_item_unseen(False)
            self.recalc_feed_counts()

    @returns_unicode
    def get_rss_id(self):
        self.confirm_db_thread()
        return self.rss_id

    def remove_rss_id(self):
        self.confirm_db_thread()
        self.rss_id = None
        self.signal_change()

    def set_auto_downloaded(self, autodl=True):
        self.confirm_db_thread()
        if autodl != self.autoDownloaded:
            self.autoDownloaded = autodl
            self.signal_change()

    @eventloop.as_idle
    def set_resume_time(self, position):
        if not self.id_exists():
            return
        try:
            position = int(position)
        except TypeError:
            logging.exception("set_resume_time: not-saving!  given non-int %s",
                              position)
            return
        if self.resumeTime != position:
            self.resumeTime = position
            self.signal_change()

    def get_auto_downloaded(self):
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
                manual_dl_count >= app.config.get(prefs.MAX_MANUAL_DOWNLOADS)):
            self.pendingManualDL = True
            self.pendingReason = _("queued for download")
            self.signal_change()
            return
        else:
            self.set_auto_downloaded(autodl)
            self.pendingManualDL = False

        dler = downloader.get_downloader_for_item(self)
        if dler is not None:
            self.set_downloader(dler)
            self.downloader.set_channel_name(
                unicode_to_filename(self.get_channel_title(True)))
            if self.downloader.is_finished():
                self.on_download_finished()
            else:
                self.downloader.start()
        self.signal_change()
        self.recalc_feed_counts()

    def pause(self):
        if self.downloader:
            self.downloader.pause()

    def resume(self):
        self.download(self.get_auto_downloaded())

    def is_pending_manual_download(self):
        self.confirm_db_thread()
        return self.pendingManualDL

    def cancel_auto_download(self):
        # FIXME - this is cheating and abusing the was_downloaded flag
        self.was_downloaded = True
        self.signal_change()
        self.recalc_feed_counts()

    def is_eligible_for_auto_download(self):
        self.confirm_db_thread()
        if self.was_downloaded:
            return False
        ufeed = self.get_feed()
        if ufeed.getEverything:
            return True
        return self.eligibleForAutoDownload

    def is_pending_auto_download(self):
        return (self.get_feed().is_autodownloadable() and
                self.is_eligible_for_auto_download())

    @returns_unicode
    def get_thumbnail_url(self):
        return self.thumbnail_url

    @returns_filename
    def get_thumbnail(self):
        """NOTE: When changing this function, change feed.icon_changed
        to signal the right set of items.
        """
        self.confirm_db_thread()
        if self.icon_cache is not None and self.icon_cache.isValid():
            path = self.icon_cache.get_filename()
            return resources.path(fileutil.expand_filename(path))
        elif self.screenshot:
            path = self.screenshot
            return resources.path(fileutil.expand_filename(path))
        elif self.isContainerItem:
            return resources.path("images/thumb-default-folder.png")
        else:
            feed = self.get_feed()
            if feed.thumbnail_valid():
                return feed.get_thumbnail_path()
            elif (self.get_filename()
                  and filetypes.is_audio_filename(self.get_filename())):
                return resources.path("images/thumb-default-audio.png")
            else:
                return resources.path("images/thumb-default-video.png")

    def is_downloaded_torrent(self):
        return (self.isContainerItem and self.has_downloader() and
                self.downloader.is_finished())

    @returns_unicode
    def get_title(self):
        """Returns the title of the item.
        """
        if self.title:
            return self.title
        if self.is_external() and self.is_downloaded_torrent():
            if self.get_filename() is not None:
                basename = os.path.basename(self.get_filename())
                return filename_to_unicode(basename + os.path.sep)
        if self.entry_title is not None:
            return self.entry_title
        return _('no title')

    def set_title(self, title):
        self.confirm_db_thread()
        self.title = title
        self.signal_change()

    def set_description(self, desc):
        self.confirm_db_thread()
        self.description = desc
        self.signal_change()

    def set_channel_title(self, title):
        check_u(title)
        self.channelTitle = title
        self.signal_change()

    @returns_unicode
    def get_channel_title(self, allowSearchFeedTitle=False):
        implClass = self.get_feed().actualFeed.__class__
        if implClass in (models.RSSFeedImpl, models.ScraperFeedImpl):
            return self.get_feed().get_title()
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

    @returns_unicode
    def get_description(self):
        """Returns the description of the video (unicode).

        If the item is a torrent, then it adds some additional text.
        """
        if self.description:
            if self.is_downloaded_torrent():
                return (unicode(self.description) + u'<BR>' +
                        _('Contents appear in the library'))
            else:
                return unicode(self.description)

        if self.entry_description:
            if self.is_downloaded_torrent():
                return (unicode(self.entry_description) + u'<BR>' +
                        _('Contents appear in the library'))
            else:
                return unicode(self.entry_description)
        if self.is_external() and self.is_downloaded_torrent():
            lines = [_('Contents:')]
            lines.extend(filename_to_unicode(child.offsetPath)
                         for child in self.get_children())
            return u'<BR>\n'.join(lines)

        return u''

    def looks_like_torrent(self):
        """Returns true if we think this item is a torrent.  (For items that
        haven't been downloaded this uses the file extension which isn't
        totally reliable).
        """

        if self.has_downloader():
            return self.downloader.get_type() == u'bittorrent'
        else:
            return filetypes.is_torrent_filename(self.get_url())

    def torrent_seeding_status(self):
        """Get the torrent seeding status for this torrent.

        Possible values:

           None - Not part of a downloaded torrent
           'seeding' - Part of a torrent that we're seeding
           'stopped' - Part of a torrent that we've stopped seeding
        """

        downloader_ = self.downloader
        if downloader_ is None and self.has_parent():
            downloader_ = self.get_parent().downloader
        if downloader_ is None or downloader_.get_type() != u'bittorrent':
            return None
        if downloader_.get_state() == 'uploading':
            return 'seeding'
        else:
            return 'stopped'

    def is_transferring(self):
        return (self.downloader
                and self.downloader.get_state() in (u'uploading',
                                                    u'downloading'))

    def delete_files(self):
        """Stops downloading the item.
        """
        self.confirm_db_thread()
        if self.has_downloader():
            self.set_downloader(None)
        if self.isContainerItem:
            for item in self.get_children():
                item.delete_files()
                item.remove()
        self.delete_subtitle_files()

    def delete_subtitle_files(self):
        """Deletes subtitle files associated with this item.
        """
        files = util.gather_subtitle_files(self.get_filename())
        for mem in files:
            fileutil.delete(mem)

    def get_state(self):
        """Get the state of this item.  The state will be on of the
        following:

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

    @returns_unicode
    def _calc_state(self):
        """Recalculate the state of an item after a change
        """
        self.confirm_db_thread()
        # FIXME, 'failed', and 'paused' should get download icons.
        # The user should be able to restart or cancel them (put them
        # into the stopped state).
        if (self.downloader is None  or
                self.downloader.get_state() in (u'failed', u'stopped')):
            if self.pendingManualDL:
                self._state = u'downloading'
            elif self.expired:
                self._state = u'expired'
            elif (self.get_viewed() or
                    (self.downloader and
                        self.downloader.get_state() in (u'failed',
                                                        u'stopped'))):
                self._state = u'not-downloaded'
            else:
                self._state = u'new'
        elif self.downloader.get_state() in (u'offline', u'paused'):
            if self.pendingManualDL:
                self._state = u'downloading'
            else:
                self._state = u'paused'
        elif not self.downloader.is_finished():
            self._state = u'downloading'
        elif not self.get_seen():
            self._state = u'newly-downloaded'
        elif self.get_expiring():
            self._state = u'expiring'
        else:
            self._state = u'saved'

    @returns_unicode
    def get_channel_category(self):
        """Get the category to use for the channel template.

        This method is similar to get_state(), but has some subtle
        differences.  get_state() is used by the download-item
        template and is usually more useful to determine what's
        actually happening with an item.  get_channel_category() is
        used by by the channel template to figure out which heading to
        put an item under.

        * downloading and not-downloaded are grouped together as
          not-downloaded
        * Newly downloaded and downloading items are always new if
          their feed hasn't been marked as viewed after the item's pub
          date.  This is so that when a user gets a list of items and
          starts downloading them, the list doesn't reorder itself.
          Once they start watching them, then it reorders itself.
        """

        self.confirm_db_thread()
        if self.downloader is None or not self.downloader.is_finished():
            if not self.get_viewed():
                return u'new'
            if self.expired:
                return u'expired'
            else:
                return u'not-downloaded'
        elif not self.get_seen():
            if not self.get_viewed():
                return u'new'
            return u'newly-downloaded'
        elif self.get_expiring():
            return u'expiring'
        else:
            return u'saved'

    def is_uploading(self):
        """Returns true if this item is currently uploading.  This
        only happens for torrents.
        """
        return self.downloader and self.downloader.get_state() == u'uploading'

    def is_uploading_paused(self):
        """Returns true if this item is uploading but paused.  This
        only happens for torrents.
        """
        return (self.downloader
                and self.downloader.get_state() == u'uploading-paused')

    def is_downloadable(self):
        return self.get_state() in (u'new', u'not-downloaded', u'expired')

    def is_downloaded(self):
        return self.get_state() in (u"newly-downloaded", u"expiring", u"saved")

    def show_save_button(self):
        return (self.get_state() in (u'newly-downloaded', u'expiring')
                and not self.keep)

    def get_size_for_display(self):
        """Returns the size of the item to be displayed.
        """
        return util.format_size_for_user(self.get_size())

    def get_size(self):
        if not hasattr(self, "_size"):
            self._size = self._get_size()
        return self._size

    def _get_size(self):
        """Returns the size of the item. We use the following methods
        to get the size:

        1. Physical size of a downloaded file
        2. HTTP content-length
        3. RSS enclosure tag value
        """
        if self.is_downloaded():
            if self.get_filename() is None:
                return 0
            try:
                fname = self.get_filename()
                return os.path.getsize(fname)
            except OSError:
                return 0
        elif self.has_downloader():
            return self.downloader.get_total_size()
        else:
            if self.enclosure_size is not None:
                return self.enclosure_size
        return 0

    def download_progress(self):
        """Returns the download progress in absolute percentage [0.0 -
        100.0].
        """
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

    @returns_unicode
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
        """Returns the date this video was released or when it was
        published.
        """
        return self.releaseDateObj

    def get_duration_value(self):
        """Returns the length of the video in seconds.
        """
        secs = 0
        if self.duration not in (-1, None):
            secs = self.duration / 1000
        return secs

    @returns_unicode
    def get_format(self, empty_for_unknown=True):
        """Returns string with the format of the video.
        """
        if self.looks_like_torrent():
            return u'.torrent'

        if self.downloader:
            if ((self.downloader.contentType
                 and "/" in self.downloader.contentType)):
                mtype, subtype = self.downloader.contentType.split('/', 1)
                mtype = mtype.lower()
                if mtype in KNOWN_MIME_TYPES:
                    format_ = subtype.split(';')[0].upper()
                    if mtype == u'audio':
                        format_ += u' AUDIO'
                    if format_.startswith(u'X-'):
                        format_ = format_[2:]
                    return (u'.%s' %
                            MIME_SUBSITUTIONS.get(format_, format_).lower())

        if self.enclosure_format is not None:
            return self.enclosure_format

        if empty_for_unknown:
            return u""
        return u"unknown"

    @returns_unicode
    def get_license(self):
        """Return the license associated with the video.
        """
        self.confirm_db_thread()
        if self.license:
            return self.license
        return self.get_feed().get_license()

    @returns_unicode
    def get_comments_link(self):
        """Returns the comments link if it exists in the feed item.
        """
        return self.comments_link

    def get_link(self):
        """Returns the URL of the webpage associated with the item.
        """
        return self.link

    def get_payment_link(self):
        """Returns the URL of the payment page associated with the
        item.
        """
        return self.payment_link

    def update(self, entry):
        """Updates an item with new data

        entry - dict containing the new data
        """
        self.update_from_feed_parser_values(FeedParserValues(entry))

    def update_from_feed_parser_values(self, fp_values):
        fp_values.update_item(self)
        self.icon_cache.request_update()
        self.signal_change()

    def on_download_finished(self):
        """Called when the download for this item finishes."""

        self.confirm_db_thread()
        self.downloadedTime = datetime.now()
        self.set_filename(self.downloader.get_filename())
        self.split_item()
        self.signal_change()
        self._replace_file_items()
        self.check_media_file(signal_change=False)

        for other in Item.make_view('downloader_id IS NULL AND url=?',
                (self.url,)):
            other.set_downloader(self.downloader)
        self.recalc_feed_counts()

    def check_media_file(self, signal_change=True):
        if filetypes.is_other_filename(self.filename):
            self.file_type = u'other'
            self.media_type_checked = True
            if signal_change:
                self.signal_change()
        else:
            moviedata.movie_data_updater.request_update(self)

    def on_downloader_migrated(self, old_filename, new_filename):
        self.set_filename(new_filename)
        self.signal_change()
        if self.isContainerItem:
            self.migrate_children(self.get_filename())
        self._replace_file_items()

    def _replace_file_items(self):
        """Remove any FileItems that share our filename from the DB.

        This fixes a race condition during migrate, where we can create
        FileItems that duplicate existing Items.  See #12253 for details.
        """
        view = Item.make_view('is_file_item AND filename=? AND id !=?',
                (filename_to_unicode(self.filename), self.id))
        for dup in view:
            dup.remove()

    def set_downloader(self, new_downloader):
        if self.has_downloader():
            if new_downloader is self.downloader:
                return
            self.downloader.remove_item(self)
        # Note: this is the attribute--not the property!
        self._downloader = new_downloader
        if new_downloader is not None:
            self.downloader_id = new_downloader.id
            self.was_downloaded = True
            new_downloader.add_item(self)
        else:
            self.downloader_id = None
        self.signal_change()

    def save(self):
        self.confirm_db_thread()
        if self.keep != True:
            self.keep = True
            self.signal_change()

    @returns_filename
    def get_filename(self):
        return self.filename

    def is_video_file(self):
        return (self.isContainerItem != True
                and filetypes.is_video_filename(self.get_filename()))

    def is_audio_file(self):
        return (self.isContainerItem != True
                and filetypes.is_audio_filename(self.get_filename()))

    def is_external(self):
        """Returns True iff this item was not downloaded from a Democracy
        channel.
        """
        return (self.feed_id is not None
                and self.get_feed_url() == 'dtv:manualFeed')

    def migrate_children(self, newdir):
        if self.isContainerItem:
            for item in self.get_children():
                item.migrate(newdir)

    def remove(self):
        if self.has_downloader():
            self.set_downloader(None)
        self.remove_icon_cache()
        if self.isContainerItem:
            for item in self.get_children():
                item.remove()
        self._remove_from_playlists()
        app.item_info_cache.item_removed(self)
        DDBObject.remove(self)

    def setup_links(self):
        self.split_item()
        if not self.id_exists():
            # In split_item() we found out that all our children were
            # deleted, so we were removed as well.  (#11979)
            return
        eventloop.add_idle(self.check_deleted, 'checking item deleted')
        if self.screenshot and not fileutil.exists(self.screenshot):
            self.screenshot = None
            self.signal_change()

    def check_deleted(self):
        if not self.id_exists():
            return
        if (self.isContainerItem is not None and
                not fileutil.exists(self.get_filename()) and
                not hasattr(app, 'in_unit_tests')):
            self.expire()

    def _get_downloader(self):
        try:
            return self._downloader
        except AttributeError:
            dler = downloader.get_existing_downloader(self)
            if dler is not None:
                dler.add_item(self)
            self._downloader = dler
            return dler
    downloader = property(_get_downloader)

    def fix_incorrect_torrent_subdir(self):
        """Up to revision 6257, torrent downloads were incorrectly
        being created in an extra subdirectory.  This method migrates
        those torrent downloads to the correct layout.

        from: /path/to/movies/foobar.mp4/foobar.mp4
        to:   /path/to/movies/foobar.mp4
        """
        filename_path = self.get_filename()
        if filename_path is None:
            return
        if fileutil.isdir(filename_path):
            enclosed_file = os.path.join(filename_path,
                                        os.path.basename(filename_path))
            if fileutil.exists(enclosed_file):
                logging.info("Migrating incorrect torrent download: %s",
                             enclosed_file)
                try:
                    temp = filename_path + ".tmp"
                    fileutil.move(enclosed_file, temp)
                    for turd in os.listdir(fileutil.expand_filename(
                            filename_path)):
                        os.remove(turd)
                    fileutil.rmdir(filename_path)
                    fileutil.rename(temp, filename_path)
                except (SystemExit, KeyboardInterrupt):
                    raise
                except:
                    logging.warn("fix_incorrect_torrent_subdir error:\n%s",
                                 traceback.format_exc())
                self.set_filename(filename_path)

    def __str__(self):
        return "Item - %s" % stringify(self.get_title())

class FileItem(Item):
    """An Item that exists as a local file
    """
    def setup_new(self, filename, feed_id=None, parent_id=None,
            offsetPath=None, deleted=False, fp_values=None,
            channel_title=None, mark_seen=False):
        if fp_values is None:
            fp_values = fp_values_for_file(filename)
        Item.setup_new(self, fp_values, feed_id=feed_id, parent_id=parent_id,
                eligibleForAutoDownload=False, channel_title=channel_title)
        self.is_file_item = True
        check_f(filename)
        filename = fileutil.abspath(filename)
        self.set_filename(filename)
        self.set_release_date()
        self.deleted = deleted
        self.offsetPath = offsetPath
        self.shortFilename = clean_filename(os.path.basename(self.filename))
        self.was_downloaded = False
        if mark_seen:
            self.mark_seen = True
            self.watchedTime = datetime.now()
        if not fileutil.isdir(self.filename):
            # If our file isn't a directory, then we know we are definitely
            # not a container item.  Note that the opposite isn't true in the
            # case where we are a directory with only 1 file inside.
            self.isContainerItem = False
        self.check_media_file(signal_change=False)
        self.split_item()

    # FileItem downloaders are always None
    downloader = property(lambda self: None)

    @returns_unicode
    def get_state(self):
        if self.deleted:
            return u"expired"
        elif self.get_seen():
            return u"saved"
        else:
            return u"newly-downloaded"

    def is_eligible_for_auto_download(self):
        return False

    def get_channel_category(self):
        """Get the category to use for the channel template.

        This method is similar to get_state(), but has some subtle
        differences.  get_state() is used by the download-item
        template and is usually more useful to determine what's
        actually happening with an item.  get_channel_category() is
        used by by the channel template to figure out which heading to
        put an item under.

        * downloading and not-downloaded are grouped together as
          not-downloaded
        * Items are always new if their feed hasn't been marked as
          viewed after the item's pub date.  This is so that when a
          user gets a list of items and starts downloading them, the
          list doesn't reorder itself.
        * Child items match their parents for expiring, where in
          get_state, they always act as not expiring.
        """

        self.confirm_db_thread()
        if self.deleted:
            return u'expired'
        elif not self.get_seen():
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
        if self.has_parent():
            # if we can't find the parent, it's possible that it was
            # already deleted.
            try:
                old_parent = self.get_parent()
            except ObjectNotFoundError:
                old_parent = None
        else:
            old_parent = None
        if not fileutil.exists(self.filename):
            # item whose file has been deleted outside of Miro
            self.remove()
        elif self.has_parent():
            self.make_deleted()
        else:
            # external item that the user deleted in Miro
            url = self.get_feed_url()
            if ((url.startswith("dtv:manualFeed")
                 or url.startswith("dtv:singleFeed"))):
                self.remove()
            else:
                self.make_deleted()
        if old_parent is not None and old_parent.get_children().count() == 0:
            old_parent.expire()

    def make_deleted(self):
        self._remove_from_playlists()
        self.downloadedTime = None
        self.parent_id = None
        self.feed_id = models.Feed.get_manual_feed().id
        self.deleted = True
        self.signal_change()

    def delete_files(self):
        if self.has_parent():
            dler = self.get_parent().downloader
            if dler is not None and not dler.child_deleted:
                dler.stop_upload()
                dler.child_deleted = True
                dler.signal_change()
                for sibling in self.get_parent().get_children():
                    sibling.signal_change(needs_save=False)
        try:
            if fileutil.isfile(self.filename):
                fileutil.remove(self.filename)
            elif fileutil.isdir(self.filename):
                fileutil.rmtree(self.filename)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.warn("delete_files error:\n%s", traceback.format_exc())

    def download(self, autodl=False):
        self.deleted = False
        self.signal_change()

    def set_filename(self, filename):
        Item.set_filename(self, filename)

    def set_release_date(self):
        try:
            self.releaseDateObj = datetime.fromtimestamp(
                fileutil.getmtime(self.filename))
        except OSError:
            logging.warn("Error setting release date:\n%s",
                    traceback.format_exc())
            self.releaseDateObj = datetime.now()

    def get_release_date_obj(self):
        if self.parent_id:
            return self.get_parent().releaseDateObj
        else:
            return self.releaseDateObj

    def migrate(self, newdir):
        self.confirm_db_thread()
        if self.parent_id:
            parent = self.get_parent()
            self.filename = os.path.join(parent.get_filename(),
                                         self.offsetPath)
            self.signal_change()
            return
        if self.shortFilename is None:
            logging.warn("""\
can't migrate download because we don't have a shortFilename!
filename was %s""", stringify(self.filename))
            return
        new_filename = os.path.join(newdir, self.shortFilename)
        if self.filename == new_filename:
            return
        if fileutil.exists(self.filename):
            new_filename = next_free_filename(new_filename)
            def callback():
                self.filename = new_filename
                self.signal_change()
            fileutil.migrate_file(self.filename, new_filename, callback)
        elif fileutil.exists(new_filename):
            self.filename = new_filename
            self.signal_change()
        self.migrate_children(newdir)

    def setup_links(self):
        if self.shortFilename is None:
            if self.parent_id is None:
                self.shortFilename = clean_filename(
                    os.path.basename(self.filename))
            else:
                parent_file = self.get_parent().get_filename()
                if self.filename.startswith(parent_file):
                    self.shortFilename = clean_filename(
                        self.filename[len(parent_file):])
                else:
                    logging.warn("%s is not a subdirectory of %s",
                            self.filename, parent_file)
        Item.setup_links(self)

class DeviceItem(object):
    """
    An item which lives on a device.  There's a separate, per-device JSON
    database, so this implements the necessary Item logic for those files.
    """
    def __init__(self, **kwargs):
        for required in ('video_path', 'file_type', 'device'):
            if required not in kwargs:
                raise TypeError('DeviceItem must be given a "%s" argument'
                                % required)
        self.name = self.file_format = self.size = None
        self.id = self.release_date = self.feed_name = self.feed_id = None
        self.keep = self.media_type_checked = True
        self.updating_movie_info = self.isContainerItem = False
        self.url = self.payment_link = None
        self.comments_link = self.permalink = self.file_url = None
        self.license = self.downloader = self.release_date = None
        self.duration = self.screenshot = None
        self.resumeTime = 0
        self.subtitle_encoding = self.enclosure_type = None
        self.description = u''
        self.__dict__.update(kwargs)

        if self.name is None:
            self.name = os.path.basename(self.video_path)
        if self.file_format is None:
            self.file_format = os.path.splitext(self.video_path)[1]
        if self.size is None:
            self.size = os.path.getsize(self.get_filename())
        if self.release_date is None:
            self.release_date = os.path.getctime(self.get_filename())
        if self.duration is None: # -1 is unknown
            moviedata.movie_data_updater.request_update(self)

    @returns_unicode
    def get_title(self):
        return self.name or u''

    @returns_unicode
    def get_source(self):
        return self.device.info.name

    @staticmethod
    def id_exists():
        return True

    @staticmethod
    def get_feed_url():
        return None

    @returns_unicode
    def get_description(self):
        return self.description

    @staticmethod
    def get_state():
        return u'saved'

    @staticmethod
    def get_viewed():
        return True

    @staticmethod
    def is_downloaded():
        return True

    @staticmethod
    def is_external():
        return True

    def get_release_date_obj(self):
        return datetime.fromtimestamp(self.release_date)

    @staticmethod
    def get_seen():
        return True

    @staticmethod
    def is_playable():
        return True

    @staticmethod
    def looks_like_torrent():
        return False

    @staticmethod
    def torrent_seeding_status():
        return None

    def get_size(self):
        return self.size

    def get_duration_value(self):
        if self.duration in (-1, None):
            return 0
        return self.duration / 1000

    @returns_unicode
    def get_url(self):
        return self.url

    @returns_unicode
    def get_link(self):
        return self.permalink

    @returns_unicode
    def get_comments_link(self):
        return self.comments_link

    @returns_unicode
    def get_payment_link(self):
        return self.payment_link

    def has_shareable_url(self):
        return bool(self.get_url)

    @staticmethod
    def show_save_button():
        return False

    @staticmethod
    def is_pending_manual_download():
        return False

    @staticmethod
    def is_pending_auto_download():
        return False

    @returns_filename
    def get_filename(self):
        return utf8_to_filename(os.path.join(self.device.mount,
                                             self.video_path).encode('utf8'))

    @returns_filename
    def get_thumbnail(self):
        if self.screenshot:
            return utf8_to_filename(
                os.path.join(self.device.mount,
                             self.screenshot).encode('utf8'))
        elif self.file_type == 'audio':
            return resources.path("images/thumb-default-audio.png")
        else:
            return resources.path("images/thumb-default-video.png")

    @staticmethod
    def get_thumbnail_url():
        return u''

    @returns_unicode
    def get_format(self):
        return self.file_format

    @returns_unicode
    def get_license(self):
        return self.license

    def signal_change(self):
        if self.screenshot and self.screenshot.startswith(
            moviedata.thumbnail_directory()):
            # migrate the screenshot onto the device
            basename = os.path.basename(self.screenshot)
            shutil.move(self.screenshot,
                        os.path.join(self.device.mount, '.miro', basename))
            self.screenshot = os.path.join('.miro', basename)

        for index, data in enumerate(self.device.database[self.file_type]):
            if data['video_path'] == self.video_path:
                self.device.database[self.file_type][index] = self.to_dict()

        from miro import devices
        devices.write_database(self.device.mount, self.device.database)

        from miro import messages
        message = messages.ItemsChanged('device', self.device.id,
                                        [], [messages.ItemInfo(self)], [])
        message.send_to_frontend()

    def to_dict(self):
        data = {}
        for k, v in self.__dict__.items():
            if v is not None and k not in ('device', 'file_type'):
                data[k] = v
        return data

def fp_values_for_file(filename, title=None, description=None):
    data = {
            'enclosures': [{'url': resources.url(filename)}]
    }
    if title is None:
        data['title'] = filename_to_unicode(os.path.basename(filename))
    else:
        data['title'] = title
    if description is not None:
        data['description'] = description
    return FeedParserValues(FeedParserDict(data))

def update_incomplete_movie_data():
    IncompleteMovieDataUpdator()
    # this will stay around because it connects to the movie data updater's
    # signal.  Once it disconnects from the signal, we clean it up

class IncompleteMovieDataUpdator(object):
    def __init__(self):
        self.do_some_updates()
        self.done = False
        self.handle = moviedata.movie_data_updater.connect('queue-empty',
                self.on_queue_empty)

    def do_some_updates(self):
        chunk = list(Item.next_10_incomplete_movie_data_view())
        if chunk:
            for item in chunk:
                print 'checking: ', item
                item.check_media_file()
        else:
            self.done = True

    def on_queue_empty(self, movie_data_updator):
        if self.done:
            movie_data_updator.disconnect(self.handle)
        else:
            eventloop.add_idle(self.do_some_updates,
                    'update incomplete movie data')

def fix_non_container_parents():
    """Make sure all items referenced by parent_id have isContainerItem set

    Bug #12906 has a database where this was not so.
    """
    where_sql = ("(isContainerItem = 0 OR isContainerItem IS NULL) AND "
            "id IN (SELECT parent_id FROM item)")
    for item in Item.make_view(where_sql):
        logging.warn("parent_id points to %s but isContainerItem == %r. "
                "Setting isContainerItem to True", item.id,
                item.isContainerItem)
        item.isContainerItem = True
        item.signal_change()

def move_orphaned_items():
    manual_feed = models.Feed.get_manual_feed()
    feedless_items = []
    parentless_items = []

    for item in Item.orphaned_from_feed_view():
        logging.warn("No feed for Item: %s.  Moving to manual", item.id)
        item.set_feed(manual_feed.id)
        feedless_items.append('%s: %s' % (item.id, item.url))

    for item in Item.orphaned_from_parent_view():
        logging.warn("No parent for Item: %s.  Moving to manual", item.id)
        item.parent_id = None
        item.set_feed(manual_feed.id)
        parentless_items.append('%s: %s' % (item.id, item.url))

    if feedless_items:
        databaselog.info("Moved items to manual feed because their feed was "
                "gone: %s", ', '.join(feedless_items))
    if parentless_items:
        databaselog.info("Moved items to manual feed because their parent was "
                "gone: %s", ', '.join(parentless_items))

