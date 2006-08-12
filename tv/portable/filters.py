import tabs
import feed
import folder
import playlist
import guide

# Returns items that match search
def matchingItems(obj, searchString):
    return (searchString is None or 
            searchString.lower() in obj.getTitle().lower() or
            searchString.lower() in obj.getDescription().lower())

def unviewedItems(obj):
    return not obj.getViewed()

def viewedItems(obj):
    return obj.getViewed()

def downloadingItems(obj):
    return obj.getState() == 'downloading'

def unwatchedItems(obj):
    return obj.getState() == 'newly-downloaded' and not obj.isNonVideoFile()

def expiringItems(obj):
    return obj.getState() == 'expiring' and not obj.isNonVideoFile()

def oldItems(obj):
    return obj.getState() == 'saved'

def watchableItems(obj):
    return obj.isDownloaded() and not obj.isNonVideoFile()
    
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
