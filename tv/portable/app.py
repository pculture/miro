import config       # IMPORTANT!! config MUST be imported before downloader
import prefs

import database
db = database.defaultDatabase

import views
import indexes
import sorts
import filters
import maps

import menu
import util
import feed
import item
import playlist
import tabs

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
import idlenotifier 
import eventloop
import searchengines

import os
import re
import sys
import cgi
import copy
import time
import types
import random
import datetime
import traceback
import datetime
import threading
import platform
import dialogs
import iconcache
import platformutils
import logging

# Something needs to import this outside of Pyrex. Might as well be app
import templatehelper
import databasehelper
import fasttypes
import urllib
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
        firstItemId = None
        for item in view:
            id = item.getID()
            if itemSelection.isSelected(view, id) and item.isDownloaded():
                self.configure(view, id)
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
            util.failedExn('when trying to play a video')
            self.stop()

    def playItemInternally(self, anItem, videoDisplay, videoRenderer):
        logging.info("Playing item with renderer: %s" % videoRenderer)
        frame = controller.frame
        if frame.getDisplay(frame.mainDisplay) is not videoDisplay:
            frame.selectDisplay(videoDisplay, frame.mainDisplay)
        videoDisplay.selectItem(anItem, videoRenderer)
        videoDisplay.play()

    def playItemExternally(self, itemID):
        anItem = mapToPlaylistItem(db.getObjectByID(int(itemID)))
        controller.videoInfoItem = anItem
        newDisplay = TemplateDisplay('external-playback-continue','default')
        frame = controller.frame
        frame.selectDisplay(newDisplay, frame.mainDisplay)
        return anItem
        
    def scheduleExternalPlayback(self, anItem):
        controller.videoDisplay.stopOnDeselect = False
        controller.videoInfoItem = anItem
        newDisplay = TemplateDisplay('external-playback','default')
        frame = controller.frame
        frame.selectDisplay(newDisplay, frame.mainDisplay)

    def stop(self, switchDisplay=True, markAsViewed=False):
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
                self.playItem(nextItem)

    def onMovieFinished(self):
        self.currentItem = None
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
        self.stopOnDeselect = True
        self.renderers = list()
        self.activeRenderer = None

    def initRenderers(self):
        pass

    def fileDuration (self, filename, callback):
        for renderer in self.renderers:
            duration = renderer.fileDuration(filename)
            if duration != -1:
                callback (duration)
                return
        callback (-1)
        
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
        template = TemplateDisplay('video-info','default')
        area = controller.frame.videoInfoDisplay
        controller.frame.selectDisplay(template, area)
        
        self.activeRenderer = renderer
        self.activeRenderer.selectItem(anItem)
        self.activeRenderer.setVolume(self.getVolume())

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
        return 0

    def setVolume(self, level):
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
    
###############################################################################
#### Video renderer base class                                             ####
###############################################################################

class VideoRenderer:
        
    def __init__(self):
        self.interactivelySeeking = False
    
    def canPlayItem(self, anItem):
        return self.canPlayFile (anItem.getVideoFilename())
    
    def canPlayFile(self, filename):
        return False

    def fileDuration(self, filename):
        return None
    
    def getDisplayTime(self):
        seconds = self.getCurrentTime()
        return util.formatTimeForUser(seconds)
        
    def getDisplayDuration(self):
        seconds = self.getDuration()
        return util.formatTimeForUser(seconds)

    def getDisplayRemainingTime(self):
        seconds = abs(self.getCurrentTime() - self.getDuration())
        return util.formatTimeForUser(seconds, -1)

    def getProgress(self):
        duration = self.getDuration()
        if duration == 0:
            return 0.0
        return self.getCurrentTime() / duration

    def setProgress(self, progress):
        self.setCurrentTime(self.getDuration() * progress)

    def selectItem(self, anItem):
        self.selectFile (anItem.getVideoFilename())

    def selectFile(self, filename):
        pass
        
    def reset(self):
        pass

    def getCurrentTime(self):
        return 0.0

    def setCurrentTime(self, seconds):
        pass

    def getDuration(self):
        return 0.0

    def setVolume(self, level):
        pass
                
    def goToBeginningOfMovie(self):
        pass
        
    def play(self):
        pass
        
    def pause(self):
        pass
        
    def stop(self):
        pass
    
    def getRate(self):
        return 1.0
    
    def setRate(self, rate):
        pass
        
        
