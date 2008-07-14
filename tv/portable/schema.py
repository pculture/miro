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

"""The schema module is responsible for defining what data in the database
gets stored on disk.  

The goals of this modules are:

* Clearly defining which data from DDBObjects gets stored and which doesn't.
* Validating that all data we write can be read back in
* Making upgrades of the database schema as easy as possible

Module-level variables:
    objectSchemas -- Schemas to use with the current database.
    VERSION -- Current schema version.  If you change the schema you must bump
    this number and add a function in the databaseupgrade module.

Go to the bottom of this file for the current database schema.
"""

import cPickle
import datetime
import time
import logging
from types import NoneType
from fasttypes import LinkedList
from miro.plat.utils import FilenameType

class ValidationError(Exception):
    """Error thrown when we try to save invalid data."""
    pass

class ValidationWarning(Warning):
    """Warning issued when we try to restore invalid data."""
    pass

class SchemaItem(object):
    """SchemaItem represents a single attribute that gets stored on disk.

    SchemaItem is an abstract class.  Subclasses of SchemaItem such as
    SchemaAttr, SchemaObject, SchemaList are used in actual object schemas.

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
        doesn't have to recirsively validate things.
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

class SchemaList(SchemaItem):
    def __init__(self, childSchema, noneOk=False):
        super(SchemaList, self).__init__(noneOk)
        self.childSchema = childSchema

    def validate(self, data):
        super(SchemaList, self).validate(data)
        self.validateType(data, list)

class SchemaDict(SchemaItem):
    type = dict

    def __init__(self, keySchema, valueSchema, noneOk=False):
        super(SchemaDict, self).__init__(noneOk)
        self.keySchema = keySchema
        self.valueSchema = valueSchema

    def validate(self, data):
        super(SchemaDict, self).validate(data)
        self.validateType(data, dict)

class SchemaSimpleContainer(SchemaSimpleItem):
    """Allows nested dicts, lists and tuples, however the only thing they can
    store are simple objects.  This currently includes bools, ints, longs,
    floats, strings, unicode, None, datetime and struct_time objects.
    """

    def validate(self, data):
        super(SchemaSimpleContainer, self).validate(data)
        self.validateTypes(data, (dict, list, tuple))
        self.memory = set()
        toValidate = LinkedList()
        while data:
            if id(data) in self.memory:
                return
            else:
                self.memory.add(id(data))
    
            if isinstance(data, list) or isinstance(data, tuple):
                for item in data:
                    toValidate.append(item)
            elif isinstance(data, dict):
                for key, value in data.items():
                    self.validateTypes(key, [bool, int, long, float, unicode,
                        str, NoneType, datetime.datetime, time.struct_time])
                    toValidate.append(value)
            else:
                self.validateTypes(data, [bool, int, long, float, unicode,
                        NoneType, datetime.datetime, time.struct_time])
            try:
                data = toValidate.pop()
            except:
                data = None

class SchemaStatusContainer(SchemaSimpleContainer):
    """Allows nested dicts, lists and tuples, however the only thing they can
    store are simple objects.  This currently includes bools, ints, longs,
    floats, strings, unicode, None, datetime and struct_time objects.
    """

    def validate(self, data):
        if FilenameType == unicode:
            binaryFields = ['metainfo','fastResumeData']
        else:
            binaryFields = ['channelName','shortFilename','filename','metainfo','fastResumeData']
        self.validateType(data, dict)
        for key, value in data.items():
            self.validateTypes(key, [bool, int, long, float, unicode,
                    str, NoneType, datetime.datetime, time.struct_time])
            if key not in binaryFields:
                self.validateTypes(value, [bool, int, long, float, unicode,
                        NoneType, datetime.datetime, time.struct_time])
            else:
                self.validateType(value, str)

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
    classString -- a human readable string that represents objectClass
    fields -- list of  (name, SchemaItem) pairs.  One item for each attribute
        that shoud be stored to disk.
    """
    pass

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
    classString = 'ddb-object'
    fields = [
        ('id', SchemaInt())
    ]

class IconCacheSchema (ObjectSchema):
    klass = IconCache
    classString = 'icon-cache'
    fields = [
        ('etag', SchemaString(noneOk=True)),
        ('modified', SchemaString(noneOk=True)),
        ('filename', SchemaFilename(noneOk=True)),
        ('resized_filenames', SchemaDict(SchemaString(), SchemaFilename())),
        ('url', SchemaURL(noneOk=True)),
        ]

