# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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


initialized = False
    
def initialize():
    global initialized
    initialized = True
    global videoFeedTabs, audioFeedTabs, playlistTabs

    global items, fileItems, nonContainerItems, unwatchedItems
    global watchableItems, newWatchableItems, uniqueWatchableItems, uniqueNewWatchableItems, manualItems, searchItems, individualItems
    global watchableVideoItems, uniqueNewWatchableVideoItems, watchableAudioItems, uniqueNewWatchableAudioItems
    global feeds
    global sites
    global guides, default_guide
    global manualFeed, singleFeed, directoryFeed
    global downloadingItems, pausedItems, allDownloadingItems, uniqueDownloadingItems
    global playlists, playlistFolders, channelFolders
    global audioChannelFolders, videoChannelFolders
    global themeHistories, visibleFeeds, watchedFolders
    global audioVisibleFeeds, videoVisibleFeeds

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
    from miro import sorts

    app.db.createIndex(indexes.objectsByClass)

    # no need to sort site/channel/playlist tabs...  These get ordered by the TabOrder
    # class.
    videoFeedTabs = app.db.filter(filters.videoFeedTab)
    audioFeedTabs = app.db.filter(filters.audioFeedTab)
    playlistTabs = app.db.filter(filters.playlistTab)

    # items includes fileItems.
    items = app.db.filterWithIndex(indexes.objectsByClass, item.Item)
    fileItems = app.db.filter(lambda x: isinstance(x, item.FileItem))
    nonContainerItems = items.filter(lambda x: not x.isContainerItem)
    unwatchedItems = nonContainerItems.filter(filters.unwatchedItems)
    #expiringItems = nonContainerItems.filter(filters.expiringItems)
    watchableItems = nonContainerItems.filter(filters.watchableItems)
    uniqueWatchableItems = watchableItems.filter(filters.uniqueItems)
    watchableVideoItems = uniqueWatchableItems.filter(filters.videoItems)
    watchableAudioItems = uniqueWatchableItems.filter(filters.audioItems)
    newWatchableItems = nonContainerItems.filter(filters.newWatchableItems)
    uniqueNewWatchableItems = newWatchableItems.filter(filters.uniqueItems)
    uniqueNewWatchableVideoItems = uniqueNewWatchableItems.filter(filters.videoItems)
    uniqueNewWatchableAudioItems = uniqueNewWatchableItems.filter(filters.audioItems)
    manualItems = items.filter(filters.manualItems)
    searchItems = items.filter(filters.searchItems)
    # for the single items tab--this has manual items and items from searches
    individualItems = items.filter(filters.individualItems)

    sites = app.db.filterWithIndex(indexes.objectsByClass, guide.ChannelGuide)

    # NOTE: we can't use the objectsByClass index for fileItems, because it
    # agregates all Item subclasses into one group.
    feeds = app.db.filterWithIndex(indexes.objectsByClass, feed.Feed)
    visibleFeeds = feeds.filter(filters.feedIsVisible)
    videoVisibleFeeds = visibleFeeds.filter(filters.videoFeed)
    audioVisibleFeeds = visibleFeeds.filter(filters.audioFeed)

    items.createIndex(indexes.itemsByFeed, sortFunc=sorts.item)
    items.createIndex(indexes.itemsByParent)
    items.createIndex(indexes.itemsByChannelFolder, sortFunc=sorts.item)
    feeds.createIndex(indexes.feedsByURL)
    feeds.createIndex(indexes.byFolder)

    #FIXME: These should just be globals
    guides = app.db.filterWithIndex(indexes.objectsByClass, guide.ChannelGuide)
    guides.createIndex(indexes.guidesByURL)
    default_guide = guides.filter(lambda x: x.get_default())
    manualFeed = feeds.filterWithIndex(indexes.feedsByURL, 'dtv:manualFeed')
    singleFeed = feeds.filterWithIndex(indexes.feedsByURL, 'dtv:singleFeed')
    directoryFeed = feeds.filterWithIndex(indexes.feedsByURL,
                                          'dtv:directoryfeed')

    items.createIndex(indexes.itemsByState)
    downloadingItems = items.filterWithIndex(indexes.itemsByState,
                                             'downloading')
    uniqueDownloadingItems = downloadingItems.filter(filters.uniqueItems)
    pausedItems = items.filterWithIndex(indexes.itemsByState, 'paused')
    downloadingItems.createIndex(indexes.downloadsByCategory)
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
    videoChannelFolders = channelFolders.filter(filters.videoFeed)
    audioChannelFolders = channelFolders.filter(filters.audioFeed)

    themeHistories = app.db.filterWithIndex(indexes.objectsByClass, theme.ThemeHistory)

    watchedFolders = feeds.filter(filters.watchedFolders)
    items.createIndex(indexes.byLicense)
    feeds.createIndex(indexes.byLicense)
