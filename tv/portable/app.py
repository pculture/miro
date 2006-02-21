import util
import feed
import item
import config       # IMPORTANT!! config MUST be imported before downloader
import folder
import autodler
import resource
import template
import database
import scheduler
import downloader
import autoupdate
import xhtmltools
import guide
import idlenotifier

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

from xml.dom.minidom import parse, parseString

# Something needs to import this outside of Pyrex. Might as well be app
import templatehelper
import databasehelper
import fasttypes

db = database.defaultDatabase

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
        self.currentDisplay = None

    def configure(self, view, firstItemId=None):
        self.currentPlaylist = Playlist(view, firstItemId)
    
    def reset(self):
        if self.currentPlaylist is not None:
            self.currentPlaylist.reset()
            self.currentPlaylist = None
        self.currentDisplay = None
    
    def enterPlayback(self):
        if self.currentPlaylist is not None:
            startItem = self.currentPlaylist.cur()
            if startItem is not None:
                self.playItem(startItem)
        
    def exitPlayback(self, switchDisplay=True):
        self.reset()
        if switchDisplay:
            Controller.instance.displayCurrentTabContent()
    
    def playPause(self):
        videoDisplay = Controller.instance.videoDisplay
        if self.currentDisplay == videoDisplay:
            videoDisplay.playPause()
        else:
            self.enterPlayback()

    def playItem(self, anItem):
        try:
            self.skipIfItemFileIsMissing(anItem)
            videoDisplay = Controller.instance.videoDisplay
            if videoDisplay.canPlayItem(anItem):
                self.playItemInternally(videoDisplay, anItem)
            else:
                if self.currentDisplay is videoDisplay:
                    if videoDisplay.isFullScreen:
                        videoDisplay.exitFullScreen()
                    videoDisplay.stop()
                self.scheduleExternalPlayback(anItem)
        except:
            util.failedExn('when trying to play a video')
            self.stop()

    def playItemInternally(self, videoDisplay, anItem):
        if self.currentDisplay is not videoDisplay:
            self.currentDisplay = videoDisplay
            frame = Controller.instance.frame
            frame.selectDisplay(videoDisplay, frame.mainDisplay)
        videoDisplay.selectItem(anItem)
        videoDisplay.play()

    def playItemExternally(self, itemID):
        anItem = mapToPlaylistItem(db.getObjectByID(int(itemID)))
        self.currentDisplay = TemplateDisplay('external-playback-continue', anItem.getInfoMap(), Controller.instance)
        frame = Controller.instance.frame
        frame.selectDisplay(self.currentDisplay, frame.mainDisplay)
        return anItem
        
    def scheduleExternalPlayback(self, anItem):
        Controller.instance.videoDisplay.stopOnDeselect = False
        self.currentDisplay = TemplateDisplay('external-playback', anItem.getInfoMap(), Controller.instance)
        frame = Controller.instance.frame
        frame.selectDisplay(self.currentDisplay, frame.mainDisplay)

    def stop(self, switchDisplay=True):
        videoDisplay = Controller.instance.videoDisplay
        if self.currentDisplay == videoDisplay:
            videoDisplay.stop()
        self.exitPlayback(switchDisplay)

    def skip(self, direction):
        nextItem = None
        if direction == 1:
            nextItem = self.currentPlaylist.getNext()
        else:
            if not hasattr(self.currentDisplay, 'getCurrentTime') or self.currentDisplay.getCurrentTime() <= 1.0:
                nextItem = self.currentPlaylist.getPrev()
            else:
                self.currentDisplay.goToBeginningOfMovie()
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
            self.onMovieFinished()

    def onMovieFinished(self):
        if self.skip(1) is None:
            self.stop()


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
    
    def selectItem(self, anItem):
        self.stopOnDeselect = True
        
        info = anItem.getInfoMap()
        template = TemplateDisplay('video-info', info, Controller.instance, None, None, None)
        area = Controller.instance.frame.videoInfoDisplay
        Controller.instance.frame.selectDisplay(template, area)
        
        self.activeRenderer = self.getRendererForItem(anItem)
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
        return VideoRenderer.DEFAULT_DISPLAY_TIME

    def setVolume(self, level):
        self.volume = level
        config.set(config.VOLUME_LEVEL, level)
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
            Controller.instance.playbackController.stop(False)

    
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

    # This is considered public for now (ugly, sorry)
    instance = None

    def __init__(self):
        frontend.Application.__init__(self)
        assert Controller.instance is None
        Controller.instance = self

    ### Startup and shutdown ###

    def onStartup(self):
        try:
            print "DTV: Loading preferences..."
            config.load()
            config.addChangeCallback(self.configDidChange)
            
            delegate = self.getBackendDelegate()
            feed.setDelegate(delegate)
            feed.setSortFunc(itemSort)
            downloader.setDelegate(delegate)
            autoupdate.setDelegate(delegate)
            database.setDelegate(delegate)

            #Restoring
            print "DTV: Restoring database..."
            db.restore()
            print "DTV: Recomputing filters..."
            db.recomputeFilters()

            # If there's no Channel Guide in the database, create one
            # and some test feeds
            hasGuide = False
            for obj in globalViewList['guide']:
                hasGuide = True
                channelGuide = obj
            if not hasGuide:
                print "DTV: Spawning Channel Guide..."
                channelGuide = guide.ChannelGuide()
                feed.Feed('http://del.icio.us/rss/representordie/system:media:video', initiallyAutoDownloadable=False)
                feed.Feed('http://www.videobomb.com/rss/posts/front', initiallyAutoDownloadable=False)
                feed.Feed('http://www.mediarights.org/bm/rss.php?i=1', initiallyAutoDownloadable=False)
                feed.Feed('http://www.telemusicvision.com/videos/rss.php?i=1', initiallyAutoDownloadable=False)
                feed.Feed('http://www.rocketboom.com/vlog/quicktime_daily_enclosures.xml', initiallyAutoDownloadable=False)
                feed.Feed('http://www.channelfrederator.com/rss', initiallyAutoDownloadable=False)
                feed.Feed('http://revision3.com/diggnation/feed/small.mov', initiallyAutoDownloadable=False)
                feed.Feed('http://live.watchmactv.com/wp-rss2.php', initiallyAutoDownloadable=False)
                feed.Feed('http://some-pig.net/videos/rss.php?i=2', initiallyAutoDownloadable=False)

            # Define variables for templates
            # NEEDS: reorganize this, and update templates
            globalData = {
                'database': db,
                'filter': globalFilterList,
                'sort': globalSortList,
                'view': globalViewList,
                'index': globalIndexList,
                'guide': channelGuide,
                }
            tabPaneData = {
                'global': globalData,
                }

            globalData['view']['availableItems'].addAddCallback(self.onAvailableItemsCountChange)
            globalData['view']['availableItems'].addRemoveCallback(self.onAvailableItemsCountChange)
            globalData['view']['downloadingItems'].addAddCallback(self.onDownloadingItemsCountChange)
            globalData['view']['downloadingItems'].addRemoveCallback(self.onDownloadingItemsCountChange)

            # Set up the search objects
            self.setupGlobalFeed('dtv:search')
            self.setupGlobalFeed('dtv:searchDownloads')

            # Set up tab list
            reloadStaticTabs()
            mapFunc = makeMapToTabFunction(globalData, self)
            self.tabs = db.filter(mappableToTab).map(mapFunc).sort(sortTabs)

            self.tabIDIndex = lambda x: x.id
            self.tabs.createIndex(self.tabIDIndex)

            self.tabObjIDIndex = lambda x: x.obj.getID()
            self.tabs.createIndex(self.tabObjIDIndex)

            self.currentSelectedTab = None
            self.tabListActive = True
            tabPaneData['tabs'] = self.tabs

            # Keep a ref of the 'new' and 'download' tabs, we'll need'em later
            self.newTab = None
            self.downloadTab = None
            for tab in self.tabs:
                if tab.tabTemplateBase == 'newtab':
                    self.newTab = tab
                elif tab.tabTemplateBase == 'downloadtab':
                    self.downloadTab = tab

            # Put cursor on first tab to indicate that it should be initially
            # selected
            self.tabs.resetCursor()
            self.tabs.getNext()

            # If we're missing the file system videos feed, create it
            self.setupGlobalFeed('dtv:directoryfeed')

            # Start the automatic downloader daemon
            print "DTV: Spawning auto downloader..."
            autodler.AutoDownloader()

            # Start the idle notifier daemon
            if config.get(config.LIMIT_UPSTREAM) is True:
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
            self.videoDisplay.setVolume(config.get(config.VOLUME_LEVEL))

            scheduler.ScheduleEvent(300,db.save)

            scheduler.ScheduleEvent(10, autoupdate.checkForUpdates, False)
            scheduler.ScheduleEvent(86400, autoupdate.checkForUpdates)

            # Set up tab list (on left); this will automatically set up the
            # display area (on right) and currentSelectedTab
            self.tabDisplay = TemplateDisplay('tablist', tabPaneData, self)
            self.frame.selectDisplay(self.tabDisplay, self.frame.channelsDisplay)
            self.tabs.addRemoveCallback(lambda oldObject, oldIndex: self.checkSelectedTab())
            self.checkSelectedTab()

            # If we have newly available items, provide feedback
            self.updateAvailableItemsCountFeedback()

            # NEEDS: our strategy above with addRemoveCallback doesn't
            # work. I'm not sure why, but it seems to have to do with the
            # reentrant call back into the database when checkSelectedTab ends 
            # up calling endChange to force a tab to get rerendered.

        except:
            util.failedExn("while starting up")
            frontend.exit(1)

    def setupGlobalFeed(self, url):
        feedView = globalViewList['feeds'].filterWithIndex(globalIndexList['feedsByURL'], url)
        hasFeed = feedView.len() > 0
        globalViewList['feeds'].removeView(feedView)
        if not hasFeed:
            print "DTV: Spawning global feed %s" % url
            d = feed.Feed(url)

    def getGlobalFeed(self, url):
        feedView = globalViewList['feeds'].filterWithIndex(globalIndexList['feedsByURL'], url)
        feedView.resetCursor()
        feed = feedView.getNext()
        globalViewList['feeds'].removeView(feedView)
        return feed

    def removeGlobalFeed(self, url):
        feedView = globalViewList['feeds'].filterWithIndex(globalIndexList['feedsByURL'], url)
        feedView.resetCursor()
        feed = feedView.getNext()
        globalViewList['feeds'].removeView(feedView)
        if feed is not None:
            print "DTV: Removing global feed %s" % url
            feed.remove()

    def checkTabUsingIndex(self, index, id):
        view = self.tabs.filterWithIndex(index, id)
        view.beginUpdate()
        try:
            view.resetCursor()
            obj = view.getNext()
        #FIXME: This is a hack. We need to change the database API to allow this
            self.tabs.cursor = self.tabs.objectLocs[view.objects[view.cursor][0].getID()]
        finally:
            view.endUpdate()
            self.tabs.removeView(view)
        return obj

    def checkTabByID(self, id):
        return self.checkTabUsingIndex(self.tabIDIndex, id)

    def checkTabByObjID(self, id):
        return self.checkTabUsingIndex(self.tabObjIDIndex, id)

    def allowShutdown(self):
        allow = True
        downloadsCount = globalViewList['downloadingItems'].len()
        if downloadsCount > 0:
            allow = self.getBackendDelegate().interruptDownloadsAtShutdown(downloadsCount)
        return allow

    def onShutdown(self):
        try:
            print "DTV: Saving preferences..."
            config.save()

            print "DTV: Stopping scheduler"
            scheduler.ScheduleEvent.scheduler.shutdown()

            print "DTV: Removing search feed"
            TemplateActionHandler(self, None, None).resetSearch()
            self.removeGlobalFeed('dtv:search')

            print "DTV: Removing static tabs..."
            removeStaticTabs()
            # for item in db:
            #    print str(item.__class__.__name__) + " of id "+str(item.getID())
            print "DTV: Saving database..."
            db.save()

            # FIXME closing BitTorrent is slow and makes the application seem hung...
            print "DTV: Shutting down BitTorrent..."
            downloader.shutdownBTDownloader()

            print "DTV: Done shutting down."

        except:
            util.failedExn("while shutting down")
            frontend.exit(1)

    ### Handling config/prefs changes
    
    def configDidChange(self, key, value):
        if key is config.LIMIT_UPSTREAM.key:
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
        return GUIActionHandler(self).addFeed(url, showTemplate)

    def addFeedFromFile(self,file):
        feed.addFeedFromFile(file)
        return False

    ### Handling 'DTVAPI' events from the channel guide ###

    def addFeed(self, url):
        return GUIActionHandler(self).addFeed(url, selected = None)

    def selectFeed(self, url):
        return GUIActionHandler(self).selectFeed(url)

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
        newSelected = self.tabs.cur()
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
        if self.tabs.cur():
            self.tabs.cur().redraw()

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
        count = globalViewList['availableItems'].len()
        self.getBackendDelegate().updateAvailableItemsCountFeedback(count)

    ### ----

    def onDisplaySwitch(self, newDisplay):
        # Nick, your turn ;)
        pass
        
    def setUpstreamLimit(self, setLimit):
        if setLimit:
            limit = config.get(config.UPSTREAM_LIMIT_IN_KBS)
            # upstream limit should be set here
        else:
            # upstream limit should be unset here
            pass


