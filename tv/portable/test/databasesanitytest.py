"""Test database sanity checking.  Right now this is pretty short
because we don't do that much sanity checking.
"""

import os
import tempfile
import unittest

from miro import iconcache
from miro import item
from miro import feed
from miro import databasesanity
from miro import database
from miro import util

from miro.test.framework import MiroTestCase

class SanityCheckingTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.save_path = tempfile.mktemp()

    def tearDown(self):
        try:
            os.unlink(self.save_path)
        except OSError:
            pass
        MiroTestCase.tearDown(self)

    def check_object_list_fails_test(self, object_list):
        self.assertRaises(databasesanity.DatabaseInsaneError,
                          databasesanity.check_sanity, object_list, False)

    def check_fix_if_possible(self, start_list, fixed_list):
        self.error_signal_okay = True
        rv = databasesanity.check_sanity(start_list)
        self.assertEquals(start_list, fixed_list)
        self.assertEquals(rv, False)
        self.assertEquals(self.saw_error, True)

    def check_object_list_passes_test(self, object_list):
        databasesanity.check_sanity(object_list)

    def test_phantom_feed_checking(self):
        f = feed.Feed(u"http://feed.uk")
        i = item.Item(item.FeedParserValues({}), feed_id=f.id)
        i2 = item.FileItem('/foo/bar.txt', feed_id=f.id)
        self.check_object_list_fails_test([i])
        self.check_fix_if_possible([i, i2], [])
        self.check_object_list_passes_test([i, f])
        self.check_object_list_passes_test([])

    def test_manual_feed_checking(self):
        f = feed.Feed(u"dtv:manualFeed")
        f2 = feed.Feed(u"dtv:manualFeed")
        f3 = feed.Feed(u"dtv:manualFeed")
        self.check_object_list_passes_test([f])
        self.check_object_list_fails_test([f, f2])
        self.error_signal_okay = True
        test_list = [f, f2, f3]
        databasesanity.check_sanity(test_list)
        self.assertEquals(len(test_list), 1)
        self.assertEquals(self.saw_error, True)
