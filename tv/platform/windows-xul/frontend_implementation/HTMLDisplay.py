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

# NEEDS: we need to cancel loads when we get a transition to a new
# page, and then not loadURI until we get a successful cancellation.
class ProgressListener:
    _com_interfaces_ = [components.interfaces.nsIWebProgressListener,
			components.interfaces.nsIURIContentListener]

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
	iwpl = components.interfaces.nsIWebProgressListener

	if stateFlags & iwpl.STATE_IS_DOCUMENT:
	    if stateFlags & iwpl.STATE_START:
		# Load of top-level document began
		print "STARTED: %d" % id(request)
		pass
	    if stateFlags & iwpl.STATE_STOP:
		# Load of top-level document finished
		print "FINISHED: %d" % id(request)
		self.boundDisplay.onDocumentLoadFinished()

    def onStartURIOpen(uri):
	print "onStartURIOpen!"
	return True

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
	self.frame = None

	klass = components.classes["@participatoryculture.org/dtv/jsbridge;1"]
	self.jsbridge = klass.getService(components.interfaces.pcfIDTVJSBridge)

        # Save HTML to disk for loading via file: url. We'll delete it
	# when the load has finished in onDocumentLoadFinished.
        (handle, location) = tempfile.mkstemp('.html')
        handle = os.fdopen(handle,"w")
        handle.write(html)
        handle.close()
	self.deleteOnLoadFinished = location
	# For debugging generated HTML, you could uncomment the next
	# two lines.
	print "Logged HTML to %s" % location # NEEDS
	self.deleteOnLoadFinished = None # NEEDS

	# Translate path into URL and stash until we are ready to display
	# ourselves.
	parts = re.split(r'\\', location)
	self.initialURL = "file:///" + '/'.join(parts)

    # NEEDS: register for onDocumentLoadFinished
    # NEEDS: wire up onURLLoad callback
    # NEEDS: set useragent as a pref: 
    # "DTV/pre-release (http://participatoryculture.org/)"

    def getXULElement(self, frame):
	self.lock.acquire()
	try:
	    if not (self.frame is None):
		assert self.frame == frame, "XUL displays cannot be reused"
		return self.elt

	    self.frame = frame
	    self.elt = self.frame.getXULDocument().createElement("browser")
	    self.elt.setAttribute("flex", "1")
	    self.elt.setAttribute("type", "content")
	    self.elt.setAttribute("src", self.initialURL)
	    return self.elt
	finally:
	    self.lock.release()

    def onSelected(self, frame):
	# Technically, there is a race condition here. You apparently
	# can't add a progress listener until the browser element has
	# been inserted in the XUL document, and presumably the 'src'
	# URL doesn't start loading until then. But as the code sits
	# now, there is a small window between when selectDisplay
	# inserts the element in the document and when it calls this
	# function, allowing us to register the listener. This means
	# we might miss the "load finished" event. What we need is a
	# way to simultaneously get the current state of the load and
	# register our handler.
	self.jsbridge.xulAddProgressListener(self.elt,
					     self.progressListener)

#	print "boxObject %s" % self.elt.boxObject
#	q = self.elt.boxObject.queryInterface(components.interfaces.nsIBrowserBoxObject)
#	ds = q.docShell
#	print "docShell %s" % ds
#	wp = ds.queryInterface(components.interfaces.nsIInterfaceRequestor).getInterface(components.interfaces.nsIWebProgress)
#	print "wp %s" % wp
#	wp.addProgressListener(self.progressListener, components.interfaces.nsIWebProgress.NOTIFY_ALL)
#	ds = ds.queryInterface(components.interfaces.nsIDocShell)
#	print "q'd: %s" % ds
#	print "pUCL was %s" % ds.parentURIContentListener
#	ds.parentURIContentListener = self.progressListener

#	old = self.jsbridge.xulGetContentListener(self.elt)
#	print "old %s" % old
#	self.jsbridge.xulSetContentListener(self.elt,
#					    self.progressListener)
#	print "success"

#	window = self.jsbridge.xulGetContentWindow(self.elt)
#	print "got win %s" % window
#	window.myProp = 12
#	window.setAttribute("myProp", "12")
#	print "set prop"

	self.jsbridge.xulSetDocumentBridge(self.elt, "myValXXX1")

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
	self.jsbridge.xulAddElementAtEnd(self.elt, xml, id)
	pass
    @deferUntilAfterLoad
    def addItemBefore(self, xml, id):
	self.jsbridge.xulAddElementBefore(self.elt, xml, id)
	pass
    @deferUntilAfterLoad
    def removeItem(self, id):
	self.jsbridge.xulRemoveElement(self.elt, id)
	pass
    @deferUntilAfterLoad
    def changeItem(self, id, xml):
	self.jsbridge.xulChangeElement(self.elt, id, xml)
	pass
    @deferUntilAfterLoad
    def hideItem(self, id):
	self.jsbridge.xulHideElement(self.elt, id)
	pass
    @deferUntilAfterLoad
    def showItem(self, id):
	self.jsbridge.xulShowElement(self.elt, id)
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
	self.jsbridge.xulSetDocumentBridge(self.elt, "myValXXX2") # NEEDS

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
	# NEEDS: should keep track if this has already happened?
	self.jsbridge.xulAddProgressListener(self.elt,
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
