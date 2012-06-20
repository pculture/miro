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

"""``miro.schema`` -- The schema module is responsible for defining
what data in the database gets stored on disk.

The goals of this modules are:

* Clearly defining which data from DDBObjects gets stored and which
  doesn't.
* Validating that all data we write can be read back in
* Making upgrades of the database schema as easy as possible

Module-level variables:

* ``object_schemas`` -- Schemas to use with the current database.
* ``VERSION`` -- Current schema version.  If you change the schema you
  must bump this number and add a function in the databaseupgrade
  module.

Go to the bottom of this file for the current database schema.
"""

import datetime
import time
from types import NoneType
from miro.plat.utils import PlatformFilenameType

class ValidationError(StandardError):
    """Error thrown when we try to save invalid data."""
    pass

class ValidationWarning(Warning):
    """Warning issued when we try to restore invalid data."""
    pass

class SchemaItem(object):
    """SchemaItem represents a single attribute that gets stored on
    disk.

    SchemaItem is an abstract class.  Subclasses of SchemaItem such as
    SchemaAttr, SchemaList are used in actual object schemas.

    Member variables:

    * ``noneOk`` -- specifies if None is a valid value for this attribute
    """

    def __init__(self, noneOk=False):
        self.noneOk = noneOk

    def validate(self, data):
        """Validate that data is a valid value for this SchemaItem.

        validate is "dumb" when it comes to container types like
        SchemaList, etc.  It only checks that the container is the
        right type, not its children.  This isn't a problem because
        saveObject() calls validate() recursively on all the data it
        saves, therefore validate doesn't have to recursively validate
        things.
        """

        if data is None:
            if not self.noneOk:
                raise ValidationError("None value is not allowed")
        return True

    def validateType(self, data, correctType):
        """Helper function that many subclasses use"""
        if data is not None and not isinstance(data, correctType):
            raise ValidationError("%r (type: %s) is not a %s" %
                                  (data, type(data), correctType))

    def validateTypes(self, data, possibleTypes, msg=""):
        if data is None:
            return
        for t in possibleTypes:
            if isinstance(data, t):
                return
        raise ValidationError("%r (type: %s) is not any of: %s (%s)" %
                              (data, type(data), possibleTypes, msg))

class SchemaSimpleItem(SchemaItem):
    """Base class for SchemaItems for simple python types."""

class SchemaBool(SchemaSimpleItem):
    """Defines the SchemaBool type."""
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, bool)

class SchemaFloat(SchemaSimpleItem):
    """Defines the SchemaFloat type."""
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, float)

class SchemaString(SchemaSimpleItem):
    """Defines the SchemaString type."""
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, unicode)

class SchemaBinary(SchemaSimpleItem):
    """Defines the SchemaBinary type for blobs."""
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, str)

class SchemaFilename(SchemaSimpleItem):
    """Defines the SchemaFilename type."""
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, PlatformFilenameType)

class SchemaURL(SchemaSimpleItem):
    """Defines the SchemaURL type."""
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, unicode)
        if data:
            try:
                data.encode('ascii')
            except UnicodeEncodeError:
                ValidationError(u"URL (%s) is not ASCII" % data)

class SchemaInt(SchemaSimpleItem):
    """Defines the SchemaInt type."""
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateTypes(data, [int, long])

class SchemaDateTime(SchemaSimpleItem):
    """Defines the SchemaDateTime type."""
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, datetime.datetime)

class SchemaTimeDelta(SchemaSimpleItem):
    """Defines the SchemaTimeDelta type."""
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, datetime.timedelta)

class SchemaMultiValue(SchemaSimpleItem):
    """Stores integer, boolean, string, or unicode data"""
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateTypes(data, [int, long, bool, str, unicode])

class SchemaStringSet(SchemaItem):
    """Stores a set of strings.

    This is stored in the database as a long string that separated by a
    delimiter (by default ":").
    """

    def __init__(self, noneOk=False, delimiter=':'):
        SchemaItem.__init__(self, noneOk)
        self.delimiter = delimiter

    def validate(self, data):
        if data is None:
            super(SchemaStringSet, self).validate(data)
            return
        self.validateType(data, set)
        for obj in data:
            self.validateType(obj, unicode)
            if self.delimiter in obj:
                raise ValidationError("%r contains the delimiter (%s)" %
                        (data, self.delimiter))

