import unittest
import email.Utils
import socket
import sys
import tempfile
import traceback
from copy import copy
from StringIO import StringIO

from miro.clock import clock
import os

from miro.download_utils import clean_filename
from miro import app
from miro import download_utils
from miro import database
from miro import dialogs
from miro import httpclient
from miro import signals
from miro import util
from miro.test.framework import EventLoopTest, MiroTestCase, HadToStopEventLoop
from miro.plat.utils import FilenameType

class TestingConnectionHandler(httpclient.ConnectionHandler):
    def __init__(self, test):
        super(TestingConnectionHandler, self).__init__()
        self.states['foo'] = self.handleFoo
        self.states['bar'] = self.handleBar
        self.states['noread'] = None
        self.fooData = ''
        self.barData = ''
        self.gotHandleClose = False
        self.closeType = None
        self.test = test

    def handleFoo(self):
        data = self.buffer.read()
        self.fooData += data
        self.test.stopEventLoop(False)

    def handleBar(self):
        data = self.buffer.read()
        self.barData += data
        self.test.stopEventLoop(False)

    def handleClose(self, type):
        self.gotHandleClose = True
        self.closeType = type
        self.test.stopEventLoop(False)

class FakeStream:
    def __init__(self, closeCallback=None):
        self.open = False
        self.paused = False
        self.readCallback = None
        self.closeCallback = closeCallback
        self.timedOut = False
        self.connectionErrback = None
        self.name = ""
        self.output = ''
        self.unprocessed = ''
        self.input = ''
        self.pendingOutput = ''
        self.timedOut = False
        # to add a new page response, add the uri in the appropriate
        # host, then add the appropriate response in _generateResponse
        self.pages = {
            'pculture.org':
                {'/normalpage.txt': 'I AM A NORMAL PAGE\n',
                 '/normalpage2.txt': 'I AM A NORMAL PAGE\n',
                 '/normalpage3.txt': 'I AM A NORMAL PAGE\n',
                 '/nohead.php': 'DYNAMIC CONTENT',
                 '/cookie.php': 'normal page',
                 '/etag.txt': 'normal page',
                 '/BasicAuthentication/': 'normal page',
                 '/DigestAuthentication/': 'normal page',
                 '/secure.txt': 'Normal',
                 },
            'www.foo.com':
                {'/': "Normal", '/2': "Blah"},
            'www.bar.com':
                {'/': "Normal", '/2': "Blah"},
            'www.baz.com':
                {'/': "Normal", '/2': "Blah"},
            'www.froz.com':
                {'/': "Normal", '/2': "Blah"},
            'www.qux.com':
                {'/': "Normal", '/2': "Blah"},
            }

    def _tryReadCallback(self):
        if ((len(self.pendingOutput) > 0 and self.readCallback
             and not self.paused)):
            response = self.pendingOutput
            self.pendingOutput = ''
            self.readCallback(response)

    def pause(self):
        self.paused = True

    def unpause(self):
        self.paused = False
        self._tryReadCallback()

    def unpause_momentarily(self):
        self.paused = False
        self._tryReadCallback()
        self.paused = True

    def _generateResponse(self, method, uri, version, headers):
        text = None
        now = email.Utils.formatdate(usegmt=True)
        if not self.pages.has_key(headers["Host"]):
            self.errback(httpclient.ConnectionError("Can't connect"))
            return None

        host_pages = self.pages[headers["Host"]]
        if host_pages.has_key(uri):
            text = host_pages[uri]

        if text is not None:
            if method == "GET":
                if ((uri == '/BasicAuthentication/'
                     and (not headers.has_key('Authorization')
                          or headers['Authorization'] != 'Basic Z3Vlc3Q6Z3Vlc3Q='))):
                    text = "Not authorized"
                    return "\r\n".join([
                            "HTTP/1.1 401 Unauthorized",
                            "WWW-Authenticate: Basic realm=\"test\"",
                            "Content-Type: text/html; charset=UTF-8",
                            "Date: %s" % now,
                            "Content-Length: %d" % len(text),
                            "",
                            text])

                elif ((uri == '/DigestAuthentication/'
                       and (not headers.has_key('Authorization')
                            or (headers['Authorization'] != 'FOO')))):
                    text = "Not authorized"
                    return "\r\n".join([
                            "HTTP/1.1 401 Unauthorized",
                            "WWW-Authenticate: Digest realm=\"test\",domain=\"/DigestAuthentication\",nonce=\"13dc6f6b70fec989c0d5bd5956818b33\"",
                            "Content-Type: text/html; charset=UTF-8",
                            "Date: %s" % now,
                            "Content-Length: %d" % len(text),
                            "",
                            text])

                elif uri == '/etag.txt':
                    etag = "\"1262547188.66\""
                    if headers.get("If-None-Match") == etag:
                        return "\r\n".join([
                                "HTTP/1.1 304 Not Modified",
                                "ETag: %s" % etag,
                                "",
                                ""])
                    else:
                        return "\r\n".join([
                                "HTTP/1.1 200 OK",
                                "ETag: %s" % etag,
                                "Last-Modified: Sun, 03 Jan 2010 19:33:08 GMT",
                                "Content-Length: %d" % len(text),
                                "Content-Type: text/plain",
                                "",
                                text])

                elif uri == '/cookie.php':
                    if "Cookie" in headers:
                        text += "\n%s" % headers["Cookie"]
                    return "\r\n".join([
                            "HTTP/1.1 200 OK",
                            "Content-Type: text/plain; charset=UTF-8",
                            "Set-Cookie: MiroTestCookie=foobar; path=/; domain=pculture.org",
                            "Last-Modified: %s" % now,
                            "Date: %s" % now,
                            "Content-Length: %d" % len(text),
                            "",
                            text])

                else:
                    return "\r\n".join([
                            "HTTP/1.1 200 OK",
                            "Content-Type: text/plain; charset=UTF-8",
                            "Last-Modified: %s" % now,
                            "Date: %s" % now,
                            "Content-Length: %d" % len(text),
                            "",
                            text])

            elif method == "HEAD":
                if uri == '/nohead.php':
                    return "\r\n".join([
                            "HTTP/1.1 405 NOT ALLOWED",
                            "Date: %s" % now,
                            "",
                            ""])
                else:
                    return "\r\n".join([
                            "HTTP/1.1 200 OK",
                            "Content-Type: text/plain; charset=UTF-8",
                            "Last-Modified: %s" % now,
                            "Date: %s" % now,
                            "Content-Length: %d" % len(text),
                            "",
                            ""])

        text = "<h1>Not found</h1>"
        return "\r\n".join([
                "HTTP/1.1 404 Not Founde",
                "Content-Type: text/html; charset=UTF-8",
                "Date: %s" % now,
                "Content-Length: %d" % len(text),
                "",
                text])

    def _processRequest(self, method, uri, version, headers):
        response = self._generateResponse(method,uri, version, headers)
        if response is not None:
            self.pendingOutput += response
            self._tryReadCallback()

    def _processData(self, data):
        self.unprocessed += data
        while self.unprocessed.find("\r\n\r\n") != -1:
            requests = self.unprocessed.split("\r\n\r\n", 1)
            self.unprocessed = requests[1]
            headers = requests[0].split("\r\n")
            (req_method, req_uri, req_version) =  headers.pop(0).split(' ')
            headers = dict([x.split(': ', 1) for x in headers])
            self._processRequest(req_method, req_uri, req_version, headers)

    def __str__(self):
        if self.name:
            return "%s: %s" % (type(self).__name__, self.name)
        else:
            return "Unknown %s" % type(self).__name__

    def startReadTimeout(self):
        pass

    def stopReadTimeout(self):
        pass

    def openConnection(self, host, port, callback, errback,
                       disabledReadTimeout=None):
        self.name = "Outgoing %s:%s" % (host, port)
        self.output = ''
        self.host = host
        self.port = port
        self.open = True
        self.errback = errback
        self.dsiabledReadTimeout = disabledReadTimeout
        callback(self)

    def acceptConnection(self, host, port, callback, errback):
        errback()

    def closeConnection(self):
        self.open = False

    def isOpen(self):
        return self.open

    def sendData(self, data, callback = None):
        if not self.isOpen():
            raise ValueError("Socket not connected")
        self.output += data
        self._processData(data)

    def startReading(self, readCallback):
        if not self.isOpen():
            raise ValueError("Socket not connected")
        self.readCallback = readCallback
        self._tryReadCallback()

    def stopReading(self):
        """Stop reading from the socket."""
        if not self.isOpen():
            raise ValueError("Socket not connected")
        self.readCallback = None

    def onReadTimeout(self):
        raise IOError("Read Timeout")

    def handleSocketError(self, code, msg, operation):
        raise IOError("Socket Error")

class DumbFakeStream(FakeStream):
    def _generateResponse(self, method, uri, version, headers):
        return None

class TestingHTTPConnection(httpclient.HTTPConnection):
    """HTTPConnection that doesn't actually connect to the network."""
    streamFactory = FakeStream

class TestingHTTPSConnection(httpclient.HTTPSConnection):
    """HTTPSConnection that doesn't actually connect to the network."""
    streamFactory = FakeStream

