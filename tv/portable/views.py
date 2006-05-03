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
feeds = db.filterWithIndex(indexes.objectsByClass,feed.Feed)
remoteDownloads = db.filterWithIndex(indexes.objectsByClass, downloader.RemoteDownloader)
httpauths = db.filterWithIndex(indexes.objectsByClass,downloader.HTTPAuthPassword)
staticTabs = db.filterWithIndex(indexes.objectsByClass,tabs.StaticTab)

remoteDownloads.createIndex(indexes.downloadsByDLID)
items.createIndex(indexes.itemsByFeed)
feeds.createIndex(indexes.feedsByURL)
allTabs.createIndex(indexes.tabIDIndex)
allTabs.createIndex(indexes.tabObjIDIndex)

#FIXME: These should just be globals
guide = db.filterWithIndex(indexes.objectsByClass,guide.ChannelGuide)
manualFeed = feeds.filterWithIndex(indexes.feedsByURL, 'dtv:manualFeed')

availableItems = items.filter(lambda x:x.getState() == 'finished' or x.getState() == 'uploading')
downloadingItems = items.filter(lambda x:x.getState() == 'downloading')

