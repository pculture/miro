from app import db
import feed
import downloader
import guide
import item
import tabs

import indexes
import filters
import maps
import sorts


db.createIndex(indexes.objectsByClass)

allTabs = db.filter(filters.mappableToTab).map(maps.mapToTab).sort(sorts.tabs)

items = db.filterWithIndex(indexes.objectsByClass,item.Item)
fileItems = db.filter(lambda x: isinstance(x, item.FileItem))
# NOTE: we can't use the objectsByClass index for fileItems, because it
# agregates all Item subclasses into one group.
feeds = db.filterWithIndex(indexes.objectsByClass,feed.Feed)
remoteDownloads = db.filterWithIndex(indexes.objectsByClass, downloader.RemoteDownloader)
httpauths = db.filterWithIndex(indexes.objectsByClass,downloader.HTTPAuthPassword)
staticTabs = db.filterWithIndex(indexes.objectsByClass,tabs.StaticTab)

remoteDownloads.createIndex(indexes.downloadsByDLID)
remoteDownloads.createIndex(indexes.downloadsByURL)
items.createIndex(indexes.itemsByFeed)
feeds.createIndex(indexes.feedsByURL)
allTabs.createIndex(indexes.tabIDIndex)
allTabs.createIndex(indexes.tabObjIDIndex)

#FIXME: These should just be globals
guide = db.filterWithIndex(indexes.objectsByClass,guide.ChannelGuide)
manualFeed = feeds.filterWithIndex(indexes.feedsByURL, 'dtv:manualFeed')
directoryFeed = feeds.filterWithIndex(indexes.feedsByURL, 'dtv:directoryfeed')

newlyDownloadedItems = items.filter(lambda x:x.getState() == 'newly-downloaded')
downloadingItems = items.filter(filters.downloadingItems)
downloadingItemsExternal = items.filter(filters.downloadingItemsExternal)
downloadingItemsNonExternal = items.filter(filters.downloadingItemsNonExternal)
manualDownloads = items.filter(filters.manualDownloads)