###############################################################################
#### TemplateDisplay: a HTML-template-driven right-hand display panel      ####
###############################################################################

class TemplateDisplay(frontend.HTMLDisplay):

    def __init__(self, templateName, data, controller, existingView = None, frameHint=None, areaHint=None):
        "'templateName' is the name of the inital template file. 'data' is keys for the template."

        # Copy the event cookie for this instance (allocated by our
        # base class) into the template data
        data = copy.copy(data)
        data['eventCookie'] = self.getEventCookie()
        data['dtvPlatform'] = self.getDTVPlatformName()

        #print "Processing %s" % templateName
        self.controller = controller
        self.templateName = templateName
        self.templateData = data
        (tch, self.templateHandle) = template.fillTemplate(templateName, data, self)
        html = tch.getOutput()

        self.actionHandlers = [
            ModelActionHandler(self.controller.getBackendDelegate()),
            GUIActionHandler(self.controller),
            TemplateActionHandler(self.controller, self, self.templateHandle),
            ]

        loadTriggers = self.templateHandle.getTriggerActionURLsOnLoad()
        newPage = self.runActionURLs(loadTriggers)

        if newPage:
            self.templateHandle.unlinkTemplate()
            self.__init__(re.compile(r"^template:(.*)$").match(url).group(1),data,controller, existingView, frameHint, areaHint)
        else:
            frontend.HTMLDisplay.__init__(self, html, existingView=existingView, frameHint=frameHint, areaHint=areaHint)

            thread = threading.Thread(target=self.templateHandle.initialFillIn,\
                                      name="Initial fillin for template %s" %\
                                      templateName)
            thread.setDaemon(False)
            thread.start()

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
        
    def onURLLoad(self, url):
        #print "DTV: got %s" % url
        try:
            # Special-case non-'action:'-format URL
            match = re.compile(r"^template:(.*)$").match(url)
            if match:
                self.dispatchAction('switchTemplate', name = match.group(1))
                return False

            # Standard 'action:' URL
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

                if self.dispatchAction(action, **args):
                    return False
                else:
                    print "Ignored bad action URL: %s" % url
                    return False

            #NEEDS: handle feed:// URLs and USM subscription URLs

            # Let channel guide URLs pass through
            if url.startswith(config.get(config.CHANNEL_GUIDE_URL)):
                return True
            if url.startswith('file://'):
                return True

            # If we get here, this isn't a DTV URL. We should open it
            # in an external browser.
            if (url.startswith('http://') or url.startswith('https://') or
                url.startswith('ftp://') or url.startswith('mailto:')):
                self.controller.getBackendDelegate().openExternalURL(url)
                return False

        except:
            details = "Handling action URL '%s'" % (url, )
            util.failedExn("while handling a request", details = details)

        return True

    def dispatchAction(self, action, **kwargs):
        for handler in self.actionHandlers:
            if hasattr(handler, action):
                getattr(handler, action)(**kwargs)
                return True

        return False

    def onDeselected(self, frame):
        unloadTriggers = self.templateHandle.getTriggerActionURLsOnUnload()
        self.runActionURLs(unloadTriggers)
        self.templateHandle.unlinkTemplate()

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
        currentFeed = Controller.instance.currentSelectedTab.feedID()
        if currentFeed:
            self.removeFeed(currentFeed)

    def removeFeed(self, feed):
        obj = db.getObjectByID(int(feed))
        if self.backEndDelegate.validateFeedRemoval(obj.getTitle()):
            obj.remove()

    def updateCurrentFeed(self):
        currentFeed = Controller.instance.currentSelectedTab.feedID()
        if currentFeed:
            self.updateFeed(currentFeed)

    def updateFeed(self, feed):
        obj = db.getObjectByID(int(feed))
        thread = threading.Thread(target=obj.update, name="updateFeed")
        thread.setDaemon(False)
        thread.start()

    def updateAllFeeds(self):
        # We might want to limit the number of simultaneous threads but for
        # now, this naive and simple implementation will do the trick.
        for f in globalViewList['feeds']:
            thread = threading.Thread(target=f.update, name="updateAllFeeds")
            thread.setDaemon(False)
            thread.start()

    def copyCurrentFeedURL(self):
        currentFeed = Controller.instance.currentSelectedTab.feedID()
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
        config.set(config.CHECK_CHANNELS_EVERY_X_MN,value)

    def setLimitUpstream(self, value):
        value = (value == "1")
        config.set(config.LIMIT_UPSTREAM,value)

    def setMaxUpstream(self, value):
        value = int(value)
        config.set(config.UPSTREAM_LIMIT_IN_KBS,value)

    def setPreserveDiskSpace(self, value):
        value = (value == "1")
        config.set(config.PRESERVE_DISK_SPACE,value)

    def setMinDiskSpace(self, value):
        value = int(value)
        config.set(config.PRESERVE_X_GB_FREE,value)

    def setDefaultExpiration(self, value):
        value = int(value)
        config.set(config.EXPIRE_AFTER_X_DAYS,value)

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
        url = config.get(config.VIDEOBOMB_URL) + paramString
        self.backEndDelegate.openExternalURL(url)

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

    def __init__(self, controller):
        self.controller = controller

    def selectTab(self, id, templateNameHint = None):
        cur = self.controller.checkTabByID(id)

        # Figure out what happened
        oldSelected = self.controller.currentSelectedTab
        newSelected = cur

        # Handle reselection action (checkSelectedTab won't; it doesn't
        # see a difference)
        if oldSelected and oldSelected.id == newSelected.id:
            newSelected.start(self.controller.frame, templateNameHint)

        # Handle case where a different tab was clicked
        self.controller.checkSelectedTab(templateNameHint)

    # NEEDS: name should change to addAndSelectFeed; then we should create
    # a non-GUI addFeed to match removeFeed. (requires template updates)

    def addFeed(self, url, showTemplate = None, selected = '1'):
        url = feed.normalizeFeedURL(url)
        db.beginUpdate()
        try:
            feedView = globalViewList['feeds'].filterWithIndex(globalIndexList['feedsByURL'],url)
            exists = feedView.len() > 0

            if not exists:
                myFeed = feed.Feed(url)
            else:
                feedView.resetCursor()
                myFeed = feedView.getNext()
                # At this point, the addition is guaranteed to be reflected
                # in the tab list.

            globalViewList['feeds'].removeView(feedView)

            if selected == '1':
                self.controller.checkTabByObjID(myFeed.getID())
                self.controller.checkSelectedTab(showTemplate)

        finally:
            db.endUpdate()

    # NEEDS: factor out common code with addFeed
    def selectFeed(self, url):
        url = feed.normalizeFeedURL(url)
        db.beginUpdate()
        try:
            # Find the feed
            feedView = globalViewList['feeds'].filterWithIndex(globalIndexList['feedsByURL'],url)
            exists = feedView.len() > 0
            if not exists:
                print "selectFeed: no such feed: %s" % url
                return
            feedView.resetCursor()
            myFeed = feedView.getNext()
            globalViewList['feeds'].removeView(feedView)

            # Select it
            self.controller.checkTabByObjID(myFeed.getID())
            self.controller.checkSelectedTab()

        finally:
            db.endUpdate()

    # Following for testing/debugging

    def showHelp(self):
        # FIXME don't hardcode this URL
        self.controller.getBackendDelegate().openExternalURL('http://www.getdemocracy.com/help')

    def testGetHTTPAuth(self, **args):
        printResultThread("testGetHTTPAuth: got %s", lambda: self.controller.getBackendDelegate().getHTTPAuth(**args)).start()

    def testIsScrapeAllowed(self, url):
        printResultThread("testIsScrapeAllowed: got %s", lambda: self.controller.getBackendDelegate().isScrapeAllowed(url)).start()