class SchemaReprContainer(SchemaItem):
    """SchemaItem saved using repr() to save nested lists, dicts and
    tuples that store simple types.  The look is similar to JSON, but
    supports a couple different things, for example unicode and str
    values are distinct.  The types that we support are bool, int,
    long, float, unicode, None and datetime.  Dictionary keys can also
    be byte strings (AKA str types)
    """

    VALID_TYPES = [bool, int, long, float, unicode, NoneType,
                   datetime.datetime, time.struct_time]

    VALID_KEY_TYPES = VALID_TYPES + [str]

    def validate(self, data):
        if data is None:
            # let the super class handle the noneOkay attribute
            super(SchemaReprContainer, self).validate(data)
            return
        memory = set()
        to_validate = [data]

        while to_validate:
            obj = to_validate.pop()
            if id(obj) in memory:
                continue
            else:
                memory.add(id(obj))

            if isinstance(obj, list) or isinstance(obj, tuple):
                for item in obj:
                    to_validate.append(item)
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    self.validateTypes(key, self.VALID_KEY_TYPES)
                    to_validate.append(value)
            else:
                self.validateTypes(obj, self.VALID_TYPES)

class SchemaTuple(SchemaReprContainer):
    """Special case of SchemaReprContainer that stores a simple tuple
    """
    def __init__(self, *childSchemas, **kargs):
        if 'noneOk' in kargs:
            noneOk = kargs['noneOk']
        else:
            noneOk = False
        super(SchemaTuple, self).__init__(noneOk)
        self.childSchemas = childSchemas

    def validate(self, data):
        if data is None:
            super(SchemaTuple, self).validate(data)
            return
        self.validateType(data, tuple)
        for i, value in enumerate(data):
            try:
                self.childSchemas[i].validate(value)
            except ValidationError:
                raise ValidationError("%r (index: %s) has the wrong type" %
                                      (value, i))

class SchemaList(SchemaReprContainer):
    """Special case of SchemaReprContainer that stores a simple list

    All values in the list must have the same type.
    """
    def __init__(self, childSchema, noneOk=False):
        super(SchemaList, self).__init__(noneOk)
        self.childSchema = childSchema

    def validate(self, data):
        if data is None:
            super(SchemaList, self).validate(data)
            return
        self.validateType(data, list)
        for i, value in enumerate(data):
            try:
                self.childSchema.validate(value)
            except ValidationError:
                raise ValidationError("%r (index: %s) has the wrong type" %
                                      (value, i))

class SchemaDict(SchemaReprContainer):
    """Special case of SchemaReprContainer that stores a simple dict.

    All keys and values must have the same type.
    """

    def __init__(self, keySchema, valueSchema, noneOk=False):
        super(SchemaDict, self).__init__(noneOk)
        self.keySchema = keySchema
        self.valueSchema = valueSchema

    def validate(self, data):
        if data is None:
            super(SchemaDict, self).validate(data)
            return
        self.validateType(data, dict)
        for key, value in data.items():
            try:
                self.keySchema.validate(key)
            except ValidationError:
                raise ValidationError("key %r has the wrong type: %s" % (key, type(key)))
            try:
                self.valueSchema.validate(value)
            except ValidationError:
                raise ValidationError("value %r (key: %r) has the wrong type: %s"
                        % (value, key, type(value)))

class SchemaObject(SchemaItem):
    """SchemaObject type."""
    def __init__(self, klass, noneOk=False):
        super(SchemaObject, self).__init__(noneOk)
        self.klass = klass

    def validate(self, data):
        super(SchemaObject, self).validate(data)
        self.validateType(data, self.klass)

class ObjectSchema(object):
    """The schema to save/restore an object with.  Object schema isn't
    a SchemaItem, it's the schema for an entire object.

    Member variables:

    * ``klass`` -- the python class that this schema is for
    * ``table_name`` -- SQL table name to store the class in
    * ``fields`` -- list of (name, SchemaItem) pairs.  One item for
      each attribute that should be stored to disk.
    """

    @classmethod
    def ddb_object_classes(cls):
        return (cls.klass,)

    @classmethod
    def get_ddb_class(cls, restored_data):
        return cls.klass

    indexes = ()
    unique_indexes = ()

