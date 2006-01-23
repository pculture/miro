import app
import threading
import asyncore
import asynchat
import socket
import re
import resource

###############################################################################
#### HTTP server to deliver pages/events to browsers via XMLHttpRequest    ####
###############################################################################

# document cookie -> (content type, body)
pendingDocuments = {}

# The port we're listening on
serverPort = None
lock = threading.RLock() # and a lock protecting it

def getServerPort():
    lock.acquire()
    try:
        if serverPort is None:
            # Bring up the server.
            httpListener()

        assert serverPort, "httpListener didn't set the port"
        result = serverPort
    finally:
        lock.release()

    print "returning %d for port" % result
    return result

class httpListener(asyncore.dispatcher):
    def __init__(self):
        global serverPort

        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bind( ('127.0.0.1', 0) )
        (myAddr, myPort) = self.socket.getsockname()
        print "Listening on %s %s" % (myAddr, myPort)
        assert not serverPort, "Only one httpListener allowed, please"
        serverPort = myPort
        self.listen(2)

    def handle_accept(self):
        print "accepting conn"
        (conn, address) = self.accept()
        httpServer(conn)

class httpServer(asynchat.async_chat):

    lock = threading.RLock()
    chromeJavascriptStream = None
    chromeJavascriptQueue = []

    def __init__(self, conn):
        asynchat.async_chat.__init__(self, conn)
        self.set_terminator('\r\n')
        self.buffer = ''
        self.gotRequest = None
        self.isChunked = False

        # NEEDS: more convincing random ID
        self.boundary = "DTVDTVDTVDTVDTVDTV%s" % (str(id(self)))

    def collect_incoming_data(self, data):
        self.buffer += data

    def found_terminator(self):
        if self.gotRequest:
            self.buffer = ''
            return
        request = self.buffer
        self.buffer = ''
        self.gotRequest = True
        print "got request '%s'" % request

        ## Mutator stream ##
        match = re.match("GET /dtv/mutators/([^ ]*)", request)
        if match:
            cookie = match.group(1)
            print "My event cookie is %s" % cookie
            self.push("""HTTP/1.0 200 OK
Content-Type: multipart/x-mixed-replace;boundary="%s"

--%s""" % (self.boundary, self.boundary))
            self.isChunked = True
            HTMLDisplay.setMutationOutput(cookie, self)
            return

        ## Chrome-context Javascript stream ##
        match = re.match("GET /dtv/xuljs", request)
        if match:
            self.push("""HTTP/1.0 200 OK
Content-Type: multipart/x-mixed-replace;boundary="%s"

--%s""" % (self.boundary, self.boundary))
            self.isChunked = True
            httpServer.lock.acquire()
            try:
                assert not httpServer.chromeJavascriptStream, \
                    "There can't be two xuljs's"
                httpServer.chromeJavascriptStream = self
                for a in httpServer.chromeJavascriptQueue:
                    print "flush pending xuljs: %s" % a
                    self.push_chunk("text/plain", a)
                httpServer.chromeJavascriptQueue = []
            finally:
                httpServer.lock.release()
            print "Hey look, got xuljs."
            return

        ## Initial HTML ##
        match = re.match("GET /dtv/document/([^ ]*)", request)
        if match:
            cookie = match.group(1)
            print "My document cookie is %s" % cookie
            self.isChunked = False

            assert cookie in pendingDocuments, \
                "bad document request %s to HTMLDisplay server" % \
                cookie
            (contentType, body) = pendingDocuments[cookie]
            del pendingDocuments[cookie]

            self.push("""HTTP/1.0 200 OK
Content-Length: %s
Content-Type: %s

%s""" % (len(body), contentType, body))
            self.close_when_done()

        ## Action ## 
        match = re.match(r"GET /dtv/action/([^ ?]*)\?([^ ]*)", request)
        if match:
            cookie = match.group(1)
            url = match.group(2)
            print "dispatching %s to %s" % (url, cookie)
	    HTMLDisplay.dispatchEventByCookie(cookie, url)
            self.push("""HTTP/1.0 200 OK
Content-Length: 0
Content-Type: text/plain

""")
            self.close_when_done()

        ## Resource file ##
        match = re.match("GET /dtv/resource/([^ ]*)", request)
        if match:
            relativePath = match.group(1)
            fullPath = resource.path(relativePath)
            data = open(fullPath,'rb').read()

            # Guess the content-type.
            contentType = None
            if re.search(".png$", fullPath):
                contentType = "image/png"
            elif re.search(".jpg$", fullPath):
                contentType = "image/jpeg"
            elif re.search(".jpeg$", fullPath):
                contentType = "image/jpeg"
            elif re.search(".gif$", fullPath):
                contentType = "image/gif"
            elif re.search(".css$", fullPath):
                contentType = "text/css"

            self.push("""HTTP/1.0 200 OK
Content-Length: %s
""" % len(data))
            if contentType:
                self.push("""Content-Type: %s
""" % contentType)
            self.push("""
""")
            self.push(data)
            self.close_when_done()

        ## Fell through - bad URL ##
        assert False, ("Invalid request '%s' to HTMLDisplay server" \
                       % request)

    def handle_close(self):
        print "connection closed"
        self.close() # removes self from map and leads to GC

    def push_chunk(self, mimeType, body):
        assert self.isChunked, \
            "push_chunk only works on event-based HTTP sessions"
        self.push("""Content-type: %s

%s
--%s""" % (mimeType, body, self.boundary))

