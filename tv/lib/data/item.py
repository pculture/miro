# Miro - an RSS based video player application
# Copyright (C) 2012
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

"""miro.data.item -- Defines ItemInfo and describes how to create them

ItemInfo is the read-only interface to database items.  To create one you need
to run a SELECT on the database and pass in the data from one row.

column_info() and join_sql() describe what columns need to be selected and how
to join the tables together in order to create an ItemInfo.
"""

import datetime
import itertools
import functools
import logging
import os

from miro import app
from miro import displaytext
from miro.fileobject import FilenameType
from miro import filetypes
from miro import fileutil
from miro import prefs
from miro import schema
from miro import util
from miro.gtcache import gettext as _
from miro.plat import resources
from miro.plat.utils import PlatformFilenameType

def _unicode_to_filename(unicode_value):
    # Convert a unicode value from the database to FilenameType
    # FIXME: This code is not very good and should be replaces as part of
    # #13182
    if unicode_value is not None and PlatformFilenameType != unicode:
        return unicode_value.encode('utf-8')
    else:
        return unicode_value

class SelectColumn(object):
    """Describes a single column that we select for ItemInfo.

    :attribute table: name of the table that contains the column
    :attribute column: column nabe
    :attribute attr_name: attribute name in ItemInfo
    """

    # _schema_map maps (table, column) tuples to their SchemaItem objects
    _schema_map = {}
    for object_schema in (schema.object_schemas +
                          schema.device_object_schemas +
                          schema.sharing_object_schemas):
        for column_name, schema_item in object_schema.fields:
            _schema_map[object_schema.table_name, column_name] = schema_item

    def __init__(self, table, column, attr_name=None):
        if attr_name is None:
            attr_name = column
        self.table = table
        self.column = column
        self.attr_name = attr_name

    def sqlite_type(self):
        """Get the sqlite type specification for this column."""
        schema_item = self._schema_map[self.table, self.column]
        return app.db.get_sqlite_type(schema_item)