# Functions that are safe to call from action: URLs that change state
# specific to a particular instantiation of a template, and so have to
# be scoped to a particular HTML display widget.
class TemplateActionHandler:
    
    def __init__(self, controller, display, templateHandle):
        self.controller = controller
        self.display = display
        self.templateHandle = templateHandle

    def switchTemplate(self, name):
        # Graphically indicate that we're not at the home
        # template anymore
        self.controller.setTabListActive(False)

        self.templateHandle.unlinkTemplate()
        # Switch to new template. It get the same variable
        # dictionary as we have.
        # NEEDS: currently we hardcode the display area. This means
        # that these links always affect the right-hand 'content'
        # area, even if they are loaded from the left-hand 'tab'
        # area. Actually this whole invocation is pretty hacky.
        self.controller.frame.selectDisplay(TemplateDisplay(name, self.display.templateData, self.controller, existingView = "sharedView", frameHint=self.controller.frame, areaHint=self.controller.frame.mainDisplay), self.controller.frame.mainDisplay)

    def doneWithIntro(self):
        # Find the guide
        guide = None
        for obj in globalViewList['guide']:
            guide = obj
        assert guide is not None

        guide.setSawIntro()
        self.goToGuide()

    def goToGuide(self):
        # Find the guide
        guide = None
        for obj in globalViewList['guide']:
            guide = obj
        assert guide is not None

        # Does the Guide want to implement itself as a redirection to
        # a URL?
        (mode, location) = guide.getLocation()

        if mode == 'template':
            self.switchTemplate(location)
        elif mode == 'url':
            self.controller.frame.selectURL(location, \
                                            self.controller.frame.mainDisplay)
        else:
            assert False, "Invalid guide load mode '%s'" % mode

    def setViewFilter(self, viewName, fieldKey, functionKey, parameter, invert):
        #print "set filter: view %s field %s func %s param %s invert %s" % (viewName, fieldKey, functionKey, parameter, invert)
        if viewName != "undefined":
            invert = stringToBoolean(invert)
            namedView = self.templateHandle.findNamedView(viewName)
            namedView.setFilter(fieldKey, functionKey, parameter, invert)

    def setViewSort(self, viewName, fieldKey, functionKey, reverse="false"):
        #print "set sort: view %s field %s func %s reverse %s" % (viewName, fieldKey, functionKey, reverse)
        reverse = stringToBoolean(reverse)
        namedView = self.templateHandle.findNamedView(viewName)
        namedView.setSort(fieldKey, functionKey, reverse)

    def playViewNamed(self, viewName, firstItemId):
        # Find the database view that we're supposed to be
        # playing; take out items that aren't playable video
        # clips and put it in the format the frontend expects.
        namedView = self.templateHandle.findNamedView(viewName)
        view = namedView.getView()
        self.playView(view, firstItemId)

    def playView(self, view, firstItemId):
        self.controller.playbackController.configure(view, firstItemId)
        self.controller.playbackController.enterPlayback()

    def playItemExternally(self, itemID):
        self.controller.playbackController.playItemExternally(itemID)
        
    def skipItem(self, itemID):
        self.controller.playbackController.skip(1)
    
    def updateLastSearchEngine(self, engine):
        searchFeed = self.controller.getGlobalFeed('dtv:search')
        assert searchFeed is not None
        searchFeed.lastEngine = engine
    
    def updateLastSearchQuery(self, query):
        searchFeed = self.controller.getGlobalFeed('dtv:search')
        assert searchFeed is not None
        searchFeed.lastQuery = query
        
    def performSearch(self, engine, query):
        searchFeed = self.controller.getGlobalFeed('dtv:search')
        assert searchFeed is not None
        searchFeed.lookup(engine, query)

    def resetSearch(self):
        searchFeed = self.controller.getGlobalFeed('dtv:search')
        assert searchFeed is not None
        searchDownloadsFeed = Controller.instance.getGlobalFeed('dtv:searchDownloads')
        assert searchDownloadsFeed is not None
        searchFeed.preserveDownloads(searchDownloadsFeed)
        searchFeed.reset()
        
    # The Windows XUL port can send a setVolume at any time, even when
    # there's no video display around. We can just ignore it
    def setVolume(self, level):
        pass

