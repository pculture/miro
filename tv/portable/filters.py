import tabs
import feed

# Returns items that match search
def matchingItems(obj, searchString):
    return (searchString is None or 
            searchString.lower() in obj.getTitle().lower() or
            searchString.lower() in obj.getDescription().lower())

def unviewedItems(obj):
    return not obj.getViewed()

def viewedItems(obj):
    return obj.getViewed()

def undownloadedItems(obj):
    return obj.getState() in ['stopped', 'downloading']

def downloadingItems(obj):
    return obj.getState() == 'downloading'

def downloadingItemsNonExternal(obj):
    return obj.getState() == 'downloading' and obj.getFeed().url != 'dtv:manualFeed'

def downloadingItemsExternal(obj):
    return obj.getState() == 'downloading' and obj.getFeed().url == 'dtv:manualFeed'

def unwatchedItems(obj):
    return (obj.getState() in ['finished','uploading'] or
            obj.getState() == 'saved' and not obj.getSeen())

def expiringItems(obj):
    return obj.getState() == 'watched'

def recentItems(obj):
    #FIXME make this look at the feed's time until expiration
    return obj.getState() in ['finished','uploading','watched']

def oldItems(obj):
    return obj.getState() == 'saved' and obj.getSeen()

def watchableItems(obj):
    return obj.getState() in ['finished', 'uploading', 'watched', 'saved']
    
# Return True if a tab should be shown for obj in the frontend. The filter
# used on the database to get the list of tabs.
def mappableToTab(obj):
    return isinstance(obj, tabs.StaticTab) or (isinstance(obj, feed.Feed) and
                                               obj.isVisible())