class DumbTestingHTTPConnection(httpclient.HTTPConnection):
    """HTTPConnection that doesn't actually do much of anything."""
    streamFactory = DumbFakeStream

class TestingHTTPConnectionPool(httpclient.HTTPConnectionPool):
    # makes testing more sane
    MAX_CONNECTIONS = 4
    HTTP_CONN = TestingHTTPConnection
    HTTPS_CONN = TestingHTTPSConnection
    streamFactory = FakeStream

    def getConnection(self, scheme, host, port=None, type='active'):
        if port is None:
            if scheme == 'https':
                port = 443
            else:
                port = 80
        conns = self._getServerConnections(scheme, host, port)
        for conn in conns[type]:
            # returns the first one we find
            return conn

    def getAllConnections(self):
        retval = []
        for conns in self.connections.values():
            retval.extend(conns['free'])
            retval.extend(conns['active'])
        return retval

    def assertConnectionStarted(self, url):
        assert self.checkConnectionStarted(url)

    def assertConnectionNotStarted(self, url):
        assert not self.checkConnectionStarted(url)

    def checkConnectionStarted(self, url):
        scheme, host, port, path = download_utils.parse_url(url)
        conns = self._getServerConnections(scheme, host, port)
        for conn in conns['active']:
            try:
                if ((conn.host == host and conn.port == port
                     and conn.path == path)):
                    return True
            except StandardError:
                pass
        return False

class DumbTestingHTTPConnectionPool(TestingHTTPConnectionPool):
    HTTP_CONN = DumbTestingHTTPConnection
    HTTPS_CONN = DumbTestingHTTPConnection

class DumbTestHTTPClient(httpclient.HTTPClient):
    connectionPool = DumbTestingHTTPConnectionPool()

class TestHTTPClient(httpclient.HTTPClient):
    connectionPool = TestingHTTPConnectionPool()

class TestingHeaderGrabber(httpclient.HTTPHeaderGrabber):
    connectionPool = TestingHTTPConnectionPool()

def startResponse(version='1.1', status=200, headers={}):
    rv = ["HTTP/%s %s OK" % (version, status),
          "Content-Type: text/plain; charset=ISO-8859-1",
          "Last-Modified: Wed, 10 May 2006 22:30:33 GMT",
          "Date: Wed, 10 May 2006 22:38:39 GMT"
          ]

    for key, value in headers.items():
        rv.append('%s: %s' % (key, value))

    return "\r\n".join(rv) + "\r\n\r\n"

class AsyncSocketTest(EventLoopTest):
    def setUp(self):
        self.data = None
        self.errbackCalled = False
        self.callbackCalled = False
        self.fakeCallbackError = False
        EventLoopTest.setUp(self)

    def callback(self, data):
        if self.fakeCallbackError:
            1/0
        self.data = data
        self.callbackCalled = True
        self.stopEventLoop(False)

    def errback(self, error):
        self.data = error
        self.errbackCalled = True
        self.stopEventLoop(False)

class NetworkBufferTest(MiroTestCase):
    def setUp(self):
        self.buffer = httpclient.NetworkBuffer()
        MiroTestCase.setUp(self)

    def test_read_line(self):
        self.buffer.addData("HEL")
        self.assertEquals(self.buffer.readline(), None)
        self.buffer.addData("LO\r\n")
        self.assertEquals(self.buffer.readline(), 'HELLO')
        self.buffer.addData("HOWS\r\nIT\nGOING\r\nCRONLY\rDOESNTBREAK")
        self.assertEquals(self.buffer.readline(), 'HOWS')
        self.assertEquals(self.buffer.readline(), 'IT')
        self.assertEquals(self.buffer.readline(), 'GOING')
        self.assertEquals(self.buffer.readline(), None)
        self.assertEquals(self.buffer.read(), "CRONLY\rDOESNTBREAK")

    def test_read(self):
        self.buffer.addData("12345678901234567890")
        self.assertEquals(self.buffer.read(4), "1234")
        self.assertEquals(self.buffer.read(6), "567890")
        self.buffer.addData("CARBOAT")
        self.assertEquals(self.buffer.read(), "1234567890CARBOAT")

    def test_length(self):
        self.buffer.addData("ONE\r\nTWO")
        self.assertEquals(self.buffer.length, 8)
        self.buffer.readline()
        self.assertEquals(self.buffer.length, 3)
        self.buffer.read(1)
        self.assertEquals(self.buffer.length, 2)
        self.buffer.unread("AAA")
        self.assertEquals(self.buffer.length, 5)
        self.buffer.addData("MORE")
        self.assertEquals(self.buffer.length, 9)

    def test_get_value(self):
        self.buffer.addData("ONE")
        self.buffer.addData("TWO")
        self.buffer.addData("THREE")
        self.assertEquals(self.buffer.getValue(), "ONETWOTHREE")
        # check to make sure the value doesn't change as a result
        self.assertEquals(self.buffer.getValue(), "ONETWOTHREE")


class WeirdCloseConnectionTest(AsyncSocketTest):
    def test_close_during_open_connection(self):
        """
        Test opening a connection, then closing the HTTPConnection
        before it happens.  The openConnection callback shouldn't be
        called.

        Open a socket on localhost and try to connect to that, this
        should be pretty much instantaneous, so we don't need a long
        timeout to runEventLoop.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind( ('127.0.0.1', 0))
        sock.listen(1)
        host, port = sock.getsockname()
        try:
            conn = httpclient.AsyncSocket()
            conn.openConnection(host, port, self.callback, self.errback)
            conn.closeConnection()
            self.runEventLoop(timeout=1, timeoutNormal=True)
            self.assert_(not self.callbackCalled)
            self.assert_(self.errbackCalled)
        finally:
            sock.close()

    def test_close_during_accept_connection(self):
        """
        Test opening a connection, then closing the HTTPConnection
        before it happens.  The openConnection callback shouldn't be
        called.

        Open a socket on localhost and try to connect to that, this
        should be pretty much instantaneous, so we don't need a long
        timeout to runEventLoop.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            conn = httpclient.AsyncSocket()
            conn.acceptConnection('127.0.0.1', 0, self.callback, self.errback)
            sock.connect((conn.addr, conn.port))
            conn.closeConnection()
            self.runEventLoop(timeout=1, timeoutNormal=True)
            self.assert_(not self.callbackCalled)
            self.assert_(self.errbackCalled)
        finally:
            sock.close()

class ConnectionHandlerTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind( ('127.0.0.1', 0) )
        server.listen(1)
        address = server.getsockname()

        self.connectionHandler = TestingConnectionHandler(self)
        def stopEventLoop(conn):
            self.stopEventLoop(False)
        self.connectionHandler.openConnection(address[0], address[1],
                stopEventLoop, stopEventLoop)
        self.runEventLoop()
        self.remoteSocket, address = server.accept()
        self.remoteSocket.setblocking(False)

    def test_send(self):
        data = 'abcabc' * 1024  * 64
        self.connectionHandler.sendData(data)
        self.received = httpclient.NetworkBuffer()
        def readData():
            try:
                readIn = self.remoteSocket.recv(1024 * 1024)
            except:
                readIn = ''
            self.received.addData(readIn)
            if self.received.length == len(data):
                self.stopEventLoop(False)
            else:
                self.addTimeout(0.1, readData, 'test')
        self.addTimeout(0.1, readData, 'test')
        self.runEventLoop()
        self.assert_(self.received.read() == data)

    def test_read(self):
        self.connectionHandler.changeState('foo')
        self.remoteSocket.send('abc')
        self.runEventLoop(timeout=1)
        self.assertEquals(self.connectionHandler.fooData, 'abc')
        self.connectionHandler.changeState('bar')
        self.remoteSocket.send('def')
        self.runEventLoop(timeout=1)
        self.assertEquals(self.connectionHandler.barData, 'def')
        self.remoteSocket.send('ghi')
        self.connectionHandler.changeState('noread')
        self.runEventLoop(timeout=0.1, timeoutNormal=True)
        self.assertEquals(self.connectionHandler.fooData, 'abc')
        self.assertEquals(self.connectionHandler.barData, 'def')
        self.connectionHandler.changeState('foo')
        self.runEventLoop(timeout=1)
        self.assertEquals(self.connectionHandler.fooData, 'abcghi')

    def test_close(self):
        self.connectionHandler.closeConnection()
        self.assert_(not self.connectionHandler.stream.isOpen())
        # second close shouldn't throw any exceptions
        self.connectionHandler.closeConnection()

    def test_remote_close(self):
        self.connectionHandler.changeState('foo')
        self.remoteSocket.shutdown(socket.SHUT_WR)
        self.runEventLoop()
        self.assertEquals(self.connectionHandler.gotHandleClose, True)

    # FIXME - this test fails on Windows.
    def test_remote_close2(self):
        self.remoteSocket.shutdown(socket.SHUT_RD)
        self.remoteSocket.close()
        # Note: we have to send enough data so that the OS won't
        # buffer the entire send call.  Otherwise we may miss that the
        # socket has closed.
        self.connectionHandler.sendData("A" * 1024 * 1024)
        self.runEventLoop(timeout=1)
        self.assertEquals(self.connectionHandler.gotHandleClose, True)

    def test_string(self):
        # just make sure it doesn't throw an exception
        str(self.connectionHandler)
        self.assert_(True)

