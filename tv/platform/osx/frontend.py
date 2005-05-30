import objc
from WebKit import *
import re
from Foundation import *
from AppKit import *
from PyObjCTools import NibClassBuilder, AppHelper
import resource
import template
import database
import threading
#import vlc
import os
import struct
import time
import feed

NibClassBuilder.extractClasses("MainMenu")
NibClassBuilder.extractClasses("MainWindow")
NibClassBuilder.extractClasses("VideoView")
NibClassBuilder.extractClasses("AddChannelSheet")

###############################################################################
#### Application object                                                    ####
###############################################################################

class Application:
    def __init__(self):
	self.app = NSApplication.sharedApplication()
	self.ctrl = AppController.alloc().init(self)
	self.app.setDelegate_(self.ctrl)
	NSBundle.loadNibNamed_owner_("MainMenu", self.app)

	# Force Cocoa into multithreaded mode
	# (NSThread.isMultiThreaded will be true when this call
	# returns)
	NSThread.detachNewThreadSelector_toTarget_withObject_("noop", self.ctrl, self.ctrl)

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

class AppController(NSObject):
    def init(self, actualApp):
	self.actualApp = actualApp
	return self
    
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
	#print "**** openFile %s" % filename
	return False

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
    def __init__(self, app):
	"""The initially active display will be an instance of NullDisplay."""
	# Do this in two steps so that self.obj is set when self.obj.init
	# is called. That way, init can turn around and call selectDisplay.
	self.obj = MainController.alloc()
	self.obj.init(self, app)

    def selectDisplay(self, display, index):
	"""Install the provided 'display' in the left-hand side (index == 0)
	or right-hand side (index == 1) of the window."""
	self.obj.selectDisplay(display, index)

    # Internal use: return an estimate of the size of a given display area as
    # a Cocoa frame object.
    def getDisplaySizeHint(self, index):
	return self.obj.getDisplaySizeHint(index)

class MainController (NibClassBuilder.AutoBaseClass):
    # Outlets: tabView, contentTemplateView, mainWindow
    # Is the delegate for the split view

    def init(self, owner, app):
	# owner is the actual frame object (the argument to onSelected, etc)
	NSObject.init(self)
	NSBundle.loadNibNamed_owner_("MainWindow", self)
	
	self.owner = owner
	self.app = app
	self.currentDisplay = [None, None]
	self.currentDisplayView = [None, None]
	self.addChannelSheet = None
	return self

    def awakeFromNib(self):
	self.mainWindow.makeKeyAndOrderFront_(None)

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

    ### Size contraints on splitview ###

    minimumTabListWidth = 150 # pixels
    minimumContentWidth = 300 # pixels

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
	splitViewSize = sender.frame().size
	tabSize = self.tabView.frame().size
	contentSize = self.contentTemplateView.frame().size

	tabSize.height = splitViewSize.height
	contentSize.height = splitViewSize.height

	contentSize.width = splitViewSize.width - sender.dividerThickness() - tabSize.width
	if contentSize.width < self.minimumContentWidth:
	    contentSize.width = self.minimumContentWidth
	tabSize.width = splitViewSize.width - sender.dividerThickness() - contentSize.width

	self.tabView.setFrameSize_(tabSize)
	self.tabView.setFrameOrigin_(NSPoint(0, 0))
	self.contentTemplateView.setFrameSize_(contentSize)
	self.contentTemplateView.setFrameOrigin_(NSPoint(tabSize.width + sender.dividerThickness(), 0))

    ### 'Add Channel' sheet ###

    def openAddChannelSheet_(self, sender):
	if not self.addChannelSheet:
	    NSBundle.loadNibNamed_owner_("AddChannelSheet", self)
	if not self.addChannelSheet:
	    raise NotImplementedError, "Missing or defective AddChannelSheet nib"
	self.addChannelSheetURL.setStringValue_("")
	NSApplication.sharedApplication().beginSheet_modalForWindow_modalDelegate_didEndSelector_contextInfo_(self.addChannelSheet, self.mainWindow, self, self.addChannelSheetDidEnd, 0)
	# Sheet's now visible and function returns.

    def addChannelSheetDidEnd(self, sheet, returnCode, contextInfo):
	sheet.orderOut_(self)
    # decorate with appropriate selector
    addChannelSheetDidEnd = AppHelper.endSheetMethod(addChannelSheetDidEnd)

    def addChannelSheetDone_(self, sender):
	sheetURL = self.addChannelSheetURL.stringValue()
	# NEEDS: pass a non-default template name?
	self.app.addAndSelectFeed(sheetURL)
	NSApplication.sharedApplication().endSheet_(self.addChannelSheet)

    def addChannelSheetCancel_(self, sender):
	NSApplication.sharedApplication().endSheet_(self.addChannelSheet)

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
	raise NotImplementedError

    def isScrapeAllowed(self, url):
	"""Tell the user that URL wasn't a valid feed and ask if it should be
	scraped for links instead. Returns True if the user gives
	permission, or False if not."""
	raise NotImplementedError

