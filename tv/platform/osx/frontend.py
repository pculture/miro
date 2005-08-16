from PyObjCTools import NibClassBuilder, AppHelper
from objc import YES, NO, nil
from gestalt import gestalt
from Foundation import *
from AppKit import *
from WebKit import *

try:
    from QTKit import *
except:
    print "[DTV] QTKit coudln't be imported. Please upgrade to Quicktime 7 or later. You can update at http://apple.com/quicktime/ or by running Software Update."

import app
import feed
import config
import resource
import template
import database

import re
import os
import tempfile
import sys
import objc
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
NibClassBuilder.extractClasses("FullScreenAlertPanel")

doNotCollect = {}
nc = NSNotificationCenter.defaultCenter()

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

    def checkQuicktimeVersion(self, showError):
        supported = gestalt('qtim') >= 0x07000000
        
        if not supported and showError:
            alert = NSAlert.alloc().init()
            alert.setAlertStyle_(NSCriticalAlertStyle)
            alert.setMessageText_('Unsupported version of Quicktime')
            alert.setInformativeText_('To run DTV you need the most recent version of Quicktime, which is a free update.')
            
            button1 = alert.addButtonWithTitle_('Quit')
            button1.setTag_(NSAlertFirstButtonReturn)
            button2 = alert.addButtonWithTitle_('Download Quicktime now')
            button2.setTag_(NSAlertSecondButtonReturn)

            result = alert.runModal()
            if result == NSAlertFirstButtonReturn:
                NSApplication.sharedApplication().terminate_(nil)
            elif result == NSAlertSecondButtonReturn:
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
        print "NOT IMPLEMENTED"

    def showPreferencesWindow_(self, sender):
        prefController = PreferencesWindowController.alloc().init()
        prefController.retain()
        prefController.showWindow_(nil)

    def donate_(self, sender):
        print "NOT IMPLEMENTED"

    def tellAFriend_(self, sender):
        print "NOT IMPLEMENTED"


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
        self.collectionDisplay = None
        self.mainDisplay = None
        # Do this in two steps so that self.obj is set when self.obj.init
        # is called. That way, init can turn around and call selectDisplay.
        self.obj = MainController.alloc()
        self.obj.init(self, appl)

    def selectDisplay(self, display, area=None):
        """Install the provided 'display' in the requested area"""
        self.obj.selectDisplay(display, area)

    # Internal use: return an estimate of the size of a given display area as
    # a Cocoa frame object.
    def getDisplaySizeHint(self, area):
        return self.obj.getDisplaySizeHint(area)


class DisplayHostView (NibClassBuilder.AutoBaseClass):
    
    def awakeFromNib(self):
        self.hostedDisplay = None
        self.hostedView = nil
    
    def setDisplay(self, display, owner):
        pool = NSAutoreleasePool.alloc().init()

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

        del pool


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
        self.frame.collectionDisplay = self.collectionHostView
        self.frame.mainDisplay = self.mainHostView
        self.restoreLayout()
        self.actionButton.sendActionOn_(NSLeftMouseDownMask)
        self.showWindow_(nil)

    def appWillTerminate_(self, notification):
        self.saveLayout()

    def restoreLayout(self):
        windowFrame = config.get(config.MAIN_WINDOW_FRAME)
        if windowFrame is not None:
           windowFrame = NSRectFromString(windowFrame)
           self.window().setFrame_display_(windowFrame, NO)

        leftFrame = config.get(config.LEFT_VIEW_SIZE)
        rightFrame = config.get(config.RIGHT_VIEW_SIZE)
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

        config.set(config.MAIN_WINDOW_FRAME, windowFrame)
        config.set(config.LEFT_VIEW_SIZE, leftFrame)
        config.set(config.RIGHT_VIEW_SIZE, rightFrame)
        config.save()

    ### Switching displays ###

    def selectDisplay(self, display, area):
        # Tell the new display we want to switch to it. It'll call us
        # back when it's ready to display without flickering.
        display.callWhenReadyToDisplay(lambda: self.doSelectDisplay(display, area))

    def doSelectDisplay(self, display, area):
        if area is not None:
            area.setDisplay(display, self.frame)

    def getDisplaySizeHint(self, area):
        return area.frame()

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
        tabBox = self.tabView.superview().superview().superview()
        contentBox = self.mainHostView.superview().superview().superview()

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

    ### Actions ###

    def switchTabs_(self, sender):
        tag = sender.selectedCell().tag()
        self.tabView.selectTabViewItemAtIndex_(tag)
        newDisplay = None
        if tag == 1:
            newDisplay = self.frame.channelsDisplay
        elif tag == 2:
            newDisplay = self.frame.collectionDisplay
        self.appl.onDisplaySwitch(newDisplay)

    def playVideo_(self, sender):
        print "NOT IMPLEMENTED"

    def playVideoFullScreen_(self, sender):
        print "NOT IMPLEMENTED"

    def playVideoHalfScreen_(self, sender):
        print "NOT IMPLEMENTED"

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
        print "NOT IMPLEMENTED"

    def copyChannelLink_(self, sender):
        print "NOT IMPLEMENTED"

    def updateChannel_(self, sender):
        print "NOT IMPLEMENTED"

    def updateAllChannels_(self, sender):
        print "NOT IMPLEMENTED"

    def renameChannel_(self, sender):
        print "NOT IMPLEMENTED"

    def createCollection_(self, sender):
        print "NOT IMPLEMENTED"

    def deleteCollection_(self, sender):
        print "NOT IMPLEMENTED"

    def sendCollectionToFriend_(self, sender):
        print "NOT IMPLEMENTED"

    def showActionMenu_(self, sender):
        mainMenu = NSApplication.sharedApplication().mainMenu()
        tag = self.switcherMatrix.selectedCell().tag()
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

