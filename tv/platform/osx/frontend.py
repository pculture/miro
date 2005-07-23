import objc
from PyObjCTools import NibClassBuilder, AppHelper
from Foundation import *
from AppKit import *
from WebKit import *
from QTKit import *

import app
import feed
import resource
import template
import database
#import vlc

import re
import os
import sys
import time
import math
import struct
import threading

NibClassBuilder.extractClasses("MainMenu")
NibClassBuilder.extractClasses("MainWindow")
NibClassBuilder.extractClasses("PreferencesWindow")
NibClassBuilder.extractClasses("AddChannelSheet")
NibClassBuilder.extractClasses("PasswordWindow")
NibClassBuilder.extractClasses("QuestionWindow")

doNotCollect = {}

###############################################################################
#### Application object                                                    ####
###############################################################################

class Application:

    def __init__(self):
        self.appl = NSApplication.sharedApplication()
        NSBundle.loadNibNamed_owner_("MainMenu", self.appl)
        controller = self.appl.delegate()
        controller.actualApp = self

        # Force Cocoa into multithreaded mode
        # (NSThread.isMultiThreaded will be true when this call returns)
        NSThread.detachNewThreadSelector_toTarget_withObject_("noop", controller, controller)

    def Run(self):
        AppHelper.runEventLoop()

    def getBackendDelegate(self):
        return UIBackendDelegate()

    def onStartup(self):
        # For overriding
        None

    def onShutdown(self):
        # For overriding
        None

    def addAndSelectFeed(self, url):
        # For overriding
        None


class AppController (NSObject):

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
        # Call the startup hook before any events (such as instructions
        # to open files...) are delivered.
        self.actualApp.onStartup()

    def applicationDidFinishLaunching_(self, notification):
        pass

    def applicationWillTerminate_(self, notification):
        self.actualApp.onShutdown()

    def application_openFile_(self, app, filename):
        return self.actualApp.addFeedFromFile(filename)

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

    openURL_withReplyEvent_ = objc.selector(openURL_withReplyEvent_,
                                            signature="v@:@@")

    def showPreferencesWindow_(self, sender):
        prefController = PreferencesWindowController.alloc().init()
        prefController.retain()
        prefController.showWindow_(None)


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
        # Do this in two steps so that self.obj is set when self.obj.init
        # is called. That way, init can turn around and call selectDisplay.
        self.obj = MainController.alloc()
        self.obj.init(self, appl)

    def selectDisplay(self, display, index):
        """Install the provided 'display' in the left-hand side (index == 0)
        or right-hand side (index == 1) of the window."""
        self.obj.selectDisplay(display, index)

    # Internal use: return an estimate of the size of a given display area as
    # a Cocoa frame object.
    def getDisplaySizeHint(self, index):
        return self.obj.getDisplaySizeHint(index)


