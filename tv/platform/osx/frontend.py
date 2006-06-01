from PyObjCTools import NibClassBuilder, AppHelper, Conversion
from objc import YES, NO, nil
from gestalt import gestalt
from Foundation import *
from AppKit import *
from WebKit import *

try:
    from QTKit import *
except:
    print "DTV: QTKit coudln't be imported. Please upgrade to Quicktime 7 or later. You can update at http://apple.com/quicktime/ or by running Software Update."

import app
import feed
import prefs
import config
import resource
import template
import database
import eventloop
import autoupdate
import singleclick
import platformutils

import re
import os
import sys
import glob
import objc
import time
import math
import struct
import string
import signal
import urlparse
import threading

NibClassBuilder.extractClasses("MainMenu")
NibClassBuilder.extractClasses("MainWindow")
NibClassBuilder.extractClasses("PreferencesWindow")
NibClassBuilder.extractClasses("AddChannelSheet")
NibClassBuilder.extractClasses("PasswordWindow")
NibClassBuilder.extractClasses("ExceptionReporterPanel")

doNotCollect = {}
nc = NSNotificationCenter.defaultCenter()

def exit(returnCode):
   sys.exit(returnCode)

def quit():
    NSApplication.sharedApplication().terminate_(nil)

# These are used by the channel guide. This platform uses the
# old-style 'magic URL' guide API, so we just return None. See
# ChannelGuideToDtvApi in the Trac wiki for the full writeup.
def getDTVAPICookie():
    return None
def getDTVAPIURL():
    return None

###############################################################################
#### Dynamically link some specific Carbon functions which we need but     ####
###  which are not available in the default MacPython                      ####
###############################################################################

kUIModeNormal = 0
kUIModeAllHidden = 3

carbonPath = objc.pathForFramework('/System/Library/Frameworks/Carbon.framework')
carbonBundle = NSBundle.bundleWithPath_(carbonPath)
objc.loadBundleFunctions(carbonBundle, globals(), ((u'SetSystemUIMode', 'III'),))

OverallAct = 0

coreServicesPath = objc.pathForFramework('/System/Library/Frameworks/CoreServices.framework')
coreServicesBundle = NSBundle.bundleWithPath_(coreServicesPath)
objc.loadBundleFunctions(coreServicesBundle, globals(), ((u'UpdateSystemActivity', 'IC'),))

###############################################################################
#### Helper methods used to display alert dialog of various types          ####
###############################################################################

def showInformationalDialog(summary, message, buttons=None):
    return showDialog(summary, message, buttons, NSInformationalAlertStyle)

def showWarningDialog(summary, message, buttons=None):
    return showDialog(summary, message, buttons, NSWarningAlertStyle)

def showCriticalDialog(summary, message, buttons=None):
    return showDialog(summary, message, buttons, NSCriticalAlertStyle)

def showDialog(summary, message, buttons, style):
    pool = NSAutoreleasePool.alloc().init()
    alert = NSAlert.alloc().init()
    alert.setAlertStyle_(style)
    alert.setMessageText_(summary)
    alert.setInformativeText_(message)
    if buttons is not None:
        for title in buttons:
            alert.addButtonWithTitle_(title)
    result = alert.runModal()
    result -= NSAlertFirstButtonReturn
    del alert
    del pool
    return result


###############################################################################
#### Application object                                                    ####
###############################################################################

class Application:

    def __init__(self):
        self.appl = NSApplication.sharedApplication()
        NSBundle.loadNibNamed_owner_("MainMenu", self.appl)
        controller = self.appl.delegate()
        controller.actualApp = self
        
        controller.checkQuicktimeVersion(True)

        # Force Cocoa into multithreaded mode
        # (NSThread.isMultiThreaded will be true when this call returns)
        NSThread.detachNewThreadSelector_toTarget_withObject_("noop", controller, controller)

    def Run(self):
        eventloop.setDelegate(self)
        AppHelper.runEventLoop()

    def getBackendDelegate(self):
        return UIBackendDelegate()

    def onStartup(self):
        # For overriding
        pass

    def onShutdown(self):
        # For overriding
        pass

    def addAndSelectFeed(self, url):
        # For overriding
        pass

    ### eventloop (the Democracy one, not the Cocoa one) delegate methods

    def beginLoop(self, loop):
        loop.pool = NSAutoreleasePool.alloc().init()

    def endLoop(self, loop):
        del loop.pool

class AppController (NibClassBuilder.AutoBaseClass):

    # Do nothing. A dummy method called by Application to force Cocoa into
    # multithreaded mode.
    def noop(self):
        return

    def applicationWillFinishLaunching_(self, notification):
        man = NSAppleEventManager.sharedAppleEventManager()
        man.setEventHandler_andSelector_forEventClass_andEventID_(
            self,
            "openURL:withReplyEvent:",
            struct.unpack(">i", "GURL")[0],
            struct.unpack(">i", "GURL")[0])

        nc.addObserver_selector_name_object_(self, 'videoWillPlay:', 'videoWillPlay',  nil)
        nc.addObserver_selector_name_object_(self, 'videoWillStop:', 'videoWillPause', nil)
        nc.addObserver_selector_name_object_(self, 'videoWillStop:', 'videoWillStop',  nil)
        
        ws = NSWorkspace.sharedWorkspace()
        wsnc = ws.notificationCenter()
        wsnc.addObserver_selector_name_object_(self, 'workspaceWillSleep:', NSWorkspaceWillSleepNotification, nil)
        wsnc.addObserver_selector_name_object_(self, 'workspaceDidWake:',   NSWorkspaceDidWakeNotification,   nil)
        
    def applicationDidFinishLaunching_(self, notification):
        # The [NSURLRequest setAllowsAnyHTTPSCertificate:forHost:] selector is
        # not documented anywhere, so I assume it is not public. It is however 
        # a very clean and easy way to allow us to load our channel guide from
        # https, so let's use it here anyway :)
        components = urlparse.urlparse(config.get(prefs.CHANNEL_GUIDE_URL))
        channelGuideHost = components[1]
        NSURLRequest.setAllowsAnyHTTPSCertificate_forHost_(YES, channelGuideHost)

        # Startup
        self.actualApp.onStartup()
    
    def applicationDidBecomeActive_(self, notification):
        # This should hopefully avoid weird things like #1722
        app.controller.frame.controller.window().contentView().setNeedsDisplay_(YES)
    
    def applicationWillTerminate_(self, notification):
        # Reset the application icon to its default state
        defaultAppIcon = NSImage.imageNamed_('NSApplicationIcon')
        NSApplication.sharedApplication().setApplicationIconImage_(defaultAppIcon)
        # Call shutdown on backend
        self.actualApp.onShutdown()

    def application_openFiles_(self, app, filenames):
        platformutils.callOnMainThreadAndWaitUntilDone(self.openFiles, filenames)
        app.replyToOpenOrPrint_(NSApplicationDelegateReplySuccess)

    def addTorrent(self, path):
        try:
            infoHash = singleclick.getTorrentInfoHash(path)
        except:
            print "WARNING: %s doesn't seem to be a torrent file" % path
        else:
            singleclick.addTorrent(path, infoHash)
            app.controller.selectTabByTemplateBase('downloadtab')
        
    def addVideo(self, path):
        singleclick.addVideo(path)
        app.controller.selectTabByTemplateBase('librarytab')

    def workspaceWillSleep_(self, notification):
        downloads = app.globalViewList['remoteDownloads']
        dlCount = len(downloads)
        if dlCount > 0:
            print "DTV: System is going to sleep, suspending downloads."
            downloads.beginRead()
            try:
                for dl in downloads:
                    dl.pause(block=True)
            finally:
                downloads.endRead()

    def workspaceDidWake_(self, notification):
        downloads = app.globalViewList['remoteDownloads']
        dlCount = len(downloads)
        if dlCount > 0:
            print "DTV: System is awake, resuming downloads."
            downloads.beginRead()
            try:
                for dl in downloads:
                    dl.start()
            finally:
                downloads.endRead()

    def videoWillPlay_(self, notification):
        self.playPauseMenuItem.setTitle_('Pause Video')

    def videoWillStop_(self, notification):
        self.playPauseMenuItem.setTitle_('Play Video')

    def checkQuicktimeVersion(self, showError):
        supported = gestalt('qtim') >= 0x07000000
        
        if not supported and showError:
            summary = u'Unsupported version of Quicktime'
            message = u'To run %s you need the most recent version of Quicktime, which is a free update.' % (config.get(prefs.LONG_APP_NAME), )
            buttons = ('Quit', 'Download Quicktime now')
            result = showCriticalDialog(summary, message, buttons)
            if result == 0:
                NSApplication.sharedApplication().terminate_(nil)
            else:
                url = NSURL.URLWithString_('http://www.apple.com/quicktime/download')
                NSWorkspace.sharedWorkspace().openURL_(url)
        
        return supported

    @objc.signature('v@:@@')
    def openURL_withReplyEvent_(self, event, replyEvent):
        print "**** got open URL event"
        keyDirectObject = struct.unpack(">i", "----")[0]
        url = event.paramDescriptorForKeyword_(keyDirectObject).stringValue()

        # Convert feed: URL to http:
        # (we only get here if the URL is a feed: URL, because of what
        # we've claimed in Info.plist)
        match = re.compile(r"^feed:(.*)$").match(url)
        if match:
            url = "http:%s" % match.group(1)
            self.actualApp.addAndSelectFeed(url)

    def checkForUpdates_(self, sender):
        autoupdate.checkForUpdates(True)

    def showPreferencesWindow_(self, sender):
        prefController = PreferencesWindowController.alloc().init()
        prefController.retain()
        prefController.showWindow_(nil)

    def openFile_(self, sender):
        openPanel = NSOpenPanel.openPanel()
        openPanel.setAllowsMultipleSelection_(YES)
        openPanel.setCanChooseDirectories_(NO)
        result = openPanel.runModalForDirectory_file_types_(NSHomeDirectory(), nil, nil)
        if result == NSOKButton:
            filenames = openPanel.filenames()
            self.openFiles(filenames)
                
    def openFiles(self, filenames):
        singleclick.resetCommandLineView()
        for filename in filenames:
            root, ext = os.path.splitext(filename.lower())
            if ext == ".democracy":
                singleclick.addSubscriptions(filename)
            elif ext == ".torrent":
                self.addTorrent(filename)
            elif ext in (".rss", ".rdf", ".atom"):
                singleclick.addFeed(filename)
            else:
                self.addVideo(filename)
        singleclick.playCommandLineView()

    def donate_(self, sender):
        print "NOT IMPLEMENTED"

    def shutdown_(self, sender):
        app.controller.quit()

    itemsAlwaysAvailable = ('checkForUpdates:', 'showPreferencesWindow:', 'openFile:', 'shutdown:')
    def validateMenuItem_(self, item):
        return item.action() in self.itemsAlwaysAvailable
        

###############################################################################
#### Main window                                                           ####
###############################################################################

# ObjC classes can't be instantiated directly. To shield the user from
# this, we create a Python proxy object thats hold a reference to an
# actual ObjC class that is created when the proxy is
# instantiated. The ObjC class is in turn constructed with an 'owner'
# reference pointing to the proxy object, which is used to deliver
# callbacks.

class MainFrame:

    def __init__(self, appl):
        """The initially active display will be an instance of NullDisplay."""
        self.channelsDisplay = None
        self.mainDisplay = None
        self.videoInfoDisplay = None
        # Do this in two steps so that self.controller is set when self.controler.init
        # is called. That way, init can turn around and call selectDisplay.
        self.controller = MainController.alloc()
        self.controller.init(self, appl)

    def selectDisplay(self, display, area=None):
        """Install the provided 'display' in the requested area"""
        pool = NSAutoreleasePool.alloc().init()
        self.controller.selectDisplay(display, area)
        del pool

    def getDisplay(self, area):
        return area.hostedDisplay

    # Internal use: return an estimate of the size of a given display area as
    # a Cocoa frame object.
    def getDisplaySizeHint(self, area):
        return self.controller.getDisplaySizeHint(area)


