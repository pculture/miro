import unittest
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


class HTTPClientTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.data = None
        self.errbackCalled = False
        self.callbackCalled = False

    def callback(self, data):
        self.data = data
        self.callbackCalled = True
        eventloop.quit()

    def errback(self, error):
        self.data = error
        self.errbackCalled = True
        eventloop.quit()

    def makeRequest(self, url):
        httpclient.makeRequest(url, self.callback, self.errback)
        eventloop._eventLoop.loop()

    def testNormalGet(self):
        self.makeRequest('http://participatoryculture.org/democracytest/normalpage.txt')
        self.assert_(self.callbackCalled)
        print self.data
        self.assertEquals(self.data['body'], "I AM A NORMAL PAGE\n")

    #def testRedirect(`
        #http://participatoryculture.org/democracytest/start.php
