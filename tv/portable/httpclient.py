"""httpclient.py 

Implements an HTTP client.  The main way that this module is used is the
grabURL function that that's an asynchronous version of our old grabURL.

A lot of the code here comes from inspection of the httplib standard module.
Some of it was taken more-or-less directly from there.  I (Ben Dean-Kawamura)
believe our clients follow the HTTP 1.1 spec completely, I used RFC2616 as a
reference (http://www.w3.org/Protocols/rfc2616/rfc2616.html).
"""

import errno
import re
import socket
import threading
from urlparse import urlparse, urljoin
from collections import deque

from BitTornado.clock import clock

import config
import downloader
from download_utils import cleanFilename
import eventloop
import util
import sys

# Pass in a connection to the frontend
def setDelegate(newDelegate):
    global delegate
    delegate = newDelegate

def trapCall(function, *args, **kwargs):
    """Do a util.trapCall, where when = 'While talking to the network'"""
    util.trapCall("While talking to the network", function, *args, **kwargs)

class NetworkBuffer(object):
    """Responsible for storing incomming network data and doing some basic
    parsing of it.  I think this is about as fast as we can do things in pure
    python, someday we may want to make it C...
    """
    def __init__(self):
        self.chunks = []
        self.length = 0

    def addData(self, data):
        self.chunks.append(data)
        self.length += len(data)

    def _mergeChunks(self):
        self.chunks = [''.join(self.chunks)]

    def read(self, size=None):
        """Read at most size bytes from the data that has been added to the
        buffer.  """

        self._mergeChunks()
        if size is not None:
            rv = self.chunks[0][:size]
            self.chunks[0] = self.chunks[0][len(rv):]
        else:
            rv = self.chunks[0]
            self.chunks = []
        self.length -= len(rv)
        return rv

    def readline(self):
        """Like a file readline, with several difference:  
        * If there isn't a full line ready to be read we return None.  
        * Doesn't include the trailing line separator.
        * Both "\r\n" and "\n" act as a line ender
        """

        self._mergeChunks()
        split = self.chunks[0].split("\n", 1)
        if len(split) == 2:
            self.chunks[0] = split[1]
            self.length = len(self.chunks[0])
            if split[0].endswith("\r"):
                return split[0][:-1]
            else:
                return split[0]
        else:
            return None

    def unread(self, data):
        """Put back read data.  This make is like the data was never read at
        all.
        """
        self.chunks.insert(0, data)
        self.length += len(data)

    def getValue(self):
        self._mergeChunks()
        return self.chunks[0]

class NotReadyToSendError(Exception):
    pass