class DisplayHostView (NibClassBuilder.AutoBaseClass):
    
    def initWithFrame_(self, frame):
        self = super(DisplayHostView, self).initWithFrame_(frame)
        self.scheduledDisplay = None
        self.hostedDisplay = None
        self.hostedView = nil
        self.backgroundColor = NSColor.whiteColor()
        return self

    def drawRect_(self, rect):
        self.backgroundColor.set()
        NSRectFill(rect)

    def setScheduledDisplay(self, display):
        if self.scheduledDisplay is not None:
            self.scheduledDisplay.cancel()
        self.scheduledDisplay = display
    
    def setDisplay(self, display, owner):
        self.scheduledDisplay = None

        # Send notification to old display if any
        if self.hostedDisplay is not None:
            self.hostedDisplay.onDeselected_private(owner)
            self.hostedDisplay.onDeselected(owner)
        oldView = self.hostedView

        # Switch to new display
        self.hostedDisplay = display
        if display is not None:
            self.hostedView = display.getView()
        else:
            self.hostedView = nil
        if display is None:
            return

        # Figure out where to put the content area
        # NEEDS: clean up outlet names/types in nib
        frame = self.bounds()
        mask = self.autoresizingMask()

        # Arrange to cover the template that marks the content area
        self.hostedView.setFrame_(frame)
        self.addSubview_(self.hostedView)
        self.hostedView.setAutoresizingMask_(mask)

        # Mark as needing display
        self.setNeedsDisplayInRect_(frame)
        self.hostedView.setNeedsDisplay_(YES)

        # Wait until now to clean up the old view, to reduce flicker
        # (doesn't actually work all that well, sadly -- possibly what
        # we want to do is wait until notification comes from the new
        # view that it's been fully loaded to even show it)
        if oldView and (not (oldView is self.hostedView)):
            oldView.removeFromSuperview()

        # Send notification to new display
        display.onSelected_private(owner)
        display.onSelected(owner)


class MainController (NibClassBuilder.AutoBaseClass):

    def init(self, frame, appl):
        NSObject.init(self)
        self.frame = frame
        self.appl = appl
        NSBundle.loadNibNamed_owner_("MainWindow", self)

        nc.addObserver_selector_name_object_(
            self,
            'appWillTerminate:',
            NSApplicationWillTerminateNotification,
            NSApplication.sharedApplication())

        return self

    def awakeFromNib(self):
        self.frame.channelsDisplay = self.channelsHostView
        self.frame.mainDisplay = self.mainHostView
        self.frame.videoInfoDisplay = self.videoInfoHostView
        self.frame.videoInfoDisplay.backgroundColor = NSColor.blackColor()
        self.restoreLayout()
        self.updateWindowTexture()
        self.actionButton.sendActionOn_(NSLeftMouseDownMask)
        self.showWindow_(nil)

    def appWillTerminate_(self, notification):
        self.saveLayout()

    def restoreLayout(self):
        windowFrame = config.get(prefs.MAIN_WINDOW_FRAME)
        if windowFrame is None:
            windowFrame = self.window().frame()
        else:
            windowFrame = NSRectFromString(windowFrame)
        screen = self.window().screen()
        if screen is not None:
            visibleFrame = screen.visibleFrame()
            if not NSContainsRect(visibleFrame, windowFrame):
                print "DTV: Fitting window to screen size"
                windowFrame = visibleFrame
        self.window().setFrame_display_(windowFrame, NO)

        leftFrame = config.get(prefs.LEFT_VIEW_SIZE)
        rightFrame = config.get(prefs.RIGHT_VIEW_SIZE)
        if leftFrame is not None and rightFrame is not None:
           leftFrame = NSRectFromString(leftFrame)
           rightFrame = NSRectFromString(rightFrame)
           self.splitView.subviews().objectAtIndex_(0).setFrame_(leftFrame)
           self.splitView.subviews().objectAtIndex_(1).setFrame_(rightFrame)
           self.splitView.adjustSubviews()

    def saveLayout(self):
        windowFrame = self.window().frame()
        windowFrame = NSStringFromRect(windowFrame)
        leftFrame = self.splitView.subviews().objectAtIndex_(0).frame()
        leftFrame = NSStringFromRect(leftFrame)
        rightFrame = self.splitView.subviews().objectAtIndex_(1).frame()
        rightFrame = NSStringFromRect(rightFrame)

        config.set(prefs.MAIN_WINDOW_FRAME, windowFrame)
        config.set(prefs.LEFT_VIEW_SIZE, leftFrame)
        config.set(prefs.RIGHT_VIEW_SIZE, rightFrame)
        config.save()

    def updateWindowTexture(self):
        bgTexture = NSImage.alloc().initWithSize_(self.window().frame().size)
        bgTexture.lockFocus()
                
        topImage = NSImage.imageNamed_(u'wtexture_top')
        topColor = NSColor.colorWithPatternImage_(topImage)
        topColor.set()
        NSGraphicsContext.currentContext().setPatternPhase_(bgTexture.size())
        NSRectFill(((0, bgTexture.size().height - topImage.size().height), (bgTexture.size().width, topImage.size().height)))
        
        bottomImage = NSImage.imageNamed_(u'wtexture_bottom')
        bottomColor = NSColor.colorWithPatternImage_(bottomImage)
        bottomColor.set()
        NSGraphicsContext.currentContext().setPatternPhase_(bottomImage.size())
        NSRectFill(((0, 0), (bgTexture.size().width, bottomImage.size().height)))

        bgColor = NSColor.colorWithCalibratedWhite_alpha_(195.0/255.0, 1.0)
        bgColor.set()
        NSRectFill(((0, bottomImage.size().height), (bgTexture.size().width, bgTexture.size().height -  bottomImage.size().height - topImage.size().height)))
        
        bgTexture.unlockFocus()
        
        self.window().setBackgroundColor_(NSColor.colorWithPatternImage_(bgTexture))
        
    ### Switching displays ###

    def selectDisplay(self, display, area):
        if display is not None:
            # Tell the display area that the next display it will host once it's
            # ready is this one.
            area.setScheduledDisplay(display)
            # Tell the new display we want to switch to it. It'll call us
            # back when it's ready to display without flickering.
            display.callWhenReadyToDisplay(lambda: self.doSelectDisplay(display, area))

    @platformutils.onMainThread
    def doSelectDisplay(self, display, area):
        if area is not None:
            area.setDisplay(display, self.frame)
            if isinstance(display, app.TemplateDisplay) and area == self.mainHostView:
                view = display.getWatchable()
                if view is not None:
                    nc.postNotificationName_object_userInfo_('displayIsWatchable', display, {'view': view})
                else:
                    nc.postNotificationName_object_('displayIsNotWatchable', display)

    def getDisplaySizeHint(self, area):
        return area.frame()

    ### Window resize handler

    def windowDidResize_(self, notification):
        self.updateWindowTexture()

    ### Size constraints on splitview ###

    minimumTabListWidth = 160 # pixels
    minimumContentWidth = 500 # pixels

    # How far left can the user move the slider?
    def splitView_constrainMinCoordinate_ofSubviewAt_(self, sender, proposedMin, offset):
        return proposedMin + self.minimumTabListWidth

    # How far right can the user move the slider?
    def splitView_constrainMaxCoordinate_ofSubviewAt_(self, sender, proposedMax, offset):
        return proposedMax - self.minimumContentWidth

    # The window was resized; compute new positions of the splitview
    # children. Rule: resizing the window doesn't change the size of
    # the tab list unless it's necessary to shrink it to obey the
    # minimum content area size constraint.
    def splitView_resizeSubviewsWithOldSize_(self, sender, oldSize):
        tabBox = self.channelsHostView.superview()
        contentBox = self.mainHostView.superview()

        splitViewSize = sender.frame().size
        tabSize = tabBox.frame().size
        contentSize = contentBox.frame().size
        dividerWidth = sender.dividerThickness()

        tabSize.height = contentSize.height = splitViewSize.height

        contentSize.width = splitViewSize.width - dividerWidth - tabSize.width
        if contentSize.width < self.minimumContentWidth:
            contentSize.width = self.minimumContentWidth
        tabSize.width = splitViewSize.width - dividerWidth - contentSize.width

        tabBox.setFrameSize_(tabSize)
        tabBox.setFrameOrigin_(NSZeroPoint)
        contentBox.setFrameSize_(contentSize)
        contentBox.setFrameOrigin_((tabSize.width + dividerWidth, 0))

    def splitView_canCollapseSubview_(self, sender, subview):
        return self.channelsHostView.isDescendantOf_(subview) and app.controller.videoDisplay.isSelected()

    ### Events ###

    def keyDown_(self, event):
        if self.frame.mainDisplay.hostedDisplay is app.controller.videoDisplay and event.characters().characterAtIndex_(0) == 0x20:
            app.controller.playbackController.playPause()

    ### Actions ###

    def playPause_(self, sender):
        VideoDisplayController.getInstance().playPause_(sender)

    def stopVideo_(self, sender):
        VideoDisplayController.getInstance().stop_(sender)

    def playFullScreen_(self, sender):
        VideoDisplayController.getInstance().playFullScreen_(sender)

    def playHalfScreen_(self, sender):
        pass

    def deleteVideo_(self, sender):
        print "NOT IMPLEMENTED"

    def saveVideo_(self, sender):
        print "NOT IMPLEMENTED"

    def copyVideoLink_(self, sender):
        print "NOT IMPLEMENTED"

    def addChannel_(self, sender):
        controller = AddChannelSheetController.alloc().init(self.appl)
        controller.retain()
        NSApplication.sharedApplication().beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(controller.window(), self.window(), self, nil, 0)

    def removeChannel_(self, sender):
        feedID = app.controller.currentSelectedTab.feedID()
        if feedID is not None:
            backEndDelegate = self.appl.getBackendDelegate()
            eventloop.addUrgentCall(lambda:app.ModelActionHandler(backEndDelegate).removeFeed(feedID), "Remove channel")

    def copyChannelLink_(self, sender):
        NSPasteboard.generalPasteboard().declareTypes_owner_([NSURLPboardType], self)

    def updateChannel_(self, sender):
        feedID = app.controller.currentSelectedTab.feedID()
        if feedID is not None:
            backEndDelegate = self.appl.getBackendDelegate()
            eventloop.addUrgentCall(lambda:app.ModelActionHandler(backEndDelegate).updateFeed(feedID), "Update channel")

    def updateAllChannels_(self, sender):
        backEndDelegate = self.appl.getBackendDelegate()
        eventloop.addUrgentCall(lambda:app.ModelActionHandler(backEndDelegate).updateAllFeeds(), "Update all channels")

    def renameChannel_(self, sender):
        print "NOT IMPLEMENTED"

    def createCollection_(self, sender):
        print "NOT IMPLEMENTED"

    def deleteCollection_(self, sender):
        print "NOT IMPLEMENTED"

    def sendCollectionToFriend_(self, sender):
        print "NOT IMPLEMENTED"

    def tellAFriend_(self, sender):
        print "NOT IMPLEMENTED"

    def showActionMenu_(self, sender):
        mainMenu = NSApplication.sharedApplication().mainMenu()
        # collections do not really work just yet so we hardcode the action menu
        # to the channel menu
        # tag = self.switcherMatrix.selectedCell().tag()
        tag = 1
        menu = mainMenu.itemWithTag_(tag).submenu()

        location = sender.frame().origin
        location.x += 10.0
        location.y += 3.0

        curEvent = NSApplication.sharedApplication().currentEvent()
        event = NSEvent.mouseEventWithType_location_modifierFlags_timestamp_windowNumber_context_eventNumber_clickCount_pressure_(
            curEvent.type(),
            location,
            curEvent.modifierFlags(),
            curEvent.timestamp(),
            curEvent.windowNumber(),
            nil,
            curEvent.eventNumber(),
            curEvent.clickCount(),
            curEvent.pressure() )

        NSMenu.popUpContextMenu_withEvent_forView_( menu, event, sender )

    def showHelp_(self, sender):
        summary = u'Help for %s will be available soon.' % \
            (config.get(prefs.LONG_APP_NAME), )
        message = u'In the meantime, please visit our homepage for our help FAQ: %s\n\nFor individual user support, please e-mail feedback@ppolitics.org.' % (config.get(prefs.PROJECT_URL), )
        showInformationalDialog(summary, message)

    itemsAlwaysAvailable = ('addChannel:', 'showHelp:', 'updateAllChannels:')
    selectedChannelItems = ('removeChannel:', 'copyChannelLink:', 'updateChannel:')
    def validateMenuItem_(self, item):
        if item.action() in self.selectedChannelItems:
            currentTab = app.controller.currentSelectedTab
            return currentTab is not None and currentTab.isFeed()
        elif item.action() == 'playPause:' or item.action() == 'playFullScreen:':
            display = self.frame.mainDisplay.hostedDisplay
            if display is not None:
                if display is app.controller.videoDisplay:
                    return YES
                else:
                    return display.getWatchable() is not None
            else:
                return NO
        elif item.action() == 'stopVideo:':
            return self.frame.mainDisplay.hostedDisplay is app.controller.videoDisplay
        else:
            return item.action() in self.itemsAlwaysAvailable

    def pasteboard_provideDataForType_(self, pasteboard, type):
        feedURL = app.controller.currentSelectedTab.feedURL()
        if feedURL is not None:
            url = NSURL.URLWithString_(feedURL)
            url.writeToPasteboard_(NSPasteboard.generalPasteboard())


