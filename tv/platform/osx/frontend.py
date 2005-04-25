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
import vlc
import os

NibClassBuilder.extractClasses("MainMenu")
NibClassBuilder.extractClasses("MainWindow")
NibClassBuilder.extractClasses("VideoView")

###############################################################################
#### Application object                                                    ####
###############################################################################

class Application:
    def __init__(self):
	self.app = NSApplication.sharedApplication()
	self.ctrl = AppController.alloc().init(self.OnStartup, self.OnShutdown)
	self.app.setDelegate_(self.ctrl)
	NSBundle.loadNibNamed_owner_("MainMenu", self.app)

	# Force Cocoa into multithreaded mode
	# (NSThread.isMultiThreaded will be true when this call
	# returns)
	NSThread.detachNewThreadSelector_toTarget_withObject_("noop", self.ctrl, self.ctrl)

    def Run(self):
	AppHelper.runEventLoop()

    def OnStartup(self):
	# For overriding
	None

    def OnShutdown(self):
	# For overriding
	None

class AppController(NSObject):
    def init(self, onStartupHook, onShutdownHook):
	self.onStartupHook = onStartupHook
	self.onShutdownHook = onShutdownHook
	return self
    
    # Do nothing. A dummy method called by Application to force Cocoa into
    # multithreaded mode.
    def noop(self):
	return

    def applicationDidFinishLaunching_(self, notification):
	self.onStartupHook()

    def applicationWillTerminate_(self, notification):
	self.onShutdownHook()

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
    def __init__(self, tabs):
	"""'tabs' is a View containing Tab subclasses. The initially
	selected tab is given by the cursor. The initially active display
	will be an instance of NullDisplay."""
	# Do this in two steps so that self.obj is set when self.obj.init
	# is called. That way, init can turn around and call selectDisplay.
	self.obj = MainController.alloc()
	self.obj.init(tabs, self)

    def selectDisplay(self, display):
	"""Install the provided 'display' in the right-hand side
	of the window."""
	self.obj.selectDisplay(display)

    def setTabListActive(self, active):
	"""If active is true, show the tab list normally. If active is
	false, show the tab list a different way to indicate that it
	doesn't pertain directly to what is going on (for example, a
	video is playing) but that it can still be clicked on."""
	self.obj.setTabListActive(active)
	None

    # Internal use: return an estimate of the size of the display area as
    # a Cocoa frame object.
    def getDisplaySizeHint(self):
	return self.obj.getDisplaySizeHint()

class MainController (NibClassBuilder.AutoBaseClass):
    # Outlets: tabView, contentTemplateView, mainWindow
    # Is the delegate for the split view

    def init(self, tabs, owner):
	# owner is the actual frame object (the argument to onSelected, etc)
	NSObject.init(self)
	NSBundle.loadNibNamed_owner_("MainWindow", self)
	
	self.tabs = tabs.map(lambda x: TabAdaptor(x, self.getTabState))
	self.owner = owner
	self.active = True
	self.currentDisplay = None
	self.currentDisplayView = None
	self.templateHandle = None
	self.lastSelectedTab = None

	# NEEDS: set cursor to first item (presently map doesn't preserve
	# cursors; remove when this changes)
	self.tabs.resetCursor()
	self.tabs.getNext()
	
	# Initalize tab view
	(html, self.templateHandle) = template.fillTemplate('tablist', {'tabs': self.tabs}, lambda js:self.execTabJS(js)) # NEEDS: lock
	self.web = ManagedWebView.alloc().init(html, self.tabView, None, lambda x:self.onTabURLLoad(x))

	self.checkSelectedTab()
	# NEEDS: Cursor hasn't been updated yet, and I'm not sure how
	# to predict this. Mail sent to Nick.
	self.tabs.addRemoveCallback(lambda oldObject, oldIndex: self.checkSelectedTab())
	return self

    def execTabJS(self, js):
	self.web.execJS(js)

    def __del__(self):
	self.templateHandle and self.templateHandle.unlinkTemplate()

    def awakeFromNib(self):
	self.mainWindow.makeKeyAndOrderFront_(None)

    def selectDisplay(self, display):
	# Tell the new display we want to switch to it. It'll call us
	# back when it's ready to display without flickering.
	display.callWhenReadyToDisplay(lambda: self.doSelectDisplay(display))

    def doSelectDisplay(self, display):
	pool = NSAutoreleasePool.alloc().init()

	# Send notification to old display if any
	if self.currentDisplay:
	    self.currentDisplay.onDeselected_private(self.owner)
	    self.currentDisplay.onDeselected(self.owner)
	oldView = self.currentDisplayView

	# Switch to new display
	self.currentDisplay = display
	view = self.currentDisplayView = display and display.getView() or None
	if display is None:
	    return

	# Figure out where to put the content area
	frame = self.contentTemplateView.bounds()
	parent = self.contentTemplateView
	mask = self.contentTemplateView.autoresizingMask()

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

    def getDisplaySizeHint(self):
	return self.contentTemplateView.frame()

    def getTabState(self, tabId):
	# Determine if this tab is selected
	cur = self.tabs.cur()
	isSelected = False
	if cur:
	    isSelected = (cur.id == tabId)

	# Compute status string
	if isSelected:
	    if self.active:
		return 'selected'
	    else:
		return 'selected-inactive'
	else:
	    return 'normal'

    def onTabURLLoad(self, url):
	match = re.compile(r"^action:selectTab\?id=(.*)$").match(url)
	if match:
	    # NEEDS: take lock

	    # Move the cursor to the newly selected object
	    newId = match.group(1)
	    self.tabs.resetCursor()
	    while True:
		cur = self.tabs.getNext()
		if cur == None:
		    assert(0) # NEEDS: better error (JS sent bad tab id)
		if cur.id == newId:
		    break

	    # Figure out what happened
	    oldSelected = self.lastSelectedTab
	    newSelected = self.tabs.cur()

	    # Handle reselection action
	    if oldSelected and oldSelected.id == newSelected.id:
		# Tab was reselected
		if self.currentDisplay:
		    self.currentDisplay.onSelectedTabClicked()

	    # Handle case where a different tab was clicked
	    self.checkSelectedTab()
	    return False
	return True

    def checkSelectedTab(self):
	# NEEDS: locking ...
	oldSelected = self.lastSelectedTab
	newSelected = self.tabs.cur()

	#print "OldSelected %s NewSelected %s" % (oldSelected, newSelected)

	tabChanged = ((oldSelected == None) != (newSelected == None)) or (oldSelected and newSelected and oldSelected.id != newSelected.id)
	if tabChanged: # Tab selection has changed! Deal.

	    # Redraw the old and new objects (remember, these are TabAdaptors,
	    # not actual database objects)
	    if oldSelected:
		oldSelected.redraw()
	    if newSelected:
		newSelected.redraw()

	    # Boot up the new tab's template.
	    if newSelected:
		newSelected.start(self.owner)
	    else:
		self.selectDisplay(NullDisplay())

	    # Record that we're up to date
	    self.lastSelectedTab = newSelected

    def setTabListActive(self, active):
	self.active = active
	if self.tabs.cur():
	    self.tabs.cur().redraw()