class MainController (NibClassBuilder.AutoBaseClass):
    # Outlets: tabView, contentTemplateView
    # Is the delegate for the split view

    def init(self, owner, appl):
        # owner is the actual frame object (the argument to onSelected, etc)
        NSObject.init(self)
        NSBundle.loadNibNamed_owner_("MainWindow", self)

        self.owner = owner
        self.appl = appl
        self.currentDisplay = [None, None]
        self.currentDisplayView = [None, None]
        self.addChannelSheet = None
        return self

    def awakeFromNib(self):
        self.window.makeKeyAndOrderFront_(None)

    ### Switching displays ###

    def selectDisplay(self, display, index):
        # Tell the new display we want to switch to it. It'll call us
        # back when it's ready to display without flickering.
        display.callWhenReadyToDisplay(lambda: self.doSelectDisplay(display, index))

    def doSelectDisplay(self, display, index):
        pool = NSAutoreleasePool.alloc().init()

        # Send notification to old display if any
        if self.currentDisplay[index]:
            self.currentDisplay[index].onDeselected_private(self.owner)
            self.currentDisplay[index].onDeselected(self.owner)
        oldView = self.currentDisplayView[index]

        # Switch to new display
        self.currentDisplay[index] = display
        view = self.currentDisplayView[index] = display and display.getView() or None
        if display is None:
            return

        # Figure out where to put the content area
        # NEEDS: clean up outlet names/types in nib
        theTemplate = (index == 0) and self.tabView or self.contentTemplateView
        frame = theTemplate.bounds()
        parent = theTemplate
        mask = theTemplate.autoresizingMask()

        # Arrange to cover the template that marks the content area
        view.setFrame_(frame)
        parent.addSubview_(view)
        view.setAutoresizingMask_(mask)

        # Mark as needing display
        parent.setNeedsDisplayInRect_(frame)
        view.setNeedsDisplay_(True)

        # Wait until now to clean up the old view, to reduce flicker
        # (doesn't actually work all that well, sadly -- possibly what
        # we want to do is wait until notification comes from the new
        # view that it's been fully loaded to even show it)
        if oldView:
            oldView.removeFromSuperview()

        # Send notification to new display
        display.onSelected_private(self.owner)
        display.onSelected(self.owner)

        pool.release()

    def getDisplaySizeHint(self, index):
        theTemplate = (index == 0) and self.tabView or self.contentTemplateView
        return theTemplate.frame()

    ### Size constraints on splitview ###

    minimumTabListWidth = 180 # pixels
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
        tabBox = self.tabView.superview().superview().superview()
        contentBox = self.contentTemplateView.superview().superview().superview()

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
        contentBox.setFrameOrigin_((tabSize.width + dividerWidth,0))

    ### 'Add Channel' sheet ###

    def openAddChannelSheet_(self, sender):
        controller = AddChannelSheetController.alloc().init(self.appl)
        controller.retain()
        NSApplication.sharedApplication().beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(controller.window(), self.window, self, None, 0)

    ### Action button ###

    def showActionMenu_(self, sender):
        mainMenu = NSApplication.sharedApplication().mainMenu()
        menu = mainMenu.itemWithTag_(1).submenu()

        location = sender.convertPoint_toView_(sender.frame().origin, None)
        location.x += 1.0
        location.y -= 4.0

        curEvent = NSApplication.sharedApplication().currentEvent()
#        event = NSEvent.mouseEventWithType_location_modifierFlags_timestamp_windowNumber_context_eventNumber_clickCount_pressure_(
#            curEvent.type(),
#            location,
#            curEvent.modifierFlags(),
#            curEvent.timestamp(),
#            curEvent.windowNumber(),
#            curEvent.context(),
#            curEvent.eventNumber(),
#            curEvent.clickCount(),
#            curEvent.pressure() )

        NSMenu.popUpContextMenu_withEvent_forView_( menu, curEvent, sender )


###############################################################################
#### Add channel sheet                                                     ####
###############################################################################

class AddChannelSheetController (NibClassBuilder.AutoBaseClass):

    def init(self, parent):
        super(AddChannelSheetController, self).initWithWindowNibName_owner_("AddChannelSheet", self)
        self.parentController = parent
        return self

    def awakeFromNib(self):
        self.addChannelSheetURL.setStringValue_("")

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
        channelsItem = self.makePreferenceItem("ChannelsItem", "Channels", "channels_pref", self.channelsView)
        downloadsItem = self.makePreferenceItem("DownloadsItem", "Downloads", "downloads_pref", self.downloadsView)
        diskSpaceItem = self.makePreferenceItem("DiskSpaceItem", "Disk Space", "disk_space_pref", self.diskSpaceView)

        self.items = {channelsItem.itemIdentifier(): channelsItem,
                      downloadsItem.itemIdentifier(): downloadsItem,
                      diskSpaceItem.itemIdentifier(): diskSpaceItem}

        self.allItems = (channelsItem.itemIdentifier(), 
                         downloadsItem.itemIdentifier(),
                         diskSpaceItem.itemIdentifier())

        toolbar = NSToolbar.alloc().initWithIdentifier_("Preferences")
        toolbar.setDelegate_(self)
        toolbar.setAllowsUserCustomization_(False)
        toolbar.setSelectedItemIdentifier_(channelsItem.itemIdentifier())

        self.window().setToolbar_(toolbar)
        self.switchPreferenceView_(channelsItem)

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
        return True

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
        self.window().setFrame_display_animate_(wframe, True, True)