class MultiClassObjectSchema(ObjectSchema):
    """ObjectSchema where rows will be restored to different python
    classes.

    Instead of the klass attribute, MultiClassObjectSchema should
    define 2 class methods: ddb_object_classes() returns the list of
    all classes that this schema works with and get_ddb_class() which
    inputs a dictionary containing db data and return which class we
    should use to restore that row.
    """

from miro.database import DDBObject
from miro.databaselog import DBLogEntry
from miro.downloader import RemoteDownloader
from miro.feed import (Feed, FeedImpl, RSSFeedImpl, SavedSearchFeedImpl,
                       ScraperFeedImpl)
from miro.feed import (SearchFeedImpl, DirectoryWatchFeedImpl,
                       DirectoryFeedImpl, SearchDownloadsFeedImpl)
from miro.feed import ManualFeedImpl
from miro.folder import (HideableTab, ChannelFolder, PlaylistFolder,
                         PlaylistFolderItemMap)
from miro.guide import ChannelGuide
from miro.item import Item, FileItem
from miro.iconcache import IconCache
from miro.metadata import MetadataStatus, MetadataEntry
from miro.playlist import SavedPlaylist, PlaylistItemMap
from miro.tabs import TabOrder
from miro.theme import ThemeHistory
from miro.widgetstate import DisplayState, ViewState, GlobalState

class DDBObjectSchema(ObjectSchema):
    klass = DDBObject
    table_name = 'ddb_object'
    fields = [
        ('id', SchemaInt())
    ]

class IconCacheSchema (DDBObjectSchema):
    klass = IconCache
    table_name = 'icon_cache'
    fields = DDBObjectSchema.fields + [
        ('etag', SchemaString(noneOk=True)),
        ('modified', SchemaString(noneOk=True)),
        ('filename', SchemaFilename(noneOk=True)),
        ('url', SchemaURL(noneOk=True)),
        ]

class ItemSchema(MultiClassObjectSchema):
    table_name = 'item'

    @classmethod
    def ddb_object_classes(cls):
        return (Item, FileItem)

    @classmethod
    def get_ddb_class(cls, restored_data):
        if restored_data['is_file_item']:
            return FileItem
        else:
            return Item

    fields = DDBObjectSchema.fields + [
        ('is_file_item', SchemaBool()),
        ('new', SchemaBool()),
        ('title', SchemaString(noneOk=True)),
        ('feed_id', SchemaInt(noneOk=True)),
        ('downloader_id', SchemaInt(noneOk=True)),
        ('parent_id', SchemaInt(noneOk=True)),
        ('auto_downloaded', SchemaBool()),
        ('pending_manual_download', SchemaBool()),
        ('pending_reason', SchemaString()),
        ('expired', SchemaBool()),
        ('keep', SchemaBool()),
        ('creation_time', SchemaDateTime()),
        ('link_number', SchemaInt(noneOk=True)),
        ('icon_cache_id', SchemaInt(noneOk=True)),
        ('downloaded_time', SchemaDateTime(noneOk=True)),
        ('watched_time', SchemaDateTime(noneOk=True)),
        ('last_watched', SchemaDateTime(noneOk=True)),
        ('subtitle_encoding', SchemaString(noneOk=True)),
        ('is_container_item', SchemaBool(noneOk=True)),
        ('release_date', SchemaDateTime()),
        ('eligible_for_autodownload', SchemaBool()),
        ('duration', SchemaInt(noneOk=True)),
        ('screenshot', SchemaFilename(noneOk=True)),
        ('resume_time', SchemaInt()),
        ('channel_title', SchemaString(noneOk=True)),
        ('license', SchemaString(noneOk=True)),
        ('rss_id', SchemaString(noneOk=True)),
        ('thumbnail_url', SchemaURL(noneOk=True)),
        ('entry_title', SchemaString(noneOk=True)),
        ('torrent_title', SchemaString(noneOk=True)),
        ('entry_description', SchemaString(noneOk=False)),
        ('link', SchemaURL(noneOk=False)),
        ('payment_link', SchemaURL(noneOk=False)),
        ('comments_link', SchemaURL(noneOk=False)),
        ('url', SchemaURL(noneOk=False)),
        ('enclosure_size', SchemaInt(noneOk=True)),
        ('enclosure_type', SchemaString(noneOk=True)),
        ('enclosure_format', SchemaString(noneOk=True)),
        ('was_downloaded', SchemaBool()),
        ('filename', SchemaFilename(noneOk=True)),
        ('deleted', SchemaBool(noneOk=True)),
        ('short_filename', SchemaFilename(noneOk=True)),
        ('offset_path', SchemaFilename(noneOk=True)),
        ('play_count', SchemaInt()),
        ('skip_count', SchemaInt()),
        # metadata:
        ('cover_art', SchemaFilename(noneOk=True)),
        ('description', SchemaString(noneOk=True)),
        ('album', SchemaString(noneOk=True)),
        ('album_artist', SchemaString(noneOk=True)),
        ('artist', SchemaString(noneOk=True)),
        ('track', SchemaInt(noneOk=True)),
        ('album_tracks', SchemaInt(noneOk=True)),
        ('year', SchemaInt(noneOk=True)),
        ('genre', SchemaString(noneOk=True)),
        ('rating', SchemaInt(noneOk=True)),
        ('file_type', SchemaString(noneOk=True)),
        ('has_drm', SchemaBool(noneOk=True)),
        ('show', SchemaString(noneOk=True)),
        ('episode_id', SchemaString(noneOk=True)),
        ('episode_number', SchemaInt(noneOk=True)),
        ('season_number', SchemaInt(noneOk=True)),
        ('kind', SchemaString(noneOk=True)),
        ('net_lookup_enabled', SchemaBool()),
        ('metadata_title', SchemaString(noneOk=True)),
    ]

    indexes = (
            ('item_feed', ('feed_id',)),
            ('item_feed_visible', ('feed_id', 'deleted')),
            ('item_parent', ('parent_id',)),
            ('item_downloader', ('downloader_id',)),
            ('item_feed_downloader', ('feed_id', 'downloader_id',)),
            ('item_file_type', ('file_type',)),
            ('item_filename', ('filename',)),
    )

