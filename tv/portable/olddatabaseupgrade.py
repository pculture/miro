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

"""Module used to upgrade from databases before we had our current scheme.

Strategy:
* Unpickle old databases using a subclass of pickle.Unpickle that loads
    fake class objects for all our DDBObjects.  The fake classes are just
    empty shells with the upgrade code that existed when we added the schema
    module.

* Save those objects to disk, using the initial schema of the new system.

"""

from new import classobj
from copy import copy
from datetime import datetime
import pickle
import shutil
import threading
import types
import time

from miro.schema import ObjectSchema, SchemaInt, SchemaFloat, SchemaSimpleItem
from miro.schema import SchemaObject, SchemaBool, SchemaDateTime, SchemaTimeDelta
from miro.schema import SchemaList, SchemaDict
from fasttypes import LinkedList
from types import NoneType
from miro import storedatabase

######################### STAGE 1 helpers  #############################
# Below is a snapshot of what the database looked like at 0.8.2.  DDBObject
# classes and other classes that get saved in the database are present only as
# skeletons, all we want from them is their __setstate__ method.  
#
# The __setstate_ methods are almost exactly like they were in 0.8.2.  I
# removed some things that don't apply to us simple restoring, then saving the
# database (starting a Thread, sending messages to the downloader daemon,
# etc.).  I added some things to make things compatible with our schema,
# mostly this means setting attributes to None, where before we used the fact
# that access the attribute would throw an AttributeError (ugh!).
#
# We prepend "Old" to the DDBObject so they're easy to recognize if
# somehow they slip through to a real database
#
# ObjectSchema
# classes are exactly as they appeared in version 6 of the schema.
#
# Why version 6?
# Previous versions were in RC's.  They dropped some of the data that we
# need to import from old databases By making olddatabaseupgrade start on
# version 6 we avoid that bug, while still giving the people using version 1
# and 2 an upgrade path that does something.


def defaultFeedIconURL():
    from miro.plat import resources
    return resources.url("images/feedicon.png")

#Dummy class for removing bogus FileItem instances
class DropItLikeItsHot(object):
    __DropMeLikeItsHot = True
    def __slurp(self, *args, **kwargs):
        pass
    def __getattr__(self, attr):
        if attr == '__DropMeLikeItsHot':
            return self.__DropMeLikeItsHot
        else:
            print "DTV: WARNING! Attempt to call '%s' on DropItLikeItsHot instance" % attr
            import traceback
            traceback.print_stack()
            return self.__slurp
    __setstate__ = __slurp
    def __repr__(self):
        return "DropMeLikeItsHot"
    def __str__(self):
        return "DropMeLikeItsHot"

class OldDDBObject(object):
    pass


class OldItem(OldDDBObject):
    # allOldItems is a hack to get around the fact that old databases can have
    # items that aren't at the top level.  In fact, they can be in fairly
    # crazy places.  See bug #2515.  So we need to keep track of the items
    # when we unpickle the objects.
    allOldItems = set()

    def __setstate__(self, state):
        (version, data) = state
        if version == 0:
            data['pendingManualDL'] = False
            if not data.has_key('linkNumber'):
                data['linkNumber'] = 0
            version += 1
        if version == 1:
            data['keep'] = False
            data['pendingReason'] = ""
            version += 1
        if version == 2:
            data['creationTime'] = datetime.now()
            version += 1
        assert(version == 3)
        data['startingDownload'] = False
        self.__dict__ = data

        # Older versions of the database allowed Feed Implementations
        # to act as feeds. If that's the case, change feed attribute
        # to contain the actual feed.
        # NOTE: This assumes that the feed object is decoded
        # before its items. That appears to be generally true
        if not issubclass(self.feed.__class__, OldDDBObject):
            try:
                self.feed = self.feed.ufeed
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                self.__class__ = DropItLikeItsHot
            if self.__class__ is OldFileItem:
                self.__class__ = DropItLikeItsHot

        self.iconCache = None
        if not 'downloadedTime' in data:
            self.downloadedTime = None
        OldItem.allOldItems.add(self)

class OldFileItem(OldItem):
    pass

class OldFeed(OldDDBObject):
    def __setstate__(self,state):
        (version, data) = state
        if version == 0:
            version += 1
        if version == 1:
            data['thumbURL'] = defaultFeedIconURL()
            version += 1
        if version == 2:
            data['lastViewed'] = datetime.min
            data['unwatched'] = 0
            data['available'] = 0
            version += 1
        assert(version == 3)
        data['updating'] = False
        if not data.has_key('initiallyAutoDownloadable'):
            data['initiallyAutoDownloadable'] = True
        self.__dict__ = data
        # This object is useless without a FeedImpl associated with it
        if not data.has_key('actualFeed'):
            self.__class__ = DropItLikeItsHot

        self.iconCache = None