class ItemSelectInfo(object):
    """Describes query the data needed for an ItemInfo."""

    # name of the main item table
    table_name = 'item'
    # SelectColumn objects for each attribute of ItemInfo
    select_columns = [
        SelectColumn('item', 'id'),
        SelectColumn('item', 'new'),
        SelectColumn('item', 'title'),
        SelectColumn('item', 'entry_title'),
        SelectColumn('item', 'torrent_title'),
        SelectColumn('item', 'feed_id'),
        SelectColumn('item', 'parent_id'),
        SelectColumn('item', 'parent_title'),
        SelectColumn('item', 'downloader_id'),
        SelectColumn('item', 'is_file_item'),
        SelectColumn('item', 'pending_manual_download'),
        SelectColumn('item', 'pending_reason'),
        SelectColumn('item', 'expired'),
        SelectColumn('item', 'keep'),
        SelectColumn('item', 'creation_time', 'date_added'),
        SelectColumn('item', 'downloaded_time'),
        SelectColumn('item', 'watched_time'),
        SelectColumn('item', 'last_watched'),
        SelectColumn('item', 'subtitle_encoding'),
        SelectColumn('item', 'is_container_item'),
        SelectColumn('item', 'release_date'),
        SelectColumn('item', 'duration', 'duration_ms'),
        SelectColumn('item', 'screenshot', 'screenshot_path_unicode'),
        SelectColumn('item', 'resume_time'),
        SelectColumn('item', 'license'),
        SelectColumn('item', 'rss_id'),
        SelectColumn('item', 'entry_description'),
        SelectColumn('item', 'enclosure_type', 'mime_type'),
        SelectColumn('item', 'enclosure_format'),
        SelectColumn('item', 'enclosure_size'),
        SelectColumn('item', 'link', 'permalink'),
        SelectColumn('item', 'payment_link'),
        SelectColumn('item', 'comments_link'),
        SelectColumn('item', 'url'),
        SelectColumn('item', 'was_downloaded'),
        SelectColumn('item', 'filename', 'filename_unicode'),
        SelectColumn('item', 'play_count'),
        SelectColumn('item', 'skip_count'),
        SelectColumn('item', 'cover_art', 'cover_art_path_unicode'),
        SelectColumn('item', 'description', 'metadata_description'),
        SelectColumn('item', 'album'),
        SelectColumn('item', 'album_artist'),
        SelectColumn('item', 'artist'),
        SelectColumn('item', 'track'),
        SelectColumn('item', 'album_tracks'),
        SelectColumn('item', 'year'),
        SelectColumn('item', 'genre'),
        SelectColumn('item', 'rating'),
        SelectColumn('item', 'file_type'),
        SelectColumn('item', 'has_drm'),
        SelectColumn('item', 'show'),
        SelectColumn('item', 'size'),
        SelectColumn('item', 'episode_id'),
        SelectColumn('item', 'episode_number'),
        SelectColumn('item', 'season_number'),
        SelectColumn('item', 'kind'),
        SelectColumn('item', 'net_lookup_enabled'),
        SelectColumn('item', 'eligible_for_autodownload'),
        SelectColumn('item', 'thumbnail_url'),
        SelectColumn('feed', 'orig_url', 'feed_url'),
        SelectColumn('feed', 'expire', 'feed_expire'),
        SelectColumn('feed', 'expire_timedelta', 'feed_expire_timedelta'),
        SelectColumn('feed', 'autoDownloadable', 'feed_auto_downloadable'),
        SelectColumn('feed', 'getEverything', 'feed_get_everything'),
        SelectColumn('feed', 'thumbnail_path', 'feed_thumbnail_path_unicode'),
        SelectColumn('icon_cache', 'filename', 'icon_cache_path_unicode'),
        SelectColumn('remote_downloader', 'content_type',
                      'downloader_content_type'),
        SelectColumn('remote_downloader', 'state', 'downloader_state'),
        SelectColumn('remote_downloader', 'reason_failed'),
        SelectColumn('remote_downloader', 'short_reason_failed'),
        SelectColumn('remote_downloader', 'type', 'downloader_type'),
        SelectColumn('remote_downloader', 'retry_time'),
        SelectColumn('remote_downloader', 'retry_count'),
        SelectColumn('remote_downloader', 'eta', '_eta'),
        SelectColumn('remote_downloader', 'rate', '_rate'),
        SelectColumn('remote_downloader', 'upload_rate', '_upload_rate'),
        SelectColumn('remote_downloader', 'current_size', 'downloaded_size'),
        SelectColumn('remote_downloader', 'total_size', 'downloader_size'),
        SelectColumn('remote_downloader', 'upload_size'),
        SelectColumn('remote_downloader', 'activity', 'downloader_activity'),
        SelectColumn('remote_downloader', 'seeders'),
        SelectColumn('remote_downloader', 'leechers'),
        SelectColumn('remote_downloader', 'connections'),
    ]
    # name of the column that stores video paths
    path_column = 'filename'

    # how to join the main table to other tables.  Maps table names to
    # (item_column, other_column) tuples
    join_info = {
        'feed': ('feed_id', 'id'),
        'playlist_item_map': ('id', 'item_id'),
        'remote_downloader': ('downloader_id', 'id'),
        'icon_cache': ('icon_cache_id', 'id'),
        'item_fts': ('id', 'docid'),
    }

    def __init__(self):
        self.joined_tables = set(c.table for c in self.select_columns
                                 if c.table != self.table_name)

    def can_join_to(self, table):
        """Can we join to a table."""
        return table in self.join_info

    def join_sql(self, table=None, join_type='LEFT JOIN'):
        """Get an expression to join the main table to other tables.

        :param table: name of the table to join to, or None to join to all
        tables used in select_columns
        """
        if table is not None:
            item_column, other_column = self.join_info[table]
            return '%s %s ON %s.%s=%s.%s' % (join_type, table,
                                             self.table_name, item_column,
                                             table, other_column)
        else:
            return '\n'.join(self.join_sql(table)
                             for table in self.joined_tables)

    def item_join_column(self, table):
        """Get the item table column used to join to another table."""
        return self.join_info[table][0]

# ItemInfo has a couple of tricky things going on for it:
#  - We need to support both selecting from the main database and the device
#    database.  So we need a flexible way to map items in the result row to
#    attributes
#  - We want to create items quickly.  We don't want to do a bunch of work in
#    the constructor
#
# The solution we use is a metaclass that takes a ItemSelectInfo and creates a
# bunch of class descriptors to implement the attributes by reading from a
# result row
class ItemInfoAttributeGetter(object):
    def __init__(self, index):
        self.index = index

    def __get__(self, instance, owner):
        if instance is None:
            raise AttributeError("class attribute not supported")
        return instance.row_data[self.index]

