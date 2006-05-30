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
import tabs

import folder
import autodler
import resource
import template
import singleclick
import storedatabase
import downloader
import download_utils
import autoupdate
import xhtmltools
import guide
import idlenotifier 
import eventloop
import dialogs

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
from gettext import gettext as _

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
            self.currentPlaylist.reset()
            self.currentPlaylist = None
    
    def enterPlayback(self):
        if self.currentPlaylist is not None:
            startItem = self.currentPlaylist.cur()
            if startItem is not None:
                self.playItem(startItem)
        
    def exitPlayback(self, switchDisplay=True):
        self.reset()
        if switchDisplay:
            controller.displayCurrentTabContent()
    
    def playPause(self):
        videoDisplay = controller.videoDisplay
        frame = controller.frame
        if frame.getDisplay(frame.mainDisplay) == videoDisplay:
            videoDisplay.playPause()
        else:
            self.enterPlayback()

    def playItem(self, anItem):
        try:
            anItem = self.skipIfItemFileIsMissing(anItem)
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

    def skipIfItemFileIsMissing(self, anItem):
        path = anItem.getPath()
        if not os.path.exists(path):
            print "DTV: movie file '%s' is missing, skipping to next" % path
            return self.skip(1)
        else:
            return anItem

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
        delegate = self.getBackendDelegate()

    ### Startup and shutdown ###

    def onStartup(self):
        try:
            print "DTV: Loading preferences..."
            config.load()
            config.addChangeCallback(self.configDidChange)
            
            delegate = self.getBackendDelegate()
            feed.setDelegate(delegate)
            feed.setSortFunc(sorts.item)
            download_utils.setDelegate(delegate)
            autoupdate.setDelegate(delegate)
            database.setDelegate(delegate)
            dialogs.setDelegate(delegate)

            #Restoring
            print "DTV: Restoring database..."
            try:
                storedatabase.restoreDatabase()
            except Exception:
                util.failedExn("While restoring database")
            print "DTV: Recomputing filters..."
            db.recomputeFilters()
            downloader.startupDownloader()

            channelGuide = getInitialChanelGuide()
            self.setupGlobalFeed('dtv:manualFeed', initiallyAutoDownloadable=False)
            views.availableItems.addAddCallback(self.onAvailableItemsCountChange)
            views.availableItems.addRemoveCallback(self.onAvailableItemsCountChange)
            views.downloadingItems.addAddCallback(self.onDownloadingItemsCountChange)
            views.downloadingItems.addRemoveCallback(self.onDownloadingItemsCountChange)

            # Set up the search objects
            self.setupGlobalFeed('dtv:search')
            self.setupGlobalFeed('dtv:searchDownloads')

            # Set up tab list
            tabs.reloadStaticTabs()

            # If we don't have any tabs by now, something is wrong
            # Our tab selection logic assumes we have at least one tab
            # and will freak out if there aren't any
            assert(len(views.allTabs) > 0)

            self.currentSelectedTab = None
            self.tabListActive = True

            # Keep a ref of the 'new' and 'download' tabs, we'll need'em later
            self.newTab = None
            self.downloadTab = None
            for tab in views.allTabs:
                if tab.tabTemplateBase == 'newtab':
                    self.newTab = tab
                elif tab.tabTemplateBase == 'downloadtab':
                    self.downloadTab = tab

            views.allTabs.resetCursor()
            views.allTabs.getNext()

            # If we're missing the file system videos feed, create it
            self.setupGlobalFeed('dtv:directoryfeed')

            # Start the automatic downloader daemon
            print "DTV: Spawning auto downloader..."
            autodler.AutoDownloader()

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

            eventloop.addTimeout (300, storedatabase.saveDatabaseIdle, "Database Save")
            eventloop.addTimeout (30, autoupdate.checkForUpdates, "Check for updates")

            # Set up tab list (on left); this will automatically set up the
            # display area (on right) and currentSelectedTab
            self.tabDisplay = TemplateDisplay('tablist')
            self.frame.selectDisplay(self.tabDisplay, self.frame.channelsDisplay)
            views.allTabs.addRemoveCallback(lambda oldObject, oldIndex: self.checkSelectedTab())

            self.checkSelectedTab()

            # If we have newly available items, provide feedback
            self.updateAvailableItemsCountFeedback()

            # NEEDS: our strategy above with addRemoveCallback doesn't
            # work. I'm not sure why, but it seems to have to do with the
            # reentrant call back into the database when checkSelectedTab ends 
            # up calling endChange to force a tab to get rerendered.

            singleclick.parseCommandLineArgs()

            print "DTV: Starting event loop thread"
            eventloop.startup()

            # Uncomment the following to test the ChoiceDialog
            #d = dialogs.ChoiceDialog("HI", "long hi", dialogs.BUTTON_YES,
                                     #dialogs.BUTTON_NO)
            #def callback(dialog):
                #if dialog.choice is None:
                    #print "CLOSED"
                #elif dialog.choice == dialogs.BUTTON_NO:
                    #print "NO"
                #elif dialog.choice == dialogs.BUTTON_YES:
                    #print "YES"
                #else:
                    #print "OOPSS: ", dialog.__dict__
            #d.run(callback)

        except:
            util.failedExn("while starting up")
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
        feedView.resetCursor()
        feed = feedView.getNext()
        feedView.unlink()
        return feed

    def removeGlobalFeed(self, url):
        feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
        feedView.resetCursor()
        feed = feedView.getNext()
        feedView.unlink()
        if feed is not None:
            print "DTV: Removing global feed %s" % url
            feed.remove()

    # Change the currently selected tab to the one remaining when
    # filtered by index and id. Returns the currently selected tab.
    def checkTabUsingIndex(self, index, id):
        # view should contain only one tab object
        view = views.allTabs.filterWithIndex(index, id)
        view.beginUpdate()
        try:
            view.resetCursor()
            obj = view.getNext()

        #FIXME: This is a hack.
        # It takes the cursor into view and makes a cursor into self.tabs
        #
        # view.objects[view.cursor][0] is the object in view before it was
        # mapped into a tab
        # 
        # objectLocs is an internal dictionary of object IDs to cursors
        #
        # We need to change the database API to allow this to happen
        # cleanly and give sane error messages (See #1053 and #1155)
            views.allTabs.cursor = views.allTabs.objectLocs[view.objects[view.cursor][0].getID()]
        finally:
            view.endUpdate()
            view.unlink()
        return obj

    # Select a tab given a tab id (as opposed to an object id)
    # Returns the selected tab
    def checkTabByID(self, id):
        return self.checkTabUsingIndex(indexes.tabIDIndex, id)

    # Select a tab given an object id (as opposed to an object id)
    # Returns the selected tab
    def checkTabByObjID(self, id):
        return self.checkTabUsingIndex(indexes.tabObjIDIndex, id)

    def allowShutdown(self):
        allow = True
        downloadsCount = views.downloadingItems.len()
        if downloadsCount > 0:
            allow = self.getBackendDelegate().interruptDownloadsAtShutdown(downloadsCount)
        return allow

    def downloaderShutdown(self):
        frontend.quit()

    @eventloop.asUrgent
    def quit(self):
        err = storedatabase.saveDatabase()
        if err is None:
            print "DTV: Shutting down Downloader..."
            downloader.shutdownDownloader(self.downloaderShutdown)
        else:
            def callback(dialog):
                if dialog.choice == dialogs.BUTTON_QUIT:
                    print "DTV: Shutting down Downloader..."
                    downloader.shutdownDownloader(self.downloaderShutdown)

            try:
                errno = err.errno
            except:
                errno = 0
            try:
                if err.filename:
                    err = "%s: %s" % (err.filename, err.strerror)
                else:
                    err = err.strerror
            except:
                pass

            title = _("%s database save failed") % (config.get(prefs.SHORT_APP_NAME), )
            ENOSPC = 28
            if errno == ENOSPC:
                description = _("%s was unable to save its database: %s.\nWe suggest deleting files from the full disk or simply deleting some movies from your collection.\nRecent changes may be lost.\nQuit Anyway?") % (config.get(prefs.LONG_APP_NAME), err)
            else:
                description = _("%s was unable to save its database: %s.\nRecent changes may be lost.\nQuit Anyway?") \
                              % (config.get(prefs.LONG_APP_NAME), err)
            dialog = dialogs.ChoiceDialog(title, description, dialogs.BUTTON_QUIT, dialogs.BUTTON_CANCEL)
            dialog.run (callback)

    def onShutdown(self):
        try:
            print "DTV: Shutting down event loop"
            eventloop.quit()
            eventloop.join()
            
            print "DTV: Saving preferences..."
            config.save()

            print "DTV: Removing search feed"
            TemplateActionHandler(None, None).resetSearch()
            self.removeGlobalFeed('dtv:search')

            print "DTV: Shutting down icon cache updates"
            iconCacheUpdater.shutdown()

            print "DTV: Removing static tabs..."
            tabs.removeStaticTabs()
            # for item in db:
            #    print str(item.__class__.__name__) + " of id "+str(item.getID())
            print "DTV: Saving database..."
            storedatabase.saveDatabase()

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
    def addAndSelectFeed(self, url, showTemplate = None):
        return GUIActionHandler().addFeed(url, showTemplate)

    ### Handling 'DTVAPI' events from the channel guide ###

    def addFeed(self, url):
        return GUIActionHandler().addFeed(url, selected = None)

    def selectFeed(self, url):
        return GUIActionHandler().selectFeed(url)

    ### Keeping track of the selected tab and showing the right template ###

    def getTabState(self, tabId):
        # Determine if this tab is selected
        isSelected = False
        if self.currentSelectedTab:
            isSelected = (self.currentSelectedTab.id == tabId)

        # Compute status string
        if isSelected:
            if self.tabListActive:
                return 'selected'
            else:
                return 'selected-inactive'
        else:
            return 'normal'

    def checkSelectedTab(self, templateNameHint = None):
        # NEEDS: locking ...
        # NEEDS: ensure is reentrant (as in two threads calling it simultaneously by accident)

        # We'd like to track the currently selected tab entirely with
        # the cursor on self.tabs. Alas, it is not to be -- when
        # getTabState is called from the database code in response to
        # a change to a tab object (say), the cursor has been
        # temporarily moved by the database code. Long-term, we should
        # make the database code not do this. But short-term, we track
        # the the currently selected tab separately too, synchronizing
        # it to the cursor here. This isn't really wasted effort,
        # because this variable is also the mechanism by which we
        # check to see if the cursor has moved since the last call to
        # checkSelectedTab.
        #
        # Why use the cursor at all? It's necessary because we want
        # the database code to handle moving the cursor on a deleted
        # record automatically for us.

        oldSelected = self.currentSelectedTab
        newSelected = views.allTabs.cur()
        self.currentSelectedTab = newSelected

        tabChanged = ((oldSelected == None) != (newSelected == None)) or (oldSelected and newSelected and oldSelected.id != newSelected.id)
        if tabChanged: # Tab selection has changed! Deal.
            # Redraw the old and new tabs
            if oldSelected:
                oldSelected.redraw()
            if newSelected:
                newSelected.redraw()
            # Boot up the new tab's template.
            self.displayCurrentTabContent(templateNameHint)

    def displayCurrentTabContent(self, templateNameHint = None):
        if self.currentSelectedTab is not None:
            self.currentSelectedTab.start(self.frame, templateNameHint)
        else:
            # If we're in the middle of a shutdown, selectDisplay
            # might not be there... I'm not sure why...
            if hasattr(self,'selectDisplay'):
                self.selectDisplay(NullDisplay())

    def setTabListActive(self, active):
        """If active is true, show the tab list normally. If active is
        false, show the tab list a different way to indicate that it
        doesn't pertain directly to what is going on (for example, a
        video is playing) but that it can still be clicked on."""
        self.tabListActive = active
        if views.allTabs.cur():
            views.allTabs.cur().redraw()

    def selectTab(self, id):
        try:
            cur = self.checkTabByID(id)
        except: # That tab doesn't exist anymore! Give up.
            print "Tab %s doesn't exist! Cannot select it." % str(id)
            return

        oldSelected = self.currentSelectedTab
        newSelected = cur

        # Handle reselection action (checkSelectedTab won't; it doesn't
        # see a difference)
        if oldSelected and oldSelected.id == newSelected.id:
            newSelected.start(self.frame, None)

        # Handle case where a different tab was clicked
        self.checkSelectedTab()

    def selectTabByTemplateBase(self, templatebase):
        views.allTabs.beginRead()
        try:
            views.allTabs.resetCursor()
            while 1:
                obj = views.allTabs.getNext()
                if obj is None:
                    print ("WARNING, couldn't find tab with template base %s"
                            % templatebase)
                    return
                elif obj.tabTemplateBase == templatebase:
                    self.selectTab(obj.id)
                    return
        finally:
            views.allTabs.endRead()


    ### Keep track of currently available+downloading items and refresh the
    ### corresponding tabs accordingly.

    def onAvailableItemsCountChange(self, obj, id):
        assert self.newTab is not None
        self.newTab.redraw()
        self.updateAvailableItemsCountFeedback()

    def onDownloadingItemsCountChange(self, obj, id):
        assert self.downloadTab is not None
        self.downloadTab.redraw()

    def updateAvailableItemsCountFeedback(self):
        count = views.availableItems.len()
        self.getBackendDelegate().updateAvailableItemsCountFeedback(count)

    ### ----

    def onDisplaySwitch(self, newDisplay):
        # Nick, your turn ;)
        pass
        
    def setUpstreamLimit(self, setLimit):
        if setLimit:
            limit = config.get(prefs.UPSTREAM_LIMIT_IN_KBS)
            # upstream limit should be set here
        else:
            # upstream limit should be unset here
            pass

    def getBackendDelegate(self):
        print "WARNING: using deprecated getBackendDelegate(). Use app.delegate instead"
        return frontend.Application.getBackendDelegate(self)