class OldFolder(OldDDBObject):
    pass

class OldHTTPAuthPassword(OldDDBObject):
    pass

class OldFeedImpl:
    def __setstate__(self, data):
        self.__dict__ = data
        if 'expireTime' not in data:
            self.expireTime = None

        # Some feeds had invalid updating freq.  Catch that error here, so we
        # don't lose the dabatase when we restore it.
        try:
            self.updateFreq = int(self.updateFreq)
        except ValueError:
            self.updateFreq = -1

class OldScraperFeedImpl(OldFeedImpl):
    def __setstate__(self,state):
        (version, data) = state
        assert(version == 0)
        data['updating'] = False
        data['tempHistory'] = {}
        OldFeedImpl.__setstate__(self, data)

class OldRSSFeedImpl(OldFeedImpl):
    def __setstate__(self,state):
        (version, data) = state
        assert(version == 0)
        data['updating'] = False
        OldFeedImpl.__setstate__(self, data)

class OldSearchFeedImpl(OldRSSFeedImpl):
    pass

class OldSearchDownloadsFeedImpl(OldFeedImpl):
    pass

class OldDirectoryFeedImpl(OldFeedImpl):
    def __setstate__(self,state):
        (version, data) = state
        assert(version == 0)
        data['updating'] = False
        if not data.has_key('initialUpdate'):
            data['initialUpdate'] = False
        OldFeedImpl.__setstate__(self, data)

class OldRemoteDownloader(OldDDBObject):
    def __setstate__(self,state):
        (version, data) = state
        self.__dict__ = copy(data)
        self.status = {}
        for key in ('startTime', 'endTime', 'filename', 'state',
                'currentSize', 'totalSize', 'reasonFailed'):
            self.status[key] = self.__dict__[key]
            del self.__dict__[key]
        # force the download daemon to create a new downloader object.
        self.dlid = 'noid'

class OldChannelGuide(OldDDBObject):
    def __setstate__(self,state):
        (version, data) = state

        if version == 0:
            self.sawIntro = data['viewed']
            self.cachedGuideBody = None
            self.loadedThisSession = False
            self.cond = threading.Condition()
        else:
            assert(version == 1)
            self.__dict__ = data
            self.cond = threading.Condition()
            self.loadedThisSession = False
        if not data.has_key('id'):
            self.__class__ = DropItLikeItsHot

        # No need to load a fresh channel guide here.

class OldMetainfo(OldDDBObject):
    pass

fakeClasses = {
    'item.Item': OldItem,
    'item.FileItem': OldFileItem,
    'feed.Feed': OldFeed,
    'feed.FeedImpl': OldFeedImpl,
    'feed.RSSFeedImpl': OldRSSFeedImpl,
    'feed.ScraperFeedImpl': OldScraperFeedImpl,
    'feed.SearchFeedImpl': OldSearchFeedImpl,
    'feed.DirectoryFeedImpl': OldDirectoryFeedImpl,
    'feed.SearchDownloadsFeedImpl': OldSearchDownloadsFeedImpl,
    'downloader.HTTPAuthPassword': OldHTTPAuthPassword,
    'downloader.RemoteDownloader': OldRemoteDownloader,
    'guide.ChannelGuide': OldChannelGuide,

    # Drop these classes like they're hot!
    #
    # YahooSearchFeedImpl is a leftover class that we don't use anymore.
    #
    # The HTTPDownloader and BTDownloader classes were removed in 0.8.2.  The
    # cleanest way to handle them is to just drop them.  If the user still has
    # these in their database, too bad.  BTDownloaders may contain BTDisplay
    # and BitTorrent.ConvertedMetainfo.ConvertedMetainfo objects, drop those
    # too.
    #
    # We use BitTornado now, so drop the metainfo... We should recreate it
    # after the upgrade.
    #
    # DownloaderFactory and StaticTab shouldn't be pickled, but I've seen
    # databases where it is.
    # 
    # We used to have classes called RSSFeed, ScraperFeed, etc.  Now we have
    # the Feed class which contains a FeedImpl subclass.  Since this only
    # happens on really old databases, we should just drop the old ones.
    'BitTorrent.ConvertedMetainfo.ConvertedMetainfo': DropItLikeItsHot,
    'downloader.DownloaderFactory': DropItLikeItsHot,
    'app.StaticTab': DropItLikeItsHot,
    'feed.YahooSearchFeedImpl': DropItLikeItsHot,
    'downloader.BTDownloader': DropItLikeItsHot,
    'downloader.BTDisplay': DropItLikeItsHot,
    'downloader.HTTPDownloader': DropItLikeItsHot,
    'scheduler.ScheduleEvent': DropItLikeItsHot,
    'feed.UniversalFeed' : DropItLikeItsHot,
    'feed.RSSFeed': DropItLikeItsHot,
    'feed.ScraperFeed': DropItLikeItsHot,
    'feed.SearchFeed': DropItLikeItsHot,
    'feed.DirectoryFeed': DropItLikeItsHot,
    'feed.SearchDownloadsFeed': DropItLikeItsHot,
}