###############################################################################
#### 'Delegate' objects for asynchronously asking the user questions       ####
###############################################################################

class UIBackendDelegate:

    def getHTTPAuth(self, url, domain, prefillUser = None, prefillPassword = None):
        """Ask the user for HTTP login information for a location, identified
        to the user by its URL and the domain string provided by the
        server requesting the authorization. Default values can be
        provided for prefilling the form. If the user submits
        information, it's returned as a (user, password)
        tuple. Otherwise, if the user presses Cancel or similar, None
        is returned."""
        message = "%s requires a username and password for \"%s\"." % (url, domain)
        return PasswordController.alloc().init(message, prefillUser, prefillPassword).getAnswer()

    def isScrapeAllowed(self, url):
        """Tell the user that URL wasn't a valid feed and ask if it should be
        scraped for links instead. Returns True if the user gives
        permission, or False if not."""
        # This message could use some serious work.
        message = "%s is not a DTV-style channel.  DTV can try to subscribe, but videos may lack proper descriptions and thumbnails.\n\nPlease notify the publisher if you want this channel to be fully supported" % url
        return QuestionController.alloc().init(message).getAnswer()

    def updateAvailable(self, url):
        """Tell the user that an update is available and ask them if they'd
        like to download it now"""
        message = "A new version of DTV is available.\n\nWould you like to download it now?"
        if QuestionController.alloc().init(message).getAnswer():
            self.openExternalURL(url)

    def openExternalURL(self, url):
        # We could use Python's webbrowser.open() here, but
        # unfortunately, it doesn't have the same semantics under UNIX
        # as under other OSes. Sometimes it blocks, sometimes it doesn't.
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))


# NEEDS: Factor code common between PasswordController and
# QuestionController out into a superclass

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

        pool.release()
        return self

    def getAnswer(self):
        """Present the dialog and wait for user answer. Returns (username,
        password) if the user pressed OK, or None if the user pressed Cancel."""
        # PasswordController is likely to get release()d by Python in response
        # to getAnswer returning.
        self.performSelectorOnMainThread_withObject_waitUntilDone_("showAtModalLevel:", None, False)
        self.condition.acquire()
        self.condition.wait()
        self.condition.release()
        self.release()
        return self.result

    # executes in GUI thread
    def showAtModalLevel_(self, sender):
        self.window.setLevel_(NSModalPanelWindowLevel)
        self.window.makeKeyAndOrderFront_(None)

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


class QuestionController(NibClassBuilder.AutoBaseClass):

    def init(self, message):
        # as loaded, button titles are "Yes" and "No" and window title is
        # "Question", but these could be made arguments to init()
        pool = NSAutoreleasePool.alloc().init()
        # sets defaultButton, alternateButton, textArea, window
        NSBundle.loadNibNamed_owner_("QuestionWindow", self)
        self.textArea.setStringValue_(message)
        self.result = None
        self.condition = threading.Condition()

        # Ensure we're not deallocated until the window that has actions
        # that point at us is closed
        self.retain()
        pool.release()
        return self

    def getAnswer(self):
        """Present the dialog and wait for user answer. Returns True or False
        depending on the button selected."""
        self.performSelectorOnMainThread_withObject_waitUntilDone_("showAtModalLevel:", None, False)
        self.condition.acquire()
        self.condition.wait()
        self.condition.release()
        self.release()
        return self.result

    # executes in GUI thread
    def showAtModalLevel_(self, sender):
        self.window.setLevel_(NSModalPanelWindowLevel)
        self.window.makeKeyAndOrderFront_(None)

    # bound to button in nib
    def defaultAction_(self, sender):
        self.condition.acquire()
        self.result = True
        self.window.close()
        self.condition.notify()
        self.condition.release()

    # bound to button in nib
    def alternateAction_(self, sender):
        self.condition.acquire()
        self.result = False
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

        super(TabButtonCell, self).drawTitle_withFrame_inView_(self.attributedTitle(), rect, view)