class AsyncSocket(object):
    """Socket class that uses our new fangled asynchronous eventloop
    module.
    """

    def __init__(self, closeCallback=None):
        """Create an AsyncSocket.  If closeCallback is given, it will be
        called if we detect that the socket has been closed durring a
        read/write operation.  The arguments will be the AsyncSocket object
        and either socket.SHUT_RD or socket.SHUT_WR.
        """
        self.toSend = ''
        self.readSize = 4096
        self.socket = None
        self.readCallback = None
        self.closeCallback = closeCallback

    def openConnection(self, host, port, callback, errback):
        """Open a connection.  On success, callback will be called with this
        object.
        """
        def finishOpen(address):
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setblocking(0)
            rv = self.socket.connect_ex((address, port))
            if rv not in (0, errno.EINPROGRESS, errno.EWOULDBLOCK):
                trapCall(errback, socket.error((rv, errno.errorcode[rv])))
            trapCall(callback, self)
        eventloop.callInThread(finishOpen, errback, socket.gethostbyname,
                host)

    def closeConnection(self):
        if self.isOpen():
            eventloop.stopHandlingSocket(self.socket)
            self.socket.close()
            self.socket = None

    def isOpen(self):
        return self.socket is not None

    def sendData(self, data):
        """Send data out to the socket when it becomes ready.
        
        NOTE: currently we have no way of detecting when the data gets sent
        out, or if errors happen.
        """

        if not self.isOpen():
            raise ValueError("Socket not connected")
        self.toSend += data
        eventloop.addWriteCallback(self.socket, self.onWriteReady)

    def startReading(self, readCallback):
        """Start reading from the socket.  When data becomes available it will
        be passed to readCallback.  If there is already a read callback, it
        will be replaced.
        """

        if not self.isOpen():
            raise ValueError("Socket not connected")
        self.readCallback = readCallback
        eventloop.addReadCallback(self.socket, self.onReadReady)

    def stopReading(self):
        """Stop reading from the socket."""

        if not self.isOpen():
            raise ValueError("Socket not connected")
        self.readCallback = None
        eventloop.removeReadCallback(self.socket)

    def onWriteReady(self):
        try:
            sent = self.socket.send(self.toSend)
        except socket.error, (code, msg):
            if code not in (errno.EWOULDBLOCK, errno.EINTR):
                if code not in (errno.ECONNRESET, errno.EPIPE):
                    print "WARNING, got unexpected error from send"
                    print "%s: %s" % (errno.errorcode.get(code), msg)
                self.closeConnection()
                if self.closeCallback:
                    trapCall(self.closeCallback, self, socket.SHUT_WR)
        else:
            self.toSend = self.toSend[sent:]
            if self.toSend == '':
                eventloop.removeWriteCallback(self.socket)

    def onReadReady(self):
        try:
            data = self.socket.recv(self.readSize)
        except socket.error, (code, msg):
            if code not in (errno.EWOULDBLOCK, errno.EINTR):
                if code != errno.ECONNREFUSED:
                    print "WARNING, got unexpected error from recv"
                    print "%s: %s" % (errno.errorcode.get(code), msg)
                self.closeConnection()
                if self.closeCallback:
                    trapCall(self.closeCallback, self, socket.SHUT_RD)
        else:
            if data == '':
                if self.closeCallback:
                    trapCall(self.closeCallback, self, socket.SHUT_RD)
            else:
                trapCall(self.readCallback, data)

class ConnectionHandler(object):
    """Base class to handle asynchronous network streams.  It implements a
    simple state machine to deal with incomming data.

    Sending data: Use the sendData() method.

    Reading Data: Add entries to the state dictionary, which maps strings to
    methods.  The state methods will be called when there is data available,
    which can be read from the buffer variable.  The states dictionary can
    contain a None value, to signal that the handler isn't interested in
    reading at that point.  Use changeState() to switch states.

    Subclasses should override tho the handleClose() method to handle the
    socket closing.
    """

    def __init__(self):
        self.buffer = NetworkBuffer()
        self.states = {'initializing': None, 'closed': None}
        self.stream = AsyncSocket(closeCallback=self.closeCallback)
        self.changeState('initializing')

    def openConnection(self, host, port, callback, errback):
        self.host = host
        self.port = port
        def callbackIntercept(asyncSocket):
            trapCall(callback, self)
        self.stream.openConnection(host, port, callbackIntercept, errback)

    def closeConnection(self):
        if self.stream.isOpen():
            self.stream.closeConnection()
        self.changeState('closed')

    def sendData(self, data):
        self.stream.sendData(data)

    def changeState(self, newState):
        self.readHandler = self.states[newState]
        self.state = newState
        self.updateReadCallback()
        # there may be extra data that the last read handler didn't pay
        # attention to, invoke the new readHandler now
        if self.readHandler is not None:
            self.readHandler()

    def updateReadCallback(self):
        if self.readHandler is not None:
            self.stream.startReading(self.handleData)
        elif self.stream.isOpen():
            try:
                self.stream.stopReading()
            except KeyError:
                pass

    def handleData(self, data):
        self.buffer.addData(data)
        self.readHandler()

    def closeCallback(self, stream, type):
        self.handleClose(type)

    def handleClose(self, type):
        """Handle our stream becoming closed.  Type is either socket.SHUT_RD,
        or socket.SHUT_WR.
        """
        raise NotImplementError()

    def __str__(self):
        return "%s -- %s" % (self.__class__, self.state)

class HTTPError(Exception):
    pass
class BadStatusLine(HTTPError):
    pass
class BadHeaderLine(HTTPError):
    pass
class ServerClosedConnection(HTTPError):
    pass
class BadChunkSize(HTTPError):
    pass
class CRLFExpected(HTTPError):
    pass
class PipelinedRequestNeverStarted(HTTPError):
    pass
class BadRedirect(HTTPError):
    pass
class AuthorizationFailed(HTTPError):
    pass
