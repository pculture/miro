import os
import tempfile

from test.framework import DemocracyTestCase
import util

class FakeStream:
    """Fake streams are used for the AutoflushingStream test.  They don't
    really do much, except check that write is always called with a string
    object (unicode won't always work when writing to stdout).
    """

    def write(self, out):
        if not isinstance(out, str):
            raise ValueError("Got non-string object (%s) from "
            "autoflushing stream" % str.__class__)
    def flush(self):
        pass

class AutoflushingStreamTest(DemocracyTestCase):
    def setUp(self):
        DemocracyTestCase.setUp(self)
        self.stream = FakeStream()
        self.afs = util.AutoflushingStream(self.stream)

    def testBasicWrite(self):
        self.afs.write("Hello World\n")
        self.afs.write("")
        self.afs.write("LotsofData" * 200)

    def testUnicodeWrite(self):
        self.afs.write(u'\xf8')