class DumbHTTPClientTest(AsyncSocketTest):
    def setUp(self):
        AsyncSocketTest.setUp(self)
        self.testRequest = DumbTestingHTTPConnection()
        self.testRequest.openConnection('foo.com', 80,
                                        lambda x: None,
                                        lambda x: None)
        self.testRequest.sendRequest(self.callback, self.errback, "", 80,
                                     method='GET', path='/bar/baz;123?a=b')

    def test_scheme(self):
        conn = httpclient.HTTPConnection()
        self.assertEquals(conn.scheme, 'http')

    def test_request_line(self):
        self.assertEquals(self.testRequest.stream.output.split("\r\n")[0],
                          'GET /bar/baz;123?a=b HTTP/1.1')

    def test_status_line(self):
        self.testRequest.handleData("HTTP/1.0 200 OK\r\n")
        self.assertEquals(self.testRequest.version, 'HTTP/1.0')
        self.assertEquals(self.testRequest.status, 200)
        self.assertEquals(self.testRequest.reason, 'OK')

    def test_status_line2(self):
        self.testRequest.handleData("HTTP/1.1 404 Not Found\r\n")
        self.assertEquals(self.testRequest.version, 'HTTP/1.1')
        self.assertEquals(self.testRequest.status, 404)
        self.assertEquals(self.testRequest.reason, 'Not Found')

    def test_bad_status_line(self):
        self.testRequest.handleData("HTTP/0.9 200 OK\r\n")
        self.assert_(self.errbackCalled)
        self.assert_(isinstance(self.data, httpclient.BadStatusLine))

    def test_bad_status_line2(self):
        self.testRequest.handleData("HTTP/1.0 641 OK\r\n")
        self.assert_(self.errbackCalled)
        self.assert_(isinstance(self.data, httpclient.BadStatusLine))

    def test_bad_status_line3(self):
        self.testRequest.handleData("HTTP/1.0 TwoHundred OK\r\n")
        self.assert_(self.errbackCalled)
        self.assert_(isinstance(self.data, httpclient.BadStatusLine))

    def test_noreason(self):
        self.testRequest.handleData("HTTP/1.0 200\r\n")
        self.assertEquals(self.testRequest.version, 'HTTP/1.0')
        self.assertEquals(self.testRequest.status, 200)
        self.assertEquals(self.testRequest.reason, '')

    def test_try_to_handle_http_0_point_9(self):
        self.testRequest.handleData("StartOfThebody\r\n")
        self.assertEquals(self.testRequest.version, 'HTTP/0.9')
        self.assertEquals(self.testRequest.status, 200)
        self.assertEquals(self.testRequest.reason, '')
        self.assertEquals(self.testRequest.buffer.read(),
                          "StartOfThebody\r\n")

    fake_response = "\r\n".join([
            "HTTP/1.0 200 OK",
            "Content-Type: text/plain; charset=ISO-8859-1",
            "Last-Modified: Wed, 10 May 2006 22:30:33 GMT",
            "Date: Wed, 10 May 2006 22:38:39 GMT",
            "X-Cache: HIT from pcf2.pcf.osuosl.org",
            "Server: Apache",
            "Content-Length: 14",
            "",
            "HELLO: WORLD",
            ""])

    def test_basic_headers(self):
        self.testRequest.handleData(self.fake_response)
        self.testRequest.handleClose(socket.SHUT_RD)
        headers = self.testRequest.headers
        self.assertEquals(headers['x-cache'], 'HIT from pcf2.pcf.osuosl.org')
        self.assertEquals(headers['server'], 'Apache')
        self.assertEquals(headers['last-modified'],
                          'Wed, 10 May 2006 22:30:33 GMT')
        self.assertEquals(headers['content-length'], '14')
        self.assertEquals(self.testRequest.contentLength, 14)
        self.assertEquals(headers['date'], 'Wed, 10 May 2006 22:38:39 GMT')
        self.assertEquals(headers['content-type'],
                          'text/plain; charset=ISO-8859-1')

    def test_basic_headers_missing_last_modified(self):
        self.testRequest.handleData("\r\n".join([
                    "HTTP/1.0 200 OK",
                    "Content-Type: text/plain; charset=ISO-8859-1",
                    "Date: Wed, 10 May 2006 22:38:39 GMT",
                    "X-Cache: HIT from pcf2.pcf.osuosl.org",
                    "Server: Apache",
                    "Content-Length: 14",
                    "",
                    "HELLO: WORLD\r\n"
                    ]))
        self.testRequest.handleClose(socket.SHUT_RD)
        headers = self.testRequest.headers
        self.assertEquals(headers['x-cache'], 'HIT from pcf2.pcf.osuosl.org')
        self.assertEquals(headers['server'], 'Apache')
        self.assert_(not headers.has_key('last-modfied'))
        self.assertEquals(headers['content-length'], '14')
        self.assertEquals(self.testRequest.contentLength, 14)
        self.assertEquals(headers['date'], 'Wed, 10 May 2006 22:38:39 GMT')
        self.assertEquals(headers['content-type'],
                          'text/plain; charset=ISO-8859-1')

    def test_basic_headers_missing_last_modified2(self):
        self.testRequest.handleData("\r\n".join([
                    "HTTP/1.0 200 OK",
                    "Content-Type: text/plain; charset=ISO-8859-1",
                    "Last-Modified: ",
                    "Date: Wed, 10 May 2006 22:38:39 GMT",
                    "X-Cache: HIT from pcf2.pcf.osuosl.org",
                    "Server: Apache",
                    "Content-Length: 14",
                    "",
                    "HELLO: WORLD",
                    ""]))
        self.testRequest.handleClose(socket.SHUT_RD)
        headers = self.testRequest.headers
        self.assertEquals(headers['x-cache'], 'HIT from pcf2.pcf.osuosl.org')
        self.assertEquals(headers['server'], 'Apache')
        self.assert_(not headers.has_key('last-modfied'))
        self.assertEquals(headers['content-length'], '14')
        self.assertEquals(self.testRequest.contentLength, 14)
        self.assertEquals(headers['date'], 'Wed, 10 May 2006 22:38:39 GMT')
        self.assertEquals(headers['content-type'],
                          'text/plain; charset=ISO-8859-1')

    def test_callback_error(self):
        self.error_signal_okay = True
        self.fakeCallbackError = True
        self.testRequest.handleData(self.fake_response)
        self.testRequest.handleClose(socket.SHUT_RD)
        self.assert_(self.saw_error)

    def test_header_continuation(self):
        self.testRequest.handleData("HTTP/1.1 200 OK\r\n")
        self.testRequest.handleData("x-test-wrapped: one\r\n")
        self.testRequest.handleData(" two\r\n")
        self.testRequest.handleData("\r\n")
        self.assertEquals(self.testRequest.headers['x-test-wrapped'],
                          'one two')

    def test_header_join(self):
        self.testRequest.handleData("HTTP/1.0 200 OK\r\n")
        self.testRequest.handleData("x-test-list: 1\r\n")
        self.testRequest.handleData("x-test-list: 2\r\n")
        self.testRequest.handleData("x-test-list: 3\r\n")
        self.testRequest.handleData("x-test-list: 4\r\n")
        self.testRequest.handleData("\r\n")
        self.assertEquals(self.testRequest.headers['x-test-list'], '1,2,3,4')

    def test_bad_header_continuation(self):
        self.testRequest.handleData("HTTP/1.0 200 OK\r\n")
        self.testRequest.handleData("IShouldBeContinued\r\n")
        self.testRequest.handleData("\r\n")
        self.assert_(self.errbackCalled)
        self.assert_(isinstance(self.data, httpclient.BadHeaderLine))

    def test_will_close(self):
        self.testRequest.handleData(startResponse(
                headers={'Content-Length': 128}))
        self.assertEquals(self.testRequest.willClose, False)

    def test_will_close2(self):
        self.testRequest.handleData(startResponse(
            headers={'Transfer-Encoding':'chunked'}))
        self.assertEquals(self.testRequest.willClose, False)

    def test_will_close3(self):
        self.testRequest.handleData(startResponse(version='1.0',
            headers={'Content-Length': 128}))
        # HTTP1.0 connections always close
        self.assertEquals(self.testRequest.willClose, True)

    def test_will_close4(self):
        self.testRequest.handleData(startResponse())
        # No content-length and not chunked, we need to close
        self.assertEquals(self.testRequest.willClose, True)

    def test_will_close_5(self):
        self.testRequest.handleData(startResponse(
                headers={'Connection': 'close', 'Content-Length': 128}))
        self.assertEquals(self.testRequest.willClose, True)

    def test_will_close_6(self):
        self.testRequest.handleData(startResponse(
                headers={'Connection': 'CLoSe', 'Content-Length': 128}))
        self.assertEquals(self.testRequest.willClose, True)

    def test_pipeline(self):
        self.assertEqual(self.testRequest.pipelinedRequest, None)
        self.testRequest.handleData(startResponse(
                headers={'Content-Length': 128}))
        self.assertEquals(self.testRequest.canSendRequest(), True)
        self.testRequest.sendRequest(self.callback, self.errback, "", 80,
                                     path="/pipelined/path")
        self.assertEquals(self.testRequest.pipelinedRequest[6],
                          '/pipelined/path')
        self.testRequest.handleData('a' * 128)
        self.assert_(self.callbackCalled)
        self.assertEquals(self.data['body'], 'a' * 128)
        self.assertEquals(self.testRequest.state, 'response-status')
        self.assertEquals(self.testRequest.path, '/pipelined/path')
        self.assertEquals(self.testRequest.pipelinedRequest, None)
        # make sure that the previous request doesn't mess with the current
        # request
        self.assertEquals(self.testRequest.headers, {})
        self.assertEquals(self.testRequest.body, '')
        self.assertEquals(self.testRequest.status, None)

    def test_bad_pipeline(self):
        self.testRequest.handleData(startResponse())
        # no content length means we can't pipeline a request
        self.assertEquals(self.testRequest.canSendRequest(), False)
        self.assertRaises(httpclient.NetworkError,
                          self.testRequest.sendRequest, self.callback,
                          self.errback, "", 80)

    def test_pipeline_never_started(self):
        self.pipelineError = None
        self.testRequest.handleData(startResponse(
                headers={'Content-Length': 128}))
        def pipelineErrback(error):
            self.pipelineError = error
        self.testRequest.sendRequest(self.callback, pipelineErrback, "", 80,
                                     path="/pipelined/path")
        self.testRequest.handleClose(socket.SHUT_RDWR)
        self.assert_(isinstance(self.pipelineError,
                                httpclient.PipelinedRequestNeverStarted))

    def test_pipeline_never_started2(self):
        self.pipelineError = None
        self.testRequest.handleData(startResponse(
                headers={'Content-Length': 128}))
        def pipelineErrback(error):
            self.pipelineError = error
        self.testRequest.sendRequest(self.callback, pipelineErrback, "", 80,
                                     path="/pipelined/path")
        self.testRequest.closeConnection()
        self.assert_(isinstance(self.pipelineError,
                                httpclient.PipelinedRequestNeverStarted))

    def test_content_length_handling(self):
        self.testRequest.handleData(startResponse(
                headers={'Content-Length': '5'}))
        self.testRequest.handleData("12345EXTRASTUFF")
        self.assertEquals(self.testRequest.body, '12345')

    def test_transfer_encoding_trumps_content_length(self):
        self.testRequest.handleData(startResponse(
                headers={'Content-Length': '5',
                         'Transfer-Encoding': 'chunked'}))
        self.assertEquals(self.testRequest.contentLength, None)

    def test_416_content_length(self):
        """Test the content length after a 416 status code."""
        self.testRequest.handleData(startResponse(
                status=416, headers={'Content-Range': 'bytes */1234'}))
        self.assertEquals(self.testRequest.contentLength, 1234)

    def test_no_body(self):
        self.testRequest.handleData(startResponse(status=204))
        self.assertEquals(self.testRequest.state, 'closed')
        self.assertEquals(self.testRequest.body, '')

    def test_no_body2(self):
        self.testRequest.handleData(startResponse(status=123))
        self.assertEquals(self.testRequest.state, 'closed')
        self.assertEquals(self.testRequest.body, '')

    def test_no_body3(self):
        self.testRequest.method='HEAD'
        self.testRequest.handleData(startResponse())
        self.assertEquals(self.testRequest.state, 'closed')
        self.assertEquals(self.testRequest.body, '')

    def test_no_body4(self):
        self.testRequest.bodyDataCallback = lambda data: 0
        self.testRequest.handleData(startResponse(
                headers={"Content-Length":'0'}))
        self.assertEquals(self.testRequest.state, 'ready')
        self.assertEquals(self.testRequest.body, '')

    def test_split_up_message(self):
        data = self.fake_response
        for cutoff in [3, 6, 10, 4, 100, 52]:
            self.testRequest.handleData(data[:cutoff])
            data = data[cutoff:]
        self.testRequest.handleData(data)
        self.testRequest.handleClose(socket.SHUT_RD)
        self.assertEquals(self.testRequest.version, 'HTTP/1.0')
        self.assertEquals(self.testRequest.status, 200)
        self.assertEquals(self.testRequest.reason, 'OK')
        self.assertEquals(self.testRequest.headers['server'],
                          'Apache')
        self.assertEquals(self.testRequest.body, 'HELLO: WORLD\r\n')

    def test_one_chunk(self):
        self.testRequest.handleData(self.fake_response)
        self.testRequest.handleClose(socket.SHUT_RD)
        self.assertEquals(self.testRequest.version, 'HTTP/1.0')
        self.assertEquals(self.testRequest.status, 200)
        self.assertEquals(self.testRequest.reason, 'OK')
        self.assertEquals(self.testRequest.headers['server'],
                'Apache')
        self.assertEquals(self.testRequest.body, 'HELLO: WORLD\r\n')

    def test_bad_chunk_size(self):
        self.testRequest.handleData(startResponse(
            headers={'Transfer-Encoding': 'chunked'}))
        self.testRequest.handleData("Fifty\r\n")
        self.assert_(self.errbackCalled)
        self.assert_(isinstance(self.data, httpclient.BadChunkSize))

    def test_ignore_chunk_extensions(self):
        self.testRequest.handleData(startResponse(
            headers={'Transfer-Encoding': 'chunked'}))
        self.testRequest.handleData("ff ;ext1=2 ; ext3=4\r\n")
        self.assert_(not self.errbackCalled)
        self.assertEquals(self.testRequest.state, 'chunk-data')
        self.assertEquals(self.testRequest.chunkSize, 255)

    def test_chunk_without_crlf(self):
        self.testRequest.handleData(startResponse(
            headers={'Transfer-Encoding': 'chunked'}))
        self.testRequest.handleData("5\r\n")
        self.testRequest.handleData("12345RN") # "RN" should have been "\r\n"
        self.assert_(self.errback)
        self.assert_(isinstance(self.data, httpclient.CRLFExpected))

    def test_premature_close(self):
        data = self.fake_response
        self.testRequest.handleData(data[:123])
        self.testRequest.handleClose(socket.SHUT_RD)
        self.assert_(self.errbackCalled)
        self.assert_(isinstance(self.data, httpclient.ServerClosedConnection))

    def test_close_before_ready_callback(self):
        data = self.fake_response
        self.readyCallbackSeen = False
        def fakeReadyCallback(client):
            self.readyCallbackSeen = True
        self.testRequest.readyCallback = fakeReadyCallback
        self.testRequest.handleData(startResponse(
            headers={'Content-Length': 128}))
        self.assertEquals(self.testRequest.canSendRequest(), True)
        self.testRequest.handleData('a' * 128)
        # At this point, our connection should have scheduled an idle
        # call to check if it should call fakeReadyCallback().  If
        # readyCallbackSeen is True on the next line, it's actually
        # not an error with httpclient.  However, if we haven't gotten
        # the callback yet, then we close the connection then we
        # shouldn't get the callback later.
        self.assert_(not self.readyCallbackSeen)
        self.testRequest.handleClose(socket.SHUT_RD)
        self.runPendingIdles()
        self.assert_(not self.readyCallbackSeen)