class NotReadyToSendError(Exception):
    pass

class HTTPConnection(ConnectionHandler):
    def __init__(self, closeCallback=None, readyCallback=None):
        super(HTTPConnection, self).__init__()
        self.scheme = 'http'
        self.shortVersion = 0
        self.states['ready'] = None
        self.states['response-status'] = self.onStatusData
        self.states['response-headers'] = self.onHeaderData
        self.states['response-body'] = self.onBodyData
        self.states['chunk-size'] = self.onChunkSizeData
        self.states['chunk-data'] = self.onChunkData
        self.states['chunk-trailer'] = self.onChunkTrailerData
        self.changeState('ready')
        self.idleSince = clock()
        self.unparsedHeaderLine = ''
        self.pipelinedRequest = None
        self.closeCallback = closeCallback
        self.readyCallback = readyCallback
        self.sentReadyCallback = False

    def closeConnection(self):
        super(HTTPConnection, self).closeConnection()
        if self.closeCallback is not None:
            self.closeCallback(self)
            self.closeCallback = None

    def canSendRequest(self):
        return (self.state == 'ready' or 
                (self.state != 'closed' and self.pipelinedRequest is None and
                    not self.willClose))

    def sendRequest(self, callback, errback, method="GET", path='/',
            headers=None):

        if not self.canSendRequest():
            raise NotReadyToSendError()

        if headers is None:
            headers = {}
        else:
            headers = headers.copy()
        headers['Host'] = self.host.encode('idna')
        headers['Accept-Encoding'] = 'identity'

        self.sendRequestData(method, path, headers)
        if self.state == 'ready':
            self.startNewRequest(callback, errback, method, path, headers)
        else:
            self.pipelinedRequest = (callback, errback, method, path, headers)

    def startNewRequest(self, callback, errback, method, path, headers):
        """Called when we're ready to start processing a new request, either
        because one has just been made, or because we've pipelined one, and
        the previous request is done.
        """

        self.callback = callback
        self.errback = errback
        self.method = method
        self.path = path
        self.requestHeaders = headers
        self.headers = {}
        self.version = self.status = self.reason = self.body = None
        self.contentLength = None
        self.willClose = True 
        # Assume we will close, until we get the headers
        self.chunked = False
        self.chunks = []
        self.idleSince = None
        self.sentReadyCallback = False
        self.changeState('response-status')

    def sendRequestData(self, method, path, headers):
        sendOut = []
        sendOut.append('%s %s HTTP/1.1\r\n' % (method, path))
        for header, value in headers.items():
            sendOut.append('%s: %s\r\n' % (header, value))
        sendOut.append('\r\n')
        self.sendData(''.join(sendOut))

    def onStatusData(self):
        line = self.buffer.readline()
        if line is not None:
            self.handleStatusLine(line)
            if self.shortVersion != 9:
                self.changeState('response-headers')
            else:
                self.startBody()

    def onHeaderData(self):
        while self.state == 'response-headers':
            line = self.buffer.readline()
            if line is None:
                break
            self.handleHeaderLine(line)
        
    def onBodyData(self):
        if (self.contentLength is not None and 
                self.buffer.length >= self.contentLength):
            self.body = self.buffer.read(self.contentLength)
            self.finishRequest()

    def onChunkSizeData(self):
        line = self.buffer.readline()
        if line is not None:
            sizeString = line.split(';', 1)[0] # ignore chunk-extensions
            try:
                self.chunkSize = int(sizeString, 16)
            except ValueError:
                self.handleError(BadChunkSize(line))
                return
            if self.chunkSize != 0:
                self.changeState('chunk-data')
            else:
                self.changeState('chunk-trailer')

    def onChunkData(self):
        if self.buffer.length >= self.chunkSize + 2:
            self.chunks.append(self.buffer.read(self.chunkSize))
            crlf = self.buffer.read(2)
            if crlf != "\r\n":
                self.handleError(CRLFExpected(crlf))
            self.changeState('chunk-size')

    def onChunkTrailerData(self):
        # discard all trailers, we shouldn't have any
        line = self.buffer.readline()
        while line is not None:
            if line == '':
                self.finishRequest()
            line = self.buffer.readline()

    def handleStatusLine(self, line):
        try:
            (version, status, reason) = line.split(None, 2)
        except ValueError:
            try:
                (version, status) = line.split(None, 1)
                reason = ""
            except ValueError:
                # empty version will cause next test to fail and status
                # will be treated as 0.9 response.
                version = ""
        if not version.startswith('HTTP/'):
            # assume it's a Simple-Response from an 0.9 server
            self.buffer.unread(line + '\r\n')
            self.version = "HTTP/0.9"
            self.status = 200
            self.reason = ""
            self.shortVersion = 9
        else:
            try:
                status = int(status)
                if status < 100 or status > 599:
                    self.handleError(BadStatusLine(line))
                    return
            except ValueError:
                self.handleError(BadStatusLine(line))
                return
            if version == 'HTTP/1.0':
                self.shortVersion = 10
            elif version.startswith('HTTP/1.'):
                # use HTTP/1.1 code for HTTP/1.x where x>=1
                self.shortVersion = 11
            else:
                self.handleError(BadStatusLine(line))
                return
            self.version = version
            self.status = status
            self.reason = reason

    def handleHeaderLine(self, line):
        if self.unparsedHeaderLine == '':
            if line == '':
                self.startBody()
            elif ':' in line:
                self.parseHeader(line)
            else:
                self.unparsedHeaderLine = line
        else:
            # our last line may have been a continued header, or it may be
            # garbage, 
            if len(line) > 0 and line[0] in (' ', '\t'):
                self.unparsedHeaderLine += line.lstrip()
                if ':' in self.unparsedHeaderLine:
                    self.parseHeader(self.unparsedHeaderLine)
                    self.unparsedHeaderLine = ''
            else:
                msg = "line: %s, next line: %s" % (self.unparsedHeaderLine, 
                        line)
                self.handleError(BadHeaderLine(msg))

    def parseHeader(self, line):
        header, value = line.split(":", 1)
        value = value.strip()
        header = header.lstrip().lower()
        if value == '':
            self.handleError(BadHeaderLine(line))
            return
        if header not in self.headers:
            self.headers[header] = value
        else:
            self.headers[header] += (',%s' % value)

    def startBody(self):
        if ((100 <= self.status <= 199) or self.status in (204, 304) or
                self.method == 'HEAD'):
            self.finishRequest()
        else:
            self.findExpectedLength()
            self.checkChunked()
            self.decideWillClose()
            if not self.chunked:
                self.changeState('response-body')
            else:
                self.changeState('chunk-size')
        self.maybeSendReadyCallback()

    def checkChunked(self):
        te = self.headers.get('transfer-encoding', '')
        self.chunked = (te.lower() == 'chunked')

    def findExpectedLength(self):
        if self.headers.get('transfer-encoding', 'identity') == 'identity':
            try:
                self.contentLength = int(self.headers['content-length'])
            except (ValueError, KeyError):
                pass
            if self.contentLength < 0:
                self.contentLength = None
        else:
            self.contentLength = None

    def decideWillClose(self):
        if self.shortVersion != 11:
            # Close all connections to HTTP/1.0 servers.
            self.willClose = True
        elif 'close' in self.headers.get('connection', ''):
            self.willClose = True
        elif not self.chunked and self.contentLength is None:
            # if we aren't chunked and didn't get a content length, we have to
            # assume the connection will close
            self.willClose = True
        else:
            # HTTP/1.1 connections are assumed to stay open 
            self.willClose = False

    def finishRequest(self):
        if self.chunked:
            body = ''.join(self.chunks)
        else:
            body = self.body

        if self.stream.isOpen():
            if self.willClose:
                self.closeConnection()
                self.changeState('closed')
            elif self.pipelinedRequest is not None:
                self.startNewRequest(*self.pipelinedRequest)
                self.pipelinedRequest = None
            else:
                self.changeState('ready')
                self.idleSince = clock()

        response = self.headers
        response['body'] = body
        for key in ('version', 'status', 'reason', 'method', 'path', 'host',
                'port'):
            response[key] = getattr(self, key)
        trapCall(self.callback, response)
        self.maybeSendReadyCallback()

    def maybeSendReadyCallback(self):
        if (self.readyCallback and self.canSendRequest() and not
                self.sentReadyCallback):
            self.sentReadyCallback = True
            self.readyCallback(self)
        
    def handleClose(self, type):
        oldState = self.state
        self.closeConnection()
        if oldState == 'response-body' and self.contentLength is None:
            self.body = self.buffer.read()
            self.finishRequest()
        else:
            self.errback(ServerClosedConnection())
        if self.pipelinedRequest is not None:
            (callback, errback, method, path, headers) = self.pipelinedRequest
            trapCall(errback, PipelinedRequestNeverStarted())

    def handleError(self, error):
        self.closeConnection()
        trapCall(self.errback, error)

