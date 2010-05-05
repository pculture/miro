import os
import tempfile
import threading

from miro import util # This adds logging.timing
from miro import download_utils
from miro import httpclient
from miro.test.framework import EventLoopTest
from miro.plat import resources
from miro.dl_daemon import download

def testing_next_free_filename(filename):
    return tempfile.mktemp()

class TestingDownloader(download.HTTPDownloader):
    # update stats really often to make sure that we can do things like pause
    # in the middle of a download
    CHECK_STATS_TIMEOUT = 0.01

    def __init__(self, test, *args, **kwargs):
        self.test = test
        if 'restore' in kwargs:
            kwargs['restore']['statusCallback'] = lambda: 0
            kwargs['restore']['lastStatus'] = None
        else:
            self.statusCallback = lambda: 0
            self.lastStatus = None
        download.HTTPDownloader.__init__(self, *args, **kwargs)

    def update_stats(self):
        download.HTTPDownloader.update_stats(self)
        self.lastStatus = self.getStatus()
        self.test.add_idle(self.statusCallback, "status callback")

    def updateClient(self):
        # This normally sends info through the DownoaderDaemon, but that
        # doesn't exist.
        pass

class HTTPDownloaderTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        download.chatter = False
        download.next_free_filename = testing_next_free_filename
        download._downloads = {}
        self.start_http_server()
        # screen-redirect is a 302 redirect to linux-screen.jpg, which is a
        # fairly big file.  The idea is to try to mimic a real-world item,
        # which often have redirects.
        self.download_url = unicode(
                self.httpserver.build_url('screen-redirect'))
        self.download_path = resources.path(
                'testdata/httpserver/linux-screen.jpg')
        self.event_loop_timeout = 0.5
        self.download_size = 45572

    def tearDown(self):
        download.next_free_filename = download_utils.next_free_filename
        download.chatter = True
        EventLoopTest.tearDown(self)

    def stopOnFinished(self):
        if self.downloader.state == "finished":
            self.stopEventLoop(False)

    def getDownloadedData(self):
        return open(self.downloader.filename, 'rb').read()

    def countConnections(self):
        self.wait_for_libcurl_manager()
        return len(httpclient.curl_manager.transfer_map)

#    Really slow test that downloads a very large file.
#    def testHuge(self):
#        url = 'http://archive-c01.libsyn.com/aXdueJh2m32XeGh6l3efp5qtZXiX/podcasts/askaninja/AANQ21.m4v'
#        self.downloader = TestingDownloader(url, "ID1")
#        self.downloader.statusCallback = self.stopOnFinished
#        self.runEventLoop(timeout=120)
#        self.assertEquals(self.failed, None)
#
    def testDownload(self):
        self.downloader = TestingDownloader(self, self.download_url, "ID1")
        self.downloader.statusCallback = self.stopOnFinished
        self.runEventLoop()
        self.assertEquals(self.getDownloadedData(),
                open(self.download_path).read())

    def testStop(self):
        # nice large download so that we have time to interrupt it
        self.downloader = TestingDownloader(self, self.download_url, "ID1")
        def stopOnData():
            if (self.downloader.state == 'downloading' and
                    self.downloader.currentSize == 10000):
                self.downloader.stop(False)
                self.stopEventLoop(False)
        self.downloader.statusCallback = stopOnData
        self.httpserver.pause_after(10000)
        self.runEventLoop()
        self.assertEquals(self.downloader.state, 'stopped')
        self.assertEquals(self.downloader.currentSize, 0)
        self.wait_for_libcurl_manager()
        self.assert_(not os.path.exists(self.downloader.filename))
        self.assertEquals(self.countConnections(), 0)
        def restart():
            self.downloader.start()
        self.add_timeout(0.1, restart, 'restarter')
        self.downloader.statusCallback = self.stopOnFinished
        self.httpserver.pause_after(-1)
        self.runEventLoop()
        self.assertEquals(self.downloader.currentSize, self.download_size)
        self.assertEquals(self.downloader.totalSize, self.download_size)

    def testPause(self):
        self.downloader = TestingDownloader(self, self.download_url, "ID1")
        def pauseOnData():
            if (self.downloader.state == 'downloading' and 
                    self.downloader.currentSize == 10000):
                self.downloader.pause()
                self.stopEventLoop(False)
        self.downloader.statusCallback = pauseOnData
        self.httpserver.pause_after(10000)
        self.runEventLoop()
        self.assertEquals(self.downloader.state, 'paused')
        self.assertEquals(self.downloader.currentSize, 10000)
        self.assert_(os.path.exists(self.downloader.filename))
        self.assertEquals(self.countConnections(), 0)
        def restart():
            self.downloader.start()
        self.add_timeout(0.1, restart, 'restarter')
        self.downloader.statusCallback = self.stopOnFinished
        self.httpserver.pause_after(-1)
        self.runEventLoop()
        self.assertEquals(self.downloader.currentSize, self.download_size)
        self.assertEquals(self.downloader.totalSize, self.download_size)

    def testRestore(self):
        self.downloader = TestingDownloader(self, self.download_url, "ID1")
        def pauseInMiddle():
            if (self.downloader.state == 'downloading' and
                    self.downloader.currentSize == 10000):
                self.downloader.pause()
                self.stopEventLoop(False)
        self.downloader.statusCallback = pauseInMiddle
        self.httpserver.pause_after(10000)
        self.runEventLoop()
        self.assertEquals(self.downloader.state, 'paused')
        self.assertEquals(self.downloader.currentSize, 10000)
        restore = self.downloader.lastStatus.copy()
        restore['state'] = 'downloading'
        download._downloads = {}
        self.downloader2 = TestingDownloader(self, restore=restore)
        restoreSize = restore['currentSize']
        self.restarted = False
        def startNewDownloadIntercept():
            self.restarted = True
            self.stopEventLoop(False)
        def statusCallback():
            if self.downloader2.state == 'finished':
                self.stopEventLoop(False)
        self.downloader2.startNewDownload = startNewDownloadIntercept
        self.downloader2.statusCallback = statusCallback
        self.httpserver.pause_after(-1)
        self.runEventLoop()
        self.assert_(not self.restarted)