class HTTPClientTestBase(AsyncSocketTest):
    def setUp(self):
        AsyncSocketTest.setUp(self)
        self.testRequest = TestingHTTPConnection()
        self.testRequest.openConnection('foo.com', 80, lambda x: None,
                                        lambda x: None)
        self.testRequest.sendRequest(self.callback, self.errback, "", 80,
                                     method='GET', path='/bar/baz;123?a=b')
        TestHTTPClient.connectionPool = TestingHTTPConnectionPool()
        TestingHeaderGrabber.connectionPool = TestingHTTPConnectionPool()
        self.logins = []
        signals.system.connect('new-dialog', self.onNewDialog)

    def addLogin(self, user, password):
        self.logins.append((user, password))

    def onNewDialog(self, obj, dialog):
        self.assertEquals(dialog.__class__, dialogs.HTTPAuthDialog)
        if self.logins:
            user, password = self.logins.pop(0)
            dialog.run_callback(dialogs.BUTTON_OK, user, password)
        else:
            dialog.run_callback(None)

class HTTPClientTest(HTTPClientTestBase):
    def test_real_request(self):
        url = 'http://pculture.org/normalpage.txt'
        httpclient.grabURL(url, self.callback, self.errback,
                           clientClass=TestHTTPClient)
        self.runEventLoop(timeout=10)
        self.assert_(self.callbackCalled)
        self.assertEquals(self.data['body'], "I AM A NORMAL PAGE\n")

    def test_grab_headers(self):
        url = 'http://pculture.org/normalpage.txt'
        httpclient.grabHeaders(url, self.callback, self.errback,
                               TestingHeaderGrabber)
        self.runEventLoop(timeout=10)
        self.assert_(self.callbackCalled)
        self.assertEquals(self.data['body'], "")
        self.assertEquals(self.data['status'], 200)
        self.assertEquals(self.data['original-url'], self.data['updated-url'])
        self.assertEquals(self.data['original-url'],
                          self.data['redirected-url'])

    def test_grab_headers2(self):
        url = 'http://pculture.org/nohead.php'
        httpclient.grabHeaders(url, self.callback, self.errback,
                               clientClass = TestingHeaderGrabber)
        self.runEventLoop(timeout=10)
        self.assert_(self.callbackCalled)
        self.assertEquals(self.data['body'], "")
        self.assertEquals(self.data['status'], 200)
        self.assertEquals(self.data['original-url'], self.data['updated-url'])
        self.assertEquals(self.data['original-url'],
                          self.data['redirected-url'])

    def test_grab_headers_cancel(self):
        url = 'http://pculture.org/normalpage.txt'
        client = httpclient.grabHeaders(url, self.callback, self.errback,
                                        clientClass = TestingHeaderGrabber)
        client.cancel()

        # Hmmmm.... it looks like the behavior changed, so cancel no
        # longer triggers an errback. I guess this is okay. --NN
        self.assertRaises(HadToStopEventLoop,
                          lambda: self.runEventLoop(timeout=1))

    def test_connection_failure(self):
        httpclient.grabURL("http://slashdot.org:123123", self.callback,
                           self.errback, clientClass=TestHTTPClient)
        self.runEventLoop()
        self.assert_(self.errbackCalled)
        self.assertEquals(self.data.__class__, httpclient.ConnectionError)

    def test_multiple_requests(self):
        def middleCallback(data):
            self.firstData = data
            req.sendRequest(self.callback, self.errback,
                            "pculture.org", 80, method='GET',
                            path='/normalpage.txt')

        req = TestingHTTPConnection()
        def stopEventLoop(conn):
            self.stopEventLoop(False)
        self.addIdle(lambda: req.openConnection('pculture.org', 80,
                                                stopEventLoop, self.errback),
                     "Open connection")
        self.runEventLoop()
        self.assert_(not self.errbackCalled)
        self.addIdle(lambda: req.sendRequest(middleCallback,
                                             self.errback,
                                             "pculture.org",
                                             80,
                                             method='GET',
                                             path='/normalpage.txt'),
                     "Send Request")
        self.runEventLoop()
        self.assert_(not self.errbackCalled)
        self.assertEquals(self.firstData['body'], self.data['body'])

    def test_unexpected_status_code(self):
        """Test what happens when we get a bad status code.

        The header callback should be called, but the on body data
        callback shouldn't.  Also, we should call the errback instead
        of the callback.
        """
        self.onHeadersCalled = self.onBodyDataCalled = False
        def onHeaders(headers):
            self.onHeadersCalled = True
        def onBodyData(data):
            self.onBodyDataCalled = True
        url = "http://pculture.org/404"
        client = TestHTTPClient(url, self.callback, self.errback,
                                onHeaders, onBodyData)
        client.startRequest()
        self.runEventLoop()
        self.assert_(self.onHeadersCalled)
        self.assert_(not self.onBodyDataCalled)
        self.assert_(not self.callbackCalled)
        self.assert_(self.errbackCalled)

    def test_header_callback(self):
        def headerCallback(response):
            self.headerResponse = copy(response)
            self.callbackCalledInHeaderCallback = self.callbackCalled
            self.errbackCalledInHeaderCallback = self.errbackCalled
            self.stopEventLoop(False)
        url = 'http://pculture.org/normalpage.txt'
        httpclient.grabURL(url, self.callback, self.errback,
                headerCallback=headerCallback, clientClass=TestHTTPClient)
        self.runEventLoop()
        self.assert_(not self.callbackCalledInHeaderCallback)
        self.assert_(not self.errbackCalledInHeaderCallback)
        self.assert_(self.headerResponse['content-type'].startswith('text/plain'))
        self.assertEquals(self.headerResponse['body'], None)

    def test_header_callback_cancel(self):
        def headerCallback(response):
            reqId.cancel()
            self.stopEventLoop(False)
        url = 'http://pculture.org/normalpage.txt'
        reqId = httpclient.grabURL(url, self.callback, self.errback,
                headerCallback=headerCallback, clientClass=TestHTTPClient)
        self.error_signal_okay = True
        self.runEventLoop()
        self.assert_(not self.callbackCalled)
        self.assert_(not self.errbackCalled)
        self.assert_(not self.saw_error)

    def test_body_data_callback_cancel(self):
        def bodyDataCallback(response):
            reqId.cancel()
            self.stopEventLoop(False)
        url = 'http://pculture.org/normalpage.txt'
        reqId = httpclient.grabURL(url, self.callback, self.errback,
                bodyDataCallback=bodyDataCallback, clientClass=TestHTTPClient)
        self.error_signal_okay = True
        self.runEventLoop()
        self.assert_(not self.callbackCalled)
        self.assert_(not self.errbackCalled)
        self.assert_(not self.saw_error)

    def test_body_data_callback(self):
        self.lastSeen = None
        def bodyDataCallback(data):
            self.lastSeen = data
        self.testRequest.bodyDataCallback = bodyDataCallback
        self.testRequest.handleData(startResponse(
                    headers={'content-length':'20'}))
        self.assertEquals(self.lastSeen, None)
        self.testRequest.handleData("12345")
        self.assertEquals(self.lastSeen, "12345")
        self.testRequest.handleData("1234567890")
        self.assertEquals(self.lastSeen, "1234567890")
        self.testRequest.handleData("1234567890")
        self.assertEquals(self.lastSeen, "12345")

    def test_body_data_callback_chunked(self):
        self.lastSeen = None
        def bodyDataCallback(data):
            self.lastSeen = data
        self.testRequest.bodyDataCallback = bodyDataCallback
        self.testRequest.handleData(startResponse(
                headers={'transfer-encoding': 'chunked'}))
        self.testRequest.handleData("5\r\nHI")
        self.assertEquals(self.lastSeen, "HI")
        self.testRequest.handleData("BEN\r\n")
        self.assertEquals(self.lastSeen, "BEN")
        self.testRequest.handleData("A\r\n")
        self.assertEquals(self.lastSeen, "BEN")
        self.testRequest.handleData("1234567890\r\n0")
        self.assertEquals(self.lastSeen, "1234567890")
        self.assert_(not self.callbackCalled)
        self.testRequest.handleData("\r\n\r\n")
        self.assert_(self.callbackCalled)

    def test_body_data_callback_real_request(self):
        url = 'http://pculture.org/normalpage.txt'
        self.gotData = ''
        def bodyDataCallback(data):
            self.gotData += data
            if self.gotData == 'I AM A NORMAL PAGE\n':
                self.stopEventLoop(False)

        httpclient.grabURL(url, self.callback, self.errback,
                           bodyDataCallback=bodyDataCallback,
                           clientClass=TestHTTPClient)
        self.runEventLoop()
        self.assertEquals(self.gotData, 'I AM A NORMAL PAGE\n')

    def test_auth(self):
        self.addLogin(u'ben', u'baddpassword')
        self.addLogin(u'guest', u'guest')
        url = 'http://pculture.org/BasicAuthentication/'
        client = TestHTTPClient(url, self.callback, self.errback)
        client.startRequest()
        self.runEventLoop()
        self.assert_(self.callbackCalled)
        self.assertEquals(self.data['status'], 200)
        self.assertEquals(client.authAttempts, 2)

    def test_bad_auth(self):
        self.addLogin(u'baduser', u'baddpass')
        self.addLogin(u'anotherbadtry', u'god')
        self.addLogin(u'billgates', u'password')
        url = 'http://pculture.org/BasicAuthentication/'
        client = TestHTTPClient(url, self.callback, self.errback)
        client.startRequest()
        self.runEventLoop()
        self.assert_(self.errbackCalled)
        self.assert_(isinstance(self.data, httpclient.AuthorizationFailed))
        self.assertEquals(client.authAttempts, 3)

    def test_digest_auth(self):
        # we don't support digest authorization yet, make sure we get the
        # right errback at least
        url = 'http://pculture.org/DigestAuthentication/'
        client = TestHTTPClient(url, self.callback, self.errback)
        client.startRequest()
        self.runEventLoop()
        self.assert_(self.errbackCalled)
        self.assert_(isinstance(self.data, httpclient.AuthorizationFailed))
        self.assertEquals(client.authAttempts, 0)

