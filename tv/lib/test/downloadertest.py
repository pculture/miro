import tempfile
import os

from miro import downloader
from miro import eventloop
from miro import models
from miro.dl_daemon import command
from miro.test.framework import MiroTestCase, EventLoopTest

class DownloaderTest(EventLoopTest):
    # Test feeds that download things

    def setUp(self):
        EventLoopTest.setUp(self)
        self.url = u'http://pculture.org/feeds_test/unittest-feed-1.rss'
        self.feed = models.Feed(self.url)
        downloader.init_controller()
        downloader.startup_downloader()

    def tearDown(self):
        downloader.shutdown_downloader()
        downloader.daemon_starter = None
        EventLoopTest.tearDown(self)

    def run_eventloop_until_items(self):
        tracker = self.feed.items.make_tracker()
        tracker.connect('added', lambda view, obj: eventloop.shutdown())
        try:
            self.runEventLoop()
        finally:
            tracker.unlink()

    def run_eventloop_until_download(self):
        tracker = self.feed.downloaded_items.make_tracker()
        tracker.connect('added', lambda view, obj: eventloop.shutdown())
        try:
            self.runEventLoop()
        finally:
            tracker.unlink()

    def download_item(self):
        self.feed.update()
        self.run_eventloop_until_items()
        self.assertEquals(self.feed.items.count(), 1)
        i = list(self.feed.items)[0]
        i.download()
        self.run_eventloop_until_download()

    def test_download(self):
        self.download_item()

    def test_delete(self):
        self.download_item()
        self.assertEquals(self.feed.items.count(), 1)
        list(self.feed.items)[0].expire()