###############################################################################
#### Our own prettier beveled NSBox                                        ####
###############################################################################

class BeveledBox (NibClassBuilder.AutoBaseClass):
    # Actual base class is NSBox

    TOP_COLOR        = NSColor.colorWithDeviceWhite_alpha_( 147 / 255.0, 1.0 )
    LEFT_RIGHT_COLOR = NSColor.colorWithDeviceWhite_alpha_( 224 / 255.0, 1.0 )
    BOTTOM_COLOR     = NSColor.colorWithDeviceWhite_alpha_( 240 / 255.0, 1.0 )
    CONTOUR_COLOR    = NSColor.colorWithDeviceWhite_alpha_( 102 / 255.0, 1.0 )

    def drawRect_(self, rect):
        interior = NSInsetRect( rect, 1, 1 )

        NSColor.whiteColor().set()
        NSRectFill( interior )

        self.CONTOUR_COLOR.set()
        NSFrameRect( interior )

        self.TOP_COLOR.set()
        p1 = NSPoint( rect.origin.x+1, rect.size.height-0.5 )
        p2 = NSPoint( rect.size.width-1, rect.size.height-0.5 )
        NSBezierPath.strokeLineFromPoint_toPoint_( p1, p2 )

        self.LEFT_RIGHT_COLOR.set()
        p1 = NSPoint( rect.origin.x+0.5, rect.size.height-1 )
        p2 = NSPoint( rect.origin.x+0.5, rect.origin.y+1 )
        NSBezierPath.strokeLineFromPoint_toPoint_( p1, p2 )
        p1 = NSPoint( rect.size.width-0.5, rect.origin.y+1 )
        p2 = NSPoint( rect.size.width-0.5, rect.size.height-1 )
        NSBezierPath.strokeLineFromPoint_toPoint_( p1, p2 )

        self.BOTTOM_COLOR.set()
        p1 = NSPoint( rect.origin.x+1, rect.origin.y+0.5 )
        p2 = NSPoint( rect.size.width-1, rect.origin.y+0.5 )
        NSBezierPath.strokeLineFromPoint_toPoint_( p1, p2 )


###############################################################################
#### The progress display                                                  ####
###############################################################################

