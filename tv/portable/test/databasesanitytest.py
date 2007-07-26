"""Test database sanity checking.  Right now this is pretty short because we
don't do that much sanity checking.
"""

import os
import tempfile
import unittest

import iconcache
import item
import feed
import databasesanity
import database
import util

from test.framework import DemocracyTestCase

class SanityCheckingTest(DemocracyTestCase):
    def setUp(self):
        DemocracyTestCase.setUp(self)
        self.savePath = tempfile.mktemp()
        # reroute util.failed
        self.utilDotFailedOkay = True

    def tearDown(self):
        try:
            os.unlink(self.savePath)
        except OSError:
            pass
        util.failed = self.oldUtilDotFailed
        DemocracyTestCase.tearDown(self)

    def checkObjectListFailsTest(self, objectList):
        self.assertRaises(databasesanity.DatabaseInsaneError,
                databasesanity.checkSanity, objectList, False)

    def checkFixIfPossible(self, startList, fixedList):
        self.failedCalled = False
        rv = databasesanity.checkSanity(startList)
        self.assertEquals(startList, fixedList)
        self.assertEquals(rv, False)
        self.assertEquals(self.failedCalled, True)

    def checkObjectListPassesTest(self, objectList):
        databasesanity.checkSanity(objectList)

    def testPhantomFeedChecking(self):
        f = feed.Feed(u"http://feed.uk")
        i = item.Item({}, feed_id=f.id)
        i2 = item.FileItem('/foo/bar.txt', feed_id=f.id)
        self.checkObjectListFailsTest([i])
        self.checkFixIfPossible([i, i2], [])
        self.checkObjectListPassesTest([i, f])
        self.checkObjectListPassesTest([])

    def testManualFeedChecking(self):
        f = feed.Feed(u"dtv:manualFeed")
        f2 = feed.Feed(u"dtv:manualFeed")
        f3 = feed.Feed(u"dtv:manualFeed")
        self.checkObjectListPassesTest([f])
        self.checkObjectListFailsTest([f, f2])
        self.failedCalled = False
        testList = [f, f2, f3]
        databasesanity.checkSanity(testList)
        self.assertEquals(len(testList), 1)
        self.assertEquals(self.failedCalled, True)
