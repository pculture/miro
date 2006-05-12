import unittest
import socket
import traceback

import eventloop
import httpclient
from test.schedulertest import EventLoopTest

class NetworkBufferTest(unittest.TestCase):
    def setUp(self):
        self.buffer = httpclient.NetworkBuffer()

    def testReadLine(self):
        self.buffer.addData("HEL")
        self.assertEquals(self.buffer.readline(), None)
        self.buffer.addData("LO\r\n")
        self.assertEquals(self.buffer.readline(), 'HELLO')
        self.buffer.addData("HOWS\r\nIT\r\nGOING\r\nEXTRA")
        self.assertEquals(self.buffer.readline(), 'HOWS')
        self.assertEquals(self.buffer.readline(), 'IT')
        self.assertEquals(self.buffer.readline(), 'GOING')
        self.assertEquals(self.buffer.readline(), None)
        self.assertEquals(self.buffer.read(), "EXTRA")

    def testRead(self):
        self.buffer.addData("12345678901234567890")
        self.assertEquals(self.buffer.read(4), "1234")
        self.assertEquals(self.buffer.read(6), "567890")
        self.buffer.addData("CARBOAT")
        self.assertEquals(self.buffer.read(), "1234567890CARBOAT")

    def testLength(self):
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

class TestingHTTPReqest(httpclient.HTTPRequest):
    """HTTPRequest that doesn't actually connect to the network."""

    def __init__(self, host, port, callback, errback):
        super(TestingHTTPReqest, self).__init__(host, port, callback, errback)
        self.output = ''

    def openConnection(self, host, port):
        self.connected = True

    def closeConnection(self):
        self.connected = False

    def sendData(self, data):
        self.output += data

    def startReading(self):
        pass

    def stopReading(self):
        pass

class HTTPClientTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.data = None
        self.errbackCalled = False
        self.callbackCalled = False
        self.testRequest = TestingHTTPReqest('foo.com', 80, self.callback,
                self.errback)
        self.testRequest.sendRequest('GET', '/bar/baz;123?a=b')

    def callback(self, data):
        self.data = data
        self.callbackCalled = True
        eventloop.quit()

    def errback(self, error):
        self.data = error
        self.errbackCalled = True
        eventloop.quit()

    def testRequestLine(self):
        self.assertEquals(self.testRequest.output.split("\r\n")[0],
                'GET /bar/baz;123?a=b HTTP/1.1')

    def testStatusLine(self):
        self.testRequest.handleData("HTTP/1.0 200 OK\r\n")
        self.assertEquals(self.testRequest.version, 'HTTP/1.0')
        self.assertEquals(self.testRequest.status, 200)
        self.assertEquals(self.testRequest.reason, 'OK')

    def testStatusLine(self):
        self.testRequest.handleData("HTTP/1.1 404 Not Found\r\n")
        self.assertEquals(self.testRequest.version, 'HTTP/1.1')
        self.assertEquals(self.testRequest.status, 404)
        self.assertEquals(self.testRequest.reason, 'Not Found')

    def testBadStatusLine(self):
        self.testRequest.handleData("HTTP/0.9 200 OK\r\n")
        self.assert_(self.errbackCalled)
        self.assert_(isinstance(self.data, httpclient.BadStatusLine))

    def testBadStatusLine2(self):
        self.testRequest.handleData("HTTP/1.0 641 OK\r\n")
        self.assert_(self.errbackCalled)
        self.assert_(isinstance(self.data, httpclient.BadStatusLine))

    def testNoReason(self):
        self.testRequest.handleData("HTTP/1.0 200\r\n")
        self.assertEquals(self.testRequest.version, 'HTTP/1.0')
        self.assertEquals(self.testRequest.status, 200)
        self.assertEquals(self.testRequest.reason, '')

    def testTryToHandleHTTP0Point9(self):
        self.testRequest.handleData("StartOfThebody\r\n")
        self.assertEquals(self.testRequest.version, 'HTTP/0.9')
        self.assertEquals(self.testRequest.status, 200)
        self.assertEquals(self.testRequest.reason, '')
        self.assertEquals(self.testRequest.buffer.read(),
                "StartOfThebody\r\n")

    fakeResponse = """\
HTTP/1.0 200 OK\r
Content-Type: text/plain; charset=ISO-8859-1\r
Last-Modified: Wed, 10 May 2006 22:30:33 GMT\r
Date: Wed, 10 May 2006 22:38:39 GMT\r
X-Cache: HIT from pcf2.pcf.osuosl.org\r
Server: Apache\r
Connection: close\r
\r
HELLO WORLD\r\n"""

    def testBasicHeaders(self):
        self.testRequest.handleData(self.fakeResponse)
        self.testRequest.handleClose(socket.SHUT_RD)
        headers = self.testRequest.headers
        self.assertEquals(headers['x-cache'], 'HIT from pcf2.pcf.osuosl.org')
        self.assertEquals(headers['server'], 'Apache')
        self.assertEquals(headers['last-modified'], 
            'Wed, 10 May 2006 22:30:33 GMT')
        self.assertEquals(headers['connection'], 'close')
        self.assertEquals(headers['date'], 'Wed, 10 May 2006 22:38:39 GMT')
        self.assertEquals(headers['content-type'], 
            'text/plain; charset=ISO-8859-1')

    def testBadHeader(self):
        self.testRequest.handleData("HTTP/1.0 200 OK\r\n")
        self.testRequest.handleData("FOO:\r\n")
        self.assert_(self.errbackCalled)
        self.assert_(isinstance(self.data, httpclient.BadHeaderLine))

    def testHeaderContinuation(self):
        self.testRequest.handleData("HTTP/1.0 200 OK\r\n")
        self.testRequest.handleData("Cont\r\n")
        self.testRequest.handleData(" ent-Type: text/plain\r\n")
        self.assertEquals(self.testRequest.headers['content-type'],
                'text/plain')

    def testBadHeaderContinuation(self):
        self.testRequest.handleData("HTTP/1.0 200 OK\r\n")
        self.testRequest.handleData("IShouldBeContinued\r\n")
        self.testRequest.handleData("\r\n")
        self.assert_(self.errbackCalled)
        self.assert_(isinstance(self.data, httpclient.BadHeaderLine))

    def testSplitUpMessage(self):
        data = self.fakeResponse
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
        self.assertEquals(self.testRequest.body, 'HELLO WORLD\r\n')

    def testOneChunk(self):
        self.testRequest.handleData(self.fakeResponse)
        self.testRequest.handleClose(socket.SHUT_RD)
        self.assertEquals(self.testRequest.version, 'HTTP/1.0')
        self.assertEquals(self.testRequest.status, 200)
        self.assertEquals(self.testRequest.reason, 'OK')
        self.assertEquals(self.testRequest.headers['server'],
                'Apache')
        self.assertEquals(self.testRequest.body, 'HELLO WORLD\r\n')

    def testPrematureClose(self):
        data = self.fakeResponse
        self.testRequest.handleData(data[:123])
        self.testRequest.handleClose(socket.SHUT_RD)
        self.assert_(self.errbackCalled)
        self.assert_(isinstance(self.data, httpclient.ServerClosedConnection))

    def testRealRequest(self):
        url = 'http://participatoryculture.org/democracytest/normalpage.txt'
        httpclient.makeRequest(url, self.callback, self.errback)
        self.runEventLoop()
        self.assert_(self.callbackCalled)
        self.assertEquals(self.data['body'], "I AM A NORMAL PAGE\n")

    #def testRedirect(`
        #http://participatoryculture.org/democracytest/start.php
