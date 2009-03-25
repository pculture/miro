import os
import shutil
import tempfile
import unittest

from miro import database
from miro import feed
from miro import ddblinks
from miro import olddatabaseupgrade
from miro import storedatabase
from miro import databaseupgrade
from miro import databasesanity
from miro.plat import resources

from miro.test.framework import EventLoopTest

class TestConvert(EventLoopTest):
    def setUp(self):
        storedatabase.skipOnRestore = True
        self.tmpPath = tempfile.mktemp()
        feed.restored_feeds = []
        EventLoopTest.setUp(self)

    def tearDown(self):
        storedatabase.skipOnRestore = False
        try:
            os.unlink(self.tmpPath)
        except:
            pass
        EventLoopTest.tearDown(self)

    def checkConversion(self):
        olddatabaseupgrade.convertOldDatabase(self.tmpPath)
        objects = storedatabase.restoreObjectList(self.tmpPath)
        # Not sure what kind of checks we can do on the restored objects,
        # let's make sure that they are there at least.  Also, make sure the
        # sanity tests can recover from any errors
        self.assert_(len(objects) > 0)
        ddblinks.setup_links(objects)
        databasesanity.checkSanity(objects, fixIfPossible=True, quiet=True,
                reallyQuiet=True)

    def testConvert82(self):
        shutil.copyfile(resources.path("testdata/olddatabase-0.8.2"), 
                self.tmpPath)
        self.checkConversion()
        shutil.copyfile(resources.path("testdata/olddatabase-0.8.2-2"), 
                self.tmpPath)
        self.checkConversion()

    def testConvert81(self):
        shutil.copyfile(resources.path("testdata/olddatabase-0.8.1"), 
                self.tmpPath)
        self.checkConversion()

    def testBug2003(self):
        # the olddatabase.bug.2003 file is a database I (BDK) created in a
        # fairly hackish way to simulate old databases like the one reported
        # in 2003 and 2515.  The testBug2515 test is much more comprehensive,
        # but I figure we may as well leave this one in.
        shutil.copyfile(resources.path("testdata/olddatabase.bug.2003"),
                self.tmpPath)
        self.checkConversion()

    def testBug2515(self):
        # Real life database that has the phantom feed with downloaders bug.
        # This one came from david moore, and was attached to #2515
        shutil.copyfile(resources.path("testdata/olddatabase.bug.2515"),
                self.tmpPath)
        self.checkConversion()

    def testBug2685(self):
        # Database created by ben to simulate bug #2685
        shutil.copyfile(resources.path("testdata/olddatabase.bug.2685"),
                self.tmpPath)
        self.checkConversion()

    def testBug3163(self):
        # Database created by ben to simulate bug #3163 (channel guide doesn't
        # have an id attribute).
        shutil.copyfile(resources.path("testdata/olddatabase.bug.3163"),
                self.tmpPath)
        self.checkConversion()

    def testBug4039(self):
        # Test that when databases fail sanity tests, we don't call
        # onRestore() for the objects that failed.  olddatabase.bug.4039
        # contains a database an item whose feed doesn't exist.
        shutil.copyfile(resources.path("testdata/olddatabase.bug.4039"),
                self.tmpPath)
        db = database.DynamicDatabase()
        storedatabase.skipOnRestore = False
        storedatabase.restoreDatabase(db=db, pathname=self.tmpPath)
        # if onRestore() was called, we would have added the feed to the
        # restored_feeds list
        self.assertEquals(len(db.objects), 0)
        self.assertEquals(len(feed.restored_feeds), 0)

    def testBug4039part2(self):
        # On the other hand, for database that are normal, we should call
        # onRestore()
        shutil.copyfile(resources.path("testdata/olddatabase.bug.4039.part2"),
                self.tmpPath)
        db = database.DynamicDatabase()
        storedatabase.skipOnRestore = False
        storedatabase.restoreDatabase(db=db, pathname=self.tmpPath)
        self.assertEquals(len(db.objects), 3)
        self.assertEquals(len(feed.restored_feeds), 1)