###############################################################################
#### Add channel sheet                                                     ####
###############################################################################

class AddChannelSheetController (NibClassBuilder.AutoBaseClass):

    def init(self, parent):
        super(AddChannelSheetController, self).initWithWindowNibName_owner_("AddChannelSheet", self)
        self.parentController = parent
        return self

    def awakeFromNib(self):
        url = NSPasteboard.generalPasteboard().stringForType_(NSStringPboardType)
        if url is None or not feed.validateFeedURL(url):
            url = ''
        self.addChannelSheetURL.setStringValue_(url)

    def addChannelSheetDone_(self, sender):
        sheetURL = self.addChannelSheetURL.stringValue()
        self.parentController.addAndSelectFeed(sheetURL)
        self.closeSheet()

    def addChannelSheetCancel_(self, sender):
        self.closeSheet()

    def closeSheet(self):
        NSApplication.sharedApplication().endSheet_(self.window())
        self.window().orderOut_(self)
        #self.release()


###############################################################################
#### Preferences window                                                    ####
###############################################################################

class PreferencesWindowController (NibClassBuilder.AutoBaseClass):

    class PreferenceItem (NSToolbarItem):
        def setView_(self, view):
            self.view = view

    def init(self):
        super(PreferencesWindowController, self).initWithWindowNibName_("PreferencesWindow")
        return self

    def awakeFromNib(self):
        generalItem = self.makePreferenceItem("GeneralItem", "General", "general_pref", self.generalView)
        channelsItem = self.makePreferenceItem("ChannelsItem", "Channels", "channels_pref", self.channelsView)
        downloadsItem = self.makePreferenceItem("DownloadsItem", "Downloads", "downloads_pref", self.downloadsView)
        diskSpaceItem = self.makePreferenceItem("DiskSpaceItem", "Disk Space", "disk_space_pref", self.diskSpaceView)

        self.items = {generalItem.itemIdentifier(): generalItem,
                      channelsItem.itemIdentifier(): channelsItem,
                      downloadsItem.itemIdentifier(): downloadsItem,
                      diskSpaceItem.itemIdentifier(): diskSpaceItem}

        self.allItems = (generalItem.itemIdentifier(),
                         channelsItem.itemIdentifier(),
                         downloadsItem.itemIdentifier(),
                         diskSpaceItem.itemIdentifier())

        initialItem = generalItem

        toolbar = NSToolbar.alloc().initWithIdentifier_("Preferences")
        toolbar.setDelegate_(self)
        toolbar.setAllowsUserCustomization_(NO)
        toolbar.setSelectedItemIdentifier_(initialItem.itemIdentifier())

        self.window().setToolbar_(toolbar)
        if hasattr(self.window(), 'setShowsToolbarButton_'): # 10.4 only
            self.window().setShowsToolbarButton_(NO)
        self.switchPreferenceView_(initialItem)

    def makePreferenceItem(self, identifier, label, imageName, view):
        item = self.PreferenceItem.alloc().initWithItemIdentifier_(identifier)
        item.setLabel_(label)
        item.setImage_(NSImage.imageNamed_(imageName))
        item.setTarget_(self)
        item.setAction_("switchPreferenceView:")
        item.setView_(view)
        return item

    def toolbarAllowedItemIdentifiers_(self, toolbar):
        return self.allItems

    def toolbarDefaultItemIdentifiers_(self, toolbar):
        return self.allItems

    def toolbarSelectableItemIdentifiers_(self, toolbar):
        return self.allItems

    def toolbar_itemForItemIdentifier_willBeInsertedIntoToolbar_(self, toolbar, itemIdentifier, flag ):
        return self.items[ itemIdentifier ]

    def validateToolbarItem_(self, item):
        return YES

    def switchPreferenceView_(self, sender):
        if self.window().contentView() == sender.view:
            return

        window = self.window()
        wframe = window.frame()
        vframe = sender.view.frame()
        toolbarHeight = wframe.size.height - window.contentView().frame().size.height
        wframe.origin.y += wframe.size.height - vframe.size.height - toolbarHeight
        wframe.size = vframe.size
        wframe.size.height += toolbarHeight

        self.window().setContentView_(sender.view)
        self.window().setFrame_display_animate_(wframe, YES, YES)

class GeneralPrefsController (NibClassBuilder.AutoBaseClass):
    
    def awakeFromNib(self):
        run = config.get(prefs.RUN_DTV_AT_STARTUP)
        self.runAtStartupCheckBox.setState_(run and NSOnState or NSOffState)
    
    def runAtStartup_(self, sender):
        run = (sender.state() == NSOnState)
        config.set(prefs.RUN_DTV_AT_STARTUP, run)

        defaults = NSUserDefaults.standardUserDefaults()
        lwdomain = defaults.persistentDomainForName_('loginwindow')
        lwdomain = Conversion.pythonCollectionFromPropertyList(lwdomain)
        launchedApps = lwdomain['AutoLaunchedApplicationDictionary']
        ourPath = NSBundle.mainBundle().bundlePath()
        ourEntry = None
        for entry in launchedApps:
            if entry['Path'] == ourPath:
                ourEntry = entry
                break

        if run and ourEntry is None:
            launchInfo = dict(Path=ourPath, Hide=NO)
            launchedApps.append(launchInfo)
        elif ourEntry is not None:
            launchedApps.remove(entry)

        lwdomain = Conversion.propertyListFromPythonCollection(lwdomain)
        defaults.setPersistentDomain_forName_(lwdomain, 'loginwindow')
        defaults.synchronize()
                    
class ChannelsPrefsController (NibClassBuilder.AutoBaseClass):

    def awakeFromNib(self):
        minutes = config.get(prefs.CHECK_CHANNELS_EVERY_X_MN)
        itemIndex = self.periodicityPopup.indexOfItemWithTag_(minutes)
        self.periodicityPopup.selectItemAtIndex_(itemIndex)

    def checkEvery_(self, sender):
        minutes = sender.selectedItem().tag()
        config.set(prefs.CHECK_CHANNELS_EVERY_X_MN, minutes)

class DownloadsPrefsController (NibClassBuilder.AutoBaseClass):
    
    def awakeFromNib(self):
        moviesDirPath = config.get(prefs.MOVIES_DIRECTORY)
        self.moviesDirectoryField.setStringValue_(moviesDirPath)
        limit = config.get(prefs.LIMIT_UPSTREAM)
        self.limitUpstreamCheckBox.setState_(limit and NSOnState or NSOffState)
        self.limitValueField.setEnabled_(limit)
        self.limitValueField.setIntValue_(config.get(prefs.UPSTREAM_LIMIT_IN_KBS))
    
    def limitUpstream_(self, sender):
        limit = (sender.state() == NSOnState)
        self.limitValueField.setEnabled_(limit)
        config.set(prefs.LIMIT_UPSTREAM, limit)
        self.setUpstreamLimit_(self.limitValueField)
    
    def setUpstreamLimit_(self, sender):
        limit = sender.intValue()
        config.set(prefs.UPSTREAM_LIMIT_IN_KBS, limit)
        
    def changeMoviesDirectory_(self):
        panel = NSOpenPanel.openPanel()
        panel.setCanChooseFiles_(NO)
        panel.setCanChooseDirectories_(YES)
        panel.setCanCreateDirectories_(YES)
        panel.setAllowsMultipleSelection_(NO)
        panel.setTitle_('Movies Directory')
        panel.setMessage_('Select a Directory to store Democracy downloads in.')
        panel.setPrompt_('Select')
        
        oldMoviesDirectory = self.moviesDirectoryField.stringValue()
        result = panel.runModalForDirectory_file_(oldMoviesDirectory, nil)
        
        if result == NSOKButton:
            newMoviesDirectory = panel.directory()
            if newMoviesDirectory != oldMoviesDirectory:
                self.moviesDirectoryField.setStringValue_(newMoviesDirectory)
                summary = u'Migrate existing movies?'
                message = u'You\'ve selected a new folder to download movies to.  Should Democracy migrate your existing downloads there?  (Currently dowloading movies will not be moved until they finish).'
                buttons = (u'Yes', u'No')
                result = showWarningDialog(summary, message, buttons)
                migrate = (result == 0)
                app.changeMoviesDirectory(newMoviesDirectory, migrate)
                

class DiskSpacePrefsController (NibClassBuilder.AutoBaseClass):
    
    def awakeFromNib(self):
        preserve = config.get(prefs.PRESERVE_DISK_SPACE)
        self.preserveSpaceCheckBox.setState_(preserve and NSOnState or NSOffState)
        self.minimumSpaceField.setEnabled_(preserve)
        self.minimumSpaceField.setIntValue_(config.get(prefs.PRESERVE_X_GB_FREE))
        itemTag = int(config.get(prefs.EXPIRE_AFTER_X_DAYS) * 24)
        itemIndex = self.expirationDelayPopupButton.indexOfItemWithTag_(itemTag)
        self.expirationDelayPopupButton.selectItemAtIndex_(itemIndex)
    
    def preserveDiskSpace_(self, sender):
        preserve = (sender.state() == NSOnState)
        self.minimumSpaceField.setEnabled_(preserve)
        config.set(prefs.PRESERVE_DISK_SPACE, preserve)
        self.setMinimumSpace_(self.minimumSpaceField)
    
    def setMinimumSpace_(self, sender):
        space = sender.floatValue()
        config.set(prefs.PRESERVE_X_GB_FREE, space)
        
    def setExpirationDelay_(self, sender):
        delay = sender.selectedItem().tag()
        config.set(prefs.EXPIRE_AFTER_X_DAYS, delay / 24.0)


###############################################################################
#### 'Delegate' objects for asynchronously asking the user questions       ####
###############################################################################