# Helper: liberally interpret the provided string as a boolean
def stringToBoolean(string):
    if string == "" or string == "0" or string == "false":
        return False
    else:
        return True

###############################################################################
#### Tabs                                                                  ####
###############################################################################

class Tab:
    idCounter = 0

    def __init__(self, tabTemplateBase, tabData, contentsTemplate, contentsData, sortKey, obj, controller):
        self.tabTemplateBase = tabTemplateBase
        self.tabData = tabData
        self.contentsTemplate = contentsTemplate
        self.contentsData = contentsData
        self.sortKey = sortKey
        self.controller = controller
        self.display = None
        self.id = "tab%d" % Tab.idCounter
        Tab.idCounter += 1
        self.obj = obj

    def start(self, frame, templateNameHint):
        self.controller.setTabListActive(True)
        self.display = TemplateDisplay(templateNameHint or self.contentsTemplate, self.contentsData, self.controller, existingView="sharedView", frameHint=frame, areaHint=frame.mainDisplay)
        frame.selectDisplay(self.display, frame.mainDisplay)

    def markup(self):
        """Get HTML giving the visual appearance of the tab. 'state' is
        one of 'selected' (tab is currently selected), 'normal' (tab is
        not selected), or 'selected-inactive' (tab is selected but
        setTabListActive was called with a false value on the MainFrame
        for which the tab is being rendered.) The HTML should be returned
        as a xml.dom.minidom element or document fragment."""
        state = self.controller.getTabState(self.id)
        file = "%s-%s" % (self.tabTemplateBase, state)
        return template.fillStaticTemplate(file, self.tabData)

    def redraw(self):
        # Force a redraw by sending a change notification on the underlying
        # DB object.
        self.obj.beginChange()
        self.obj.endChange()

    def isFeed(self):
        """True if this Tab represents a Feed."""
        return isinstance(self.obj, feed.Feed)

    def feedURL(self):
        """If this Tab represents a Feed, the feed's URL. Otherwise None."""
        if self.isFeed():
            return self.obj.getURL()
        else:
            return None

    def feedID(self):
        """If this Tab represents a Feed, the feed's ID. Otherwise None."""
        if self.isFeed():
            return self.obj.getID()
        else:
            return None

    def onDeselected(self, frame):
        self.display.onDeselect(frame)

