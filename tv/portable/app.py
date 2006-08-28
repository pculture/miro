import config       # IMPORTANT!! config MUST be imported before downloader
import prefs

import database
db = database.defaultDatabase

import views
import indexes
import sorts
import filters
import maps

import util
import feed
import item
import playlist
import tabs

import folder
import autodler
import resource
import selection
import template
import singleclick
import storedatabase
import downloader
import autoupdate
import xhtmltools
import guide
import idlenotifier 
import eventloop

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
import dialogs
from iconcache import iconCacheUpdater

# Something needs to import this outside of Pyrex. Might as well be app
import templatehelper
import databasehelper
import fasttypes
import urllib
from gtcache import gettext as _
from gtcache import ngettext

from BitTornado.clock import clock

# Global Controller singleton
controller = None

# Backend delegate singleton
delegate = None

# Run the application. Call this, not start(), on platforms where we
# are responsible for the event loop.
def main():
    Controller().Run()

# Start up the application and return. Call this, not main(), on
# platform where we are not responsible for the event loop.
def start():
    Controller().runNonblocking()

###############################################################################
#### The Playback Controller base class                                    ####
###############################################################################

class PlaybackControllerBase:
    
    def __init__(self):
        self.currentPlaylist = None

    def configure(self, view, firstItemId=None):
        self.currentPlaylist = Playlist(view, firstItemId)
    
    def reset(self):
        if self.currentPlaylist is not None:
            eventloop.addIdle (self.currentPlaylist.reset, "Reset Playlist")
            self.currentPlaylist = None
    
    def enterPlayback(self):
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

    def playItem(self, anItem):
        try:
            while not os.path.exists(anItem.getVideoFilename()):
                print "DTV: movie file '%s' is missing, skipping to next" % \
                        anItem.getVideoFilename()
                anItem = self.currentPlaylist.getNext()
                if anItem is None:
                    self.stop()
                    return

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
        frame = controller.frame
        if frame.getDisplay(frame.mainDisplay) is not videoDisplay:
            frame.selectDisplay(videoDisplay, frame.mainDisplay)
        videoDisplay.selectItem(anItem, videoRenderer)
        videoDisplay.play()

    def playItemExternally(self, itemID):
        anItem = mapToPlaylistItem(db.getObjectByID(int(itemID)))
        controller.videoInfoItem = anItem
        newDisplay = TemplateDisplay('external-playback-continue')
        frame = controller.frame
        frame.selectDisplay(newDisplay, frame.mainDisplay)
        return anItem
        
    def scheduleExternalPlayback(self, anItem):
        controller.videoDisplay.stopOnDeselect = False
        controller.videoInfoItem = anItem
        newDisplay = TemplateDisplay('external-playback')
        frame = controller.frame
        frame.selectDisplay(newDisplay, frame.mainDisplay)

    def stop(self, switchDisplay=True):
        frame = controller.frame
        videoDisplay = controller.videoDisplay
        if frame.getDisplay(frame.mainDisplay) == videoDisplay:
            videoDisplay.stop()
        self.exitPlayback(switchDisplay)

    def skip(self, direction):
        nextItem = None
        if self.currentPlaylist is not None:
            if direction == 1:
                nextItem = self.currentPlaylist.getNext()
            else:
                frame = controller.frame
                currentDisplay = frame.getDisplay(frame.mainDisplay)
                if not hasattr(currentDisplay, 'getCurrentTime') or currentDisplay.getCurrentTime() <= 2.0:
                    nextItem = self.currentPlaylist.getPrev()
                else:
                    currentDisplay.goToBeginningOfMovie()
                    return self.currentPlaylist.cur()
        if nextItem is None:
            self.stop()
        else:
            self.playItem(nextItem)
        return nextItem

    def onMovieFinished(self):
        return self.skip(1)


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
        
    def getRendererForItem(self, anItem):
        for renderer in self.renderers:
            if renderer.canPlayItem(anItem):
                return renderer
        return None

    def canPlayItem(self, anItem):
        return self.getRendererForItem(anItem) is not None
    
    def canPlayFile(self, file):
        for renderer in self.renderers:
            if renderer.canPlayFile(file):
                return True
        return False
    
    def selectItem(self, anItem, renderer):
        self.stopOnDeselect = True
        controller.videoInfoItem = anItem
        template = TemplateDisplay('video-info')
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
    
    DISPLAY_TIME_FORMAT  = "%H:%M:%S"
    DEFAULT_DISPLAY_TIME = time.strftime(DISPLAY_TIME_FORMAT, time.gmtime(0))
    
    def __init__(self):
        self.interactivelySeeking = False
    
    def canPlayItem(self, anItem):
        return self.canPlayFile (anItem.getVideoFilename())
    
    def canPlayFile(self, filename):
        return False
    
    def getDisplayTime(self):
        seconds = self.getCurrentTime()
        return time.strftime(self.DISPLAY_TIME_FORMAT, time.gmtime(seconds))

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

    ### Startup and shutdown ###

    def onStartup(self):
        try:
            print "DTV: Starting up Democracy Player"
            print "DTV: Version:  %s" % config.get(prefs.APP_VERSION)
            print "DTV: Revision: %s" % config.get(prefs.APP_REVISION)
            
            print "DTV: Loading preferences..."
            config.load()
            config.addChangeCallback(self.configDidChange)
            
            global delegate
            feed.setDelegate(delegate)
            feed.setSortFunc(sorts.item)
            autoupdate.setDelegate(delegate)
            database.setDelegate(delegate)
            dialogs.setDelegate(delegate)
            
            if not config.get(prefs.STARTUP_TASKS_DONE):
                print "DTV: Showing startup dialog..."
                delegate.performStartupTasks(self.finishStartup)
                config.set(prefs.STARTUP_TASKS_DONE, True)
                config.save()
            else:
                self.finishStartup()
        except:
            util.failedExn("while starting up")
            frontend.exit(1)

    def finishStartup(self, gatheredVideos=None):
        try:
            #Restoring
            print "DTV: Restoring database..."
            #            try:
            database.defaultDatabase.liveStorage = storedatabase.LiveStorage()
            #            except Exception:
            #                util.failedExn("While restoring database")
            print "DTV: Recomputing filters..."
            db.recomputeFilters()

            downloader.startupDownloader()

            self.setupGlobalFeed('dtv:manualFeed', initiallyAutoDownloadable=False)
            views.unwatchedItems.addAddCallback(self.onUnwatchedItemsCountChange)
            views.unwatchedItems.addRemoveCallback(self.onUnwatchedItemsCountChange)
            views.downloadingItems.addAddCallback(self.onDownloadingItemsCountChange)
            views.downloadingItems.addRemoveCallback(self.onDownloadingItemsCountChange)

            # Set up the search objects
            self.setupGlobalFeed('dtv:search')
            self.setupGlobalFeed('dtv:searchDownloads')

            # Set up tab list
            tabs.reloadStaticTabs()
            try:
                channelTabOrder = getSingletonDDBObject(views.channelTabOrder)
            except LookupError:
                print "DTV: Creating channel tab order"
                channelTabOrder = tabs.TabOrder('channel')
            try:
                playlistTabOrder = getSingletonDDBObject(views.playlistTabOrder)
            except LookupError:
                print "DTV: Creating playlist tab order"
                playlistTabOrder = tabs.TabOrder('playlist')

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
            print "DTV: Spawning auto downloader..."
            autodler.startDownloader()

            # Start the idle notifier daemon
            if config.get(prefs.LIMIT_UPSTREAM) is True:
                print "DTV: Spawning idle notifier"
                self.idlingNotifier = idlenotifier.IdleNotifier(self)
                self.idlingNotifier.start()
            else:
                self.idlingNotifier = None

            # Set up the playback controller
            self.playbackController = frontend.PlaybackController()

            # Put up the main frame
            print "DTV: Displaying main frame..."
            self.frame = frontend.MainFrame(self)

            # Set up the video display
            self.videoDisplay = frontend.VideoDisplay()
            self.videoDisplay.initRenderers()
            self.videoDisplay.playbackController = self.playbackController
            self.videoDisplay.setVolume(config.get(prefs.VOLUME_LEVEL))

            # create our selection handler

            self.selection = selection.SelectionHandler()

            self.selection.selectFirstGuide()
            if self.initial_feeds:
                views.feedTabs.resetCursor()
                f = views.feedTabs.getNext()
                if f is not None:
                    self.selection.selectTabByObject(f)


            # Reconnect items to downloaders.
            item.reconnectDownloaders()

            eventloop.addTimeout (30, autoupdate.checkForUpdates, "Check for updates")
            feed.expireItems()

            self.tabDisplay = TemplateDisplay('tablist',
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
                        print "DTV: WARNING, error while adding file %s" % v

            # Use an idle for parseCommandLineArgs because the frontend may
            # have put in idle calls to do set up video playback or similar
            # things.
            eventloop.addIdle(singleclick.parseCommandLineArgs, 
                    'parse command line')

            print "DTV: Starting event loop thread"
            eventloop.startup()            
        except:
            util.failedExn("while finishing starting up")
            frontend.exit(1)

    def setupGlobalFeed(self, url, *args, **kwargs):
        feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
        hasFeed = feedView.len() > 0
        feedView.unlink()
        if not hasFeed:
            print "DTV: Spawning global feed %s" % url
            d = feed.Feed(url, *args, **kwargs)

    def getGlobalFeed(self, url):
        feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
        return feedView[0]

    def removeGlobalFeed(self, url):
        feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
        feedView.resetCursor()
        feed = feedView.getNext()
        feedView.unlink()
        if feed is not None:
            print "DTV: Removing global feed %s" % url
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
                folder.PlaylistFolder)
        if obj.__class__ in typeCheckList:
            obj.rename()
        else:
            print "WARNING: Bad object type in renameCurrentTab() %s" % obj.__class__

    def renameCurrentChannel(self):
        self.renameCurrentTab(typeCheckList=[folder.ChannelFolder])

    def renameCurrentPlaylist(self):
        self.renameCurrentTab(typeCheckList=[playlist.SavedPlaylist,
                folder.PlaylistFolder])

    def updateCurrentFeed(self):
        for tab in self.selection.getSelectedTabs():
            if tab.isFeed():
                tab.obj.update()

    def updateAllFeeds(self):
        for f in views.feeds:
            f.update()

    def removeGuide(self, guide):
        if guide.getDefault():
            print "WARNING: attempt to remove default guide"
            return
        title = _('Remove %s') % guide.getTitle()
        description = _("Are you sure you want to remove the guide %s?") % (guide.getTitle(),)
        dialog = dialogs.ChoiceDialog(title, description, 
                dialogs.BUTTON_YES, dialogs.BUTTON_NO)
        def dialogCallback(dialog):
            if guide.idExists() and dialog.choice == dialogs.BUTTON_YES:
                guide.remove()
        dialog.run(dialogCallback)

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
                manualFeed = getSingletonDDBObject(views.manualFeed)
                for feed in feeds:
                    if feed.idExists():
                        feed.remove(moveItemsTo=manualFeed)
            elif dialog.choice == dialogs.BUTTON_DELETE_VIDEOS:
                for feed in feeds:
                    if feed.idExists():
                        feed.remove()
        dialog.run(dialogCallback)

    def downloaderShutdown(self):
        print "DTV: Closing Database..."
        database.defaultDatabase.liveStorage.close()
        print "DTV: Shutting down event loop"
        eventloop.quit()
        print "DTV: Shutting down frontend"
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
                    dialogs.BUTTON_CANCEL, dialogs.BUTTON_QUIT)
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
        print "DTV: Shutting down Downloader..."
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
            eventloop.join()        

            print "DTV: Saving preferences..."
            config.save()

            print "DTV: Removing search feed"
            TemplateActionHandler(None, None).resetSearch()
            self.removeGlobalFeed('dtv:search')

            print "DTV: Shutting down icon cache updates"
            iconCacheUpdater.shutdown()

            print "DTV: Removing static tabs..."
            views.allTabs.unlink() 
            tabs.removeStaticTabs()

            if self.idlingNotifier is not None:
                print "DTV: Shutting down IdleNotifier"
                self.idlingNotifier.join()

            print "DTV: Done shutting down."
            print "Remaining threads are:"
            for thread in threading.enumerate():
                print thread

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

    ### ----

    def setUpstreamLimit(self, setLimit):
        if setLimit:
            limit = config.get(prefs.UPSTREAM_LIMIT_IN_KBS)
            # upstream limit should be set here
        else:
            # upstream limit should be unset here
            pass

    def handleDrop(self, dropData, type, sourceData):
        try:
            destType, destID = dropData.split("-")
            if destID == 'END':
                destObj = None
            elif destID == 'START':
                if destType == 'channel':
                    tabOrder = getSingletonDDBObject(views.channelTabOrder)
                else:
                    tabOrder = getSingletonDDBObject(views.playlistTabOrder)
                for tab in tabOrder.getView():
                    destObj = tab.obj
                    break
                print "destOBJ is ", destObj
            else:
                destObj = db.getObjectByID(int(destID))
            sourceArea, sourceID = sourceData.split("-")
            sourceID = int(sourceID)
            draggedIDs = self.selection.calcSelection(sourceArea, sourceID)
        except:
            print "WARNING: error parsing drop (%r, %r, %r)" % \
                    (dropData, type, sourceData)
            traceback.print_exc()
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
            tabOrder = getSingletonDDBObject(views.playlistTabOrder)
            tabOrder.handleDNDReorder(destObj, draggedIDs)
        elif (destType in ('channel', 'channelfolder') and
                type in ('channel', 'channelfolder')):
            # Reordering the channel tabs
            tabOrder = getSingletonDDBObject(views.channelTabOrder)
            tabOrder.handleDNDReorder(destObj, draggedIDs)
        elif destType == "playlistitem" and type == "downloadeditem":
            # Reording items in a playlist
            playlist = self.selection.getSelectedTabs()[0].obj
            playlist.handleDNDReorder(destObj, draggedIDs)
        else:
            print "Can't handle drop. Dest type: %s Dest id: %s Type: %s" % \
                    (destType, destID, type)

