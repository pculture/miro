import sys

from miro.test.framework import MiroTestCase
from miro import fileutil

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