###############################################################################
#### TemplateDisplay: a HTML-template-driven right-hand display panel      ####
###############################################################################

class TemplateDisplay(frontend.HTMLDisplay):

    def __init__(self, templateName, frameHint=None, areaHint=None, baseURL=None):
        "'templateName' is the name of the inital template file. 'data' is keys for the template."

        #print "Processing %s" % templateName
        self.templateName = templateName
        (tch, self.templateHandle) = template.fillTemplate(templateName, self, self.getDTVPlatformName(), self.getEventCookie())
        html = tch.getOutput()

        self.actionHandlers = [
            ModelActionHandler(controller.getBackendDelegate()),
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

    # Returns true if the browser should handle the URL.
    def onURLLoad(self, url):
        #print "DTV: got %s" % url
        try:
            # Special-case non-'action:'-format URL
            if url.startswith ("template:"):
                self.dispatchAction ('switchTemplate', name = url[len("template:"):])
                return False

            # Standard 'action:' URL
            if url.startswith ("action:"):
                match = re.compile(r"^action:([^?]+)(\?(.*))?$").match(url)
                if match:
                    action = match.group(1)
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
                        if type(key) == unicode:
                            key = key.encode('utf8')
                        args[key] = value[0]
    
                    self.dispatchAction(action, **args)
                    return False

            # Let channel guide URLs pass through
            if url.startswith(config.get(prefs.CHANNEL_GUIDE_URL)):
                return True
            if url.startswith('file://'):
                if url.endswith ('.html'):
                    return True
                else:
                    filename = urllib.unquote(url[len('file://'):])
                    eventloop.addIdle (lambda:singleclick.openFile (filename), "Open Local File from onURLLoad")
                    return False

            # If we get here, this isn't a DTV URL. We should open it
            # in an external browser.
            if (url.startswith('http://') or url.startswith('https://') or
                url.startswith('ftp://') or url.startswith('mailto:')):
                controller.getBackendDelegate().openExternalURL(url)
                return False

        except:
            details = "Handling action URL '%s'" % (url, )
            util.failedExn("while handling a request", details = details)

        return True

    @eventloop.asUrgent
    def dispatchAction(self, action, **kwargs):
        for handler in self.actionHandlers:
            if hasattr(handler, action):
                getattr(handler, action)(**kwargs)
                return
        print "Ignored bad action URL: action=%s" % action

    @eventloop.asUrgent
    def onDeselected(self, frame):
        unloadTriggers = self.templateHandle.getTriggerActionURLsOnUnload()
        self.runActionURLs(unloadTriggers)
        self.templateHandle.unlinkTemplate()
        frontend.HTMLDisplay.onDeselected(self, frame)

    def getWatchable(self):
        view = None
        for name in ('watchable-items', 'unwatched-items', 'expiring-items', 'saved-items'):
            try:
                namedView = self.templateHandle.findNamedView(name)
                if namedView.getView().len() > 0:
                    view = namedView
                    break
            except:
                pass
        if view is None:
            return None
        
        return view.getView()


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

    def startDownload(self, item):
        obj = db.getObjectByID(int(item))
        obj.download()

    def removeCurrentFeed(self):
        currentFeed = controller.currentSelectedTab.feedID()
        if currentFeed:
            self.removeFeed(currentFeed)

    def removeFeed(self, feedID):
        obj = db.getObjectByID(int(feedID))
        title = 'Remove Channel'
        description = """Are you sure you want to remove the channel \'%s\'? This operation cannot be undone.""" % obj.getTitle()
        dialog = dialogs.ChoiceDialog(title, description, dialogs.BUTTON_YES,
                dialogs.BUTTON_NO)
        def dialogCallback(dialog):
            if dialog.choice == dialogs.BUTTON_YES:
                obj.remove()
        dialog.run(dialogCallback)

    def updateCurrentFeed(self):
        currentFeed = controller.currentSelectedTab.feedID()
        if currentFeed:
            self.updateFeed(currentFeed)

    def updateFeed(self, feed):
        obj = db.getObjectByID(int(feed))
        obj.update()

    def updateAllFeeds(self):
        # We might want to limit the number of simultaneous threads but for
        # now, this naive and simple implementation will do the trick.
        for f in views.feeds:
            f.update()

    def copyCurrentFeedURL(self):
        currentFeed = controller.currentSelectedTab.feedID()
        if currentFeed:
            self.copyFeedURL(currentFeed)

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
        obj = db.getObjectByID(int(item))
        obj.expire()

    def keepItem(self, item):
        obj = db.getObjectByID(int(item))
        obj.setKeep(True)

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

    def setMinDiskSpace(self, value):
        value = int(value)
        config.set(prefs.PRESERVE_X_GB_FREE,value)

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
        thumb_url = obj.getThumbnail()
        if (not thumb_url.startswith('resource:')):
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

    def selectTab(self, id, templateNameHint = None):
        controller.selectTab(id)

    # NEEDS: name should change to addAndSelectFeed; then we should create
    # a non-GUI addFeed to match removeFeed. (requires template updates)
    def openFile(self, path):
        singleclick.openFile(path)

    def addFeed(self, url, showTemplate = None, selected = '1'):
        url = feed.normalizeFeedURL(url)
        db.beginUpdate()
        try:
            feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
            exists = feedView.len() > 0

            if not exists:
                myFeed = feed.Feed(url)
            else:
                feedView.resetCursor()
                myFeed = feedView.getNext()
                # At this point, the addition is guaranteed to be reflected
                # in the tab list.

            feedView.unlink()

            if selected == '1':
                controller.checkTabByObjID(myFeed.getID())
                controller.checkSelectedTab(showTemplate)

        finally:
            db.endUpdate()

    # NEEDS: factor out common code with addFeed
    def selectFeed(self, url):
        url = feed.normalizeFeedURL(url)
        db.beginUpdate()
        try:
            # Find the feed
            feedView = views.feeds.filterWithIndex(indexes.feedsByURL, url)
            exists = feedView.len() > 0
            if not exists:
                print "selectFeed: no such feed: %s" % url
                return
            feedView.resetCursor()
            myFeed = feedView.getNext()
            feedView.unlink()

            # Select it
            controller.checkTabByObjID(myFeed.getID())
            controller.checkSelectedTab()

        finally:
            db.endUpdate()

    # Following for testing/debugging

    def showHelp(self):
        # FIXME don't hardcode this URL
        controller.getBackendDelegate().openExternalURL('http://www.getdemocracy.com/help')

    def testGetHTTPAuth(self, **args):
        printResultThread("testGetHTTPAuth: got %s", lambda: controller.getBackendDelegate().getHTTPAuth(**args)).start()

    def testIsScrapeAllowed(self, url):
        printResultThread("testIsScrapeAllowed: got %s", lambda: controller.getBackendDelegate().isScrapeAllowed(url)).start()

# Functions that are safe to call from action: URLs that change state
# specific to a particular instantiation of a template, and so have to
# be scoped to a particular HTML display widget.
class TemplateActionHandler:
    
    def __init__(self, display, templateHandle):
        self.display = display
        self.templateHandle = templateHandle

    def switchTemplate(self, name, baseURL=None):
        # Graphically indicate that we're not at the home
        # template anymore
        controller.setTabListActive(False)

        self.templateHandle.unlinkTemplate()
        # Switch to new template. It get the same variable
        # dictionary as we have.
        # NEEDS: currently we hardcode the display area. This means
        # that these links always affect the right-hand 'content'
        # area, even if they are loaded from the left-hand 'tab'
        # area. Actually this whole invocation is pretty hacky.
        template = TemplateDisplay(name, frameHint=controller.frame, areaHint=controller.frame.mainDisplay, baseURL=baseURL)
        controller.frame.selectDisplay(template, controller.frame.mainDisplay)

    def doneWithIntro(self):
        getSingletonDDBObject(views.guide).setSawIntro()
        self.goToGuide()

    def goToGuide(self):
        guide = getSingletonDDBObject(views.guide)
        # Does the Guide want to implement itself as a redirection to
        # a URL?
        (mode, location) = guide.getLocation()

        if mode == 'template':
            self.switchTemplate(location, baseURL=config.get(prefs.CHANNEL_GUIDE_URL))
        elif mode == 'url':
            controller.frame.selectURL(location, \
                                            controller.frame.mainDisplay)
        else:
            assert False, "Invalid guide load mode '%s'" % mode

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
        self.view.beginRead()
        try:
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
        finally:
            self.view.endRead()

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

class PlaylistItemFromItem (frontend.PlaylistItem):

    def __init__(self, anItem):
        self.item = anItem

    def getTitle(self):
        return self.item.getTitle()

    def getPath(self):
        return self.item.getFilename()

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
    if not isinstance(obj, item.Item):
        return False

    return (obj.getState() == "finished" or obj.getState() == "uploading" or

            obj.getState() == "watched" or obj.getState() == "saved")

def mapToPlaylistItem(obj):
    return PlaylistItemFromItem(obj)

class TooManySingletonsError(Exception):
    pass

def getSingletonDDBObject(view):
    view.beginRead()
    try:
        viewLength = view.len()
        if viewLength == 1:
            view.resetCursor()
            return view.next()
        elif viewLength == 0:
            raise LookupError("Can't find singleton in %s" % repr(view))
        else:
            msg = "%d objects in %s" % (viewLength, len(view))
            raise TooManySingletonsError(msg)
    finally:
        view.endRead()

def getInitialChanelGuide():
    try:
        channelGuide = getSingletonDDBObject(views.guide)
    except LookupError:
        print "DTV: Spawning Channel Guide..."
        channelGuide = guide.ChannelGuide()
        feed.Feed('http://del.icio.us/rss/representordie/system:media:video', 
                initiallyAutoDownloadable=False)
        feed.Feed('http://www.videobomb.com/rss/posts/front',
                initiallyAutoDownloadable=False)
        feed.Feed('http://www.mediarights.org/bm/rss.php?i=1',
                initiallyAutoDownloadable=False)
        feed.Feed('http://www.telemusicvision.com/videos/rss.php?i=1',
                initiallyAutoDownloadable=False)
        feed.Feed('http://www.rocketboom.com/vlog/quicktime_daily_enclosures.xml',
                initiallyAutoDownloadable=False)
        feed.Feed('http://www.channelfrederator.com/rss',
                initiallyAutoDownloadable=False)
        feed.Feed('http://revision3.com/diggnation/feed/small.mov',
                initiallyAutoDownloadable=False)
        feed.Feed('http://live.watchmactv.com/wp-rss2.php',
                initiallyAutoDownloadable=False)
        feed.Feed('http://some-pig.net/videos/rss.php?i=2',
                initiallyAutoDownloadable=False)
    except TooManySingletonsError:
        print "DTV: Multiple Channel Guides!  Using the first one"
        guideView = views.guide
        guideView.beginUpdate()
        try:
            guideView.resetCursor()
            channelGuide = guideView.getNext()
            while 1:
                thowOut = guideView.getNext()
                if thowOut is None:
                    break
                else:
                    thowOut.remove()
        finally:
            guideView.endUpdate()
    return channelGuide

# Race conditions:

# if a download finishes downloading during the same session after a
# migration, the download won't be moved to the new directory because
# the config hasn't been updated.  Even once we do pass the
# configuration changes in, there's a race condition if the download
# finishes before the new config data is passed over.  The fix for
# this is to always pass the migrate command to remotedownloader.  It
# can then handle all of that.  Since we never destroy a dlid unless
# we're deleting the item, we can always tell the downloader to
# migrate unless we don't have a dlid, in which case we can handle it.
# I don't see any race conditions in that case.

@eventloop.asUrgent
def changeMoviesDirectory(newDir, migrate):
    oldDir = config.get(prefs.MOVIES_DIRECTORY)
    config.set(prefs.MOVIES_DIRECTORY, newDir)
    if migrate:
        views.remoteDownloads.beginRead()
        try:
            for download in views.remoteDownloads:
                print "migrating", download.getFilename()
                download.migrate()
        finally:
            views.remoteDownloads.endRead()
        views.fileItems.beginRead()
        try:
            for item in views.fileItems:
                currentFilename = item.getFilename()
                if os.path.dirname(currentFilename) == oldDir:
                    item.migrate(newDir)
        finally:
             views.fileItems.endRead()
    getSingletonDDBObject(views.directoryFeed).update()