###############################################################################
#### TemplateDisplay: a HTML-template-driven right-hand display panel      ####
###############################################################################

class TemplateDisplay(frontend.HTMLDisplay):

    def __init__(self, templateName, frameHint=None, areaHint=None, 
            baseURL=None, *args, **kargs):
        "'templateName' is the name of the inital template file. 'data' is keys for the template."

        #print "Processing %s" % templateName
        self.templateName = templateName
        (tch, self.templateHandle) = template.fillTemplate(templateName, self,
                self.getDTVPlatformName(), self.getEventCookie(),
                self.getBodyTagExtra(), *args, **kargs)
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

    def runActionURLs(self, triggers):
        newPage = False
        for url in triggers:
            if url.startswith('action:'):
                self.onURLLoad(url)
            elif url.startswith('javascript:'):
                js = url.replace('javascript:', '')
                self.execJS(js)
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
        #print "DTV: got %s" % url
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
                if url.endswith ('.html'):
                    path = url[len("file://"):]
                    return os.path.exists(path)
                else:
                    filename = urllib.unquote(url[len('file://'):])
                    eventloop.addIdle (lambda:singleclick.openFile (filename), "Open Local File from onURLLoad")
                    return False

            # If we get here, this isn't a DTV URL. We should open it
            # in an external browser.
            if (url.startswith('http://') or url.startswith('https://') or
                url.startswith('ftp://') or url.startswith('mailto:')):
                delegate.openExternalURL(url)
                return False

        except:
            details = "Handling action URL '%s'" % (url, )
            util.failedExn("while handling a request", details = details)

        return True

    @eventloop.asUrgent
    def dispatchAction(self, action, **kwargs):
        start = clock()
        for handler in self.actionHandlers:
            if hasattr(handler, action):
                getattr(handler, action)(**kwargs)
                return
        end = clock()
        if end - start > 0.5:
            print "WARNING: dispatch action %s too slow (%.3f secs)" % (action, end - start)
        print "Ignored bad action URL: action=%s" % action

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
    
    def setAutoDownloadableFeed(self, feed, automatic):
        obj = db.getObjectByID(int(feed))
        obj.setAutoDownloadable(automatic)

    def setGetEverything(self, feed, everything):
        obj = db.getObjectByID(int(feed))
        obj.setGetEverything(everything == 'True')

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

    def downloadCurrentItems(self):
        selected = controller.selection.getSelectedItems()
        downloadable = [i for i in selected if i.isDownloadable() ]
        for item in downloadable:
            item.download()

    def stopDownloadingCurrentItems(self):
        selected = controller.selection.getSelectedItems()
        downloading = [i for i in selected if i.getState() == 'downloading']
        for item in downloading:
            item.expire()

    def addToNewPlaylist(self):
        selected = controller.selection.getSelectedItems()
        childIDs = [i.getID() for i in selected if i.isDownloaded()]
        playlist.createNewPlaylist(childIDs)

    def mergeToFolder(self):
        tls = controller.selection.tabListSelection
        selectionType = tls.getType()
        childIDs = set(tls.currentSelection)
        if selectionType == 'channeltab':
            folder.createNewChannelFolder(childIDs)
        elif selectionType == 'playlisttab':
            folder.createNewPlaylistFolder(childIDs)
        else:
            print "WARNING: bad selection type %s in mergeToFolder" % \
                selectionType

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
            print ("Warning: Can't handle type %s in remove()" % objType)

    def rename(self, id):
        try:
            obj = db.getObjectByID(int(id))
        except:
            print "Warning: tried to rename object that doesn't exist with id %d" % int(feed)
            return
        if obj.__class__ in (playlist.SavedPlaylist, folder.ChannelFolder,
                folder.PlaylistFolder):
            obj.rename()
        else:
            print "WARNING: Unknown object type in remove() %s" % type(obj)

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
            print "DTV: Warning: tried to expire item that doesn't exist with id %d" % int(item)

    def keepItem(self, item):
        obj = db.getObjectByID(int(item))
        obj.save()

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
            paramString = "%s%sdescription=%s" % (paramString, glue,  xhtmltools.urlencode(description))
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

    def _getFeed(self, url):
        return views.feeds.getItemWithIndex(indexes.feedsByURL, url)

    def _getGuide(self, url):
        return views.guides.getItemWithIndex(indexes.guidesByURL, url)

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
            myFeed = self._getFeed (url)
            if myFeed is None:
                myFeed = feed.Feed(url)
    
            if selected == '1':
                controller.selection.selectTabByObject(myFeed)
        self.addURL (_("Democracy - Add Channel"), _("Enter the URL of the channel to add"), doAdd, url)

    def selectFeed(self, url):
        url = feed.normalizeFeedURL(url)
        db.confirmDBThread()
        # Find the feed
        myFeed = self._getFeed (url)
        if myFeed is None:
            print "selectFeed: no such feed: %s" % url
            return
        controller.selection.selectTabByObject(myFeed)
        
    def addGuide(self, url = None, selected = '1'):
        def doAdd(url):
            db.confirmDBThread()
            myGuide = self._getGuide (url)
            if myGuide is None:
                myGuide = guide.ChannelGuide(url)
    
            if selected == '1':
                controller.selection.selectTabByObject(myGuide)
        self.addURL (_("Democracy - Add Channel Guide"), _("Enter the URL of the channel guide to add"), doAdd, url)

    # Following for testing/debugging

    def handleDrop(self, data, type, sourcedata):
        controller.handleDrop(data, type, sourcedata)

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

    def switchTemplate(self, name, baseURL=None, *args, **kargs):
        self.templateHandle.unlinkTemplate()
        # Switch to new template. It get the same variable
        # dictionary as we have.
        # NEEDS: currently we hardcode the display area. This means
        # that these links always affect the right-hand 'content'
        # area, even if they are loaded from the left-hand 'tab'
        # area. Actually this whole invocation is pretty hacky.
        template = TemplateDisplay(name, frameHint=controller.frame,
                areaHint=controller.frame.mainDisplay, baseURL=baseURL,
                *args, **kargs)
        controller.frame.selectDisplay(template, controller.frame.mainDisplay)

    def doneWithIntro(self, id):
        guide = views.guides.getObjectByID(int(id)).setSawIntro()
        self.goToGuide(id)

    def goToGuide(self, id):
        # Only switch to the guide if the template display is already
        # selected This prevents doubling clicking on a movie from
        # openning the channel guide instead of the video
        if controller.frame.getDisplay(controller.frame.mainDisplay) is self.display:
            if id is None:
                guide = getSingletonDDBObject(views.default_guide)
            else:
                guide = views.guides.getObjectByID(int(id))

            # Does the Guide want to implement itself as a redirection to
            # a URL?
            (mode, location) = guide.getLocation()

            if mode == 'template':
                if location == 'guide':
                    baseURL = guide.getURL()
                else:
                    baseURL = None
                self.switchTemplate(location, baseURL=baseURL,
                        id=guide.getID())
            elif mode == 'url':
                controller.frame.selectURL(location, \
                                           controller.frame.mainDisplay)
            else:
                raise StandardError("DTV: Invalid guide load mode '%s'" % mode)

    def setViewFilter(self, viewName, fieldKey, functionKey, parameter, invert):
        print "Warning! setViewFilter deprecated"

    def setViewSort(self, viewName, fieldKey, functionKey, reverse="false"):
        print "Warning! setViewSort deprecated"

    def setSearchString(self, searchString):
        self.templateHandle.getTemplateVariable('updateSearchString')(unicode(searchString))

    def playViewNamed(self, viewName, firstItemId):
        # Find the database view that we're supposed to be
        # playing; take out items that aren't playable video
        # clips and put it in the format the frontend expects.
        view = self.templateHandle.getTemplateVariable(viewName)
        controller.playbackController.configure(view, firstItemId)
        controller.playbackController.enterPlayback()

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

    def handleSelect(self, area, viewName, id, shiftDown, ctrlDown):
        shift = (shiftDown == '1')
        ctrl = (ctrlDown == '1')
        view = self.templateHandle.getTemplateVariable(viewName)
        controller.selection.selectItem(area, view, int(id), shift, ctrl)

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
            if str(cur.getID()) == firstItemId:
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
            eventloop.addIdle(lambda:anItem.onViewed(), "Mark item viewed")
        return anItem