# Database object representing a static (non-feed-associated) tab.
class StaticTab(database.DDBObject):
    def __init__(self, tabTemplateBase, contentsTemplate, order):
        self.tabTemplateBase = tabTemplateBase
        self.contentsTemplate = contentsTemplate
        self.order = order
        database.DDBObject.__init__(self)

# Remove all static tabs from the database
def removeStaticTabs():
    db.beginUpdate()
    try:
        for obj in globalViewList['staticTabs']:
            obj.remove()
    finally:
        db.endUpdate()

# Reload the StaticTabs in the database from the statictabs.xml resource file.
def reloadStaticTabs():
    db.beginUpdate()
    try:
        # Wipe all of the StaticTabs currently in the database.
        removeStaticTabs()

        # Load them anew from the resource file.
        # NEEDS: maybe better error reporting?
        document = parse(resource.path('statictabs.xml'))
        for n in document.getElementsByTagName('statictab'):
            tabTemplateBase = n.getAttribute('tabtemplatebase')
            contentsTemplate = n.getAttribute('contentstemplate')
            order = int(n.getAttribute('order'))
            StaticTab(tabTemplateBase, contentsTemplate, order)
    finally:
        db.endUpdate()

# Return True if a tab should be shown for obj in the frontend. The filter
# used on the database to get the list of tabs.
def mappableToTab(obj):
    return isinstance(obj, StaticTab) or (isinstance(obj, feed.Feed) and
                                          obj.isVisible())

