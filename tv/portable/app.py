import feed
import item
import config
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

db = database.defaultDatabase

def main():
    Controller().Run()

###############################################################################
#### Provides cross platform part of Video Display                         ####
#### This must be defined before we import the frontend                    ####
###############################################################################
class VideoDisplayDB:
    
    def __init__(self, firstItemId, origView):
        self.origView = origView

        #FIXME: These views need to be released
        self.subView = self.origView.filter(mappableToPlaylistItem)
        self.view = self.subView.map(mapToPlaylistItem)

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


# We can now safely import the frontend module
import frontend

###############################################################################
#### The main application controller object, binding model to view         ####
###############################################################################

class Controller (frontend.Application):

    instance = None

    def __init__(self):
        frontend.Application.__init__(self)
        assert(Controller.instance is None)
        Controller.instance = self

    ### Startup and shutdown ###

    def onStartup(self):
        try:
            print "DTV: Loading preferences..."
            config.load()
            
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
            for obj in db.objects:
                if obj[0].__class__.__name__ == 'ChannelGuide':
                    hasGuide = True
                    channelGuide = obj[0]
                    break
            if not hasGuide:
                print "Spawning Channel Guide..."
                channelGuide = guide.ChannelGuide()
                feed.UniversalFeed('http://www.mediarights.org/bm/rss.php?i=1')
                feed.UniversalFeed('http://live.watchmactv.com/wp-rss2.php')
                feed.UniversalFeed('http://www.rocketboom.com/vlog/quicktime_daily_enclosures.xml')
                feed.UniversalFeed('http://some-pig.net/videos/rss.php?i=2')
                feed.UniversalFeed('http://64.207.132.106/tmv/rss.php?i=2')
                feed.UniversalFeed('http://revision3.com/diggnation/feed/small.mov')

            # Define variables for templates
            # NEEDS: reorganize this, and update templates
            globalData = {
                'database': db,
                'filter': globalFilterList,
                'sort': globalSortList,
                'view': globalViewList,
                'guide': channelGuide,
                }
            tabPaneData = {
                'global': globalData,
                }

            # Set up tab list
            reloadStaticTabs()
            mapFunc = makeMapToTabFunction(globalData, self)
            self.tabs = db.filter(mappableToTab).map(mapFunc).sort(sortTabs)

            self.currentSelectedTab = None
            self.tabListActive = True
            tabPaneData['tabs'] = self.tabs

            # Put cursor on first tab to indicate that it should be initially
            # selected
            self.tabs.resetCursor()
            self.tabs.getNext()

            # If we're missing the file system videos feed, create it
            hasDirFeed = False
            for obj in db.objects:
                if obj[0].__class__.__name__ == 'DirectoryFeed':
                    hasDirFeed = True
                    break
            if not hasDirFeed:
                print "DTV: Spawning file system videos feed"
                d = feed.DirectoryFeed()

            # Start the automatic downloader daemon
            print "DTV: Spawning auto downloader..."
            autodler.AutoDownloader()

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

            # NEEDS: our strategy above with addRemoveCallback doesn't
            # work. I'm not sure why, but it seems to have to do with the
            # reentrant call back into the database when checkSelectedTab ends 
            # up calling endChange to force a tab to get rerendered.

        except:
            print "DTV: Exception on startup:"
            traceback.print_exc()
            sys.exit(1)

    def onShutdown(self):
        try:
            print "DTV: Saving preferences..."
            config.save()

            print "DTV: Stopping scheduler"
            scheduler.ScheduleEvent.scheduler.shutdown()

            print "DTV: Removing static tabs..."
            db.removeMatching(lambda x:str(x.__class__.__name__) == "StaticTab")
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
            sys.exit(1)

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

    def onDisplaySwitch(self, newDisplay):
        # Nick, your turn ;)
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
            ModelActionHandler(),
            GUIActionHandler(self.controller),
            TemplateActionHandler(self.controller, self, self.templateHandle),
            ]


        newPage = False
        triggers = self.templateHandle.getTriggerActionURLs()
        for url in triggers:
            if url.startswith('action:'):
                #print "loading %s" % url
                self.onURLLoad(url)
            elif url.startswith('template:'):
                newPage = True
                break

        if newPage:
            self.templateHandle.unlinkTemplate()
            self.__init__(re.compile(r"^template:(.*)$").match(url).group(1),data,controller, existingView, frameHint, areaHint)
        else:
            frontend.HTMLDisplay.__init__(self, html, existingView=existingView, frameHint=frameHint, areaHint=areaHint)

            thread = threading.Thread(target=self.templateHandle.initialFillIn)
            thread.setDaemon(False)
            thread.start()

    def onURLLoad(self, url):
        #print "DTV: got %s" % url
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
            sys.exit(1)

        return True

    def dispatchAction(self, action, **kwargs):
        for handler in self.actionHandlers:
            if hasattr(handler, action):
                getattr(handler, action)(**kwargs)
                return True

        return False

    def onDeselect(self):
        self.templateHandle.unlinkTemplate()