#    def validateMenuItem_(self, item):
#        return super(MainController, self).validateMenuItem_(item)


###############################################################################
#### Fullscreen alert panel                                                ####
###############################################################################

class FullScreenAlertPanelController (NibClassBuilder.AutoBaseClass):

    @classmethod
    def displayIfNeeded(cls):
        noAlert = config.get(config.NO_FULLSCREEN_ALERT)
        if not noAlert:
            controller = FullScreenAlertPanelController.alloc().init()
            NSApplication.sharedApplication().runModalForWindow_(controller.window())

    def init(self):
        parent = super(FullScreenAlertPanelController, self)
        self = parent.initWithWindowNibName_owner_('FullScreenAlertPanel', self)
        return self

    def dismiss_(self, sender):
        if self.dontShowCheckbox.state() == NSOnState:
            config.set(config.NO_FULLSCREEN_ALERT, TRUE)
        NSApplication.sharedApplication().stopModal()
        self.window().orderOut_(nil)


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
    
    def runAtStartup_(self, sender):
        run = (sender.state() == NSOnState)
        config.set(config.RUN_DTV_AT_STARTUP, run)

class ChannelsPrefsController (NibClassBuilder.AutoBaseClass):

    def checkEvery_(self, sender):
        minutes = sender.tag()
        config.set(config.CHECK_CHANNELS_EVERY_X_MN, minutes)

class DownloadsPrefsController (NibClassBuilder.AutoBaseClass):
    
    def limitUpstream_(self, sender):
        limit = (sender.state() == NSOnState)
        config.set(config.LIMIT_UPSTREAM, limit)
    
    def setUpstreamLimit_(self, sender):
        limit = sender.floatValue()
        config.set(config.UPSTREAM_LIMIT_IN_KBS, limit)

