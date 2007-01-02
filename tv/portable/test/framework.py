import unittest

import database
import eventloop
import frontend
import app
import downloader
import util
import databaseupgrade
import storedatabase
import subscription
import selection

class HadToStopEventLoop(Exception):
    pass

class DummyMainFrame:
    def __init__(self):
        self.displays = {}
        self.mainDisplay = "mainDisplay"
        self.channelsDisplay = "channelsDisplay"
        self.collectionDisplay = "collectionDisplay"
        self.videoInfoDisplay = "videoInfoDisplay"

    def selectDisplay(self, display, area):
        self.displays[area] = display

    def getDisplay(self, area):
        return self.displays.get(area)

    def onSelectedTabChange(self, tabType, multiple, guideURL, videoFilename):
        pass

class DummyController:
    def __init__(self):
        self.selection = selection.SelectionHandler()
        self.frame = DummyMainFrame()

class DemocracyTestCase(unittest.TestCase):
    def setUp(self):
        # reset the event loop
        util.chatter = False
        database.resetDefaultDatabase()
        eventloop._eventLoop.threadPool.closeThreads()
        eventloop._eventLoop = eventloop.EventLoop() 
        self.oldUtilDotFailed = util.failed
        self.failedCalled = False
        self.utilDotFailedOkay = False
        def newUtilDotFailed(*args, **kwargs):
            if self.utilDotFailedOkay:
                self.failedCalled = True
            else:
                print "util.failed called!"
                print "args: %s kwargs: %s"  % (args, kwargs)
                import traceback
                if kwargs.get('withExn'):
                    traceback.print_exc()
                else:
                    traceback.print_stack()
                raise Exception("util.failed called")
        util.failed = newUtilDotFailed
        app.controller = DummyController()

    def tearDown(self):
        util.chatter = True
        # this prevents weird errors when we quit
        eventloop._eventLoop.threadPool.closeThreads()


class EventLoopTest(DemocracyTestCase):
    def setUp(self):
        DemocracyTestCase.setUp(self)
        self.hadToStopEventLoop = False

        # Maybe we should get rid of references to _eventLoop and fix the
        # API to allow running the eventloop in the current thread... --NN
        eventloop._eventLoop.threadPool.initThreads()

    def stopEventLoop(self):
        self.hadToStopEventLoop = True
        eventloop.quit()
        eventloop.threadPoolQuit()

    def runPendingIdles(self):
        idleQueue = eventloop._eventLoop.idleQueue
        urgentQueue = eventloop._eventLoop.urgentQueue
        while idleQueue.hasPendingIdle() or urgentQueue.hasPendingIdle():
            urgentQueue.processIdles()
            idleQueue.processNextIdle()

    def runEventLoop(self, timeout=10, timeoutNormal=False):
        self.hadToStopEventLoop = False
        timeout = eventloop.addTimeout(timeout, self.stopEventLoop, 
                "Stop test event loop")
        eventloop._eventLoop.quitFlag = False
        eventloop._eventLoop.loop()
        eventloop.threadPoolQuit()
        if self.hadToStopEventLoop and not timeoutNormal:
            raise HadToStopEventLoop()
        else:
            timeout.cancel()

    def processIdles(self):
        eventloop._eventLoop.idleQueue.processIdles()
        eventloop._eventLoop.urgentQueue.processIdles()

class DownloaderTestCase(EventLoopTest):
    def setUp(self):
        DemocracyTestCase.setUp(self)
        # FIXME: This is kind of ugly
        app.delegate = frontend.UIBackendDelegate()
        downloader.startupDownloader()

    def tearDown(self):
        DemocracyTestCase.tearDown(self)
        downloader.shutdownDownloader(eventloop.quit)
        self.runEventLoop()
        app.delegate = None
