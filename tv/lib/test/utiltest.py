# coding=latin-1
# The above comment is required, because it includes non-latin characters
# as an inline string in the source, we need to have this here as per PEP 263.
import itertools
import os
import tempfile
import time
import signal
import shutil
import unittest
import sys
import zipfile

from miro.test.framework import skip_for_platforms, MiroTestCase
from miro import download_utils
from miro import util
from miro import buildutils
from miro.fileobject import FilenameType
from miro.plat.utils import unicode_to_filename

# We're going to override this so we can guarantee that if the order
# changes later that it doesn't really affect us.
util.PREFERRED_TYPES = [
    'application/x-bittorrent', 'video/ogg', 'video/mp4',
    'video/quicktime', 'video/mpeg']

class FakeStream:
    """Fake streams are used for the AutoFlushingStream test.  They
    don't really do much, except check that write is always called
    with a string object (unicode won't always work when writing to
    stdout).
    """

    def write(self, out):
        if not isinstance(out, str):
            raise ValueError("Got non-string object (%s) from "
            "autoflushing stream" % str.__class__)

    def flush(self):
        pass

class MockCache(util.Cache):
    """
    MockCache is used to test the Cache object.  The new values are a tuple of
    the value passed in and a counter value, incremented each time a new value
    is made.
    """
    def __init__(self, size):
        util.Cache.__init__(self, size)
        self.value_counter = itertools.count()

    def create_new_value(self, val, invalidator=None):
        return (val, self.value_counter.next())

class AutoFlushingStreamTest(unittest.TestCase):
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.stream = FakeStream()
        self.afs = util.AutoFlushingStream(self.stream)

    def test_basic_write(self):
        self.afs.write("Hello World\n")
        self.afs.write("")
        self.afs.write("LotsofData" * 200)

    def test_unicode_write(self):
        self.afs.write(u'\xf8')

