import frontend
import app
import tempfile
import os
import re
import threading
from xpcom import components

###############################################################################
#### HTML display                                                          ####
###############################################################################

class ProgressListener:
    _com_interfaces_ = [components.interfaces.nsIWebProgressListener]

    def __init__(self, boundDisplay):
	self.boundDisplay = boundDisplay

    def onLocationChange(self, webProgress, request, location):
	print "onLocationChange: %s" % request

    def onProgressChange(self, webProgress, request, curSelfProgress,
			 maxSelfProgress, curTotalProgress, maxTotalProgess):
	pass

    def onSecurityChange(self, webProgress, request, state):
	pass

    def onStateChange(self, webProgress, request, stateFlags, status):
	print "onStateChange! %s %s %s" % (request, stateFlags, status)

class HTMLDisplay (app.Display):
    "Selectable Display that shows a HTML document."

    def __init__(self, html, existingView=None, frameHint=None, areaHint=None):
        """'html' is the initial contents of the display, as a string. If
        frameHint is provided, it is used to guess the initial size the HTML
        display will be rendered at, which might reduce flicker when the
        display is installed."""
	print "HTMLDisplay created"
        app.Display.__init__(self)

	self.lock = threading.RLock()
	self.initialLoadFinished = False
	self.execQueue = []
	self.progressListener = ProgressListener(self)

	klass = components.classes["@participatoryculture.org/dtv/jsbridge;1"]
	self.jsbridge = klass.getService(components.interfaces.pcfIDTVJSBridge)

	# This flag is set when we are deseleted to ensure that we
	# stop trying to generate events against the browser object.
	self.isDead = False

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

	# Translate path into URL and stash until we are ready to display
	# ourselves.
	parts = re.split(r'\\', location)
	self.initialURL = "file:///" + '/'.join(parts)

    # NEEDS: register for onDocumentLoadFinished
    # NEEDS: wire up onURLLoad callback
    # NEEDS: set useragent as a pref: 
    # "DTV/pre-release (http://participatoryculture.org/)"

    def doSelect(self, frame, area):
	print "HTMLDisplay selected"
	assert not self.isDead, "HTMLDisplay selected multiple times"
	self.boundElement = frame.getAreaElement(area, "html")
	print "loading URL %s" % self.initialURL
	# NEEDS: probably some locking
	self.jsbridge.xulAddProgressListener(self.boundElement,
					     self.progressListener)
	self.jsbridge.xulLoadURI(self.boundElement, self.initialURL)
	frame.ensureAreaMode(area, "html")

    def doDeselect(self, frame, area):
	print "HTMLDisplay deselected"
	self.lock.acquire()
	self.isDead = True
	self.jsbridge.xulRemoveProgressListener(self.boundElement,
						self.progressListener)
	self.lock.release()

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

    def ignoreIfDead(func):
	def wrapper(self, *args, **kwargs):
	    self.lock.acquire()
	    try:
		if not self.isDead:
		    func(*args, **kwargs)
	    finally:
		self.lock.release()
	return wrapper

    @deferUntilAfterLoad
    @ignoreIfDead
    def execJS(self, js):
	raise NotImplementedError

    # DOM hooks used by the dynamic template code
    # NEEDS: bind!
    @deferUntilAfterLoad
    @ignoreIfDead
    def addItemAtEnd(self, xml, id):
	self.jsbridge.addElementAtEnd(self.boundElement, xml, id)
	pass
    @deferUntilAfterLoad
    @ignoreIfDead
    def addItemBefore(self, xml, id):
	self.jsbridge.addElementBefore(self.boundElement, xml, id)
	pass
    @deferUntilAfterLoad
    @ignoreIfDead
    def removeItem(self, id):
	self.jsbridge.removeElement(self.boundElement, id)
	pass
    @deferUntilAfterLoad
    @ignoreIfDead
    def changeItem(self, id, xml):
	self.jsbridge.changeElement(self.boundElement, id, xml)
	pass
    @deferUntilAfterLoad
    @ignoreIfDead
    def hideItem(self, id):
	self.jsbridge.hideElement(self.boundElement, id)
	pass
    @deferUntilAfterLoad
    @ignoreIfDead
    def showItem(self, id):
	self.jsbridge.showElement(self.boundElement, id)
	pass
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
	# NEEDS: should keep track if this has already happened
	self.jsbridge.xulAddProgressListener(self.boundElement,
					     self.progressListener)

    def __del__(self):
        self.unlink()

    # NEEDS: right-click menu.
    # Protocol: if type(getContextClickMenu) == "function", call it and
    # pass the DOM node that was clicked on. That returns "URL|description"
    # with blank lines for separators. On a click, force navigation of that
    # frame to that URL, maybe by setting document.location.href.

###############################################################################
###############################################################################
