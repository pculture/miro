"""This module tests miro.filetags for correct and complete extraction (and
writing - to be implemented) of metadata tags.
"""

try:
    import simplejson as json
except ImportError:
    import json

from miro.test.framework import MiroTestCase, dynamic_test

from os import path

from miro.plat import resources
from miro.filetags import process_file

@dynamic_test(expected_cases=8)
class FileTagsTest(MiroTestCase):
    # mp3-2.mp3:
        # FIXME: losing data - TPE2="Chicago Public Media"

    # drm.m4v:
        # FIXME: losing data - CPRT='\xa9 2002 Discovery Communications Inc.'
        # FIXME: losing data - DESC='When it comes to sorting out some'...
        # FIXME: losing data - LDES='When it comes to sorting out some'...
        # FIXME: we should probably not include an album_artist field when
        # its origin is the same field as artist
        # FIXME: losing data - TVSH='The Most Extreme'
        # FIXME: losing data - TVNN='Animal Planet'

    @classmethod
    def generate_tests(cls):
        results_path = resources.path(path.join('testdata', 'filetags.json'))
        return json.load(open(results_path)).iteritems()

    def dynamic_test_case(self, filename, expected):
        # make all keys unicode
        #expected = dict((unicode(key), value)
                        #for key, value in expected.iteritems())
        filename = resources.path(path.join('testdata', 'metadata', filename))
        results = process_file(filename, self.tempdir)
        # cover art nedes to be handled specially
        if expected.pop('cover_art'):
            self.assertNotEqual(results.pop('cover_art_path'), None)
        else:
            self.assert_('cover_art_path' not in results)
        # for the rest, we just compare the dicts
        self.assertEquals(results, expected)
