"""Responsible for upgrading old versions of the database.

NOTE: For really old versions (before the schema.py module, see
olddatabaseupgrade.py)
"""

import schema
import util

class DatabaseTooNewError(Exception):
    """Error that we raise when we see a database that is newer than the
    version that we can update too.
    """
    pass

def upgrade(savedObjects, saveVersion, upgradeTo=None):
    """Upgrade a list of SavableObjects that were saved using an old version 
    of the database schema.

    This method will call upgradeX for each number X between saveVersion and
    upgradeTo.  For example, if saveVersion is 2 and upgradeTo is 4, this
    method is equivelant to:

        upgrade3(savedObjects)
        upgrade4(savedObjects)

    By default, upgradeTo will be the VERSION variable in schema.
    """

    changed = set()

    if upgradeTo is None:
        upgradeTo = schema.VERSION

    if saveVersion > upgradeTo:
        msg = ("Database was created by a newer version of Democracy " 
               "(db version is %s)" % saveVersion)
        raise DatabaseTooNewError(msg)

    while saveVersion < upgradeTo:
        if util.chatter:
            print "upgrading database to version %s" % (saveVersion + 1)
        upgradeFunc = globals()['upgrade%d' % (saveVersion + 1)]
        thisChanged = upgradeFunc(savedObjects)
        if thisChanged is None or changed is None:
            changed = None
        else:
            changed.update (thisChanged)
        saveVersion += 1
    return changed

def upgrade2(objectList):
    """Add a dlerType variable to all RemoteDownloader objects."""

    for o in objectList:
        if o.classString == 'remote-downloader':
            # many of our old attributes are now stored in status
            o.savedData['status'] = {}
            for key in ('startTime', 'endTime', 'filename', 'state',
                    'currentSize', 'totalSize', 'reasonFailed'):
                o.savedData['status'][key] = o.savedData[key]
                del o.savedData[key]
            # force the download daemon to create a new downloader object.
            o.savedData['dlid'] = 'noid'

def upgrade3(objectList):
    """Add the expireTime variable to FeedImpl objects."""

    for o in objectList:
        if o.classString == 'feed':
            feedImpl = o.savedData['actualFeed']
            if feedImpl is not None:
                feedImpl.savedData['expireTime'] = None

def upgrade4(objectList):
    """Add iconCache variables to all Item objects."""
    for o in objectList:
        if o.classString in ['item', 'file-item', 'feed']:
            o.savedData['iconCache'] = None

def upgrade5(objectList):
    """Upgrade metainfo from old BitTorrent format to BitTornado format"""
    for o in objectList:
        if o.classString == 'remote-downloader':
            if o.savedData['status'].has_key('metainfo'):
                o.savedData['status']['metainfo'] = None
                o.savedData['status']['infohash'] = None

def upgrade6(objectList):
    """Add downloadedTime to items."""
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            o.savedData['downloadedTime'] = None

def upgrade7(objectList):
    """Add the initialUpdate variable to FeedImpl objects."""
    for o in objectList:
        if o.classString == 'feed':
            feedImpl = o.savedData['actualFeed']
            if feedImpl is not None:
                feedImpl.savedData['initialUpdate'] = False

def upgrade8(objectList):
    """Have items point to feed_id instead of feed."""
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            o.savedData['feed_id'] = o.savedData['feed'].savedData['id']
            
def upgrade9(objectList):
    """Added the deleted field to file items"""
    for o in objectList:
        if o.classString == 'file-item':
            o.savedData['deleted'] = False

def upgrade10(objectList):
    """Add a watchedTime attribute to items.  Since we don't know when that
    was, we use the downloaded time which matches with our old behaviour.
    """

    import datetime
    changed = set()
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            if o.savedData['seen']:
                o.savedData['watchedTime'] = o.savedData['downloadedTime']
            else:
                o.savedData['watchedTime'] = None
            changed.add(o)
    return changed

def upgrade11(objectList):
    """We dropped the loadedThisSession field from ChannelGuide.  No need to
    change anything for this."""
    return set()

def upgrade12(objectList):
    import item
    from datetime import datetime
    changed = set()
    for o in objectList:
        if o.classString in ('item', 'file-item'):
            if not o.savedData.has_key('releaseDateObj'):
                try:
                    enclosures = o.savedData['entry'].enclosures
                    for enc in enclosures:
                        if item.isVideoEnclosure(enc):
                            enclosure = enc
                            break
                    o.savedData['releaseDateObj'] = datetime(*enclosure.updated_parsed[0:7])
                except:
                    try:
                        o.savedData['releaseDateObj'] = datetime(*o.savedData['entry'].updated_parsed[0:7])
                    except:
                        o.savedData['releaseDateObj'] = datetime.min
                changed.add(o)
    return changed

def upgrade13(objectList):
    """Add an isContainerItem field.  Computing this requires reading
    through files and we need to do this check anyway in onRestore, in
    case it has only been half done."""
    changed = set()
    todelete = []
    for i in xrange (len(objectList) - 1, -1, -1):
        o = objectList [i]
        if o.classString in ('item', 'file-item'):
            if o.savedData['feed_id'] == None:
                del objectList[i]
            else:
                o.savedData['isContainerItem'] = None
                o.savedData['parent_id'] = None
                o.savedData['videoFilename'] = ""
            changed.add(o)
    return changed

def upgrade14(objectList):
    """Add default and url fields to channel guide."""
    changed = set()
    todelete = []
    for o in objectList:
        if o.classString == 'channel-guide':
            o.savedData['url'] = None
            changed.add(o)
    return changed

def upgrade15(objectList):
    """In the unlikely event that someone has a playlist around, change items
    to item_ids."""
    changed = set()
    for o in objectList:
        if o.classString == 'playlist':
            o.savedData['item_ids'] = o.savedData['items']
            changed.add(o)
    return changed

def upgrade16(objectList):
    changed = set()
    for o in objectList:
        if o.classString == 'file-item':
            o.savedData['shortFilename'] = None
            changed.add(o)
    return changed

def upgrade17(objectList):
    """Add folder_id attributes to Feed and SavedPlaylist.  Add item_ids
    attribute to PlaylistFolder.
    """
    changed = set()
    for o in objectList:
        if o.classString in ('feed', 'playlist'):
            o.savedData['folder_id'] = None
            changed.add(o)
        elif o.classString == 'playlist-folder':
            o.savedData['item_ids'] = []
            changed.add(o)
    return changed

#def upgradeX (objectList):
#    """ upgrade an object list to X.  return set of changed savables. """
#    changed = set()
#    for o in objectList:
#        if objectneedschange:
#            changeObject()
#            changed.add(o)
#    return changed
