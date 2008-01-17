# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

from app import db
import feed
import folder
import downloader
import guide
import item
import tabs
import playlist
import searchengines
import theme

import indexes
import filters
import maps
import sorts

from threading import Condition
initialized = False
    
def initialize():
    global initialized
    initialized = True
    global allTabs, guideTabs, staticTabs, feedTabs, playlistTabs
    global selectedTabs, tabOrders, channelTabOrder, playlistTabOrder
    global items, fileItems, toplevelItems, nonContainerItems, unwatchedItems
    global watchableItems, newWatchableItems, uniqueWatchableItems, uniqueNewWatchableItems
    global feeds, remoteDownloads
    global httpauths, staticTabsObjects, autoUploads, guides, default_guide
    global manualFeed, singleFeed, directoryFeed, newlyDownloadedItems
    global downloadingItems, pausedItems, manualDownloads, autoDownloads
    global playlists, playlistFolders, channelFolders, searchEngines
    global themeHistories

    db.createIndex(indexes.objectsByClass)

    allTabs = db.filter(filters.mappableToTab).map(maps.mapToTab)
    allTabs.createIndex(indexes.tabType)
    guideTabs = allTabs.filterWithIndex(indexes.tabType, 'guide') \
                .sort(sorts.guideTabs)
    staticTabs = allTabs.filterWithIndex(indexes.tabType, 'statictab') \
                 .sort(sorts.staticTabs)

    # no need to sort channel/playlist tabs...  These get ordered by the TabOrder
    # class.
    feedTabs = allTabs.filterWithIndex(indexes.tabType, 'feed')
    playlistTabs = allTabs.filterWithIndex(indexes.tabType, 'playlist')
    selectedTabs = allTabs.filter(lambda x: x.selected)

    tabOrders = db.filterWithIndex(indexes.objectsByClass, tabs.TabOrder)
    tabOrders.createIndex(indexes.tabOrderType)
    channelTabOrder = tabOrders.filterWithIndex(indexes.tabOrderType, u'channel')
    playlistTabOrder = tabOrders.filterWithIndex(indexes.tabOrderType, u'playlist')

    # items includes fileItems.
    items = db.filterWithIndex(indexes.objectsByClass,item.Item)
    fileItems = db.filter(lambda x: isinstance(x, item.FileItem))
    toplevelItems = items.filter(lambda x: x.feed_id is not None)
    nonContainerItems = items.filter(lambda x: not x.isContainerItem)
    unwatchedItems = nonContainerItems.filter(filters.unwatchedItems)
    #expiringItems = nonContainerItems.filter(filters.expiringItems)
    watchableItems = nonContainerItems.filter(filters.watchableItems)
    uniqueWatchableItems = watchableItems.filter(filters.uniqueItems)
    newWatchableItems = nonContainerItems.filter(filters.newWatchableItems)
    uniqueNewWatchableItems = newWatchableItems.filter(filters.uniqueItems)

    # NOTE: we can't use the objectsByClass index for fileItems, because it
    # agregates all Item subclasses into one group.
    feeds = db.filterWithIndex(indexes.objectsByClass,feed.Feed)
    remoteDownloads = db.filterWithIndex(indexes.objectsByClass, downloader.RemoteDownloader)
    httpauths = db.filterWithIndex(indexes.objectsByClass,downloader.HTTPAuthPassword)
    staticTabsObjects = db.filterWithIndex(indexes.objectsByClass,tabs.StaticTab)

    remoteDownloads.createIndex(indexes.downloadsByDLID)
    remoteDownloads.createIndex(indexes.downloadsByURL)
    autoUploads = remoteDownloads.filter (filters.autoUploadingDownloaders, sortFunc=sorts.downloadersByEndTime)
    items.createIndex(indexes.itemsByFeed, sortFunc=sorts.item)
    toplevelItems.createIndex(indexes.itemsByFeed)
    items.createIndex(indexes.itemsByParent)
    items.createIndex(indexes.itemsByChannelFolder, sortFunc=sorts.item)
    feeds.createIndex(indexes.feedsByURL)
    feeds.createIndex(indexes.byFolder)

    #FIXME: These should just be globals
    guides = db.filterWithIndex(indexes.objectsByClass,guide.ChannelGuide)
    guides.createIndex(indexes.guidesByURL)
    default_guide = guides.filter(lambda x: x.getDefault())
    manualFeed = feeds.filterWithIndex(indexes.feedsByURL, 'dtv:manualFeed')
    singleFeed = feeds.filterWithIndex(indexes.feedsByURL, 'dtv:singleFeed')
    directoryFeed = feeds.filterWithIndex(indexes.feedsByURL,
                                          'dtv:directoryfeed')

    items.createIndex(indexes.itemsByState)
    newlyDownloadedItems = items.filterWithIndex(indexes.itemsByState,
                                                 'newly-downloaded')
    downloadingItems = items.filterWithIndex(indexes.itemsByState,
                                             'downloading')
    pausedItems = items.filterWithIndex(indexes.itemsByState, 'paused')
    downloadingItems.createIndex(indexes.downloadsByCategory)
    manualDownloads = items.filter(filters.manualDownloads)
    autoDownloads = items.filter(filters.autoDownloads)

    playlists = db.filterWithIndex(indexes.objectsByClass,
                                   playlist.SavedPlaylist)
    playlists.createIndex(indexes.playlistsByItemID, multiValued=True)
    playlists.createIndex(indexes.playlistsByItemAndFolderID, multiValued=True)
    playlists.createIndex(indexes.byFolder)
    playlistFolders = db.filterWithIndex(indexes.objectsByClass,
                                         folder.PlaylistFolder)
    playlistFolders.createIndex(indexes.playlistsByItemID, multiValued=True)

    channelFolders = db.filterWithIndex(indexes.objectsByClass,
                                        folder.ChannelFolder)
    channelFolders.createIndex(indexes.foldersByTitle)
    searchEngines = db.filterWithIndex(indexes.objectsByClass,
                                       searchengines.SearchEngine)
    searchEngines = searchEngines.sort(sorts.searchEngines)

    themeHistories = db.filterWithIndex(indexes.objectsByClass,theme.ThemeHistory)
