import sys

from miro.plat.utils import unicode_to_filename
from miro.test.framework import MiroTestCase
from miro import fileobject

class FileObjectTest(MiroTestCase):
    def test_type(self):
        filename = fileobject.FilenameType("/foo/bar")
        if sys.platform == 'win32':
            self.assert_(isinstance(filename, unicode))
        else:
            self.assert_(isinstance(filename, str))

    def test_file_urlize(self):
        filename = fileobject.FilenameType("/foo/bar/*^&")
        self.assertEquals(filename.urlize(), "file:///foo/bar/%2A%5E%26")
        self.assertEquals(type(filename.urlize()), str)

    def test_file_urlize_with_unicode(self):
        # contrived way of getting unicode characters in a filename
        basename = unicode_to_filename(u'b\u0103r')
        directory = fileobject.FilenameType('/foo/')
        filename = fileobject.FilenameType(directory + basename)
        # "/foo/bar" with a breve over the "a"
        self.assertEquals(filename.urlize(), "file:///foo/b%C4%83r")
        # urlize() should convert it to utf-8 then quote it
        self.assertEquals(type(filename.urlize()), str)

    def test_custom_urlize(self):
        def my_handler(self, add_at_end):
            return ''.join(reversed(self)) + add_at_end
        filename = fileobject.FilenameType('/foo/bar/')
        filename.set_urlize_handler(my_handler, ('testing',))
        self.assertEquals(filename.urlize(), '/rab/oof/testing')
