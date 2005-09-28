import frontend
import app
import MozillaBrowser
import tempfile
import os
import re
import threading

from frontend_implementation.MainFrame import blankWindowClassAtom
from frontend_implementation.MainFrame import invisibleDisplayParentHwnd

import win32gui, win32api
from win32con import *
from ctypes import *
from ctypes.wintypes import *

###############################################################################
#### HTML display                                                          ####
###############################################################################

class HTMLDisplay (app.Display):
    "Selectable Display that shows a HTML document."

    def __init__(self, html, existingView=None, frameHint=None, areaHint=None):
        """'html' is the initial contents of the display, as a string. If
        frameHint is provided, it is used to guess the initial size the HTML
        display will be rendered at, which might reduce flicker when the
        display is installed."""
        app.Display.__init__(self)

	self.lock = threading.RLock()
	self.initialLoadFinished = False
	self.execQueue = []

	# Our message map.
	messageMap = { WM_CLOSE: self.onWMClose,
		       WM_SIZE: self.onWMSize,
		       WM_ERASEBKGND: lambda *args: 1, # flicker reduction
		       WM_ACTIVATE: self.onWMActivate }

	# We have a custom message map, so go ahead and create a custom
	# window class.
	wc = win32gui.WNDCLASS()
	wc.style = 0
	wc.lpfnWndProc = messageMap
	wc.cbWndExtra = 0
	wc.hInstance = win32api.GetModuleHandle(None)
	wc.hIcon = win32gui.LoadIcon(0, IDI_APPLICATION)
	wc.hCursor = win32gui.LoadCursor(0, IDC_ARROW)
	wc.hbrBackground = win32gui.GetStockObject(WHITE_BRUSH)
        #wc.lpszMenuName = None
	wc.lpszClassName = "DTV HTMLDisplay class for %s" % id(self)
	classAtom = win32gui.RegisterClass(wc)
	del wc

        # Create a containing child window.
        self.hwnd = win32gui.CreateWindowEx(0, classAtom,
            "", WS_CHILDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT,
            CW_USEDEFAULT, invisibleDisplayParentHwnd, 0,
            win32api.GetModuleHandle(None), None)

        # If we have size information available, use it. It will be
        # the tuple (width, height). Calling MoveWindow results into a
        # call to onWMSize which results in a call to recomputeSize on
        # the browser.
        displaySizeHint = frameHint and areaHint and frameHint.getDisplaySizeHint(areaHint) or None
        if displaySizeHint:
            win32gui.MoveWindow(self.hwnd, 0, 0, 
                displaySizeHint[0], displaySizeHint[1], False)

        # Save HTML to disk for loading via file: url. We'll delete it
	# when the load has finished in onDocumentLoadFinishedCallback.
        (handle, location) = tempfile.mkstemp('.html')
        handle = os.fdopen(handle,"w")
        handle.write(html)
        handle.close()
	self.deleteOnLoadFinished = location
	# For debugging generated HTML, you could uncomment the next
	# two lines.
	#print "Logged HTML to %s" % location
	#self.deleteOnLoadFinished = None

	# Translate path into URL.
	parts = re.split(r'\\', location)
	url = "file:///" + '/'.join(parts)
	print "url = %s" % url

        userAgent = "DTV/pre-release (http://participatoryculture.org/)"
	self.mb = MozillaBrowser. \
	    MozillaBrowser(hwnd = self.hwnd,
			   initialURL = url,
			   onLoadCallback = self.onURLLoad,
			   onActionCallback = self.onURLLoad,
			   onDocumentLoadFinishedCallback = \
			       self.onDocumentLoadFinished,
			   userAgent = userAgent)

    def getHwnd(self):
        return self.hwnd

    def onWMClose(self, hwnd, msg, wparam, lparam):
	win32gui.PostQuitMessage(0)

    def onWMSize(self, hwnd, msg, wparam, lparam):
	self.mb and self.mb.recomputeSize()

    def onWMActivate(self, hwnd, msg, wparam, lparam):
	if self.mb:
	    if wparam == WA_ACTIVE or wparam == WA_CLICKACTIVE:
		self.mb.activate()
	    if wparam == WA_INACTIVE:
		self.mb.deactivate()

    def onSelected(self, *args):
	# Give focus whenever the display is installed. Probably the best
	# of several not especially attractive options.
	app.Display.onSelected(self, *args)
	self.mb and self.mb.activate()

    # Decorator. Causes calls to be queued up, in order, until
    # onDocumentLoadFinished is called.
    def deferUntilAfterLoad(func):
	def wrapper(self, *args, **kwargs):
	    self.lock.acquire()
	    try:
		if not self.initialLoadFinished:
		    self.execQueue.append(lambda: func(self, *args, **kwargs))
		else:
		    func(self, *args, **kwargs)
	    finally:
		self.lock.release()
	return wrapper

    @deferUntilAfterLoad
    def execJS(self, js):
	raise NotImplementedError

    # DOM hooks used by the dynamic template code
    @deferUntilAfterLoad
    def addItemAtEnd(self, xml, id):
	self.mb.addElementAtEnd(xml, id)
    @deferUntilAfterLoad
    def addItemBefore(self, xml, id):
	self.mb.addElementBefore(xml, id)
    @deferUntilAfterLoad
    def removeItem(self, id):
	self.mb.removeElement(id)
    @deferUntilAfterLoad
    def changeItem(self, id, xml):
	self.mb.changeElement(id, xml)
    @deferUntilAfterLoad
    def hideItem(self, id):
	self.mb.hideElement(id)
    @deferUntilAfterLoad
    def showItem(self, id):
	self.mb.showElement(id)
    def onURLLoad(self, url):
        """Called when this HTML browser attempts to load a URL (either
        through user action or Javascript.) The URL is provided as a
        string. Return true to allow the URL to load, or false to cancel
        the load (for example, because it was a magic URL that marks
        an item to be downloaded.) Implementation in HTMLDisplay always
        returns true; override in a subclass to implement special
        behavior."""
        # For overriding
        return True

    def onDocumentLoadFinished(self):
	if self.deleteOnLoadFinished:
	    try:
		# Comment this line out for debugging
		os.remove(self.deleteOnLoadFinished)
		pass
	    except os.error:
		pass
	    self.deleteOnLoadFinished = None

	# Dispatch calls that got queued up as a result of @deferUntilAfterLoad
	if not self.initialLoadFinished:
	    self.lock.acquire()
	    try:
		self.initialLoadFinished = True
		for func in self.execQueue:
		    func()
		self.execQueue = []
	    finally:
		self.lock.release()

    def unlink(self):
        self.mb = None
        if self.hwnd:
            win32gui.DestroyWindow(self.hwnd)
        self.hwnd = None

    def __del__(self):
        self.unlink()

    # NEEDS: right-click menu.
    # Protocol: if type(getContextClickMenu) == "function", call it and
    # pass the DOM node that was clicked on. That returns "URL|description"
    # with blank lines for separators. On a click, force navigation of that
    # frame to that URL, maybe by setting document.location.href.

###############################################################################
###############################################################################