class ItemInfoMeta(type):
    """Metaclass for ItemInfo.

    It depends on ItemInfo and all subclasses doing a couple things:
        - defining a class attribute called "select_info" that holds a
          ItemSelectInfo object.
        - storing the result row from sqlite in an instance attribute called
          "row_data"
    """
    def __new__(cls, classname, bases, dct):
        count = itertools.count()
        select_info = dct.get('select_info')
        if select_info is not None:
            for select_column in select_info.select_columns:
                attribute = ItemInfoAttributeGetter(count.next())
                dct[select_column.attr_name] = attribute
        return type.__new__(cls, classname, bases, dct)

class ItemInfoBase(object):
    """ItemInfo represents a row in one of the item lists.

    This work similarly to the miro.item.Item class, except it's read-only.
    Subclases of this handle items from the main database, device database,
    and sharing database
    """

    __metaclass__ = ItemInfoMeta

    #: ItemSelectInfo object that describes what to select to create an
    #: ItemInfoMeta
    select_info = None
    html_stripper = util.HTMLStripper()

    # default values for columns from the item table.  For DeviceItemInfo and
    # SharingItemInfo, we will use these for columns that don't exist in their
    # item table.
    date_added = None
    watched_time = None
    last_watched = None
    parent_id = None
    rating = None
    album_tracks = None
    new = False
    keep = True
    was_downloaded = False
    expired = False
    eligible_for_autodownload = False
    is_file_item = True
    is_container_item = False
    icon_cache_path_unicode = None
    subtitle_encoding = None
    release_date = None
    parent_title = None
    feed_url = None
    feed_thumbnail_path_unicode = None
    license = None
    rss_id = None
    entry_title = None
    entry_description = None
    torrent_title = None
    permalink = None
    payment_link = None
    comments_link = None
    thumbnail_url = None
    url = None
    size = None
    enclosure_size = None
    enclosure_type = None
    mime_type = None
    enclosure_format = None
    auto_sync = None
    screenshot_path_unicode = None
    cover_art_path_unicode = None
    resume_time = 0
    play_count = 0
    skip_count = 0
    net_lookup_enabled = False
    has_drm = False
    album = None
    kind = None
    duration_ms = None
    metadata_description = None
    show = None
    file_type = None
    artist = None
    episode_id = None
    track = None
    year = None
    genre = None
    episode_number = None
    season_number = None
    album_artist = None
    # default values for columns in the remote_downloader table
    downloader_size = None
    downloader_type = None
    seeders = None
    upload_size = None
    downloader_id = None
    _rate = None
    connections = None
    downloaded_time = None
    downloaded_size = None
    pending_reason = None
    retry_time = None
    retry_count = None
    short_reason_failed = None
    reason_failed = None
    leechers = None
    _eta = None
    pending_manual_download = None
    downloader_state = None
    _upload_rate = None
    downloader_activity = None
    downloader_content_type = None
    # default values for columns in the feed table
    feed_id = None
    feed_get_everything = None
    feed_auto_downloadable = False
    feed_expire_timedelta = None
    feed_expire = u'never'

    def __init__(self, row_data):
        """Create an ItemInfo object.

        :param row_data: data from sqlite.  There should be a value for each
        SelectColumn that column_info() returns.
        """
        self.row_data = row_data

    def __hash__(self):
        return hash(self.row_data)

    def __eq__(self, other):
        return self.row_data == other.row_data

    # NOTE: The previous ItemInfo API was all attributes, so we use properties
    # to try to match that.

    @property
    def filename(self):
        return _unicode_to_filename(self.filename_unicode)

    @property
    def downloaded(self):
        return self.has_filename

    @property
    def has_filename(self):
        return self.filename_unicode is not None

    @property
    def icon_cache_path(self):
        return _unicode_to_filename(self.icon_cache_path_unicode)

    @property
    def cover_art_path(self):
        return _unicode_to_filename(self.cover_art_path_unicode)

    @property
    def screenshot_path(self):
        return _unicode_to_filename(self.screenshot_path_unicode)

    @property
    def feed_thumbnail_path(self):
        return _unicode_to_filename(self.feed_thumbnail_path_unicode)

    @property
    def is_playable(self):
        return self.has_filename and self.file_type != u'other'

    @property
    def is_torrent(self):
        return self.downloader_type == u'BitTorrent'

    @property
    def is_torrent_folder(self):
        return self.is_torrent and self.is_container_item

    def looks_like_torrent(self):
        return self.is_torrent or filetypes.is_torrent_filename(self.url)

    @property
    def description(self):
        if self.metadata_description:
            return self.metadata_description
        elif self.entry_description:
            return self.entry_description
        else:
            return None

    @property
    def description_stripped(self):
        if not hasattr(self, '_description_stripped'):
            self._description_stripped = ItemInfo.html_stripper.strip(
                self.description)
        return self._description_stripped

    @property
    def thumbnail(self):
        if (self.cover_art_path_unicode is not None
            and fileutil.exists(self.cover_art_path)):
            return self.cover_art_path
        if (self.icon_cache_path_unicode is not None and
            fileutil.exists(self.icon_cache_path)):
            return self.icon_cache_path
        if (self.screenshot_path_unicode is not None
            and fileutil.exists(self.screenshot_path)):
            return self.screenshot_path
        if self.is_container_item:
            return resources.path("images/thumb-default-folder.png")
        if self.feed_thumbnail_path is not None:
            return self.feed_thumbnail_path
        # default
        if self.file_type == u'audio':
            return resources.path("images/thumb-default-audio.png")
        else:
            return resources.path("images/thumb-default-video.png")

    @property
    def is_external(self):
        """Is this an externally downloaded item."""
        return False

    @property
    def remote(self):
        return self.source_type == u'sharing'

    @property
    def device(self):
        return self.source_type == u'device'

    @property
    def has_shareable_url(self):
        """Does this item have a URL that the user can share with
        others?

        This returns True when the item has a non-file URL.
        """
        return self.url is not None and not self.url.startswith(u"file:")

    @property
    def file_format(self):
        """Returns string with the format of the video.
        """
        if self.looks_like_torrent():
            return u'.torrent'

        if self.enclosure_format is not None:
            return self.enclosure_format

        return filetypes.calc_file_format(self.filename,
                                          self.downloader_content_type)

    @property
    def video_watched(self):
        return self.watched_time is not None

    @property
    def expiration_date(self):
        """When will this item expire?

        :returns: a datetime.datetime object or None if it doesn't expire.
        """
        if (self.watched_time is None or self.keep or
            not self.has_filename or self.is_file_item):
            return None

        if self.feed_expire == u'never':
            return None
        elif self.feed_expire == u"feed":
            if self.feed_expire_timedelta is None:
                logging.warn("feed_expire is 'feed', but "
                             "feed_expire_timedelta is None")
                return None
            expire_time = self.feed_expire_time_parsed
            if expire_time is None:
                logging.warn("feed_expire is 'feed', but "
                             "feed_expire_time_parsed failed")
                return None
        elif self.feed_expire == u"system":
            days = app.config.get(prefs.EXPIRE_AFTER_X_DAYS)
            if days <= 0:
                return None
            expire_time = datetime.timedelta(days=days)
        else:
            raise AssertionError("Unknown expire value: %s" % self.feed_expire)
        return self.watched_time + expire_time

    @property
    def feed_expire_time_parsed(self):
        if self.feed_expire_timedelta is None:
            return None
        try:
            expire_time_split = self.feed_expire_timedelta.split(":")
            return datetime.timedelta(*(int(c) for c in expire_time_split))
        except StandardError:
            logging.warn("Error parsing feed_expire_timedelta", exc_info=True)
            return None

    @property
    def expiration_date_text(self):
        return displaytext.expiration_date(self.expiration_date)

    @property
    def can_be_saved(self):
        return self.has_filename and not self.keep

    @property
    def is_download(self):
        return (self.downloader_state in ('downloading', 'paused', 'offline') or
                self.pending_manual_download)

    @property
    def is_paused(self):
        return self.downloader_state == 'paused'

    @property
    def is_seeding(self):
        return self.downloader_state == 'uploading'

    @property
    def startup_activity(self):
        if self.pending_manual_download:
            return self.pending_reason
        elif self.downloader_activity:
            return self.downloader_activity
        elif self.is_retrying:
            return self._startup_activity_retry
        else:
            return _("starting up...")

    @property
    def is_retrying(self):
        return self.retry_count is not None and self.retry_time is not None

    @property
    def _startup_activity_retry(self):
        if self.retry_time > datetime.datetime.now():
            retry_delta = self.retry_time - datetime.datetime.now()
            time_str = displaytext.time_string(retry_delta.seconds)
            return _('no connection - retrying in %(time)s', {"time": time_str})
        else:
            return _('no connection - retrying soon')

    @property
    def download_progress(self):
        """Calculate how for a download has progressed.

        :returns: [0.0, 1.0] depending on how much has been downloaded, or
        None if we don't have the info to make this calculation
        """
        if self.downloaded_size in (0, None):
            # Download hasn't started yet.  Give the downloader a little more
            # time before deciding that the eta is unknown.
            return 0.0
        if self.downloaded_size is None or self.downloader_size is None:
            # unknown total size, return None
            return None
        return float(self.downloaded_size) / self.downloader_size

    @property
    def eta(self):
        if self.is_paused:
            return None
        else:
            return self._eta

    @property
    def rate(self):
        if self.is_paused:
            return None
        else:
            return self._rate

    @property
    def upload_rate(self):
        if self.is_paused:
            return None
        else:
            return self._upload_rate

    @property
    def download_rate_text(self):
        return displaytext.download_rate(self.rate)

    @property
    def upload_rate_text(self):
        return displaytext.download_rate(self.upload_rate)

    @property
    def upload_ratio(self):
        if self.downloaded_size:
            return float(self.upload_size) / self.downloaded_size
        else:
            return 0.0

    @property
    def upload_ratio_text(self):
        return "%0.2f" % self.upload_ratio

    @property
    def eta_text(self):
        return displaytext.time_string_0_blank(self.eta)

    @property
    def downloaded_size_text(self):
        return displaytext.size_string(self.downloaded_size)

    @property
    def upload_size_text(self):
        return displaytext.size_string(self.upload_size)

    @property
    def is_failed_download(self):
        return self.downloader_state == 'failed'

    @property
    def pending_auto_dl(self):
        return (self.feed_auto_downloadable and
                not self.was_downloaded and
                self.feed_auto_downloadable and
                (self.feed_get_everything or self.eligible_for_autodownload))

    @property
    def title_sort_key(self):
        return util.name_sort_key(self.title)

    @property
    def artist_sort_key(self):
        return util.name_sort_key(self.artist)

    @property
    def album_sort_key(self):
        return util.name_sort_key(self.album)

    @property
    def has_parent(self):
        return self.parent_id is not None

    @property
    def parent_title_for_sort(self):
        """value to use for sorting by parent title.

        This will sort items by their parent title (torrent folder name or
        feed name, but if 2 torrents have the same name, or a torrent and a
        feed have the same name, then they will be separated)
        """
        return (self.parent_title, self.feed_id, self.parent_id)

    @property
    def album_artist_sort_key(self):
        if self.album_artist:
            return util.name_sort_key(self.album_artist)
        else:
            return self.artist_sort_key

    @property
    def description_oneline(self):
        return self.description_stripped[0].replace('\n', '$')

    @property
    def auto_rating(self):
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

    @property
    def duration(self):
        if self.duration_ms is None:
            return None
        else:
            return self.duration_ms // 1000

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.title)

    def __str__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.title)

