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

import config       # IMPORTANT!! config MUST be imported before downloader
import prefs

import database
db = database.defaultDatabase

import views
import indexes
import sorts
# import filters
import maps

import util
import feed
import item
import playlist
import tabs

import opml
import folder
import autodler
import databaseupgrade
import resources
import selection
import template
import singleclick
import storedatabase
import subscription
import downloader
import autoupdate
import xhtmltools
import guide
import eventloop
import searchengines
import download_utils
import signals

import os
import re
import shutil
import cgi
import traceback
import threading
import platform
from frontends.html import dialogs
import iconcache
import moviedata
import platformutils
import logging
import theme

# These are Python templates for string substitution, not at all
# related to our HTML based templates
from string import Template

# Something needs to import this outside of Pyrex. Might as well be app
import templatehelper
import databasehelper
# import fasttypes
import urllib
import menubar # Needed because the XUL port only includes this in pybridge
from gtcache import gettext as _
from gtcache import ngettext
from clock import clock

# Global Controller singleton
controller = None

# Backend delegate singleton
delegate = None

# Run the application. Call this, not start(), on platforms where we
# are responsible for the event loop.
def main():
    platformutils.setupLogging()
    util.setupLogging()
    Controller().Run()

# Start up the application and return. Call this, not main(), on
# platform where we are not responsible for the event loop.
def start():
    platformutils.setupLogging()
    util.setupLogging()
    Controller().runNonblocking()

###############################################################################
#### The Playback Controller base class                                    ####
###############################################################################

class PlaybackControllerBase:
    
    def __init__(self):
        self.currentPlaylist = None
        self.justPlayOne = False
        self.currentItem = None
        self.updateVideoTimeDC = None

    def configure(self, view, firstItemId=None, justPlayOne=False):
        self.currentPlaylist = Playlist(view, firstItemId)
        self.justPlayOne = justPlayOne
    
    def reset(self):
        if self.currentPlaylist is not None:
            eventloop.addIdle (self.currentPlaylist.reset, "Reset Playlist")
            self.currentPlaylist = None

    def configureWithSelection(self):
        itemSelection = controller.selection.itemListSelection
        view = itemSelection.currentView
        if itemSelection.currentView is None:
            return

        for item in view:
            itemid = item.getID()
            if itemSelection.isSelected(view, itemid) and item.isDownloaded():
                self.configure(view, itemid)
                break
    
    def enterPlayback(self):
        if self.currentPlaylist is None:
            self.configureWithSelection()
        if self.currentPlaylist is not None:
            startItem = self.currentPlaylist.cur()
            if startItem is not None:
                self.playItem(startItem)
        
    def exitPlayback(self, switchDisplay=True):
        self.reset()
        if switchDisplay:
            controller.selection.displayCurrentTabContent()
    
    def playPause(self):
        videoDisplay = controller.videoDisplay
        frame = controller.frame
        if frame.getDisplay(frame.mainDisplay) == videoDisplay:
            videoDisplay.playPause()
        else:
            self.enterPlayback()

    def pause(self):
        videoDisplay = controller.videoDisplay
        frame = controller.frame
        if frame.getDisplay(frame.mainDisplay) == videoDisplay:
            videoDisplay.pause()

    def removeItem(self, item):
        if item.idExists():
            item.executeExpire()

    def playItem(self, anItem):
        try:
            if self.currentItem:
                self.currentItem.onViewedCancel()
            self.currentItem = None
            while not os.path.exists(anItem.getVideoFilename()):
                logging.info ("movie file '%s' is missing, skipping to next",
                              anItem.getVideoFilename())
                eventloop.addIdle(self.removeItem, "Remove deleted item", args=(anItem.item,))
                anItem = self.currentPlaylist.getNext()
                if anItem is None:
                    self.stop()
                    return

            self.currentItem = anItem
            if anItem is not None:
                videoDisplay = controller.videoDisplay
                videoRenderer = videoDisplay.getRendererForItem(anItem)
                if videoRenderer is not None:
                    self.playItemInternally(anItem, videoDisplay, videoRenderer)
                else:
                    frame = controller.frame
                    if frame.getDisplay(frame.mainDisplay) is videoDisplay:
                        if videoDisplay.isFullScreen:
                            videoDisplay.exitFullScreen()
                        videoDisplay.stop()
                    self.scheduleExternalPlayback(anItem)
        except:
            signals.system.failedExn('when trying to play a video')
            self.stop()

    def playItemInternally(self, anItem, videoDisplay, videoRenderer):
        logging.info("Playing item with renderer: %s" % videoRenderer)
        controller.videoDisplay.setExternal(False)
        frame = controller.frame
        if frame.getDisplay(frame.mainDisplay) is not videoDisplay:
            frame.selectDisplay(videoDisplay, frame.mainDisplay)
        videoDisplay.selectItem(anItem, videoRenderer)
        if config.get(prefs.RESUME_VIDEOS_MODE) and anItem.resumeTime > 10:
            videoDisplay.playFromTime(anItem.resumeTime)
        else:
            videoDisplay.play()
        self.startUpdateVideoTime()

    def playItemExternally(self, itemID):
        anItem = mapToPlaylistItem(db.getObjectByID(int(itemID)))
        controller.videoInfoItem = anItem
        newDisplay = TemplateDisplay('external-playback-continue','default')
        frame = controller.frame
        frame.selectDisplay(newDisplay, frame.mainDisplay)
        return anItem
        
    def scheduleExternalPlayback(self, anItem):
        controller.videoDisplay.setExternal(True)
        controller.videoDisplay.stopOnDeselect = False
        controller.videoInfoItem = anItem
        newDisplay = TemplateDisplay('external-playback','default')
        frame = controller.frame
        frame.selectDisplay(newDisplay, frame.mainDisplay)
        anItem.markItemSeen()

    def startUpdateVideoTime(self):
        if not self.updateVideoTimeDC:
            self.updateVideoTimeDC = eventloop.addTimeout(.5, self.updateVideoTime, "Update Video Time")

    def stopUpdateVideoTime(self):
        if self.updateVideoTimeDC:
            self.updateVideoTimeDC.cancel()
            self.updateVideoTimeDC = None

    def updateVideoTime(self, repeat=True):
        t = controller.videoDisplay.getCurrentTime()
        if t != None and self.currentItem:
            self.currentItem.setResumeTime(t)
        if repeat:
            self.updateVideoTimeDC = eventloop.addTimeout(.5, self.updateVideoTime, "Update Video Time")

    def stop(self, switchDisplay=True, markAsViewed=False):
        controller.videoDisplay.setExternal(False)
        if self.updateVideoTimeDC:
            self.updateVideoTime(repeat=False)
            self.stopUpdateVideoTime()
        if self.currentItem:
            self.currentItem.onViewedCancel()
        self.currentItem = None
        frame = controller.frame
        videoDisplay = controller.videoDisplay
        if frame.getDisplay(frame.mainDisplay) == videoDisplay:
            videoDisplay.stop()
        self.exitPlayback(switchDisplay)

    def skip(self, direction, allowMovieReset=True):
        frame = controller.frame
        currentDisplay = frame.getDisplay(frame.mainDisplay)
        if self.currentPlaylist is None:
            self.stop()
        elif (allowMovieReset and direction == -1
                and hasattr(currentDisplay, 'getCurrentTime') 
                and currentDisplay.getCurrentTime() > 2.0):
            currentDisplay.goToBeginningOfMovie()
        elif config.get(prefs.SINGLE_VIDEO_PLAYBACK_MODE) or self.justPlayOne:
            self.stop()
        else:
            if direction == 1:
                nextItem = self.currentPlaylist.getNext()
            else:
                nextItem = self.currentPlaylist.getPrev()
            if nextItem is None:
                self.stop()
            else:
                if self.updateVideoTimeDC:
                    self.updateVideoTime(repeat=False)
                    self.stopUpdateVideoTime()
                self.playItem(nextItem)

    def onMovieFinished(self):
        self.stopUpdateVideoTime()
        setToStart = False
        if self.currentItem:
            self.currentItem.setResumeTime(0)
            if self.currentItem.getFeedURL() == 'dtv:singleFeed':
                setToStart = True
        if setToStart:
            frame = controller.frame
            currentDisplay = frame.getDisplay(frame.mainDisplay)
            currentDisplay.pause()
            currentDisplay.goToBeginningOfMovie()
            currentDisplay.pause()
        else:
            return self.skip(1, False)