###############################################################################
#### Tabs                                                                  ####
###############################################################################

class Tab:
    """Base class for the records that makes up the list of left-hand
    tabs to show. Cannot be put into a MainFrame directly -- you must
    use a subclass, such as HTMLTab, that knows how to render itself."""

    def __init__(self):
	pass

    def start(self, frame):
	"""Called when the tab is clicked on in a MainFrame where it was
	not already the selected tab (or when it becomes selected by other
	means, eg, the selected tab was deleted and this tab has become
	selected by default.) 'frame' is the MainFrame where the tab is
	selected. Should usually result in a call to
	frame.selectDisplay()."""
	None

class HTMLTab(Tab):
    """A Tab whose appearance is defined by HTML."""

    def __init__(self):
	pass
    
    def getHTML(self, state):
	"""Get HTML giving the visual appearance of the tab. 'state' is
	one of 'selected' (tab is currently selected), 'normal' (tab is
	not selected), or 'selected-inactive' (tab is selected but
	setTabListActive was called with a false value on the MainFrame
	for which the tab is being rendered.) The HTML should be returned
	as a xml.dom.minidom element or document fragment."""
	None
	
    def redraw(self):
	# Force a redraw by sending a change notification on the underlying
	# DB object.
	# NEEDS: make this go away.
	None

class TabAdaptor:
    tabIdCounter = 0

    def __init__(self, tab, getTabState):
	self.tab = tab
	self.getTabState = getTabState
	self.id = "tab%d" % TabAdaptor.tabIdCounter
	TabAdaptor.tabIdCounter += 1
    
    def markup(self):
	return self.tab.getHTML(self.getTabState(self.id))

    def start(self, frame):
	return self.tab.start(frame)

    def redraw(self):
	self.tab.redraw()
	
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

    def onSelectedTabClicked(self):
	"""Called on the Display shown in the current MainFrame when the
	selected tab is clicked again by the user."""
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

    # We don't need to override onSelected, onDeselected, onSelectedTabClicked
      
    def __init__(self, html, frameHint=None):
	"""'html' is the initial contents of the display, as a string. If
	frameHint is provided, it is used to guess the initial size the HTML
	display will be rendered at, which might reduce flicker when the
	display is installed."""
	pool = NSAutoreleasePool.alloc().init()

	self.readyToDisplayHook = None
	self.readyToDisplay = False
	self.web = ManagedWebView.alloc().init(html, None, self.nowReadyToDisplay, lambda x:self.onURLLoad(x), frameHint and frameHint.getDisplaySizeHint() or None)
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
	self.view.mainFrame().loadHTMLString_baseURL_(initialHTML, None)
	return self

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

def playVideoFileHack(filename):
    # Old way
    #	vlch = vlcext.create()
    #	print vlcext.init(vlch, ('vlc', '--plugin-path', '/Users/gschmidt/co/vlc-0.8.1/VLC.app/Contents/MacOS/modules'))
    #	print vlcext.addTarget(vlch, '/Users/gschmidt/Movies/utahsaints.avi')
    #	print vlcext.play(vlch)
    
    # New way
    pluginRoot = os.path.join(NSBundle.mainBundle().bundlePath(), 'Contents/MacOS/modules')
    print pluginRoot
    mc = vlc.MediaControl(['--verbose', '1', '--plugin-path', pluginRoot])
    mc.playlist_add_item(filename)
    mc.start(0)

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

    def onSelectedTabClicked(self):
	self.currentFrame.setTabListActive(True)
	self.currentFrame.selectDisplay(self.previousDisplay)

class PlayerController(NibClassBuilder.AutoBaseClass):
    # Has outlets for most of the GUI widgets

    def init(self, playlist, owner):
	# owner is our Python-instantiable proxy, the actual Display object
	# NEEDS: text field are hidden by image -- why?
	# NEEDS: resizing behavior of some controls is wrong
	NSObject.init(self)
	NSBundle.loadNibNamed_owner_("VideoView", self)

	# Start a VLC instance
	pluginRoot = os.path.join(NSBundle.mainBundle().bundlePath(), 'Contents/MacOS/modules')
	mc = vlc.MediaControl(['--verbose', '1', '--plugin-path', pluginRoot])

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