class FeedSchema(DDBObjectSchema):
    klass = Feed
    table_name = 'feed'
    fields = DDBObjectSchema.fields + [
        ('orig_url', SchemaURL()),
        ('baseTitle', SchemaString(noneOk=True)),
        ('errorState', SchemaBool()),
        ('loading', SchemaBool()),
        ('feed_impl_id', SchemaInt()),
        ('icon_cache_id', SchemaInt(noneOk=True)),
        ('folder_id', SchemaInt(noneOk=True)),
        ('searchTerm', SchemaString(noneOk=True)),
        ('userTitle', SchemaString(noneOk=True)),
        ('autoDownloadable', SchemaBool()),
        ('getEverything', SchemaBool()),
        ('maxNew', SchemaInt()),
        ('maxOldItems', SchemaInt(noneOk=True)),
        ('fallBehind', SchemaInt()),
        ('expire', SchemaString()),
        ('expireTime', SchemaTimeDelta(noneOk=True)),
        ('section', SchemaString()), # not used anymore
        ('visible', SchemaBool()),
    ]

    indexes = (
        ('feed_impl_key', ('feed_impl_id',)),
    )

class FeedImplSchema(DDBObjectSchema):
    klass = FeedImpl
    table_name = 'feed_impl'
    fields = DDBObjectSchema.fields + [
        ('url', SchemaURL()),
        ('ufeed_id', SchemaInt()),
        ('title', SchemaString(noneOk=True)),
        ('created', SchemaDateTime()),
        ('thumbURL', SchemaURL(noneOk=True)),
        ('updateFreq', SchemaInt()),
        ('initialUpdate', SchemaBool()),
    ]

class RSSFeedImplSchema(FeedImplSchema):
    klass = RSSFeedImpl
    table_name = 'rss_feed_impl'
    fields = FeedImplSchema.fields + [
        ('initialHTML', SchemaBinary(noneOk=True)),
        ('etag', SchemaString(noneOk=True)),
        ('modified', SchemaString(noneOk=True)),
    ]

class SavedSearchFeedImplSchema(FeedImplSchema):
    klass = SavedSearchFeedImpl
    table_name = 'saved_search_feed_impl'
    fields = FeedImplSchema.fields + [
        ('etag', SchemaDict(SchemaString(),SchemaString(noneOk=True))),
        ('modified', SchemaDict(SchemaString(),SchemaString(noneOk=True))),
    ]

    @staticmethod
    def handle_malformed_etag(row):
        return {}

    @staticmethod
    def handle_malformed_modified(row):
        return {}