def _fetch_item_rows(connection, item_ids, select_info):
    """Fetch rows for fetch_item_infos and fetch_device_item_infos."""

    columns = ','.join('%s.%s' % (c.table, c.column)
                       for c in select_info.select_columns)
    item_ids = ','.join(str(item_id) for item_id in item_ids)
    sql = ("SELECT %s FROM %s %s WHERE %s.id IN (%s)" %
           (columns, select_info.table_name, select_info.join_sql(),
            select_info.table_name, item_ids))
    return connection.execute(sql)

def fetch_item_infos(connection, item_ids):
    """Fetch a list of ItemInfos """
    result_set = _fetch_item_rows(connection, item_ids, ItemSelectInfo())
    return [ItemInfo(row) for row in result_set]

def fetch_device_item_infos(device, item_ids):
    """Fetch a list of ItemInfos for a device"""
    result_set = _fetch_item_rows(device.db_info.db.connection,
                                  item_ids, DeviceItemSelectInfo())
    return [DeviceItemInfo(device.id, row) for row in result_set]

class ItemInfo(ItemInfoBase):
    source_type = 'database'
    select_info = ItemSelectInfo()

    @property
    def is_external(self):
        if self.is_file_item:
            return not self.has_parent
        else:
            return self.feed_url == 'dtv:manualFeed'