class UIBackendDelegate:

    # This lock is used by getHTTPAuth to serialize HTTP authentication requests 
    # and prevent multiple authentication dialogs to pop up at once.
    httpAuthLock = threading.Lock()

    def runDialog(self, dialog):
        buttons = map(lambda x:x.text, dialog.buttons)
        result = showWarningDialog(dialog.title, dialog.description, buttons)
        dialog.runCallback(dialog.buttons[result])

    def getHTTPAuth(self, url, domain, prefillUser = None, prefillPassword = None):
        """Ask the user for HTTP login information for a location, identified
        to the user by its URL and the domain string provided by the
        server requesting the authorization. Default values can be
        provided for prefilling the form. If the user submits
        information, it's returned as a (user, password)
        tuple. Otherwise, if the user presses Cancel or similar, None
        is returned."""
        ret = None
        self.httpAuthLock.acquire()
        try:
            message = "%s requires a username and password for \"%s\"." % (url, domain)
            ret = PasswordController.alloc().init(message, prefillUser, prefillPassword).getAnswer()
        finally:
            self.httpAuthLock.release()
        return ret;

    def isScrapeAllowed(self, url):
        """Tell the user that URL wasn't a valid feed and ask if it should be
        scraped for links instead. Returns True if the user gives
        permission, or False if not."""
        summary = u"Channel is not compatible with %s!" % \
            (config.get(prefs.SHORT_APP_NAME), )
        message = u"But we'll try our best to grab the files. It may take extra time to list the videos, and descriptions may look funny.\n\nPlease contact the publishers of %s and ask if they can supply a feed in a format that will work with %s." % (url, config.get(prefs.SHORT_APP_NAME), )
        buttons = (u'Continue',)
        showWarningDialog(summary, message, buttons)
        return True

    def updateAvailable(self, url):
        """Tell the user that an update is available and ask them if they'd
        like to download it now"""
        summary = "%s Version Alert" % (config.get(prefs.SHORT_APP_NAME), )
        message = "A new version of %s is available. Would you like to download it now?" % (config.get(prefs.LONG_APP_NAME), )
        buttons = (u'Download', u'Cancel')
        result = showInformationalDialog(summary, message, buttons)
        if result == 0:
            self.openExternalURL(url)

    def dtvIsUpToDate(self):
        summary = u'%s Version Check' % (config.get(prefs.SHORT_APP_NAME), )
        message = u'%s is up to date.' % (config.get(prefs.LONG_APP_NAME), )
        showInformationalDialog(summary, message)

    def saveFailed(self, reason):
        summary = u'%s database save failed' % (config.get(prefs.SHORT_APP_NAME), )
        message = u"%s was unable to save its database.\nRecent changes may be lost\n\n%s" % (config.get(prefs.LONG_APP_NAME), reason)
        buttons = (u'Continue',)
        showCriticalDialog(summary, message, buttons)
        return True

    def validateFeedRemoval(self, feedTitle):
        summary = u'Remove Channel'
        message = u'Are you sure you want to remove the channel \'%s\'? This operation cannot be undone.' % feedTitle
        buttons = (u'Remove', u'Cancel')
        result = showCriticalDialog(summary, message, buttons)
        return (result == 0)

    def openExternalURL(self, url):
        # We could use Python's webbrowser.open() here, but
        # unfortunately, it doesn't have the same semantics under UNIX
        # as under other OSes. Sometimes it blocks, sometimes it doesn't.
        pool = NSAutoreleasePool.alloc().init()
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))
        del pool

    def updateAvailableItemsCountFeedback(self, count):
        pool = NSAutoreleasePool.alloc().init()
        appIcon = NSImage.imageNamed_('NSApplicationIcon')
        badgedIcon = NSImage.alloc().initWithSize_(appIcon.size())
        badgedIcon.lockFocus()
        try:
            appIcon.compositeToPoint_operation_((0,0), NSCompositeSourceOver)
            if count > 0:
                digits = len(str(count))
                badge = nil
                if digits <= 2:
                    badge = NSImage.imageNamed_('dock_badge_1_2.png')
                elif digits <= 5:
                    badge = NSImage.imageNamed_('dock_badge_%d.png' % digits)
                else:
                    print "DTV: Wow, that's a whole lot of new items!"
                if badge is not nil:
                    appIconSize = appIcon.size()
                    badgeSize = badge.size()
                    badgeLoc = (appIconSize.width - badgeSize.width, appIconSize.height - badgeSize.height)
                    badge.compositeToPoint_operation_(badgeLoc, NSCompositeSourceOver)
                    badgeLabel = NSString.stringWithString_(u'%d' % count)
                    badgeLabelFont = NSFont.boldSystemFontOfSize_(24)
                    badgeLabelColor = NSColor.whiteColor()
                    badgeParagraphStyle = NSMutableParagraphStyle.alloc().init()
                    badgeParagraphStyle.setAlignment_(NSCenterTextAlignment)
                    badgeLabelAttributes = {NSFontAttributeName: badgeLabelFont, 
                                            NSForegroundColorAttributeName: badgeLabelColor,
                                            NSParagraphStyleAttributeName: badgeParagraphStyle}
                    badgeLabelLoc = (badgeLoc[0], badgeLoc[1]-10)
                    badgeLabel.drawInRect_withAttributes_((badgeLabelLoc, badgeSize), badgeLabelAttributes)
        finally:
            badgedIcon.unlockFocus()
        NSApplication.sharedApplication().setApplicationIconImage_(badgedIcon)
        del pool
        
    def interruptDownloadsAtShutdown(self, downloadsCount):
        summary = u'Are you sure you want to quit?'
        message = u'You have %d download%s still in progress.' % (downloadsCount, downloadsCount > 1 and 's' or '')
        buttons = (u'Quit', u'Cancel')
        result = showWarningDialog(summary, message, buttons)
        return (result == 0)
        
    def notifyUnkownErrorOccurence(self, when, log = ''):
        controller = ExceptionReporterController.alloc().initWithMoment_log_(when, log)
        controller.showPanel()
        return True

    def copyTextToClipboard(self, text):
        print "WARNING: copyTextToClipboard not implemented"

    def killDownloadDaemon(self, oldpid):
        # Use UNIX style kill
        if oldpid is not None:
            try:
                os.kill(oldpid, signal.SIGTERM)
                sleep(1)
                os.kill(oldpid, signal.SIGKILL)
            except:
                pass

    def launchDownloadDaemon(self, oldpid, env):
        self.killDownloadDaemon(oldpid)

        print "DTV: Launching Download Daemon"
        pool = NSAutoreleasePool.alloc().init()
        
        bundle = NSBundle.mainBundle()
        pyexe = self.__findPythonExecutableInBundle(bundle)
        if pyexe is not None:
            import imp
            mfile, mpath, mdesc = imp.find_module('dl_daemon')
            daemonPrivatePath = os.path.join(mpath, 'private')
            pythonPath = list(sys.path)
            pythonPath[0:0] = [daemonPrivatePath]

            env['PYTHONPATH'] = ':'.join(pythonPath)
            env['BUNDLEPATH'] = bundle.bundlePath()
            env['RESOURCEPATH'] = bundle.resourcePath()
            env['BUNDLEIDENTIFIER'] = bundle.bundleIdentifier()
            env['DYLD_LIBRARY_PATH'] = os.path.join(bundle.bundlePath(), 'Contents', 'Frameworks')

            script = bundle.pathForResource_ofType_('Democracy_Downloader', 'py')

            task = NSTask.alloc().init()
            task.setLaunchPath_(pyexe)
            task.setArguments_([script])
            task.setEnvironment_(env)
            task.launch()
        else:
            print "DTV: WARNING! Unable to launch python subprocess for the downloader"
        
        del pool
        
    def __findPythonExecutableInBundle(self, bundle):
        info = bundle.infoDictionary()
        for location in info['PyRuntimeLocations']:
            if location.startswith('@executable_path'):
                location = location.replace('@executable_path', os.path.dirname(bundle.executablePath()))
            location = os.path.dirname(location)
            location = os.path.join(location, "bin", "python")
            location = os.path.normpath(location)
            if os.path.exists(location):
                return location
        return None

class ExceptionReporterController (NibClassBuilder.AutoBaseClass):
    
    def initWithMoment_log_(self, when, log):
        self = super(ExceptionReporterController, self).initWithWindowNibName_owner_("ExceptionReporterPanel", self)
        self.info = config.getAppConfig()
        self.info['when'] = when
        self.info['log'] = log
        return self
        
    def awakeFromNib(self):
        title = string.Template(self.window().title()).safe_substitute(self.info)
        msg1 = string.Template(self.msg1Field.stringValue()).safe_substitute(self.info)
        msg3 = string.Template(self.msg3View.string()).safe_substitute(self.info)
        nsmsg3 = NSString.stringWithString_(unicode(msg3))
        msg3Data = nsmsg3.dataUsingEncoding_(NSUTF8StringEncoding)
        (msg3, attrs) = NSAttributedString.alloc().initWithHTML_documentAttributes_(msg3Data)
        logmsg = string.Template(self.logView.string()).safe_substitute(self.info)

        self.window().setTitle_(title)
        self.msg1Field.setStringValue_(msg1)
        self.msg3View.setBackgroundColor_(NSColor.controlColor())
        self.msg3View.textContainer().setLineFragmentPadding_(0)
        self.msg3View.textStorage().setAttributedString_(msg3)
        self.logView.setString_(logmsg)
    
    def showPanel(self):
        NSApplication.sharedApplication().runModalForWindow_(self.window())
    
    def dismissPanel_(self, sender):
        self.window().close()
        NSApplication.sharedApplication().stopModal()
 
       
class PasswordController (NibClassBuilder.AutoBaseClass):

    def init(self, message, prefillUser = None, prefillPassword = None):
        pool = NSAutoreleasePool.alloc().init()
        # sets passwordField, textArea, usernameField, window
        NSBundle.loadNibNamed_owner_("PasswordWindow", self)

        self.usernameField.setStringValue_(prefillUser or "")
        self.passwordField.setStringValue_(prefillPassword or "")
        self.textArea.setStringValue_(message)
        self.result = None
        self.condition = threading.Condition()

        # Ensure we're not deallocated until the window that has actions
        # that point at us is closed
        self.retain()
        del pool
        return self

    def getAnswer(self):
        """Present the dialog and wait for user answer. Returns (username,
        password) if the user pressed OK, or None if the user pressed Cancel."""
        # PasswordController is likely to get release()d by Python in response
        # to getAnswer returning.
        self.performSelectorOnMainThread_withObject_waitUntilDone_("showAtModalLevel:", nil, NO)
        self.condition.acquire()
        self.condition.wait()
        self.condition.release()
        self.release()
        return self.result

    # executes in GUI thread
    def showAtModalLevel_(self, sender):
        self.window.setLevel_(NSModalPanelWindowLevel)
        self.window.makeKeyAndOrderFront_(nil)

    # bound to button in nib
    def acceptEntry_(self, sender):
        self.condition.acquire()
        self.result = (self.usernameField.stringValue(),
        self.passwordField.stringValue())
        self.window.close()
        self.condition.notify()
        self.condition.release()

    # bound to button in nib
    def cancelEntry_(self, sender):
        self.condition.acquire()
        self.result = None
        self.window.close()
        self.condition.notify()
        self.condition.release()


###############################################################################
#### The tab selector button class                                         ####
###############################################################################

class TabButtonCell (NibClassBuilder.AutoBaseClass):

    def awakeFromNib(self):
        self.background = NSImage.imageNamed_('tab')
        self.selectedBackground = NSImage.imageNamed_('tab_blue')

        pstyle = NSMutableParagraphStyle.alloc().init()
        pstyle.setAlignment_(NSCenterTextAlignment)
        self.titleAttrs = { NSFontAttributeName:NSFont.fontWithName_size_("Lucida Grande", 12),
                            NSParagraphStyleAttributeName:pstyle }

    def drawInteriorWithFrame_inView_(self, rect, view):
        image = self.background
        if self.state() == NSOnState:
            image = self.selectedBackground

        y = rect.origin.y
        if view.isFlipped():
            y += rect.size.height

        tileWidth = image.size().width
        times = math.ceil(rect.size.width / tileWidth)
        for i in range(0, int(times)):
            x = (rect.origin.x + (i * tileWidth), y)
            image.compositeToPoint_operation_(x, NSCompositeSourceOver)

        self.drawTitle(rect)

    def drawTitle(self, rect):
        r = rect
        r.origin.x += 8
        r.origin.y += 5
        r.size.width -= 16
        title = self.title()
        NSString.stringWithString_(title).drawInRect_withAttributes_( r, self.titleAttrs )


###############################################################################
#### Custom split view                                                     ####
###############################################################################

class DTVSplitView (NibClassBuilder.AutoBaseClass):
    
    def awakeFromNib(self):
        self.background = NSImage.imageNamed_('splitview_divider_background')
        self.backgroundRect = ((0,0), self.background.size())
        self.dimple = NSImage.imageNamed_('splitview_divider_dimple')
        
    def dividerThickness(self):
        return 10.0
        
    def drawDividerInRect_(self, rect):
        dividerOrigin = (rect.origin.x, 12)
        dividerSize = (rect.size.width, rect.size.height - 58 - 12)
        dividerRect = (dividerOrigin, dividerSize)
        self.background.drawInRect_fromRect_operation_fraction_(dividerRect, self.backgroundRect, NSCompositeSourceOver, 1.0)
        dimplePosition = (rect.origin.x, (dividerSize[1] - self.dimple.size().height) / 2)
        self.dimple.compositeToPoint_operation_(dimplePosition, NSCompositeSourceOver)


###############################################################################
#### Custom metal slider                                                   ####
###############################################################################

class MetalSlider (NibClassBuilder.AutoBaseClass):

    def awakeFromNib(self):
        oldCell = self.cell()
        newCell = MetalSliderCell.alloc().init()
        newCell.setState_(oldCell.state())
        newCell.setEnabled_(oldCell.isEnabled())
        newCell.setFloatValue_(oldCell.floatValue())
        newCell.setTarget_(oldCell.target())
        newCell.setAction_(oldCell.action())
        self.setCell_(newCell)