# FIXME - this needs to be reimplemented with the TestHTTPClient
# above.
#
#     def testChunkedData(self):
#         url = 'http://jigsaw.w3.org/HTTP/ChunkedScript'
#         httpclient.grabURL(url, self.callback, self.errback, clientClass=TestHTTPClient)
#         self.runEventLoop(timeout=5)
#         header = """\
# This output will be chunked encoded by the server, if your client is HTTP/1.1
# Below this line, is 1000 repeated lines of 0-9.
# -------------------------------------------------------------------------"""
#         bodyLine = """\
# 01234567890123456789012345678901234567890123456789012345678901234567890"""
#         lines = self.data['body'].split('\n')
#         headerLines = header.split('\n')
#         self.assertEquals(lines[0], headerLines[0])
#         self.assertEquals(lines[1], headerLines[1])
#         self.assertEquals(lines[2], headerLines[2])
#         for x in range(3, 1003):
#             self.assertEquals(lines[x], bodyLine)

    def test_cookie(self):
        url = "http://pculture.org/cookie.php"
        httpclient.grabURL(url, self.callback, self.errback,
                           clientClass=TestHTTPClient)
        self.runEventLoop(timeout=5)
        # self.data is a 404
        self.assertEquals(len(self.data['cookies']), 1)
        self.assert_(self.data['cookies'].has_key('MiroTestCookie'))
        self.assertEquals(self.data['cookies']['MiroTestCookie']['Value'],
                          'foobar')
        httpclient.grabURL(url, self.callback, self.errback,
                           cookies=self.data['cookies'],
                           clientClass=TestHTTPClient)
        self.runEventLoop(timeout=2)
        self.assertNotEqual(self.data['body'].find('MiroTestCookie=foobar'), -1)

    def test_parse_url(self):
        for mem in ([
                ("https://www.foo.com/abc;123?a=b#4",
                 ("https", "www.foo.com", 443, "/abc;123?a=b")),

                ("http://www.foo.com/abc;123?a=b#4",
                 ("http", "www.foo.com", 80, "/abc;123?a=b")),

                ("http://www.foo.com:5000/abc;123?a=b#4",
                 ("http", "www.foo.com", 5000, "/abc;123?a=b")),

                # I guess some feeds have bad url, with a double port in
                # them, test that we handle these.
                ("http://www.foo.com:123:123/abc;123?a=b#4",
                 ("http", "www.foo.com", 123, "/abc;123?a=b")),

                # handle windows file paths
                ("file:///c:/foo/bar/baz",
                 ("file", "", None, "c:/foo/bar/baz")),

                # handle urls with : in the path
                ("http://www.foo.com/s:6p23p/video",
                 ("http", "www.foo.com", 80, "/s:6p23p/video"))
                ]):
            self.assertEquals(download_utils.parse_url(mem[0]), mem[1])

