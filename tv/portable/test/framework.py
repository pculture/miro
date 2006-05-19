import unittest

import database
import eventloop

class DemocracyTestCase(unittest.TestCase):
    def setUp(self):
        # reset the event loop
        database.resetDefaultDatabase()
        eventloop._eventLoop.threadPool.closeThreads()
        eventloop._eventLoop = eventloop.EventLoop() 

    def tearDown(self):
        # this prevents weird errors when we quit
        eventloop._eventLoop.threadPool.closeThreads()
