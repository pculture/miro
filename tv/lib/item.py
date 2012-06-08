# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

import collections
from datetime import datetime, timedelta
import locale
import os.path
import traceback
import logging
import re
import shutil
import time

from miro.gtcache import gettext as _
from miro.util import (check_u, returns_unicode, check_f, returns_filename,
                       quote_unicode_url, stringify, get_first_video_enclosure,
                       entity_replace)
from miro.plat.utils import (filename_to_unicode, unicode_to_filename,
                             utf8_to_filename)

from miro.download_utils import (clean_filename, next_free_filename,
        next_free_directory)

from miro.database import (DDBObject, ObjectNotFoundError,
                           DatabaseConstraintError)
from miro.databasehelper import make_simple_get_set
from miro import app
from miro import httpclient
from miro import iconcache
from miro import databaselog
from miro import downloader
from miro import eventloop
from miro import prefs
from miro.plat import resources
from miro import util
from miro import filetypes
from miro import messages
from miro import searchengines
from miro import fileutil
from miro import signals
from miro import search
from miro import models
from miro import metadata

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

# We don't mdp_state as of version 5.0, but we need to set this for
# DeviceItems so that older versions can read the device DB
MDP_STATE_RAN = 1

def _check_for_image(path, element):
    """Given an element (which is really a dict), traverses
    the path in the element and if that turns out to be an image,
    then it returns True.

    Otherwise it returns False.
    """
    for part in path:
        try:
            element = element[part]
        except (KeyError, TypeError):
            return False
    if ((isinstance(element, basestring)
         and element.endswith((".jpg", ".jpeg", ".png", ".gif")))):
        return True
    return False

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
            'release_date': self._calc_release_date(),
        }

    def update_item(self, item):
        for key, value in self.data.items():
            setattr(item, key, value)
        item.calc_title()

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
            title = entity_replace(self.entry.title)
            # Strip tags from the title.
            p = re.compile('<.*?>')
            return p.sub('', title)

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
        if "enclosures" in self.entry:
            for enclosure in self.entry["enclosures"]:
                url = self._get_element_thumbnail(enclosure)
                if url is not None:
                    return url

        # Try to get the thumbnail for our entry
        return self._get_element_thumbnail(self.entry)

    def _get_element_thumbnail(self, element):
        # handles <thumbnail><href>http:...
        if _check_for_image(("thumbnail", "href"), element):
            return element["thumbnail"]["href"]
        if _check_for_image(("thumbnail",), element):
            return element["thumbnail"]

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
            return self.first_video_enclosure.payment_url.decode(
                'ascii', 'replace')
        except (AttributeError, UnicodeDecodeError):
            try:
                return self.entry.payment_url.decode('ascii','replace')
            except (AttributeError, UnicodeDecodeError):
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
        # FIXME - this is awful.  need to handle site-specific things
        # a different way.
        release_date = None

        # if this is not a youtube url, then we try to use
        # updated_parsed from either the enclosure or the entry
        if "youtube.com" not in self._calc_url():
            try:
                release_date = self.first_video_enclosure.updated_parsed
            except AttributeError:
                try:
                    release_date = self.entry.updated_parsed
                except AttributeError:
                    pass

        # if this is a youtube url and/or there was no updated_parsed,
        # then we try to use the published_parsed from either the
        # enclosure or the entry
        if release_date is None:
            try:
                release_date = self.first_video_enclosure.published_parsed
            except AttributeError:
                try:
                    release_date = self.entry.published_parsed
                except AttributeError:
                    pass

        if release_date is not None:
            return datetime(*release_date[0:7])

        return datetime.min

class FileFeedParserValues(FeedParserValues):
    """FeedParserValues for FileItems"""
    def __init__(self, filename, title=None, description=None):
        self.first_video_enclosure = {'url': resources.url(filename)}
        if title is None:
            title = filename_to_title(filename)
        if description is None:
            description = u''
        self.data = {
            'license': None,
            'rss_id': None,
            'entry_title': title,
            'thumbnail_url': None,
            'entry_description': description,
            'link': u'',
            'payment_link': u'',
            'comments_link': u'',
            'url': resources.url(filename),
            'enclosure_size': None,
            'enclosure_type': None,
            'enclosure_format': self._calc_enclosure_format(),
            'release_date': datetime.min,
        }

class _ItemsForPathCountTracker(object):
    """Helps Item implement have_item_for_path

    This class tracks how many items we have for a given path.  It's optimized
    pretty agressively.  We call it many times when importing new files.
    """

    def get_count(self, path):
        try:
            counts = self.count_for_paths
        except AttributeError:
            counts = self._init_counts_for_paths()
        return counts[self._count_key(path)]

    def _init_counts_for_paths(self):
        # Use a raw DB query for this one, since we want to be as fast as
        # possible
        counts = collections.defaultdict(int)
        app.db.cursor.execute("SELECT lower(filename), COUNT(*) "
                              "FROM item "
                              "GROUP BY filename")
        counts.update(app.db.cursor)
        self.count_for_paths = counts
        return counts

    def _count_key(self, path):
        # normalize paths so that they match whats in the database, and work
        # case-insensitively
        return filename_to_unicode(path).lower()

    def reset(self):
        try:
            del self.count_for_paths
        except AttributeError:
            pass

    def add_item(self, item):
        if item.filename is None:
            return
        try:
            self.count_for_paths[self._count_key(item.filename)] += 1
        except AttributeError:
            return # counts not created yet we can just ignore

    def remove_item(self, item):
        if item.filename is None:
            return
        try:
            self.count_for_paths[self._count_key(item.filename)] -= 1
        except AttributeError:
            return # counts not created yet we can just ignore

class ItemChangeTracker(object):
    """Tracks changes to items and send the ItemsChanged message."""
    def __init__(self):
        self.reset()
        app.db.connect('transaction-finished', self.on_event_finished)

    def reset(self):
        self.added = set()
        self.changed = set()
        self.removed = set()
        self.changed_columns = set()

    def on_event_finished(self, live_storage, success):
        self.send_changes()

    def send_changes(self):
        if self.added or self.changed or self.removed:
            m = messages.ItemChanges(self.added, self.changed, self.removed,
                                     self.changed_columns)
            m.send_to_frontend()
            self.reset()

    def on_item_added(self, item):
        self.added.add(item.id)

    def on_item_changed(self, item):
        self.changed.add(item.id)
        self.changed_columns.update(item.changed_attributes)

    def on_item_removed(self, item):
        self.removed.add(item.id)