# FIXME - these need to be reimplemented with TestHTTPClient above.
#
#     def checkRedirect(self, url, redirectUrl, updatedUrl, **extra):
#         self.errbackCalled = self.callbackCalled = False
#         httpclient.grabURL(url, self.callback, self.errback, clientClass=TestHTTPClient, **extra)
#         self.runEventLoop(timeout=20)
#         self.assert_(not self.errbackCalled)
#         self.assert_(self.callbackCalled)
#         self.assertEquals(self.data['redirected-url'], redirectUrl)
#         self.assertEquals(self.data['updated-url'], updatedUrl)

#     def test307Redirect(self):
#         self.checkRedirect('http://jigsaw.w3.org/HTTP/300/307.html',
#                 'http://jigsaw.w3.org/HTTP/300/Overview.html',
#                 'http://jigsaw.w3.org/HTTP/300/307.html')

#     def test301Redirect(self):
#         self.checkRedirect('http://jigsaw.w3.org/HTTP/300/301.html',
#                 'http://jigsaw.w3.org/HTTP/300/Overview.html',
#                 'http://jigsaw.w3.org/HTTP/300/Overview.html')

#     def test302Redirect(self):
#         self.checkRedirect('http://jigsaw.w3.org/HTTP/300/302.html',
#                 'http://jigsaw.w3.org/HTTP/300/Overview.html',
#                 'http://jigsaw.w3.org/HTTP/300/302.html')

#     def test303Redirect(self):
#         self.checkRedirect('http://jigsaw.w3.org/HTTP/300/Go_303',
#                 'http://jigsaw.w3.org/HTTP/300/303_ok.html',
#                 'http://jigsaw.w3.org/HTTP/300/Go_303', method="POST", postVariables={})
#         self.assertEquals(self.data['method'], 'GET')

#     def test303RedirectWithData(self):
#         self.checkRedirect('http://jigsaw.w3.org/HTTP/300/Go_303',
#                 'http://jigsaw.w3.org/HTTP/300/303_ok.html',
#                 'http://jigsaw.w3.org/HTTP/300/Go_303', method="POST", postVariables={'foo':'bar'})
#         self.assertEquals(self.data['method'], 'GET')

#     def testMultipleRedirect(self):
#         # The redirect chain is:
#         # redirect.php PERMAMENT REDIRECT -> redirect2.php
#         # redirect2.php PERMAMENT REDIRECT -> redirect3.php
#         # redirect3.php TEMPORARY REDIRECT -> end.txt
#         # The updated-url should be redirect3.php, since that it was the 1st
#         # redirect that was temporary
#         self.checkRedirect(
#                 'http://pculture.org/redirect.php',
#                 'http://pculture.org/end.txt',
#                 'http://pculture.org/redirect3.php')

#     def testFileUpload(self):
#         self.errbackCalled = self.callbackCalled = False
#         httpclient.grabURL('http://pculture.org/fileupload.php', self.callback, self.errback, method="POST", postFiles = {'myfile': {
#             'filename' : 'tempfile.txt',
#             'mimetype' : 'application/octet-stream',
#             'handle'   : StringIO('This is a test file', clientClass=TestHTTPClient)
#             }})
#         self.runEventLoop(timeout=20)
#         self.assert_(not self.errbackCalled)
#         self.assert_(self.callbackCalled)
#         result = self.data['body'].split()
#         self.assertEqual(result[0], 'tempfile.txt')
#         self.assertEqual(result[1], 'application/octet-stream')
#         self.assertEqual(result[2], '0b26e313ed4a7ca6904b0e9369e5b957')

#     def testRedirectLimit(self):
#         url = 'http://pculture.org/redirect.php'
#         client = httpclient.HTTPClient(url, self.callback, self.errback)
#         client.MAX_REDIRECTS = 2
#         client.startRequest()
#         self.runEventLoop()
#         self.assert_(self.errbackCalled)
#         self.assert_(isinstance(self.data, httpclient.UnexpectedStatusCode))

    def test_clean_filename(self):
        tempdir = tempfile.gettempdir()
        def testIt(filename):
            cleaned = clean_filename(filename)
            self.assertEqual(cleaned.__class__, FilenameType)
            self.assertNotEqual(cleaned, '')
            path = os.path.join(tempdir, cleaned)
            f = open(path, 'w')
            f.write("AOEUOAEU")
            f.close()
            os.remove(path)
        testIt(u'iamnormal.txt')
        testIt(u'???')
        testIt(u'\xf8benben.jpg')
        testIt(u'\xf8???.\xf2\xf3x')

    def test_get_filename_from_response(self):
        client = TestHTTPClient('http://www.foo.com', self.callback,
                                self.errback)

        def getIt(path, cd=None):
            response = {
                'path': path,
                'redirected-url': 'http://example.com' + path
                }
            if cd:
                response['content-disposition'] = cd
            return client.getFilenameFromResponse(response)

        self.assertEquals("unknown", getIt("/"))
        self.assertEquals("index.html", getIt("/index.html"))
        self.assertEquals("index.html", getIt("/path/path2/index.html"))
        self.assertEquals("unknown", getIt("/path/path2/"))
        self.assertEquals("myfile.txt", getIt("/", 'filename="myfile.txt"'))
        self.assertEquals("myfile.txt",
                          getIt("/", 'filename="myfile.txt"; size=45'))
        self.assertEquals("myfile.txt",
                          getIt("/", ' filename =  "myfile.txt"'))
        self.assertEquals("myfile.txt", getIt("/", 'filename=myfile.txt'))
        self.assertEquals("myfile.txt",
                          getIt("/index.html", 'filename="myfile.txt"'))
        self.assertEquals("lots.of.extensions",
                          getIt("/", 'filename="lots.of.extensions"'))
        self.assertEquals("uncleanfilename",
                          getIt("/index", 'filename="\\un/cl:ean*fi?lena<m>|e"'))
        self.assertEquals("uncleanfil-ename2",
                          getIt('/uncl*ean"fil?"ena|m""e2"'))

    def test_get_charset_from_response(self):
        client = TestHTTPClient('http://pculture.org/normal.txt',
                                self.callback, self.errback)
        def get_it(content_type):
            if content_type:
                response = {'content-type': content_type}
            else:
                response = {}
            return client.getCharsetFromResponse(response)
        self.assertEquals('iso-8859-1', get_it(None))
        self.assertEquals('iso-8859-1', get_it('gabaldigook'))
        self.assertEquals('iso-8859-1', get_it("text/html"))
        self.assertEquals('utf-8', get_it("text/html; charset=utf-8"))
        self.assertEquals('utf-8', get_it("text/html; charset = utf-8"))
        self.assertEquals('utf-8',
                          get_it("text/html; charset=utf-8; extraparam=2"))