class ProgressDisplayView (NibClassBuilder.AutoBaseClass):
    # Actual base class is NSView

    def initWithFrame_(self, frame):
        super(ProgressDisplayView, self).initWithFrame_(frame)

        self.backgroundLeft = NSImage.imageNamed_( "display_left" )
        self.backgroundLeftWidth = self.backgroundLeft.size().width
        self.backgroundRight = NSImage.imageNamed_( "display_right" )
        self.backgroundRightWidth = self.backgroundRight.size().width
        self.backgroundCenter = NSImage.imageNamed_( "display_center" )
        self.backgroundCenterWidth = self.backgroundCenter.size().width

        self.grooveContourColor = NSColor.colorWithCalibratedWhite_alpha_( 0.1, 0.3 )
        self.grooveFillColor = NSColor.colorWithCalibratedWhite_alpha_( 0.5, 0.3 )

        self.timeAttrs = { NSFontAttributeName:NSFont.fontWithName_size_("Helvetica", 10),
                           NSForegroundColorAttributeName:NSColor.colorWithCalibratedWhite_alpha_(69/255.0, 1.0) }

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

        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, 'prepareForNewMovie:', 'PrepareForNewMovie', None)
        nc.addObserver_selector_name_object_(self, 'movieWillStartPlaying:', 'MovieWillStartPlaying', None)
        nc.addObserver_selector_name_object_(self, 'movieWillStopPlaying:', 'MovieWillStopPlaying', None)

        self.movie = None
        self.heartbeatTimer = None

        return self;

    def prepareForNewMovie_(self, notification):
        self.movie = notification.userInfo().get('Movie')
        self.setNeedsDisplay_(True)

    def movieWillStartPlaying_(self, notification):
        self.heartbeatTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(0.5, self, 'heartbeat:', notification.userInfo(), True)

    def movieWillStopPlaying_(self, notification):
        if self.heartbeatTimer != None:
            self.heartbeatTimer.invalidate()
        self.heartbeatTimer = None

    def heartbeat_(self, timer):
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        self.drawBackground()
        self.drawTimeIndicator()
        self.drawProgressGroove()
        self.drawProgressCursor()

    def drawBackground(self):
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

    def drawTimeIndicator(self):
        timeStr = '00:00:00'
        if self.movie != None:
            seconds = self.getCurrentTimeInSeconds()
            timeStr = time.strftime("%H:%M:%S", time.gmtime(seconds))
        NSString.stringWithString_(timeStr).drawAtPoint_withAttributes_( (8,5), self.timeAttrs )

    def drawProgressGroove(self):
        origin = NSPoint(60, 8)
        size = NSSize(self.getGrooveWidth(), 8)
        rect = NSOffsetRect(NSRect(origin, size), -0.5, -0.5)

        self.grooveFillColor.set()
        NSBezierPath.fillRect_(rect)
        self.grooveContourColor.set()
        NSBezierPath.strokeRect_(rect)

    def drawProgressCursor(self):
        if self.movie == None:
            return

        progress = 0.0

        currentTime = self.getCurrentTimeInSeconds()
        if currentTime > 0.0:
            progress = self.getDurationInSeconds() / currentTime

        offset = 0
        if progress > 0.0:
            offset = (self.getGrooveWidth() - 9) / progress

        x = math.floor(59 + offset) + 0.5
        self.cursor.compositeToPoint_operation_((x,7), NSCompositeSourceOver)

    def getDurationInSeconds(self):
        if self.movie == None:
            return 0
        qttime = self.movie.duration()
        return qttime.timeValue / float(qttime.timeScale)

    def getCurrentTimeInSeconds(self):
        if self.movie == None:
            return 0
        qttime = self.movie.currentTime()
        return qttime.timeValue / float(qttime.timeScale)

    def getGrooveWidth(self):
        return self.bounds().size.width - 60 - 8


###############################################################################
#### Right-hand pane displays generally                                    ####
###############################################################################

# To be provided in platform package
class Display:
    "Base class representing a display in a MainFrame's right-hand pane."

    def __init__(self):
        self.currentFrame = None # tracks the frame that currently has us selected

    def onSelected(self, frame):
        "Called when the Display is shown in the given MainFrame."
        None

    def onDeselected(self, frame):
        """Called when the Display is no longer shown in the given
        MainFrame. This function is called on the Display losing the
        selection before onSelected is called on the Display gaining the
        selection."""
        None

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


class NullDisplay (Display):
    "Represents an empty right-hand area."

    def __init__(self):
        pool = NSAutoreleasePool.alloc().init()
        # NEEDS: take (and leak) a covering reference -- cargo cult programming
        self.view = WebView.alloc().init().retain()
        Display.__init__(self)
        pool.release()

    def getView(self):
        return self.view


###############################################################################
#### Right-hand pane HTML display                                          ####
###############################################################################

