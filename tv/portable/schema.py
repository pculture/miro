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

"""The schema module is responsible for defining what data in the database
gets stored on disk.  

The goals of this modules are:

* Clearly defining which data from DDBObjects gets stored and which doesn't.
* Validating that all data we write can be read back in
* Making upgrades of the database schema as easy as possible

Module-level variables:
    object_schemas -- Schemas to use with the current database.
    VERSION -- Current schema version.  If you change the schema you must bump
    this number and add a function in the databaseupgrade module.

Go to the bottom of this file for the current database schema.
"""

import datetime
import time
from types import NoneType
from fasttypes import LinkedList
from miro.plat.utils import FilenameType
from miro.frontendstate import WidgetsFrontendState

class ValidationError(Exception):
    """Error thrown when we try to save invalid data."""
    pass

class ValidationWarning(Warning):
    """Warning issued when we try to restore invalid data."""
    pass

class SchemaItem(object):
    """SchemaItem represents a single attribute that gets stored on disk.

    SchemaItem is an abstract class.  Subclasses of SchemaItem such as
    SchemaAttr, SchemaList are used in actual object schemas.

    Member variables:
        noneOk -- specifies if None is a valid value for this attribute
    """

    def __init__(self, noneOk=False):
        self.noneOk = noneOk

    def validate(self, data):
        """Validate that data is a valid value for this SchemaItem.

        validate is "dumb" when it comes to container types like SchemaList,
        etc.  It only checks that the container is the right type, not its
        children.  This isn't a problem because saveObject() calls
        validate() recursively on all the data it saves, therefore validate
        doesn't have to recursively validate things.
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

    def validateTypes(self, data, possibleTypes):
        if data is None:
            return
        for t in possibleTypes:
            if isinstance(data, t):
                return
        raise ValidationError("%r (type: %s) is not any of: %s" % 
                (data, type(data), possibleTypes))

class SchemaSimpleItem(SchemaItem):
    """Base class for SchemaItems for simple python types."""

class SchemaBool(SchemaSimpleItem):
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, bool)

class SchemaFloat(SchemaSimpleItem):
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, float)

class SchemaString(SchemaSimpleItem):
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, unicode)

class SchemaBinary(SchemaSimpleItem):
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, str)

class SchemaFilename(SchemaSimpleItem):
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, FilenameType)

class SchemaURL(SchemaSimpleItem):
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, unicode)
        if data:
            try:
                data.encode('ascii')
            except UnicodeEncodeError:
                ValidationError(u"URL (%s) is not ASCII" % data)

class SchemaInt(SchemaSimpleItem):
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateTypes(data, [int, long])

class SchemaDateTime(SchemaSimpleItem):
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, datetime.datetime)

class SchemaTimeDelta(SchemaSimpleItem):
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, datetime.timedelta)

class SchemaReprContainer(SchemaItem):
    """SchemaItem saved using repr() to save nested lists, dicts and tuples
    that store simple types.  The look is similar to JSON, but supports a
    couple different things, for example unicode and str values are distinct.
    The types that we support are bool, int, long, float, unicode, None and
    datetime.  Dictionary keys can also be byte strings (AKA str types)
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

class SchemaList(SchemaReprContainer):
    """Special case of SchemaReprContainer that stores a simple list

    All values must have the same type
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
    """Special case of SchemaReprContainer that stores a simple dict

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
                raise ValidationError("key %r has the wrong type" % key)
            try:
                self.valueSchema.validate(value)
            except ValidationError:
                raise ValidationError("value %r (key: %r) has the wrong type"
                        % (value, key))

class SchemaStatusContainer(SchemaReprContainer):
    """Version of SchemaReprContainer that stores the status dict for
    RemoteDownloaders.  It allows some values to be byte strings rather than
    unicode objects.
    """


    def validate(self, data):
        binary_fields = self._binary_fields()
        self.validateType(data, dict)
        for key, value in data.items():
            self.validateTypes(key, [bool, int, long, float, unicode,
                    str, NoneType, datetime.datetime, time.struct_time])
            if key not in binary_fields:
                self.validateTypes(value, [bool, int, long, float, unicode,
                        NoneType, datetime.datetime, time.struct_time])
            else:
                self.validateType(value, str)

    def _binary_fields(self):
        if FilenameType == unicode:
            return ('metainfo', 'fastResumeData')
        else:
            return ('channelName', 'shortFilename', 'filename', 'metainfo',
                    'fastResumeData')

class SchemaObject(SchemaItem):
    def __init__(self, klass, noneOk=False):
        super(SchemaObject, self).__init__(noneOk)
        self.klass = klass

    def validate(self, data):
        super(SchemaObject, self).validate(data)
        self.validateType(data, self.klass)