###############################################################################
#### Base class for displays                                               ####
#### This must be defined before we import the frontend                    ####
###############################################################################

class Display:
    "Base class representing a display in a MainFrame's right-hand pane."

    def __init__(self):
        self.currentFrame = None # tracks the frame that currently has us selected

    def isSelected(self):
        return self.currentFrame is not None

    def onSelected(self, frame):
        "Called when the Display is shown in the given MainFrame."
        pass

    def onDeselected(self, frame):
        """Called when the Display is no longer shown in the given
        MainFrame. This function is called on the Display losing the
        selection before onSelected is called on the Display gaining the
        selection."""
        pass

    def onSelected_private(self, frame):
        assert(self.currentFrame == None)
        self.currentFrame = frame

    def onDeselected_private(self, frame):
        assert(self.currentFrame == frame)
        self.currentFrame = None

    # The MainFrame wants to know if we're ready to display (eg, if the
    # a HTML display has finished loading its contents, so it can display
    # immediately without flicker.) We're to call hook() when we're ready
    # to be displayed.
    def callWhenReadyToDisplay(self, hook):
        hook()

    def cancel(self):
        """Called when the Display is not shown because it is not ready yet
        and another display will take its place"""
        pass

    def getWatchable(self):
        """Subclasses can implement this if they can return a database view
        of watchable items"""
        return None


###############################################################################
#### Provides cross platform part of Video Display                         ####
#### This must be defined before we import the frontend                    ####
###############################################################################

class VideoDisplayBase (Display):
    
    def __init__(self):
        Display.__init__(self)
        self.playbackController = None
        self.volume = 1.0
        self.previousVolume = 1.0
        self.isPlaying = False
        self.isFullScreen = False
        self.isExternal = False
        self.stopOnDeselect = True
        self.renderers = list()
        self.activeRenderer = None

    def initRenderers(self):
        pass

    def setExternal(self, external):
        self.isExternal = external

    def fillMovieData (self, filename, movie_data, callback):
        for renderer in self.renderers:
            success = renderer.fillMovieData(filename, movie_data)
            if success:
                callback ()
                return
        callback ()
        
    def getRendererForItem(self, anItem):
        for renderer in self.renderers:
            if renderer.canPlayItem(anItem):
                return renderer
        return None

    def canPlayItem(self, anItem):
        return self.getRendererForItem(anItem) is not None
    
    def canPlayFile(self, filename):
        for renderer in self.renderers:
            if renderer.canPlayFile(filename):
                return True
        return False
    
    def selectItem(self, anItem, renderer):
        self.stopOnDeselect = True
        controller.videoInfoItem = anItem
        templ = TemplateDisplay('video-info', 'default')
        area = controller.frame.videoInfoDisplay
        controller.frame.selectDisplay(templ, area)

        self.setActiveRenderer(renderer)
        self.activeRenderer.selectItem(anItem)
        self.activeRenderer.setVolume(self.getVolume())

    def setActiveRenderer (self, renderer):
        self.activeRenderer = renderer

    def reset(self):
        self.isPlaying = False
        self.stopOnDeselect = True
        if self.activeRenderer is not None:
            self.activeRenderer.reset()
        self.activeRenderer = None

    def goToBeginningOfMovie(self):
        if self.activeRenderer is not None:
            self.activeRenderer.goToBeginningOfMovie()

    def playPause(self):
        if self.isPlaying:
            self.pause()
        else:
            self.play()

    def playFromTime(self, startTime):
        if self.activeRenderer is not None:
            self.activeRenderer.playFromTime(startTime)
        self.isPlaying = True

    def play(self):
        if self.activeRenderer is not None:
            self.activeRenderer.play()
        self.isPlaying = True

    def pause(self):
        if self.activeRenderer is not None:
            self.activeRenderer.pause()
        self.isPlaying = False

    def stop(self):
        if self.isFullScreen:
            self.exitFullScreen()
        if self.activeRenderer is not None:
            self.activeRenderer.stop()
        self.reset()

    def goFullScreen(self):
        self.isFullScreen = True
        if not self.isPlaying:
            self.play()

    def exitFullScreen(self):
        self.isFullScreen = False

    def getCurrentTime(self):
        if self.activeRenderer is not None:
            return self.activeRenderer.getCurrentTime()
        return None

    def setCurrentTime(self, seconds):
        if self.activeRenderer is not None:
            self.activeRenderer.setCurrentTime(seconds)

    def getProgress(self):
        if self.activeRenderer is not None:
            return self.activeRenderer.getProgress()
        return 0.0

    def setProgress(self, progress):
        if self.activeRenderer is not None:
            return self.activeRenderer.setProgress(progress)

    def getDuration(self):
        if self.activeRenderer is not None:
            return self.activeRenderer.getDuration()
        return None

    def setVolume(self, level):
        if level > 1.0:
            level = 1.0
        if level < 0.0:
            level = 0.0
        self.volume = level
        config.set(prefs.VOLUME_LEVEL, level)
        if self.activeRenderer is not None:
            self.activeRenderer.setVolume(level)

    def getVolume(self):
        return self.volume

    def muteVolume(self):
        self.previousVolume = self.getVolume()
        self.setVolume(0.0)

    def restoreVolume(self):
        self.setVolume(self.previousVolume)

    def onDeselected(self, frame):
        if self.isPlaying and self.stopOnDeselect:
            controller.playbackController.stop(False)
        
# We can now safely import the frontend module
import frontend