class ScraperFeedImplSchema(FeedImplSchema):
    klass = ScraperFeedImpl
    table_name = 'scraper_feed_impl'
    fields = FeedImplSchema.fields + [
        ('initialHTML', SchemaBinary(noneOk=True)),
        ('initialCharset', SchemaString(noneOk=True)),
        ('linkHistory', SchemaReprContainer()),
    ]

    @staticmethod
    def handle_malformed_linkHistory(row):
        return {}

class SearchFeedImplSchema(SavedSearchFeedImplSchema):
    klass = SearchFeedImpl
    table_name = 'search_feed_impl'
    fields = SavedSearchFeedImplSchema.fields + [
        ('engine', SchemaString()),
        ('query', SchemaString()),
    ]

class DirectoryWatchFeedImplSchema(FeedImplSchema):
    klass = DirectoryWatchFeedImpl
    table_name = 'directory_watch_feed_impl'
    fields = FeedImplSchema.fields + [
        ('firstUpdate', SchemaBool()),
        ('dir', SchemaFilename(noneOk=True)),
        ]

class DirectoryFeedImplSchema(FeedImplSchema):
    klass = DirectoryFeedImpl
    table_name = 'directory_feed_impl'
    # DirectoryFeedImpl doesn't have any addition fields over FeedImpl

class SearchDownloadsFeedImplSchema(FeedImplSchema):
    klass = SearchDownloadsFeedImpl
    table_name = 'search_downloads_feed_impl'
    # SearchDownloadsFeedImpl doesn't have any addition fields over
    # FeedImpl

class ManualFeedImplSchema(FeedImplSchema):
    klass = ManualFeedImpl
    table_name = 'manual_feed_impl'
    # no addition fields over FeedImplSchema

class RemoteDownloaderSchema(DDBObjectSchema):
    klass = RemoteDownloader
    table_name = 'remote_downloader'
    fields = DDBObjectSchema.fields + [
        ('url', SchemaURL()),
        ('orig_url', SchemaURL()),
        ('dlid', SchemaString()),
        ('content_type', SchemaString(noneOk=True)),
        ('channel_name', SchemaFilename(noneOk=True)),
        ('metainfo', SchemaBinary(noneOk=True)),
        ('manualUpload', SchemaBool()),
        ('state', SchemaString()),
        ('main_item_id', SchemaInt(noneOk=True)),
        ('child_deleted', SchemaBool()),
        ('total_size', SchemaInt(noneOk=True)),
        ('current_size', SchemaInt()),
        ('start_time', SchemaInt(noneOk=True)),
        ('end_time', SchemaInt(noneOk=True)),
        ('short_filename', SchemaFilename(noneOk=True)),
        ('filename', SchemaFilename(noneOk=True)),
        ('reason_failed', SchemaString(noneOk=True)),
        ('short_reason_failed', SchemaString(noneOk=True)),
        ('type', SchemaString(noneOk=True)),
        ('retry_time', SchemaDateTime(noneOk=True)),
        ('retry_count', SchemaInt(noneOk=True)),
        ('upload_size', SchemaInt(noneOk=True)),
        ('info_hash', SchemaString(noneOk=True)),
        ('eta', SchemaInt(noneOk=True)),
        ('rate', SchemaInt(noneOk=True)),
        ('upload_rate', SchemaInt(noneOk=True)),
        ('activity', SchemaString(noneOk=True)),
        ('seeders', SchemaInt(noneOk=True)),
        ('leechers', SchemaInt(noneOk=True)),
        ('connections', SchemaInt(noneOk=True)),
    ]

    indexes = (
        ('downloader_state', ('state',)),
    )

    @staticmethod
    def handle_malformed_status(row):
        return {}

class HideableTabSchema(DDBObjectSchema):
    klass = HideableTab
    table_name = 'hideable_tab'
    fields = DDBObjectSchema.fields + [
        ('type', SchemaString()),
        ('expanded', SchemaBool()),
    ]

    indexes = (
        ('hideable_tab_type', ('type',)),
    )

class ChannelFolderSchema(DDBObjectSchema):
    klass = ChannelFolder
    table_name = 'channel_folder'
    fields = DDBObjectSchema.fields + [
        ('expanded', SchemaBool()),
        ('title', SchemaString()),
        ('section', SchemaString()), # not used any more
    ]