class HTMLDisplay (Display):
    "HTML browser that can be shown in a MainFrame's right-hand pane."

    # We don't need to override onSelected, onDeselected

    def __init__(self, html, frameHint=None, indexHint=None):
        """'html' is the initial contents of the display, as a string. If
        frameHint is provided, it is used to guess the initial size the HTML
        display will be rendered at, which might reduce flicker when the
        display is installed."""
        pool = NSAutoreleasePool.alloc().init()
        self.readyToDisplayHook = None
        self.readyToDisplay = False
        self.web = ManagedWebView.alloc().init(html, None, self.nowReadyToDisplay, lambda x:self.onURLLoad(x), frameHint and indexHint and frameHint.getDisplaySizeHint(indexHint) or None)
        Display.__init__(self)
        pool.release()

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

    def onURLLoad(self, url):
        """Called when this HTML browser attempts to load a URL (either
        through user action or Javascript.) The URL is provided as a
        string. Return true to allow the URL to load, or false to cancel
        the load (for example, because it was a magic URL that marks
        an item to be downloaded.) Implementation in HTMLDisplay always
        returns true; override in a subclass to implement special
        behavior."""
        # For overriding
        None

    def callWhenReadyToDisplay(self, hook):
        # NEEDS: lock?
        if self.readyToDisplay:
            hook()
        else:
            assert(self.readyToDisplayHook == None)
            self.readyToDisplayHook = hook

    # Called (via callback established in constructor)
    def nowReadyToDisplay(self):
        self.readyToDisplay = True
        if self.readyToDisplayHook:
            hook = self.readyToDisplayHook
            self.readyToDisplayHook = None
            hook()


###############################################################################
#### An enhanced WebView                                                   ####
###############################################################################

class ManagedWebView (NSObject):

    def init(self, initialHTML, existingView=None, onInitialLoadFinished=None, onLoadURL=None, sizeHint=None):
        self.onInitialLoadFinished = onInitialLoadFinished
        self.onLoadURL = onLoadURL
        self.initialLoadFinished = False
        self.view = existingView
        if not self.view:
            self.view = WebView.alloc().init()
            if sizeHint:
                # We have an estimate of the size that will be assigned to
                # the view when it is actually inserted in the MainFrame.
                # Use this to size the view we just created so the HTML
                # is hopefully rendered to the correct dimensions, instead
                # of having to be corrected after being displayed.
                self.view.setFrame_(sizeHint)
        self.jsQueue = []
        self.view.setPolicyDelegate_(self)
        self.view.setResourceLoadDelegate_(self)
        self.view.setFrameLoadDelegate_(self)
        self.view.setUIDelegate_(self)
        self.view.mainFrame().loadHTMLString_baseURL_(initialHTML, None)
        return self

    ##
    # Create CTRL-click menu on the fly
    def webView_contextMenuItemsForElement_defaultMenuItems_(self,webView,contextMenu,defaultMenuItems):
        if self.initialLoadFinished:
            menuItems = []

            exists = webView.windowScriptObject().evaluateWebScript_("typeof(getContextClickMenu)") == "function"
            if exists:
                x = webView.windowScriptObject().callWebScriptMethod_withArguments_("getContextClickMenu",[contextMenu['WebElementDOMNode']])

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
                        menuItem.setEnabled_(True)
                        menuItem.setRepresentedObject_(url)
                        menuItem.setTarget_(self)
                        menuItems.append(menuItem)
                return menuItems
        else:
            return []

    ##
    # Process a click on an item in a context menu
    def processContextClick_(self,item):
        self.execJS("document.location.href = \""+item.representedObject()+"\";")

    # Return the actual WebView that we're managing
    def getView(self):
        return self.view

    # Execute given Javascript string in context of the HTML document,
    # queueing as necessary if the initial HTML hasn't finished loading yet
    def execJS(self, js):
        pool = NSAutoreleasePool.alloc().init()

        #print "JS: %s" % js
        if not self.initialLoadFinished:
            self.jsQueue.append(js)
        else:
            # WebViews are not documented to be thread-safe, so be cautious
            # and do updates only on the main thread (in fact, crashes in
            # khtml occur if this is not done)
            self.view.performSelectorOnMainThread_withObject_waitUntilDone_("stringByEvaluatingJavaScriptFromString:", js, False)
            # self.view.setNeedsDisplay_(True) # shouldn't be necessary

        pool.release()

    # Generate callback when the initial HTML (passed in the constructor)
    # has been loaded
    def webView_didFinishLoadForFrame_(self, webview, frame):
        if (not self.initialLoadFinished) and (frame is self.view.mainFrame()):
            self.initialLoadFinished = True
            # Execute any Javascript that we queued because the page load
            # hadn't completed
            for js in self.jsQueue:
                self.view.stringByEvaluatingJavaScriptFromString_(js)
            self.jsQueue = []
            if self.onInitialLoadFinished:
                self.onInitialLoadFinished()

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