###############################################################################
#### Right-hand pane displays generally                                    ####
###############################################################################

# To be provided in platform package
class Display:
    "Base class representing a display in a MainFrame's right-hand pane."
    
    def onSelected(self, frame):
	"""Called when the Display is shown in the given MainFrame."""
	None

    def onDeselected(self, frame):
	"""Called when the Display is no longer shown in the given
	MainFrame. This function is called on the Display losing the
	selection before onSelected is called on the Display gaining the
	selection."""
	None

    def __init__(self):
	self.currentFrame = None # tracks the frame that currently has us selected

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

class NullDisplay(Display):
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

class HTMLDisplay(Display):
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

class ManagedWebView(NSObject):
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

import sys
# Given a Unix PID, give focus to the corresponding process. Requires rooting
# around in Carbon APIs.
def darkVoodooMakePidFront(pid):
    # See http://svn.red-bean.com/pyobjc/trunk/pyobjc/Examples/Scripts/wmEnable.py
    def S(*args):
	return ''.join(args)
    OSErr = objc._C_SHT
    OUTPID = 'o^L'
    INPID = 'L'
    OUTPSN = 'o^{ProcessSerialNumber=LL}'
    INPSN = 'n^{ProcessSerialNumber=LL}'	
    FUNCTIONS=[
	( u'GetCurrentProcess', S(OSErr, OUTPSN) ),
	( u'GetProcessForPID', S(OSErr, INPID, OUTPSN) ),
	( u'SetFrontProcess', S(OSErr, INPSN) ),
	]	

    bndl = NSBundle.bundleWithPath_(objc.pathForFramework('/System/Library/Frameworks/ApplicationServices.framework'))
    if bndl is None:
	print >>sys.stderr, 'ApplicationServices missing'
	assert(0)
    d = {}
    objc.loadBundleFunctions(bndl, d, FUNCTIONS)
    for (fn, sig) in FUNCTIONS:
	if fn not in d:
	    print >>sys.stderr, 'Missing', fn
	    assert(0)
    err, psn = d['GetProcessForPID'](pid)
    if err:
        print >>sys.stderr, 'GetProcessForPID', (err, psn)
	assert(0)
    err = d['SetFrontProcess'](psn)
    if err:
        print >>sys.stderr, 'SetFrontProcess', (err, psn)
	assert(0)

def playVideoFileHack(filename):
    # Old way
    #	vlch = vlcext.create()
    #	print vlcext.init(vlch, ('vlc', '--plugin-path', '/Users/gschmidt/co/vlc-0.8.1/VLC.app/Contents/MacOS/modules'))
    #	print vlcext.addTarget(vlch, '/Users/gschmidt/Movies/utahsaints.avi')
    #	print vlcext.play(vlch)
    
    # New way
    # pluginRoot = os.path.join(NSBundle.mainBundle().bundlePath(), 'Contents/MacOS/modules')
    # print pluginRoot
    # mc = vlc.MediaControl(['--verbose', '1', '--plugin-path', pluginRoot])
    # mc.playlist_add_item(filename)
    # mc.start(0)
    print "Hack play: %s" % filename
    app = "/Applications/VLC-no-controls.app"
    path = "%s/Contents/MacOS/VLC" % app
    pid = os.spawnl(os.P_NOWAIT, path, path, 
		    "--fullscreen", filename)
    print "pid: %s" % pid
    # Give VLC a chance to connect to the process server.
    time.sleep(1)
    darkVoodooMakePidFront(pid)

