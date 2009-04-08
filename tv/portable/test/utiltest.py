import os
import os.path
import tempfile

from miro.test.framework import MiroTestCase
from miro import download_utils
from miro import util


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

class LoggingStreamTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.warnings = []
        self.errors = []
        self.stdout = util.AutoLoggingStream(self.warn_callback, '(from stdout) ')
        self.stderr = util.AutoLoggingStream(self.err_callback, '(from stderr) ')

    def _check_data(self, data):
        """Check that write is always called with a string object (unicode
        won't always work when writing to stdout)
        """
        if not isinstance(data, str):
            raise ValueError("Got non-string object (%r) from LoggingStream" %
                    data)

    def warn_callback(self, data):
        self._check_data(data)
        self.warnings.append(data)

    def err_callback(self, data):
        self._check_data(data)
        self.errors.append(data)

    def testBasicWrite(self):
        self.stdout.write("Hello World\n")
        self.stdout.write("")
        self.stderr.write("LotsofData" * 200)
        self.assertEquals(len(self.warnings), 1)
        self.assertEquals(self.warnings[0], '(from stdout) Hello World')
        self.assertEquals(len(self.errors), 1)
        self.assertEquals(self.errors[0], '(from stderr) ' + 
            "LotsofData" * 200)

    def testUnicodeWrite(self):
        self.stdout.write(u'\xf8')
        self.assertEquals(len(self.warnings), 1)
        self.assertEquals(self.warnings[0], '(from stdout) \\xf8')

class UtilTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
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

class Test_simple_config_file(MiroTestCase):
    def test_read_simple_config_file(self):
        t = tempfile.gettempprefix()
        fn = os.path.join(t, "temp.config")

        if not os.path.exists(os.path.dirname(fn)):
            os.makedirs(os.path.dirname(fn))

        try:
            f = open(fn, "w")
            f.write("""
a = b
c = dSSS

E = F
""".strip().replace("S", " "))
            f.close()

            cfg = util.read_simple_config_file(fn)
            self.assertEquals(cfg["a"], "b")
            self.assertEquals(cfg["c"], "d   ")
            self.assertEquals(cfg["E"], "F")
            self.assertEquals(cfg.get("G"), None)
        finally:
            os.remove(fn)

    def test_write_simple_config_file(self):
        t = tempfile.gettempprefix()
        fn = os.path.join(t, "temp.config")

        if not os.path.exists(os.path.dirname(fn)):
            os.makedirs(os.path.dirname(fn))

        try:
            cfg = {"a": "b",
                   "c": "d",
                   "E": "F   "}
            util.write_simple_config_file(fn, cfg)

            cfg2 = util.read_simple_config_file(fn)
            self.assertEquals(cfg2["a"], cfg["a"])
            self.assertEquals(cfg2["c"], cfg["c"])
            self.assertEquals(cfg2["E"], cfg["E"])
        finally:
            os.remove(fn)

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