class FakeClassUnpickler(pickle.Unpickler):
    unpickleNormallyWhitelist = [
        'datetime.datetime', 
        'datetime.timedelta', 
        'time.struct_time',
        'miro.feedparser.FeedParserDict',
        '__builtin__.unicode',
    ]

    def find_class(self, module, name):
        if module == 'feedparser':
            # hack to handle the fact that everything is inside the miro
            # package nowadays
            module = 'miro.feedparser'
        fullyQualifiedName = "%s.%s" % (module, name)
        if fullyQualifiedName in fakeClasses:
            return fakeClasses[fullyQualifiedName]
        elif fullyQualifiedName in self.unpickleNormallyWhitelist:
            return pickle.Unpickler.find_class(self, module, name)
        else:
            raise ValueError("Unrecognized class: %s" % fullyQualifiedName)

class IconCache:
    # We need to define this class for the ItemSchema.  In practice we will
    # always use None instead of one of these objects.
    pass


######################### STAGE 2 helpers #############################

class DDBObjectSchema(ObjectSchema):
    klass = OldDDBObject
    classString = 'ddb-object'
    fields = [
        ('id', SchemaInt())
    ]

# Unlike the SchemaString in schema.py, this allows binary strings or
# unicode strings
class SchemaString(SchemaSimpleItem):
    def validate(self, data):
        super(SchemaSimpleItem, self).validate(data)
        self.validateTypes(data, (unicode, str))

# Unlike the simple container in schema.py, this allows binary strings
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
                        str, NoneType, datetime, time.struct_time])
                    toValidate.append(value)
            else:
                self.validateTypes(data, [bool, int, long, float, unicode,str,
                        NoneType, datetime, time.struct_time])
            try:
                data = toValidate.pop()
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                data = None


class ItemSchema(DDBObjectSchema):
    klass = OldItem
    classString = 'item'
    fields = DDBObjectSchema.fields + [
        ('feed', SchemaObject(OldFeed)),
        ('seen', SchemaBool()),
        ('downloaders', SchemaList(SchemaObject(OldRemoteDownloader))),
        ('autoDownloaded', SchemaBool()),
        ('startingDownload', SchemaBool()),
        ('lastDownloadFailed', SchemaBool()),
        ('pendingManualDL', SchemaBool()),
        ('pendingReason', SchemaString()),
        ('entry', SchemaSimpleContainer()),
        ('expired', SchemaBool()),
        ('keep', SchemaBool()),
        ('creationTime', SchemaDateTime()),
        ('linkNumber', SchemaInt(noneOk=True)),
        ('iconCache', SchemaObject(IconCache, noneOk=True)),
        ('downloadedTime', SchemaDateTime(noneOk=True)),
    ]

class FileItemSchema(ItemSchema):
    klass = OldFileItem
    classString = 'file-item'
    fields = ItemSchema.fields + [
        ('filename', SchemaString()),
    ]

class FeedSchema(DDBObjectSchema):
    klass = OldFeed
    classString = 'feed'
    fields = DDBObjectSchema.fields + [
        ('origURL', SchemaString()),
        ('errorState', SchemaBool()),
        ('initiallyAutoDownloadable', SchemaBool()),
        ('loading', SchemaBool()),
        ('actualFeed', SchemaObject(OldFeedImpl)),
        ('iconCache', SchemaObject(IconCache, noneOk=True)),
    ]

class FeedImplSchema(ObjectSchema):
    klass = OldFeedImpl
    classString = 'field-impl'
    fields = [
        ('available', SchemaInt()),
        ('unwatched', SchemaInt()),
        ('url', SchemaString()),
        ('ufeed', SchemaObject(OldFeed)),
        ('items', SchemaList(SchemaObject(OldItem))),
        ('title', SchemaString()),
        ('created', SchemaDateTime()),
        ('autoDownloadable', SchemaBool()),
        ('startfrom', SchemaDateTime()),
        ('getEverything', SchemaBool()),
        ('maxNew', SchemaInt()),
        ('fallBehind', SchemaInt()),
        ('expire', SchemaString()),
        ('visible', SchemaBool()),
        ('updating', SchemaBool()),
        ('lastViewed', SchemaDateTime()),
        ('thumbURL', SchemaString()),
        ('updateFreq', SchemaInt()),
        ('expireTime', SchemaTimeDelta(noneOk=True)),
    ]

