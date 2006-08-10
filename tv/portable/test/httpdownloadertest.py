import os
import tempfile

import download_utils
import eventloop
import httpclient
from test import schedulertest
from dl_daemon import download

def testingNextFreeFilename(filename):
    return tempfile.mktemp()

class TestingDownloader(download.HTTPDownloader):
    UPDATE_CLIENT_INTERVAL = 0 # every data block does an updateClient

    def __init__(self, *args, **kwargs):
        if 'restore' in kwargs:
            kwargs['restore']['statusCallback'] = lambda: 0
            kwargs['restore']['lastStatus'] = None
        else:
            self.statusCallback = lambda: 0
            self.lastStatus = None
        download.HTTPDownloader.__init__(self, *args, **kwargs)

    def updateClient(self):
        self.lastStatus = self.getStatus()
        eventloop.addIdle(self.statusCallback, "status callback")

class HTTPDownloaderTest(schedulertest.EventLoopTest):
    def setUp(self):
        super(HTTPDownloaderTest, self).setUp()
        download.chatter = False
        download.nextFreeFilename = testingNextFreeFilename
        download._downloads = {}
        allConnections = []
        for conns in httpclient.HTTPClient.connectionPool.connections.values():
            allConnections.extend(conns['active'])
            allConnections.extend(conns['free'])
        for c in allConnections:
            c.closeConnection()
        httpclient.HTTPClient.connectionPool = httpclient.HTTPConnectionPool() 

    def tearDown(self):
        download.nextFreeFilename = download_utils.nextFreeFilename
        download.chatter = True
        super(HTTPDownloaderTest, self).tearDown()

    def stopOnFinished(self):
        if self.downloader.state == "finished":
            eventloop.quit()

    def getDownloadedData(self):
        return open(self.downloader.filename, 'rb').read()

    def countConnections(self):
        total = 0
        pool = httpclient.HTTPClient.connectionPool
        for conns in pool.connections.values():
            total += len(conns['active'])
        return total

    def testDownload(self):
        url = 'http://participatoryculture.org/democracytest/normalpage.txt'
        self.downloader = TestingDownloader(url, "ID1")
        self.downloader.statusCallback = self.stopOnFinished
        self.runEventLoop()
        self.assertEquals(self.getDownloadedData(), "I AM A NORMAL PAGE\n")

    def testStop(self):
        # nice large download so that we have time to interrupt it
        url = 'http://www.getdemocracy.com/images/linux-screen.jpg'
        self.downloader = TestingDownloader(url, "ID1")
        def stopOnData():
            if (self.downloader.state == 'downloading' and 
                    self.downloader.currentSize > 0):
                self.downloader.stop(False)
                eventloop.quit()
        self.downloader.statusCallback = stopOnData
        self.runEventLoop()
        self.assertEquals(self.downloader.state, 'stopped')
        self.assertEquals(self.downloader.currentSize, 0)
        self.assert_(not os.path.exists(self.downloader.filename))
        self.assertEquals(self.countConnections(), 0)
        def restart():
            self.downloader.start()
        eventloop.addTimeout(0.5, restart, 'restarter')
        self.downloader.statusCallback = self.stopOnFinished
        self.runEventLoop()
        self.assertEquals(self.downloader.currentSize, 45572)
        self.assertEquals(self.downloader.totalSize, 45572)

    def testPause(self):
        url = 'http://www.getdemocracy.com/images/linux-screen.jpg'
        self.downloader = TestingDownloader(url, "ID1")
        def pauseOnData():
            if (self.downloader.state == 'downloading' and 
                    self.downloader.currentSize > 0):
                self.downloader.pause()
                eventloop.quit()
        self.downloader.statusCallback = pauseOnData
        self.runEventLoop()
        self.assertEquals(self.downloader.state, 'paused')
        self.assert_(self.downloader.currentSize > 0)
        self.assert_(os.path.exists(self.downloader.filename))
        self.assertEquals(self.countConnections(), 0)
        def restart():
            self.downloader.start()
        eventloop.addTimeout(0.5, restart, 'restarter')
        self.downloader.statusCallback = self.stopOnFinished
        self.runEventLoop()
        self.assertEquals(self.downloader.currentSize, 45572)
        self.assertEquals(self.downloader.totalSize, 45572)

    def testRestore(self):
        url = 'http://www.getdemocracy.com/images/linux-screen.jpg'
        self.downloader = TestingDownloader(url, "ID1")
        def pauseInMiddle():
            if (self.downloader.state == 'downloading' and 
                    self.downloader.currentSize > 1000):
                self.downloader.pause()
                eventloop.quit()
        self.downloader.statusCallback = pauseInMiddle
        self.runEventLoop()
        self.assertEquals(self.downloader.state, 'paused')
        self.assert_(0 < self.downloader.currentSize < 2000)
        restore = self.downloader.lastStatus.copy()
        restore['state'] = 'downloading'
        download._downloads = {}
        self.downloader2 = TestingDownloader(restore=restore)
        restoreSize = restore['currentSize']
        self.restarted = False
        def statusCallback():
            # make sure we don't ever restart it
            if self.downloader2.currentSize < restoreSize:
                print "%d < %d" % (self.downloader2.currentSize, restoreSize)
                self.restarted = True
                eventloop.quit()
            elif self.downloader2.state == 'finished':
                eventloop.quit()
        self.downloader2.statusCallback = statusCallback
        self.runEventLoop()
        self.assert_(not self.restarted)
