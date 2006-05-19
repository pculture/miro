"""Test database sanity checking.  Right now this is pretty short because we
don't do that much sanity checking.
"""

import os
import tempfile
import unittest

import item
import feed
import databasesanity
import database
import util

class SanityCheckingTest(unittest.TestCase):
    def setUp(self):
        self.savePath = tempfile.mktemp()
        # reroute util.failed
        self.oldUtilDotFailed = util.failed
        self.failedCalled = False
        def newUtilDotFailed(*args, **kwargs):
            self.failedCalled = True
        util.failed = newUtilDotFailed

    def tearDown(self):
        try:
            os.unlink(self.savePath)
        except OSError:
            pass
        util.failed = self.oldUtilDotFailed
        database.resetDefaultDatabase()

    def testPhantomFeedChecking(self):
        f = feed.Feed("http://feed.uk")
        i = item.Item(f, {})
        # Databases with item's that have missing feeds are insane
        self.assertRaises(databasesanity.DatabaseInsaneError,
                databasesanity.checkSanity, [i], False)
        # test fixing the list 
        self.assertEquals(self.failedCalled, False)
        self.assertEquals(databasesanity.checkSanity([i]), [i, f])
        self.assertEquals(self.failedCalled, True)
        # Once the feed is there too, we're okay again
        databasesanity.checkSanity([i, f])
