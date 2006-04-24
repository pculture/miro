import os
import shutil
import tempfile
import unittest

import olddatabaseupgrade
import storedatabase
import databaseupgrade
import resource

class TestConvert(unittest.TestCase):
    def setUp(self):
        storedatabase.skipOnRestore = True
        databaseupgrade.chatter = False
        self.tmpPath = tempfile.mktemp()

    def tearDown(self):
        storedatabase.skipOnRestore = False
        try:
            os.unlink(self.tmpPath)
        except:
            pass

    def checkConversion(self):
        olddatabaseupgrade.convertOldDatabase(self.tmpPath)
        objects = storedatabase.restoreObjectList(self.tmpPath)
        # Not sure what kind of checks we can do on the restored objects,
        # let's make sure that they are there at least.
        self.assert_(len(objects) > 0)

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