# We can now safely import the frontend module
import frontend

###############################################################################
#### The main application controller object, binding model to view         ####
###############################################################################

class Controller (frontend.Application):

    def __init__(self):
        global controller
        global delegate
        frontend.Application.__init__(self)
        assert controller is None
        assert delegate is None
        controller = self
        delegate = frontend.UIBackendDelegate()
        self.frame = None
        self.inQuit = False
        self.guideURL = None
        self.initial_feeds = False # True if this is the first run and there's an initial-feeds.democracy file.
        self.finishedStartup = False
        self.databaseIsSetup = threading.Event()

    ### Startup and shutdown ###

    def onStartup(self, gatheredVideos=None):
        try:
            logging.info ("Starting up Democracy Player")
            logging.info ("Version:  %s", config.get(prefs.APP_VERSION))
            logging.info ("Revision: %s", config.get(prefs.APP_REVISION))

            util.print_mem_usage("Pre everything memory check")
            
            logging.info ("Loading preferences...")

            config.load()
            config.addChangeCallback(self.configDidChange)
            
            global delegate
            feed.setDelegate(delegate)
            feed.setSortFunc(sorts.item)
            autoupdate.setDelegate(delegate)
            database.setDelegate(delegate)
            dialogs.setDelegate(delegate)
            
            if not config.get(prefs.STARTUP_TASKS_DONE):
                logging.info ("Showing startup dialog...")
                delegate.performStartupTasks(self.finishStartup)
                config.set(prefs.STARTUP_TASKS_DONE, True)
                config.save()
            else:
                database.set_thread()
                self.finishStartup(gatheredVideos)
        except:
            util.failedExn("while starting up")
            frontend.exit(1)

    def finishStartup(self, gatheredVideos=None):
        try:
            views.initialize()
            #Restoring
            util.print_mem_usage("Pre-database memory check:")
            logging.info ("Restoring database...")
            #            try:
            database.defaultDatabase.liveStorage = storedatabase.LiveStorage()
            #            except Exception:
            #                util.failedExn("While restoring database")
            util.print_mem_usage("Post-database memory check")
            logging.info ("Recomputing filters...")
            db.recomputeFilters()

            downloader.startupDownloader()

            util.print_mem_usage("Post-downloader memory check")

            self.setupGlobalFeed('dtv:manualFeed', initiallyAutoDownloadable=False)
            views.unwatchedItems.addAddCallback(self.onUnwatchedItemsCountChange)
            views.unwatchedItems.addRemoveCallback(self.onUnwatchedItemsCountChange)
            views.downloadingItems.addAddCallback(self.onDownloadingItemsCountChange)
            views.downloadingItems.addRemoveCallback(self.onDownloadingItemsCountChange)

            # Set up the search objects
            self.setupGlobalFeed('dtv:search', initiallyAutoDownloadable=False)
            self.setupGlobalFeed('dtv:searchDownloads')

            # Set up tab list
            tabs.reloadStaticTabs()
            try:
                channelTabOrder = util.getSingletonDDBObject(views.channelTabOrder)
            except LookupError:
                logging.info ("Creating channel tab order")
                channelTabOrder = tabs.TabOrder('channel')
            try:
                playlistTabOrder = util.getSingletonDDBObject(views.playlistTabOrder)
            except LookupError:
                logging.info ("Creating playlist tab order")
                playlistTabOrder = tabs.TabOrder('playlist')

            # Set up search engines
            searchengines.createEngines()

            channelGuide = _getInitialChannelGuide()

            # Keep a ref of the 'new' and 'download' tabs, we'll need'em later
            self.newTab = None
            self.downloadTab = None
            for tab in views.allTabs:
                if tab.tabTemplateBase == 'newtab':
                    self.newTab = tab
                elif tab.tabTemplateBase == 'downloadtab':
                    self.downloadTab = tab

            # If we're missing the file system videos feed, create it
            self.setupGlobalFeed('dtv:directoryfeed')

            # Start the automatic downloader daemon
            logging.info ("Spawning auto downloader...")
            autodler.startDownloader()

            # Start the idle notifier daemon
            if config.get(prefs.LIMIT_UPSTREAM) is True:
                logging.info ("Spawning idle notifier")
                self.idlingNotifier = idlenotifier.IdleNotifier(self)
                self.idlingNotifier.start()
            else:
                self.idlingNotifier = None

            # Set up the playback controller
            self.playbackController = frontend.PlaybackController()

            util.print_mem_usage("Pre-UI memory check")

            # Put up the main frame
            logging.info ("Displaying main frame...")
            self.frame = frontend.MainFrame(self)

            logging.info ("Creating video display...")
            # Set up the video display
            self.videoDisplay = frontend.VideoDisplay()
            self.videoDisplay.initRenderers()
            self.videoDisplay.playbackController = self.playbackController
            self.videoDisplay.setVolume(config.get(prefs.VOLUME_LEVEL))

            util.print_mem_usage("Post-UI memory check")

            # create our selection handler

            self.selection = selection.SelectionHandler()

            self.selection.selectFirstGuide()

            if self.initial_feeds:
                views.feedTabs.resetCursor()
                tab = views.feedTabs.getNext()
                if tab is not None:
                    self.selection.selectTabByObject(tab.obj)

            util.print_mem_usage("Post-selection memory check")

            # Reconnect items to downloaders.
            item.reconnectDownloaders()

            util.print_mem_usage("Post-item reconnect memory check")

            eventloop.addTimeout (30, autoupdate.checkForUpdates, "Check for updates")
            feed.expireItems()

            self.tabDisplay = TemplateDisplay('tablist','default',
                    playlistTabOrder=playlistTabOrder,
                    channelTabOrder=channelTabOrder)
            self.frame.selectDisplay(self.tabDisplay, self.frame.channelsDisplay)

            # If we have newly available items, provide feedback
            self.updateAvailableItemsCountFeedback()

            # Now adding the video files we possibly gathered from the startup
            # dialog
            if gatheredVideos is not None and len(gatheredVideos) > 0:
                singleclick.resetCommandLineView()
                for v in gatheredVideos:
                    try:
                        singleclick.addVideo(v)
                    except:
                        logging.info ("error while adding file %s", v)

            util.print_mem_usage("Pre single-click memory check")

            # Use an idle for parseCommandLineArgs because the frontend may
            # have put in idle calls to do set up video playback or similar
            # things.
            eventloop.addIdle(singleclick.parseCommandLineArgs, 
                    'parse command line')

            util.print_mem_usage("Post single-click memory check")

            start = clock()
            iconcache.clearOrphans()
            logging.timing ("Icon clear: %.3f", clock() - start)

            logging.info ("Starting event loop thread")
            eventloop.startup()            

            logging.info ("Finished startup sequence")
            self.finishedStartup = True

            self.databaseIsSetup.set()
        except databaseupgrade.DatabaseTooNewError:
            title = _("Database too new")
            description = _("""\
You have a database that was saved with a newer version of Democracy. \
You must download the latest version of Democracy and run that.""")
            def callback(dialog):
                eventloop.quit()
                frontend.quit()
            dialogs.MessageBoxDialog(title, description).run(callback)
            logging.info ("Starting event loop thread")
            eventloop.startup()
        except:
            util.failedExn("while finishing starting up")
            frontend.exit(1)

    def setupGlobalFeed(self, url, *args, **kwargs):
        feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
        try:
            if feedView.len() == 0:
                logging.info ("Spawning global feed %s", url)
                d = feed.Feed(url, *args, **kwargs)
            elif feedView.len() > 1:
                allFeeds = [f for f in feedView]
                for extra in allFeeds[1:]:
                    extra.remove()
                util.failed("Too many db objects for %s" % url)
        finally:
            feedView.unlink()

    def getGlobalFeed(self, url):
        feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
        rv = feedView[0]
        feedView.unlink()
        return rv

    def removeGlobalFeed(self, url):
        feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
        feedView.resetCursor()
        feed = feedView.getNext()
        feedView.unlink()
        if feed is not None:
            logging.info ("Removing global feed %s", url)
            feed.remove()

    def copyCurrentFeedURL(self):
        tabs = self.selection.getSelectedTabs()
        if len(tabs) == 1 and tabs[0].isFeed():
            delegate.copyTextToClipboard(tabs[0].obj.getURL())

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
        type = selection.getType()
        if type == 'channeltab':
            self.removeCurrentFeed()
        elif type == 'addedguidetab':
            self.removeCurrentGuide()
        elif type == 'playlisttab':
            self.removeCurrentPlaylist()
        elif type == 'item':
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
            removable = [i for i in selected if i.isDownloaded() ]
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
        for feed in feeds:
            if feed.hasDownloadedItems():
                self.removeFeedsWithDownloads(feeds)
                return
        self.removeFeedsWithoutDownloads(feeds)

    def removeFeedsWithoutDownloads(self, feeds):
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

    def playView(self, view, firstItemId=None, justPlayOne=False):
        self.playbackController.configure(view, firstItemId, justPlayOne)
        self.playbackController.enterPlayback()

    def downloaderShutdown(self):
        logging.info ("Closing Database...")
        database.defaultDatabase.liveStorage.close()
        logging.info ("Shutting down event loop")
        eventloop.quit()
        logging.info ("Shutting down frontend")
        frontend.quit()

    @eventloop.asUrgent
    def quit(self):
        global delegate
        if self.inQuit:
            return
        downloadsCount = views.downloadingItems.len()
        if downloadsCount > 0:
            title = _("Are you sure you want to quit?")
            message = ngettext ("You have %d download still in progress.", 
                                "You have %d downloads still in progress.", 
                                downloadsCount) % (downloadsCount,)
            dialog = dialogs.ChoiceDialog(title, message, 
                    dialogs.BUTTON_QUIT, dialogs.BUTTON_CANCEL)
            def callback(dialog):
                if dialog.choice == dialogs.BUTTON_QUIT:
                    self.quitStage2()
                else:
                    self.inQuit = False
            dialog.run(callback)
            self.inQuit = True
        else:
            self.quitStage2()

    def quitStage2(self):
        logging.info ("Shutting down Downloader...")
        downloader.shutdownDownloader(self.downloaderShutdown)

    def setGuideURL(self, guideURL):
        """Change the URL of the current channel guide being displayed.  If no
        guide is being display, pass in None.

        This method must be called from the onSelectedTabChange in the
        platform code.  URLs that begin with guideURL will be allow through in
        onURLLoad().
        """
        self.guideURL = guideURL

    def onShutdown(self):
        try:
            self.databaseIsSetup.wait()
            eventloop.join()        
            logging.info ("Saving preferences...")
            config.save()

            logging.info ("Removing search feed")
            TemplateActionHandler(None, None).resetSearch()
            self.removeGlobalFeed('dtv:search')

            logging.info ("Shutting down icon cache updates")
            iconcache.iconCacheUpdater.shutdown()

            logging.info ("Removing static tabs...")
            views.allTabs.unlink() 
            tabs.removeStaticTabs()

            if self.idlingNotifier is not None:
                logging.info ("Shutting down IdleNotifier")
                self.idlingNotifier.join()

            logging.info ("Done shutting down.")
            logging.info ("Remaining threads are:")
            for thread in threading.enumerate():
                logging.info ("%s", thread)

        except:
            util.failedExn("while shutting down")
            frontend.exit(1)

    ### Handling config/prefs changes
    
    def configDidChange(self, key, value):
        if key is prefs.LIMIT_UPSTREAM.key:
            if value is False:
                # The Windows version can get here without creating an
                # idlingNotifier
                try:
                    self.idlingNotifier.join()
                except:
                    pass
                self.idlingNotifier = None
            elif self.idlingNotifier is None:
                self.idlingNotifier = idlenotifier.IdleNotifier(self)
                self.idlingNotifier.start()

    ### Handling system idle events
    
    def systemHasBeenIdlingSince(self, seconds):
        self.setUpstreamLimit(False)

    def systemIsActiveAgain(self):
        self.setUpstreamLimit(True)

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

    ### Keep track of currently available+downloading items and refresh the
    ### corresponding tabs accordingly.

    def onUnwatchedItemsCountChange(self, obj, id):
        assert self.newTab is not None
        self.newTab.redraw()
        self.updateAvailableItemsCountFeedback()

    def onDownloadingItemsCountChange(self, obj, id):
        assert self.downloadTab is not None
        self.downloadTab.redraw()

    def updateAvailableItemsCountFeedback(self):
        global delegate
        count = views.unwatchedItems.len()
        delegate.updateAvailableItemsCountFeedback(count)

    ### Chrome search:
    ### Switch to the search tab and perform a search using the specified engine.

    def performSearch(self, engine, query):        
        handler = TemplateActionHandler(None, None)
        handler.updateLastSearchEngine(engine)
        handler.updateLastSearchQuery(query)
        handler.performSearch(engine, query)
        self.selection.selectTabByTemplateBase('searchtab')

    ### ----

    def setUpstreamLimit(self, setLimit):
        if setLimit:
            limit = config.get(prefs.UPSTREAM_LIMIT_IN_KBS)
            # upstream limit should be set here
        else:
            # upstream limit should be unset here
            pass

    def handleURIDrop(self, data, **kwargs):
        """Handle an external drag that contains a text/uri-list mime-type.
        data should be the text/uri-list data, in escaped form.

        kwargs is thrown away.  It exists to catch weird URLs, like
        javascript: which sometime result in us getting extra arguments.
        """

        lastAddedFeed = None
        data = urllib.unquote(data)
        for url in data.split("\n"):
            url = url.strip()
            if url == "":
                continue
            if url.startswith("file://"):
                filename = url[len('file://'):]
                eventloop.addIdle (singleclick.openFile,
                    "Open Dropped file", args=(filename,))
            elif url.startswith("http:") or url.startswith("https:"):
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