class VideoDisplay(Display):
    "Video player that can be shown in a MainFrame's right-hand pane."

    def __init__(self, playlist, previousDisplay):
	"""'playlist' is a View giving the video items to play
	as PlaylistItems. The cursor of the View indicates where playback
	should start. 'previousDisplay' indicates the display that should
	be switched to when the user is done interacting with the player."""
	pool = NSAutoreleasePool.alloc().init()
	self.previousDisplay = previousDisplay

	self.obj = PlayerController.alloc()
	self.obj.init(playlist, self)
	Display.__init__(self)

	pool.release()

    def getView(self):
	return self.obj.rootView

class PlayerController(NibClassBuilder.AutoBaseClass):
    # Has outlets for most of the GUI widgets

    def init(self, playlist, owner):
	# owner is our Python-instantiable proxy, the actual Display object
	# NEEDS: text field are hidden by image -- why?
	# NEEDS: resizing behavior of some controls is wrong
	NSObject.init(self)
	NSBundle.loadNibNamed_owner_("VideoView", self)

	# Start a VLC instance
	# (Removed for fullscreen demo hack)
	# pluginRoot = os.path.join(NSBundle.mainBundle().bundlePath(), 'Contents/MacOS/modules')
	# mc = vlc.MediaControl(['--verbose', '1', '--plugin-path', pluginRoot])

	# Set up initial playlist state and start playing
	# NEEDS: lock from observation to callback registration
	# NEEDS: bail if playlist is empty (else VLC exception!)
	self.playlistView = playlist
	print "PLAYLIST SIZE: %d" % playlist.len()
	for a in playlist:
	    print "%s (%s)" % (a.getTitle(), a.getPath())
	    mc.playlist_add_item(a.getPath())
	mc.start(0)

	playlist.addChangeCallback(lambda index: self.onPlaylistItemChanged(index))
	playlist.addAddCallback(lambda newIndex: self.onPlaylistItemAdded(newIndex))
	playlist.addRemoveCallback(lambda oldObject, oldIndex: self.onPlaylistItemRemoved(oldObject, oldIndex))

	# Put GUI controls in correct state
	self.synchronizeControls()
	
    def synchronizeControls(self):
	# NEEDS: add actual logic
	# NEEDS: set licenseImage, licenseText
	self.backButton.setEnabled_(True)
	self.topText.setStringValue_("My nice video's title goes here.")
	self.bottomText.setStringValue_("Here I tell you where I got it and when it expires.")
	self.deleteButton.setEnabled_(True)
	self.donateButton.setEnabled_(True)
	self.fastForwardButton.setEnabled_(True)
	self.forwardButton.setEnabled_(True)
	self.fullscreenButton.setEnabled_(True)
	self.playButton.setEnabled_(True) # NEEDS: also image change
	self.rewindButton.setEnabled_(True)
	self.saveButton.setEnabled_(True)
	self.volumeSlider.setEnabled_(True) # NEEDS: also set position

    def onPlaylistItemChanged(self, index):
	# NEEDS
	print "should update playlist item in VLC"

    def onPlaylistItemAdded(self, newIndex):
	# NEEDS
	print "should add playlist item in VLC"

    def onPlaylistItemRemoved(self, oldObject, oldIndex):
	# NEEDS
	# NEEDS: Bail if playlist is now empty
	print "should remove playlist item in VLC"

    def back_(self, sender):
	print "back"
    def changeVolume_(self, sender):
	print "changeVolume"
    def deleteItem_(self, sender):
	print "deleteItem"
    def donate_(self, sender):
	print "donate"
    def fastForward_(self, sender):
	print "fastForward"
    def forward_(self, sender):
	print "forward"
    def goFullscreen_(self, sender):
	print "goFullscreen"
    def play_(self, sender):
	print "play"
    def rewind_(self, sender):
	print "rewind"
    def saveItem_(self, sender):
	print "saveItem"

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