###############################################################################
#### The main application controller object, binding model to view         ####
###############################################################################
class Controller(frontend.Application):

    def __init__(self):
        global controller
        global delegate
        assert controller is None
        assert delegate is None
        controller = self
        delegate = frontend.UIBackendDelegate()
        frontend.Application.__init__(self)
        self.frame = None
        self.inQuit = False
        self.guideURL = None
        self.guide = None
        self.finishedStartup = False
        self.idlingNotifier = None
        self.gatheredVideos = None
        self.librarySearchTerm = None
        self.newVideosSearchTerm = None

    def getGlobalFeed(self, url):
        feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
        rv = feedView[0]
        feedView.unlink()
        return rv

    def removeGlobalFeed(self, url):
        feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
        feedView.resetCursor()
        nextfeed = feedView.getNext()
        feedView.unlink()
        if nextfeed is not None:
            logging.info ("Removing global feed %s", url)
            nextfeed.remove()

    def copyCurrentFeedURL(self):
        tabs = self.selection.getSelectedTabs()
        if len(tabs) == 1 and tabs[0].isFeed():
            delegate.copyTextToClipboard(tabs[0].obj.getURL())

    def recommendCurrentFeed(self):
        tabs = self.selection.getSelectedTabs()
        if len(tabs) == 1 and tabs[0].isFeed():
            # See also dynamic.js if changing this URL
            feed = tabs[0].obj
            query = urllib.urlencode({'url': feed.getURL(), 'title': feed.getTitle()})
            delegate.openExternalURL('http://www.videobomb.com/democracy_channel/email_friend?%s' % (query, ))

    def copyCurrentItemURL(self):
        tabs = self.selection.getSelectedItems()
        if len(tabs) == 1 and isinstance(tabs[0], item.Item):
            url = tabs[0].getURL()
            if url:
                delegate.copyTextToClipboard(url)

    def selectAllItems(self):
        self.selection.itemListSelection.selectAll()
        self.selection.setTabListActive(False)

    def removeCurrentSelection(self):
        if self.selection.tabListActive:
            selection = self.selection.tabListSelection
        else:
            selection = self.selection.itemListSelection
        seltype = selection.getType()
        if seltype == 'channeltab':
            self.removeCurrentFeed()
        elif seltype == 'addedguidetab':
            self.removeCurrentGuide()
        elif seltype == 'playlisttab':
            self.removeCurrentPlaylist()
        elif seltype == 'item':
            self.removeCurrentItems()

    def removeCurrentFeed(self):
        if self.selection.tabListSelection.getType() == 'channeltab':
            feeds = [t.obj for t in self.selection.getSelectedTabs()]
            self.removeFeeds(feeds)

    def removeCurrentGuide(self):
        if self.selection.tabListSelection.getType() == 'addedguidetab':
            guides = [t.obj for t in self.selection.getSelectedTabs()]
            if len(guides) != 1:
                raise AssertionError("Multiple guides selected")
            self.removeGuide(guides[0])

    def removeCurrentPlaylist(self):
        if self.selection.tabListSelection.getType() == 'playlisttab':
            playlists = [t.obj for t in self.selection.getSelectedTabs()]
            self.removePlaylists(playlists)

    def removeCurrentItems(self):
        if self.selection.itemListSelection.getType() != 'item':
            return
        selected = self.selection.getSelectedItems()
        if self.selection.tabListSelection.getType() != 'playlisttab':
            removable = [i for i in selected if (i.isDownloaded() or i.isExternal()) ]
            if removable:
                item.expireItems(removable)
        else:
            playlist = self.selection.getSelectedTabs()[0].obj
            for i in selected:
                playlist.removeItem(i)

    def renameCurrentTab(self, typeCheckList=None):
        selected = self.selection.getSelectedTabs()
        if len(selected) != 1:
            return
        obj = selected[0].obj
        if typeCheckList is None:
            typeCheckList = (playlist.SavedPlaylist, folder.ChannelFolder,
                folder.PlaylistFolder, feed.Feed)
        if obj.__class__ in typeCheckList:
            obj.rename()
        else:
            logging.warning ("Bad object type in renameCurrentTab() %s", obj.__class__)

    def renameCurrentChannel(self):
        self.renameCurrentTab(typeCheckList=[feed.Feed, folder.ChannelFolder])

    def renameCurrentPlaylist(self):
        self.renameCurrentTab(typeCheckList=[playlist.SavedPlaylist,
                folder.PlaylistFolder])

    def downloadCurrentItems(self):
        selected = self.selection.getSelectedItems()
        downloadable = [i for i in selected if i.isDownloadable() ]
        for item in downloadable:
            item.download()

    def stopDownloadingCurrentItems(self):
        selected = self.selection.getSelectedItems()
        downloading = [i for i in selected if i.getState() == 'downloading']
        for item in downloading:
            item.expire()

    def pauseDownloadingCurrentItems(self):
        selected = self.selection.getSelectedItems()
        downloading = [i for i in selected if i.getState() == 'downloading']
        for item in downloading:
            item.pause()

    def updateCurrentFeed(self):
        for tab in self.selection.getSelectedTabs():
            if tab.isFeed():
                tab.obj.update()

    def updateAllFeeds(self):
        for f in views.feeds:
            f.update()

    def removeGuide(self, guide):
        if guide.getDefault():
            logging.warning ("attempt to remove default guide")
            return
        title = _('Remove %s') % guide.getTitle()
        description = _("Are you sure you want to remove the guide %s?") % (guide.getTitle(),)
        dialog = dialogs.ChoiceDialog(title, description, 
                dialogs.BUTTON_YES, dialogs.BUTTON_NO)
        def dialogCallback(dialog):
            if guide.idExists() and dialog.choice == dialogs.BUTTON_YES:
                guide.remove()
        dialog.run(dialogCallback)

    def removePlaylist(self, playlist):
        return self.removePlaylists([playlist])

    def removePlaylists(self, playlists):
        if len(playlists) == 1:
            title = _('Remove %s') % playlists[0].getTitle()
            description = _("Are you sure you want to remove %s") % \
                    playlists[0].getTitle()
        else:
            title = _('Remove %s channels') % len(playlists)
            description = \
                    _("Are you sure you want to remove these %s playlists") % \
                    len(playlists)
        dialog = dialogs.ChoiceDialog(title, description, 
                dialogs.BUTTON_YES, dialogs.BUTTON_NO)
        def dialogCallback(dialog):
            if dialog.choice == dialogs.BUTTON_YES:
                for playlist in playlists:
                    if playlist.idExists():
                        playlist.remove()
        dialog.run(dialogCallback)

    def removeFeed(self, feed):
        return self.removeFeeds([feed])

    def removeFeeds(self, feeds):
        downloads = False
        downloading = False
        allDirectories = True
        for feed in feeds:
            # We only care about downloaded items in non directory feeds.
            if isinstance(feed, folder.ChannelFolder) or not feed.getURL().startswith("dtv:directoryfeed"):
                allDirectories = False
                if feed.hasDownloadedItems():
                    downloads = True
                    break
                if feed.hasDownloadingItems():
                    downloading = True
        if downloads:
            self.removeFeedsWithDownloads(feeds)
        elif downloading:
            self.removeFeedsWithDownloading(feeds)
        elif allDirectories:
            self.removeDirectoryFeeds(feeds)
        else:
            self.removeFeedsNormal(feeds)

    def removeFeedsWithDownloads(self, feeds):
        if len(feeds) == 1:
            title = _('Remove %s') % feeds[0].getTitle()
            description = _("""\
What would you like to do with the videos in this channel that you've \
downloaded?""")
        else:
            title = _('Remove %s channels') % len(feeds)
            description = _("""\
What would you like to do with the videos in these channels that you've \
downloaded?""")
        dialog = dialogs.ThreeChoiceDialog(title, description, 
                dialogs.BUTTON_KEEP_VIDEOS, dialogs.BUTTON_DELETE_VIDEOS,
                dialogs.BUTTON_CANCEL)
        def dialogCallback(dialog):
            if dialog.choice == dialogs.BUTTON_KEEP_VIDEOS:
                manualFeed = util.getSingletonDDBObject(views.manualFeed)
                for feed in feeds:
                    if feed.idExists():
                        feed.remove(moveItemsTo=manualFeed)
            elif dialog.choice == dialogs.BUTTON_DELETE_VIDEOS:
                for feed in feeds:
                    if feed.idExists():
                        feed.remove()
        dialog.run(dialogCallback)

    def removeFeedsWithDownloading(self, feeds):
        if len(feeds) == 1:
            title = _('Remove %s') % feeds[0].getTitle()
            description = _("""\
Are you sure you want to remove %s?  Any downloads in progress will \
be canceled.""") % feeds[0].getTitle()
        else:
            title = _('Remove %s channels') % len(feeds)
            description = _("""\
Are you sure you want to remove these %s channels?  Any downloads in \
progress will be canceled.""") % len(feeds)
        dialog = dialogs.ChoiceDialog(title, description, 
                dialogs.BUTTON_YES, dialogs.BUTTON_NO)
        def dialogCallback(dialog):
            if dialog.choice == dialogs.BUTTON_YES:
                for feed in feeds:
                    if feed.idExists():
                        feed.remove()
        dialog.run(dialogCallback)

    def removeFeedsNormal(self, feeds):
        if len(feeds) == 1:
            title = _('Remove %s') % feeds[0].getTitle()
            description = _("""\
Are you sure you want to remove %s?""") % feeds[0].getTitle()
        else:
            title = _('Remove %s channels') % len(feeds)
            description = _("""\
Are you sure you want to remove these %s channels?""") % len(feeds)
        dialog = dialogs.ChoiceDialog(title, description, 
                dialogs.BUTTON_YES, dialogs.BUTTON_NO)
        def dialogCallback(dialog):
            if dialog.choice == dialogs.BUTTON_YES:
                for feed in feeds:
                    if feed.idExists():
                        feed.remove()
        dialog.run(dialogCallback)

    def removeDirectoryFeeds(self, feeds):
        if len(feeds) == 1:
            title = _('Stop watching %s') % feeds[0].getTitle()
            description = _("""\
Are you sure you want to stop watching %s?""") % feeds[0].getTitle()
        else:
            title = _('Stop watching %s directories') % len(feeds)
            description = _("""\
Are you sure you want to stop watching these %s directories?""") % len(feeds)
        dialog = dialogs.ChoiceDialog(title, description, 
                dialogs.BUTTON_YES, dialogs.BUTTON_NO)
        def dialogCallback(dialog):
            if dialog.choice == dialogs.BUTTON_YES:
                for feed in feeds:
                    if feed.idExists():
                        feed.remove()
        dialog.run(dialogCallback)

    def playView(self, view, firstItemId=None, justPlayOne=False):
        self.playbackController.configure(view, firstItemId, justPlayOne)
        self.playbackController.enterPlayback()

    def shutdown(self):
        logging.info ("Shutting down Downloader...")
        downloader.shutdownDownloader(self.downloaderShutdown)

    def downloaderShutdown(self):
        logging.info ("Closing Database...")
        if database.defaultDatabase.liveStorage is not None:
            database.defaultDatabase.liveStorage.close()
        logging.info ("Shutting down event loop")
        eventloop.quit()
        logging.info ("Shutting down frontend")
        frontend.quit()

    @eventloop.asUrgent
    def setGuideURL(self, guideURL):
        """Change the URL of the current channel guide being displayed.  If no
        guide is being display, pass in None.

        This method must be called from the onSelectedTabChange in the
        platform code.  URLs are legal within guideURL will be allow
        through in onURLLoad().
        """
        self.guide = None
        if guideURL is not None:
            self.guideURL = guideURL
            for guideObj in views.guides:
                if guideObj.getURL() == controller.guideURL:
                    self.guide = guideObj
        else:
            self.guideURL = None

    @eventloop.asIdle
    def setLastVisitedGuideURL(self, url):
        selectedTabs = self.selection.getSelectedTabs()
        selectedObjects = [t.obj for t in selectedTabs]
        if (len(selectedTabs) != 1 or 
                not isinstance(selectedObjects[0], guide.ChannelGuide)):
            logging.warn("setLastVisitedGuideURL called, but a channelguide "
                    "isn't selected.  Selection: %s" % selectedObjects)
            return
        if selectedObjects[0].isPartOfGuide(url) and (
            url.startswith(u"http://") or url.startswith(u"https://")):
            selectedObjects[0].lastVisitedURL = url
            selectedObjects[0].extendHistory(url)
        else:
            logging.warn("setLastVisitedGuideURL called, but the guide is no "
                    "longer selected")

    def onShutdown(self):
        try:
            eventloop.join()        
            logging.info ("Saving preferences...")
            config.save()

