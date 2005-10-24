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

def main():
    Controller().Run()

###############################################################################
#### Provides cross platform part of Video Display                         ####
#### This must be defined before we import the frontend                    ####
###############################################################################
class VideoDisplayDB:
    
    def __init__(self):
        self.initialView = None
        self.filteredView = None
        self.view = None
    
    def setPlaylist(self, playlist, firstItemId):
        self.initialView = playlist
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

    def playPause(self):
        raise NotImplementedErr

    def stop(self):
        raise NotImplementedErr

    def skipTo(self, item):
        if item is not None:
            item.onViewed()
        return item

    def cur(self):
        return self.skipTo(self.view.cur())

    def getNext(self):
        return self.skipTo(self.view.getNext())
        
    def getPrev(self):
        return self.skipTo(self.view.getPrev())


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


# We can now safely import the frontend module
import frontend

###############################################################################
#### The main application controller object, binding model to view         ####
###############################################################################

class Controller (frontend.Application):

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
                print "Spawning Channel Guide..."
                channelGuide = guide.ChannelGuide()
                feed.Feed('http://www.mediarights.org/bm/rss.php?i=1')
                feed.Feed('http://live.watchmactv.com/wp-rss2.php')
                feed.Feed('http://www.rocketboom.com/vlog/quicktime_daily_enclosures.xml')
                feed.Feed('http://some-pig.net/videos/rss.php?i=2')
                feed.Feed('http://64.207.132.106/tmv/rss.php?i=2')
                feed.Feed('http://revision3.com/diggnation/feed/small.mov')

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
            dirFeed = globalViewList['feeds'].filterWithIndex(globalIndexList['feedsByURL'],'dtv:directoryfeed')
            hasDirFeed = dirFeed.len() > 0
            globalViewList['feeds'].removeView(dirFeed)

            if not hasDirFeed:
                print "DTV: Spawning file system videos feed"
                d = feed.Feed('dtv:directoryfeed')

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

            # Put up the main frame
            print "DTV: Displaying main frame..."
            self.frame = frontend.MainFrame(self)

            scheduler.ScheduleEvent(300,db.save)

            autoupdate.checkForUpdates()
            scheduler.ScheduleEvent(86400,autoupdate.checkForUpdates)

            # Set up tab list (on left); this will automatically set up the
            # display area (on right) and currentSelectedTab
            self.tabDisplay = TemplateDisplay('tablist', tabPaneData, self)
            self.frame.selectDisplay(self.tabDisplay, self.frame.channelsDisplay)
            self.tabs.addRemoveCallback(lambda oldObject, oldIndex: self.checkSelectedTab())
            self.checkSelectedTab()

            # Set up the video display
            self.videoDisplay = frontend.VideoDisplay()

            # If we have newly available items, provide feedback
            self.updateAvailableItemsCountFeedback()

            # NEEDS: our strategy above with addRemoveCallback doesn't
            # work. I'm not sure why, but it seems to have to do with the
            # reentrant call back into the database when checkSelectedTab ends 
            # up calling endChange to force a tab to get rerendered.

        except:
            print "DTV: Exception on startup:"
            traceback.print_exc()
            frontend.exit(1)

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

    def onShutdown(self):
        try:
            print "DTV: Saving preferences..."
            config.save()

            print "DTV: Stopping scheduler"
            scheduler.ScheduleEvent.scheduler.shutdown()

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
            print "DTV: Exception on shutdown:"
            traceback.print_exc()
            frontend.exit(1)

    ### Handling config/prefs changes
    
    def configDidChange(self, key, value):
        if key is config.LIMIT_UPSTREAM.key:
            if value is False:
                self.idlingNotifier.join()
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
            if newSelected:
                newSelected.start(self.frame, templateNameHint)
            else:
                # If we're in the middle of a shutdown, selectDisplay
                # might not be there... I'm not sure why...
                if hasattr(self,'selectDisplay'):
                    self.selectDisplay(NullDisplay())

            # Note: Commenting this out since onDeselect() is called
            #       by Tab.start() --NN 08/22/05

            #if not oldSelected is None:
            #    oldSelected.onDeselect()

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

        #print "Processing %s" % templateName
        self.controller = controller
        self.templateName = templateName
        self.templateData = data
        (html, self.templateHandle) = template.fillTemplate(templateName, data, self)

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

            thread = threading.Thread(target=self.templateHandle.initialFillIn)
            thread.setDaemon(False)
            thread.start()

    def runActionURLs(self, triggers):
        newPage = False
        for url in triggers:
            if url.startswith('action:'):
                #print "loading %s" % url
                self.onURLLoad(url)
            elif url.startswith('template:'):
                newPage = True
                break
        return newPage
        
    def onURLLoad(self, url):
        print "DTV: got %s" % url
        try:
            # Special-case non-'action:'-format URL
            match = re.compile(r"^template:(.*)$").match(url)
            if match:
                self.dispatchAction('switchTemplate', name = match.group(1))
                return False

            # Standard 'action:' URL
            match = re.compile(r"^action:([^?]+)\?(.*)$").match(url)
            if match:
                action = match.group(1)
                argString = match.group(2)
                argLists = cgi.parse_qs(argString, keep_blank_values=True)

                # argLists is a dictionary from parameter names to a list
                # of values given for that parameter. Take just one value
                # for each parameter, raising an error if more than one
                # was given.
                args = {}
                for key in argLists.keys():
                    value = argLists[key]
                    if len(value) != 1:
                        raise template.TemplateError, "Multiple values of '%s' argument passend to '%s' action" % (key, action)
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
            print "Exception in URL action handler (for URL '%s'):" % url
            traceback.print_exc()
            frontend.exit(1)

        return True

    def dispatchAction(self, action, **kwargs):
        for handler in self.actionHandlers:
            if hasattr(handler, action):
                getattr(handler, action)(**kwargs)
                return True

        return False

    def onDeselect(self):
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

    def changeFeedSettings(self, feed, maxnew, fallbehind, automatic, expireDays, expireHours, expire, getEverything="0"):
        obj = db.getObjectByID(int(feed))
        obj.saveSettings(automatic,maxnew,fallbehind,expire,expireDays,expireHours,getEverything)

    def startDownload(self, item):
        obj = db.getObjectByID(int(item))
        obj.download()

    def removeFeed(self, feed):
        obj = db.getObjectByID(int(feed))
        if self.backEndDelegate.validateFeedRemoval(obj.getTitle()):
            obj.remove()

    def updateFeed(self, feed):
        obj = db.getObjectByID(int(feed))
        thread = threading.Thread(target=obj.update)
        thread.setDaemon(False)
        thread.start()

    def markFeedViewed(self, feed):
        obj = db.getObjectByID(int(feed))
        obj.markAsViewed()

    def expireItem(self, item):
        obj = db.getObjectByID(int(item))
        obj.expire()

    def keepItem(self,item):
        obj = db.getObjectByID(int(item))
        obj.setKeep(True)

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

    # Following for testing/debugging

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
        videoDisplay = self.controller.videoDisplay
        videoDisplay.configure(view, firstItemId, self.display)
        self.controller.frame.selectDisplay(videoDisplay, self.controller.frame.mainDisplay)
        videoDisplay.playPause()


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

        # Free up the template currently being displayed
        # NOTE: This is kind of a hacky way to do this, but it works --NN
        try:
            frame.mainDisplay.hostedDisplay.onDeselect()
        except:
            pass

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

    def onDeselect(self):
        self.display.onDeselect()

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
                return Tab(obj.tabTemplateBase, data, obj.contentsTemplate, data, [obj.order], obj, controller)
            elif isinstance(obj, feed.Feed):
                data['feed'] = obj
                # Change this to sort feeds on a different value
                sortKey = obj.getTitle()
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
#### Video clips                                                           ####
###############################################################################

def mappableToPlaylistItem(obj):
    if not isinstance(obj, item.Item):
        return False

    return (obj.getState() == "finished" or obj.getState() == "uploading" or
            obj.getState() == "watched" or obj.getState() == "saved")

class PlaylistItemFromItem (frontend.PlaylistItem):

    def __init__(self, item):
        self.item = item

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

globalIndexList = {
    'itemsByFeed': lambda x:str(x.getFeed().getID()),
    'feedsByURL': lambda x:str(x.getURL()),
    'class': lambda x:x.__class__
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