###############################################################################
#### Right-hand pane video display                                         ####
###############################################################################

class VideoDisplay (Display):
    "Video player that can be shown in a MainFrame's right-hand pane."

    controller = None

    def __init__(self, filename):
        Display.__init__(self)
        self.filename = filename

    def onSelected(self, frame):
        self.controller.enableControls(True)
        self.controller.setMovieFile(self.filename)
#        self.controller.play_(None)

    def onDeselected(self, frame):
        self.controller.stop_(None)
        self.controller.enableControls(False)
        self.controller.reset()

    def getView(self):
        return self.controller.rootView


class VideoDisplayController (NibClassBuilder.AutoBaseClass):

    def awakeFromNib(self):
        self.isPlaying = False
        VideoDisplay.controller = self

    def notify(self, message, movie):
        nc = NSNotificationCenter.defaultCenter()
        info = { 'Movie': movie }
        nc.postNotificationName_object_userInfo_(message, self, info)

    def setMovieFile(self, filename):
        (movie, error) = QTMovie.alloc().initWithFile_error_(filename)
        self.videoView.setMovie_(movie)
        self.notify('PrepareForNewMovie', movie)

    def reset(self):
        self.videoView.setMovie_(None)

    def enableControls(self, enabled):
        self.fastBackwardButton.setEnabled_(enabled)
        self.stopButton.setEnabled_(enabled)
        self.playPauseButton.setEnabled_(enabled)
        self.fastForwardButton.setEnabled_(enabled)
        self.muteButton.setEnabled_(enabled)
        self.volumeSlider.setEnabled_(enabled)
        self.maxVolumeButton.setEnabled_(enabled)
        self.fullscreenButton.setEnabled_(enabled)

    def play_(self, sender):
        self.notify('MovieWillStartPlaying', self.videoView.movie())
        self.playPauseButton.setImage_(NSImage.imageNamed_('pause.png'))
        self.playPauseButton.setAlternateImage_(NSImage.imageNamed_('pause_blue.png'))
        self.videoView.play_(self)
        self.isPlaying = True

    def pause_(self, sender):
        self.notify('MovieWillStopPlaying', self.videoView.movie())
        self.playPauseButton.setImage_(NSImage.imageNamed_('play.png'))
        self.playPauseButton.setAlternateImage_(NSImage.imageNamed_('play_blue.png'))
        self.videoView.pause_(self)
        self.isPlaying = False

    def stop_(self, sender):
        self.pause_(sender)
        self.videoView.gotoBeginning_(self)

    def playPause_(self, sender):
        if self.isPlaying:
            self.pause_(sender)
        else:
            self.play_(sender)

    def fastForward_(self, sender):
        self.videoView.movie().setRate_(2.0)

    def fastBackward_(self, sender):
        self.videoView.movie().setRate_(-2.0)

    def setVolume_(self, sender):
        self.videoView.movie().setVolume_(sender.floatValue())

    def muteVolume_(self, sender):
        self.volumeSlider.setFloatValue_(0.0)
        self.setVolume_(self.volumeSlider)

    def setMaxVolume_(self, sender):
        self.volumeSlider.setFloatValue_(1.0)
        self.setVolume_(self.volumeSlider)

    def goFullscreen_(self, sender):
        pass


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

###############################################################################
###############################################################################