class LoggingStreamTest(unittest.TestCase):
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.warnings = []
        self.errors = []
        self.stdout = util.AutoLoggingStream(
            self.warn_callback, '(from stdout) ')
        self.stderr = util.AutoLoggingStream(
            self.err_callback, '(from stderr) ')

    def _check_data(self, data):
        """Check that write is always called with a string object
        (unicode won't always work when writing to stdout)
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

    def test_basic_write(self):
        self.stdout.write("Hello World\n")
        self.stdout.write("")
        self.stderr.write("LotsofData" * 200)
        self.assertEquals(len(self.warnings), 1)
        self.assertEquals(self.warnings[0], '(from stdout) Hello World')
        self.assertEquals(len(self.errors), 1)
        self.assertEquals(self.errors[0], '(from stderr) ' +
            "LotsofData" * 200)

    def test_unicode_write(self):
        self.stdout.write(u'\xf8')
        self.assertEquals(len(self.warnings), 1)
        self.assertEquals(self.warnings[0], '(from stdout) \\xf8')

class UtilTest(unittest.TestCase):
    def setUp(self):
        unittest.TestCase.setUp(self)
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

    def test_is_url_positive(self):
        for testurl in [u"http://foo.bar.com/",
                        u"https://foo.bar.com/",
                        ]:
            self.assertEqual(util.is_url(testurl), True)

    def test_is_url_negative(self):
        for testurl in [u"",
                        None,
                        u"feed://foo.bar.com/",
                        u"http://foo.bar.com",
                        u"http:foo.bar.com/",
                        u"https:foo.bar.com/",
                        u"feed:foo.bar.com/",
                        u"http:/foo.bar.com/",
                        u"https:/foo.bar.com/",
                        u"feed:/foo.bar.com/",
                        u"http:///foo.bar.com/",
                        u"https:///foo.bar.com/",
                        u"feed:///foo.bar.com/",
                        u"foo.bar.com",
                        u"crap:foo.bar.com",
                        u"crap:/foo.bar.com",
                        u"crap://foo.bar.com",
                        u"crap:///foo.bar.com",
                        # Bug #12645
                        u"No license (All rights reserved)",
                        ]:
            self.assertEqual(util.is_url(testurl), False)

    def test_stringify(self):
        # input, handleerror, expected output if handlerror is None,
        # then it isn't passed in as an argument

        class GoodStringObject(object):
            """Object whose __str__ method returns an ASCII string."""
            def __str__(self):
                return "abc"

        class BadStringObject(object):
            """Object whose __str__ method returns a non-ASCII string."""
            def __str__(self):
                return "abc\xe4"

        for i, h, o in [
            ( "", None, ""),
            ( "abc", None, "abc"),
            ( 5, None, "5"),
            ( 5.5, None, "5.5"),
            ( u"abc", None, "abc"),
            ( u"abc\xe4", None, "abc&#228;"),
            ( u"abc\xe4", "replace", "abc?"),
            # test that bytestrings are converted to plain ASCII
            ( "abc", None, "abc"),
            ( "abc\xe4", None, "abc?"),
            # test that objects are converted to plain ASCII
            ( GoodStringObject(), None, "abc"),
            ( BadStringObject(), None, "abc?"),
            ]:

            if h == None:
                self.assertEquals(util.stringify(i), o)
            else:
                self.assertEquals(util.stringify(i, h), o)

    def test_random_string(self):
        ret = util.random_string(0)
        self.assertEquals(len(ret), 0)

        for length in (1, 5, 10):
            ret = util.random_string(length)
            self.assertEquals(len(ret), length)
            self.assertEquals(ret.isalpha(), True)

    def test_cmp_enclosures(self):
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

    def test_get_first_video_enclosure(self):
        """
        Test for util.get_first_video_enclosure
        """
        class FakeEntry(object):
            def __init__(self, enclosures):
                self.enclosures = enclosures

        # set up the entries..
        filesizes_entry = FakeEntry(self.filesize_elements)
        types_entry = FakeEntry(self.type_elements)
        combinations_entry = FakeEntry(self.combination_elements)

        # get their "selected" results
        selected_filesize = util.get_first_video_enclosure(filesizes_entry)
        selected_type = util.get_first_video_enclosure(types_entry)
        selected_combination = util.get_first_video_enclosure(
            combinations_entry)

        # now make sure they returned what we expected..
        self.assertEqual(selected_filesize['href'],
                         u'http://example.org/4.ogg')
        self.assertEqual(selected_type['href'],
                         u'http://example.org/4.torrent')
        self.assertEqual(selected_combination['href'],
                         u'http://example.org/1.ogg')

    def test_clamp_text(self):
        # limit 20
        self.assertRaises(TypeError, util.clamp_text, None)
        self.assertEqual('', util.clamp_text(''))
        self.assertEqual('1', util.clamp_text('1'))
        self.assertEqual('12345678901234567890',
                         util.clamp_text('12345678901234567890'))
        self.assertEqual('12345678901234567...',
                         util.clamp_text('123456789012345678901'))
        self.assertEqual('12345678901234567...',
                         util.clamp_text(
                             '12345678901234567890 1234 1234 1234'))

        # limit 4
        self.assertRaises(TypeError, util.clamp_text, None, 4)
        self.assertEqual('', util.clamp_text('', 4))
        self.assertEqual('1', util.clamp_text('1', 4))
        self.assertEqual(
            '1...', util.clamp_text('12345678901234567890', 4))
        self.assertEqual(
            '1...', util.clamp_text('123456789012345678901', 4))
        self.assertEqual(
            '1...', util.clamp_text('12345678901234567890 1234 1234 1234', 4))

    def test_check_u(self):
        util.check_u(None)
        util.check_u(u'abc')
        util.check_u(u'&*@!#)*) !@)( !@# !)@(#')

        self.assertRaises(util.MiroUnicodeError, util.check_u, 'abc')
        self.assertRaises(util.MiroUnicodeError,
                          util.check_u, '&*@!#)*) !@)( !@# !)@(#')

    def test_check_b(self):
        util.check_b(None);
        util.check_b("abc");

        self.assertRaises(util.MiroUnicodeError, util.check_b, 42)
        self.assertRaises(util.MiroUnicodeError, util.check_b, [])
        self.assertRaises(util.MiroUnicodeError, util.check_b, ['1','2'])
        self.assertRaises(util.MiroUnicodeError, util.check_b, {})
        self.assertRaises(util.MiroUnicodeError, util.check_b, {'a': 1, 'b':2})

    def test_check_f(self):
        def test_name(text):
            correct_type = FilenameType(text)
            util.check_f(correct_type)

            if sys.platform == 'win32':
                incorrect_type = str(text)
            else:
                incorrect_type = unicode(text)

            self.assertRaises(util.MiroUnicodeError,
                              util.check_f, incorrect_type)

        util.check_f(None)
        test_name("")
        test_name("abc.txt")
        test_name("./xyz.avi")

    def assertEqualWithType(self, expected, expectedType, val):
        self.assertEqual(val, expected)
        self.assertTrue(isinstance(val, expectedType),
                        "Not of type " + str(expectedType))

    def test_unicodify(self):

        self.assertEqual(None, util.unicodify(None))

        # Int
        self.assertEqualWithType(5, int, util.unicodify(5))

        # String
        self.assertEqualWithType('abc', unicode, util.unicodify('abc'))

        # List
        res = util.unicodify(['abc', '123'])
        self.assertEqualWithType('abc', unicode, res[0])
        self.assertEqualWithType('123', unicode, res[1])

        # Dict
        res = util.unicodify({'a': 'abc', 'b': '123'})
        self.assertEqualWithType('abc', unicode, res['a'])
        self.assertEqualWithType('123', unicode, res['b'])

        # List of dicts
        res = util.unicodify([{'a': 'abc', 'b': '$$$'},
                              {'y': u'25', 'z': '28'}])
        self.assertEqualWithType('abc', unicode, res[0]['a'])
        self.assertEqualWithType('$$$', unicode, res[0]['b'])
        self.assertEqualWithType('25', unicode, res[1]['y'])
        self.assertEqualWithType('28', unicode, res[1]['z'])

    def test_quote_unicode_url(self):
        # Non-unicode
        self.assertRaises(util.MiroUnicodeError, util.quote_unicode_url,
            'http://www.example.com')

        # Unicode, no substitution
        self.assertEqualWithType('http://www.example.com', unicode,
            util.quote_unicode_url(u'http://www.example.com'))

        # Unicode, substitution
        self.assertEqualWithType(u'http://www.example.com/fran%C3%83%C2%A7ois',
            unicode,
            util.quote_unicode_url(u'http://www.example.com/fran\xc3\xa7ois'))

    def test_call_command_failure(self):
        # command doesn't exist
        self.assertRaises(OSError, util.call_command, 'thiscommanddoesntexist')

        # command exists but invalid option and returns error code.
        #
        # Note: on win32, this probably requires cygwin.
        self.assertRaises(OSError, util.call_command,  'ps', '--badarg')

    @skip_for_platforms('win32')
    def test_call_command_success(self):
        pid = int(os.getpid())
        stdout = util.call_command('ps', '-p', str(pid), '-o', 'pid=')
        pid_read = int(stdout)
        self.assertEqual(pid, pid_read)

    def test_to_uni(self):
        # try it twice to make sure the cached value is correct as well
        for i in range(0,2):
            self.assertEqualWithType('', unicode, util.to_uni(''))
            self.assertEqualWithType('', unicode, util.to_uni(u''))
            self.assertEqualWithType('abc', unicode, util.to_uni('abc'))
            self.assertEqualWithType('abc', unicode, util.to_uni(u'abc'))
            self.assertEqualWithType('!@^)!@%I*', unicode,
                                     util.to_uni('!@^)!@%I*'))
            self.assertEqualWithType('!@^)!@%I*', unicode,
                                     util.to_uni(u'!@^)!@%I*'))

    def test_escape(self):
        # try it twice to make sure the cached value is correct as well
        for i in range(0,2):
            self.assertEqualWithType('', unicode, util.escape(''))
            self.assertEqualWithType('&amp;', unicode, util.escape('&'))
            self.assertEqualWithType('&lt;', unicode, util.escape('<'))
            self.assertEqualWithType('&gt;', unicode, util.escape('>'))
            self.assertEqualWithType('la &amp; &lt;html&gt;', unicode,
                                     util.escape('la & <html>'))

    def test_entity_replace(self):
        self.assertEqual('', util.entity_replace(''))
        self.assertEqual('abcd yz XXX i!@#$%^&*()= 123 <>&',
                         util.entity_replace(
                             'abcd yz XXX i!@#$%^&*()= 123 <>&'))
        self.assertEqual('&#35;', util.entity_replace('&#35;'))
        self.assertEqual('\'', util.entity_replace('&#39;'))
        self.assertEqual('\'', util.entity_replace('&apos;'))
        self.assertEqual('"', util.entity_replace('&#34;'))
        self.assertEqual('"', util.entity_replace('&quot;'))
        self.assertEqual('&', util.entity_replace('&#38;'))
        self.assertEqual('&', util.entity_replace('&amp;'))
        self.assertEqual('<', util.entity_replace('&#60;'))
        self.assertEqual('<', util.entity_replace('&lt;'))
        self.assertEqual('>', util.entity_replace('&#62;'))
        self.assertEqual('>', util.entity_replace('&gt;'))
        self.assertEqual('abcd yz XX<X i!@#$%^&*()=& 123 <>&',
                         util.entity_replace(
                             'abcd yz XX&lt;X i!@#$%^&*()=&#38; 123 <>&'))

    def test_ascii_lower(self):
        self.assertEqual('', util.ascii_lower(''))
        self.assertEqual('a', util.ascii_lower('a'))
        self.assertEqual('a', util.ascii_lower('A'))
        self.assertEqual('ab', util.ascii_lower('AB'))
        self.assertEqual('a b', util.ascii_lower('A B'))
        self.assertEqual('a b', util.ascii_lower('a B'))
        self.assertEqual('a-b', util.ascii_lower('A-B'))
        self.assertEqual('\xD1', util.ascii_lower('\xD1'))
        self.assertEqual(';2%/*()_-?+z', util.ascii_lower(';2%/*()_-?+Z'))


class DownloadUtilsTest(MiroTestCase):
    def check_clean_filename(self, filename, test_against):
        self.assertEquals(download_utils.clean_filename(filename),
                          test_against)

    def test_clean_filename(self):
        self.check_clean_filename('normalname', 'normalname')
        self.check_clean_filename('a:b?c>d<e|f*/g\\h"\'', 'abcdefgh')
        self.check_clean_filename('', '_')
        long_filename = 'booya' * 100
        long_extension = '.' + 'foo' * 20
        self.check_clean_filename(long_filename, long_filename[:100])
        # total file length isn't over the limit, so the extension
        # stays the same
        self.check_clean_filename('abc' + long_extension,
                                  'abc' + long_extension)
        self.check_clean_filename(long_filename + long_extension,
                                  long_filename[:50] + long_extension[:50])

    def test_next_free_filename_generators(self):
        # try path without extension
        path = "/foo/.bar/test"
        generator = util.next_free_filename_candidates(path)
        # first candidate should just be the file itself
        self.assertEquals(generator.next(), "/foo/.bar/test")
        # next candidate should just be the file with .X added to it
        self.assertEquals(generator.next(), "/foo/.bar/test.1")
        self.assertEquals(generator.next(), "/foo/.bar/test.2")

        # try path with extension
        path = "/foo/.bar/test.jpg"
        generator = util.next_free_filename_candidates(path)
        # first candidate should just be the file itself
        self.assertEquals(generator.next(), "/foo/.bar/test.jpg")
        # next candidate should just be the file with .X added before the
        # extension
        self.assertEquals(generator.next(), "/foo/.bar/test.1.jpg")
        self.assertEquals(generator.next(), "/foo/.bar/test.2.jpg")

        # test that if we call it too many times, we get an exception
        generator = util.next_free_filename_candidates(path)
        for x in xrange(100000):
            try:
                generator.next()
            except ValueError:
                # this is good, it means that there's a failsafe if we try too
                # many candidates
                if x < 100:
                    raise # we shouldn't get an exception too soon
                break
        else:
            raise AssertionError("next_free_filename_candidates() "
                    "continues forever")

    def test_next_free_directory_generators(self):
        path = "/foo/.bar/test"
        generator = util.next_free_directory_candidates(path)
        # first candidate should just be the file itself
        self.assertEquals(generator.next(), "/foo/.bar/test")
        # next candidate should just be the file with .X added to it
        self.assertEquals(generator.next(), "/foo/.bar/test.1")
        self.assertEquals(generator.next(), "/foo/.bar/test.2")

        # test that if we call it too many times, we get an exception
        generator = util.next_free_directory_candidates(path)
        for x in xrange(100000):
            try:
                generator.next()
            except ValueError:
                # this is good, it means that there's a failsafe if we try too
                # many candidates
                if x < 100:
                    raise # we shouldn't get an exception too soon
                break
        else:
            raise AssertionError("next_free_filename_candidates() "
                    "continues forever")


    def test_next_free_filename(self):
        # make a bunch of files that we should skip over
        for name in ('foo', 'foo.1', 'foo.2', 'bar.jpg', 'bar.1.jpg'):
            path = os.path.join(self.tempdir, name)
            open(path, 'wt').write("FAKE FILE")

        path1 = os.path.join(self.tempdir, 'foo')
        # test we find the a nonexistent file
        returned_path, fp = util.next_free_filename(path1)
        self.assertEquals(returned_path, os.path.join(self.tempdir, 'foo.3'))
        # test that we create the file
        self.assert_(os.path.exists(returned_path))

        # try with an extension
        path2 = os.path.join(self.tempdir, 'bar.jpg')
        returned_path, fp = util.next_free_filename(path2)
        self.assertEquals(returned_path, os.path.join(self.tempdir,
            'bar.2.jpg'))
        self.assert_(os.path.exists(returned_path))

    def test_next_free_directory(self):
        # make a bunch of directories that we should skip over
        for name in ('foo', 'foo.1', 'foo.2'):
            path = os.path.join(self.tempdir, name)
            os.mkdir(path)

        path = os.path.join(self.tempdir, 'foo')
        # test we find the a nonexistent file
        returned_path = util.next_free_directory(path)
        self.assertEquals(returned_path, os.path.join(self.tempdir, 'foo.3'))
        # test that we don't create the directory
        self.assert_(not os.path.exists(returned_path))

class Test_simple_config_file(unittest.TestCase):
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.tempdir = tempfile.mkdtemp()
        if not os.path.exists(self.tempdir):
            os.makedirs(self.tempdir)

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_read_simple_config_file(self):
        fn = os.path.join(self.tempdir, "temp.config")

        f = open(fn, "w")
        f.write("""