#             logging.info ("Removing search feed")
#             TemplateActionHandler(None, None).resetSearch()
#             self.removeGlobalFeed('dtv:search')

            logging.info ("Shutting down icon cache updates")
            iconcache.iconCacheUpdater.shutdown()
            logging.info ("Shutting down movie data updates")
            moviedata.movieDataUpdater.shutdown()

#             logging.info ("Removing static tabs...")
#             views.allTabs.unlink() 
#             tabs.removeStaticTabs()

            if self.idlingNotifier is not None:
                logging.info ("Shutting down IdleNotifier")
                self.idlingNotifier.join()

            logging.info ("Done shutting down.")
            logging.info ("Remaining threads are:")
            for thread in threading.enumerate():
                logging.info ("%s", thread)

        except:
            signals.system.failedExn("while shutting down")
            frontend.exit(1)

    ### Handling events received from the OS (via our base class) ###

    # Called by Frontend via Application base class in response to OS request.
    def addAndSelectFeed(self, url = None, showTemplate = None):
        return GUIActionHandler().addFeed(url, showTemplate)

    def addAndSelectGuide(self, url = None):
        return GUIActionHandler().addGuide(url)

    def addSearchFeed(self, term=None, style=dialogs.SearchChannelDialog.CHANNEL, location = None):
        return GUIActionHandler().addSearchFeed(term, style, location)

    def testSearchFeedDialog(self):
        return GUIActionHandler().testSearchFeedDialog()

    ### Handling 'DTVAPI' events from the channel guide ###

    def addFeed(self, url = None):
        return GUIActionHandler().addFeed(url, selected = None)

    def selectFeed(self, url):
        return GUIActionHandler().selectFeed(url)

    ### Chrome search:
    ### Switch to the search tab and perform a search using the specified engine.

    def performSearch(self, engine, query):
        util.checkU(engine)
        util.checkU(query)
        handler = TemplateActionHandler(None, None)
        handler.updateLastSearchEngine(engine)
        handler.updateLastSearchQuery(query)
        handler.performSearch(engine, query)
        self.selection.selectTabByTemplateBase('searchtab')

    ### ----

    def handleURIDrop(self, data, **kwargs):
        """Handle an external drag that contains a text/uri-list mime-type.
        data should be the text/uri-list data, in escaped form.

        kwargs is thrown away.  It exists to catch weird URLs, like
        javascript: which sometime result in us getting extra arguments.
        """

        lastAddedFeed = None
        data = urllib.unquote(data)
        for url in data.split(u"\n"):
            url = url.strip()
            if url == u"":
                continue
            if url.startswith(u"file://"):
                filename = download_utils.getFileURLPath(url)
                filename = platformutils.osFilenameToFilenameType(filename)
                eventloop.addIdle (singleclick.openFile,
                    "Open Dropped file", args=(filename,))
            elif url.startswith(u"http:") or url.startswith(u"https:"):
                url = feed.normalizeFeedURL(url)
                if feed.validateFeedURL(url) and not feed.getFeedByURL(url):
                    lastAddedFeed = feed.Feed(url)

        if lastAddedFeed:
            controller.selection.selectTabByObject(lastAddedFeed)

    def handleDrop(self, dropData, type, sourceData):
        try:
            destType, destID = dropData.split("-")
            if destID == 'END':
                destObj = None
            elif destID == 'START':
                if destType == 'channel':
                    tabOrder = util.getSingletonDDBObject(views.channelTabOrder)
                else:
                    tabOrder = util.getSingletonDDBObject(views.playlistTabOrder)
                for tab in tabOrder.getView():
                    destObj = tab.obj
                    break
            else:
                destObj = db.getObjectByID(int(destID))
            sourceArea, sourceID = sourceData.split("-")
            sourceID = int(sourceID)
            draggedIDs = self.selection.calcSelection(sourceArea, sourceID)
        except:
            logging.exception ("error parsing drop (%r, %r, %r)",
                               dropData, type, sourceData)
            return

        if destType == 'playlist' and type == 'downloadeditem':
            # dropping an item on a playlist
            destObj.handleDNDAppend(draggedIDs)
        elif ((destType == 'channelfolder' and type == 'channel') or
                (destType == 'playlistfolder' and type == 'playlist')):
            # Dropping a channel/playlist onto a folder
            obj = db.getObjectByID(int(destID))
            obj.handleDNDAppend(draggedIDs)
        elif (destType in ('playlist', 'playlistfolder') and 
                type in ('playlist', 'playlistfolder')):
            # Reording the playlist tabs
            tabOrder = util.getSingletonDDBObject(views.playlistTabOrder)
            tabOrder.handleDNDReorder(destObj, draggedIDs)
        elif (destType in ('channel', 'channelfolder') and
                type in ('channel', 'channelfolder')):
            # Reordering the channel tabs
            tabOrder = util.getSingletonDDBObject(views.channelTabOrder)
            tabOrder.handleDNDReorder(destObj, draggedIDs)
        elif destType == "playlistitem" and type == "downloadeditem":
            # Reording items in a playlist
            playlist = self.selection.getSelectedTabs()[0].obj
            playlist.handleDNDReorder(destObj, draggedIDs)
        else:
            logging.info ("Can't handle drop. Dest type: %s Dest id: %s Type: %s",
                          destType, destID, type)

    def addToNewPlaylist(self):
        selected = controller.selection.getSelectedItems()
        childIDs = [i.getID() for i in selected if i.isDownloaded()]
        playlist.createNewPlaylist(childIDs)

    def startUploads(self):
        selected = controller.selection.getSelectedItems()
        for i in selected:
            i.startUpload()

    def newDownload(self, url = None):
        return GUIActionHandler().addDownload(url)
        
###############################################################################
#### TemplateDisplay: a HTML-template-driven right-hand display panel      ####
###############################################################################

