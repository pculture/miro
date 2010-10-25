import shutil
import os
import pstats
import cProfile

from miro import app
from miro import messagehandler
from miro import messages
from miro import models
from miro.test.framework import EventLoopTest
from miro.test import messagetest
from miro.plat.utils import FilenameType

class TrackItemTest(EventLoopTest):
    def setUp(self):
        print 'setting up'
        EventLoopTest.setUp(self)
        # We want to store our database in a file, so that we can test
        # performance on a freshly opened db.
        save_path = FilenameType(self.make_temp_path(extension=".db"))
        if os.path.exists(save_path):
            os.unlink(save_path)
        self.reload_database(save_path)
        models.Feed(u'dtv:search')
        self.test_handler = messagetest.TestFrontendMessageHandler()
        messages.FrontendMessage.install_handler(self.test_handler)
        self.backend_message_handler = messagehandler.BackendMessageHandler(None)
        messages.BackendMessage.install_handler(self.backend_message_handler)
        self.feed = models.Feed(u'dtv:manualFeed')
        self.items = []
        template_file = self.make_temp_path(".avi")
        self.stats_path = self.make_temp_path(".prof")
        open(template_file, 'w').write(' ')
        app.bulk_sql_manager.start()
        for x in xrange(5000):
            path = self.make_temp_path(".avi")
            shutil.copyfile(template_file, path)
            models.FileItem(path, self.feed.id)
        app.bulk_sql_manager.finish()
        self.reload_database(save_path)

    def test_track_items(self):
        print 'running tests'
        cProfile.runctx("self._timed_code()", globals(), locals(),
                self.stats_path)
        stats = pstats.Stats(self.stats_path)
        print '*' * 20 + "first run" + "*" * 20
        stats.strip_dirs().sort_stats("cumulative").print_stats(0.2)

        cProfile.runctx("self._timed_code()", globals(), locals(),
                self.stats_path)
        stats = pstats.Stats(self.stats_path)
        print '*' * 20 + "second run" + "*" * 20
        stats.strip_dirs().sort_stats("cumulative").print_stats(0.2)

    def _timed_code(self):
        messages.TrackItems('feed', self.feed.id).send_to_backend()
        self.runUrgentCalls()