class HTTPSConnection(HTTPConnection):
    # TODO: I think the class hierarchy is a little weird here, but I'm not
    # sure how to fix it.  I would like to have a 

    def openConnection(self, host, port, callback, errback):
        def onConnectionOpen(self):
            self.socket.setblocking(1)
            eventloop.callInThread(onSSLOpen, errback, socket.ssl,
                    self.socket)
        def onSSLOpen(ssl):
            self.socket.setblocking(0)
            self.ssl = ssl
            # finally we can call the actuall callback
            callback(self)
        super(HTTPSConnection, self).openConnection(host, port,
                onConnectionOpen, errback)
        self.host = host
        self.port = port

def parseURL(url):
    (scheme, host, path, params, query, fragment) = urlparse(url)
    # Filter invalid URLs with duplicated ports (http://foo.bar:123:123/baz)
    # which seem to be part of #441.
    if host.count(':') > 1:
        host = host[0:host.rfind(':')]

    if ':' in host:
        host, port = host.split(':')
        port = int(port)
    else:
        host = host
        if scheme == 'https':
            port = 443
        else:
            port = 80

    fullPath = path
    if params:
        fullPath += ';%s' % params
    if query:
        fullPath += '?%s' % query
    return scheme, host, port, fullPath

class HTTPConnectionPool(object):
    """Handle a pool of HTTP connections.

    We use the following stategy to handle new requests:
    * If there is an connection on the server that's ready to send, use that.
    * If we haven't hit our connection limits, create a new request
    * When a connection becomes closed, we look for our last 

    NOTE: "server" in this class means the combination of the scheme, hostname
    and port.
    """

    MAX_CONNECTIONS_PER_SERVER = 2 
    CONNECTION_TIMEOUT = 300
    MAX_CONNECTIONS = 30

    def __init__(self):
        self.pendingRequests = []
        self.activeConnectionCount = 0
        self.freeConnectionCount = 0
        self.connections = {}
        eventloop.addTimeout(60, self.cleanupPool, 
            "Check HTTP Connection Timeouts")

    def _getServerConnections(self, scheme, host, port):
        key = '%s:%s:%s' % (scheme, host, port)
        try:
            return self.connections[key]
        except KeyError:
            self.connections[key] = {'free': set(), 'active': set()}
            return self.connections[key]

    def _popPendingRequest(self):
        """Try to choose a pending request to process.  If one is found,
        remove it from the pendingRequests list and return it.  If not, return
        None.
        """

        if self.activeConnectionCount >= self.MAX_CONNECTIONS:
            return None
        for i in xrange(len(self.pendingRequests)):
            req = self.pendingRequests[i]
            conns = self._getServerConnections(req['scheme'], req['host'], 
                    req['port'])
            if (len(conns['free']) > 0 or 
                    len(conns['active']) < self.MAX_CONNECTIONS_PER_SERVER):
                del self.pendingRequests[i]
                return req
        return None

    def _onConnectionClosed(self, conn):
        conns = self._getServerConnections(conn.scheme, conn.host, conn.port)
        if conn in conns['active']:
            conns['active'].remove(conn)
            self.activeConnectionCount -= 1
        elif conn in conns['free']:
            conns['free'].remove(conn)
            self.freeConnectionCount -= 1
        self.runPendingRequests()

    def _onConnectionReady(self, conn):
        conns = self._getServerConnections(conn.scheme, conn.host, conn.port)
        conns['active'].remove(conn)
        self.activeConnectionCount -= 1
        conns['free'].add(conn)
        self.freeConnectionCount += 1
        self.runPendingRequests()

    def addRequest(self, callback, errback, url, method, headers):
        """Add a request to be run.  The request will run immediately if we
        have a free connection, otherwise it will be queued.
        """

        scheme, host, port, path = parseURL(url)
        req = {
            'callback' : callback,
            'errback': errback,
            'scheme': scheme,
            'host': host,
            'port': port,
            'method': method,
            'path': path,
            'headers': headers,
        }
        self.pendingRequests.append(req)
        self.runPendingRequests()

    def runPendingRequests(self):
        """Find pending requests have a free connection, otherwise it will be
        queued.
        """

        while True:
            req = self._popPendingRequest()
            if req is None:
                return
            conns = self._getServerConnections(req['scheme'], req['host'], 
                    req['port'])
            if len(conns['free']) > 0:
                conn = conns['free'].pop()
                self.freeConnectionCount -= 1
                conn.sendRequest(req['callback'], req['errback'],
                        req['method'], req['path'], req['headers'])
            else:
                conn = self._makeNewConnection(req)
            conns['active'].add(conn)
            self.activeConnectionCount += 1
            connectionCount = (self.activeConnectionCount +
                    self.freeConnectionCount)
            if connectionCount > self.MAX_CONNECTIONS:
                self._dropAFreeConnection()

    def _makeNewConnection(self, req):
        def openConnectionCallback(conn):
            conn.sendRequest(req['callback'], req['errback'],
                    req['method'], req['path'], req['headers'])
        def openConnectionErrback(error):
            conns = self._getServerConnections(req['scheme'], req['host'], 
                    req['port'])
            conns['active'].remove(conn)
            self.activeConnectionCount -= 1
            req['errback'](error)

        if req['scheme'] == 'http':
            conn = HTTPConnection(self._onConnectionClosed,
                    self._onConnectionReady) 
            conn.openConnection(req['host'], req['port'],
                    openConnectionCallback, openConnectionErrback)
        elif req['scheme'] == 'https':
            raise NotImplementError()
        else:
            raise ValueError("Unknown scheme: %s" % req['scheme'])
        return conn

    def _dropAFreeConnection(self):
        # TODO: pick based on LRU
        firstTime = sys.maxint
        toDrop = None

        for conns in self.connections.values():
            for candidate in conns['free']:
                if candidate.idleSince < firstTime:
                    toDrop = candidate
        if toDrop is not None:
            toDrop.closeConnection()

    def cleanupPool(self):
        for serverKey in self.connections.keys():
            conns = self.connections[serverKey]
            toRemove = []
            for conn in conns['free']:
                if conn.idleSince + self.CONNECTION_TIMEOUT <= clock():
                    toRemove.append(conn)
            for x in toRemove:
                conn.closeConnection()
            if len(conns['free']) == len(conns['active']) == 0:
                del self.connections[serverKey]
        eventloop.addTimeout(60, self.cleanupPool, 
            "HTTP Connection Pool Cleanup")

