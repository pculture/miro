import frontend
import app
import tempfile
import os
import re
import threading
from xpcom import components
import time

###############################################################################
#### HTML display                                                          ####
###############################################################################

# NEEDS: we need to cancel loads when we get a transition to a new
# page, and then not loadURI until we get a successful cancellation.
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

    def onStatusChange(self, webProgress, request, status, message):
	pass

class HTMLDisplay (app.Display):
    "Selectable Display that shows a HTML document."

    cookieToInstanceMap = {}

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
	self.elt = None

        # Create a JS bridge component that sends events to the UI thread
        # See http://www.mozilla.org/projects/xpcom/Proxies.html

        jsbridge = components.classes[
            "@participatoryculture.org/dtv/jsbridge;1"].getService(
                 components.interfaces.pcfIDTVJSBridge)

        proxy = components.classes["@mozilla.org/xpcomproxy;1"].getService(
            components.interfaces.nsIProxyObjectManager)
        
        eventQ = components.classes[
            "@mozilla.org/event-queue-service;1"].getService(
            components.interfaces.nsIEventQueueService)

        self.jsbridge = proxy.getProxyForObject(
            eventQ.getSpecialEventQueue(eventQ.UI_THREAD_EVENT_QUEUE),
            components.interfaces.pcfIDTVJSBridge, jsbridge,
            proxy.INVOKE_SYNC | proxy.FORCE_PROXY_CREATION)

        # Save HTML to disk for loading via file: url. We'll delete it
	# when the load has finished in onDocumentLoadFinished.
        (handle, location) = tempfile.mkstemp('.html')
        handle = os.fdopen(handle,"w")
        handle.write(html)
        handle.close()
	self.deleteOnLoadFinished = location
	# For debugging generated HTML, you could uncomment the next
	# two lines.
	print "Logged HTML to %s" % location # NEEDS: RECOMMENT
	self.deleteOnLoadFinished = None # NEEDS: RECOMMENT

	# Translate path into URL and stash until we are ready to display
	# ourselves.
	parts = re.split(r'\\', location)
	self.initialURL = "file:///" + '/'.join(parts)

    # NEEDS: set useragent as a pref: 
    # "DTV/pre-release (http://participatoryculture.org/)"

    # NEEDS: security audit: do we need to make cookies difficult to
    # predict?
    def getEventCookie(self):
	# Can't do this initialization in constructor, because of
	# circular dependency between HTMLDisplay constructor and
	# derived TemplateDisplay constructor. (You need the initial
	# HTML to create the HTMLDisplay, but you need the eventCookie
	# to make the initial HTML.) NEEDS: wish there was a way to
	# put a mutex around this. Is safe in the current
	# implementation, though, because getEventCookie is always
	# called first from the TemplateDisplay constructor.
	if hasattr(self, 'eventCookie'):
	    return self.eventCookie

	# Create cookie and ave this instance in the instance cookie
	# lookup table
	self.eventCookie = str(id(self))
	HTMLDisplay.cookieToInstanceMap[self.eventCookie] = self

	return self.eventCookie

    def getDTVPlatformName(self):
	return "xul"

    @classmethod
    def dispatchEventByCookie(klass, eventCookie, eventURL):
	print "dispatch %s %s" % (eventCookie, eventURL)
	return klass.cookieToInstanceMap[eventCookie].onURLLoad(eventURL)

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
	assert self.elt, "HTMLDisplay methods called out of assumed order"
	self.jsbridge.xulAddProgressListener(self.elt,
					     self.progressListener)

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
#	self.jsbridge.xulSetDocumentBridge(self.elt, "myValXXX2") # NEEDS
	print "--------------- onDocumentLoadFinished"

	if self.deleteOnLoadFinished:
	    try:
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
	print "WARNING ---------- unlink()"
	self.lock.acquire()

	try:
	    if self.eventCookie in HTMLDisplay.cookieToInstanceMap:
		del HTMLDisplay.cookieToInstanceMap[self.eventCookie]

		# Because this is inside the 'if' above, we make sure it only
		# happens once.
		self.jsbridge.xulRemoveProgressListener(self.elt,
							self.progressListener)
	finally:
	    self.lock.release()

    def __del__(self):
        self.unlink()

    # NEEDS: right-click menu.
    # Protocol: if type(getContextClickMenu) == "function", call it and
    # pass the DOM node that was clicked on. That returns "URL|description"
    # with blank lines for separators. On a click, force navigation of that
    # frame to that URL, maybe by setting document.location.href.

###############################################################################
###############################################################################
