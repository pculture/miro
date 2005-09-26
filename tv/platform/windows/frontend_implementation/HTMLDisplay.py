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

        # Create a dummy child window
        self.hwnd = win32gui.CreateWindowEx(0, blankWindowClassAtom,
            "", WS_CHILDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT,
            CW_USEDEFAULT, invisibleDisplayParentHwnd, 0,
            win32api.GetModuleHandle(None), None)

        # If we have size information available, use it. It will be the
        # tuple (width, height).
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
        print "Logged HTML to %s" % location
	self.deleteOnLoadFinished = location

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

    # Decorator. Causes calls to be queued up, in order, until
    # onDocumentLoadFinished is called.
    def deferUntilAfterLoad(func):
	def wrapper(self, *args, **kwargs):
	    self.lock.acquire()
	    if not self.initialLoadFinished:
		self.execQueue.append(lambda: func(self, *args, **kwargs))
	    else:
		func(self, *args, **kwargs)
	    self.lock.release()
	return wrapper

    @deferUntilAfterLoad
    def execJS(self, js):
	raise NotImplementedError

    # DOM hooks used by the dynamic template code
    @deferUntilAfterLoad
    def addItemAtEnd(self, xml, id):
	print "aIAE"
	self.mb.addElementAtEnd(xml, id)
	print "back"
    @deferUntilAfterLoad
    def addItemBefore(self, xml, id):
	print "aIB on %s" % self
	self.mb.addElementBefore(xml, id)
	print "back"
    @deferUntilAfterLoad
    def removeItem(self, id):
	print "rI"
	self.mb.removeItem(id)
	print "back"
    @deferUntilAfterLoad
    def changeItem(self, id, xml):
	print "cI"
	self.mb.changeItem(id, xml)
	print "back"
    @deferUntilAfterLoad
    def hideItem(self, id):
	print "hI"
	self.mb.hideItem(id)
	print "back"
    @deferUntilAfterLoad
    def showItem(self, id):
	print "sI"
	self.mb.showItem(id)
	print "back"

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
	print "onDocumentLoadFinished"
	if self.deleteOnLoadFinished:
	    try:
		# NEEDS: debugging
#		os.remove(self.deleteOnLoadFinished)
		pass
	    except os.error:
		pass
	    self.deleteOnLoadFinished = None

	# Dispatch calls that got queued up as a result of @deferUntilAfterLoad
	if not self.initialLoadFinished:
	    self.lock.acquire()
	    print "Dispatching queued up events"
	    self.initialLoadFinished = True
	    for func in self.execQueue:
		print "dispatching %s" % func
		func()
		print "back from dispatch"
#		print "skipping %s" % func
	    self.execQueue = []
	    print "Done dispatching"
	    self.lock.release()

    def unlink(self):
        self.mb = None
        if self.hwnd:
            print "HTMLDisplay unlink %s" % self.hwnd
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