class PlaylistItemFromItem:

    def __init__(self, anItem):
        self.item = anItem

    def getTitle(self):
        return self.item.getTitle()

    def getVideoFilename(self):
        return self.item.getVideoFilename()

    def getLength(self):
        # NEEDS
        return 42.42

    def onViewed(self):
        self.item.markItemSeen()

    # Return the ID that is used by a template to indicate this item 
    def getID(self):
        return self.item.getID()

    def __getattr__(self, attr):
        return getattr(self.item, attr)

def mappableToPlaylistItem(obj):
    return (isinstance(obj, item.Item) and obj.isDownloaded())

def mapToPlaylistItem(obj):
    return PlaylistItemFromItem(obj)

class TooManySingletonsError(Exception):
    pass

def getSingletonDDBObject(view):
    view.confirmDBThread()
    viewLength = view.len()
    if viewLength == 1:
        view.resetCursor()
        return view.next()
    elif viewLength == 0:
        raise LookupError("Can't find singleton in %s" % repr(view))
    else:
        msg = "%d objects in %s" % (viewLength, len(view))
        raise TooManySingletonsError(msg)

def _defaultFeeds():
    defaultFeedURLs = [
        'http://del.icio.us/rss/representordie/system:media:video', 
        'http://www.videobomb.com/rss/posts/front',
        'http://www.mediarights.org/bm/rss.php?i=1',
        'http://www.telemusicvision.com/videos/rss.php?i=1',
        'http://www.rocketboom.com/vlog/quicktime_daily_enclosures.xml',
        'http://www.channelfrederator.com/rss',
        'http://revision3.com/diggnation/feed/small.mov',
        'http://live.watchmactv.com/wp-rss2.php',
        'http://some-pig.net/videos/rss.php?i=2',
        'http://videobomb.com/rss/posts/list',
    ]
    for url in defaultFeedURLs:
        feed.Feed(url, initiallyAutoDownloadable=False)

def _getInitialChannelGuide():
    default_guide = None
    for guideObj in views.guides:
        if default_guide is None:
            if guideObj.getDefault():
                default_guide = guideObj
        else:
            guideObj.remove()
    if default_guide is None:
        print "DTV: Spawning Channel Guide..."
        default_guide = guide.ChannelGuide()
        initialFeeds = resource.path("initial-feeds.democracy")
        if os.path.exists(initialFeeds):
            singleclick.openFile (initialFeeds)
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
            print "migrating", download.getFilename()
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
    getSingletonDDBObject(views.directoryFeed).update()