class ObjectSchema(object):
    """The schema to save/restore an object with.  Object schema isn't a
    SchemaItem, it's the schema for an entire object.

    Member variables:

    klass -- the python class that this schema is for
    table_name -- SQL table name to store the class in
    fields -- list of  (name, SchemaItem) pairs.  One item for each attribute
        that should be stored to disk.
    """

    @classmethod
    def ddb_object_classes(cls):
        return (cls.klass,)

    @classmethod
    def get_ddb_class(cls, restored_data):
        return cls.klass

class MultiClassObjectSchema(ObjectSchema):
    """ObjectSchema where rows will be restored to different python classes.

    Instead of the klass attribute, MultiClassObjectSchema should define 2
    class methods: ddb_object_classes() returns the list of all classes that
    this schema works with and get_ddb_class() which inputs a dictionary
    containing db data and return which class we should use to restore that
    row.
    """

from miro.database import DDBObject
from miro.downloader import RemoteDownloader, HTTPAuthPassword
from miro.feed import Feed, FeedImpl, RSSFeedImpl, RSSMultiFeedImpl, ScraperFeedImpl
from miro.feed import SearchFeedImpl, DirectoryWatchFeedImpl, DirectoryFeedImpl, SearchDownloadsFeedImpl
from miro.feed import ManualFeedImpl, SingleFeedImpl
from miro.folder import ChannelFolder, PlaylistFolder
from miro.guide import ChannelGuide
from miro.item import Item, FileItem
from miro.iconcache import IconCache
from miro.playlist import SavedPlaylist
from miro.tabs import TabOrder
from miro.theme import ThemeHistory

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
        ('feed_id', SchemaInt(noneOk=True)),
        ('downloader_id', SchemaInt(noneOk=True)),
        ('parent_id', SchemaInt(noneOk=True)),
        ('seen', SchemaBool()),
        ('autoDownloaded', SchemaBool()),
        ('pendingManualDL', SchemaBool()),
        ('pendingReason', SchemaString()),
        ('title', SchemaString()),
        ('expired', SchemaBool()),
        ('keep', SchemaBool()),
        ('creationTime', SchemaDateTime()),
        ('linkNumber', SchemaInt(noneOk=True)),
        ('icon_cache_id', SchemaInt(noneOk=True)),
        ('downloadedTime', SchemaDateTime(noneOk=True)),
        ('watchedTime', SchemaDateTime(noneOk=True)),
        ('isContainerItem', SchemaBool(noneOk=True)),
        ('videoFilename', SchemaFilename()),
        ('isVideo', SchemaBool()),
        ('releaseDateObj', SchemaDateTime()),
        ('eligibleForAutoDownload', SchemaBool()),
        ('duration', SchemaInt(noneOk=True)),
        ('screenshot', SchemaFilename(noneOk=True)),
        ('resumeTime', SchemaInt()),
        ('channelTitle', SchemaString(noneOk=True)),
        ('license', SchemaString(noneOk=True)),
        ('rss_id', SchemaString(noneOk=True)),
        ('thumbnail_url', SchemaURL(noneOk=True)),
        ('entry_title', SchemaString(noneOk=True)),
        ('raw_descrption', SchemaString(noneOk=False)),
        ('link', SchemaURL(noneOk=False)),
        ('payment_link', SchemaURL(noneOk=False)),
        ('comments_link', SchemaURL(noneOk=False)),
        ('url', SchemaURL(noneOk=False)),
        ('enclosure_size', SchemaInt(noneOk=True)),
        ('enclosure_type', SchemaString(noneOk=True)),
        ('enclosure_format', SchemaString(noneOk=True)),
        ('feedparser_output', SchemaReprContainer()),
        ('was_downloaded', SchemaBool()),
        ('filename', SchemaFilename(noneOk=True)),
        ('deleted', SchemaBool(noneOk=True)),
        ('shortFilename', SchemaFilename(noneOk=True)),
        ('offsetPath', SchemaFilename(noneOk=True)),
    ]

class FeedSchema(DDBObjectSchema):
    klass = Feed
    table_name = 'feed'
    fields = DDBObjectSchema.fields + [
        ('origURL', SchemaURL()),
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
        ('section', SchemaString()),
        ('visible', SchemaBool()),
        ('last_viewed', SchemaDateTime()),
    ]

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

class RSSMultiFeedImplSchema(FeedImplSchema):
    klass = RSSMultiFeedImpl
    table_name = 'rss_multi_feed_impl'
    fields = FeedImplSchema.fields + [
        ('etag', SchemaDict(SchemaString(),SchemaString(noneOk=True))),
        ('modified', SchemaDict(SchemaString(),SchemaString(noneOk=True))),
        ('query', SchemaString(noneOk=True)),
    ]