class TemplateDisplay(frontend.HTMLDisplay):

    def __init__(self, templateName, templateState, frameHint=None, areaHint=None, 
            baseURL=None, *args, **kargs):
        """'templateName' is the name of the inital template file.  'data' is
        keys for the template. 'templateState' is a string with the state of the
        template.
        """

        logging.debug ("Processing %s", templateName)
        self.templateName = templateName
        self.templateState = templateState
        (tch, self.templateHandle) = template.fillTemplate(templateName,
                self, self.getDTVPlatformName(), self.getEventCookie(),
                self.getBodyTagExtra(), templateState = templateState,
                                                           *args, **kargs)
        self.args = args
        self.kargs = kargs
        self.haveLoaded = False
        html = tch.read()

        self.actionHandlers = [
            ModelActionHandler(delegate),
            HistoryActionHandler(self),
            GUIActionHandler(),
            TemplateActionHandler(self, self.templateHandle),
            ]

        loadTriggers = self.templateHandle.getTriggerActionURLsOnLoad()
        newPage = self.runActionURLs(loadTriggers)

        if newPage:
            self.templateHandle.unlinkTemplate()
            # FIXME - url is undefined here!
            self.__init__(re.compile(r"^template:(.*)$").match(url).group(1), frameHint, areaHint, baseURL)
        else:
            frontend.HTMLDisplay.__init__(self, html, frameHint=frameHint, areaHint=areaHint, baseURL=baseURL)

            self.templateHandle.initialFillIn()

    def __eq__(self, other):
        return (other.__class__ == TemplateDisplay and 
                self.templateName == other.templateName and 
                self.args == other.args and 
                self.kargs == other.kargs)

    def __str__(self):
        return "Template <%s> args=%s kargs=%s" % (self.templateName, self.args, self.kargs)

    def reInit(self, *args, **kargs):
        self.args = args
        self.kargs = kargs
        try:
            self.templateHandle.templateVars['reInit'](*args, **kargs)
        except:
            pass
        self.templateHandle.forceUpdate()
        
    def runActionURLs(self, triggers):
        newPage = False
        for url in triggers:
            if url.startswith('action:'):
                self.onURLLoad(url)
            elif url.startswith('template:'):
                newPage = True
                break
        return newPage

    def parseEventURL(self, url):
        match = re.match(r"[a-zA-Z]+:([^?]+)(\?(.*))?$", url)
        if match:
            path = match.group(1)
            argString = match.group(3)
            if argString is None:
                argString = u''
            argString = argString.encode('utf8')
            # argString is turned into a str since parse_qs will fail on utf8 that has been url encoded.
            argLists = cgi.parse_qs(argString, keep_blank_values=True)

            # argLists is a dictionary from parameter names to a list
            # of values given for that parameter. Take just one value
            # for each parameter, raising an error if more than one
            # was given.
            args = {}
            for key in argLists.keys():
                value = argLists[key]
                if len(value) != 1:
                    import template_compiler
                    raise template_compiler.TemplateError, "Multiple values of '%s' argument passed to '%s' action" % (key, url)
                # Cast the value results back to unicode
                try:
                    args[key.encode('ascii','replace')] = value[0].decode('utf8')
                except:
                    args[key.encode('ascii','replace')] = value[0].decode('ascii', 'replace')
            return path, args
        else:
            raise ValueError("Badly formed eventURL: %s" % url)


    def onURLLoad(self, url):
        if self.checkURL(url):
            if not controller.guide: # not on a channel guide:
                return True
            # The first time the guide is loaded in the template, several
            # pages are loaded, so this shouldn't be called during that
            # first load.  After that, this shows the spinning circle to
            # indicate loading
            if not self.haveLoaded and (url ==
                    controller.guide.getLastVisitedURL()):
                self.haveLoaded = True
            elif self.haveLoaded:
                script = 'top.miro_navigation_frame.guideUnloaded()'
                if not url.endswith(script):
                    self.execJS('top.miro_navigation_frame.guideUnloaded()')
            return True
        else:
            return False

    # Returns true if the browser should handle the URL.
    def checkURL(self, url):
        util.checkU(url)
        logging.info ("got %s", url)
        try:
            # Special-case non-'action:'-format URL
            if url.startswith (u"template:"):
                name, args = self.parseEventURL(url)
                self.dispatchAction('switchTemplate', name=name, **args)
                return False

            # Standard 'action:' URL
            if url.startswith (u"action:"):
                action, args = self.parseEventURL(url)
                self.dispatchAction(action, **args)
                return False

            # Let channel guide URLs pass through
            if controller.guide is not None and \
                   controller.guide.isPartOfGuide(url):
                controller.setLastVisitedGuideURL(url)
                return True
            if url.startswith(u'file://'):
                path = download_utils.getFileURLPath(url)
                return os.path.exists(path)

            # If we get here, this isn't a DTV URL. We should open it
            # in an external browser.
            if (url.startswith(u'http://') or url.startswith(u'https://') or
                url.startswith(u'ftp://') or url.startswith(u'mailto:') or
                url.startswith(u'feed://')):
                self.handleCandidateExternalURL(url)
                return False

        except:
            signals.system.failedExn("while handling a request", 
                    details="Handling action URL '%s'" % (url, ))

        return True

    @eventloop.asUrgent
    def handleCandidateExternalURL(self, url):
        """Open a URL that onURLLoad thinks is an external URL.
        handleCandidateExternalURL does extra checks that onURLLoad can't do
        because it's happens in the gui thread and can't access the DB.
        """

        # check for subscribe.getdemocracy.com links
        type, subscribeURLs = subscription.findSubscribeLinks(url)

        # check if the url that came from a guide, but the user switched tabs
        # before it went through.
        if len(subscribeURLs) == 0:
            for guideObj in views.guides:
                if guideObj.isPartOfGuide(url):
                    return

        normalizedURLs = []
        for url in subscribeURLs:
            normalized = feed.normalizeFeedURL(url)
            if feed.validateFeedURL(normalized):
                normalizedURLs.append(normalized)
        if normalizedURLs:
            if type == 'feed':
                for url in normalizedURLs:
                    if feed.getFeedByURL(url) is None:
                        newFeed = feed.Feed(url)
                        newFeed.blink()
            elif type == 'download':
                for url in normalizedURLs:
                    filename = platformutils.unicodeToFilename(url)
                    singleclick.downloadURL(filename)
            elif type == 'guide':
                for url in normalizedURLs:
                    if guide.getGuideByURL (url) is None:
                        guide.ChannelGuide(url)
            else:
                raise AssertionError("Unkown subscribe type")
            return

        if url.startswith(u'feed://'):
            url = u"http://" + url[len(u"feed://"):]
            f = feed.getFeedByURL(url)
            if f is None:
                f = feed.Feed(url)
            f.blink()
            return

        delegate.openExternalURL(url)

    @eventloop.asUrgent
    def dispatchAction(self, action, **kwargs):
        called = False
        start = clock()
        for handler in self.actionHandlers:
            if hasattr(handler, action):
                getattr(handler, action)(**kwargs)
                called = True
                break
        end = clock()
        if end - start > 0.5:
            logging.timing ("dispatch action %s too slow (%.3f secs)", action, end - start)
        if not called:
            logging.warning ("Ignored bad action URL: action=%s", action)

    @eventloop.asUrgent
    def onDeselected(self, frame):
        unloadTriggers = self.templateHandle.getTriggerActionURLsOnUnload()
        self.runActionURLs(unloadTriggers)
        self.unlink()
        frontend.HTMLDisplay.onDeselected(self, frame)

    def unlink(self):
        self.templateHandle.unlinkTemplate()
        self.actionHandlers = []

###############################################################################
#### Handlers for actions generated from templates, the OS, etc            ####
###############################################################################