# Generate a function that, given an object for which mappableToTab
# returns true, return a Tab instance -- mapping a model object into
# a UI objet that can be rendered and selected.
#
# By 'generate a function', we mean that you give makeMapToTabFunction
# the global data that you want to always be available in both the tab
# templates and the contents page template, and it returns a function
# that maps objects to tabs such that that request is satisified.
def makeMapToTabFunction(globalTemplateData, controller):
    class MapToTab:
        def __init__(self, globalTemplateData):
            self.globalTemplateData = globalTemplateData

        def mapToTab(self,obj):
            data = {'global': self.globalTemplateData};
            if isinstance(obj, StaticTab):
                if obj.contentsTemplate == 'search':
                    data['feed'] = Controller.instance.getGlobalFeed('dtv:search')
                return Tab(obj.tabTemplateBase, data, obj.contentsTemplate, data, [obj.order], obj, controller)
            elif isinstance(obj, feed.Feed):
                data['feed'] = obj
                # Change this to sort feeds on a different value
                sortKey = obj.getTitle().lower()
                return Tab('feedtab', data, 'channel', data, [100, sortKey], obj, controller)
            elif isinstance(obj, folder.Folder):
                data['folder'] = obj
                sortKey = obj.getTitle()
                return Tab('foldertab',data,'folder',data,[500,sortKey],obj,controller)
            else:
                assert(0) # NEEDS: clean up (signal internal error)

    return MapToTab(globalTemplateData).mapToTab