class DBErrorItemInfo(ItemInfoBase):
    """DBErrorItemInfo is used as a placeholder when we get DatabaseErrors
    """

    def __init__(self, id):
        ItemInfoBase.__init__(self, row_data=(id,))
        self.id = id
        self.title = _('Database Error')
        self.filename_unicode = None
        self.source_type = 'dberror'

class DeviceItemSelectInfo(ItemSelectInfo):
    """ItemSelectInfo for DeviceItems."""

    # name of the main item table
    table_name = 'device_item'
    # SelectColumn objects for each attribute of ItemInfo
    select_columns = [
        SelectColumn('device_item', 'id'),
        SelectColumn('device_item', 'title'),
        SelectColumn('device_item', 'creation_time', 'date_added'),
        SelectColumn('device_item', 'watched_time'),
        SelectColumn('device_item', 'last_watched'),
        SelectColumn('device_item', 'subtitle_encoding'),
        SelectColumn('device_item', 'release_date'),
        SelectColumn('device_item', 'parent_title'),
        SelectColumn('device_item', 'feed_url'),
        SelectColumn('device_item', 'license'),
        SelectColumn('device_item', 'rss_id'),
        SelectColumn('device_item', 'entry_title'),
        SelectColumn('device_item', 'torrent_title'),
        SelectColumn('device_item', 'entry_description'),
        SelectColumn('device_item', 'permalink'),
        SelectColumn('device_item', 'payment_link'),
        SelectColumn('device_item', 'comments_link'),
        SelectColumn('device_item', 'url'),
        SelectColumn('device_item', 'size'),
        SelectColumn('device_item', 'enclosure_size'),
        SelectColumn('device_item', 'enclosure_type', 'mime_type'),
        SelectColumn('device_item', 'enclosure_format'),
        SelectColumn('device_item', 'filename', 'filename_unicode'),
        SelectColumn('device_item', 'resume_time'),
        SelectColumn('device_item', 'play_count'),
        SelectColumn('device_item', 'skip_count'),
        SelectColumn('device_item', 'auto_sync'),
        SelectColumn('device_item', 'screenshot', 'screenshot_path_unicode'),
        SelectColumn('device_item', 'duration', 'duration_ms'),
        SelectColumn('device_item', 'cover_art', 'cover_art_path_unicode'),
        SelectColumn('device_item', 'description', 'metadata_description'),
        SelectColumn('device_item', 'album'),
        SelectColumn('device_item', 'album_artist'),
        SelectColumn('device_item', 'artist'),
        SelectColumn('device_item', 'track'),
        SelectColumn('device_item', 'album_tracks'),
        SelectColumn('device_item', 'year'),
        SelectColumn('device_item', 'genre'),
        SelectColumn('device_item', 'rating'),
        SelectColumn('device_item', 'file_type'),
        SelectColumn('device_item', 'has_drm'),
        SelectColumn('device_item', 'show'),
        SelectColumn('device_item', 'episode_id'),
        SelectColumn('device_item', 'episode_number'),
        SelectColumn('device_item', 'season_number'),
        SelectColumn('device_item', 'kind'),
        SelectColumn('device_item', 'net_lookup_enabled'),
    ]

    join_info = {
        'item_fts': ('id', 'docid'),
    }