class MetalSliderCell (NSSliderCell):

    def init(self):
        self = super(MetalSliderCell, self).init()
        self.knob = NSImage.imageNamed_('volume_knob')
        self.knobPressed = NSImage.imageNamed_('volume_knob_blue')
        self.knobSize = self.knob.size()
        return self

    def knobRectFlipped_(self, flipped):
        value = self.floatValue()
        course = self.controlView().bounds().size.width - self.knobSize.width
        origin = NSPoint(course * value, 0)
        return ( origin, (self.knobSize.width, self.controlView().bounds().size.height) )

    def drawKnob_(self, rect):
        self.controlView().lockFocus()
        location = NSPoint(rect.origin.x, rect.origin.y + rect.size.height + 1)
        if self.isEnabled():
            self.knob.compositeToPoint_operation_(location, NSCompositeSourceOver)
        else:
            self.knob.dissolveToPoint_fraction_(location, 0.5)
        self.controlView().unlockFocus()


###############################################################################
#### The base class for all our custom sliders                             ####
###############################################################################

class Slider (NibClassBuilder.AutoBaseClass):

    def initWithFrame_(self, frame):
        self = super(Slider, self).initWithFrame_(frame)
        self.value = 0.0
        self.showCursor = False
        self.dragging = False
        self.sliderWasClicked = None
        self.sliderWasDragged = None
        self.sliderWasReleased = None
        return self

    def setFloatValue_(self, value):
        self.value = value
        self.setNeedsDisplay_(YES)
        
    def floatValue(self):
        return self.value

    def setShowCursor_(self, showCursor):
        self.showCursor = showCursor

    def drawRect_(self, rect):
        self.drawTrack()
        if self.showCursor:
            self.drawCursor()

    def drawTrack(self):
        pass

    def drawCursor(self):
        x = (self.bounds().size.width - self.cursor.size().width) * self.value
        self.cursor.compositeToPoint_operation_((abs(x)+0.5, 0), NSCompositeSourceOver)

    def mouseDown_(self, event):
        if self.showCursor:
            location = self.convertPoint_fromView_(event.locationInWindow(), nil)
            if NSPointInRect(location, self.bounds()):
                self.dragging = True
                self.setFloatValue_(self.getValueForClickLocation(location))
                if self.sliderWasClicked is not None:
                    self.sliderWasClicked(self)

    def mouseDragged_(self, event):
        if self.showCursor and self.dragging:
            location = self.convertPoint_fromView_(event.locationInWindow(), nil)
            self.setFloatValue_(self.getValueForClickLocation(location))
            if self.sliderWasDragged is not None:
                self.sliderWasDragged(self)

    def mouseUp_(self, event):
        if self.showCursor:
            self.dragging = False
            if self.sliderWasReleased is not None:
                self.sliderWasReleased(self)
            self.setNeedsDisplay_(YES)

    def getValueForClickLocation(self, location):
        min = self.cursor.size().width / 2.0
        max = self.bounds().size.width - min
        span = max - min
        offset = location.x
        if offset < min:
            offset = min
        elif offset > max:
            offset = max
        return (offset - min) / span


###############################################################################
#### The progress display                                                  ####
###############################################################################

class ProgressDisplayView (NibClassBuilder.AutoBaseClass):

    def awakeFromNib(self):
        self.progressSlider.sliderWasClicked = self.progressSliderWasClicked
        self.progressSlider.sliderWasDragged = self.progressSliderWasDragged
        self.progressSlider.sliderWasReleased = self.progressSliderWasReleased
        self.backgroundLeft = NSImage.imageNamed_( "display_left" )
        self.backgroundLeftWidth = self.backgroundLeft.size().width
        self.backgroundRight = NSImage.imageNamed_( "display_right" )
        self.backgroundRightWidth = self.backgroundRight.size().width
        self.backgroundCenter = NSImage.imageNamed_( "display_center" )
        self.backgroundCenterWidth = self.backgroundCenter.size().width
        self.renderer = None
        self.updateTimer = nil
        self.wasPlaying = False

    @platformutils.onMainThread
    def setup(self, renderer):
        if self.renderer != renderer:
            self.renderer = renderer
            if renderer is not nil:
                self.updateTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(1.0, self, 'refresh:', nil, YES)
                NSRunLoop.currentRunLoop().addTimer_forMode_(self.updateTimer, NSEventTrackingRunLoopMode)
            elif self.updateTimer is not nil:
                self.updateTimer.invalidate()
                self.updateTimer = nil
        self.refresh_(nil)
        self.setNeedsDisplay_(YES)

    def teardown(self):
        self.setup(None)

    def refresh_(self, timer):
        if self.renderer is not None:
            self.progressSlider.setShowCursor_(True)
            self.progressSlider.setFloatValue_(self.renderer.getProgress())
            self.timeIndicator.setStringValue_(self.renderer.getDisplayTime())
        else:
            self.progressSlider.setShowCursor_(False)
            self.progressSlider.setFloatValue_(0.0)
            self.timeIndicator.setStringValue_(app.VideoRenderer.DEFAULT_DISPLAY_TIME)

    def drawRect_(self, rect):
        self.backgroundLeft.compositeToPoint_operation_( (0,0), NSCompositeSourceOver )
        x = self.bounds().size.width - self.backgroundRightWidth
        self.backgroundRight.compositeToPoint_operation_( (x, 0), NSCompositeSourceOver )
        emptyWidth = self.bounds().size.width - (self.backgroundRightWidth + self.backgroundLeftWidth)
        emptyRect = ((self.backgroundLeftWidth, 0), (emptyWidth, self.bounds().size.height))
        NSGraphicsContext.currentContext().saveGraphicsState()
        NSBezierPath.clipRect_(emptyRect)
        tiles = math.ceil(emptyWidth / float(self.backgroundCenterWidth))
        for i in range(0, int(tiles)):
            x = self.backgroundLeftWidth + (i * self.backgroundCenterWidth)
            self.backgroundCenter.compositeToPoint_operation_( (x, 0), NSCompositeSourceOver )
        NSGraphicsContext.currentContext().restoreGraphicsState()

    def progressSliderWasClicked(self, slider):
        if app.controller.videoDisplay.isPlaying:
            self.wasPlaying = True
            self.renderer.pause()
        self.renderer.setProgress(slider.floatValue())
        self.renderer.interactivelySeeking = True
        self.refresh_(nil)
        
    def progressSliderWasDragged(self, slider):
        self.renderer.setProgress(slider.floatValue())
        self.refresh_(nil)
        
    def progressSliderWasReleased(self, slider):
        self.renderer.interactivelySeeking = False
        if self.wasPlaying:
            self.wasPlaying = False
            self.renderer.play()

    
###############################################################################
#### The progress display progress slider                                  ####
###############################################################################

class ProgressSlider (NibClassBuilder.AutoBaseClass):
    
    def initWithFrame_(self, frame):
        self = super(ProgressSlider, self).initWithFrame_(frame)
        self.grooveContourColor = NSColor.colorWithCalibratedWhite_alpha_( 0.1, 0.3 )
        self.grooveFillColor = NSColor.colorWithCalibratedWhite_alpha_( 0.5, 0.3 )
        self.cursor = NSImage.alloc().initWithSize_((10,10))
        self.cursor.lockFocus()
        path = NSBezierPath.bezierPath()
        path.moveToPoint_((0, 4.5))
        path.lineToPoint_((4, 8))
        path.lineToPoint_((8, 4.5))
        path.lineToPoint_((4, 1))
        path.closePath()
        NSColor.colorWithCalibratedWhite_alpha_( 51/255.0, 1.0 ).set()
        path.fill()
        self.cursor.unlockFocus()
        return self
                
    def drawTrack(self):
        rect = self.bounds()
        rect = NSOffsetRect(rect, 0.5, 0.5)
        rect.size.width -= 1
        rect.size.height -= 1
        self.grooveFillColor.set()
        NSBezierPath.fillRect_(rect)
        self.grooveContourColor.set()
        NSBezierPath.strokeRect_(rect)        


###############################################################################
#### An empty display                                                      ####
###############################################################################

class NullDisplay (app.Display):
    "Represents an empty right-hand area."

    def __init__(self):
        pool = NSAutoreleasePool.alloc().init()
        # NEEDS: take (and leak) a covering reference -- cargo cult programming
        self.view = WebView.alloc().init().retain()
        self.view.setCustomUserAgent_("%s/%s (%s)" % \
                                      (config.get(prefs.SHORT_APP_NAME),
                                       config.get(prefs.APP_VERSION),
                                       config.get(prefs.PROJECT_URL),))
        app.Display.__init__(self)
        del pool

    def getView(self):
        return self.view


###############################################################################
#### Right-hand pane HTML display                                          ####
###############################################################################

class HTMLDisplay (app.Display):
    "HTML browser that can be shown in a MainFrame's right-hand pane."

#    sharedWebView = None

    # We don't need to override onSelected, onDeselected

    def __init__(self, html, existingView=None, frameHint=None, areaHint=None, baseURL=None):
        """'html' is the initial contents of the display, as a string. If
        frameHint is provided, it is used to guess the initial size the HTML
        display will be rendered at, which might reduce flicker when the
        display is installed."""
        pool = NSAutoreleasePool.alloc().init()
        self.readyToDisplayHook = None
        self.readyToDisplay = False

        self.web = ManagedWebView.alloc().init(html, None, self.nowReadyToDisplay, lambda x:self.onURLLoad(x), frameHint and areaHint and frameHint.getDisplaySizeHint(areaHint) or None, baseURL)

        app.Display.__init__(self)
        del pool

    def getEventCookie(self):
        return ''
    def getDTVPlatformName(self):
        return 'webkit'

    def getView(self):
        return self.web.getView()

    def execJS(self, js):
        """Execute the given Javascript code (provided as a string) in the
        context of this HTML document."""
        try:
            self.web.execJS(js)
        except AttributeError:
            print "Couldn't exec javascript! Web view not initialized"
        #print "DISP: %s with %s" % (self.view, js)

    # DOM hooks used by the dynamic template code -- do they need a 
    # try..except wrapper like the above?
    def addItemAtEnd(self, xml, id):
        return self.web.addItemAtEnd(xml, id)
    def addItemBefore(self, xml, id):
        return self.web.addItemBefore(xml, id)
    def removeItem(self, id):
        return self.web.removeItem(id)
    def changeItem(self, id, xml):
        return self.web.changeItem(id, xml)
    def hideItem(self, id):
        return self.web.hideItem(id)
    def showItem(self, id):
        return self.web.showItem(id)

    def onURLLoad(self, url):
        """Called when this HTML browser attempts to load a URL (either
        through user action or Javascript.) The URL is provided as a
        string. Return true to allow the URL to load, or false to cancel
        the load (for example, because it was a magic URL that marks
        an item to be downloaded.) Implementation in HTMLDisplay always
        returns true; override in a subclass to implement special
        behavior."""
        # For overriding
        pass

    def callWhenReadyToDisplay(self, hook):
        # NEEDS: lock?
        if self.readyToDisplay:
            hook()
        else:
            assert self.readyToDisplayHook == None
            self.readyToDisplayHook = hook

    # Called (via callback established in constructor)
    def nowReadyToDisplay(self):
        self.readyToDisplay = True
        if self.readyToDisplayHook:
            hook = self.readyToDisplayHook
            self.readyToDisplayHook = None
            hook()

    def unlink(self):
        webView = self.web.getView()
        if webView is not nil:
            webView.setHostWindow_(self.currentFrame.obj.window()) # not very pretty
    
    def cancel(self):
        print "DTV: Canceling load of WebView %s" % self.web.getView()
        platformutils.callOnMainThread(self.web.getView().stopLoading_, nil)
        self.readyToDisplay = False
        self.readyToDisplayHook = None
                        

###############################################################################
#### An enhanced WebView Wrapper                                           ####
###############################################################################

