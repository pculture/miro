# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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


from threading import Condition
initialized = False
    
def initialize():
    global initialized
    initialized = True
    global allTabs, guideTabs, siteTabs, staticTabs, feedTabs, playlistTabs
    global selectedTabs, tabOrders, siteTabOrder, channelTabOrder, playlistTabOrder
    global items, fileItems, toplevelItems, nonContainerItems, unwatchedItems
    global watchableItems, newWatchableItems, uniqueWatchableItems, uniqueNewWatchableItems, manualItems
    global feeds, remoteDownloads
    global httpauths, staticTabsObjects, autoUploads, guides, default_guide
    global manualFeed, singleFeed, directoryFeed, newlyDownloadedItems
    global downloadingItems, pausedItems, manualDownloads, autoDownloads, allDownloadingItems
    global playlists, playlistFolders, channelFolders
    global themeHistories, visibleFeeds

    from miro import app
    from miro import feed
    from miro import folder
    from miro import downloader
    from miro import guide
    from miro import item
    from miro import tabs
    from miro import playlist
    from miro import theme

    from miro import indexes
    from miro import filters
    from miro import maps
    from miro import sorts

    app.db.createIndex(indexes.objectsByClass)

    allTabs = app.db.filter(filters.mappableToTab).map(maps.mapToTab)
    allTabs.createIndex(indexes.tabType)
 
    guideTabs = allTabs.filterWithIndex(indexes.tabType, 'guide')
    staticTabs = allTabs.filterWithIndex(indexes.tabType, 'statictab').sort(sorts.staticTabs)

    # no need to sort site/channel/playlist tabs...  These get ordered by the TabOrder
    # class.
    siteTabs = allTabs.filterWithIndex(indexes.tabType, 'site')
    feedTabs = allTabs.filterWithIndex(indexes.tabType, 'feed')
    playlistTabs = allTabs.filterWithIndex(indexes.tabType, 'playlist')
    selectedTabs = allTabs.filter(lambda x: x.selected)

    tabOrders = app.db.filterWithIndex(indexes.objectsByClass, tabs.TabOrder)
    tabOrders.createIndex(indexes.tabOrderType)
    siteTabOrder = tabOrders.filterWithIndex(indexes.tabOrderType, u'site')
    channelTabOrder = tabOrders.filterWithIndex(indexes.tabOrderType, u'channel')
    playlistTabOrder = tabOrders.filterWithIndex(indexes.tabOrderType, u'playlist')

    # items includes fileItems.
    items = app.db.filterWithIndex(indexes.objectsByClass, item.Item)
    fileItems = app.db.filter(lambda x: isinstance(x, item.FileItem))
    toplevelItems = items.filter(lambda x: x.feed_id is not None)
    nonContainerItems = items.filter(lambda x: not x.isContainerItem)
    unwatchedItems = nonContainerItems.filter(filters.unwatchedItems)
    #expiringItems = nonContainerItems.filter(filters.expiringItems)
    watchableItems = nonContainerItems.filter(filters.watchableItems)
    uniqueWatchableItems = watchableItems.filter(filters.uniqueItems)
    newWatchableItems = nonContainerItems.filter(filters.newWatchableItems)
    uniqueNewWatchableItems = newWatchableItems.filter(filters.uniqueItems)
    manualItems = items.filter(filters.manualItems)

    # NOTE: we can't use the objectsByClass index for fileItems, because it
    # agregates all Item subclasses into one group.
    feeds = app.db.filterWithIndex(indexes.objectsByClass, feed.Feed)
    visibleFeeds = feeds.filter(filters.feedIsVisible)
    remoteDownloads = app.db.filterWithIndex(indexes.objectsByClass, downloader.RemoteDownloader)
    httpauths = app.db.filterWithIndex(indexes.objectsByClass, downloader.HTTPAuthPassword)
    staticTabsObjects = app.db.filterWithIndex(indexes.objectsByClass, tabs.StaticTab)

    remoteDownloads.createIndex(indexes.downloadsByDLID)
    remoteDownloads.createIndex(indexes.downloadsByURL)
    autoUploads = remoteDownloads.filter(filters.autoUploadingDownloaders, sortFunc=sorts.downloadersByEndTime)
    items.createIndex(indexes.itemsByFeed, sortFunc=sorts.item)
    toplevelItems.createIndex(indexes.itemsByFeed)
    items.createIndex(indexes.itemsByParent)
    items.createIndex(indexes.itemsByChannelFolder, sortFunc=sorts.item)
    feeds.createIndex(indexes.feedsByURL)
    feeds.createIndex(indexes.byFolder)

    #FIXME: These should just be globals
    guides = app.db.filterWithIndex(indexes.objectsByClass, guide.ChannelGuide)
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
    allDownloadingItems = items.filter(filters.allDownloadingItems)

    playlists = app.db.filterWithIndex(indexes.objectsByClass,
                                   playlist.SavedPlaylist)
    playlists.createIndex(indexes.playlistsByItemID, multiValued=True)
    playlists.createIndex(indexes.playlistsByItemAndFolderID, multiValued=True)
    playlists.createIndex(indexes.byFolder)
    playlistFolders = app.db.filterWithIndex(indexes.objectsByClass,
                                         folder.PlaylistFolder)
    playlistFolders.createIndex(indexes.playlistsByItemID, multiValued=True)

    channelFolders = app.db.filterWithIndex(indexes.objectsByClass,
                                        folder.ChannelFolder)
    channelFolders.createIndex(indexes.foldersByTitle)

    themeHistories = app.db.filterWithIndex(indexes.objectsByClass, theme.ThemeHistory)