class DeviceItemInfo(ItemInfoBase):
    """ItemInfo for devices """

    select_info = DeviceItemSelectInfo()
    source_type = 'device'

    def __init__(self, device_info, row_data):
        """Create an ItemInfo object.

        :param device_info: DeviceInfo object for the device
        :param row_data: data from sqlite.  There should be a value for each
        SelectColumn that column_info() returns.
        """
        self.device_info = device_info
        self.device_id = device_info.id
        self.mount = device_info.mount
        self.row_data = row_data

    @property
    def filename(self):
        relative_filename = ItemInfo.filename.__get__(self, self.__class__)
        return os.path.join(self.mount, relative_filename)

class SharingItemSelectInfo(ItemSelectInfo):
    """ItemSelectInfo for SharingItems."""

    # name of the main item table
    table_name = 'sharing_item'
    # SelectColumn objects for each attribute of ItemInfo
    select_columns = [
        SelectColumn('sharing_item', 'id'),
        SelectColumn('sharing_item', 'daap_id'),
        SelectColumn('sharing_item', 'video_path'),
        SelectColumn('sharing_item', 'title'),
        SelectColumn('sharing_item', 'description', 'metadata_description'),
        SelectColumn('sharing_item', 'file_type'),
        SelectColumn('sharing_item', 'file_format'),
        SelectColumn('sharing_item', 'duration', 'duration_ms'),
        SelectColumn('sharing_item', 'size'),
        SelectColumn('sharing_item', 'artist'),
        SelectColumn('sharing_item', 'album_artist'),
        SelectColumn('sharing_item', 'album'),
        SelectColumn('sharing_item', 'year'),
        SelectColumn('sharing_item', 'genre'),
        SelectColumn('sharing_item', 'track'),
        SelectColumn('sharing_item', 'kind'),
        SelectColumn('sharing_item', 'show'),
        SelectColumn('sharing_item', 'season_number'),
        SelectColumn('sharing_item', 'episode_id'),
        SelectColumn('sharing_item', 'episode_number'),
        SelectColumn('sharing_item', 'host'),
        SelectColumn('sharing_item', 'port'),
        SelectColumn('sharing_item', 'address'),
    ]
    path_column = 'video_path'

    join_info = {
        'item_fts': ('id', 'docid'),
        'sharing_item_playlist_map': ('daap_id', 'item_id'),
    }