class ItemSchema(DDBObjectSchema):
    klass = Item
    classString = 'item'
    fields = DDBObjectSchema.fields + [
        ('feed_id', SchemaInt(noneOk=True)),
        ('parent_id', SchemaInt(noneOk=True)),
        ('seen', SchemaBool()),
        ('autoDownloaded', SchemaBool()),
        ('pendingManualDL', SchemaBool()),
        ('pendingReason', SchemaString()),
        ('title', SchemaString()),
        ('entry', SchemaSimpleContainer()),
        ('expired', SchemaBool()),
        ('keep', SchemaBool()),
        ('creationTime', SchemaDateTime()),
        ('linkNumber', SchemaInt(noneOk=True)),
        ('iconCache', SchemaObject(IconCache, noneOk=True)),
        ('downloadedTime', SchemaDateTime(noneOk=True)),
        ('watchedTime', SchemaDateTime(noneOk=True)),
        ('isContainerItem', SchemaBool(noneOk=True)),
        ('videoFilename', SchemaFilename()),
        ('isVideo', SchemaBool()),
        ('releaseDateObj', SchemaDateTime()),
        ('eligibleForAutoDownload', SchemaBool()),
        ('duration', SchemaInt(noneOk=True)),
        ('screenshot', SchemaFilename(noneOk=True)),
        ('resized_screenshots', SchemaDict(SchemaString(), SchemaFilename())),
        ('resumeTime', SchemaInt()),
        ('channelTitle', SchemaString(noneOk=True)),
    ]

class FileItemSchema(ItemSchema):
    klass = FileItem
    classString = 'file-item'
    fields = ItemSchema.fields + [
        ('filename', SchemaFilename()),
        ('deleted', SchemaBool()),
        ('shortFilename', SchemaFilename(noneOk=True)),
        ('offsetPath', SchemaFilename(noneOk=True)),
    ]

class FeedSchema(DDBObjectSchema):
    klass = Feed
    classString = 'feed'
    fields = DDBObjectSchema.fields + [
        ('origURL', SchemaURL()),
        ('baseTitle', SchemaString(noneOk=True)),
        ('errorState', SchemaBool()),
        ('loading', SchemaBool()),
        ('actualFeed', SchemaObject(FeedImpl)),
        ('iconCache', SchemaObject(IconCache, noneOk=True)),
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
    ]

class FeedImplSchema(ObjectSchema):
    klass = FeedImpl
    classString = 'field-impl'
    fields = [
        ('url', SchemaURL()),
        ('ufeed', SchemaObject(Feed)),
        ('title', SchemaString(noneOk=True)),
        ('created', SchemaDateTime()),
        ('visible', SchemaBool()),
        ('lastViewed', SchemaDateTime()),
        ('thumbURL', SchemaURL(noneOk=True)),
        ('updateFreq', SchemaInt()),
        ('initialUpdate', SchemaBool()),
    ]

class RSSFeedImplSchema(FeedImplSchema):
    klass = RSSFeedImpl
    classString = 'rss-feed-impl'
    fields = FeedImplSchema.fields + [
        ('initialHTML', SchemaBinary(noneOk=True)),
        ('etag', SchemaString(noneOk=True)),
        ('modified', SchemaString(noneOk=True)),
    ]

class RSSMultiFeedImplSchema(FeedImplSchema):
    klass = RSSMultiFeedImpl
    classString = 'rss-multi-feed-impl'
    fields = FeedImplSchema.fields + [
        ('etag', SchemaDict(SchemaString(),SchemaString(noneOk=True))),
        ('modified', SchemaDict(SchemaString(),SchemaString(noneOk=True))),
    ]

class ScraperFeedImplSchema(FeedImplSchema):
    klass = ScraperFeedImpl
    classString = 'scraper-feed-impl'
    fields = FeedImplSchema.fields + [
        ('initialHTML', SchemaBinary(noneOk=True)),
        ('initialCharset', SchemaString(noneOk=True)),
        ('linkHistory', SchemaSimpleContainer()),
    ]

class SearchFeedImplSchema(RSSMultiFeedImplSchema):
    klass = SearchFeedImpl
    classString = 'search-feed-impl'
    fields = RSSMultiFeedImplSchema.fields + [
        ('searching', SchemaBool()),
        ('lastEngine', SchemaString()),
        ('lastQuery', SchemaString()),
    ]