class DiskSpacePrefsController (NibClassBuilder.AutoBaseClass):
    
    def setMinimumSpace_(self, sender):
        space = sender.floatValue()
        print "setting minimum space to %s" % space
        config.set(config.PRESERVE_X_GB_FREE, space)


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
        del pool
        return self

    def getAnswer(self):
        """Present the dialog and wait for user answer. Returns True or False
        depending on the button selected."""
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
        
        self.movie = nil
        self.lastTime = 0
        self.dragging = False

        return self;

    def setMovie_(self, movie):
        if self.movie is not nil:
            self.movie.setDelegate_(nil)
        self.movie = movie
        self.lastTime = 0
        if self.movie is not nil:
            self.movie.setDelegate_(self)
        self.setNeedsDisplay_(YES)

    def mouseDown_(self, event):
        if self.movie is not nil:
            location = self.convertPoint_fromView_(event.locationInWindow(), nil)
            if NSPointInRect(location, self.getGrooveRect()):
                self.dragging = True
                self.movie.stop()
                self.movie.setCurrentTime_(self.getTimeForLocation(location))

    def mouseDragged_(self, event):
        if self.dragging:
            location = self.convertPoint_fromView_(event.locationInWindow(), nil)
            self.movie.setCurrentTime_(self.getTimeForLocation(location))

    def mouseUp_(self, event):
        if self.movie is not nil:
            self.dragging = False
            self.movie.play()

    def getTimeForLocation(self, location):
        rect = self.getGrooveRect()
        offset = location.x - rect.origin.x
        if offset < 0:
            offset = 0
        if offset > rect.size.width:
            offset = rect.size.width
        if offset > 0:
            offset /= rect.size.width
        time = self.movie.duration()
        time.timeValue *= offset
        return time

    def movieShouldTask_(self, movie):
        currentTime = self.getCurrentTimeInSeconds()
        if currentTime - self.lastTime >= 1.0 or self.dragging:
            self.setNeedsDisplay_(YES)
            self.lastTime = currentTime
        return NO
        
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
        if self.movie is not nil:
            seconds = self.getCurrentTimeInSeconds()
            timeStr = time.strftime("%H:%M:%S", time.gmtime(seconds))
        NSString.stringWithString_(timeStr).drawAtPoint_withAttributes_( (8,5), self.timeAttrs )

    def drawProgressGroove(self):
        rect = self.getGrooveRect()
        self.grooveFillColor.set()
        NSBezierPath.fillRect_(rect)
        self.grooveContourColor.set()
        NSBezierPath.strokeRect_(rect)

    def drawProgressCursor(self):
        if self.movie == nil:
            return

        progress = 0.0

        currentTime = self.getCurrentTimeInSeconds()
        if currentTime > 0.0:
            progress = self.getDurationInSeconds() / currentTime

        offset = 0
        if progress > 0.0:
            offset = (self.getGrooveRect().size.width - 9) / progress

        x = math.floor(59 + offset) + 0.5
        self.cursor.compositeToPoint_operation_((x,7), NSCompositeSourceOver)

    def getDurationInSeconds(self):
        if self.movie == nil:
            return 0
        qttime = self.movie.duration()
        return qttime.timeValue / float(qttime.timeScale)

    def getCurrentTimeInSeconds(self):
        if self.movie == nil:
            return 0
        qttime = self.movie.currentTime()
        return qttime.timeValue / float(qttime.timeScale)

    def getGrooveRect(self):
        origin = NSPoint(60, 8)
        size = NSSize(self.bounds().size.width - 60 - 8, 8)
        return NSOffsetRect(NSRect(origin, size), -0.5, -0.5)


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


class NullDisplay (Display):
    "Represents an empty right-hand area."

    def __init__(self):
        pool = NSAutoreleasePool.alloc().init()
        # NEEDS: take (and leak) a covering reference -- cargo cult programming
        self.view = WebView.alloc().init().retain()
        self.view.setCustomUserAgent_("DTV/pre-release (http://participatoryculture.org/)")
        Display.__init__(self)
        del pool

    def getView(self):
        return self.view


###############################################################################
#### Right-hand pane HTML display                                          ####
###############################################################################


class HTMLDisplay (Display):
    "HTML browser that can be shown in a MainFrame's right-hand pane."

    sharedWebView = None

    # We don't need to override onSelected, onDeselected

    def __init__(self, html, existingView=None, frameHint=None, areaHint=None):
        """'html' is the initial contents of the display, as a string. If
        frameHint is provided, it is used to guess the initial size the HTML
        display will be rendered at, which might reduce flicker when the
        display is installed."""
        pool = NSAutoreleasePool.alloc().init()
        self.readyToDisplayHook = None
        self.readyToDisplay = False

#         if existingView == "sharedView":
#             if not HTMLDisplay.sharedWebView:
#                 HTMLDisplay.sharedWebView = WebView.alloc().init()
#                 HTMLDisplay.sharedWebView.setCustomUserAgent_("DTV/pre-release (http://participatoryculture.org/)")
#                 print "Creating sharedWebView: %s" % HTMLDisplay.sharedWebView
#             existingView = HTMLDisplay.sharedWebView

        self.web = ManagedWebView.alloc().init(html, None, self.nowReadyToDisplay, lambda x:self.onURLLoad(x), frameHint and areaHint and frameHint.getDisplaySizeHint(areaHint) or None)

        Display.__init__(self)
        del pool

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
            assert(self.readyToDisplayHook == None)
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
    

###############################################################################
#### An enhanced WebView                                                   ####
###############################################################################