class PlaylistFolderSchema(DDBObjectSchema):
    klass = PlaylistFolder
    table_name = 'playlist_folder'
    fields = DDBObjectSchema.fields + [
        ('expanded', SchemaBool()),
        ('title', SchemaString()),
    ]

class PlaylistSchema(DDBObjectSchema):
    klass = SavedPlaylist
    table_name = 'playlist'
    fields = DDBObjectSchema.fields + [
        ('title', SchemaString()),
        ('folder_id', SchemaInt(noneOk=True)),
    ]

class PlaylistItemMapSchema(DDBObjectSchema):
    klass = PlaylistItemMap
    table_name = 'playlist_item_map'
    fields = DDBObjectSchema.fields + [
        ('playlist_id', SchemaInt()),
        ('item_id', SchemaInt()),
        ('position', SchemaInt()),
    ]

    indexes = (
        ('playlist_item_map_item_id', ('item_id',)),
    )

class PlaylistFolderItemMapSchema(DDBObjectSchema):
    klass = PlaylistFolderItemMap
    table_name = 'playlist_folder_item_map'
    fields = DDBObjectSchema.fields + [
        ('playlist_id', SchemaInt()),
        ('item_id', SchemaInt()),
        ('position', SchemaInt()),
        ('count', SchemaInt()),
    ]

    indexes = (
        ('playlist_folder_item_map_item_id', ('item_id',)),
    )

class TabOrderSchema(DDBObjectSchema):
    klass = TabOrder
    table_name = 'taborder_order'
    fields = DDBObjectSchema.fields + [
        ('type', SchemaString()),
        ('tab_ids', SchemaList(SchemaInt())),
    ]

    @staticmethod
    def handle_malformed_tab_ids(row):
        return []

class ChannelGuideSchema(DDBObjectSchema):
    klass = ChannelGuide
    table_name = 'channel_guide'
    fields = DDBObjectSchema.fields + [
        ('url', SchemaURL(noneOk=True)),
        ('allowedURLs', SchemaList(SchemaURL())),
        ('updated_url', SchemaURL(noneOk=True)),
        ('favicon', SchemaURL(noneOk=True)),
        ('title', SchemaString(noneOk=True)),
        ('userTitle', SchemaString(noneOk=True)),
        ('icon_cache_id', SchemaInt(noneOk=True)),
        ('firstTime', SchemaBool()),
        ('store', SchemaInt()),
    ]

    @staticmethod
    def handle_malformed_allowedURLs(row):
        return []

class ThemeHistorySchema(DDBObjectSchema):
    klass = ThemeHistory
    table_name = 'theme_history'
    fields = DDBObjectSchema.fields + [
        ('lastTheme', SchemaString(noneOk=True)),
        ('pastThemes', SchemaList(SchemaString(noneOk=True), noneOk=False)),
    ]

    @staticmethod
    def handle_malformed_pastThemes(row):
        return []

class DisplayStateSchema(DDBObjectSchema):
    klass = DisplayState
    table_name = 'display_state'
    fields = DDBObjectSchema.fields + [
        ('type', SchemaString()),
        ('id_', SchemaString()),
        ('selected_view', SchemaInt(noneOk=True)),
        ('active_filters', SchemaStringSet(noneOk=True)),
        ('shuffle', SchemaBool(noneOk=True)),
        ('repeat', SchemaInt(noneOk=True)),
        ('selection', SchemaList(SchemaMultiValue(), noneOk=True)),
        ('sort_state', SchemaString(noneOk=True)),
        ('last_played_item_id', SchemaInt(noneOk=True)),
    ]

    indexes = (
        ('display_state_display', ('type', 'id_')),
    )

class GlobalStateSchema(DDBObjectSchema):
    klass = GlobalState
    table_name = 'global_state'
    fields = DDBObjectSchema.fields + [
        ('item_details_expanded', SchemaDict(SchemaInt(), SchemaBool())),
        ('guide_sidebar_expanded', SchemaBool()),
        ('tabs_width', SchemaInt())
    ]

class DBLogEntrySchema(DDBObjectSchema):
    klass = DBLogEntry
    table_name = 'db_log_entry'
    fields = DDBObjectSchema.fields + [
        ('timestamp', SchemaFloat()),
        ('priority', SchemaInt()),
        ('description', SchemaString()),
    ]