# Functions that are safe to call from action: URLs that do nothing
# but manipulate the database.
class ModelActionHandler:
    
    def __init__(self, backEndDelegate):
        self.backEndDelegate = backEndDelegate
    
    def setAutoDownloadMode(self, feed, mode):
        obj = db.getObjectByID(int(feed))
        obj.setAutoDownloadMode(mode)

    def setExpiration(self, feed, type, time):
        obj = db.getObjectByID(int(feed))
        obj.setExpiration(type, int(time))

    def setMaxNew(self, feed, maxNew):
        obj = db.getObjectByID(int(feed))
        obj.setMaxNew(int(maxNew))

    def invalidMaxNew(self, value):
        title = _("Invalid Value")
        description = _("%s is invalid.  You must enter a non-negative "
                "number.") % value
        dialogs.MessageBoxDialog(title, description).run()

    def startDownload(self, item):
        try:
            obj = db.getObjectByID(int(item))
            obj.download()
        except database.ObjectNotFoundError:
            pass

    def removeFeed(self, id):
        try:
            feed = db.getObjectByID(int(id))
            controller.removeFeed(feed)
        except database.ObjectNotFoundError:
            pass

    def removeCurrentFeed(self):
        controller.removeCurrentFeed()

    def removeCurrentPlaylist(self):
        controller.removeCurrentPlaylist()

    def removeCurrentItems(self):
        controller.removeCurrentItems()

    def mergeToFolder(self):
        tls = controller.selection.tabListSelection
        selectionType = tls.getType()
        childIDs = set(tls.currentSelection)
        if selectionType == 'channeltab':
            folder.createNewChannelFolder(childIDs)
        elif selectionType == 'playlisttab':
            folder.createNewPlaylistFolder(childIDs)
        else:
            logging.warning ("bad selection type %s in mergeToFolder",
                             selectionType)

    def remove(self, area, id):
        selectedIDs = controller.selection.calcSelection(area, int(id))
        selectedObjects = [db.getObjectByID(id) for id in selectedIDs]
        objType = selectedObjects[0].__class__

        if objType in (feed.Feed, folder.ChannelFolder):
            controller.removeFeeds(selectedObjects)
        elif objType in (playlist.SavedPlaylist, folder.PlaylistFolder):
            controller.removePlaylists(selectedObjects)
        elif objType == guide.ChannelGuide:
            if len(selectedObjects) != 1:
                raise AssertionError("Multiple guides selected in remove")
            controller.removeGuide(selectedObjects[0])
        elif objType == item.Item:
            pl = controller.selection.getSelectedTabs()[0].obj
            pl.handleRemove(destObj, selectedIDs)
        else:
            logging.warning ("Can't handle type %s in remove()", objType)

    def rename(self, id):
        try:
            obj = db.getObjectByID(int(id))
        except:
            logging.warning ("tried to rename object that doesn't exist with id %d", int(feed))
            return
        if obj.__class__ in (playlist.SavedPlaylist, folder.ChannelFolder,
                folder.PlaylistFolder):
            obj.rename()
        else:
            logging.warning ("Unknown object type in remove() %s", type(obj))

    def updateFeed(self, feed):
        obj = db.getObjectByID(int(feed))
        obj.update()

    def copyFeedURL(self, feed):
        obj = db.getObjectByID(int(feed))
        url = obj.getURL()
        self.backEndDelegate.copyTextToClipboard(url)

    def markFeedViewed(self, feed):
        try:
            obj = db.getObjectByID(int(feed))
            obj.markAsViewed()
        except database.ObjectNotFoundError:
            pass

    def updateIcons(self, feed):
        try:
            obj = db.getObjectByID(int(feed))
            obj.updateIcons()
        except database.ObjectNotFoundError:
            pass

    def expireItem(self, item):
        try:
            obj = db.getObjectByID(int(item))
            obj.expire()
        except database.ObjectNotFoundError:
            logging.warning ("tried to expire item that doesn't exist with id %d", int(item))

    def expirePlayingItem(self, item):
        self.expireItem(item)
        controller.playbackController.skip(1)

    def addItemToLibrary(self, item):
        obj = db.getObjectByID(int(item))
        manualFeed = util.getSingletonDDBObject(views.manualFeed)
        obj.setFeed(manualFeed.getID())

    def keepItem(self, item):
        obj = db.getObjectByID(int(item))
        obj.save()

    def stopUploadItem(self, item):
        obj = db.getObjectByID(int(item))
        obj.stopUpload()

    def toggleMoreItemInfo(self, item):
        obj = db.getObjectByID(int(item))
        obj.toggleShowMoreInfo()

    def revealItem(self, item):
        obj = db.getObjectByID(int(item))
        filename = obj.getFilename()
        if not os.path.exists(filename):
            basename = os.path.basename(filename)
            title = _("Error Revealing File")
            msg = _("The file \"%s\" was deleted from outside Miro.") % basename
            dialogs.MessageBoxDialog(title, msg).run()
        else:
            self.backEndDelegate.revealFile(filename)

    def clearTorrents (self):
        items = views.items.filter(lambda x: x.getFeed().url == u'dtv:manualFeed' and x.isNonVideoFile() and not x.getState() == u"downloading")
        for i in items:
            if i.downloader is not None:
                i.downloader.setDeleteFiles(False)
            i.remove()

    def pauseDownload(self, item):
        obj = db.getObjectByID(int(item))
        obj.pause()
        
    def resumeDownload(self, item):
        obj = db.getObjectByID(int(item))
        obj.resume()

    def pauseAll (self):
        autodler.pauseDownloader()
        for item in views.downloadingItems:
            item.pause()

    def resumeAll (self):
        for item in views.pausedItems:
            item.resume()
        autodler.resumeDownloader()

    def toggleExpand(self, id):
        obj = db.getObjectByID(int(id))
        obj.setExpanded(not obj.getExpanded())

    def setRunAtStartup(self, value):
        value = (value == "1")
        self.backEndDelegate.setRunAtStartup(value)

    def setCheckEvery(self, value):
        value = int(value)
        config.set(prefs.CHECK_CHANNELS_EVERY_X_MN,value)

    def setLimitUpstream(self, value):
        value = (value == "1")
        config.set(prefs.LIMIT_UPSTREAM,value)

    def setMaxUpstream(self, value):
        value = int(value)
        config.set(prefs.UPSTREAM_LIMIT_IN_KBS,value)

    def setPreserveDiskSpace(self, value):
        value = (value == "1")
        config.set(prefs.PRESERVE_DISK_SPACE,value)

    def setDefaultExpiration(self, value):
        value = int(value)
        config.set(prefs.EXPIRE_AFTER_X_DAYS,value)

    def videoBombExternally(self, item):
        obj = db.getObjectByID(int(item))
        paramList = {}
        paramList["title"] = obj.getTitle()
        paramList["info_url"] = obj.getLink()
        paramList["hookup_url"] = obj.getPaymentLink()
        try:
            rss_url = obj.getFeed().getURL()
            if (not rss_url.startswith(u'dtv:')):
                paramList["rss_url"] = rss_url
        except:
            pass
        thumb_url = obj.getThumbnailURL()
        if thumb_url is not None:
            paramList["thumb_url"] = thumb_url

        # FIXME: add "explicit" and "tags" parameters when we get them in item

        paramString = ""
        glue = '?'
       
        # This should be first, since it's most important.
        url = obj.getURL()
        url.encode('utf-8', 'replace')
        if (not url.startswith('file:')):
            paramString = "?url=%s" % xhtmltools.urlencode(url)
            glue = '&'

        for key in paramList.keys():
            if len(paramList[key]) > 0:
                paramString = "%s%s%s=%s" % (paramString, glue, key, xhtmltools.urlencode(paramList[key]))
                glue = '&'

        # This should be last, so that if it's extra long it 
        # cut off all the other parameters
        description = obj.getDescription()
        if len(description) > 0:
            paramString = "%s%sdescription=%s" % (paramString, glue,
                    xhtmltools.urlencode(description))
        url = config.get(prefs.VIDEOBOMB_URL) + paramString
        self.backEndDelegate.openExternalURL(url)

    def changeMoviesDirectory(self, newDir, migrate):
        changeMoviesDirectory(newDir, migrate == '1')

# Test shim for test* functions on GUIActionHandler
class printResultThread(threading.Thread):

    def __init__(self, format, func):
        self.format = format
        self.func = func
        threading.Thread.__init__(self)

    def run(self):
        print (self.format % (self.func(), ))

# Functions that change the history of a guide
class HistoryActionHandler:

    def __init__(self, display):
        self.display = display

    def gotoURL(self, newURL):
        self.display.execJS('top.miro_guide_frame.location="%s"' % newURL)

    def getGuide(self):
        guides = [t.obj for t in controller.selection.getSelectedTabs()]
        if len(guides) != 1:
            return
        if not isinstance(guides[0], guide.ChannelGuide):
            return
        return guides[0]

    def back(self):
        guide = self.getGuide()
        if guide is not None:
            newURL = guide.getHistoryURL(-1)
            if newURL is not None:
                self.gotoURL(newURL)

    def forward(self):
        guide = self.getGuide()
        if guide is not None:
            newURL = guide.getHistoryURL(1)
            if newURL is not None:
                self.gotoURL(newURL)

    def home(self):
        guide = self.getGuide()
        if guide is not None:
            newURL = guide.getHistoryURL(None)
            self.gotoURL(newURL)

