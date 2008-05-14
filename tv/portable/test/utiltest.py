from StringIO import StringIO

import os
import tempfile

from miro.test.framework import MiroTestCase
from miro import download_utils
from miro import util
from miro import xhtmltools

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

class AutoflushingStreamTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.stream = FakeStream()
        self.afs = util.AutoflushingStream(self.stream)

    def testBasicWrite(self):
        self.afs.write("Hello World\n")
        self.afs.write("")
        self.afs.write("LotsofData" * 200)

    def testUnicodeWrite(self):
        self.afs.write(u'\xf8')

class UtilTest(MiroTestCase):
    def testAbsolutePathToFileURL(self):
        testPaths = {
            '/ben/dean/kawamura' : 'file:///ben/dean/kawamura',
            '/eight/bit/path/\xe4' : 'file:///eight/bit/path/%E4',
            u'/unicode/path/\xe4' : 'file:///unicode/path/%C3%A4',
        }
        for source, target in testPaths.items():
            self.assertEquals(util.absolutePathToFileURL(source), target)

    def testStringify(self):
        # input, handleerror, expected output
        # if handlerror is None, then it isn't passed in as an argument
        t = [
              ( "", None, ""),
              ( "abc", None, "abc"),
              ( 5, None, "5"),
              ( 5.5, None, "5.5"),
              ( u"abc", None, "abc"),
              ( u"abc\xe4", None, "abc&#228;"),
              ( u"abc\xe4", "replace", "abc?")
            ]

        for i, h, o in t:
            if h == None:
                self.assertEquals(util.stringify(i), o)
            else:
                self.assertEquals(util.stringify(i, h), o)

    def testRandomString(self):
        ret = util.random_string(0)
        self.assertEquals(len(ret), 0)

        for length in (1, 5, 10):
            ret = util.random_string(length)
            self.assertEquals(len(ret), length)
            self.assertEquals(ret.isalpha(), True)

class XHTMLToolsTest(MiroTestCase):
    def testMultipartEncode(self):
        vars = {
                'foo': u'123',  # unicode string
        }

        files = {
            'baz': {"filename":"binarydata.zip",
                 "mimetype":"application/octet-stream",
                 "handle": StringIO('\xf8'), 
             } # baz has invalid unicode data
        }

        boundary, data = xhtmltools.multipartEncode(vars, files)

class DownloadUtilsTest(MiroTestCase):
    def checkCleanFilename(self, filename, test_against):
        self.assertEquals(download_utils.cleanFilename(filename),
                test_against)

    def testCleanFilename(self):
        self.checkCleanFilename('normalname', 'normalname')
        self.checkCleanFilename('a:b?c>d<e|f*/g\\h"\'', 'abcdefgh')
        self.checkCleanFilename('', '_')
        longFilename = 'booya' * 100
        longExtension = '.' + 'foo' * 20
        self.checkCleanFilename(longFilename, longFilename[:100])
        # total file length isn't over the limit, so the extension stays the
        # same
        self.checkCleanFilename('abc' + longExtension, 
            'abc' + longExtension)
        self.checkCleanFilename(longFilename + longExtension,
            longFilename[:50] + longExtension[:50])