def execChromeJS(js):
    """Execute some Javascript in the context of the privileged top-level
    chrome window. Queued and delivered via a HTTP-based event
    mechanism; no return value is recovered."""
    httpServer.lock.acquire()
    try:
        if httpServer.chromeJavascriptStream:
            print "exec xuljs: %s" % js
            httpServer.chromeJavascriptStream.push_chunk("text/plain", js)
        else:
            print "queue up xuljs: %s" % js
            httpServer.chromeJavascriptQueue.append(js)
    finally:
        httpServer.lock.release()

###############################################################################
#### HTML display                                                          ####
###############################################################################

# Perform escapes needed for Javascript string contents.
def quoteJS(x):
    x = re.compile("\\\\").sub("\\\\", x)  #       \ -> \\
    x = re.compile("\"").  sub("\\\"", x)  #       " -> \"
    x = re.compile("'").   sub("\\'", x)   #       ' -> \'
    x = re.compile("\n").  sub("\\\\n", x) # newline -> \n
    x = re.compile("\r").  sub("\\\\r", x) #      CR -> \r
    return x

def _genMutator(name):
    """Internal: Generates a method that causes the javascript function with
the given name to be called with the arguments passed to the method. Each
argument will be turned into a string and quoted according to Javascript's
requirements. When the method is called, it returns immediately, and the
request goes in a queue."""
    def mutatorFunc(self, *args):
        self.lock.acquire()
        try:
            args = ','.join(['"%s"' % quoteJS(a) for a in args])
            command = "%s(%s);" % (name, args)

            if self.mutationOutput:
                self.mutationOutput.push_chunk("text/plain", command)
            else:
                self.queue.append(command)
        finally:
            self.lock.release()
    return mutatorFunc

class HTMLDisplay (app.Display):
    "Selectable Display that shows a HTML document."

    def __init__(self, html, existingView=None, frameHint=None, areaHint=None):
        """'html' is the initial contents of the display, as a string.
        Remaining arguments are ignored."""

        app.Display.__init__(self)

        # Save the HTML so the server can find it
        pendingDocuments[self.getEventCookie()] = ("text/html", html)

	self.lock = threading.RLock()
        self.mutationOutput = None
        self.queue = []

    def getURL(self):
        """Return the URL to load to see this document."""
        return "http://127.0.0.1:%s/dtv/document/%s" % \
            (self.getServerPort(), self.getEventCookie())

    # The mutation functions.
    addItemAtEnd = _genMutator('addItemAtEnd')
    addItemBefore = _genMutator('addItemBefore')
    removeItem = _genMutator('removeItem')
    changeItem = _genMutator('changeItem')
    hideItem = _genMutator('hideItem')
    showItem = _genMutator('showItem')

    # NEEDS: set useragent as a pref: 
    # "DTV/pre-release (http://participatoryculture.org/)"

    ### Concerning dispatching events via context cookies ###

    cookieToInstanceMap = {}

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

	# Create cookie and add this instance to the instance cookie
	# lookup table
	self.eventCookie = str(id(self))
	HTMLDisplay.cookieToInstanceMap[self.eventCookie] = self

	return self.eventCookie

    def getDTVPlatformName(self):
	return "xul"

    def getServerPort(self):
        port = getServerPort()
        print "--- reporting port %s" % port
        return port

    @classmethod
    def dispatchEventByCookie(klass, eventCookie, eventURL):
	print "dispatch %s %s" % (eventCookie, eventURL)
	return klass.cookieToInstanceMap[eventCookie].onURLLoad(eventURL)

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

    @classmethod
    def setMutationOutput(klass, eventCookie, htmlServer):
	self = klass.cookieToInstanceMap[eventCookie]
        assert not self.mutationOutput, "HTMLDisplay already has its htmlServer"

        self.lock.acquire()
        try:
            self.mutationOutput = htmlServer
            for q in self.queue:
                self.mutationOutput.push_chunk('text/plain', q)
            self.queue = []
        finally:
            self.lock.release()

    ### Concerning destruction ###

    def unlink(self):
	self.lock.acquire()
	try:
	    if self.eventCookie in HTMLDisplay.cookieToInstanceMap:
		del HTMLDisplay.cookieToInstanceMap[self.eventCookie]
            if self.eventCookie in pendingDocuments:
                del pendingDocuments[self.eventCookie]
	finally:
	    self.lock.release()

    def __del__(self):
        self.unlink()

###############################################################################
###############################################################################