class RSSFeedImplSchema(FeedImplSchema):
    klass = OldRSSFeedImpl
    classString = 'rss-feed-impl'
    fields = FeedImplSchema.fields + [
        ('initialHTML', SchemaString(noneOk=True)),
        ('etag', SchemaString(noneOk=True)),
        ('modified', SchemaString(noneOk=True)),
    ]

class ScraperFeedImplSchema(FeedImplSchema):
    klass = OldScraperFeedImpl
    classString = 'scraper-feed-impl'
    fields = FeedImplSchema.fields + [
        ('initialHTML', SchemaString(noneOk=True)),
        ('initialCharset', SchemaString(noneOk=True)),
        ('linkHistory', SchemaSimpleContainer()),
    ]

class SearchFeedImplSchema(FeedImplSchema):
    klass = OldSearchFeedImpl
    classString = 'search-feed-impl'
    fields = FeedImplSchema.fields + [
        ('searching', SchemaBool()),
        ('lastEngine', SchemaString()),
        ('lastQuery', SchemaString()),
    ]

class DirectoryFeedImplSchema(FeedImplSchema):
    klass = OldDirectoryFeedImpl
    classString = 'directory-feed-impl'
    # DirectoryFeedImpl doesn't have any addition fields over FeedImpl

class SearchDownloadsFeedImplSchema(FeedImplSchema):
    klass = OldSearchDownloadsFeedImpl
    classString = 'search-downloads-feed-impl'
    # SearchDownloadsFeedImpl doesn't have any addition fields over FeedImpl

class RemoteDownloaderSchema(DDBObjectSchema):
    klass = OldRemoteDownloader
    classString = 'remote-downloader'
    fields = DDBObjectSchema.fields + [
        ('url', SchemaString()),
        ('itemList', SchemaList(SchemaObject(OldItem))),
        ('dlid', SchemaString()),
        ('contentType', SchemaString(noneOk=True)),
        ('status', SchemaSimpleContainer()),
    ]

class HTTPAuthPasswordSchema(DDBObjectSchema):
    klass = OldHTTPAuthPassword
    classString = 'http-auth-password'
    fields = DDBObjectSchema.fields + [
        ('username', SchemaString()),
        ('password', SchemaString()),
        ('host', SchemaString()),
        ('realm', SchemaString()),
        ('path', SchemaString()),
        ('authScheme', SchemaString()),
    ]

class FolderSchema(DDBObjectSchema):
    klass = OldFolder
    classString = 'folder'
    fields = DDBObjectSchema.fields + [
        ('feeds', SchemaList(SchemaInt())),
        ('title', SchemaString()),
    ]

class ChannelGuideSchema(DDBObjectSchema):
    klass = OldChannelGuide
    classString = 'channel-guide'
    fields = DDBObjectSchema.fields + [
        ('sawIntro', SchemaBool()),
        ('cachedGuideBody', SchemaString(noneOk=True)),
        ('loadedThisSession', SchemaBool()),
    ]

objectSchemas = [ 
    DDBObjectSchema, ItemSchema, FileItemSchema, FeedSchema, FeedImplSchema,
    RSSFeedImplSchema, ScraperFeedImplSchema, SearchFeedImplSchema,
    DirectoryFeedImplSchema, SearchDownloadsFeedImplSchema,
    RemoteDownloaderSchema, HTTPAuthPasswordSchema, FolderSchema,
    ChannelGuideSchema, 
]

def convertOldDatabase(databasePath):
    OldItem.allOldItems = set()
    shutil.copyfile(databasePath, databasePath + '.old')
    f = open(databasePath, 'rb')
    p = FakeClassUnpickler(f)
    data = p.load()
    if type(data) == types.ListType:
        # version 0 database
        objects = data
    else:
        # version 1 database
        (version, objects) = data
    # Objects used to be stored as (object, object) tuples.  Remove the dup
    objects = [o[0] for o in objects]
    # drop any top-level DropItLikeItsHot instances
    objects = [o for o in objects if not hasattr(o, '__DropMeLikeItsHot')]
    # Set obj.id for any objects missing it
    idMissing = set()
    lastId = 0
    for o in objects:
        if hasattr(o, 'id'):
            if o.id > lastId:
                lastId = o.id
        else:
            idMissing.add(o)
    for o in idMissing:
        lastId += 1
        o.id = lastId
    # drop any downloaders that are referenced by items
    def dropItFilter(obj):
        return not hasattr(obj, '__DropMeLikeItsHot')
    for i in OldItem.allOldItems:
        i.downloaders = filter(dropItFilter, i.downloaders)

    storedatabase.saveObjectList(objects, databasePath,
            objectSchemas=objectSchemas, version=6)