# The sort function used to order tabs in the tab list: just use the
# sort keys provided when mapToTab created the Tabs. These can be
# lists, which are tested left-to-right in the way you'd
# expect. Generally, the way this is used is that static tabs are
# assigned a numeric priority, and get a single-element list with that
# number as their sort key; feeds get a list with '100' in the first
# position, and a value that determines the order of the feeds in the
# second position. This way all of the feeds are together, and the
# static tabs can be positioned around them.
def sortTabs(x, y):
    if x.sortKey < y.sortKey:
        return -1
    elif x.sortKey > y.sortKey:
        return 1
    return 0


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
            anItem.onViewed()
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

    # Return a dictionary containing info to be injected in a template
    def getInfoMap(self):
        return dict(this=self.item, filter=globalFilterList)

    def __getattr__(self, attr):
        return getattr(self.item, attr)

def mappableToPlaylistItem(obj):
    if not isinstance(obj, item.Item):
        return False

    return (obj.getState() == "finished" or obj.getState() == "uploading" or
            obj.getState() == "watched" or obj.getState() == "saved")

def mapToPlaylistItem(obj):
    return PlaylistItemFromItem(obj)


###############################################################################
#### The global set of filter and sort functions accessible from templates ####
###############################################################################

def compare(x, y):
    if x < y:
        return -1
    if x > y:
        return 1
    return 0

def itemSort(x,y):
    if x.getReleaseDateObj() > y.getReleaseDateObj():
        return -1
    elif x.getReleaseDateObj() < y.getReleaseDateObj():
        return 1
    elif x.getLinkNumber() > y.getLinkNumber():
        return -1
    elif x.getLinkNumber() < y.getLinkNumber():
        return 1
    elif x.getID() > y.getID():
        return -1
    elif x.getID() < y.getID():
        return 1
    else:
        return 0

def alphabeticalSort(x,y):
    if x.getTitle() < y.getTitle():
        return -1
    elif x.getTitle() > y.getTitle():
        return 1
    elif x.getDescription() < y.getDescription():
        return -1
    elif x.getDescription() > y.getDescription():
        return 1
    else:
        return 0

def downloadStartedSort(x,y):
    if x.getTitle() < y.getTitle():
        return -1
    elif x.getTitle() > y.getTitle():
        return 1
    elif x.getDescription() < y.getDescription():
        return -1
    elif x.getDescription() > y.getDescription():
        return 1
    else:
        return 0

globalSortList = {
    'item': itemSort,
    'alphabetical': alphabeticalSort,
    'tab': sortTabs,
    'downloadStarted': downloadStartedSort,
    'text': (lambda x, y: compare(str(x), str(y))),
    'number': (lambda x, y: compare(float(x), float(y))),
}

def filterClass(obj, parameter):
    if type(obj) != types.InstanceType:
        return False

    # Pull off any package name
    name = str(obj.__class__)
    match = re.compile(r"\.([^.]*)$").search(name)
    if match:
        name = match.group(1)

    return name == parameter

def filterHasKey(obj,parameter):
    try:
        obj[parameter]
    except KeyError:
        return False
    return True

# FIXME: All of these functions have a big hack to support two
#        parameters instead of one. It's ugly. We should fix this to
#        support multiple parameters
def unviewedItems(obj, param):
    params = param.split('|',1)
    
    unviewed = (str(obj.feed.getID()) == params[0] and 
                not obj.getViewed())
    if len(params) > 1:
        unviewed= (unviewed and 
                   (str(params[1]).lower() in obj.getTitle().lower() or
                    str(params[1]).lower() in obj.getDescription().lower()))
    return unviewed

def viewedItems(obj, param):
    params = param.split('|',1)
    
    viewed = (str(obj.feed.getID()) == params[0] and 
              obj.getViewed())
    if len(params) > 1:
        viewed= (viewed and 
                 (str(params[1]).lower() in obj.getTitle().lower() or
                  str(params[1]).lower() in obj.getDescription().lower()))
    return viewed

def undownloadedItems(obj,param):
    params = param.split('|',1)
    
    undled = (str(obj.feed.getID()) == params[0] and 
              (obj.getState() == 'stopped' or
               obj.getState() == 'downloading'))
    if len(params) > 1:
        undled = (undled and 
                  (str(params[1]).lower() in obj.getTitle().lower() or
                   str(params[1]).lower() in obj.getDescription().lower()))
    return undled

def downloadingItems(obj, param):
    params = param.split('|',1)
    
    old = (str(obj.feed.getID()) == params[0] and 
           obj.getState() == 'downloading')
    if len(params) > 1:
        old = (old and 
               (str(params[1]).lower() in obj.getTitle().lower() or
                str(params[1]).lower() in obj.getDescription().lower()))
    return old

def unwatchedItems(obj, param):
    params = param.split('|',1)
    unwatched = True
    if params[0] != '':
        unwatched = (str(obj.feed.getID()) == params[0])
    if len(params) > 1:
        unwatched = (unwatched and 
                     (str(params[1]).lower() in obj.getTitle().lower() or
                      str(params[1]).lower() in obj.getDescription().lower()))
    unwatched = (unwatched and 
                 ((obj.getState() == 'finished' or
                   obj.getState() == 'uploading')))
    return unwatched

