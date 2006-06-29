import os
import shutil
import tempfile
import unittest

import olddatabaseupgrade
import storedatabase
import databaseupgrade
import databasesanity
import resource

from test.framework import DemocracyTestCase

class TestConvert(DemocracyTestCase):
    def setUp(self):
        storedatabase.skipOnRestore = True
        databaseupgrade.chatter = False
        self.utilDotFailedOkay = True
        self.tmpPath = tempfile.mktemp()
        DemocracyTestCase.setUp(self)

    def tearDown(self):
        storedatabase.skipOnRestore = False
        try:
            os.unlink(self.tmpPath)
        except:
            pass
        DemocracyTestCase.tearDown(self)

    def checkConversion(self):
        olddatabaseupgrade.convertOldDatabase(self.tmpPath)
        objects = storedatabase.restoreObjectList(self.tmpPath)
        # Not sure what kind of checks we can do on the restored objects,
        # let's make sure that they are there at least.  Also, make sure the
        # sanity tests can recover from any errors
        self.assert_(len(objects) > 0)
        databasesanity.checkSanity(objects, fixIfPossible=True)

    def testConvert82(self):
        shutil.copyfile(resource.path("testdata/olddatabase-0.8.2"), 
                self.tmpPath)
        self.checkConversion()
        shutil.copyfile(resource.path("testdata/olddatabase-0.8.2-2"), 
                self.tmpPath)
        self.checkConversion()

    def testConvert81(self):
        shutil.copyfile(resource.path("testdata/olddatabase-0.8.1"), 
                self.tmpPath)
        self.checkConversion()

    def testBug2003(self):
        # the olddatabase.bug.2003 file is a database I (BDK) created in a
        # fairly hackish way to simulate old databases like the one reported
        # in 2003 and 2515.  The testBug2515 test is much more comprehensive,
        # but I figure we may as well leave this one in.
        shutil.copyfile(resource.path("testdata/olddatabase.bug.2003"),
                self.tmpPath)
        self.checkConversion()

    def testBug2515(self):
        # Real life database that has the phantom feed with downloaders bug.
        # This one came from david moore, and was attached to #2515
        shutil.copyfile(resource.path("testdata/olddatabase.bug.2515"),
                self.tmpPath)
        self.checkConversion()
