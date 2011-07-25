import urllib
import sys

from miro.test.framework import MiroTestCase
from miro import feed
from miro import fileutil
from miro.plat import resources

class MakeFilenameTest(MiroTestCase):
    # test fileutil.make_filename()
    test_path = u'\uff4d\xef\u0213\u020f'
    # "miro" with acsents over characters

    def test_bytestring(self):
        # test that bytestrings get converted using the filesystem encoding
        path = self.test_path.encode(sys.getfilesystemencoding())
        self.assertEquals(fileutil.make_filename(path), self.test_path)

    def test_unicode(self):
        # test that unicode paths get returned without changes
        self.assertEquals(fileutil.make_filename(self.test_path),
                self.test_path)

    def test_bad_type(self):
        # test that objects that aren't unicode or strings raise a TypeError
        self.assertRaises(TypeError, fileutil.make_filename, None)

class CleanFilenameTest(MiroTestCase):
    # test fileutil.clean_filename()

    def test_valid_filename(self):
        # test that valid filenames don't change
        self.assertEquals(fileutil.clean_filename("valid_path.jpg"),
                "valid_path.jpg")

    def test_strip_bad_characters(self):
        # test that we strip out bad characters from the path
        bad_chars = ('/', '\000', '\\', ':', '*', '?', "'", '"', '<', '>',
                '|', "\n", "\r")

        path = 'h\\e\nl\rl*o' + ''.join(bad_chars) + '.world'
        correct_cleaned_path = path
        for char in bad_chars:
            correct_cleaned_path = correct_cleaned_path.replace(char, '_')
        self.assertEquals(fileutil.clean_filename(path),
                correct_cleaned_path)

    def test_max_length(self):
        # test that we don't allow paths with too many characters (currently
        # 50)

        path = 'a' * 400 + '.jpg'
        self.assertEquals(fileutil.clean_filename(path), 'a' * 96 + '.jpg')


class FilenameToDirectoryURLTest(MiroTestCase):
    # test path_to_directory_feed_url() and directory_feed_url_to_path()

    def _check_conversion(self, path):
        feed_url = feed.path_to_directory_feed_url(path)
        double_converted_path = feed.directory_feed_url_to_path(feed_url)
        self.assertEquals(path, double_converted_path)

    def test_conversion(self):
        # check ascii chars
        self._check_conversion(u'/home/miro/test')
        # check extended chars
        self._check_conversion(u'/home/miro/\xff\xfe\xfd')

    def test_invalid_input(self):
        # test converting a non-unicode path
        self.assertRaises(UnicodeError, feed.path_to_directory_feed_url,
                '/home/miro/\xff')
        # test converting URLs that aren't directory feeds
        self.assertRaises(ValueError, feed.directory_feed_url_to_path,
                'http://pculture.org/')

class URLForPathTest(MiroTestCase):
    # test resources.url()

    def _check_url_method(self, relative_path):
        full_path = resources.path(relative_path)
        # file URLs should be encoded as utf-8, then quoted
        full_path_encoded = urllib.quote(full_path.encode('utf-8'))
        correct_url = u'file://' + full_path_encoded
        self.assertEquals(correct_url, resources.url(relative_path))

    def test_url_method(self):
        # check ascii chars
        self._check_url_method(u'test/foo.jpg')
        # check extended chars
        self._check_url_method(u'test/\xff\xfe\xfd.jpeg')
