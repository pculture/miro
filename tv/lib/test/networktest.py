import email.Utils
import socket

from miro import download_utils
from miro import net
from miro.test.framework import EventLoopTest, MiroTestCase

class TestingConnectionHandler(net.ConnectionHandler):
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
            self.errback(net.ConnectionError("Can't connect"))
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
        self.buffer = net.NetworkBuffer()
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
            conn = net.AsyncSocket()
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
            conn = net.AsyncSocket()
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
        self.received = net.NetworkBuffer()
        def readData():
            try:
                readIn = self.remoteSocket.recv(1024 * 1024)
            except:
                readIn = ''
            self.received.addData(readIn)
            if self.received.length == len(data):
                self.stopEventLoop(False)
            else:
                self.add_timeout(0.1, readData, 'test')
        self.add_timeout(0.1, readData, 'test')
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