class ManagedWebView (NSObject):

    def init(self, initialHTML, existingView=nil, onInitialLoadFinished=None, onLoadURL=None, sizeHint=None, baseURL=None):
        self.onInitialLoadFinished = onInitialLoadFinished
        self.onLoadURL = onLoadURL
        self.initialLoadFinished = False
        self.view = existingView
        platformutils.callOnMainThreadAndWaitUntilDone(self.initWebView, initialHTML, sizeHint, baseURL)        
        return self

    def initWebView(self, initialHTML, sizeHint, baseURL):
        if not self.view:
            self.view = WebView.alloc().init()
            #print "***** Creating new WebView %s" % self.view
            if sizeHint:
                # We have an estimate of the size that will be assigned to
                # the view when it is actually inserted in the MainFrame.
                # Use this to size the view we just created so the HTML
                # is hopefully rendered to the correct dimensions, instead
                # of having to be corrected after being displayed.
                self.view.setFrame_(sizeHint)
            self.view.setCustomUserAgent_("%s/%s (%s)" % \
                                          (config.get(prefs.SHORT_APP_NAME),
                                           config.get(prefs.APP_VERSION),
                                           config.get(prefs.PROJECT_URL),))
        else:
            #print "***** Using existing WebView %s" % self.view
            if sizeHint:
                self.view.setFrame_(sizeHint)
        self.execQueue = []
        self.view.setPolicyDelegate_(self)
        self.view.setResourceLoadDelegate_(self)
        self.view.setFrameLoadDelegate_(self)
        self.view.setUIDelegate_(self)

        html = NSString.stringWithString_(unicode(initialHTML))
        data = html.dataUsingEncoding_(NSUTF8StringEncoding)
        if baseURL is not None:
            baseURL = NSURL.URLWithString_(baseURL)

        self.view.mainFrame().loadData_MIMEType_textEncodingName_baseURL_(data, 'text/html', 'utf-8', baseURL)        

    def isKeyExcludedFromWebScript_(self,key):
        return YES

    def isSelectorExcludedFromWebScript_(self,sel):
        if (str(sel) == 'eventURL'):
            return NO
        else:
            return YES

    def eventURL(self,url):
        self.onLoadURL(str(url))

    ##
    # Create CTRL-click menu on the fly
    def webView_contextMenuItemsForElement_defaultMenuItems_(self,webView,contextMenu,defaultMenuItems):
        platformutils.warnIfNotOnMainThread("webView_contextMenuItemsForElement_defaultMenuItems_")
        menuItems = []
        if self.initialLoadFinished:
            exists = webView.windowScriptObject().evaluateWebScript_("typeof(getContextClickMenu)") == "function"
            if exists:
                x = webView.windowScriptObject().callWebScriptMethod_withArguments_("getContextClickMenu",[contextMenu['WebElementDOMNode']])
                if len(x) > 0:
                    # getContextClickMenu returns a string with one menu
                    # item on each line in the format
                    # "URL|description" Blank lines are separators
                    for menuEntry in x.split("\n"):
                        menuEntry = menuEntry.strip()
                        if len(menuEntry) == 0:
                            menuItems.append(NSMenuItem.separatorItem())
                        else:
                            (url, name) = menuEntry.split('|',1)
                            menuItem = NSMenuItem.alloc()
                            menuItem.initWithTitle_action_keyEquivalent_(name,self.processContextClick_,"")
                            menuItem.setEnabled_(YES)
                            menuItem.setRepresentedObject_(url)
                            menuItem.setTarget_(self)
                            menuItems.append(menuItem)
        return menuItems

    # Generate callbacks when the initial HTML (passed in the constructor)
    # has been loaded
    def webView_didFinishLoadForFrame_(self, webview, frame):
        if (not self.initialLoadFinished) and (frame is self.view.mainFrame()):
            # Execute any function calls we queued because the page load
            # hadn't completed
            # NEEDS: there should be a lock here, preventing execAfterLoad
            # from dropping something in the queue just after we have finished
            # processing it
            for func in self.execQueue:
                platformutils.callOnMainThreadAndWaitUntilDone(func)
            self.execQueue = []
            self.initialLoadFinished = True

            if self.onInitialLoadFinished:
                self.onInitialLoadFinished()

            scriptObj = self.view.windowScriptObject()
            scriptObj.setValue_forKey_(self,'frontend')

    # Intercept navigation actions and give program a chance to respond
    def webView_decidePolicyForNavigationAction_request_frame_decisionListener_(self, webview, action, request, frame, listener):
        method = request.HTTPMethod()
        url = request.URL()
        body = request.HTTPBody()
        type = action['WebActionNavigationTypeKey']
        #print "policy %d for url %s" % (type, url)
        # setting document.location.href in Javascript (our preferred
        # method of triggering an action) comes out as an
        # WebNavigationTypeOther.
        if type == WebNavigationTypeLinkClicked or type == WebNavigationTypeFormSubmitted or type == WebNavigationTypeOther:
            # Make sure we have a real, bona fide Python string, not an
            # NSString. Unfortunately, == can tell the difference.
            if (not self.onLoadURL) or self.onLoadURL('%s' % url):
                listener.use()
            else:
                listener.ignore()
        else:
            listener.use()

    # Redirect resource: links to files in resource bundle
    def webView_resource_willSendRequest_redirectResponse_fromDataSource_(self, webview, resourceCookie, request, redirectResponse, dataSource):
        url = "%s" % request.URL() # Make sure it's a Python string
        match = re.compile("resource:(.*)$").match(url)
        if match:
            path = resource.path(match.group(1))
            urlObject = NSURL.fileURLWithPath_(path)
            return NSURLRequest.requestWithURL_(urlObject)
        return request

    ##
    # Process a click on an item in a context menu
    def processContextClick_(self,item):
        self.execJS("document.location.href = \""+item.representedObject()+"\";")

    # Return the actual WebView that we're managing
    def getView(self):
        return self.view

    # Call func() once the document has finished loading. If the
    # document has already finished loading, call it right away. But
    # in either case, the call is executed on the main thread, by
    # queueing an event, since WebViews are not documented to be
    # thread-safe, and we have seen crashes.
    def execAfterLoad(self, func):
        if not self.initialLoadFinished:
            self.execQueue.append(func)
        else:
            platformutils.callOnMainThread(func)

    # Decorator to make using execAfterLoad easier
    def deferUntilAfterLoad(func):
        def runFunc(*args, **kwargs):
            func(*args, **kwargs)
        def schedFunc(self, *args, **kwargs):
            rf = lambda: runFunc(self, *args, **kwargs)
            self.execAfterLoad(rf)
        return schedFunc

    # Execute given Javascript string in context of the HTML document
    @deferUntilAfterLoad
    def execJS(self, js):
        self.view.stringByEvaluatingJavaScriptFromString_(js)

    ## DOM mutators called, ultimately, by dynamic template system ##

    def findElt(self, id):
        doc = self.view.mainFrame().DOMDocument()
        elt = doc.getElementById_(id)
        return elt