###############################################################################
#### Handlers for actions generated from templates, the OS, etc            ####
###############################################################################

# Functions that are safe to call from action: URLs that do nothing
# but manipulate the database.
class ModelActionHandler:
    def changeFeedSettings(self, feed, maxnew, fallbehind, automatic, expireDays, expireHours, expire, getEverything="0"):

        db.beginUpdate()
        db.saveCursor()
        try:
            for obj in db:
                if obj.getID() == int(feed):
                    obj.saveSettings(automatic,maxnew,fallbehind,expire,expireDays,expireHours,getEverything)
                    break
        finally:
            db.restoreCursor()
            db.endUpdate()

    def startDownload(self, item):
        db.beginUpdate()
        db.saveCursor()
        try:
            for obj in db:
                if obj.getID() == int(item):
                    obj.download()
                    break
        finally:
            db.restoreCursor()
            db.endUpdate()

    def removeFeed(self, url):
        db.removeMatching(lambda x: isinstance(x,feed.UniversalFeed) and x.getURL() == url)


    def updateFeed(self, url):
        db.beginUpdate()
        db.saveCursor()
        try:
            for obj in db:
                if isinstance(obj,feed.UniversalFeed) and obj.getURL() == url:
                    thread = threading.Thread(target=obj.update)
                    thread.setDaemon(False)
                    thread.start()
                    break
        finally:
            db.restoreCursor()
            db.endUpdate()

    def markFeedViewed(self, url):
        db.beginUpdate()
        db.saveCursor()
        try:
            for obj in db:
                if isinstance(obj,feed.UniversalFeed) and obj.getURL() == url:
                    obj.markAsViewed()
                    break
        finally:
            db.restoreCursor()
            db.endUpdate()

    def expireItem(self, item):
        db.beginUpdate()
        db.saveCursor()
        try:
            for obj in db:
                if obj.getID() == int(item):
                    obj.expire()
                    break
        finally:
            db.restoreCursor()
            db.endUpdate()

    def keepItem(self,item):
        db.beginUpdate()
        db.saveCursor()
        try:
            for obj in db:
                if obj.getID() == int(item):
                    obj.setKeep(True)
                    break
        finally:
            db.restoreCursor()
            db.endUpdate()

    # Collections

    def addCollection(self, title):
        x = feed.Collection(title)

    def removeCollection(self, id):
        db.beginUpdate()
        db.removeMatching(lambda x: isinstance(x, feed.Collection) and x.getID() == int(id))
        db.endUpdate()

    def addToCollection(self, id, item):
        db.beginUpdate()
        try:

            obj = None
            for x in db:
                if isinstance(x,feed.Collection) and x.getID() == int(id):
                    obj = x
                    break

            if obj != None:
                for x in db:
                    if isinstance(x,item.Item) and x.getID() == int(item):
                        obj.addItem(x)

        finally:
            db.endUpdate()

    def removeFromCollection(self, id, item):
        db.beginUpdate()
        try:

            obj = None
            for x in db:
                if isinstance(x,feed.Collection) and x.getID() == int(id):
                    obj = x
                    break

            if obj != None:
                for x in db:
                    if isinstance(x,item.Item) and x.getID() == int(item):
                        obj.removeItem(x)

        finally:
            db.endUpdate()

    def moveInCollection(self, id, item, pos):
        db.beginUpdate()
        try:

            obj = None
            for x in db:
                if isinstance(x,feed.Collection) and x.getID() == int(id):
                    obj = x
                    break

            if obj != None:
                for x in db:
                    if isinstance(x,item.Item) and x.getID() == int(item):
                        obj.moveItem(x,int(pos))

        finally:
            db.endUpdate()

    # Following are just for debugging/testing.

    def deleteTab(self, base):
        db.beginUpdate()
        try:
            db.removeMatching(lambda x: isinstance(x, StaticTab) and x.tabTemplateBase == base)
        finally:
            db.endUpdate()

    def createTab(self, tabTemplateBase, contentsTemplate, order):
        db.beginUpdate()
        try:
            order = int(order)
            StaticTab(tabTemplateBase, contentsTemplate, order)
        finally:
            db.endUpdate()

    def recomputeFilters(self):
        db.recomputeFilters()

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
        db.beginRead()
        # NEEDS: lock on controller state

        try:
            # Move the cursor to the newly selected object
            self.controller.tabs.resetCursor()
            while True:
                cur = self.controller.tabs.getNext()
                if cur == None:
                    assert(0) # NEEDS: better error (JS sent bad tab id)
                if cur.id == id:
                    break

        finally:
            db.endRead() # NEEDS: dropping this prematurely?

        # Figure out what happened
        oldSelected = self.controller.currentSelectedTab
        newSelected = self.controller.tabs.cur()

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
        db.saveCursor()

        try:
            exists = False
            for obj in db:
                if isinstance(obj,feed.UniversalFeed) and obj.getURL() == url:
                    exists = True
                    break

            if not exists:
                myFeed = feed.UniversalFeed(url)

                # At this point, the addition is guaranteed to be reflected
                # in the tab list.

            if selected == '1':
                tabs = self.controller.tabs
                tabs.resetCursor()
                while True:
                    cur = tabs.getNext()
                    if cur == None:
                        assert(0) # NEEDS: better error (failed to add tab)
                    if cur.feedURL() == url:
                        break

                self.controller.checkSelectedTab(showTemplate)

        finally:
            db.restoreCursor()
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

    def playView(self, viewName, firstItemId):
        # Find the database view that we're supposed to be
        # playing; take out items that aren't playable video
        # clips and put it in the format the frontend expects.
        namedView = self.templateHandle.findNamedView(viewName)
        view = namedView.getView()

        self.controller.frame.selectDisplay(frontend.VideoDisplay(firstItemId, view, self.display), self.controller.frame.mainDisplay)

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
        return isinstance(self.obj, feed.Feed) or isinstance(self.obj, feed.UniversalFeed)

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

