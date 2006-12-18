import tabs
import feed
import folder
import playlist
import guide
import search

# Returns items that match search
def matchingItems(obj, searchString):
    if searchString is None:
        return True
    searchString = searchString.lower()
    if search.match (searchString, [obj.getTitle().lower(), obj.getDescription().lower()]):
        return True
    if not obj.isContainerItem:
        parent = obj.getParent()
        if parent != obj:
            return matchingItems (parent, searchString)
    return False

def downloadingItems(obj):
    return obj.getState() == 'downloading'

def downloadingOrPausedItems(obj):
    return obj.getState() in ('downloading', 'paused')

def unwatchedItems(obj):
    return obj.getState() == 'newly-downloaded' and not obj.isNonVideoFile()

def expiringItems(obj):
    return obj.getState() == 'expiring' and not obj.isNonVideoFile()

def newWatchableItems(obj):
    return (obj.getState() in ('expiring','newly-downloaded')) and not obj.isNonVideoFile()

def watchableItems(obj):
    return (obj.isDownloaded() and not obj.isNonVideoFile() and 
            not obj.isContainerItem)

newMemory = {}
newMemoryFor = None
def switchNewItemsChannel(newChannel):
    """The newItems() filter normally remembers which items were unwatched.
    This way items don't leave the new section while the user is viewing a
    channel.  This method takes care of resetting the memory when the user
    switches channels.  Call it before using the newItems() filter.
    newChannel should be the channel/channel folder object that's being
    displayed.
    """
    global newMemoryFor, newMemory
    if newMemoryFor != newChannel:
        newMemory.clear()
        newMemoryFor = newChannel

# This is "new" for the channel template
def newItems(obj):
    try:
        rv = newMemory[obj.getID()]
    except KeyError:
        rv = not obj.getViewed()
        newMemory[obj.getID()] = rv
    return rv

# Return True if a tab should be shown for obj in the frontend. The filter
# used on the database to get the list of tabs.
def mappableToTab(obj):
    return ((isinstance(obj, feed.Feed) and obj.isVisible()) or
            obj.__class__ in (tabs.StaticTab,
                folder.ChannelFolder, playlist.SavedPlaylist,
                folder.PlaylistFolder, guide.ChannelGuide))

def autoDownloads(item):
    return item.getAutoDownloaded() and item.getState() == 'downloading'

def manualDownloads(item):
    return not item.getAutoDownloaded() and not item.isPendingManualDownload() and item.getState() == 'downloading'