class ScraperFeedImplSchema(FeedImplSchema):
    klass = ScraperFeedImpl
    table_name = 'scraper_feed_impl'
    fields = FeedImplSchema.fields + [
        ('initialHTML', SchemaBinary(noneOk=True)),
        ('initialCharset', SchemaString(noneOk=True)),
        ('linkHistory', SchemaReprContainer()),
    ]

class SearchFeedImplSchema(RSSMultiFeedImplSchema):
    klass = SearchFeedImpl
    table_name = 'search_feed_impl'
    fields = RSSMultiFeedImplSchema.fields + [
        ('searching', SchemaBool()),
        ('lastEngine', SchemaString()),
        ('lastQuery', SchemaString()),
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
    # SearchDownloadsFeedImpl doesn't have any addition fields over FeedImpl

class ManualFeedImplSchema(FeedImplSchema):
    klass = ManualFeedImpl
    table_name = 'manual_feed_impl'
    # no addition fields over FeedImplSchema

class SingleFeedImplSchema(FeedImplSchema):
    klass = SingleFeedImpl
    table_name = 'single_feed_impl'
    # no addition fields over FeedImplSchema

class RemoteDownloaderSchema(DDBObjectSchema):
    klass = RemoteDownloader
    table_name = 'remote_downloader'
    fields = DDBObjectSchema.fields + [
        ('url', SchemaURL()),
        ('origURL', SchemaURL()),
        ('dlid', SchemaString()),
        ('contentType', SchemaString(noneOk=True)),
        ('channelName', SchemaFilename(noneOk=True)),
        ('status', SchemaStatusContainer()),
        ('manualUpload', SchemaBool()),
        ('state', SchemaString()),
    ]

class HTTPAuthPasswordSchema(DDBObjectSchema):
    klass = HTTPAuthPassword
    table_name = 'http_auth_password'
    fields = DDBObjectSchema.fields + [
        ('username', SchemaString()),
        ('password', SchemaString()),
        ('host', SchemaString()),
        ('realm', SchemaString()),
        ('path', SchemaString()),
        ('authScheme', SchemaString()),
    ]

class ChannelFolderSchema(DDBObjectSchema):
    klass = ChannelFolder
    table_name = 'channel_folder'
    fields = DDBObjectSchema.fields + [
        ('expanded', SchemaBool()),
        ('title', SchemaString()),
        ('section', SchemaString()),
    ]

class PlaylistFolderSchema(DDBObjectSchema):
    klass = PlaylistFolder
    table_name = 'playlist_folder'
    fields = DDBObjectSchema.fields + [
        ('expanded', SchemaBool()),
        ('title', SchemaString()),
        ('item_ids', SchemaList(SchemaInt())),
    ]

class PlaylistSchema(DDBObjectSchema):
    klass = SavedPlaylist
    table_name = 'playlist'
    fields = DDBObjectSchema.fields + [
        ('title', SchemaString()),
        ('item_ids', SchemaList(SchemaInt())),
        ('folder_id', SchemaInt(noneOk=True)),
    ]

class TabOrderSchema(DDBObjectSchema):
    klass = TabOrder
    table_name = 'taborder_order'
    fields = DDBObjectSchema.fields + [
        ('type', SchemaString()),
        ('tab_ids', SchemaList(SchemaInt())),
    ]

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
    ]

class ThemeHistorySchema(DDBObjectSchema):
    klass = ThemeHistory
    table_name = 'theme_history'
    fields = DDBObjectSchema.fields + [
        ('lastTheme', SchemaString(noneOk=True)),
        ('pastThemes', SchemaList(SchemaString(noneOk=True), noneOk=False)),
    ]

class WidgetsFrontendStateSchema(DDBObjectSchema):
    klass = WidgetsFrontendState
    table_name = 'widgets_frontend_state'
    fields = DDBObjectSchema.fields + [
        ('list_view_displays', SchemaList(SchemaBinary())),
    ]

VERSION = 86
object_schemas = [
    IconCacheSchema, ItemSchema, FeedSchema,
    FeedImplSchema, RSSFeedImplSchema, RSSMultiFeedImplSchema, ScraperFeedImplSchema,
    SearchFeedImplSchema, DirectoryFeedImplSchema, DirectoryWatchFeedImplSchema,
    SearchDownloadsFeedImplSchema, RemoteDownloaderSchema,
    HTTPAuthPasswordSchema, ChannelGuideSchema, ManualFeedImplSchema, SingleFeedImplSchema,
    PlaylistSchema, ChannelFolderSchema, PlaylistFolderSchema,
    TabOrderSchema, ThemeHistorySchema, WidgetsFrontendStateSchema
]