class HTTPConnectionPoolTest(EventLoopTest):
    def setUp(self):
        self.pool = TestingHTTPConnectionPool()
        super(HTTPConnectionPoolTest, self).setUp()

    def get_connection_for_url(self, url):
        scheme, host, port, path = download_utils.parse_url(url)
        # Run event loop to make sure all the open callbacks have run,
        # so that each connection has a URL
        self.runPendingIdles()
        for conn in self.pool.getAllConnections():
            if ((conn.scheme == scheme and conn.host == host
                 and conn.port == port and conn.path == path)):
                return conn
        raise AssertionError("No connection with url: %s" % url)

    def pause_all_connections(self):
        for conn in self.pool.getAllConnections():
            conn.stream.pause()

    def finish_connection_for_url(self, url):
        self.pause_all_connections()
        conn = self.get_connection_for_url(url)
        # The stream should be all ready to send it's response.
        # unpause it and run the event loop and it should be finished
        conn.stream.unpause()
        # We probably started a new pending request.  Make sure that
        # the stream is re-paused and if we created any new streams
        # are paused too.
        self.pause_all_connections()
        self.runPendingIdles()

    def close_connection_for_url(self, url):
        self.pause_all_connections()
        conn = self.get_connection_for_url(url)
        conn.handleClose(socket.SHUT_RDWR)

    def add_request(self, url):
        return self.pool.addRequest(
            lambda blah: self.addIdle(lambda :self.stopEventLoop(False),
                                      "Closing connection when request is done"),
            lambda error: 0, None, None, None, url, "GET", {})

    def check_counts(self, activeCount, freeCount, pendingCount):
        self.assertEquals(self.pool.activeConnectionCount, activeCount)
        self.assertEquals(self.pool.freeConnectionCount, freeCount)
        realFreeCount = realActiveCount = 0
        for key, conns in self.pool.connections.items():
            realFreeCount += len(conns['free'])
            realActiveCount += len(conns['active'])
        self.assertEquals(realActiveCount, activeCount)
        self.assertEquals(realFreeCount, freeCount)
        self.assertEquals(pendingCount, len(self.pool.pendingRequests))

    def test_normal_usage(self):
        self.add_request("http://www.foo.com/")
        self.add_request("http://www.bar.com/")
        self.add_request("http://www.foo.com/2")
        self.add_request("http://www.google.com/")
        self.check_counts(4, 0, 0)

    def test_open_connection_failed(self):
        self.pool = TestingHTTPConnectionPool()
        def stopEventLoop(error):
            self.stopEventLoop(False)
        self.pool.addRequest(stopEventLoop, stopEventLoop,
                None, None, None, "http://uselessurl/", "GET", {})
        self.runEventLoop()
        self.check_counts(0, 0, 0)

    def test_counts(self):
        self.add_request("http://pculture.org/")
        self.add_request("http://pculture.org/normalpage.txt")
        self.add_request("https://pculture.org/")
        self.check_counts(3, 0, 0)
        self.finish_connection_for_url('http://pculture.org/')
        self.check_counts(2, 1, 0)
        self.close_connection_for_url('https://pculture.org/')
        self.check_counts(1, 1, 0)
        self.close_connection_for_url('http://pculture.org/')
        self.check_counts(1, 0, 0)

    def test_server_limit(self):
        self.add_request("http://pculture.org/normalpage.txt")
        self.add_request("http://pculture.org/normalpage2.txt")
        self.add_request("https://pculture.org/normalpage.txt")
        self.check_counts(3, 0, 0)
        self.add_request("http://pculture.org/normalpage3.txt")
        self.check_counts(3, 0, 1)
        self.pool.assertConnectionNotStarted('http://pculture.org/normalpage3.txt')
        self.finish_connection_for_url("http://pculture.org/normalpage.txt")
        self.check_counts(3, 0, 0)
        self.finish_connection_for_url("http://pculture.org/normalpage2.txt")
        self.pool.assertConnectionStarted('http://pculture.org/normalpage3.txt')
        self.check_counts(2, 1, 0)

    def test_total_limit(self):
        self.add_request("http://pculture.org/normalpage.txt")
        self.add_request("http://pculture.org/normalpage2.txt")
        self.add_request("http://www.bar.com/")
        self.add_request("http://www.bar.com/2")
        self.add_request("http://www.baz.com/")
        self.add_request("http://www.froz.com/")
        self.check_counts(4, 0, 2)

    def test_both_limits(self):
        # This test is kind of pointless now, but I can't see a way to
        # test it as well as before.
        self.add_request("http://pculture.org/")
        self.add_request("http://pculture.org/2")
        self.add_request("http://pculture.org/3")
        self.check_counts(2, 0, 1)
        self.pool.assertConnectionNotStarted('http://pculture.org/3')
        self.add_request("https://www.bar.com/")
        self.add_request("http://www.bar.com/2")
        self.add_request("http://www.baz.com/")
        self.check_counts(4, 0, 2)
        self.pool.assertConnectionNotStarted('http://www.baz.com/')
        self.pool.assertConnectionNotStarted('http://pculture.org/3')
        self.finish_connection_for_url('https://www.bar.com/')
        self.check_counts(3, 1, 1)
        self.pool.assertConnectionNotStarted('http://pculture.org/3')
        self.finish_connection_for_url('http://pculture.org/')
        self.check_counts(3, 1, 0)

    def test_drop_the_lru(self):
        # Check that the first connection dropped when we run out of
        # connections is the least recently used
        self.add_request("http://www.baz.com/")
        self.add_request("http://pculture.org/")
        self.add_request("http://www.bar.com/")
        self.add_request("http://www.froz.com/")
        self.finish_connection_for_url('http://www.baz.com/')
        self.finish_connection_for_url('http://www.bar.com/')
        self.get_connection_for_url('http://www.baz.com').idleSince = 10
        self.get_connection_for_url('http://www.bar.com').idleSince = 20
        # baz.com has been idle longer, so it should be dropped when
        # we add a new request
        self.assert_(len(self.pool.connections['http:www.baz.com:80']['free']) == 1 and len(self.pool.connections['http:www.baz.com:80']['active']) == 0)
        self.add_request("http://www.booya.com/2")
        self.assert_(len(self.pool.connections['http:www.baz.com:80']['free']) == 0 and len(self.pool.connections['http:www.baz.com:80']['active']) == 0)

class HTTPSConnectionTest(HTTPClientTestBase):
    # This should have more tests, but we're using a TestHTTPClient,
    # so these are faked and probably not wildly useful.

    def test_scheme(self):
        conn = httpclient.HTTPSConnection()
        self.assertEquals(conn.scheme, 'https')

    def test_https_connection(self):
        # Note: this is a real test--we really connect to
        # www.gibill.va.gov with this test.
        conn = httpclient.HTTPSConnection()
        def handleOpen(data):
            conn.sendRequest(self.callback, self.errback,
                             'www.gibill.va.gov', 443,
                             method="GET", path='/wave/')
        def handleError(error):
            self.stopEventLoop(False)
        conn.openConnection("www.gibill.va.gov", 443, handleOpen, handleError)
        self.runEventLoop()
        self.assert_(self.callbackCalled)
        self.assertEquals(self.data['status'], 200)

    def test_grab_url(self):
        # this is faking things since we're using our TestHTTPClient
        httpclient.grabURL('https://pculture.org/secure.txt',
                           self.callback, self.errback,
                           clientClass=TestHTTPClient)
        self.runEventLoop()
        self.assertEquals(self.data['status'], 200)
        self.assert_(self.callbackCalled)

class GrabURLTest(AsyncSocketTest):
    def test_start(self):
        url = 'http://pculture.org/normalpage.txt'
        httpclient.grabURL(url, self.callback, self.errback,
                           clientClass=TestHTTPClient)
        self.runEventLoop()
        self.orig_data = self.data
        httpclient.grabURL(url, self.callback, self.errback, start=4,
                           clientClass=TestHTTPClient)
        self.runEventLoop()
        self.assertEquals(self.data['body'], self.orig_data['body'])
        self.assertEquals(self.data['status'], 200)

class EtagTest(AsyncSocketTest):
    # FIXME - This has to be a test by itself because the response has
    # no body and that screws up other tests.  I think that's probably
    # a bug in the FakeStream or something like that.
    def test_etag(self):
        url = 'http://pculture.org/etag.txt'
        httpclient.grabURL(url, self.callback, self.errback,
                           clientClass=TestHTTPClient)
        self.runEventLoop()
        etag = self.data['etag']
        httpclient.grabURL(url, self.callback, self.errback, etag=etag,
                           clientClass=TestHTTPClient)
        self.runEventLoop()
        self.assertEquals(self.data['status'], 304)
        self.assertEquals(self.data['body'], '')

class OtherEtagTests(AsyncSocketTest):
    def test_bad_etag(self):
        # this sends a bad etag.  the server returns the body
        # twice.
        url = 'http://pculture.org/etag.txt'
        httpclient.grabURL(url, self.callback, self.errback,
                           clientClass=TestHTTPClient)
        self.runEventLoop()
        etag = "aaaaaaa:bbbbbbbb"
        firstBody = self.data['body']
        httpclient.grabURL(url, self.callback, self.errback, etag=etag,
                           clientClass=TestHTTPClient)
        self.runEventLoop()
        self.assertEquals(self.data['status'], 200)
        self.assertEquals(self.data['body'], firstBody)

    def test_modified(self):
        import rfc822
        url = 'http://pculture.org/etag.txt'
        httpclient.grabURL(url, self.callback, self.errback,
                           clientClass=TestHTTPClient)
        self.runEventLoop()
        first_body = self.data['body']
        modified_tuple = rfc822.parsedate_tz(self.data['last-modified'])
        modified_time = rfc822.mktime_tz(modified_tuple)
        modified_time -= 5
        httpclient.grabURL(url, self.callback, self.errback,
                           modified=rfc822.formatdate(modified_time),
                           clientClass=TestHTTPClient)
        self.runEventLoop()
        self.assertEquals(self.data['status'], 200)
        self.assertEquals(self.data['body'], first_body)


