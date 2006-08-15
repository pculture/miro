import app
import item
import folder
import feed
import guide
import tabs

def itemsByFeed(x):
    # This specifically sorts subitems by their parent's feed.
    return x.getFeed().getID()

def itemsByChannelFolder(x):
    return x.getFeed().getFolder()

def itemsByParent(x):
    return x.parent_id

def feedsByURL(x):
    return x.getOriginalURL()

def guidesByURL(x):
    return x.getURL()

def downloadsByDLID(x):
    return str(x.dlid)

def downloadsByURL(x):
    return str(x.url)

# Returns the class of the object, aggregating all Item subtypes under Item
def objectsByClass(x):
    if isinstance(x,item.Item):
        return item.Item
    else:
        return x.__class__

def itemsByState(x):
    return x.getState()

def itemsByChannelCategory(x):
    return x.getChannelCategory()

def downloadsByCategory(x):
    """Splits downloading items into 3 categories:
        normal -- not pending or external
        pending  -- pending manual downloads
        external -- external torrents
    """
    if x.getFeed().url == 'dtv:manualFeed':
        return 'external'
    elif x.isPendingManualDownload():
        return 'pending'
    else:
        return 'normal'

tabIDIndex = lambda x: x.id

tabObjIDIndex = lambda x: x.obj.getID()

def playlistsByItemID(playlist):
    return playlist.item_ids

def playlistsByItemAndFolderID(playlist):
    return [(id, playlist.folder_id) for id in playlist.item_ids]

def tabType(tab):
    return tab.type

def tabOrderType(tabOrder):
    return tabOrder.type

def byFolder(obj):
    return obj.getFolder()
