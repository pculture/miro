"""The schema module is responsible for defining what data in the database
gets stored on disk.  

The goals of this modules are:

* Clearly defining which data from DDBObjects gets stored and which doesn't.
* Validating that all data we write can be read back in
* Making upgrades of the database schema as easy as possible

Module-level variables:
    objectSchemas -- Schemas to use with the current database.
    VERISON -- Current schema version.  If you change the schema you must bump
    this number and add a function in the dbupgrade module.

Go to the bottom of this file for the current database schema.
"""

import cPickle
import datetime
from types import NoneType

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
            raise ValidationError("%r is not a %s" % (data, correctType))

    def validateTypes(self, data, possibleTypes):
        if data is None:
            return
        for type in possibleTypes:
            if isinstance(data, type):
                return
        raise ValidationError("%r is not any of: %s" % (data, possibleTypes))

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
        self.validateTypes(data, [str, unicode])

class SchemaInt(SchemaSimpleItem):
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateTypes(data, [int, long])

class SchemaDateTime(SchemaSimpleItem):
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateType(data, datetime.datetime)

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

class SchemaSimpleValue(SchemaItem):
    """Accepts mixed types, but it must be a built in python object, currently
    allow are bools, ints, longs, floats, strings, unicode and None.
    """
    type = dict

    def __init__(self, noneOk=True):
        if not noneOk:
            raise ValueError("SchemaSimpleValue always accepts None")
        super(SchemaSimpleValue, self).__init__(noneOk)

    def validate(self, data):
        super(SchemaSimpleValue, self).validate(data)
        self.validateTypes(data, [bool, int, long, float, str, unicode,
                NoneType])

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

from feed import Feed
from downloader import RemoteDownloader
from item import Item

class ItemSchema(ObjectSchema):
    klass = Item
    classString = 'item'
    fields = [
        ('feed', SchemaObject(Feed)),
        ('seen', SchemaBool()),
        ('downloaders', SchemaList(SchemaObject(RemoteDownloader))),
        ('autoDownloaded', SchemaBool()),
        ('startingDownload', SchemaBool()),
        ('lastDownloadFailed', SchemaBool()),
        ('pendingManualDL', SchemaBool()),
        ('pendingReason', SchemaString()),
        ('entry', SchemaDict(SchemaSimpleValue(), SchemaSimpleValue())),
        ('expired', SchemaBool()),
        ('keep', SchemaBool()),
        ('creationTime', SchemaDateTime()),
        ('linkNumber', SchemaInt(noneOk=True)),
    ]

VERSION = 1 
objectSchemas = [ItemSchema]

# TODO:
# 'feed' : feed.Feed,
# 'yahoo-search-feed-impl': feed.YahooSearchFeedImpl,
# 'rss-feed-impl': feed.RSSFeedImpl,
# 'search-feed-impl': feed.SearchFeedImpl,
# 'directory-feed-impl': feed.DirectoryFeedImpl,
# 'search-downloads-feed-impl': feed.SearchDownloadsFeedImpl,
# 'downloader' : downloader.RemoteDownloader,
# 'auth-password': downloader.HTTPAuthPassword,
# 'folder': folder.Folder,
# 'channel-guide': guide.ChannelGuide,
