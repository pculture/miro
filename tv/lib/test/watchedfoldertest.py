import os
import shutil

from miro import app
from miro import models
from miro import signals
from miro.test import mock
from miro.test.framework import MiroTestCase, EventLoopTest
from miro.plat import resources
from miro.plat.utils import make_url_safe

class FakeDirectoryWatcher(signals.SignalEmitter):
    def __init__(self, directory):
        signals.SignalEmitter.__init__(self, 'added', 'deleted')

class WatchedFolderTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        app.directory_watcher = FakeDirectoryWatcher
        self.dir = self.make_temp_dir_path()
        self.url = u'dtv:directoryfeed:%s' % make_url_safe(self.dir)
        self.feed = models.Feed(self.url)
        self.source_path = resources.path("testdata/pop.mp3")
        self.directory_watcher = self.feed.actualFeed.watcher
        # not having to wait for a timeout makes the tests simpler and faster
        self.feed.actualFeed.DIRECTORY_WATCH_UPDATE_TIMEOUT = 0.0

    def tearDown(self):
        app.directory_watcher = None
        EventLoopTest.tearDown(self)

    def copy_new_file(self, filename):
        dest_path = os.path.join(self.dir, filename)
        shutil.copyfile(self.source_path, dest_path)

    def run_feed_update(self):
        self.feed.update()
        # make sure the update processes
        self.runPendingIdles()

    def check_items(self, *filenames):
        files = [i.get_filename() for i in self.feed.items]
        if len(files) != len(set(files)):
            raise AssertionError("Duplicate files in feed: %s" % files)
        correct_files = [os.path.join(self.dir, f) for f in filenames]
        self.assertSameSet(files, correct_files)

    def remove_file(self, filename):
        os.remove(os.path.join(self.dir, filename))

    def test_scan(self):
        self.copy_new_file('a.mp3')
        self.copy_new_file('b.mp3')
        self.run_feed_update()
        self.check_items('a.mp3', 'b.mp3')

    def test_removed(self):
        self.copy_new_file('a.mp3')
        self.copy_new_file('b.mp3')
        self.run_feed_update()
        self.check_items('a.mp3', 'b.mp3')
        self.remove_file('a.mp3')
        self.run_feed_update()
        self.check_items('b.mp3')

    def test_scan_duplicates(self):
        self.copy_new_file('a.mp3')
        self.copy_new_file('b.mp3')
        self.run_feed_update()
        # run the second directory scan will see the same files, we shouldn't
        # add them again.
        self.run_feed_update()
        self.check_items('a.mp3', 'b.mp3')

    def send_watcher_signal(self, signal, filename):
        self.directory_watcher.emit(signal, os.path.join(self.dir, filename))

    def test_watcher_added(self):
        self.copy_new_file('a.mp3')
        self.copy_new_file('b.mp3')
        self.run_feed_update()
        self.check_items('a.mp3', 'b.mp3')
        # simulate directory watcher informing the feed about an added file
        self.copy_new_file('c.mp3')
        self.send_watcher_signal("added", "c.mp3")
        self.run_pending_timeouts()
        self.check_items('a.mp3', 'b.mp3', 'c.mp3')
        # if we already know about the file, nothing should be added
        self.send_watcher_signal("added", "a.mp3")
        self.send_watcher_signal("added", "c.mp3")
        self.run_pending_timeouts()
        self.check_items('a.mp3', 'b.mp3', 'c.mp3')

    def test_watcher_deleted(self):
        self.copy_new_file('a.mp3')
        self.copy_new_file('b.mp3')
        self.run_feed_update()
        self.check_items('a.mp3', 'b.mp3')
        # simulate directory watcher informing feed about a deleted file
        self.remove_file('a.mp3')
        self.send_watcher_signal("deleted", "a.mp3")
        self.run_pending_timeouts()
        self.check_items('b.mp3')
        # deleted for a file not contained in our feed shouldn't crash
        self.send_watcher_signal("deleted", "a.mp3")
        self.send_watcher_signal("deleted", "never-there.mp3")
        self.run_pending_timeouts()
        self.check_items('b.mp3')

    def test_double_update(self):
        # call update twice on our feed and check that we only scan the
        # directory once.

        # set up some machinery to count how many times do_update() is called
        self.update_count = 0
        real_update_func = self.feed.actualFeed.do_update
        def intercept_update():
            self.update_count += 1
            real_update_func()
        self.feed.actualFeed.do_update = intercept_update
        # setup is done, try calling update twice
        self.feed.update()
        self.feed.update()
        self.runPendingIdles()
        self.assertEquals(self.update_count, 1)
        # We're done with the update, check that a new call results in another
        # scan
        self.feed.update()
        self.runPendingIdles()
        self.assertEquals(self.update_count, 2)

    def test_remove_duplicates_on_update(self):
        self.copy_new_file('a.mp3')
        self.copy_new_file('b.mp3')
        self.run_feed_update()
        self.check_items('a.mp3', 'b.mp3')
        # force the watched folder to create a duplicate entry, this should
        # result in a soft failure, but everything else should be okay
        self.feed.actualFeed._make_child(os.path.join(self.dir, 'a.mp3'))
        app.controller.failed_soft_okay = True
        self.run_feed_update()
        self.check_items('a.mp3', 'b.mp3')
        # check that we don't delete the file
        self.assert_(os.path.exists(os.path.join(self.dir, 'a.mp3')))
        # check that if there's a bunch of files missing, we only send 1
        # message
        self.reset_failed_soft_count()
        self.feed.actualFeed._make_child(os.path.join(self.dir, 'a.mp3'))
        self.feed.actualFeed._make_child(os.path.join(self.dir, 'a.mp3'))
        self.feed.actualFeed._make_child(os.path.join(self.dir, 'a.mp3'))
        self.run_feed_update()
        self.check_failed_soft_count(1)