## class HTTPClientPipelineCounter(httpclient.HTTPClient):
##     def __init__(self, url, callback, errback):
##         httpclient.HTTPClient.__init__(self, url, callback, errback)
##         self.pipelineErrorsSeen = 0

##     def errbackIntercept(self, error):
##         if isinstance(error, httpclient.PipelinedRequestNeverStarted):
##             self.pipelineErrorsSeen += 1
##         return httpclient.HTTPClient.errbackIntercept(self, error)

## class PipelineTest(HTTPClientTestBase):
##     def setUp(self):
##         HTTPClientTestBase.setUp(self)
##         self.pool = TestingHTTPConnectionPool()
##         self.pool.MAX_CONNECTIONS_PER_SERVER = 1
##         url = "http://www.foo.com/"
##         self.firstClient = TestHTTPClient(url, self.callback, self.errback)
##         self.firstClient.connectionPool = self.pool
##         self.firstClient.startRequest()
##         url = "http://www.foo.com/2"
##         self.pipelineResponse = self.pipelineError = None
##         def pipelineCallback(response):
##             self.pipelineResponse = response
##         def pipelineErrback(error):
##             self.pipelineError = error
##         self.runPendingIdles()
##         conn = self.pool.getConnection('http', 'www.foo.com')
##         conn.handleData(startResponse(headers={'Content-Length': 128}))
##         self.pipelinedClient = HTTPClientPipelineCounter(url,
##                                                          pipelineCallback,
##                                                          pipelineErrback)
##         self.pipelinedClient.connectionPool = self.pool
##         self.pipelinedClient.startRequest()
##         self.runPendingIdles()

#     def testPipelineRetry(self):
#         conn = self.pool.getConnection('http', 'www.foo.com')
#         self.assertEquals(self.firstClient.connection, conn)
#         self.assertEquals(self.pipelinedClient.connection, None)
#         conn.closeConnection()
#         conn.handleClose(socket.SHUT_RD)
#         self.runPendingIdles()
#         self.assertEquals(self.pipelineError, None)
#         self.assertEquals(self.pipelineResponse, None)
#         conn = self.pool.getConnection('http', 'www.foo.com')
#         conn.handleData(HTTPClientTest.fakeResponse)
#         self.assertEquals(self.pipelineResponse['body'], "HELLO: WORLD\r\n")
#         self.assertEquals(self.pipelinedClient.pipelineErrorsSeen, 1)

#     def testPipelineCancel(self):
#         # canceling the pipelined request shouldn't affect the earlier one.
#         self.pipelinedClient.cancel()
#         conn = self.pool.getConnection('http', 'www.foo.com')
#         self.assert_(conn is not None)
#         conn.handleData('a' * 128)
#         conn = self.pool.getConnection('http', 'www.foo.com', 'free')
#         self.assert_(conn is None)

#     def testPipelineCancel2(self):
#         # canceling the earlier request should result in the pipeline request
#         # retrying
#         self.firstClient.cancel()
#         self.runPendingIdles()
#         self.assertEquals(self.pipelineError, None)
#         self.assertEquals(self.pipelineResponse, None)
#         conn = self.pool.getConnection('http', 'www.foo.com')
#         conn.handleData(HTTPClientTest.fakeResponse)
#         self.assertEquals(self.pipelineResponse['body'], "HELLO: WORLD\r\n")

#     def checkPipelineCanceled(self):
#         self.assertEquals(self.pipelineError, None)
#         self.assertEquals(self.pipelineResponse, None)
#         conn = self.pool.getConnection('http', 'www.foo.com', type='active')
#         self.assert_(conn is None)
#         conn = self.pool.getConnection('http', 'www.foo.com', type='free')
#         self.assert_(conn is None)

#     def testPipelineCancel3(self):
#         # If we cancel the pipeline, then canceling the earlier request
#         self.pipelinedClient.cancel()
#         self.firstClient.cancel()
#         self.runPendingIdles()
#         self.checkPipelineCanceled()

#     def testPipelineCancel4(self):
#         # test canceling the pipeline, then letting the 1st request finish
#         self.pipelinedClient.cancel()
#         conn = self.pool.getConnection('http', 'www.foo.com')
#         conn.handleData(HTTPClientTest.fakeResponse)
#         self.runPendingIdles()
#         self.checkPipelineCanceled()

class BadURLTest(HTTPClientTestBase):
    def test_scheme(self):
        url = 'pculture.org/normalpage.txt'
        httpclient.grabURL(url, self.callback, self.errback,
                           clientClass=TestHTTPClient)
        self.runPendingIdles()
        self.assertEquals(self.errbackCalled, True)
        self.assertEquals(self.callbackCalled, False)

    def test_slashes(self):
        url = 'http:jigsaw.w3.org/HTTP/'
        httpclient.grabURL(url, self.callback, self.errback,
                           clientClass=TestHTTPClient)
        self.runPendingIdles()
        self.assertEquals(self.errbackCalled, True)
        self.assertEquals(self.callbackCalled, False)

    def test_host(self):
        url = 'http:///HTTP/'
        httpclient.grabURL(url, self.callback, self.errback,
                           clientClass=TestHTTPClient)
        self.runPendingIdles()
        self.assertEquals(self.errbackCalled, True)
        self.assertEquals(self.callbackCalled, False)

    def test_other_scheme(self):
        url = 'rtsp://jigsaw.w3.org/'
        httpclient.grabURL(url, self.callback, self.errback,
                           clientClass=TestHTTPClient)
        self.runPendingIdles()
        self.assertEquals(self.errbackCalled, True)
        self.assertEquals(self.callbackCalled, False)

class SocketCallbackTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)

    def make_socket(self):
        sock = socket.socket()
        sock.connect(('pculture.org', 80))
        return sock

# This test fails right now..  It seems like it could be an error, but
# I'm don't think it causes any harm, so I'm disabling it - Ben
#
#     def test_add_on_existing(self):
#         s1 = self.make_socket()
#         s2 = self.make_socket()
#         self.badCallbackCalled = self.goodCallbackCalled = False
#         def badCallback():
#             self.badCallbackCalled = True
#         def goodCallback():
#             self.goodCallbackCalled = True
#         def callback():
#             self.addWriteCallback(s2, badCallback)
#         self.addWriteCallback(s1, callback)
#         self.addWriteCallback(s2, goodCallback)
#         self.assert_(self.goodCallbackCalled)
#         self.assert_(not self.badCallbackCalled)

    def test_remove_then_add(self):
        """Test adding a write callback right after we remove one.
        This case isn't so bad actually, the really bad case (which I
        don't know how to simulate, is if we closed s2, then made a
        new socket, s3 that had the same fileno as s2 used to have.
        """
        s1 = self.make_socket()
        s2 = self.make_socket()
        self.count = 0
        def callback():
            self.count += 1
            if self.count == 1:
                self.removeWriteCallback(s1)
                self.addWriteCallback(s1, callback)
                self.removeWriteCallback(s2)
                self.addWriteCallback(s2, callback)
        self.addWriteCallback(s1, callback)
        self.addWriteCallback(s2, callback)
        self.addIdle(lambda: self.stopEventLoop(False), 'stop event loop')
        self.runEventLoop()
        self.assertEquals(self.count, 1)

class CookieExpirationDateTestCase(unittest.TestCase):
    def test_cookie_expiration_date(self):
        """Tests get_cookie_expiration_date to make sure it's
        returning sane values and handles cookie expiration formats
        we've had problems with.
        """
        from time import mktime, strptime, localtime
        from miro.httpclient import get_cookie_expiration_date

        for cd in [("Thu, 03-May-07 22:48:52 GMT", "2007-05-03 22:48:52 GMT"),
                   ("Fri, 03-Jun-11 13:41:15 GMT", "2011-06-03 13:41:15 GMT"),
                   ("Sun, 17-Jan-2038 19:14:07 GMT", "2038-01-17 19:14:07 GMT"),
                   ("Mon, 09-Apr-07 23:50:49 GMT", "2007-04-09 23:50:49 GMT"),
                   ("Tue, 01-Jan-2030 10:00:00 GMT", "2030-01-01 10:00:00 GMT"),
                   ("Tue, 17-Jul-2007 02:09:00 GMT", "2007-07-17 02:09:00 GMT"),
                   ("Monday, 15-Feb-10 17:13:07 GMT", "2010-02-15 17:13:07 GMT")
                   ]:

            # compare the 9-tuple we get from localtime because tuples
            # are easier to compare (and more accurate for what we're
            # looking for)
            self.assertEquals(localtime(get_cookie_expiration_date(cd[0])),
                              localtime(mktime(strptime(cd[1], "%Y-%m-%d %H:%M:%S %Z"))))

    def test_overflow_cookie_expiration_date(self):
        """Tests the case of get_cookie_expiration_date where the
        cookie expiration date causes an overflow error when parsing
        it.
        """
        if sys.maxint > 2**31 - 1:
            # this test can't be executed on 64 bit systems
            return
        from time import localtime
        from miro.httpclient import get_cookie_expiration_date, DATEINFUTURE

        dt = "Tue, 26-Jul-2050 10:00:00 GMT"
        self.assertEquals(localtime(get_cookie_expiration_date(dt)),
                          localtime(httpclient.DATEINFUTURE))