# Reload the StaticTabs in the database from the statictabs.xml resource file.
def reloadStaticTabs():
    db.beginUpdate()
    try:
        # Wipe all of the StaticTabs currently in the database.
        db.removeMatching(lambda x: x.__class__ == StaticTab)

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
    return isinstance(obj, StaticTab) or isinstance(obj, folder.Folder) or (isinstance(obj, feed.Feed) and obj.isVisible()) or isinstance(obj, feed.UniversalFeed)

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
            elif isinstance(obj, feed.Feed) or isinstance(obj, feed.UniversalFeed):
                data['feed'] = obj
                # Change this to sort feeds on a different value
                sortKey = obj.getTitle()
                return Tab('feedtab', data, 'feed-start', data, [100, sortKey], obj, controller)
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

    def getVideoInfoHTML(self):
        info = '<span>'
        
        title = self.item.getTitle()
        if title.startswith(config.get(config.MOVIES_DIRECTORY)):
            title = os.path.basename(title)
        info += '<span class="title">%s</span>' % title
        
        channelName = self.item.getFeed().getTitle()
        channelLink = self.item.getFeed().getLink()
        if channelLink == '':
            info += ' (%s)' % channelName
        else:
            info += ' (<a href="%s">%s</a>)' % (channelLink, channelName)
        
        info += '<span>'
        return info

    # Return a dictionary containing info to be injected in a template
    def getInfoMap(self):
        info = dict()
        info['this'] = self.item
        info['videoInfoHTML'] = self.getVideoInfoHTML()
        return info

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
def undownloadedItems(obj,param):
    params = param.split('|',1)
    
    undled = (str(obj.feed.getID()) == params[0] and 
              (not (obj.getState() == 'finished' or
                    obj.getState() == 'uploading' or
                    obj.getState() == 'watched')))
    if len(params) > 1:
        undled = (undled and 
                  (str(params[1]).lower() in obj.getTitle().lower() or
                   str(params[1]).lower() in obj.getDescription().lower()))
    return undled

def downloadedItems(obj, param):
    params = param.split('|',1)
    
    dled = (str(obj.feed.getID()) == params[0] and 
              ((obj.getState() == 'finished' or
                obj.getState() == 'uploading' or
                obj.getState() == 'watched')))
    if len(params) > 1:
        dled = (dled and 
                (str(params[1]).lower() in obj.getTitle().lower() or
                 str(params[1]).lower() in obj.getDescription().lower()))
    return dled

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

    'feedItems' : feedItems,
    'recentItems': recentItems,
    'allRecentItems': allRecentItems,
    'oldItems': oldItems,
    'watchableItems': watchableItems,
    'downloadedItems': downloadedItems,
    'unDownloadedItems':  undownloadedItems,
    'allDownloadingItems': allDownloadingItems                         ,
       
    'class': filterClass,
    'all': (lambda x, y: True),
    'hasKey':  filterHasKey,
    'equal':(lambda x, y: str(x) == str(y)),
}


globalViewList = {
    'items': db.filter(lambda x: isinstance(x,item.Item)),
    'feeds': db.filter(lambda x: isinstance(x,feed.UniversalFeed)),
    'httpauths':  db.filter(lambda x: isinstance(x,downloader.HTTPAuthPassword))
}