class DirectoryWatchFeedImplSchema(FeedImplSchema):
    klass = DirectoryWatchFeedImpl
    classString = 'directory-watch-feed-impl'
    fields = FeedImplSchema.fields + [
        ('firstUpdate', SchemaBool()),
        ('dir', SchemaFilename(noneOk=True)),
        ]

class DirectoryFeedImplSchema(FeedImplSchema):
    klass = DirectoryFeedImpl
    classString = 'directory-feed-impl'
    # DirectoryFeedImpl doesn't have any addition fields over FeedImpl

class SearchDownloadsFeedImplSchema(FeedImplSchema):
    klass = SearchDownloadsFeedImpl
    classString = 'search-downloads-feed-impl'
    # SearchDownloadsFeedImpl doesn't have any addition fields over FeedImpl

class ManualFeedImplSchema(FeedImplSchema):
    klass = ManualFeedImpl
    classString = 'manual-feed-impl'
    # no addition fields over FeedImplSchema

class SingleFeedImplSchema(FeedImplSchema):
    klass = SingleFeedImpl
    classString = 'single-feed-impl'
    # no addition fields over FeedImplSchema

class RemoteDownloaderSchema(DDBObjectSchema):
    klass = RemoteDownloader
    classString = 'remote-downloader'
    fields = DDBObjectSchema.fields + [
        ('url', SchemaURL()),
        ('origURL', SchemaURL()),
        ('dlid', SchemaString()),
        ('contentType', SchemaString(noneOk=True)),
        ('channelName', SchemaFilename(noneOk=True)),
        ('status', SchemaStatusContainer()),
        ('manualUpload', SchemaBool()),
    ]

class HTTPAuthPasswordSchema(DDBObjectSchema):
    klass = HTTPAuthPassword
    classString = 'http-auth-password'
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
    classString = 'channel-folder'
    fields = DDBObjectSchema.fields + [
        ('expanded', SchemaBool()),
        ('title', SchemaString()),
    ]

class PlaylistFolderSchema(DDBObjectSchema):
    klass = PlaylistFolder
    classString = 'playlist-folder'
    fields = DDBObjectSchema.fields + [
        ('expanded', SchemaBool()),
        ('title', SchemaString()),
        ('item_ids', SchemaList(SchemaInt())),
    ]

class PlaylistSchema(DDBObjectSchema):
    klass = SavedPlaylist
    classString = 'playlist'
    fields = DDBObjectSchema.fields + [
        ('title', SchemaString()),
        ('item_ids', SchemaList(SchemaInt())),
        ('folder_id', SchemaInt(noneOk=True)),
    ]

class TabOrderSchema(DDBObjectSchema):
    klass = TabOrder
    classString = 'taborder-order'
    fields = DDBObjectSchema.fields + [
        ('type', SchemaString()),
        ('tab_ids', SchemaList(SchemaInt())),
    ]

class ChannelGuideSchema(DDBObjectSchema):
    klass = ChannelGuide
    classString = 'channel-guide'
    fields = DDBObjectSchema.fields + [
        ('url', SchemaURL(noneOk=True)),
        ('allowedURLs', SchemaList(SchemaURL())),
        ('updated_url', SchemaURL(noneOk=True)),
        ('favicon', SchemaURL(noneOk=True)),
        ('title', SchemaString(noneOk=True)),
        ('iconCache', SchemaObject(IconCache, noneOk=True)),
        ('firstTime', SchemaBool()),
    ]

class ThemeHistorySchema(DDBObjectSchema):
    klass = ThemeHistory
    classString = 'theme-history'
    fields = DDBObjectSchema.fields + [
        ('lastTheme', SchemaString(noneOk=True)),
        ('pastThemes', SchemaList(SchemaString(noneOk=True), noneOk=False)),
    ]

VERSION = 66
objectSchemas = [
    DDBObjectSchema, IconCacheSchema, ItemSchema, FileItemSchema, FeedSchema,
    FeedImplSchema, RSSFeedImplSchema, RSSMultiFeedImplSchema, ScraperFeedImplSchema,
    SearchFeedImplSchema, DirectoryFeedImplSchema, DirectoryWatchFeedImplSchema,
    SearchDownloadsFeedImplSchema, RemoteDownloaderSchema,
    HTTPAuthPasswordSchema, ChannelGuideSchema, ManualFeedImplSchema, SingleFeedImplSchema,
    PlaylistSchema, ChannelFolderSchema, PlaylistFolderSchema,
    TabOrderSchema, ThemeHistorySchema
]
