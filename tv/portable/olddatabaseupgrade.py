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
import pickle
import shutil
import threading
import types

from schema import ObjectSchema, SchemaInt, SchemaFloat
from schema import SchemaObject, SchemaBool, SchemaDateTime, SchemaTimeDelta
from schema import SchemaList, SchemaDict, SchemaString, SchemaSimpleContainer
import storedatabase

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
    import resource
    return resource.url("images/feedicon.png")

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
            except:
                self.__class__ = DropItLikeItsHot
            if self.__class__ is OldFileItem:
                self.__class__ = DropItLikeItsHot

        self.iconCache = None
        if not 'downloadedTime' in data:
            self.downloadedTime = None

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


        # No need to load a fresh channel guide here.
        #
        # Try to get a fresh version.
        # NEEDS: There's a race between self.update finishing and
        # getHTML() being called. If the latter happens first, we might get
        # the version of the channel guide from the last time DTV was run even
        # if we have a perfectly good net connection.
        #self.startLoadsIfNecessary()

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
    'BitTorrent.ConvertedMetainfo.ConvertedMetainfo': OldMetainfo,

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
    # DownloaderFactory and StaticTab shouldn't be pickled, but I've seen
    # databases where it is.
    'downloader.DownloaderFactory': DropItLikeItsHot,
    'app.StaticTab': DropItLikeItsHot,
    'feed.YahooSearchFeedImpl': DropItLikeItsHot,
    'downloader.BTDownloader': DropItLikeItsHot,
    'downloader.BTDisplay': DropItLikeItsHot,
    'downloader.HTTPDownloader': DropItLikeItsHot,
}


class FakeClassUnpickler(pickle.Unpickler):
    unpickleNormallyWhitelist = [
        'datetime.datetime', 
        'datetime.timedelta', 
        'time.struct_time',
        'feedparser.FeedParserDict'
    ]

    def find_class(self, module, name):
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
    # drop any downloaders that are referenced by items
    for o in objects:
        if isinstance(o, OldItem):
            o.downloaders = [d for d in o.downloaders \
                    if not hasattr(d, '__DropMeLikeItsHot')]

    storedatabase.saveObjectList(objects, databasePath,
            objectSchemas=objectSchemas, version=6)