###############################################################################
#### TemplateDisplay: a HTML-template-driven right-hand display panel      ####
###############################################################################

class TemplateDisplay(frontend.HTMLDisplay):

    def __init__(self, templateName, templateState, frameHint=None, areaHint=None, 
            baseURL=None, *args, **kargs):
        "'templateName' is the name of the inital template file. 'data' is keys for the template. 'templateState' is a string with the state of the template"

        logging.debug ("Processing %s", templateName)
        self.templateName = templateName
        self.templateState = templateState
        (tch, self.templateHandle) = template.fillTemplate(templateName,
                self, self.getDTVPlatformName(), self.getEventCookie(),
                self.getBodyTagExtra(), templateState = templateState,
                                                           *args, **kargs)
        self.args = args
        self.kargs = kargs
        html = tch.read()

        self.actionHandlers = [
            ModelActionHandler(delegate),
            GUIActionHandler(),
            TemplateActionHandler(self, self.templateHandle),
            ]

        loadTriggers = self.templateHandle.getTriggerActionURLsOnLoad()
        newPage = self.runActionURLs(loadTriggers)

        if newPage:
            self.templateHandle.unlinkTemplate()
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
                argString = ''
            argLists = cgi.parse_qs(argString, keep_blank_values=True)

            # argLists is a dictionary from parameter names to a list
            # of values given for that parameter. Take just one value
            # for each parameter, raising an error if more than one
            # was given.
            args = {}
            for key in argLists.keys():
                value = argLists[key]
                if len(value) != 1:
                    raise template.TemplateError, "Multiple values of '%s' argument passed to '%s' action" % (key, action)
                args[str(key)] = value[0]
            return path, args
        else:
            raise ValueError("Badly formed eventURL: %s" % url)


    # Returns true if the browser should handle the URL.
    def onURLLoad(self, url):
        logging.info ("got %s", url)
        try:
            # Special-case non-'action:'-format URL
            if url.startswith ("template:"):
                name, args = self.parseEventURL(url)
                self.dispatchAction('switchTemplate', name=name, **args)
                return False

            # Standard 'action:' URL
            if url.startswith ("action:"):
                action, args = self.parseEventURL(url)
                self.dispatchAction(action, **args)
                return False

            # Let channel guide URLs pass through
            if (controller.guideURL is not None and
                    url.startswith(controller.guideURL)):
                return True
            if url.startswith('file://'):
                path = url[len("file://"):]
                return os.path.exists(path)

            if url.startswith('feed://'):
                url = "http://" + url[len("feed://"):]
                f = feed.getFeedByURL(url)
                if f is None:
                    f = feed.Feed(url)
                f.blink()
                return True

            # check for subscribe.getdemocracy.com links
            subscribeLinks = subscription.findSubscribeLinks(url)
            if subscribeLinks:
                for url in subscribeLinks:
                    f = feed.getFeedByURL(url)
                    if f is None:
                        f = feed.Feed(url)
                    f.blink()
                return True

            # If we get here, this isn't a DTV URL. We should open it
            # in an external browser.
            if (url.startswith('http://') or url.startswith('https://') or
                url.startswith('ftp://') or url.startswith('mailto:')):
                self.handleCandidateExternalURL(url)
                return False

        except:
            details = "Handling action URL '%s'" % (url, )
            util.failedExn("while handling a request", details = details)

        return True

    @eventloop.asUrgent
    def handleCandidateExternalURL(self, url):
        """Open a URL that onURLLoad thinks is an external URL.
        handleCandidateExternalURL does extra checks that onURLLoad can't do
        because it's happens in the gui thread and can't access the DB.
        """
        # check if the url that came from a guide, but the user switched tabs
        # before it went through.
        for guide in views.guides:
            if url.startswith(guide.getRedirectedURL()):
                return

        # check for subscribe.getdemocracy.com links
        subscribeLinks = subscription.findSubscribeLinks(url)
        if subscribeLinks:
            for url in subscribeLinks:
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
        self.templateHandle.unlinkTemplate()
        frontend.HTMLDisplay.onDeselected(self, frame)

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
        self.backEndDelegate.revealFile(filename)
        obj.save()

    def clearTorrents (self):
        items = views.items.filter(lambda x: x.getFeed().url == 'dtv:manualFeed' and x.isNonVideoFile() and not x.getState() == "downloading")
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
        paramList["title"] = obj.getTitle().encode('utf-8')
        paramList["info_url"] = obj.getLink()
        paramList["hookup_url"] = obj.getPaymentLink()
        try:
            rss_url = obj.getFeed().getURL()
            if (not rss_url.startswith('dtv:')):
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
                    xhtmltools.urlencode(description.encode('utf-8')))
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

