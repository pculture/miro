import os
import tempfile

from miro import util # This adds logging.timing
from miro import download_utils
from miro import httpclient
from miro.test.framework import EventLoopTest
from miro.dl_daemon import download

# BIGTESTFILE = { "url": u"http://www.getmiro.com/images/apple-screen.jpg", 
#                 "size": 171497 }
BIGTESTFILE = { "url": u"http://www.getmiro.com/images/linux-screen.jpg", 
                "size": 45572 }


def testingNextFreeFilename(filename):
    return tempfile.mktemp()

class TestingDownloader(download.HTTPDownloader):
    UPDATE_CLIENT_INTERVAL = 0 # every data block does an updateClient

    def __init__(self, test, *args, **kwargs):
        self.test = test
        if 'restore' in kwargs:
            kwargs['restore']['statusCallback'] = lambda: 0
            kwargs['restore']['lastStatus'] = None
        else:
            self.statusCallback = lambda: 0
            self.lastStatus = None
        download.HTTPDownloader.__init__(self, *args, **kwargs)

    def updateClient(self):
        self.lastStatus = self.getStatus()
        self.test.addIdle(self.statusCallback, "status callback")

class HTTPDownloaderTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
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
        EventLoopTest.tearDown(self)

    def stopOnFinished(self):
        if self.downloader.state == "finished":
            self.stopEventLoop(False)

    def getDownloadedData(self):
        return open(self.downloader.filename, 'rb').read()

    def countConnections(self):
        total = 0
        pool = httpclient.HTTPClient.connectionPool
        for conns in pool.connections.values():
            total += len(conns['active'])
        return total

#    Really slow test that downloads a very large file.
#    def testHuge(self):
#        url = 'http://archive-c01.libsyn.com/aXdueJh2m32XeGh6l3efp5qtZXiX/podcasts/askaninja/AANQ21.m4v'
#        self.downloader = TestingDownloader(url, "ID1")
#        self.downloader.statusCallback = self.stopOnFinished
#        self.runEventLoop(timeout=120)
#        self.assertEquals(self.failed, None)
#
    def testDownload(self):
        url = u'http://participatoryculture.org/democracytest/normalpage.txt'
        self.downloader = TestingDownloader(self, url, "ID1")
        self.downloader.statusCallback = self.stopOnFinished
        self.runEventLoop()
        self.assertEquals(self.getDownloadedData(), "I AM A NORMAL PAGE\n")

    def testStop(self):
        # nice large download so that we have time to interrupt it
        url = BIGTESTFILE["url"]
        self.downloader = TestingDownloader(self, url, "ID1")
        def stopOnData():
            if (self.downloader.state == 'downloading' and 
                    self.downloader.currentSize > 0):
                self.downloader.stop(False)
                self.stopEventLoop(False)
        self.downloader.statusCallback = stopOnData
        self.runEventLoop()
        self.assertEquals(self.downloader.state, 'stopped')
        self.assertEquals(self.downloader.currentSize, 0)
        self.assert_(not os.path.exists(self.downloader.filename))
        self.assertEquals(self.countConnections(), 0)
        def restart():
            self.downloader.start()
        self.addTimeout(0.5, restart, 'restarter')
        self.downloader.statusCallback = self.stopOnFinished
        self.runEventLoop()
        self.assertEquals(self.downloader.currentSize, BIGTESTFILE["size"])
        self.assertEquals(self.downloader.totalSize, BIGTESTFILE["size"])

    def testPause(self):
        url = BIGTESTFILE["url"]
        self.downloader = TestingDownloader(self, url, "ID1")
        def pauseOnData():
            if (self.downloader.state == 'downloading' and 
                    self.downloader.currentSize > 0):
                self.downloader.pause()
                self.stopEventLoop(False)
        self.downloader.statusCallback = pauseOnData
        self.runEventLoop()
        self.assertEquals(self.downloader.state, 'paused')
        self.assert_(self.downloader.currentSize > 0)
        self.assert_(os.path.exists(self.downloader.filename))
        self.assertEquals(self.countConnections(), 0)
        def restart():
            self.downloader.start()
        self.addTimeout(0.5, restart, 'restarter')
        self.downloader.statusCallback = self.stopOnFinished
        self.runEventLoop()
        self.assertEquals(self.downloader.currentSize, BIGTESTFILE["size"])
        self.assertEquals(self.downloader.totalSize, BIGTESTFILE["size"])

    def testRestore(self):
        url = BIGTESTFILE["url"]
        self.downloader = TestingDownloader(self, url, "ID1")
        def pauseInMiddle():
            if (self.downloader.state == 'downloading' and 
                    self.downloader.currentSize > 1000):
                self.downloader.pause()
                self.stopEventLoop(False)
        self.downloader.statusCallback = pauseInMiddle
        self.runEventLoop()
        self.assertEquals(self.downloader.state, 'paused')
        self.assert_(0 < self.downloader.currentSize < 2000)
        restore = self.downloader.lastStatus.copy()
        restore['state'] = 'downloading'
        download._downloads = {}
        self.downloader2 = TestingDownloader(self, restore=restore)
        restoreSize = restore['currentSize']
        self.restarted = False
        def statusCallback():
            # make sure we don't ever restart it
            if self.downloader2.currentSize < restoreSize:
                print "%d < %d" % (self.downloader2.currentSize, restoreSize)
                self.restarted = True
                self.stopEventLoop(False)
            elif self.downloader2.state == 'finished':
                self.stopEventLoop(False)
        self.downloader2.statusCallback = statusCallback
        self.runEventLoop()
        self.assert_(not self.restarted)