class ViewStateSchema(DDBObjectSchema):
    klass = ViewState
    table_name = 'view_state'
    fields = DDBObjectSchema.fields + [
        ('display_type', SchemaString()),
        ('display_id', SchemaString()),
        ('view_type', SchemaInt()),
        ('scroll_position', SchemaTuple(SchemaInt(), SchemaInt(), noneOk=True)),
        ('columns_enabled', SchemaList(SchemaString(), noneOk=True)),
        ('column_widths', SchemaDict(SchemaString(), SchemaInt(), noneOk=True)),
    ]

    indexes = (
        ('view_state_key', ('display_type', 'display_id', 'view_type')),
    )

    @staticmethod
    def handle_malformed_scroll_position(value):
        return None

    @staticmethod
    def handle_malformed_selection(value):
        return None

    @staticmethod
    def handle_malformed_columns_enabled(value):
        return None

    @staticmethod
    def handle_malformed_column_widths(value):
        return None

class MetadataStatusSchema(DDBObjectSchema):
    klass = MetadataStatus
    table_name = 'metadata_status'
    fields = DDBObjectSchema.fields + [
        ('path', SchemaFilename()),
        ('file_type', SchemaString()),
        ('finished_status', SchemaInt()),
        ('mutagen_status', SchemaString()),
        ('moviedata_status', SchemaString()),
        ('echonest_status', SchemaString()),
        ('echonest_id', SchemaString(noneOk=True)),
        ('net_lookup_enabled', SchemaBool()),
        ('mutagen_thinks_drm', SchemaBool()),
        ('max_entry_priority', SchemaInt()),
    ]

    indexes = (
        ('metadata_finished', ('finished_status',)),
    )

    unique_indexes = (
        ('metadata_path', ('path',)),
    )

class MetadataEntrySchema(DDBObjectSchema):
    klass = MetadataEntry
    table_name = 'metadata'
    fields = DDBObjectSchema.fields + [
        ('status_id', SchemaInt()),
        ('source', SchemaString()),
        ('priority', SchemaInt()),
        ('file_type', SchemaString(noneOk=True)),
        ('duration', SchemaInt(noneOk=True)),
        ('album', SchemaString(noneOk=True)),
        ('album_artist', SchemaString(noneOk=True)),
        ('album_tracks', SchemaInt(noneOk=True)),
        ('artist', SchemaString(noneOk=True)),
        ('screenshot', SchemaFilename(noneOk=True)),
        ('drm', SchemaBool(noneOk=True)),
        ('genre', SchemaString(noneOk=True)),
        ('title', SchemaString(noneOk=True)),
        ('track', SchemaInt(noneOk=True)),
        ('year', SchemaInt(noneOk=True)),
        ('description', SchemaString(noneOk=True)),
        ('rating', SchemaInt(noneOk=True)),
        ('show', SchemaString(noneOk=True)),
        ('episode_id', SchemaString(noneOk=True)),
        ('episode_number', SchemaInt(noneOk=True)),
        ('season_number', SchemaInt(noneOk=True)),
        ('kind', SchemaString(noneOk=True)),
        ('disabled', SchemaBool()),
    ]

    indexes = (
        ('metadata_entry_status', ('status_id',)),
    )

    unique_indexes = (
        ('metadata_entry_status_and_source', ('status_id', 'source')),
    )

VERSION = 187

object_schemas = [
    IconCacheSchema, ItemSchema, FeedSchema,
    FeedImplSchema, RSSFeedImplSchema, SavedSearchFeedImplSchema,
    ScraperFeedImplSchema,
    SearchFeedImplSchema, DirectoryFeedImplSchema, DirectoryWatchFeedImplSchema,
    SearchDownloadsFeedImplSchema, RemoteDownloaderSchema,
    ChannelGuideSchema, ManualFeedImplSchema,
    PlaylistSchema, HideableTabSchema, ChannelFolderSchema, PlaylistFolderSchema,
    PlaylistItemMapSchema, PlaylistFolderItemMapSchema,
    TabOrderSchema, ThemeHistorySchema, DisplayStateSchema, GlobalStateSchema,
    DBLogEntrySchema, ViewStateSchema, MetadataStatusSchema,
    MetadataEntrySchema
]