class HTTPClient(object):
    """High-level HTTP client object.  
    
    HTTPClients handle a single HTTP request, but may use several
    HTTPConnections if the server returns back with a redirection status code,
    asks for authorization, etc.  Connections are pooled using an
    HTTPConnectionPool object.
    """

    connectionPool = HTTPConnectionPool() # class-wid connection pool
    MAX_REDIRECTS = 10
    MAX_AUTH_ATTEMPS = 5
    USER_AGENT = "%s/%s (%s)" % \
            (config.get(config.SHORT_APP_NAME),
             config.get(config.APP_VERSION),
             config.get(config.PROJECT_URL))

    def __init__(self, url, callback, errback, method="GET", start=0,
            etag=None, modified=None, findHTTPAuth=None):
        self.url = url
        self.callback = callback
        self.errback = errback
        self.method = method
        self.start = start
        self.etag = etag
        self.modified = modified
        if findHTTPAuth is not None:
            self.findHTTPAuth = findHTTPAuth
        else:
            self.findHTTPAuth = downloader.findHTTPAuth
        self.depth = 0
        self.authAttempts = 0
        self.updateURLOk = True
        self.originalURL = self.updatedURL = self.redirectedURL = url
        self.initHeaders()

    def initHeaders(self):
        self.headers = {}
        if self.start > 0:
            self.headers["Range"] = "bytes="+str(self.start)+"-"
        if not self.etag is None:
            self.headers["If-None-Match"] = self.etag
        if not self.modified is None:
            self.headers["If-Modified-Since"] = self.modified
        self.headers['User-Agent'] = self.USER_AGENT
        self.setAuthHeader()

    def setAuthHeader(self):
        scheme, host, port, path = parseURL(self.url)
        auth = self.findHTTPAuth(host, path)
        if not auth is None:
            authHeader = "%s %s" % (auth.getAuthScheme(), auth.getAuthToken())
            self.headers["Authorization"] = authHeader

    def startRequest(self):
        self.connectionPool.addRequest(self.callbackIntercept,
                self.errbackIntercept, self.url, self.method, self.headers)

    def callbackIntercept(self, response):
        if self.shouldRedirect(response):
            self.handleRedirect(response)
        elif self.shouldAuthorize(response):
            self.handleAuthorize(response)
        else:
            response = self.prepareResponse(response)
            trapCall(self.callback, response)

    def prepareResponse(self, response):
        response['original-url'] = self.originalURL
        response['updated-url'] = self.updatedURL
        response['redirected-url'] = self.redirectedURL
        response['filename'] = self.getFilenameFromResponse(response)
        response['charset'] = self.getCharsetFromResponse(response)
        return response

    def findValueFromHeader(self, header, targetName):
        """Finds a value from a response header that uses key=value pairs with
        the ';' char as a separator.  This is how content-disposition and
        content-type work.
        """
        for part in header.split(';'):
            try:
                name, value = part.split("=", 1)
            except ValueError:
                pass
            else:
                if name.strip().lower() == targetName.lower():
                    return value.strip()
        return None

    def getFilenameFromResponse(self, response):
        try:
            disposition = response['content-disposition']
        except KeyError:
            pass
        else:
            filename = self.findValueFromHeader(disposition, 'filename')
            if filename is not None:
                return cleanFilename(filename)
        match = re.search("([^/]+)/?$", response['path'])
        if match is not None:
            return cleanFilename(match.group(1))
        return 'unknown'

    def getCharsetFromResponse(self, response):
        try:
            contentType = response['content-type']
        except KeyError:
            pass
        else:
            charset = self.findValueFromHeader(contentType, 'charset')
            if charset is not None:
                return charset
        return 'iso-8859-1'

    def errbackIntercept(self, error):
        if isinstance(error, PipelinedRequestNeverStarted):
            # Connection closed before our pipelined reuest started.  RFC
            # 2616 says we should retry
            self.startRequest() 
            # this should give us a new connection, since our last one closed
            return
        trapCall(self.errback, error)

    def shouldRedirect(self, response):
        return (response['status'] in (301, 302, 303, 307) and 
                self.depth < self.MAX_REDIRECTS and 
                'location' in response)

    def handleRedirect(self, response):
        self.depth += 1
        self.url = urljoin(self.url, response['location'])
        self.redirectedURL = self.url
        if response['status'] == 301 and self.updateURLOk:
            self.updatedURL = self.url
        else:
            self.updateURLOk = False
        if response['status'] == 303:
            # "See Other" we must do a get request for the result
            self.method = "GET"
        if 'Authorization' in self.headers:
            del self.headers["Authorization"]
        self.setAuthHeader()
        self.startRequest()

    def shouldAuthorize(self, response):
        return (response['status'] == 401 and 
                self.authAttempts < self.MAX_AUTH_ATTEMPS and
                'www-authorization' in response)

    def handleAuthorize(self, response):
        self.authAttempts += 1
        info = download.msg
        download.close()
        match = re.search("^(.*?)\s+realm\s*=\s*\"(.*?)\"$",
            response['www-authenticate'])
        authScheme = match.expand("\\1")
        realm = match.expand("\\2")
        scheme, host, port, path = parseURL(self.url)
        result = delegate.getHTTPAuth(host, realm)
        if not result is None:
            import downloader
            auth = downloader.HTTPAuthPassword(result[0], result[1], host, 
                    realm, path, authScheme)
            self.setAuthHeader()
            self.startRequest()
        else:
            trapCall(self.errback, AuthorizationFailed())

def grabURL(url, callback, errback, method="GET", start=0, etag=None,
        modified=None, findHTTPAuth=None):
    client = HTTPClient(url, callback, errback, method, start, etag, modified,
            findHTTPAuth)
    client.startRequest()