# Functions that are safe to call from action: URLs that can change
# the GUI presentation (and may or may not manipulate the database.)
class GUIActionHandler:

    def playUnwatched(self):
        controller.playView(views.unwatchedItems)

    def openFile(self, path):
        singleclick.openFile(path)

    def addSearchFeed(self, term=None, style = dialogs.SearchChannelDialog.CHANNEL, location = None):
        def doAdd(dialog):
            if dialog.choice == dialogs.BUTTON_CREATE_CHANNEL:
                self.addFeed(dialog.getURL())
        dialog = dialogs.SearchChannelDialog(term, style, location)
        if location == None:
            dialog.run(doAdd)
        else:
            self.addFeed(dialog.getURL())

    def addChannelSearchFeed(self, id):
        feed = db.getObjectByID(int(id))
        self.addSearchFeed(feed.inlineSearchTerm, dialogs.SearchChannelDialog.CHANNEL, int(id))

    def addEngineSearchFeed(self, term, name):
        self.addSearchFeed(term, dialogs.SearchChannelDialog.ENGINE, name)
        
    def testSearchFeedDialog(self):
        def finish(dialog):
            pass
        def thirdDialog(dialog):
            dialog = dialogs.SearchChannelDialog("Should select URL http://testurl/", dialogs.SearchChannelDialog.URL, "http://testurl/")
            dialog.run(finish)
        def secondDialog(dialog):
            dialog = dialogs.SearchChannelDialog("Should select YouTube engine", dialogs.SearchChannelDialog.ENGINE, "youtube")
            dialog.run(thirdDialog)
        dialog = dialogs.SearchChannelDialog("Should select third channel in list", dialogs.SearchChannelDialog.CHANNEL, -1)
        dialog.run(secondDialog)
        
    def addURL(self, title, message, callback, url = None):
        util.checkU(url)
        util.checkU(title)
        util.checkU(message)
        def createDialog(ltitle, lmessage, prefill = None):
            def prefillCallback():
                if prefill:
                    return prefill
                else:
                    return None
            dialog = dialogs.TextEntryDialog(ltitle, lmessage, dialogs.BUTTON_OK, dialogs.BUTTON_CANCEL, prefillCallback, fillWithClipboardURL=(prefill is None))
            def callback(dialog):
                if dialog.choice == dialogs.BUTTON_OK:
                    doAdd(dialog.value)
            dialog.run(callback)
        def doAdd(url):
            normalizedURL = feed.normalizeFeedURL(url)
            if not feed.validateFeedURL(normalizedURL):
                ltitle = title + _(" - Invalid URL")
                lmessage = _("The address you entered is not a valid URL.\nPlease double check and try again.\n\n") + message
                createDialog(ltitle, lmessage, url)
                return
            callback(normalizedURL)
        if url is None:
            createDialog(title, message)
        else:
            doAdd(url)
        
    # NEEDS: name should change to addAndSelectFeed; then we should create
    # a non-GUI addFeed to match removeFeed. (requires template updates)
    def addFeed(self, url = None, showTemplate = None, selected = '1'):
        if url:
            util.checkU(url)
        def doAdd (url):
            db.confirmDBThread()
            myFeed = feed.getFeedByURL (url)
            if myFeed is None:
                myFeed = feed.Feed(url)
    
            if selected == '1':
                controller.selection.selectTabByObject(myFeed)
            else:
                myFeed.blink()
        self.addURL (Template(_("$shortAppName - Add Channel")).substitute(shortAppName=config.get(prefs.SHORT_APP_NAME)), _("Enter the URL of the channel to add"), doAdd, url)

    def selectFeed(self, url):
        url = feed.normalizeFeedURL(url)
        db.confirmDBThread()
        # Find the feed
        myFeed = feed.getFeedByURL (url)
        if myFeed is None:
            logging.warning ("selectFeed: no such feed: %s", url)
            return
        controller.selection.selectTabByObject(myFeed)
        
    def addGuide(self, url = None, selected = '1'):
        def doAdd(url):
            db.confirmDBThread()
            myGuide = guide.getGuideByURL (url)
            if myGuide is None:
                myGuide = guide.ChannelGuide(url)
    
            if selected == '1':
                controller.selection.selectTabByObject(myGuide)
        self.addURL (Template(_("$shortAppName - Add Miro Guide")).substitute(shortAppName=config.get(prefs.SHORT_APP_NAME)), _("Enter the URL of the Miro Guide to add"), doAdd, url)

    def addDownload(self, url = None):
        def doAdd(url):
            db.confirmDBThread()
            singleclick.downloadURL(platformutils.unicodeToFilename(url))
        self.addURL (Template(_("$shortAppName - Download Video")).substitute(shortAppName=config.get(prefs.SHORT_APP_NAME)), _("Enter the URL of the video to download"), doAdd, url)

    def handleDrop(self, data, type, sourcedata):
        controller.handleDrop(data, type, sourcedata)

    def handleURIDrop(self, data, **kwargs):
        controller.handleURIDrop(data, **kwargs)

    def showHelp(self):
        delegate.openExternalURL(config.get(prefs.HELP_URL))

    def reportBug(self):
        delegate.openExternalURL(config.get(prefs.BUG_REPORT_URL))