a = b
c = dSSS

E = F
""".strip().replace("S", " "))
        f.close()

        cfg = buildutils.read_simple_config_file(fn)
        self.assertEquals(cfg["a"], "b")
        self.assertEquals(cfg["c"], "d   ")
        self.assertEquals(cfg["E"], "F")
        self.assertEquals(cfg.get("G"), None)

    def test_write_simple_config_file(self):
        fn = os.path.join(self.tempdir, "temp.config")

        cfg = {"a": "b",
               "c": "d",
               "E": "F   "}
        buildutils.write_simple_config_file(fn, cfg)

        cfg2 = buildutils.read_simple_config_file(fn)
        self.assertEquals(cfg2["a"], cfg["a"])
        self.assertEquals(cfg2["c"], cfg["c"])
        self.assertEquals(cfg2["E"], cfg["E"])

class MatrixTest(unittest.TestCase):
    def test_matrix_init(self):
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

    def test_get_set(self):
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

    def test_columns(self):
        m = util.Matrix(3, 2)
        m[0, 0] = 1
        m[0, 1] = 2
        m[1, 0] = 3
        m[1, 1] = 4
        m[2, 0] = 5
        m[2, 1] = 6

        self.assertEquals(list(m.column(0)), [1, 2])
        self.assertEquals(list(m.column(1)), [3, 4])
        self.assertEquals(list(m.column(2)), [5, 6])

    def test_rows(self):
        m = util.Matrix(3, 2)
        m[0, 0] = 1
        m[0, 1] = 2
        m[1, 0] = 3
        m[1, 1] = 4
        m[2, 0] = 5
        m[2, 1] = 6

        self.assertEquals(list(m.row(0)), [1, 3, 5])
        self.assertEquals(list(m.row(1)), [2, 4, 6])

    def test_remove(self):
        m = util.Matrix(1, 2)
        m[0,0] = 1
        m[0,1] = 2

        m.remove(2)

        self.assertEquals(m[0,0], 1)
        self.assertEquals(m[0,1], None)

class TestGatherSubtitlesFiles(unittest.TestCase):
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def create_files(self, movie_file, sub_files=None):
        if sub_files is None:
            sub_files = []

        movie_file = os.path.join(self.tempdir, movie_file)
        sub_files = [os.path.join(self.tempdir, mem) for mem in sub_files]
        sub_files.sort()

        all_files = [movie_file] + list(sub_files)
        for mem in all_files:
            dirname = os.path.dirname(mem)
            if not os.path.exists(dirname):
                os.makedirs(dirname)

            filep = open(mem, "w")
            filep.write("lalala")
            filep.close()

        return movie_file, sub_files

    def test_no_directory(self):
        # tests the case where the foofeed directory doesn't exist
        movie_file = os.path.join(self.tempdir, "foofeed", "foo.mov")
        self.assertEquals(
            [], util.gather_subtitle_files(FilenameType(movie_file)))

    def test_no_subtitle_files(self):
        movie_file, sub_files = self.create_files("foo.mov")
        self.assertEquals(
            sub_files, util.gather_subtitle_files(FilenameType(movie_file)))

    def test_single_file(self):
        movie_file, sub_files = self.create_files(
            "foo.mov", ["foo.en.srt"])
        self.assertEquals(
            sub_files, util.gather_subtitle_files(FilenameType(movie_file)))

    def test_multiple_files(self):
        movie_file, sub_files = self.create_files(
            "foo.mov", ["foo.en.srt", "foo.fr.srt", "foo.es.srt"])
        self.assertEquals(
            sub_files, util.gather_subtitle_files(FilenameType(movie_file)))

    def test_lots_of_files(self):
        movie_file, sub_files = self.create_files(
            "foo.mov", ["foo.en.srt", "blah.ogv", "foo.ogv"])

        # weed out the non-srt files so we can test correctly
        sub_files = [mem for mem in sub_files if mem.endswith(".srt")]
        self.assertEquals(
            sub_files, util.gather_subtitle_files(FilenameType(movie_file)))

    def test_subtitles_dir(self):
        movie_file, sub_files = self.create_files(
            "foo.mov", [os.path.join("subtitles", "foo.en.srt"),
                        os.path.join("subtitles", "foo.fr.srt")])
        self.assertEquals(
            sub_files, util.gather_subtitle_files(FilenameType(movie_file)))

    def test_filename_possibilities(self):
        movie_file, sub_files = self.create_files(
            "foo.mov", ["foo.en.srt", "foo.en.sub", "foo.srt", "foo.sub"])

        self.assertEquals(
            sub_files, util.gather_subtitle_files(FilenameType(movie_file)))

class TestCopySubtitleFile(unittest.TestCase):
    def setUp(self):
        unittest.TestCase.setUp(self)
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def create_files(self, files):
        for mem in files:
            dirname = os.path.dirname(mem)
            if not os.path.exists(dirname):
                os.makedirs(dirname)

            filep = open(mem, "w")
            filep.write("lalala")
            filep.close()

    def test_simple(self):
        sub_path = os.path.join(self.tempdir, "otherdir/subtitle.srt")
        video_path = os.path.join(self.tempdir, "foo.mov")
        self.create_files([sub_path, video_path])

        ret = util.copy_subtitle_file(sub_path, video_path)
        expected = os.path.join(self.tempdir, "foo.srt")
        self.assert_(os.path.exists(expected))
        self.assertEqual(expected, ret)

    def test_simple_with_language(self):
        sub_path = os.path.join(self.tempdir, "otherdir/subtitle.en.srt")
        video_path = os.path.join(self.tempdir, "foo.mov")
        self.create_files([sub_path, video_path])

        ret = util.copy_subtitle_file(sub_path, video_path)
        expected = os.path.join(self.tempdir, "foo.en.srt")
        self.assert_(os.path.exists(expected))
        self.assertEqual(expected, ret)

    def test_nonlanguage(self):
        # "ex" is not a valid language code, so this should ignore
        # that part
        sub_path = os.path.join(self.tempdir, "otherdir/subtitle.ex.srt")
        video_path = os.path.join(self.tempdir, "foo.mov")
        self.create_files([sub_path, video_path])

        ret = util.copy_subtitle_file(sub_path, video_path)
        expected = os.path.join(self.tempdir, "foo.srt")
        self.assert_(os.path.exists(expected))
        self.assertEqual(expected, ret)

class TestNameSortKey(unittest.TestCase):
    def test_simple(self):
        for testcase in ((None, 'ZZZZZZZZZZZZZ'),
                         (u'', (u'',)),
                         (u'a', (u'a',)),
                         (u'a1a', (u'a', 1.0, u'a')),
                         (u'Episode_100', (u'episode_', 100.0, u'')),
                         (u'episode_1', (u'episode_', 1.0, u''))
                         ):
            self.assertEquals(util.name_sort_key(testcase[0]),
                              testcase[1])

    def test_hashable(self):
        for testcase in (None,
                         u'',
                         u'a',
                         u'a1a',
                         u'Episode_100',
                         u'episode_1',
                         ):
            hash(util.name_sort_key(testcase))

    def test_sorting(self):
        for inlist, outlist in (
            ([], []),
            (["b", "a", "c"], ["a", "b", "c"]),
            (["a_12", "a_1", "a_100"], ["a_1", "a_12", "a_100"]),
            (["A_12", "a_1", "A_100"], ["a_1", "A_12", "A_100"])
            ):
            inlist.sort(key=util.name_sort_key)
            self.assertEquals(inlist, outlist)


class TestGatherMediaFiles(unittest.TestCase):
    def setUp(self):
        unittest.TestCase.setUp(self)

        self.tempdir = tempfile.mkdtemp()
        if not os.path.exists(self.tempdir):
            os.makedirs(self.tempdir)

        self.expectedFiles = []

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def add_file(self, filepath, expected):
        """Create a file in the temporary directory"""
        fullfilepath = os.path.join(self.tempdir, filepath)
        dirname = os.path.dirname(fullfilepath)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        filep = open(fullfilepath, "w")
        filep.write("lalala")
        filep.close()

        if expected:
            self.expectedFiles.append(fullfilepath)

    def verify_results(self):
        finder = util.gather_media_files(self.tempdir)
        found = []

        try:
            while(True):
                num_parsed, found = finder.next()
        except StopIteration:
            self.assertEquals(set(found), set(self.expectedFiles))

    def test_empty_dir(self):
        self.verify_results()

    def test_dir_without_media(self):
        self.add_file('index.html', False)
        self.verify_results()
        self.add_file('README.txt', False)
        self.verify_results()

    def test_dir_with_media(self):
        self.add_file('test.ogv', True)
        self.verify_results()
        self.add_file('test.avi', True)
        self.verify_results()

    def test_dir_mixed_files(self):
        self.add_file('index.html', False)
        self.add_file('test.ogv', True)
        self.verify_results()

    def test_subdirs(self):
        self.add_file(os.path.join('aaa', 'index.html'), False)
        self.verify_results()
        self.add_file(os.path.join('bbb', 'test.ogv'), True)
        self.verify_results()
        self.add_file('test.ogv', True)
        self.verify_results()

class TestBackupSupportDir(MiroTestCase):
    # Test backing up the support directory
    def setUp(self):
        MiroTestCase.setUp(self)
        self.support_dir = self.make_temp_dir_path()
        self.correct_files = []
        self.skip_dirs = []
        self.setup_support_dir()

    def setup_support_dir(self):
        """Add objects to our fake support directory that we want around for
        every test.
        """

        # add log files
        self.add_file_to_support_dir('miro.log')
        self.add_file_to_support_dir('miro-downloader.log')
        for i in range(1, 5):
            self.add_file_to_support_dir('miro.log.%s' % i)
            self.add_file_to_support_dir('miro-downloader.log.%s' % i)
        # add database files
        self.add_file_to_support_dir('sqlitedb')
        self.add_file_to_support_dir('sqlitedb-journal')
        self.add_file_to_support_dir('dbbackups/sqlitedb_backup_165')
        self.add_file_to_support_dir('dbbackups/sqlitedb_backup_170')
        self.add_file_to_support_dir('dbbackups/sqlitedb_backup_183')
        # add other files
        self.add_skip_dir('icon-cache')
        self.add_skip_dir('cover-art')
        self.add_file_to_support_dir('httpauth', should_skip=True)
        self.add_file_to_support_dir('preferences.bin', should_skip=True)
        for i in range(5):
            self.add_file_to_support_dir('cover-art/Album-%s' % i,
                                         should_skip=True)
            self.add_file_to_support_dir('icon-cache/icon-%s' % i,
                                         should_skip=True)
            self.add_file_to_support_dir('crashes/crash-report-%i' % i)

    def add_skip_dir(self, skip_dir):
        self.skip_dirs.append(os.path.join(self.support_dir, skip_dir))

    def add_file_to_support_dir(self, path, archive_name=None,
                                should_skip=False, contents='FAKE DATA'):
        if archive_name is None:
            archive_name = path
        full_path = os.path.join(self.support_dir, path)
        directory = os.path.dirname(full_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        open(full_path, "wt").write(contents)
        if not should_skip:
            self.correct_files.append(archive_name)

    def check_backup(self):
        backup = util.SupportDirBackup(self.support_dir, self.skip_dirs,
                                       max_size=1000000)
        archive = zipfile.ZipFile(backup.fileobj(), 'r')
        errors = archive.testzip()
        self.assertTrue(errors is None, "Errors in the zip file: %s" % errors)
        self.assertSameSet(archive.namelist(), self.correct_files)

    def test_backup(self):
        self.check_backup()

    def test_extendend_chars(self):
        filename = unicode_to_filename(u'\ufffdxtended Chars')
        self.add_file_to_support_dir(filename, 'xtended Chars')
        self.check_backup()

    def test_size_limit(self):
        # create 200 kb worth of data
        large_data = " " * 200000
        # add a bunch of those files
        for i in xrange(10):
            self.add_file_to_support_dir('big-file-%s' % i,
                                         contents=large_data)
        # check that we don't max an archive file too much bigger than our max
        # size
        max_size = 1000000 # 1MB
        backup = util.SupportDirBackup(self.support_dir, self.skip_dirs,
                                       max_size=max_size)
        filesize = os.stat(backup.backupfile).st_size
        self.assertTrue(filesize <= 1100000,
                        "Backup file too big.  filesize: %s max_size: %s" %
                        (filesize, max_size))


class MtimeInvalidatorTestCase(MiroTestCase):

    def test_valid(self):
        filename = os.path.join(self.tempdir, 'mtime_test')
        file(filename, 'w').write('foo')
        invalidator = util.mtime_invalidator(filename)
        self.assertFalse(invalidator(None))

    def test_invalid(self):
        filename = os.path.join(self.tempdir, 'mtime_test_future')
        file(filename, 'w').write('foo')
        invalidator = util.mtime_invalidator(filename)
        mtime = os.stat(filename).st_mtime
        # pretend the file was modified in the future
        os.utime(filename, (mtime + 10, mtime + 10))
        self.assertTrue(invalidator(None))

    def test_doesnotexist(self):
        filename = os.path.join(self.tempdir,
                                'mtime_test_doesnotexist')
        invalidator = util.mtime_invalidator(filename)
        self.assertTrue(invalidator(None))

    def test_disappears(self):
        filename = os.path.join(self.tempdir,
                                'mtime_test_disappears')
        file(filename, 'w').write('foo')
        invalidator = util.mtime_invalidator(filename)
        self.assertFalse(invalidator(None))
        os.unlink(filename)
        self.assertTrue(invalidator(None))

class CacheTestCase(MiroTestCase):

    def setUp(self):
        MiroTestCase.setUp(self)
        self.cache = MockCache(2)

    def test_set_get(self):
        self.cache.set(1, 1)
        self.assertEquals(self.cache.get(1), 1)

    def test_create_new_value_get(self):
        self.assertEquals(self.cache.get(1), (1, 0))
        self.assertEquals(self.cache.get(3), (3, 1))

    def test_remove(self):
        self.cache.set(1, 1)
        self.cache.remove(1)
        self.assertFalse(1 in self.cache.keys())

    def test_lru(self):
        self.cache.get(1)
        self.cache.get(2)
        self.cache.get(3)
        # 1 has expired out
        self.assertEquals(set(self.cache.keys()), set((2, 3)))

    def test_invalidator_set(self):
        def invalidator(key):
            return True
        self.cache.set(1, 1, invalidator=invalidator)
        # previous value is now invalid, get a new one
        self.assertEquals(self.cache.get(1), (1, 0))

    def test_invalidator_get(self):
        def invalidator(key):
            return True
        self.assertEquals(self.cache.get(1, invalidator=invalidator),
                          (1, 0))
        # previous value was invalid, get a new one
        self.assertEquals(self.cache.get(1, invalidator=invalidator),
                          (1, 1))


class AlarmTestCase(MiroTestCase):
    @staticmethod
    def _long_function():
        time.sleep(1.5)
        return True

    def _wrapped_function(self, set_signal=True):
        with util.alarm(1, set_signal=set_signal):
            return self._long_function()

    if hasattr(signal, 'SIGALRM'):
        def test_alarm_works(self):
            self.assertRaises(IOError, self._wrapped_function)

        def test_context_manager__True(self):
            with util.alarm(1) as result:
                self.assertTrue(result)

    def test_alarm_noop(self):
        self.assertTrue(self._wrapped_function(set_signal=False))

    def test_context_manager__False(self):
        with util.alarm(0, set_signal=False) as result:
            self.assertFalse(result)

class NamedTupleTest(MiroTestCase):
    def test_namedtuple(self):
        MyClass = util.namedtuple("MyClass", "a b c", "My Docstring")
        m = MyClass(1,2,3)
        self.assertEquals(m.__doc__, "My Docstring")
        self.assertEquals((m.a, m.b, m.c), (1,2,3))