# Functions that are safe to call from action: URLs that can change
# the GUI presentation (and may or may not manipulate the database.)
class GUIActionHandler:

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

    def addChannelSearchFeed(self, term, id):
        self.addSearchFeed(term, dialogs.SearchChannelDialog.CHANNEL, int(id))

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
            url = feed.normalizeFeedURL(url)
            if not feed.validateFeedURL(url):
                ltitle = title + _(" - Invalid URL")
                lmessage = _("The address you entered is not a valid URL.\nPlease double check and try again.\n\n") + message
                createDialog(ltitle, lmessage, url)
                return
            callback(url)
        if url is None:
            createDialog(title, message)
        else:
            doAdd(url)
        
    # NEEDS: name should change to addAndSelectFeed; then we should create
    # a non-GUI addFeed to match removeFeed. (requires template updates)
    def addFeed(self, url = None, showTemplate = None, selected = '1'):
        def doAdd (url):
            db.confirmDBThread()
            myFeed = feed.getFeedByURL (url)
            if myFeed is None:
                myFeed = feed.Feed(url)
    
            if selected == '1':
                controller.selection.selectTabByObject(myFeed)
            else:
                myFeed.blink()
        self.addURL (_("Democracy - Add Channel"), _("Enter the URL of the channel to add"), doAdd, url)

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
        self.addURL (_("Democracy - Add Channel Guide"), _("Enter the URL of the channel guide to add"), doAdd, url)

    def handleDrop(self, data, type, sourcedata):
        controller.handleDrop(data, type, sourcedata)

    def handleURIDrop(self, data, **kwargs):
        controller.handleURIDrop(data, **kwargs)

    def showHelp(self):
        # FIXME don't hardcode this URL
        delegate.openExternalURL('http://www.getdemocracy.com/help')

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

    def goToGuide(self, id):
        # Only switch to the guide if the template display is already
        # selected This prevents doubling clicking on a movie from
        # openning the channel guide instead of the video
        if controller.frame.getDisplay(controller.frame.mainDisplay) is self.display:
            if id is None:
                guide = util.getSingletonDDBObject(views.default_guide)
            else:
                try:
                    guide = views.guides.getObjectByID(int(id))
                except database.ObjectNotFoundError: 
                    # guide was deleted before we got this action URL
                    return

            # Does the Guide want to implement itself as a redirection to
            # a URL?
            (mode, location) = guide.getLocation()

            if mode == 'template':
                if location == 'guide':
                    baseURL = guide.getRedirectedURL()
                else:
                    baseURL = None
                self.switchTemplate(location, baseURL=baseURL,
                        id=guide.getID())
            elif mode == 'url':
                controller.frame.selectURL(location, \
                                           controller.frame.mainDisplay)
            else:
                raise StandardError("Invalid guide load mode '%s'" % mode)

    def setViewFilter(self, viewName, fieldKey, functionKey, parameter, invert):
        logging.warning ("setViewFilter deprecated")

    def setViewSort(self, viewName, fieldKey, functionKey, reverse="false"):
        logging.warning ("setViewSort deprecated")

    def setSearchString(self, searchString):
        self.templateHandle.getTemplateVariable('updateSearchString')(unicode(searchString))

    def toggleDownloadsView(self):
        self.templateHandle.getTemplateVariable('toggleDownloadsView')(self.templateHandle)

    def toggleWatchableView(self):
        self.templateHandle.getTemplateVariable('toggleWatchableView')(self.templateHandle)

    def toggleNewItemsView(self):
        self.templateHandle.getTemplateVariable('toggleNewItemsView')(self.templateHandle)

    def toggleAllItemsMode(self):
        self.templateHandle.getTemplateVariable('toggleAllItemsMode')(self.templateHandle)

    def pauseDownloads(self):
        view = self.templateHandle.getTemplateVariable('allDownloadingItems')
        for item in view:
            item.pause()

    def resumeDownloads(self):
        view = self.templateHandle.getTemplateVariable('allDownloadingItems')
        for item in view:
            item.resume()

    def cancelDownloads(self):
        view = self.templateHandle.getTemplateVariable('allDownloadingItems')
        for item in view:
            item.expire()

    def playViewNamed(self, viewName, firstItemId):
        view = self.templateHandle.getTemplateVariable(viewName)
        controller.playView(view, firstItemId)

    def playOneItem(self, viewName, itemID):
        view = self.templateHandle.getTemplateVariable(viewName)
        controller.playView(view, itemID, justPlayOne=True)

    def playNewVideos(self, id):
        try:
            obj = db.getObjectByID(int(id))
        except ObjectNotFoundError:
            return

        def myUnwatchedItems(obj):
            return (obj.getState() == 'newly-downloaded' and
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
        self.templateHandle.getTemplateVariable('setSortBy')(by, section, self.templateHandle)

    def handleSelect(self, area, viewName, id, shiftDown, ctrlDown):
        try:
            view = self.templateHandle.getTemplateVariable(viewName)
        except KeyError: # user switched templates before we got this
            return
        shift = (shiftDown == '1')
        ctrl = (ctrlDown == '1')
        controller.selection.selectItem(area, view, int(id), shift, ctrl)

    def handleContextMenuSelect(self, id, area, viewName):
        try:
            obj = db.getObjectByID(int(id))
        except:
            traceback.print_exc()
        else:
            view = self.templateHandle.getTemplateVariable(viewName)
            if not controller.selection.isSelected(area, view, int(id)):
                self.handleSelect(area, viewName, id, False, False)
            popup = menu.makeContextMenu(self.currentName, view,
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

def _defaultFeeds():
    defaultFeedURLs = [ ('News and Tech',
                         ['http://jetset.blip.tv/?skin=rss',
                          'http://revision3.com/diggnation/feed/quicktime-large',
                          'http://www.podshow.com/feeds/hd.xml',
                          'http://podcast.msnbc.com/audio/podcast/MSNBC-NN-NETCAST-M4V.xml']),
                        
                        ('Entertainment',
                         ['http://feeds.feedburner.com/freshtopia',
                          'http://feeds.feedburner.com/thechannelchannel/featured']),

                        ('High-Def',
                         ['http://www.telemusicvision.com/videos/rss.php?i=1',
                          'http://revision3.com/pixelperfect/feed/quicktime-high-definition',
                          'http://www.movedigital.com/rss/rocketboom/main.xml'])
                        ]
    if platform.system() == "MacOS":
        defaultFeedURLs.append(
            ('Mac',
             ['http://feeds.feedburner.com/peters-screencast',
              'http://macbreak.libsyn.com/rss',
              'http://www.podshow.com/feeds/appleclipscomputer.xml',
              'http://libsyn.com/podcasts/donmc/_static/scoipod.xml']))

    if platform.system() == "Windows":
        defaultFeedURLs[1][1][:0] = ['http://feeds.feedburner.com/Terravideos']
    else:
        defaultFeedURLs[1][1][:0] = ['http://www.zefrank.com/theshow/index.xml',
                                  'http://feeds.feedburner.com/AskANinja']

    for defaultFolder in defaultFeedURLs:
        c_folder = folder.ChannelFolder(defaultFolder[0])
        for url in defaultFolder[1]:
            d_feed = feed.Feed(url, initiallyAutoDownloadable=False)
            d_feed.setFolder(c_folder)
    playlist.SavedPlaylist(_("Example Playlist"))

def _getInitialChannelGuide():
    default_guide = None
    for guideObj in views.guides:
        if default_guide is None:
            if guideObj.getDefault():
                default_guide = guideObj
        else:
            guideObj.remove()
    if default_guide is None:
        logging.info ("Spawning Channel Guide...")
        default_guide = guide.ChannelGuide()
        initialFeeds = resources.path("initial-feeds.democracy")
        if os.path.exists(initialFeeds):
            urls = subscription.parseFile(initialFeeds)
            if urls is not None:
                for url in urls:
                    feed.Feed(url, initiallyAutoDownloadable=False)
            dialog = dialogs.MessageBoxDialog(_("Custom Channels"), _("You are running a version of Democracy Player with a custom set of channels."))
            dialog.run()
            controller.initial_feeds = True
        else:
            _defaultFeeds()
    return default_guide

# Race conditions:

# We do the migration in the dl_daemon if the dl_daemon knows about it
# so that we don't get a race condition.

@eventloop.asUrgent
def changeMoviesDirectory(newDir, migrate):
    oldDir = config.get(prefs.MOVIES_DIRECTORY)
    config.set(prefs.MOVIES_DIRECTORY, newDir)
    if migrate:
        views.remoteDownloads.confirmDBThread()
        for download in views.remoteDownloads:
            logging.info ("migrating %s", download.getFilename())
            download.migrate(newDir)
        for item in views.fileItems:
            # Only migrate top level items.
            if item.parent_id is None:
                currentFilename = item.getFilename()
                if os.path.dirname(currentFilename) == oldDir:
                    item.migrate(newDir)
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