def expiringItems(obj, param):
    params = param.split('|',1)
    expiring = True
    if params[0] != '':
        expiring = (str(obj.feed.getID()) == params[0])
    if len(params) > 1:
        expiring = (expiring and 
                (str(params[1]).lower() in obj.getTitle().lower() or
                 str(params[1]).lower() in obj.getDescription().lower()))
    expiring = (expiring and (obj.getState() == 'watched'))
    return expiring

def feedItems(obj, param):
    params = param.split('|',1)
    
    dled = (str(obj.feed.getID()) == params[0])
    if len(params) > 1:
        dled = (dled and 
                (str(params[1]).lower() in obj.getTitle().lower() or
                 str(params[1]).lower() in obj.getDescription().lower()))
    return dled

def recentItems(obj, param):
    #FIXME make this look at the feed's time until expiration
    params = param.split('|',1)
    
    recent = (str(obj.feed.getID()) == params[0] and 
              ((obj.getState() == 'finished' or
                obj.getState() == 'uploading' or
                obj.getState() == 'watched')))
    if len(params) > 1:
        recent = (recent and 
                  (str(params[1]).lower() in obj.getTitle().lower() or
                   str(params[1]).lower() in obj.getDescription().lower()))
    return recent

def oldItems(obj, param):
    params = param.split('|',1)
    
    old = (str(obj.feed.getID()) == params[0] and 
           obj.getState() == 'saved')
    if len(params) > 1:
        old = (old and 
               (str(params[1]).lower() in obj.getTitle().lower() or
                str(params[1]).lower() in obj.getDescription().lower()))
    return old

def watchableItems(obj, param):
    params = param.split('|',1)

    if len(params)>1:
        search = params[1]
    else:
        search = ''

    return (((len(params[0]) == 0) or str(obj.feed.getID()) == params[0]) and 
            ((obj.getState() == 'finished' or
              obj.getState() == 'uploading' or
              obj.getState() == 'watched' or
              obj.getState() == 'saved')) and
            (search.lower() in obj.getTitle().lower() or 
             search.lower() in obj.getDescription().lower()))
    
def allRecentItems(obj, param):
    params = param.split('|',1)
    if len(params)>1:
        search = params[1]
    else:
        search = ''

    return ((obj.getState() == 'finished' or obj.getState() == 'uploading' or
            obj.getState() == 'watched') and 
            (search.lower() in obj.getTitle().lower() or 
             search.lower() in obj.getDescription().lower()))

def allDownloadingItems(obj, param):
    params = param.split('|',1)
    if len(params)>1:
        search = params[1]
    else:
        search = ''

    return (obj.getState() == 'downloading' and
            (search.lower() in obj.getTitle().lower() or 
             search.lower() in obj.getDescription().lower()))

globalFilterList = {
    'substring': (lambda x, y: str(y) in str(x)),
    'boolean': (lambda x, y: x),

    'unviewedItems': unviewedItems,
    'viewedItems': viewedItems,

    'feedItems' : feedItems,
    'recentItems': recentItems,
    'allRecentItems': allRecentItems,
    'oldItems': oldItems,
    'watchableItems': watchableItems,
    'downloadingItems': downloadingItems,
    'unwatchedItems': unwatchedItems,
    'expiringItems': expiringItems,
    'undownloadedItems':  undownloadedItems,
    'allDownloadingItems': allDownloadingItems,
    
    'class': filterClass,
    'all': (lambda x, y: True),
    'hasKey':  filterHasKey,
    'equal':(lambda x, y: str(x) == str(y)),
    'feedID': (lambda x, y: str(x.getFeedID()) == str(y))
}

globalViewList = {}  # filled in below with indexed view

# Returns the class of the object, aggregating all Item subtypes under Item
def getClassForFilter(x):
    if isinstance(x,item.Item):
        return item.Item
    else:
        return x.__class__

globalIndexList = {
    'itemsByFeed': lambda x:str(x.getFeed().getID()),
    'feedsByURL': lambda x:str(x.getURL()),
    'class': getClassForFilter
}

db.createIndex(globalIndexList['class'])
globalViewList['items'] = db.filterWithIndex(globalIndexList['class'],item.Item)
globalViewList['feeds'] = db.filterWithIndex(globalIndexList['class'],feed.Feed)
globalViewList['httpauths'] = db.filterWithIndex(globalIndexList['class'],downloader.HTTPAuthPassword)
globalViewList['staticTabs'] = db.filterWithIndex(globalIndexList['class'],StaticTab)
globalViewList['guide'] =  db.filterWithIndex(globalIndexList['class'],guide.ChannelGuide)
globalViewList['availableItems'] = globalViewList['items'].filter(lambda x:x.getState() == 'finished' or x.getState() == 'uploading')
globalViewList['downloadingItems'] = globalViewList['items'].filter(lambda x:x.getState() == 'downloading')

globalViewList['items'].createIndex(globalIndexList['itemsByFeed'])
globalViewList['feeds'].createIndex(globalIndexList['feedsByURL'])