class SharingItemInfo(ItemInfoBase):
    """ItemInfo for devices """

    select_info = SharingItemSelectInfo()
    source_type = 'sharing'

    def __init__(self, share_info, row_data):
        """Create an ItemInfo object.

        :param share_info: SharingInfo object for the device
        :param row_data: data from sqlite.  There should be a value for each
        SelectColumn that column_info() returns.
        """
        self.share_info = share_info
        self.row_data = row_data

    @property
    def filename(self):
        # FIXME: code from the old ItemInfo.  Needs some serious cleanup
        # For daap, sent it to be the same as http as it is basically
        # http with a different port.
        def daap_handler(path, host, port):
            return 'http://%s:%s%s' % (host, port, path)
        fn = FilenameType(self.video_path)
        fn.set_urlize_handler(daap_handler,
                              [self.share_info.host, self.share_info.port])
        return fn

    @property
    def has_filename(self):
        # all sharing items have files on the share
        return True

class ItemSource(object):
    """Create ItemInfo objects.

    ItemSource stores info about a database that stores items and contains the
    logic to build an ItemInfo from a SELECT result.  It tries to abstract
    away the differences between items on the main database and device
    databases.

    :attribute select_info: ItemSelectInfo for a database
    :attribute connection_pool: ConnectionPool for the same database
    """

    select_info = ItemSelectInfo()

    def __init__(self):
        self.connection_pool = app.connection_pools.get_main_pool()

    def get_connection(self):
        """Get a database connection to use.

        A database connection must be created before using any of the query
        methods.  Call release_connection() once the connection is finished
        with.
        """
        return self.connection_pool.get_connection()

    def release_connection(self, connection):
        """Release a connection returned by get_connection().

        Once a connection is released it should not be used anymore.
        """
        self.connection_pool.release_connection(connection)

    def wal_mode(self):
        """Is this database using WAL mode for transactions?"""
        return self.connection_pool.wal_mode

    def make_item_info(self, row_data):
        """Create an ItemInfo from a result row."""
        return ItemInfo(row_data)

class DeviceItemSource(ItemSource):

    select_info = DeviceItemSelectInfo()

    def __init__(self, device_info):
        self.connection_pool = \
                app.connection_pools.get_device_pool(device_info.id)
        self.device_info = device_info

    def make_item_info(self, row_data):
        return DeviceItemInfo(self.device_info, row_data)

class SharingItemSource(ItemSource):
    select_info = SharingItemSelectInfo()

    def __init__(self, share_info):
        self.connection_pool = \
                app.connection_pools.get_sharing_pool(share_info.id)
        self.share_info = share_info

    def make_item_info(self, row_data):
        return SharingItemInfo(self.share_info, row_data)