#     def printHTML(self):
#         print
#         print "--- Document HTML ---"
#         print self.view.mainFrame().DOMDocument().body().outerHTML()
#         print "--- End Document HTML ---"

    def createElt(self, xml):
        parent = self.view.mainFrame().DOMDocument().createElement_("div")
        if len(xml) == 0:
            #FIXME: this is awfully ugly but it fixes the symptoms described
            #in #1664. Next step is to fix the root cause.
            parent.setInnerHTML_("<div style='height: 1px;'/>")
        else:
            parent.setInnerHTML_(xml)
        #FIXME: This is a bit of a hack. Since, we only deal with
        # multiple elements on initialFillIn, it should be fine for now
        if parent.childNodes().length() > 1:
            eltlist = []
            for child in range(parent.childNodes().length()):
                eltlist.append(parent.childNodes().item_(child))
            return eltlist
        else:
            return parent.firstChild()
        
    @deferUntilAfterLoad
    def addItemAtEnd(self, xml, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: addItemAtEnd: missing element %s" % id
        else:
            #print "add item %s at end of %s" % (elt.getAttribute_("id"), id)
            #print xml[0:79]
            elt.insertBefore__(self.createElt(xml), None)

    @deferUntilAfterLoad
    def addItemBefore(self, xml, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: addItemBefore: missing element %s" % id
        else:
            newelts = self.createElt(xml)
            try:
                for newelt in newelts:
                    #print "add item %s before %s" % (newelt.getAttribute_("id"), id)
                    elt.parentNode().insertBefore__(newelt, elt)
            except:
                #print "add item %s before %s" % (newelts, id)
                elt.parentNode().insertBefore__(newelts, elt)

    @deferUntilAfterLoad
    def removeItem(self, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: removeItem: missing element %s" % id
        else:
            #print "remove item %s" % id
            elt.parentNode().removeChild_(elt)

    @deferUntilAfterLoad
    def changeItem(self, id, xml):
        elt = self.findElt(id)
        if not elt:
            print "warning: changeItem: missing element %s" % id
        else:
            #print "change item %s (new id %s)" % (id, elt.getAttribute_("id"))
            #print xml[0:79]
            #if id != elt.getAttribute_("id"):
            #    raise Exception
            #elt = self.findElt(id)
            #if not elt:
            #    print "ERROR ELEMENT LOST %s" % id
            elt.setOuterHTML_(xml)

    @deferUntilAfterLoad
    def hideItem(self, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: hideItem: missing element %s" % id
        else:
            #print "hide item %s (new style '%s')" % (id, elt.getAttribute_("style"))
            elt.setAttribute__("style", "display:none")

    @deferUntilAfterLoad
    def showItem(self, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: showItem: missing element %s" % id
        else:
            #print "show item %s (new style '%s')" % (id, elt.getAttribute_("style"))
            elt.setAttribute__("style", "")


###############################################################################
#### The Playback Controller                                               ####
###############################################################################

class PlaybackController (app.PlaybackControllerBase):
    
    def playItemExternally(self, itemID):
        item = app.PlaybackControllerBase.playItemExternally(self, itemID)
        moviePath = item.getPath()
        ok = NSWorkspace.sharedWorkspace().openFile_withApplication_andDeactivate_(moviePath, nil, YES)
        if not ok:
            print "DTV: movie %s could not be externally opened" % moviePath
 

###############################################################################
#### Right-hand pane video display                                         ####
###############################################################################

class VideoDisplay (app.VideoDisplayBase):
    "Video player shown in a MainFrame's right-hand pane."

    def __init__(self):
        app.VideoDisplayBase.__init__(self)
        self.controller = VideoDisplayController.getInstance()
        self.controller.videoDisplay = self

    def initRenderers(self):
        self.renderers.append(QuicktimeRenderer(self.controller))

    def selectItem(self, item, renderer):
        app.VideoDisplayBase.selectItem(self, item, renderer)
        self.controller.selectItem(item, renderer)
 
    def play(self):
        app.VideoDisplayBase.play(self)
        self.controller.play()

    def pause(self):
        app.VideoDisplayBase.pause(self)
        self.controller.pause()

    def stop(self):
        app.VideoDisplayBase.stop(self)
        self.controller.stop()
    
    def goFullScreen(self):
        app.VideoDisplayBase.goFullScreen(self)
        self.controller.goFullScreen()

    def exitFullScreen(self):
        app.VideoDisplayBase.exitFullScreen(self)
        self.controller.exitFullScreen()

    def setVolume(self, level):
        app.VideoDisplayBase.setVolume(self, level)
        self.controller.setVolume(level)

    def muteVolume(self):
        app.VideoDisplayBase.muteVolume(self)
        self.controller.volumeSlider.setEnabled_(NO)

    def restoreVolume(self):
        app.VideoDisplayBase.restoreVolume(self)
        self.controller.volumeSlider.setEnabled_(YES)

    def onSelected(self, frame):
        app.VideoDisplayBase.onSelected(self, frame)
        self.controller.onSelected()

    def onDeselected(self, frame):
        app.VideoDisplayBase.onDeselected(self, frame)
        self.controller.onDeselected()

    def getView(self):
        return self.controller.rootView


###############################################################################
#### The video display controller object, instantiated from the nib file   ####
###############################################################################

class VideoDisplayController (NibClassBuilder.AutoBaseClass):

    _instance = nil

    @classmethod
    def getInstance(self):
        assert VideoDisplayController._instance is not nil
        return VideoDisplayController._instance

    def awakeFromNib(self):
        VideoDisplayController._instance = self
        self.forwardButton.sendActionOn_(NSLeftMouseDownMask)
        self.backwardButton.sendActionOn_(NSLeftMouseDownMask)
        nc.addObserver_selector_name_object_(
            self, 
            'handleWatchableDisplayNotification:', 
            'displayIsWatchable', 
            nil)
        nc.addObserver_selector_name_object_(
            self, 
            'handleNonWatchableDisplayNotification:', 
            'displayIsNotWatchable', 
            nil)
        self.systemActivityUpdaterTimer = nil
        self.reset()

    def onSelected(self):
        self.enableSecondaryControls(YES)
        self.preventSystemSleep(True)

    def onDeselected(self):
        self.enableSecondaryControls(NO)
        self.preventSystemSleep(False)
        self.videoAreaView.teardown()
        self.progressDisplayer.teardown()
        self.reset()

    def selectItem(self, item, renderer):
        self.videoAreaView.setup(item, renderer)
        self.progressDisplayer.setup(renderer)

    def reset(self):
        self.currentWatchableDisplay = None
        self.fastSeekTimer = nil

    def preventSystemSleep(self, prevent):
        if prevent and self.systemActivityUpdaterTimer is nil:
            print "DTV: Launching system activity updater timer"
            self.systemActivityUpdaterTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(30, self, 'updateSystemActivity:', nil, YES)
        elif self.systemActivityUpdaterTimer is not nil:
            print "DTV: Stopping system activity updater timer"
            self.systemActivityUpdaterTimer.invalidate()
            self.systemActivityUpdaterTimer = nil

    def updateSystemActivity_(self, timer):
        UpdateSystemActivity(OverallAct)

    def enablePrimaryControls(self, enabled):
        self.playPauseButton.setEnabled_(enabled)
        self.fullscreenButton.setEnabled_(enabled)
        self.muteButton.setEnabled_(enabled)
        self.volumeSlider.setEnabled_(enabled and self.muteButton.state() is NSOnState)

    def enableSecondaryControls(self, enabled, allowFastSeeking=YES):
        self.backwardButton.setEnabled_(enabled)
        self.stopButton.setEnabled_(enabled)
        self.forwardButton.setEnabled_(enabled)
        if allowFastSeeking:
            self.backwardButton.setAction_('backward:')
            self.forwardButton.setAction_('forward:')
        else:
            self.backwardButton.setAction_('skipBackward:')
            self.forwardButton.setAction_('skipForward:')

    def updatePlayPauseButton(self, prefix):
        self.playPauseButton.setImage_(NSImage.imageNamed_('%s' % prefix))
        self.playPauseButton.setAlternateImage_(NSImage.imageNamed_('%s_blue' % prefix))

    def playPause_(self, sender):
        app.controller.playbackController.playPause()

    def play(self):
        nc.postNotificationName_object_('videoWillPlay', nil)
        self.enablePrimaryControls(YES)
        self.enableSecondaryControls(YES)
        self.updatePlayPauseButton('pause')

    def pause(self):
        nc.postNotificationName_object_('videoWillPause', nil)
        self.updatePlayPauseButton('play')

    def stop_(self, sender):
        eventloop.addUrgentCall(lambda:app.controller.playbackController.stop(), "Stop Video")
    
    def stop(self):
        nc.postNotificationName_object_('videoWillStop', nil)
        self.updatePlayPauseButton('play')

    def playFullScreen_(self, sender):
        if not app.controller.videoDisplay.isPlaying:
            app.controller.playbackController.playPause()
        self.videoDisplay.goFullScreen()

    def goFullScreen(self):
        self.videoAreaView.enterFullScreen()

    def exitFullScreen_(self, sender):
        self.exitFullScreen()

    def exitFullScreen(self):
        self.videoAreaView.exitFullScreen()

    def forward_(self, sender):
        eventloop.addUrgentCall(lambda:self.performSeek(sender, 1), "Forward")
        
    def skipForward_(self, sender):
        eventloop.addUrgentCall(lambda:app.controller.playbackController.skip(1), "Skip Forward")

    def fastForward_(self, sender):
        self.performSeek(sender, 1, 0.0)

    def backward_(self, sender):
        eventloop.addUrgentCall(lambda:self.performSeek(sender, -1), "Backward")

    def skipBackward_(self, sender):
        eventloop.addUrgentCall(lambda:app.controller.playbackController.skip(-1), "Skip Backward")

    def fastBackward_(self, sender):
        self.performSeek(sender, -1, 0.0)

    def performSeek(self, sender, direction, seekDelay=0.5):
        if sender.state() == NSOnState:
            sender.sendActionOn_(NSLeftMouseUpMask)
            if seekDelay > 0.0:
                info = {'seekDirection': direction}
                self.fastSeekTimer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(seekDelay, self, 'fastSeek:', info, NO)
                self.scheduleFastSeek(self.fastSeekTimer)
            else:
                self.fastSeekTimer = nil
                self.fastSeek(direction)
        else:
            sender.sendActionOn_(NSLeftMouseDownMask)
            if self.fastSeekTimer is nil:
                rate = 1.0
                if not self.videoDisplay.isPlaying:
                    rate = 0.0
                    self.updatePlayPauseButton('play')
                if self.videoDisplay.activeRenderer is not None:
                    self.videoDisplay.activeRenderer.setRate(rate)
            else:
                self.fastSeekTimer.invalidate()
                self.fastSeekTimer = nil
                app.controller.playbackController.skip(direction)

    @platformutils.onMainThread
    def scheduleFastSeek(self, timer):
        platformutils.warnIfNotOnMainThread('scheduleFastSeek')
        NSRunLoop.currentRunLoop().addTimer_forMode_(timer, NSEventTrackingRunLoopMode)

    def fastSeek_(self, timer):
        info = timer.userInfo()
        direction = info['seekDirection']
        self.fastSeek(direction)

    def fastSeek(self, direction):
        if not self.videoDisplay.isPlaying:
            self.updatePlayPauseButton('pause')
        rate = 3 * direction
        self.videoDisplay.activeRenderer.setRate(rate)
        self.fastSeekTimer = nil

    def setVolume_(self, sender):
        self.videoDisplay.setVolume(sender.floatValue())

    def setVolume(self, level):
        if self.muteButton.state() == NSOnState:
            self.volumeSlider.setFloatValue_(level)

    def muteUnmuteVolume_(self, sender):
        if sender.state() is NSOffState:
            self.videoDisplay.muteVolume()
        else:
            self.videoDisplay.restoreVolume()

    def handleWatchableDisplayNotification_(self, notification):
        self.enablePrimaryControls(YES)
        self.enableSecondaryControls(NO)
        info = notification.userInfo()
        view = info['view']
        app.controller.playbackController.configure(view)

    def handleNonWatchableDisplayNotification_(self, notification):
        self.enablePrimaryControls(NO)
        display = notification.object()
        if hasattr(display, 'templateName') and display.templateName.startswith('external-playback'):
            self.enableSecondaryControls(YES, NO)
    
    def handleMovieNotification_(self, notification):
        renderer = self.videoDisplay.activeRenderer
        if notification.name() == QTMovieDidEndNotification and not renderer.interactivelySeeking:
            app.controller.playbackController.onMovieFinished()


###############################################################################
#### The "dummy" video area. The actual video display will happen in a     ####
#### child VideoWindow window. This allows to have a single movie view for ####
#### both windowed and fullscreen playback                                 ####
###############################################################################

class VideoAreaView (NibClassBuilder.AutoBaseClass):
    
    def setup(self, item, renderer):
        if not self.videoWindow.isFullScreen:
            self.adjustVideoWindowFrame()
        self.videoWindow.setup(renderer, item)
        platformutils.callOnMainThreadAndWaitUntilDone(self.activateVideoWindow)

    def activateVideoWindow(self):
        self.videoWindow.orderFront_(nil)
        if self.videoWindow.parentWindow() is nil:
            self.window().addChildWindow_ordered_(self.videoWindow, NSWindowAbove)
    
    def drawRect_(self, rect):
        NSColor.blackColor().set()
        NSRectFill(rect)
    
    def teardown(self):
        if self.videoWindow.isFullScreen:
            self.videoWindow.exitFullScreen()
        self.window().removeChildWindow_(self.videoWindow)
        self.videoWindow.orderOut_(nil)
        self.videoWindow.teardown()
    
    def adjustVideoWindowFrame(self):
        if self.window() is nil:
            return
        frame = self.frame()
        frame.origin = self.convertPoint_toView_(NSZeroPoint, nil)
        frame.origin = self.window().convertBaseToScreen_(frame.origin)
        self.videoWindow.setFrame_display_(frame, YES)
        
    def setFrame_(self, frame):
        super(VideoAreaView, self).setFrame_(frame)
        self.adjustVideoWindowFrame()
    
    def enterFullScreen(self):
        self.adjustVideoWindowFrame()
        if self.window() is not nil:
            self.videoWindow.enterFullScreen(self.window().screen())
            self.window().removeChildWindow_(self.videoWindow)
            self.window().orderOut_(nil)

    def exitFullScreen(self):
        if self.videoWindow.isFullScreen:
            self.window().addChildWindow_ordered_(self.videoWindow, NSWindowAbove)
            self.window().makeKeyAndOrderFront_(nil)
            self.videoWindow.exitFullScreen()
    

###############################################################################
#### The video window, used to display the movies in both windowed and     ####
#### fullscreen modes.                                                     ####
###############################################################################

class VideoWindow (NibClassBuilder.AutoBaseClass):
    
    def initWithContentRect_styleMask_backing_defer_(self, rect, style, backing, defer):
        self = super(VideoWindow, self).initWithContentRect_styleMask_backing_defer_(
            rect,
            NSBorderlessWindowMask,
            backing,
            defer )
        self.setAcceptsMouseMovedEvents_(YES)
        self.setBackgroundColor_(NSColor.blackColor())
        self.isFullScreen = NO
        return self

    def setup(self, renderer, item):
        if self.contentView() != renderer.view:
            self.setContentView_(renderer.view)
        self.palette.setup(item, renderer)
        if self.isFullScreen:
            platformUtils.callOnMainThreadAfterDelay(0.5, self.palette.reveal, self)
    
    def teardown(self):
        self.setContentView_(nil)

    def canBecomeMainWindow(self):
        return self.isFullScreen
    
    def canBecomeKeyWindow(self):
        return self.isFullScreen

    def enterFullScreen(self, screen):
        SetSystemUIMode(kUIModeAllHidden, 0)
        NSCursor.setHiddenUntilMouseMoves_(YES)
        self.isFullScreen = YES
        self.previousFrame = self.frame()
        self.setFrame_display_animate_(screen.frame(), YES, YES)
        self.makeKeyAndOrderFront_(nil)

    def exitFullScreen(self):
        NSCursor.setHiddenUntilMouseMoves_(NO)
        self.isFullScreen = NO
        self.palette.remove()
        self.setFrame_display_animate_(self.previousFrame, YES, YES)
        SetSystemUIMode(kUIModeNormal, 0)
        
    def sendEvent_(self, event):
        if self.isFullScreen:
            if event.type() == NSLeftMouseDown:
                if NSApplication.sharedApplication().isActive():
                    app.controller.videoDisplay.exitFullScreen()
                else:
                    NSApplication.sharedApplication().activateIgnoringOtherApps_(YES)
            elif event.type() == NSKeyDown:
                if event.characters().characterAtIndex_(0) == 0x1B:
                    app.controller.videoDisplay.exitFullScreen()
                elif event.characters().characterAtIndex_(0) == 0x20:
                    app.controller.playbackController.playPause()
            elif event.type() == NSMouseMoved:
                if not self.palette.isVisible():
                    self.palette.reveal(self)
                else:
                    self.palette.resetAutoConceal()
        else:
            if event.type() == NSLeftMouseDown:
                if NSApplication.sharedApplication().isActive():
                    app.controller.videoDisplay.goFullScreen()
                else:
                    NSApplication.sharedApplication().activateIgnoringOtherApps_(YES)


###############################################################################
#### Quicktime video renderer                                              ####
###############################################################################

class QuicktimeRenderer (app.VideoRenderer):

    POSSIBLY_SUPPORTED_EXT = ('.wmv', '.avi', '.asf')
    UNSUPPORTED_EXT = ('.ram', '.rm', '.rpm', '.rv', '.ra')
    CORRECT_QTMEDIA_TYPES = (QTMediaTypeVideo, QTMediaTypeMPEG, QTMediaTypeMovie)

    def __init__(self, delegate):
        app.VideoRenderer.__init__(self)
        self.view = QTMovieView.alloc().initWithFrame_(((0,0),(100,100)))
        self.view.setFillColor_(NSColor.blackColor())
        self.view.setControllerVisible_(NO)
        self.view.setEditable_(NO)
        self.view.setPreservesAspectRatio_(YES)
        self.delegate = delegate
        self.cachedMovie = nil

    @platformutils.onMainThread
    def registerMovieObserver(self, movie):
        nc.addObserver_selector_name_object_(self.delegate, 'handleMovieNotification:', QTMovieDidEndNotification, movie)

    @platformutils.onMainThread
    def unregisterMovieObserver(self, movie):
        nc.removeObserver_name_object_(self.delegate, QTMovieDidEndNotification, movie)

    def reset(self):
        self.unregisterMovieObserver(self.view.movie())
        self.view.setMovie_(nil)
        self.cachedMovie = nil

    @platformutils.onMainThreadWithReturn
    def canPlayItem(self, item):
        canPlay = False
        pathname = item.getPath()
        if self.cachedMovie is not nil and self.cachedMovie.attributeForKey_(QTMovieFileNameAttribute) == pathname:
            qtmovie = self.cachedMovie
        else:
            (qtmovie, error) = QTMovie.alloc().initWithFile_error_(pathname)
            self.cachedMovie = qtmovie

        # Purely referential movies have a no duration, no track and need to be 
        # streamed first. Since we don't support this yet, we delegate the 
        # streaming to the standalone QT player to avoid any problem (like the 
        # crash in #944) by simply declaring that we can't play the corresponding item.
        # Note that once the movie is fully streamed and cached by QT, DTV will
        # be able to play it internally just fine -- luc
        
        # [UPDATE - 26 Feb, 2006]
        # Actually, streaming movies *can* have tracks as shown in #1124. We
        # therefore need to drill down and find out if we have a zero length
        # video track/media.
        
        if qtmovie is not nil and qtmovie.duration().timeValue > 0:
            allTracks = qtmovie.tracks()
            if len(qtmovie.tracks()) > 0:
                # First make sure we have at least one video track with a non zero length
                allMedia = [track.media() for track in allTracks]
                for media in allMedia:
                    mediaType = media.attributeForKey_(QTMediaTypeAttribute)
                    mediaDuration = media.attributeForKey_(QTMediaDurationAttribute).QTTimeValue().timeValue
                    if mediaType in self.CORRECT_QTMEDIA_TYPES and mediaDuration > 0:
                        # We have one, see if the file is something we support
                        (path, ext) = os.path.splitext(pathname.lower())
                        if ext in self.POSSIBLY_SUPPORTED_EXT and self.hasFlip4MacComponent():
                            canPlay = True
                            break
                        elif ext not in self.POSSIBLY_SUPPORTED_EXT and ext not in self.UNSUPPORTED_EXT:
                            canPlay = True
                            break
        else:
            self.cachedMovie = nil

        return canPlay

    def hasFlip4MacComponent(self):
        return len(glob.glob('/Library/Quicktime/Flip4Mac*')) > 0

    @platformutils.onMainThread
    def selectItem(self, item):
        pathname = item.getPath()
        if self.cachedMovie is not nil and self.cachedMovie.attributeForKey_(QTMovieFileNameAttribute) == pathname:
            qtmovie = self.cachedMovie
        else:
            (qtmovie, error) = QTMovie.alloc().initWithFile_error_(pathname)
        self.reset()
        if qtmovie is not nil:
            self.view.setMovie_(qtmovie)
            self.view.setNeedsDisplay_(YES)
            self.registerMovieObserver(qtmovie)

    def play(self):
        platformutils.callOnMainThread(self.view.play_, self)
        self.view.setNeedsDisplay_(YES)

    def pause(self):
        platformutils.callOnMainThread(self.view.pause_, nil)

    def stop(self):
        platformutils.callOnMainThread(self.view.pause_, nil)

    def goToBeginningOfMovie(self):
        if self.view.movie() is not nil:
            self.view.movie().gotoBeginning()

    def getDuration(self):
        if self.view.movie() is nil:
            return 0
        qttime = self.view.movie().duration()
        return qttime.timeValue / float(qttime.timeScale)

    def getCurrentTime(self):
        if self.view.movie() is nil:
            return 0
        qttime = self.view.movie().currentTime()
        return qttime.timeValue / float(qttime.timeScale)

    def setCurrentTime(self, time):
        if self.view.movie() is not nil:
            qttime = self.view.movie().currentTime()
            qttime.timeValue = time * float(qttime.timeScale)
            self.view.movie().setCurrentTime_(qttime)

    def getRate(self):
        if self.view.movie() is nil:
            return 0.0
        return self.view.movie().rate()

    def setRate(self, rate):
        if self.view.movie() is not nil:
            self.view.movie().setRate_(rate)
        
    @platformutils.onMainThread
    def setVolume(self, level):
        if self.view.movie() is not nil:
            self.view.movie().setVolume_(level)
    
        
###############################################################################
#### Playlist item ?                                                       ####
###############################################################################

class PlaylistItem:
    "The record that makes up VideoDisplay playlists."

    def getTitle(self):
        """Return the title of this item as a string, for visual presentation
        to the user."""
        raise NotImplementedError

    def getPath(self):
        """Return the full path in the local filesystem to the video file
        to play."""
        raise NotImplementedError

    def getLength(self):
        """Return the length of this item in seconds as a real number. This
        is used only cosmetically, for telling the user the total length
        of the current playlist and so on."""
        raise NotImplementedError

    def onViewed(self):
        """Called by the frontend when a clip is at least partially watched
        by the user. To handle this event, for example by marking the
        item viewed in the database, override this method in a subclass."""
        raise NotImplementedError


###############################################################################
#### The fullscreen controls palette                                       ####
###############################################################################

class FullScreenPalette (NibClassBuilder.AutoBaseClass):
    
    HOLD_TIME = 2
    
    def initWithContentRect_styleMask_backing_defer_(self, rect, style, backing, defer):
        self = super(FullScreenPalette, self).initWithContentRect_styleMask_backing_defer_(
            rect,
            NSBorderlessWindowMask,
            backing,
            defer )
        nc.addObserver_selector_name_object_(self, 'videoWillPlay:', 'videoWillPlay', nil)
        nc.addObserver_selector_name_object_(self, 'videoWillPause:', 'videoWillPause', nil)
        self.setBackgroundColor_(NSColor.clearColor())
        self.setAlphaValue_(1.0)
        self.setOpaque_(NO)
        self.autoConcealTimer = nil
        self.updateTimer = nil
        self.holdStartTime = 0.0
        self.renderer = None
        self.wasPlaying = False
        return self

    def awakeFromNib(self):
        self.seekForwardButton.sendActionOn_(NSLeftMouseDownMask)
        self.seekBackwardButton.sendActionOn_(NSLeftMouseDownMask)
        self.progressSlider.track = NSImage.imageNamed_('fs-progress-background')
        self.progressSlider.cursor = NSImage.imageNamed_('fs-progress-slider')
        self.progressSlider.sliderWasClicked = self.progressSliderWasClicked
        self.progressSlider.sliderWasDragged = self.progressSliderWasDragged
        self.progressSlider.sliderWasReleased = self.progressSliderWasReleased
        self.progressSlider.setShowCursor_(True)
        self.volumeSlider.track = NSImage.imageNamed_('fs-volume-background')
        self.volumeSlider.cursor = NSImage.imageNamed_('fs-volume-slider')
        self.volumeSlider.sliderWasDragged = self.volumeSliderWasDragged
        self.volumeSlider.setShowCursor_(True)

    def canBecomeKeyWindow(self):
        return NO

    def canBecomeMainWindow(self):
        return NO

    def setup(self, item, renderer):
        self.titleLabel.setStringValue_(item.getTitle())
        self.feedLabel.setStringValue_(item.getFeed().getTitle())
        self.donationLabel.setStringValue_(u'')
        self.renderer = renderer
        self.update_(nil)

    def reveal(self, parent):
        if not self.isVisible():
            self.update_(nil)
            self.volumeSlider.setFloatValue_(app.controller.videoDisplay.getVolume())
            screenSize = parent.screen().frame().size
            height = self.frame().size.height
            frame = ((0, -height), (screenSize.width, height))
            self.setFrame_display_(frame, NO)        
            parent.addChildWindow_ordered_(self, NSWindowAbove)
            self.orderFront_(nil)
            frame = ((0, 0), (screenSize.width, height))
            self.setFrame_display_animate_(frame, YES, YES)
            self.holdStartTime = time.time()
            self.autoConcealTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0, self, 'concealAfterDelay:', nil, YES)
            self.updateTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.0, self, 'update:', nil, YES)
            NSRunLoop.currentRunLoop().addTimer_forMode_(self.updateTimer, NSEventTrackingRunLoopMode)
            self.update_(nil)
    
    def conceal(self):
        if self.autoConcealTimer is not nil:
            self.autoConcealTimer.invalidate()
            self.autoConcealTimer = nil
        if self.updateTimer is not nil:
            self.updateTimer.invalidate()
            self.updateTimer = nil
        frame = self.frame()
        frame.origin.y = -frame.size.height
        self.setFrame_display_animate_(frame, YES, YES)
        self.remove()
        NSCursor.setHiddenUntilMouseMoves_(YES)
    
    def concealAfterDelay_(self, timer):
        if time.time() - self.holdStartTime > self.HOLD_TIME:
            self.conceal()
    
    def resetAutoConceal(self):
        self.holdStartTime = time.time()
        
    def expireNow_(self, sender):
        pass
        
    def tellAFriend_(self, sender):
        pass
        
    def update_(self, timer):
        self.timeIndicator.setStringValue_(self.renderer.getDisplayTime())
        self.progressSlider.setFloatValue_(self.renderer.getProgress())
            
    def progressSliderWasClicked(self, slider):
        if app.controller.videoDisplay.isPlaying:
            self.wasPlaying = True
            self.renderer.pause()
        self.renderer.setProgress(slider.floatValue())
        self.renderer.interactivelySeeking = True
        self.resetAutoConceal()
        
    def progressSliderWasDragged(self, slider):
        self.renderer.setProgress(slider.floatValue())
        self.resetAutoConceal()
        
    def progressSliderWasReleased(self, slider):
        self.renderer.interactivelySeeking = False
        if self.wasPlaying:
            self.wasPlaying = False
            self.renderer.play()

    def volumeSliderWasDragged(self, slider):
        app.controller.videoDisplay.setVolume(slider.floatValue())
        self.resetAutoConceal()

    def videoWillPlay_(self, notification):
        self.playPauseButton.setImage_(NSImage.imageNamed_('fs-button-pause'))
        self.playPauseButton.setAlternateImage_(NSImage.imageNamed_('fs-button-pause-alt'))

    def videoWillPause_(self, notification):
        self.playPauseButton.setImage_(NSImage.imageNamed_('fs-button-play'))
        self.playPauseButton.setAlternateImage_(NSImage.imageNamed_('fs-button-play-alt'))

    def remove(self):
        if self.parentWindow() is not nil:
            self.parentWindow().removeChildWindow_(self)
        self.orderOut_(nil)


###############################################################################
#### The fullscreen palette background view                                ####
###############################################################################

class FullScreenPaletteView (NibClassBuilder.AutoBaseClass):

    def awakeFromNib(self):
        self.background = NSImage.imageNamed_('fs-background')
        self.backgroundRect = NSRect((0,0), self.background.size())
        self.topLine = NSImage.imageNamed_('fs-topline')
        self.topLineRect = NSRect((0,0), self.topLine.size())

    def drawRect_(self, rect):
        width = self.bounds().size.width
        bgRect = ((0,0), (width, self.backgroundRect.size.height))
        self.background.drawInRect_fromRect_operation_fraction_(bgRect, self.backgroundRect, NSCompositeSourceOver, 1.0)
        tlRect1 = ((0,self.backgroundRect.size.height), (width-135, self.topLineRect.size.height))
        self.topLine.drawInRect_fromRect_operation_fraction_(tlRect1, self.topLineRect, NSCompositeSourceOver, 1.0)
        tlRect2 = ((width-25,self.backgroundRect.size.height), (25, self.topLineRect.size.height))
        self.topLine.drawInRect_fromRect_operation_fraction_(tlRect2, self.topLineRect, NSCompositeSourceOver, 1.0)


###############################################################################
#### The fullscreen palette control pane                                   ####
###############################################################################

class FullScreenControlsView (NibClassBuilder.AutoBaseClass):
    
    def awakeFromNib(self):
        self.background = NSImage.imageNamed_('fs-controls-background')
        self.backgroundRect = NSRect((0,0), self.background.size())

    def drawRect_(self, rect):
        self.background.compositeToPoint_operation_((0, 0), NSCompositeSourceOver)
        
    def hitTest_(self, point):
        # Our buttons have transparent parts, but we still want mouse clicks
        # to be detected if they happen there, so we override hit testing and
        # simply test for button frames.
        for subview in self.subviews():
            if NSPointInRect(self.convertPoint_fromView_(point, nil), subview.frame()):
                return subview
        return self


###############################################################################
#### The fullscreen palette progress and volume sliders                    ####
###############################################################################

class FullScreenSlider (NibClassBuilder.AutoBaseClass):

    def drawTrack(self):
        self.track.compositeToPoint_operation_((0, 2), NSCompositeSourceOver)

