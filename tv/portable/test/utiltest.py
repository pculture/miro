from StringIO import StringIO

import os
import tempfile

from miro.test.framework import MiroTestCase
from miro import download_utils
from miro import util
from miro import xhtmltools


# We're going to override this so we can guarantee that if the order
# changes later that it doesn't really affect us.
util.PREFERRED_TYPES = [
    'application/x-bittorrent', 'video/ogg', 'video/mp4',
    'video/quicktime', 'video/mpeg']


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
    def setUp(self):
        self.filesize_elements = [
            {'href': u'http://example.org/1.ogg',
             'type': u'video/ogg',
             'filesize': u'21663'},
            {'href': u'http://example.org/2.ogg',
             'type': u'video/ogg',
             'filesize': u'notafilesize'},
            {'href': u'http://example.org/3.ogg',
             'type': u'video/ogg',
             'filesize': u'288'},
            {'href': u'http://example.org/4.ogg',
             'type': u'video/ogg',
             'filesize': u'800088'},
            {'href': u'http://example.org/5.ogg',
             'type': u'video/ogg',
             'filesize': u'82'}]
        self.type_elements = [
            {'href': u'http://example.org/1.mp4',
             'type': u'video/mp4',
             'filesize': u'2000'},
            {'href': u'http://example.org/2.mpeg',
             'type': u'video/mpeg',
             'filesize': u'2000'},
            {'href': u'http://example.org/3.mov',
             'type': u'video/quicktime',
             'filesize': u'2000'},
            {'href': u'http://example.org/4.torrent',
             'type': u'application/x-bittorrent',
             'filesize': u'2000'},
            {'href': u'http://example.org/5.ogg',
             'type': u'video/ogg',
             'filesize': u'2000'}]
        self.combination_elements = [
            {'href': u'http://example.org/1.ogg',
             'type': u'video/ogg',
             'filesize': u'302999'},
            {'href': u'http://example.org/2.mov',
             'type': u'video/quicktime',
             'filesize': u'2000'},
            {'href': u'http://example.org/3.mp4',
             'type': u'video/mp4',
             'filesize': u'401971'},
            {'href': u'http://example.org/4.ogg',
             'type': u'video/ogg',
             'filesize': u'166955'},
            {'href': u'http://example.org/5.mpeg',
             'type': u'video/mpeg',
             'filesize': u'244700'}]

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

    def testCmpEnclosures(self):
        """
        Test for util.cmp_enclosures
        """
        def get_hrefs(enclosures):
            return [enclosure['href'] for enclosure in enclosures]

        self.filesize_elements.sort(util.cmp_enclosures)
        self.type_elements.sort(util.cmp_enclosures)
        self.combination_elements.sort(util.cmp_enclosures)

        self.assertEqual(
            get_hrefs(self.filesize_elements),
            [u'http://example.org/4.ogg',
             u'http://example.org/1.ogg',
             u'http://example.org/3.ogg',
             u'http://example.org/5.ogg',
             u'http://example.org/2.ogg'])
        self.assertEqual(
            get_hrefs(self.type_elements),
            [u'http://example.org/4.torrent',
             u'http://example.org/5.ogg',
             u'http://example.org/1.mp4',
             u'http://example.org/3.mov',
             u'http://example.org/2.mpeg'])
        self.assertEqual(
            get_hrefs(self.combination_elements),
            [u'http://example.org/1.ogg',
             u'http://example.org/4.ogg',
             u'http://example.org/3.mp4',
             u'http://example.org/2.mov',
             u'http://example.org/5.mpeg'])
            
    def testGetFirstVideoEnclosure(self):
        """
        Test for util.getFirstVideoEnclosure
        """
        class FakeEntry(object):
            def __init__(self, enclosures):
                self.enclosures = enclosures

        # set up the entries..
        filesizes_entry = FakeEntry(self.filesize_elements)
        types_entry = FakeEntry(self.type_elements)
        combinations_entry = FakeEntry(self.combination_elements)

        # get their "selected" results
        selected_filesize = util.getFirstVideoEnclosure(filesizes_entry)
        selected_type = util.getFirstVideoEnclosure(types_entry)
        selected_combination = util.getFirstVideoEnclosure(combinations_entry)

        # now make sure they returned what we expected..
        self.assertEqual(selected_filesize['href'], u'http://example.org/4.ogg')
        self.assertEqual(selected_type['href'], u'http://example.org/4.torrent')
        self.assertEqual(selected_combination['href'],
                         u'http://example.org/1.ogg')

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

class MatrixTest(MiroTestCase):
    def testMatrixInit(self):
        m = util.Matrix(1, 2)
        self.assertEquals(list(m), [None, None])

        m = util.Matrix(2, 1)
        self.assertEquals(list(m), [None, None])

        m = util.Matrix(1, 5)
        self.assertEquals(m.columns, 1)
        self.assertEquals(m.rows, 5)

        m = util.Matrix(0, 0)
        self.assertEquals(m.columns, 0)
        self.assertEquals(m.rows, 0)

        m = util.Matrix(5, 1)
        self.assertEquals(m.columns, 5)
        self.assertEquals(m.rows, 1)

        self.assertEquals(m[0, 0], None)
        self.assertEquals(m[1, 0], None)
        self.assertEquals(m[2, 0], None)
        self.assertEquals(m[3, 0], None)
        self.assertEquals(m[4, 0], None)

    def testGetSet(self):
        m = util.Matrix(3, 2)
        m[0, 0] = 1
        m[0, 1] = 2
        m[1, 0] = 3
        m[1, 1] = 4
        m[2, 0] = 5
        m[2, 1] = 6

        self.assertEquals(m[0,0], 1)
        self.assertEquals(m[1,0], 3)
        self.assertEquals(m[2,0], 5)

        m[0,0] = 17
        self.assertEquals(m[0,0], 17)

    def testRowsColumns(self):
        m = util.Matrix(3, 2)
        m[0, 0] = 1
        m[0, 1] = 2
        m[1, 0] = 3
        m[1, 1] = 4
        m[2, 0] = 5
        m[2, 1] = 6

        self.assertEquals(list(m.row(0)), [1, 3, 5])
        self.assertEquals(list(m.row(1)), [2, 4, 6])
        self.assertEquals(list(m.column(0)), [1, 2])
        self.assertEquals(list(m.column(1)), [3, 4])
        self.assertEquals(list(m.column(2)), [5, 6])

    def testRemove(self):
        m = util.Matrix(1, 2)
        m[0,0] = 1
        m[0,1] = 2

        m.remove(2)

        self.assertEquals(m[0,0], 1)
        self.assertEquals(m[0,1], None)