class Item(DDBObject, iconcache.IconCacheOwnerMixin):
    """An item corresponds to a single entry in a feed.  It has a
    single url associated with it.
    """

    ICON_CACHE_VITAL = False

    # tweaked by the unittests to make things easier
    _allow_nonexistent_paths = False

    def setup_new(self, fp_values, link_number=0, feed_id=None, parent_id=None,
            eligible_for_autodownload=True, channel_title=None):
        for attr in metadata.attribute_names:
            setattr(self, attr, None)
        self.is_file_item = False
        self.new = True
        self.feed_id = feed_id
        self.parent_id = parent_id
        self.channel_title = channel_title
        self.is_container_item = None
        self.auto_downloaded = False
        self.pending_manual_download = False
        self.downloaded_time = None
        self.watched_time = self.last_watched = None
        self.pending_reason = u""
        entry_title = self.torrent_title = None
        self.metadata_title = None
        self.filename = None
        fp_values.update_item(self)
        self.expired = False
        self.keep = False
        self.eligible_for_autodownload = eligible_for_autodownload
        self.duration = None
        self.screenshot = None
        self.resume_time = 0
        self.channel_title = None
        self.downloader_id = None
        self.was_downloaded = False
        self.subtitle_encoding = None
        self.setup_new_icon_cache()
        self.play_count = 0
        self.skip_count = 0
        self.net_lookup_enabled = False
        # Initalize FileItem attributes to None
        self.deleted = self.short_filename = self.offset_path = None

        # link_number is a hack to make sure that scraped items at the
        # top of a page show up before scraped items at the bottom of
        # a page. 0 is the topmost, 1 is the next, and so on
        self.link_number = link_number
        self.creation_time = datetime.now()
        self._look_for_downloader()
        self.setup_common()
        self.split_item()

    def setup_restored(self):
        self.setup_common()
        self.setup_links()
        if (self.filename is not None and
            not self.deleted and
            not app.local_metadata_manager.path_in_system(self.filename)):
            logging.warn("Path for item not in MetadataManager (%s).  "
                         "Adding it now." % (self.filename))
            app.local_metadata_manager.add_file(self.filename)

    def setup_common(self):
        self.selected = False
        self.active = False
        self.expiring = None
        self.showMoreInfo = False
        self.playing = False
        Item._path_count_tracker.add_item(self)

    def after_setup_new(self):
        app.item_info_cache.item_created(self)
        Item.change_tracker.on_item_added(self)

    def signal_change(self, needs_save=True, can_change_views=True):
        app.item_info_cache.item_changed(self)
        Item.change_tracker.on_item_changed(self)
        DDBObject.signal_change(self, needs_save, can_change_views)

    @classmethod
    def auto_pending_view(cls):
        return cls.make_view('feed.autoDownloadable AND '
                'NOT item.was_downloaded AND '
                '(item.eligible_for_autodownload OR feed.getEverything)',
                joins={'feed': 'item.feed_id=feed.id'})

    @classmethod
    def manual_pending_view(cls):
        return cls.make_view('pending_manual_download')

    @classmethod
    def auto_downloads_view(cls):
        return cls.make_view("item.auto_downloaded AND "
                "rd.state in ('downloading', 'paused')",
                joins={'remote_downloader rd': 'item.downloader_id=rd.id'})

    @classmethod
    def manual_downloads_view(cls):
        return cls.make_view("NOT item.auto_downloaded AND "
                "NOT item.pending_manual_download AND "
                "rd.state in ('downloading', 'paused')",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def download_tab_view(cls):
        return cls.make_view("(item.pending_manual_download OR "
                "(rd.state in ('downloading', 'paused', 'uploading', "
                "'uploading-paused', 'offline') OR "
                "(rd.state == 'failed' AND "
                "feed.orig_url == 'dtv:manualFeed')) AND "
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
        return cls.make_view("item.watched_time IS NULL AND "
                "item.parent_id IS NULL AND "
                "rd.state in ('finished', 'uploading', 'uploading-paused')",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def newly_downloaded_view(cls):
        return cls.make_view("item.watched_time IS NULL AND "
                "(item.file_type in ('audio', 'video')) AND "
                "((is_file_item AND NOT deleted) OR "
                "(rd.main_item_id=item.id AND "
                "rd.state in ('finished', 'uploading', 'uploading-paused')))",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'},
                order_by='downloaded_time DESC')

    @classmethod
    def downloaded_view(cls):
        return cls.make_view("rd.state in ('finished', 'uploading', "
                "'uploading-paused')",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def incomplete_mdp_view(cls):
        """Return up to limit local items that have not yet been examined with
        MDP; a file is considered examined even if we have decided to skip it.

        NB. don't change this without also changing in_incomplete_mdp_view!
        """
        return cls.make_view("((is_file_item AND NOT deleted) OR "
                "(rd.state in ('finished', 'uploading', 'uploading-paused'))) "
                "AND NOT is_container_item " # match CMF short-circuit, just in case
                "AND mdp_state IS NULL", # State.UNSEEN
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @property
    def in_incomplete_mdp_view(self):
        """This is the python version of the SQL query in incomplete_mdp_view,
        to be used in situations where e.g. we need to assert that an item is no
        longer eligible for the view - where actually querying the entire view
        would be unreasonable.

        NB. don't change this without also changing incomplete_mdp_view!
        """
        if not self.id_exists():
            return False
        if self.is_container_item:
            return False
        # FIXME: if possible we should use the actual incomplete_mdp_view with
        # an id=self.id constraint, but I don't see a straightforward way to do
        # that
        valid_file_item = self.is_file_item and not self.deleted
        downloaded = self.downloader_state in (
                'finished', 'uploading', 'uploading-paused')
        return self.mdp_state is None and (valid_file_item or downloaded)

    @classmethod
    def unique_others_view(cls):
        return cls.make_view("item.file_type='other' AND "
                "((is_file_item AND NOT deleted) OR "
                "(rd.main_item_id=item.id AND "
                "rd.state in ('finished', 'uploading', 'uploading-paused')))",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})

    @classmethod
    def unique_new_video_view(cls, include_podcasts=False):
        query = ("item.watched_time IS NULL AND "
                 "item.file_type='video' AND "
                 "((is_file_item AND NOT deleted) OR "
                 "(rd.main_item_id=item.id AND "
                 "rd.state in ('finished', 'uploading', 'uploading-paused')))")
        joins = {'remote_downloader AS rd': 'item.downloader_id=rd.id'}
        if not include_podcasts:
            query = query + (" AND (feed_id IS NULL OR "
                             "feed.orig_url == 'dtv:manualFeed' OR "
                             "is_file_item)")
            joins['feed'] = 'feed_id = feed.id'
        return cls.make_view(query, joins=joins)

    @classmethod
    def unique_new_audio_view(cls, include_podcasts=False):
        query = ("item.watched_time IS NULL AND "
                 "item.file_type='audio' AND "
                 "((is_file_item AND NOT deleted) OR "
                 "(rd.main_item_id=item.id AND "
                 "rd.state in ('finished', 'uploading', 'uploading-paused')))")
        joins = {'remote_downloader AS rd': 'item.downloader_id=rd.id'}
        if not include_podcasts:
            query = query + (" AND (feed_id IS NULL OR "
                             "feed.orig_url == 'dtv:manualFeed' OR "
                             "is_file_item)")
            joins['feed'] = 'feed_id = feed.id'
        return cls.make_view(query, joins=joins)

    @classmethod
    def toplevel_view(cls):
        return cls.make_view('feed_id IS NOT NULL AND '
                             "feed.orig_url != 'dtv:manualFeed' AND "
                             "feed.orig_url NOT LIKE 'dtv:search%'",
                             joins={'feed': 'item.feed_id = feed.id'})

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
                "(is_file_item OR rd.state in ('finished', 'uploading', "
                "'uploading-paused'))",
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
        return cls.make_view("feed_id=? AND new", (feed_id,))

    @classmethod
    def feed_auto_pending_view(cls, feed_id):
        return cls.make_view('feed_id=? AND feed.autoDownloadable AND '
                'NOT item.was_downloaded AND '
                '(item.eligible_for_autodownload OR feed.getEverything)',
                (feed_id,),
                joins={'feed': 'item.feed_id=feed.id'})

    @classmethod
    def feed_unwatched_view(cls, feed_id):
        return cls.make_view("feed_id=? AND item.watched_time IS NULL AND "
                "file_type in ('audio', 'video') AND "
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
        return cls.make_view("feed.orig_url == 'dtv:search'",
                joins={'feed': 'item.feed_id=feed.id'})

    @classmethod
    def watchable_video_view(cls, include_podcasts=False):
        query = ("not is_container_item AND "
                 "(deleted IS NULL or not deleted) AND "
                 "(is_file_item OR rd.main_item_id=item.id) AND "
                 "item.file_type='video'")
        if not include_podcasts:
            query = query + (" AND (feed_id IS NULL OR "
                             "feed.orig_url == 'dtv:manualFeed' OR "
                             "feed.orig_url == 'dtv:searchDownloads' OR "
                             "feed.orig_url == 'dtv:search' OR "
                             "is_file_item)")
        return cls.make_view(query,
            joins={'feed': 'item.feed_id=feed.id',
                   'remote_downloader as rd': 'item.downloader_id=rd.id'})

    @classmethod
    def watchable_view(cls):
        return cls.make_view(
            "not is_container_item AND "
            "(deleted IS NULL or not deleted) AND "
            "(is_file_item OR rd.main_item_id=item.id) AND " 
            "NOT item.file_type='other'",
            joins={'feed': 'item.feed_id=feed.id',
                   'remote_downloader as rd': 'item.downloader_id=rd.id'})

    @classmethod
    def watchable_audio_view(cls, include_podcasts=False):
        query = ("not is_container_item AND "
                 "(deleted IS NULL or not deleted) AND "
                 "(is_file_item OR rd.main_item_id=item.id) AND "
                 "item.file_type='audio'")
        if not include_podcasts:
            query = query + (" AND (feed_id IS NULL OR "
                             "feed.orig_url == 'dtv:manualFeed' OR "
                             "feed.orig_url == 'dtv:searchDownloads' OR "
                             "feed.orig_url == 'dtv:search' OR "
                             "is_file_item)")
        return cls.make_view(query,
            joins={'feed': 'item.feed_id=feed.id',
                   'remote_downloader as rd': 'item.downloader_id=rd.id'})

    @classmethod
    def watchable_other_view(cls):
        return cls.make_view(
            "(deleted IS NULL OR not deleted) AND "
            "(is_file_item OR rd.id IS NOT NULL) AND "
            "item.file_type='other'",
            joins={'feed': 'item.feed_id=feed.id',
                   'remote_downloader as rd': 'rd.main_item_id=item.id'})

    @classmethod
    def feed_expiring_view(cls, feed_id, watched_before):
        return cls.make_view("watched_time is not NULL AND "
                "watched_time < ? AND feed_id = ? AND keep = 0",
                (watched_before, feed_id),
                joins={'feed': 'item.feed_id=feed.id'})

    @classmethod
    def latest_in_feed_view(cls, feed_id):
        return cls.make_view("feed_id=?", (feed_id,),
                order_by='release_date DESC', limit=1)

    @classmethod
    def media_children_view(cls, parent_id):
        return cls.make_view("parent_id=? AND "
                "file_type IN ('video', 'audio')", (parent_id,))

    @classmethod
    def containers_view(cls):
        return cls.make_view("is_container_item")

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
    def recently_watched_view(cls):
        return cls.make_view("file_type IN ('video', 'audio') AND last_watched")

    @classmethod
    def recently_downloaded_view(cls):
        return cls.make_view("item.watched_time IS NULL AND "
                "item.parent_id IS NULL AND "
                "NOT is_file_item AND downloaded_time AND "
                "rd.state in ('finished', 'uploading', 'uploading-paused')",
                joins={'remote_downloader AS rd': 'item.downloader_id=rd.id'})


    @classmethod
    def update_folder_trackers(cls, db_info=None):
        """Update each view tracker that care's about the item's
        folder (both playlist and channel folders).
        """
        if db_info is None:
            view_tracker_manager = app.db_info.view_tracker_manager
        else:
            view_tracker_manager = db_info.view_tracker_manager
        for tracker in view_tracker_manager.trackers_for_ddb_class(cls):
            # bit of a hack here.  We only need to update ViewTrackers
            # that care about the item's folder.  This seems like a
            # safe way to check if that's true.
            if 'folder_id' in tracker.where:
                tracker.check_all_objects()

    @classmethod
    def items_with_path_view(cls, path):
        return cls.make_view('lower(filename)=?',
                             (filename_to_unicode(path).lower(),))

    @classmethod
    def downloader_view(cls, dler_id):
        return cls.make_view("downloader_id=?", (dler_id,))

    _path_count_tracker = _ItemsForPathCountTracker()

    @classmethod
    def have_item_for_path(cls, path):
        """Check if we have an item for a path.

        This method is optimized to avoid DB queries if at all possible.
        """
        # NOTE: use Item here rather than cls, since FileItem and Item share
        # the same _path_count_tracker.
        return Item._path_count_tracker.get_count(path) > 0

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
            return (fn for fn in fileutil.miro_allfiles(filename_root))
        else:
            return []

    def _make_new_children(self, paths):
        filename_root = self.get_filename()
        if filename_root is None:
            logging.error("Item._make_new_children: get_filename here is None")
            return
        for path in paths:
            # XXX this assert is expensive due to stat()
            assert os.path.isfile(path)
            assert path.startswith(filename_root)
            offset_path = path[len(filename_root):]
            while offset_path[0] in ('/', '\\'):
                offset_path = offset_path[1:]
            FileItem(path, parent_id=self.id, offset_path=offset_path)

    @eventloop.idle_iterator
    def find_new_children(self, callback=None):
        """If this feed is a container item, walk through its
        directory and find any new children.  You may specify a callback
        which will be called at the end of the find_new_children()
        operation as a sort of serializing operation.  Doing so,
        is entirely optional though on an as-needed basis.
        """
        if not self.id_exists() or self.is_container_item == False:
            return
        if self.is_container_item:
            skip = [c.get_filename() for c in self.get_children()]
        else:
            skip = []
        if self.get_state() == 'downloading':
            # don't try to find videos that we're in the middle of
            # re-downloading
            return
        dirty = False
        this_pass = []
        start = time.time()
        for path in self._find_child_paths():
            if path in skip:
                continue
            this_pass.append(path)
            if time.time() - start > 0.3:
                self.is_container_item = True
                dirty = True
                self._make_new_children(this_pass)
                self.signal_change()
                yield
                if not self.id_exists():
                    return
                # Leave "skip" as is.  The filesystem namespace changes
                # asynchronously wrt to our operations and so whether we do
                # it piecemeal or in one go is the same.
                start = time.time()
                this_pass = []
        if this_pass:
            # Do the leftovers
            dirty = True
            self.is_container_item = True
            self._make_new_children(this_pass)
            self.signal_change()
        if callback:
            callback(dirty)

    def split_item(self):
        if self.is_container_item is not None:
            if self.is_container_item:
                self.find_new_children()
            return
        if ((not isinstance(self, FileItem)
             and (self.downloader is None
                  or not self.downloader.is_finished()))):
            return
        filename_root = self.get_filename()
        if filename_root is None:
            return
        if fileutil.isdir(filename_root):
            def complete(nonempty):
                if not self.id_exists():
                    return
                if not nonempty:
                    if not self.get_feed_url().startswith("dtv:directoryfeed"):
                        target_dir = app.config.get(prefs.NON_VIDEO_DIRECTORY)
                        if not filename_root.startswith(target_dir):
                            if isinstance(self, FileItem):
                                self.migrate(target_dir)
                            else:
                                self.downloader.migrate(target_dir)
                    self.is_container_item = False
                self.signal_change()
            self.find_new_children(callback=complete)
        else:
            self.is_container_item = False
        self.signal_change()

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
        Item._path_count_tracker.remove_item(self)
        self.filename = filename
        if not app.local_metadata_manager.path_in_system(filename):
            metadata = app.local_metadata_manager.add_file(filename)
        else:
            metadata = app.local_metadata_manager.get_metadata(filename)
        self.update_from_metadata(metadata)
        Item._path_count_tracker.add_item(self)

    def file_moved(self, new_filename):
        app.local_metadata_manager.file_moved(self.filename, new_filename)
        self.set_filename(new_filename)

    def update_from_metadata(self, metadata_dict):
        """Update our attributes from a metadata dictionary."""
        # change the name of title to be "metadata_title"
        metadata_dict = metadata_dict.copy()
        if 'title' in metadata_dict:
            metadata_dict['metadata_title'] = metadata_dict.pop('title')
        self._bulk_update_db_values(metadata_dict)
        self.calc_title()

    def set_user_metadata(self, metadata_dict):
        if not self.filename:
            logging.warn("No file to set metadata for in "
                         "set_metadata_from_iteminfo")
            return
        app.local_metadata_manager.set_user_data(self.filename, metadata_dict)
        self.update_from_metadata(metadata_dict)
        self.signal_change()

    def set_rating(self, rating):
        self.rating = rating
        self.signal_change()

    def matches_search(self, search_string):
        if search_string is None or search_string == '':
            return True
        my_info = app.item_info_cache.get_info(self.id)
        return search.item_matches(my_info, search_string)

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
                # If is_container_item is None, we may be in the middle
                # of building the children list.
                if (obj.is_container_item is not None and
                    not obj.is_container_item):
                    msg = "parent_id is not a containerItem"
                    raise DatabaseConstraintError(msg)
        if self.parent_id is None and self.feed_id is None:
            raise DatabaseConstraintError("feed_id and parent_id both None")
        if self.parent_id is not None and self.feed_id is not None:
            raise DatabaseConstraintError(
                "feed_id and parent_id both not None")

    def on_signal_change(self):
        self.expiring = None
        if hasattr(self, "_state"):
            del self._state
        if hasattr(self, "_size"):
            del self._size

    def recalc_feed_counts(self):
        self.get_feed().recalc_counts()

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

    def get_parent_sort_key(self):
        if self.has_parent():
            parent = self.get_parent()
            # this key lets us sort by title, but also keep torrents with
            # duplicate titles separate.
            return (parent.get_title(), parent.id)
        else:
            return None

    @returns_unicode
    def get_feed_url(self):
        return self.get_feed().orig_url

    @returns_unicode
    def get_source(self):
        if self.feed_id is not None:
            feed_ = self.get_feed()
            if feed_.orig_url != 'dtv:manualFeed':
                # we do this manually so we don't pick up the name of a search
                # query (#16044)
                return feed_.userTitle or feed_.actualFeed.get_title()
        if self.has_parent():
            try:
                return self.get_parent().get_title()
            except ObjectNotFoundError:
                return None
        return None

    def get_children(self):
        if self.is_container_item:
            return Item.children_view(self.id)
        else:
            raise ValueError("%s is not a container item" % self)

    def children_signal_change(self):
        for child in self.get_children():
            child.signal_change(needs_save=False)

    def is_playable(self):
        """Is this a playable item?"""

        if self.is_container_item:
            return Item.media_children_view(self.id).count() > 0
        else:
            return self.file_type in ('audio', 'video') and not self.has_drm

    def set_feed(self, feed_id):
        """Moves this item to another feed.
        """
        self.feed_id = feed_id
        # _feed is created by get_feed which caches the result
        if hasattr(self, "_feed"):
            del self._feed
        if self.is_container_item:
            for item in self.get_children():
                if hasattr(item, "_feed"):
                    del item._feed
                item.signal_change()
        self.signal_change()

    def expire(self):
        self.confirm_db_thread()
        self._remove_from_playlists()
        if self.is_external():
            self.delete_files_and_remove()
        else:
            self.delete_files_and_expire()
        self.recalc_feed_counts()

    def delete_files_and_remove(self):
        if self.is_downloaded():
            if self.is_container_item:
                for item in self.get_children():
                    item.make_deleted()
            elif self.get_filename():
                FileItem(self.get_filename(), feed_id=self.feed_id,
                         parent_id=self.parent_id, deleted=True)
            if self.has_downloader():
                self.downloader.set_delete_files(False)
        self.remove()

    def delete_files_and_expire(self):
        if self.is_container_item:
            # remove our children, since we're about to set
            # is_container_item to None
            for item in self.get_children():
                item.make_deleted()
                item.remove()
        Item._path_count_tracker.remove_item(self)
        self.delete_files()
        self.resume_time = 0
        self.expired = True
        self.keep = self.pending_manual_download = False
        self.filename = None
        self.file_type = self.watched_time = self.last_watched = None
        self.duration = None
        self.is_container_item = None
        self.signal_change()

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
            if self.is_container_item:
                self.children_signal_change()

    def pause_upload(self):
        if self.downloader:
            self.downloader.pause_upload()
            if self.is_container_item:
                self.children_signal_change()

    def start_upload(self):
        if self.downloader:
            self.downloader.start_upload()
            if self.is_container_item:
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

    def get_creation_time(self):
        """Returns the time this Item object was created -
        i.e. the associated file was added to our database
        """
        return self.creation_time

    def get_watched_time(self):
        """Returns the most recent watched time of this item or any
        of its child items.

        Returns a datetime.datetime instance or None if the item and none
        of its children have been watched.
        """
        if not self.get_watched():
            return None
        if self.is_container_item and self.watched_time == None:
            self.watched_time = datetime.min
            for item in self.get_children():
                child_time = item.get_watched_time()
                if child_time is None:
                    self.watched_time = None
                    return None
                if child_time > self.watched_time:
                    self.watched_time = child_time
            self.signal_change()
        return self.watched_time

    def get_expiring(self):
        if self.expiring is None:
            if not self.get_watched():
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

    def unset_new(self):
        """Unsets the "new" attribute of an item.

        This should be done after:
            The user, or the auto-downloader, downloads the item
            The user has seen the item in a feed then switched away from it
        """
        self.new = False
        self.signal_change()

    def get_watched(self):
        """Check if the media file has been watched by the user """
        self.confirm_db_thread()
        return self.watched_time is not None

    def set_watched(self):
        """Set that this item has been watched by the user

        If this item has been watched before, this sets last_watched to the
        current time.  If it hasn't been watched, this sets both watched_time
        and last_watched.
        """
        self.last_watched = datetime.now()
        if self.watched_time is None:
            self.watched_time = self.last_watched
        self.signal_change()

    def unset_watched(self):
        """Act like this item has never been watched by the user."""
        self.resume_time = 0
        self.watched_time = self.last_watched = None
        self.signal_change()

    def mark_watched(self, mark_other_items=True):
        """Marks the item as seen.
        """
        self.confirm_db_thread()
        self.has_drm = False
        if self.is_container_item:
            for child in self.get_children():
                child.set_watched()
        was_watched = self.get_watched()
        self.set_watched()
        if not was_watched:
            # need to do some extra work if this is the first time we're
            # watching the video
            if self.subtitle_encoding is None:
                config_value = app.config.get(prefs.SUBTITLE_ENCODING)
                if config_value:
                    self.subtitle_encoding = unicode(config_value)
            self.update_parent_seen()
            self.recalc_feed_counts()

        if mark_other_items and self.downloader:
            for item in self.downloader.item_list:
                if item != self:
                    item.mark_watched(False)

    def update_parent_seen(self):
        if self.parent_id:
            unseen_children = self.make_view(
                'parent_id=? AND watched_time IS NULL AND '
                "file_type in ('audio', 'video')", (self.parent_id,))
            new_seen = (unseen_children.count() == 0)
            parent = self.get_parent()
            if parent.get_watched() != new_seen:
                if new_seen:
                    parent.set_watched()
                else:
                    parent.unset_watched()

    def mark_unwatched(self, mark_other_items=True):
        self.confirm_db_thread()
        if self.is_container_item:
            for item in self.get_children():
                item.unset_watched()

        if self.get_watched():
            self.unset_watched()
            self.update_parent_seen()
            if mark_other_items and self.downloader:
                for item in self.downloader.item_list:
                    if item != self:
                        item.mark_unwatched(False)
            self.recalc_feed_counts()

    # TODO: played/seen count updates need to trigger recalculation of auto
    # ratings somewhere
    def mark_item_completed(self):
        self.confirm_db_thread()
        self.play_count += 1
        self.signal_change()

    def mark_item_skipped(self):
        self.confirm_db_thread()
        self.skip_count += 1
        self.signal_change()

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
        if autodl != self.auto_downloaded:
            self.auto_downloaded = autodl
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
        if self.resume_time != position:
            self.resume_time = position
            self.signal_change()

    def get_auto_downloaded(self):
        """Returns true iff item was auto downloaded.
        """
        self.confirm_db_thread()
        return self.auto_downloaded

    def download(self, autodl=False):
        """Starts downloading the item.
        """
        self.confirm_db_thread()
        manual_dl_count = Item.manual_downloads_view().count()
        self.expired = self.keep = False
        self.was_downloaded = True
        self.new = False
        self.watched_time = None

        if ((not autodl) and
                manual_dl_count >= app.config.get(prefs.MAX_MANUAL_DOWNLOADS)):
            self.pending_manual_download = True
            self.pending_reason = _("queued for download")
            self.signal_change()
            if self.looks_like_torrent():
                self.update_title_from_torrent()
            return
        else:
            self.set_auto_downloaded(autodl)
            self.pending_manual_download = False

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
        return self.pending_manual_download

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
        return self.eligible_for_autodownload

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
        if self.cover_art:
            path = self.cover_art
            path = resources.path(fileutil.expand_filename(path))
            if fileutil.exists(path):
                return path
        if self.icon_cache is not None and self.icon_cache.is_valid():
            # is_valid() verifies that the path exists
            path = self.icon_cache.get_filename()
            return resources.path(fileutil.expand_filename(path))
        if self.screenshot:
            path = self.screenshot
            path = resources.path(fileutil.expand_filename(path))
            if fileutil.exists(path):
                return path
        if self.is_container_item:
            return resources.path("images/thumb-default-folder.png")
        else:
            feed = self.get_feed()
            if feed.thumbnail_valid():
                # thumbnail_valid() also verifies the path exists
                return feed.get_thumbnail_path()
            elif (self.get_filename()
                  and filetypes.is_audio_filename(self.get_filename())):
                return resources.path("images/thumb-default-audio.png")
            else:
                return resources.path("images/thumb-default-video.png")

    def is_downloaded_torrent(self):
        return (self.is_container_item and self.has_downloader() and
                self.downloader.is_finished())

    @returns_unicode
    def get_title(self):
        """Returns the title of the item.
        """
        return self.title

    def calc_title(self):
        """Set the title column

        The title column store the official title for the item.  This may come
        from torrent data, file metadata, feed data, and or our filename.
        """
        if self.metadata_title:
            title = self.metadata_title
        elif self.torrent_title is not None:
            title = self.torrent_title
        elif self.entry_title is not None:
            title = self.entry_title
        elif self.filename:
            title = filename_to_unicode(os.path.basename(self.filename))
        else:
            title = _('no title')
        if title != self.title:
            self.title = title

    def set_channel_title(self, title):
        check_u(title)
        self.channel_title = title
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
        elif self.channel_title:
            return self.channel_title
        else:
            return u''

    @returns_unicode
    def get_description(self):
        """Returns the description of the video (unicode).

        If the item is a torrent, then it adds some additional text.
        """
        if self.description:
            return self.description

        if self.entry_description:
            return unicode(self.entry_description)

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

    def update_title_from_torrent(self):
        """Try to update our title using torrent metadata.

        If this item is a torrent, then we will download the .torrent file and
        use that to upate our title.  If this is not a torrent, or there's an
        error downloading the file, then nothing will change
        """
        self._update_title_from_torrent_client = httpclient.grab_url(
                self.get_url(),
                self._update_title_from_torrent_callback,
                self._update_title_from_torrent_errback,
                header_callback=self._update_title_from_torrent_headers)

    def _update_title_from_torrent_headers(self, info):
        if info['content-type'] != u'application/x-bittorrent':
            logging.warn("wrong content-type %s in "
                "update_title_from_torrent()", info['content-type'])
            # data doesn't seem like a torrent, cancel the request
            self._update_title_from_torrent_client.cancel()
            self._update_title_from_torrent_client = None

    def _update_title_from_torrent_callback(self, info):
        try:
            title = util.get_name_from_torrent_metadata(info['body'])
        except ValueError:
            logging.exception("Error setting torrent name")
        else:
            self.torrent_title = title
            self.calc_title()
            self.signal_change()
        self._update_title_from_torrent_client = None

    def _update_title_from_torrent_errback(self, error):
        logging.warn("Error downloading torrent metainfo in "
                "update_title_from_torrent(): %s", error)
        self._update_title_from_torrent_client = None

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
        if self.is_container_item:
            for item in self.get_children():
                item.delete_files()
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
            if self.pending_manual_download:
                self._state = u'downloading'
            elif self.expired:
                self._state = u'expired'
            elif self.new:
                self._state = u'new'
            else:
                self._state = u'not-downloaded'
        elif self.downloader.get_state() in (u'offline', u'paused'):
            if self.pending_manual_download:
                self._state = u'downloading'
            else:
                self._state = u'paused'
        elif not self.downloader.is_finished():
            self._state = u'downloading'
        elif not self.get_watched():
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
        if self.new:
            return u'new'
        elif self.downloader is None or not self.downloader.is_finished():
            if self.expired:
                return u'expired'
            else:
                return u'not-downloaded'
        elif not self.get_watched():
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
            size = self.downloader.get_total_size()
            if size == -1:
                logging.debug("downloader could not get total size for item")
                return 0
            return size
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
        if self.pending_manual_download:
            return self.pending_reason
        elif self.downloader:
            return self.downloader.get_startup_activity()
        else:
            return _("starting up...")

    def get_pub_date_parsed(self):
        """Returns the published date of the item as a datetime object.
        """
        return self.get_release_date()

    def get_release_date(self):
        """Returns the date this video was released or when it was
        published.
        """
        return self.release_date

    def get_duration_value(self):
        """Returns the length of the video in seconds.
        """
        secs = None
        if self.duration is not None:
            secs = self.duration / 1000
        return secs

    @returns_unicode
    def get_format(self, empty_for_unknown=True):
        """Returns string with the format of the video.
        """
        if self.looks_like_torrent():
            return u'.torrent'

        if self.enclosure_format is not None:
            return self.enclosure_format

        if self.downloader:
            if ((self.downloader.content_type
                 and "/" in self.downloader.content_type)):
                mtype, subtype = self.downloader.content_type.split('/', 1)
                mtype = mtype.lower()
                if mtype in KNOWN_MIME_TYPES:
                    format_ = subtype.split(';')[0].upper()
                    if mtype == u'audio':
                        format_ += u' AUDIO'
                    if format_.startswith(u'X-'):
                        format_ = format_[2:]
                    return (u'.%s' %
                            MIME_SUBSITUTIONS.get(format_, format_).lower())

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
        if self.icon_cache.filename is None:
            self.icon_cache.request_update()
        self.signal_change()

    def on_download_finished(self):
        """Called when the download for this item finishes."""

        self.confirm_db_thread()
        self.downloaded_time = datetime.now()
        self.set_filename(self.downloader.get_filename())
        self.split_item()
        self.signal_change()
        self._replace_file_items()
        signals.system.download_complete(self)

        for other in Item.make_view('downloader_id IS NULL AND url=?',
                (self.url,)):
            other.set_downloader(self.downloader)
        self.recalc_feed_counts()

    def on_downloader_migrated(self, old_filename, new_filename):
        self.file_moved(new_filename)
        self.signal_change()
        if self.is_container_item:
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

    def save(self, always_signal=False):
        self.confirm_db_thread()
        if self.keep != True:
            self.keep = True
            always_signal = True
        if always_signal:
            self.signal_change()

    @returns_filename
    def get_filename(self):
        return self.filename

    def is_video_file(self):
        return (self.is_container_item != True
                and filetypes.is_video_filename(self.get_filename()))

    def is_audio_file(self):
        return (self.is_container_item != True
                and filetypes.is_audio_filename(self.get_filename()))

    def is_external(self):
        """Returns True iff this item was not downloaded from a Democracy
        channel.
        """
        return (self.feed_id is not None
                and self.get_feed_url() == 'dtv:manualFeed')

    def migrate_children(self, newdir):
        if self.is_container_item:
            for item in self.get_children():
                item.migrate(newdir)

    def remove(self):
        Item._path_count_tracker.remove_item(self)
        if self.has_downloader():
            self.set_downloader(None)
        self.remove_icon_cache()
        if self.is_container_item:
            for item in self.get_children():
                item.remove()
        self._remove_from_playlists()
        DDBObject.remove(self)
        # need to call this after DDBObject.remove(), so that the item info is
        # there for ItemInfoFetcher to see.
        app.item_info_cache.item_removed(self)
        Item.change_tracker.on_item_removed(self)

    def setup_links(self):
        self.split_item()
        if not self.id_exists():
            # In split_item() we found out that all our children were
            # deleted, so we were removed as well.  (#11979)
            return
        _deleted_file_checker.schedule_check(self)

    def check_deleted(self):
        """Check whether the item's file has been deleted outside of miro.

        We expire() the item if it has.

        :returns: True if expire() was called or our id doesn't exist
        """
        if not self.id_exists():
            return True
        if (self.is_container_item is not None and
                not fileutil.exists(self.get_filename()) and
                not self._allow_nonexistent_paths):
            self.expire()
            return True
        return False

    def _get_downloader(self):
        try:
            return self._downloader
        except AttributeError:
            if self.downloader_id is None:
                dler = None
            else:
                dler = downloader.get_existing_downloader(self)
                if dler is not None:
                    dler.add_item(self)
            self._downloader = dler
            return dler
    downloader = property(_get_downloader)

    def get_auto_rating(self):
        """Guess at a rating based on the number of times the files has been
        played vs. skipped and the item's age.
        """
        # TODO: we may want to take into consideration average ratings for this
        # artist and this album, total play count and skip counts, and average
        # manual rating
        SKIP_FACTOR = 1.5 # rating goes to 1 when user skips 40% of the time
        UNSKIPPED_FACTOR = 2 # rating goes to 5 when user plays 3 times without
                             # skipping
        # TODO: should divide by log of item's age
        if self.play_count > 0:
            if self.skip_count > 0:
                return min(5, max(1, int(self.play_count -
                    SKIP_FACTOR * self.skip_count)))
            else:
                return min(5, int(UNSKIPPED_FACTOR * self.play_count))
        elif self.skip_count > 0:
            return 1
        else:
            return None

    def set_is_playing(self, playing):
        old_playing = self.playing
        self.playing = playing
        if playing != old_playing:
            self.signal_change()

    def is_playing(self):
        return self.playing

    def __str__(self):
        return "Item - %s" % stringify(self.get_title())

class FileItem(Item):
    """An Item that exists as a local file
    """
    def setup_new(self, filename, feed_id=None, parent_id=None,
            offset_path=None, deleted=False, fp_values=None,
            channel_title=None, mark_seen=False):
        if fp_values is None:
            fp_values = fp_values_for_file(filename)
        Item.setup_new(self, fp_values, feed_id=feed_id, parent_id=parent_id,
                eligible_for_autodownload=False, channel_title=channel_title)
        self.is_file_item = True
        check_f(filename)
        filename = fileutil.abspath(filename)
        self.set_filename(filename)
        self.set_release_date()
        self.deleted = deleted
        self.offset_path = offset_path
        self.short_filename = clean_filename(os.path.basename(self.filename))
        self.was_downloaded = False
        if mark_seen:
            self.watched_time = datetime.now()
        if not fileutil.isdir(self.filename):
            # If our file isn't a directory, then we know we are definitely
            # not a container item.  Note that the opposite isn't true in the
            # case where we are a directory with only 1 file inside.
            self.is_container_item = False
        # FileItems are never considered new.  The new flag only really makes
        # sense inside a feed.
        self.new = False
        self.split_item()

    # FileItem downloaders are always None
    downloader = property(lambda self: None)

    @returns_unicode
    def get_state(self):
        if self.deleted:
            return u"expired"
        elif self.get_watched():
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
        elif not self.get_watched():
            return u'newly-downloaded'

        if self.parent_id and self.get_parent().get_expiring():
            return u'expiring'
        else:
            return u'saved'

    def get_expiring(self):
        return False

    def show_save_button(self):
        return False

    def is_external(self):
        return self.parent_id is None

    def _look_for_downloader(self):
        # we don't need a database query to know that there's no downloader
        # for us.
        return

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
            if url.startswith("dtv:manualFeed"):
                self.remove()
            else:
                self.make_deleted()
        if old_parent is not None and old_parent.get_children().count() == 0:
            old_parent.expire()
        if app.local_metadata_manager.path_in_system(self.filename):
            app.local_metadata_manager.remove_file(self.filename)

    def remove(self):
        if app.local_metadata_manager.path_in_system(self.filename):
            app.local_metadata_manager.remove_file(self.filename)
        Item.remove(self)

    def make_deleted(self):
        if app.local_metadata_manager.path_in_system(self.filename):
            app.local_metadata_manager.remove_file(self.filename)
        self._remove_from_playlists()
        self.downloaded_time = None
        # Move to the manual feed, since from Miro's point of view the file is
        # no longer part of a feed, or torrent container.
        self.parent_id = None
        self.feed_id = models.Feed.get_manual_feed().id
        self.deleted = True
        self.signal_change()

    def make_undeleted(self):
        self.deleted = False
        self.signal_change()
        if not app.local_metadata_manager.path_in_system(self.filename):
            app.local_metadata_manager.add_file(self.filename)
        else:
            logging.warn("Item.make_undeleted: path exists in "
                         "MetadataManager (%r)" % self.filename)

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
        except OSError:
            logging.warn("delete_files error:\n%s", traceback.format_exc())

    def download(self, autodl=False):
        self.make_undeleted()

    def set_release_date(self):
        try:
            self.release_date = datetime.fromtimestamp(
                fileutil.getmtime(self.filename))
        except (OSError, ValueError):
            logging.warn("Error setting release date:\n%s",
                    traceback.format_exc())
            self.release_date = datetime.now()

    def get_release_date(self):
        if self.parent_id:
            return self.get_parent().release_date
        else:
            return self.release_date

    def migrate(self, newdir):
        self.confirm_db_thread()
        if self.parent_id:
            parent = self.get_parent()
            self.file_moved(os.path.join(parent.get_filename(),
                                         self.offset_path))
            return
        if self.short_filename is None:
            logging.warn("""\
can't migrate download because we don't have a short_filename!
filename was %s""", stringify(self.filename))
            return
        new_filename = os.path.join(newdir, self.short_filename)
        if self.filename == new_filename:
            return
        if fileutil.exists(self.filename):
            # create a file or directory to serve as a placeholder before we
            # start to migrate.  This helps ensure that the destination we're
            # migrating too is not already taken.
            src = self.filename
            try:
                is_dir = fileutil.isdir(src)
                if is_dir:
                    new_filename = next_free_directory(new_filename)
                    fp = None
                else:
                    new_filename, fp = next_free_filename(new_filename)
                    fp.close() # clean up if we called next_free_filename()
            except ValueError:
                func = 'next_free_directory' if is_dir else 'next_free_filename'
                logging.warn('migrate_file: %s failed.  Filename %r '
                             'candidate %r', func, src, new_filename)
            else:
                def callback():
                    self.file_moved(new_filename)
                fileutil.migrate_file(src, new_filename, callback)
        elif fileutil.exists(new_filename):
            self.file_moved(new_filename)
        self.migrate_children(newdir)

    def setup_links(self):
        if self.short_filename is None:
            if self.parent_id is None:
                self.short_filename = clean_filename(
                    os.path.basename(self.filename))
            else:
                parent_file = self.get_parent().get_filename()
                if self.filename.startswith(parent_file):
                    self.short_filename = clean_filename(
                        self.filename[len(parent_file):])
                else:
                    logging.warn("%s is not a subdirectory of %s",
                            self.filename, parent_file)
        Item.setup_links(self)


@returns_unicode
def filename_to_title(filename):
    title = filename_to_unicode(os.path.basename(filename))
    title = title.rsplit('.', 1)[0]
    title = title.replace('_', ' ')
    t2 = []
    for word in title.split(' '):
        t2.append(word.capitalize())
    title = u' '.join(t2)
    return title


def fp_values_for_file(filename, title=None, description=None):
    return FileFeedParserValues(filename, title, description)

class DeletedFileChecker(object):
    """Utility class that manages calling Item.check_deleted().

    This class ensures that we only schedule one idle callback at a time.
    """
    def __init__(self):
        # track items that we should call check_deleted for
        self.items_to_check = set()
        # track if we have run_checks() scheduled as an idle callback
        self.check_scheduled = False
        # track if we should be checking yet
        self.started = False

    def schedule_check(self, item):
        self.items_to_check.add(item)
        self._ensure_run_checks_scheduled()

    def start_checks(self):
        """Start the deleted file checking."""
        self.started = True
        self._ensure_run_checks_scheduled()

    def _ensure_run_checks_scheduled(self):
        """Ensure that we run_checks() scheduled as an idle callback.

        This method is a no-op if start_checks() hasn't been called yet.

        If this method is called multiple times before run_checks() runs, then
        it only schedules one callback.
        """
        if self.started and not self.check_scheduled:
            eventloop.add_idle(self.run_checks, 'checking items deleted')
            self.check_scheduled = True

    def run_checks(self):
        """Call check_deleted() for the items that are scheduled to check."""
        self.check_scheduled = False
        # Grab a limited number items at a time to prevent us from using too
        # much time in for this idle callback.
        # Update items_to_check immediately in case schedule_check() is called
        # in response to us calling check_deleted()
        items_this_pass = []
        for x in xrange(100):
            try:
                to_check = self.items_to_check.pop()
                items_this_pass.append(to_check)
            except KeyError:
                break # items_to_check is empty

        app.bulk_sql_manager.start()
        try:
            for item in items_this_pass:
                if item.id_exists():
                    item.check_deleted()
        finally:
            app.bulk_sql_manager.finish()
            if self.items_to_check:
                self._ensure_run_checks_scheduled()

class DeviceItem(object):
    """
    An item which lives on a device.  There's a separate, per-device JSON
    database, so this implements the necessary Item logic for those files.
    """
    def __init__(self, **kwargs):
        self.__initialized = False
        for required in ('video_path', 'file_type', 'device'):
            if required not in kwargs:
                raise TypeError('DeviceItem must be given a "%s" argument'
                                % required)
        self.file_format = self.size = None
        self.release_date = None
        self.feed_name = self.feed_id = self.feed_url = None
        self.keep = True
        self.is_container_item = False
        self.url = self.payment_link = None
        self.comments_link = self.permalink = self.file_url = None
        self.license = self.downloader = None
        self.duration = self.screenshot = self.thumbnail_url = None
        self.resume_time = 0
        self.subtitle_encoding = self.enclosure_type = None
        self.auto_sync = False
        self.file_type = None
        self.creation_time = None
        self.is_playing = False
        for attr in metadata.attribute_names:
            setattr(self, attr, None)
        if 'local_path' in kwargs:
            local_path = kwargs.pop('local_path')
        else:
            local_path = None
        self._fix_paths_from_database(kwargs)
        # set values for attributes used in pre-5.0 databases.
        self.metadata_version = 5 # version used in 4.0.x
        self.mdp_state = MDP_STATE_RAN
        self.title_tag = None

        self.__dict__.update(kwargs)

        if isinstance(self.video_path, unicode):
            # make sure video path is a filename and ID is Unicode
            self.id = self.video_path
            self.video_path = utf8_to_filename(self.video_path.encode('utf8'))
        else:
            self.id = filename_to_unicode(self.video_path)
        if self.file_format is None:
            self.file_format = filename_to_unicode(
                os.path.splitext(self.video_path)[1])
            if self.file_type == 'audio':
                self.file_format = self.file_format + ' audio'

        try: # filesystem operations
            if self.size is None:
                self.size = os.path.getsize(self.get_filename())
            if self.release_date is None or self.creation_time is None:
                ctime = fileutil.getctime(self.get_filename())
                if self.release_date is None:
                    self.release_date = ctime
                if self.creation_time is None:
                    self.creation_time = ctime
        except (OSError, IOError):
            # if there was an error reading the data from the filesystem, don't
            # bother continuing with other FS operations or starting moviedata
            logging.debug('error reading %s', self.id, exc_info=True)
        self.add_to_metadata_manager(local_path)
        self.__initialized = True

    def _fix_paths_from_database(self, data):
        """Make screenshot and cover_art the correct type.
        """
        for key in ('screenshot', 'cover_art'):
            if key in data and isinstance(data[key], unicode):
                data[key] = utf8_to_filename(data[key].encode('utf-8'))

    def add_to_metadata_manager(self, local_path):
        metadata_manager = self.device.metadata_manager
        if not metadata_manager.path_in_system(self.video_path):
            initial_metadata = metadata_manager.add_file(self.video_path,
                                                         local_path)
            # update ourself based on the initial metadata
            self.__dict__.update(initial_metadata)

    @staticmethod
    def id_exists():
        return True

    def get_release_date(self):
        try:
            return datetime.fromtimestamp(self.release_date)
        except (ValueError, TypeError):
            logging.warn('DeviceItem: release date %s invalid',
                          self.release_date)
            return datetime.now()

    def get_creation_time(self):
        try:
            return datetime.fromtimestamp(self.creation_time)
        except (ValueError, TypeError):
            logging.warn('DeviceItem: creation time %s invalid',
                          self.creation_time)
            return datetime.now()

    @returns_filename
    def get_filename(self):
        return os.path.join(self.device.mount, self.video_path)

    def get_url(self):
        return self.url or u''

    @returns_unicode
    def get_title(self):
        """Returns the title of the item.
        """
        if self.title:
            return self.title
        if self.title_tag:
            # title_tag was set to the ID3 tag by pre-5.0 versions.  We
            # convert this to title_tag in
            # devicedatabaseupgrade.import_old_items(), so this probably won't
            # be reached.  But we might as well prefer title_tag over the
            # filename if it somehow exists.
            return self.title_tag
        return os.path.basename(self.id)

    @returns_filename
    def get_thumbnail(self):
        if self.cover_art:
            return os.path.join(self.device.mount,
                                self.cover_art)
        elif self.screenshot:
            return os.path.join(self.device.mount,
                                self.screenshot)
        elif self.file_type == 'audio':
            return resources.path("images/thumb-default-audio.png")
        else:
            return resources.path("images/thumb-default-video.png")

    def remove(self, save=True):
        for file_type in [u'video', u'audio', u'other']:
            if self.video_path in self.device.database[file_type]:
                del self.device.database[file_type][self.id]
        if save:
            self.device.database.emit('item-removed', self)
            self.device.metadata_manager.remove_file(self.video_path)

    def signal_change(self):
        if not self.__initialized:
            return

        if not os.path.exists(
            os.path.join(self.device.mount, self.video_path)):
            # file was removed from the filesystem
            self.remove()
            return

        if (not isinstance(self.file_type, unicode) and
            self.file_type is not None):
            self.file_type = unicode(self.file_type)

        was_removed = False
        for type_ in set((u'video', u'audio', u'other')) - set(
            (self.file_type,)):
            if self.id in self.device.database[type_]:
                # clean up old types, if necessary
                self.remove(save=False)
                was_removed = True
                break

        if self.file_type:
            db = self.device.database
            db[self.file_type][self.id] =  self.to_dict()

            if self.file_type != u'other' or was_removed:
                db.emit('item-changed', self)

    def to_dict(self):
        data = {}
        for k, v in self.__dict__.items():
            if v is not None and k not in (u'device', u'file_type', u'id',
                                           u'video_path', u'_deferred_update'):
                if ((k == u'screenshot' or k == u'cover_art')):
                    v = filename_to_unicode(v)
                data[k] = v
        return data

_deleted_file_checker = None

def setup_deleted_checker():
    global _deleted_file_checker
    _deleted_file_checker = DeletedFileChecker()

def start_deleted_checker():
    _deleted_file_checker.start_checks()

def fix_non_container_parents():
    """Make sure all items referenced by parent_id have is_container_item set

    Bug #12906 has a database where this was not so.
    """
    where_sql = ("(is_container_item = 0 OR is_container_item IS NULL) AND "
            "id IN (SELECT parent_id FROM item)")
    for item in Item.make_view(where_sql):
        logging.warn("parent_id points to %s but is_container_item == %r. "
                "Setting is_container_item to True", item.id,
                item.is_container_item)
        item.is_container_item = True
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

def setup_metadata_manager(cover_art_dir=None, screenshot_dir=None):
    """Setup the MetadataManager for Items and FileItems."""
    if cover_art_dir is None:
        cover_art_dir = app.config.get(prefs.COVER_ART_DIRECTORY)
    if screenshot_dir is None:
        icon_cache_dir = app.config.get(prefs.ICON_CACHE_DIRECTORY)
        screenshot_dir = os.path.join(icon_cache_dir, 'extracted')
    app.local_metadata_manager = metadata.LibraryMetadataManager(
        cover_art_dir, screenshot_dir)
    app.local_metadata_manager.connect('new-metadata', on_new_metadata)

def setup_change_tracker():
    Item.change_tracker = ItemChangeTracker()

def on_new_metadata(metadata_manager, new_metadata):
    # Get all items that have changed using one query.  This is much faster
    # than calling items_with_path_view() for each path.
    path_map = collections.defaultdict(list)
    all_paths = [filename_to_unicode(p).lower() for p in new_metadata.keys()]
    # It's possible for there to be more than 999 items in all_paths.  Split
    # up the query to avoid SQLite's host parametrs limit
    for paths in util.split_values_for_sqlite(all_paths):
        placeholders = ', '.join('?' for i in xrange(len(paths)))
        view = Item.make_view('lower(filename) IN (%s)' % placeholders, paths)
        for i in view:
            path_map[i.filename].append(i)

    for path, metadata in new_metadata.iteritems():
        for item in path_map[path]:
            # optimize signal_change.  An item will only change views because
            # of new metadata if it changes file type.
            can_change_views = (metadata.get('file_type') != item.file_type)
            item.update_from_metadata(metadata)
            item.signal_change(can_change_views=can_change_views)

def update_incomplete_metadata():
    """Restart medata updates for our items.  """
    app.local_metadata_manager.restart_incomplete()