# Little ObjC-compatible class to wrap a closure (function) so it can be
# used as an ObjC-callback, eg, posted to the main thread with
# performSelectorOnMainThread_withObject_waitUntilDone_.
class ObjCHandlerWrapper(NSObject):
    def init(self, func):
        self.func = func
        return self

    def executeDiscarding1_(self, ignoredArgument):
        self.func()

    def executeOnMainThreadAsync_(self):
        self.performSelectorOnMainThread_withObject_waitUntilDone_("executeDiscarding1:", None, NO)

class ManagedWebView (NSObject):

    def init(self, initialHTML, existingView=nil, onInitialLoadFinished=None, onLoadURL=None, sizeHint=None):
        self.onInitialLoadFinished = onInitialLoadFinished
        self.onLoadURL = onLoadURL
        self.initialLoadFinished = False
        self.view = existingView
        if not self.view:
            self.view = WebView.alloc().init()
            print "***** Creating new WebView %s" % self.view
            if sizeHint:
                # We have an estimate of the size that will be assigned to
                # the view when it is actually inserted in the MainFrame.
                # Use this to size the view we just created so the HTML
                # is hopefully rendered to the correct dimensions, instead
                # of having to be corrected after being displayed.
                self.view.setFrame_(sizeHint)
            self.view.setCustomUserAgent_("DTV/pre-release (http://participatoryculture.org/)")
        else:
            print "***** Using existing WebView %s" % self.view
            if sizeHint:
                self.view.setFrame_(sizeHint)
        self.execQueue = []
        self.view.setPolicyDelegate_(self)
        self.view.setResourceLoadDelegate_(self)
        self.view.setFrameLoadDelegate_(self)
        self.view.setUIDelegate_(self)

        (handle, location) = tempfile.mkstemp('.html')
        handle = os.fdopen(handle,"w")
        handle.write(initialHTML)
        handle.close()
        print "DTV: loading temp file %s" % location
        self.view.mainFrame().loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_("file://%s" % location)))
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
                        menuItem.setEnabled_(YES)
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

    # Call func() once the document has finished loading. If the
    # document has already finished loading, call it right away. But
    # in either case, the call is executed on the main thread, by
    # queueing an event, since WebViews are not documented to be
    # thread-safe, and we have seen crashes.
    def execAfterLoad(self, func):
        if not self.initialLoadFinished:
            self.execQueue.append(func)
        else:
            # Contortion: we can't just pass random Python functions
            # into ObjC and expect it to know how to call them, so use
            # a NSObject-derived wrapper class.
            pool = NSAutoreleasePool.alloc().init()
            ObjCHandlerWrapper.alloc().init(func).executeOnMainThreadAsync_()
            del pool

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
                ObjCHandlerWrapper.alloc().init(func).executeOnMainThreadAsync_()
            self.execQueue = []
            self.initialLoadFinished = True

            if self.onInitialLoadFinished:
                self.onInitialLoadFinished()

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

    ## DOM mutators called, ultimately, by dynamic template system ##

    def findElt(self, id):
        doc = self.view.mainFrame().DOMDocument()
        elt = doc.getElementById_(id)
        return elt

    def createElt(self, xml):
        parent = self.view.mainFrame().DOMDocument().createElement_("div")
        parent.setInnerHTML_(xml)
        elt = parent.firstChild()
        if parent.childNodes().length() != 1:
            raise NotImplementedError, "in createElt, expected exactly one node"
        return elt
        
    @deferUntilAfterLoad
    def addItemAtEnd(self, xml, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: addItemAtEnd: missing element %s" % id
        else:
            elt.insertBefore__(self.createElt(xml), None)
            #print "add item %s at end of %s" % (elt.getAttribute_("id"), id)

    @deferUntilAfterLoad
    def addItemBefore(self, xml, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: addItemBefore: missing element %s" % id
        else:
            elt.parentNode().insertBefore__(self.createElt(xml), elt)
            #print "add item %s before %s" % (elt.getAttribute_("id"), id)

    @deferUntilAfterLoad
    def removeItem(self, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: removeItem: missing element %s" % id
        else:
            elt.parentNode().removeChild_(elt)
            #print "remove item %s" % id

    @deferUntilAfterLoad
    def changeItem(self, id, xml):
        elt = self.findElt(id)
        if not elt:
            print "warning: changeItem: missing element %s" % id
        else:
            elt.setOuterHTML_(xml)
            #print "change item %s (new id %s)" % (id, elt.getAttribute_("id"))

    @deferUntilAfterLoad
    def hideItem(self, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: hideItem: missing element %s" % id
        else:
            elt.getAttribute_("style").setAttribute_("display", "none")
            #print "hide item %s (new style '%s')" % (id, elt.getAttribute_("style"))

    @deferUntilAfterLoad
    def showItem(self, id):
        elt = self.findElt(id)
        if not elt:
            print "warning: showItem: missing element %s" % id
        else:
            elt.getAttribute_("style").setAttribute_("display", "")
            #print "show item %s (new style '%s')" % (id, elt.getAttribute_("style"))

###############################################################################
#### Right-hand pane video display                                         ####
###############################################################################

class VideoDisplay (Display,app.VideoDisplayDB):
    "Video player that can be shown in a MainFrame's right-hand pane."

    controller = nil

    def __init__(self, firstItemId, view, previousDisplay):
        app.VideoDisplayDB.__init__(self, firstItemId, view)
        Display.__init__(self)
        VideoDisplay.controller.previousDisplay = previousDisplay

    def onSelected(self, frame):
        VideoDisplay.controller.frame = frame
        VideoDisplay.controller.enableControls(YES)
        VideoDisplay.controller.setPlaylist(self)
        VideoDisplay.controller.play_(nil)

    def onDeselected(self, frame):
        VideoDisplay.controller.pause_(nil)
        VideoDisplay.controller.enableControls(False)
        VideoDisplay.controller.reset()

    def getView(self):
        return VideoDisplay.controller.rootView


class VideoDisplayController (NibClassBuilder.AutoBaseClass):

    def awakeFromNib(self):
        self.reset()
        self.fastForwardButton.sendActionOn_(NSLeftMouseDownMask)
        self.fullscreenController = nil
        VideoDisplay.controller = self

    def reset(self):
        self.isPlaying = False
        self.playlist = None
        self.frame = None
        self.previousDisplay = None
        self.videoView.setMovie_(nil)
        self.progressDisplayer.setMovie_(nil)
        nc.removeObserver_(self)

    def setPlaylist(self, playlist):
        self.playlist = playlist
        item = self.playlist.cur()
        self.selectPlaylistItem(item)

    def selectPlaylistItem(self, item):
        pathname = item.getPath()
        (movie, error) = QTMovie.alloc().initWithFile_error_(pathname)
        self.videoView.setMovie_(movie)
        self.progressDisplayer.setMovie_(movie)
        self.setVolume_(self.volumeSlider)

        info = item.getInfoMap()
        html = template.fillStaticTemplate('video-info', info)
        self.infoView.mainFrame().loadHTMLString_baseURL_(html, nil)

        nc.removeObserver_(self)
        nc.addObserver_selector_name_object_(
            self, 
            'handleMovieNotification:', 
            nil, 
            self.videoView.movie())

    def exitVideoMode(self):
        if self.fullscreenController is not nil:
            self.fullscreenController.exitFullscreen()
            self.fullscreenController = nil
        mainController = self.videoView.window().delegate()
        mainController.selectDisplay(self.previousDisplay, self.frame.mainDisplay)

    def enableControls(self, enabled):
        self.fastBackwardButton.setEnabled_(enabled)
        self.stopButton.setEnabled_(enabled)
        self.playPauseButton.setEnabled_(enabled)
        self.fastForwardButton.setEnabled_(enabled)
        self.muteButton.setEnabled_(enabled)
        self.volumeSlider.setEnabled_(enabled)
        self.fullscreenButton.setEnabled_(enabled)

    def play_(self, sender):
        self.videoView.play_(self)
        self.isPlaying = True

    def pause_(self, sender):
        self.videoView.pause_(self)
        self.isPlaying = False

    def stop_(self, sender):
        self.pause_(sender)
        self.videoView.gotoBeginning_(self)
        self.exitVideoMode()

    def playPause_(self, sender):
        if self.isPlaying:
            self.pause_(sender)
        else:
            self.play_(sender)

    def fastForward_(self, sender):
        if self.videoView.movie().rate() == 1.0:
            self.videoView.movie().setRate_(2.0)
            self.fastForwardButton.sendActionOn_(NSLeftMouseUpMask)
        else:
            self.videoView.movie().setRate_(1.0)
            self.fastForwardButton.sendActionOn_(NSLeftMouseDownMask)

    def fastBackward_(self, sender):
        if self.videoView.movie().rate() == 1.0:
            self.videoView.movie().setRate_(-2.0)
            self.fastForwardButton.sendActionOn_(NSLeftMouseUpMask)
        else:
            self.videoView.movie().setRate_(1.0)
            self.fastForwardButton.sendActionOn_(NSLeftMouseDownMask)

    def setVolume_(self, sender):
        self.videoView.movie().setVolume_(sender.floatValue())

    def muteUnmuteVolume_(self, sender):
        volume = self.videoView.movie().volume()
        if volume > 0.0:
            self.volumeSlider.setEnabled_(NO)
            self.videoView.movie().setVolume_(0.0)
        else:
            self.volumeSlider.setEnabled_(YES)
            self.videoView.movie().setVolume_(self.volumeSlider.floatValue())

    def goFullscreen_(self, sender):
        self.fullscreenController = FullScreenVideoController.alloc().initWithPreviousVideoView_(self.videoView)
        self.fullscreenController.setDelegate_(self)
        self.fullscreenController.enterFullScreen()

    def didEnterFullscreenMode(self):
        FullScreenAlertPanelController.displayIfNeeded()

    def didExitFullscreenMode(self):
        self.fullscreenController = nil

    def handleMovieNotification_(self, notification):
        info = notification.userInfo()
        if notification.name() == QTMovieRateDidChangeNotification:
            rate = info.get(QTMovieRateDidChangeNotificationParameter).floatValue()
            if rate == 0.0:
                self.playPauseButton.setImage_(NSImage.imageNamed_('play.png'))
                self.playPauseButton.setAlternateImage_(NSImage.imageNamed_('play_blue.png'))
            else:
                self.playPauseButton.setImage_(NSImage.imageNamed_('pause.png'))
                self.playPauseButton.setAlternateImage_(NSImage.imageNamed_('pause_blue.png'))
        elif notification.name() == QTMovieDidEndNotification:
            if not self.progressDisplayer.dragging:
                nextItem = self.playlist.getNext()
                if nextItem is not None:
                    self.selectPlaylistItem(nextItem)
                    self.play_(nil)
                else:
                    self.exitVideoMode()


###############################################################################
#### The fullscreen video controller                                       ####
#### We have to dynamically link some specific Carbon functions which are  ####
###  not available in the default MacPython                                ####
###############################################################################

kUIModeNormal = 0
kUIModeAllHidden = 3

carbonBundle = NSBundle.bundleWithPath_('/System/Library/Frameworks/Carbon.framework')
objc.loadBundleFunctions(carbonBundle, globals(), (('SetSystemUIMode', 'III', ""),))

class FullScreenVideoController (NSObject):

    def initWithPreviousVideoView_(self, previousMovieView):
        self = super(FullScreenVideoController, self).init()
        self.videoWindow = FullScreenVideoWindow.alloc().init(previousMovieView).retain()
        self.videoWindow.controller = self
        self.delegate = nil
        return self

    def setDelegate_(self, delegate):
        self.delegate = delegate

    def enterFullScreen(self):
        SetSystemUIMode(kUIModeAllHidden, 0)
        self.videoWindow.makeKeyAndOrderFront_(nil)
        
        if self.delegate is not nil and self.delegate.didEnterFullscreenMode:
            self.delegate.didEnterFullscreenMode()

    def exitFullScreen(self):
        self.videoWindow.close()
        SetSystemUIMode(kUIModeNormal, 0)
        
        if self.delegate is not nil and self.delegate.didExitFullscreenMode:
            self.delegate.didExitFullscreenMode()


###############################################################################
#### The fullscreen video window                                           ####
###############################################################################

class FullScreenVideoWindow (NSWindow):

    def init(self, previousMovieView):
        frame = NSScreen.mainScreen().frame()

        parent = super(FullScreenVideoWindow, self)
        self = parent.initWithContentRect_styleMask_backing_defer_(
            frame,
            NSBorderlessWindowMask,
            NSBackingStoreBuffered,
            YES )
        
        self.previousMovieView = previousMovieView
        self.movieView = QTMovieView.alloc().initWithFrame_(frame)
        self.movieView.setControllerVisible_(NO)
        self.movieView.setPreservesAspectRatio_(YES)
        self.movieView.setMovie_(previousMovieView.movie())
        self.setContentView_(self.movieView)
        return self

    def canBecomeMainWindow(self):
        return YES
    
    def canBecomeKeyWindow(self):
        return YES

    def sendEvent_(self, event):
        if event.type() == NSKeyDown and event.characters().characterAtIndex_(0) == 0x1B:
            self.controller.exitFullScreen()

    def close(self):
        self.previousMovieView.setMovie_(self.movieView.movie())
        super(FullScreenVideoWindow, self).close()


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
###############################################################################