# Functions that are safe to call from action: URLs that change state
# specific to a particular instantiation of a template, and so have to
# be scoped to a particular HTML display widget.
class TemplateActionHandler:
    
    def __init__(self, display, templateHandle):
        self.display = display
        self.templateHandle = templateHandle
        self.currentName = None

    def switchTemplate(self, name, state='default', baseURL=None, *args, **kargs):
        self.templateHandle.unlinkTemplate()
        # Switch to new template. It get the same variable
        # dictionary as we have.
        # NEEDS: currently we hardcode the display area. This means
        # that these links always affect the right-hand 'content'
        # area, even if they are loaded from the left-hand 'tab'
        # area. Actually this whole invocation is pretty hacky.
        template = TemplateDisplay(name, state, frameHint=controller.frame,
                areaHint=controller.frame.mainDisplay, baseURL=baseURL,
                *args, **kargs)
        controller.frame.selectDisplay(template, controller.frame.mainDisplay)
        self.currentName = name

    def setViewFilter(self, viewName, fieldKey, functionKey, parameter, invert):
        logging.warning ("setViewFilter deprecated")

    def setViewSort(self, viewName, fieldKey, functionKey, reverse="false"):
        logging.warning ("setViewSort deprecated")

    def setSearchString(self, searchString):
        try:
            self.templateHandle.getTemplateVariable('updateSearchString')(unicode(searchString))
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('updateSearchString')")

    def toggleDownloadsView(self):
        try:
            self.templateHandle.getTemplateVariable('toggleDownloadsView')(self.templateHandle)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('toggleDownloadsView')")

    def toggleWatchableView(self):
        try:
            self.templateHandle.getTemplateVariable('toggleWatchableView')(self.templateHandle)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('toggleWatchableView')")

    def toggleNewItemsView(self):
        try:
            self.templateHandle.getTemplateVariable('toggleNewItemsView')(self.templateHandle)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('toggleNewItemsView')")            

    def toggleAllItemsMode(self):
        try:
            self.templateHandle.getTemplateVariable('toggleAllItemsMode')(self.templateHandle)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('toggleAllItemsMode')")

    def pauseDownloads(self):
        try:
            view = self.templateHandle.getTemplateVariable('allDownloadingItems')
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('allDownloadingItems') during pauseDownloads()")
            return
        for item in view:
            item.pause()

    def resumeDownloads(self):
        try:
            view = self.templateHandle.getTemplateVariable('allDownloadingItems')
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('allDownloadingItems') during resumeDownloads()")
            return
        for item in view:
            item.resume()

    def cancelDownloads(self):
        try:
            view = self.templateHandle.getTemplateVariable('allDownloadingItems')
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('allDownloadingItems') during cancelDownloads()")
            return
        for item in view:
            item.expire()

    def playViewNamed(self, viewName, firstItemId):
        try:
            view = self.templateHandle.getTemplateVariable(viewName)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable (%s) during playViewNamed()" % (viewName,))
            return
        controller.playView(view, firstItemId)

    def playOneItem(self, viewName, itemID):
        try:
            view = self.templateHandle.getTemplateVariable(viewName)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable (%s) during playOneItem()" % (viewName,))
            return
        controller.playView(view, itemID, justPlayOne=True)

    def playNewVideos(self, id):
        try:
            obj = db.getObjectByID(int(id))
        except database.ObjectNotFoundError:
            return

        def myUnwatchedItems(obj):
            return (obj.getState() == u'newly-downloaded' and
                    not obj.isNonVideoFile() and
                    not obj.isContainerItem)

        controller.selection.selectTabByObject(obj, displayTabContent=False)
        if isinstance(obj, feed.Feed):
            feedView = views.items.filterWithIndex(indexes.itemsByFeed,
                    obj.getID())
            view = feedView.filter(myUnwatchedItems,
                                   sortFunc=sorts.item)
            controller.playView(view)
            view.unlink()
        elif isinstance(obj, folder.ChannelFolder):
            folderView = views.items.filterWithIndex(
                    indexes.itemsByChannelFolder, obj)
            view = folderView.filter(myUnwatchedItems,
                                     sortFunc=sorts.item)
            controller.playView(view)
            view.unlink()
        elif isinstance(obj, tabs.StaticTab): # new videos tab
            view = views.unwatchedItems
            controller.playView(view)
        else:
            raise TypeError("Can't get new videos for %s (type: %s)" % 
                    (obj, type(obj)))

    def playItemExternally(self, itemID):
        controller.playbackController.playItemExternally(itemID)
        
    def skipItem(self, itemID):
        controller.playbackController.skip(1)
    
    def updateLastSearchEngine(self, engine):
        searchFeed, searchDownloadsFeed = self.__getSearchFeeds()
        if searchFeed is not None:
            searchFeed.lastEngine = engine
    
    def updateLastSearchQuery(self, query):
        searchFeed, searchDownloadsFeed = self.__getSearchFeeds()
        if searchFeed is not None:
            searchFeed.lastQuery = query
        
    def performSearch(self, engine, query):
        util.checkU(engine)
        util.checkU(query)
        searchFeed, searchDownloadsFeed = self.__getSearchFeeds()
        if searchFeed is not None and searchDownloadsFeed is not None:
            searchFeed.preserveDownloads(searchDownloadsFeed)
            searchFeed.lookup(engine, query)

    def resetSearch(self):
        searchFeed, searchDownloadsFeed = self.__getSearchFeeds()
        if searchFeed is not None and searchDownloadsFeed is not None:
            searchFeed.preserveDownloads(searchDownloadsFeed)
            searchFeed.reset()

    def sortBy(self, by, section):
        try:
            self.templateHandle.getTemplateVariable('setSortBy')(by, section, self.templateHandle)
        except KeyError, e:
            logging.warning ("KeyError in getTemplateVariable ('setSortBy')")

    def handleSelect(self, area, viewName, id, shiftDown, ctrlDown):
        try:
            view = self.templateHandle.getTemplateVariable(viewName)
        except KeyError, e: # user switched templates before we got this
            logging.warning ("KeyError in getTemplateVariable (%s) during handleSelect()" % (viewName,))
            return
        shift = (shiftDown == '1')
        ctrl = (ctrlDown == '1')
        controller.selection.selectItem(area, view, int(id), shift, ctrl)

    def handleContextMenuSelect(self, id, area, viewName):
        from frontends.html import contextmenu
        try:
            obj = db.getObjectByID(int(id))
        except:
            traceback.print_exc()
        else:
            try:
                view = self.templateHandle.getTemplateVariable(viewName)
            except KeyError, e: # user switched templates before we got this
                logging.warning ("KeyError in getTemplateVariable (%s) during handleContextMenuSelect()" % (viewName,))
                return
            if not controller.selection.isSelected(area, view, int(id)):
                self.handleSelect(area, viewName, id, False, False)
            popup = contextmenu.makeContextMenu(self.currentName, view,
                    controller.selection.getSelectionForArea(area), int(id))
            if popup:
                delegate.showContextMenu(popup)

    def __getSearchFeeds(self):
        searchFeed = controller.getGlobalFeed('dtv:search')
        assert searchFeed is not None
        
        searchDownloadsFeed = controller.getGlobalFeed('dtv:searchDownloads')
        assert searchDownloadsFeed is not None

        return (searchFeed, searchDownloadsFeed)

    # The Windows XUL port can send a setVolume or setVideoProgress at
    # any time, even when there's no video display around. We can just
    # ignore it
    def setVolume(self, level):
        pass
    def setVideoProgress(self, pos):
        pass

# Helper: liberally interpret the provided string as a boolean
def stringToBoolean(string):
    if string == "" or string == "0" or string == "false":
        return False
    else:
        return True

###############################################################################
#### Playlist & Video clips                                                ####
###############################################################################

class Playlist:
    
    def __init__(self, view, firstItemId):
        self.initialView = view
        self.filteredView = self.initialView.filter(mappableToPlaylistItem)
        self.view = self.filteredView.map(mapToPlaylistItem)

        # Move the cursor to the requested item; if there's no
        # such item in the view, move the cursor to the first
        # item
        self.view.confirmDBThread()
        self.view.resetCursor()
        while True:
            cur = self.view.getNext()
            if cur == None:
                # Item not found in view. Put cursor at the first
                # item, if any.
                self.view.resetCursor()
                self.view.getNext()
                break
            if firstItemId is None or cur.getID() == int(firstItemId):
                # The cursor is now on the requested item.
                break

    def reset(self):
        self.initialView.removeView(self.filteredView)
        self.initialView = None
        self.filteredView = None
        self.view = None

    def cur(self):
        return self.itemMarkedAsViewed(self.view.cur())

    def getNext(self):
        return self.itemMarkedAsViewed(self.view.getNext())
        
    def getPrev(self):
        return self.itemMarkedAsViewed(self.view.getPrev())

    def itemMarkedAsViewed(self, anItem):
        if anItem is not None:
            eventloop.addIdle(anItem.onViewed, "Mark item viewed")
        return anItem

class PlaylistItemFromItem:

    def __init__(self, anItem):
        self.item = anItem
        self.dcOnViewed = None

    def getTitle(self):
        return self.item.getTitle()

    def getVideoFilename(self):
        return self.item.getVideoFilename()

    def getLength(self):
        # NEEDS
        return 42.42

    def onViewedExecute(self):
        if self.item.idExists():
            self.item.markItemSeen()
        self.dcOnViewed = None

    def onViewed(self):
        if self.dcOnViewed or self.item.getSeen():
            return
        self.dcOnViewed = eventloop.addTimeout(5, self.onViewedExecute, "Mark item viewed")

    def onViewedCancel(self):
        if self.dcOnViewed:
            self.dcOnViewed.cancel()
            self.dcOnViewed = None

    # Return the ID that is used by a template to indicate this item 
    def getID(self):
        return self.item.getID()

    def __getattr__(self, attr):
        return getattr(self.item, attr)

def mappableToPlaylistItem(obj):
    return (isinstance(obj, item.Item) and obj.isDownloaded())

def mapToPlaylistItem(obj):
    return PlaylistItemFromItem(obj)

# Race conditions:

# We do the migration in the dl_daemon if the dl_daemon knows about it
# so that we don't get a race condition.

@eventloop.asUrgent
def changeMoviesDirectory(newDir, migrate):
    if not util.directoryWritable(newDir):
        dialog = dialogs.MessageBoxDialog(_("Error Changing Movies Directory"), 
                _("You don't have permission to write to the directory you selected.  Miro will continue to use the old videos directory."))
        dialog.run()
        return

    oldDir = config.get(prefs.MOVIES_DIRECTORY)
    config.set(prefs.MOVIES_DIRECTORY, newDir)
    if migrate:
        views.remoteDownloads.confirmDBThread()
        for download in views.remoteDownloads:
            if download.isFinished():
                logging.info ("migrating %s", download.getFilename())
                download.migrate(newDir)
        # Pass in case they don't exist or are not empty:
        try:
            os.rmdir(os.path.join (oldDir, 'Incomplete Downloads'))
        except:
            pass
        try:
            os.rmdir(oldDir)
        except:
            pass
    util.getSingletonDDBObject(views.directoryFeed).update()

@eventloop.asUrgent
def saveVideo(currentPath, savePath):
    logging.info("saving video %s to %s" % (currentPath, savePath))
    try:
        shutil.copyfile(currentPath, savePath)
    except:
        title = _('Error Saving Video')
        name = os.path.basename(currentPath)
        text = _('An error occured while trying to save %s.  Please check that the file has not been deleted and try again.') % util.clampText(name, 50)
        dialogs.MessageBoxDialog(title, text).run()
        logging.warn("Error saving video: %s" % traceback.format_exc())

