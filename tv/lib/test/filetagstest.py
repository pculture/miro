"""This module tests miro.filetags for correct and complete extraction (and
writing - to be implemented) of metadata tags.
"""

import json

from miro.test.framework import MiroTestCase

from os import path

from miro.plat import resources
from miro.filetags import read_metadata

class FileTagsTest(MiroTestCase):
    def assert_file_data(self, test,
            mediatype='*', duration='*', data='*', cover_art='*'):
        if data != '*' and data is not None:
            data = dict((unicode(key), value) for key, value in data.iteritems())
        filename = resources.path(path.join('testdata', 'metadata', test))
        expected = (mediatype, duration, data, cover_art)
        results = read_metadata(filename, True)
        if results is None:
            # files for which mutagen returns nothing should have None for all
            # fields, including None instead of a tags dict.
            results = None, None, None, None
        for observed, expected_value in zip(results, expected):
            if expected_value != '*':
                self.assertEquals(observed, expected_value)

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

# This is the same _test_closure technique used for FeedParserTest:

def _test_closure(self, filename, expected):
    file_type = expected['file_type']
    duration = expected['duration']
    tags = expected['tags']
    cover_art = expected['cover_art']
    self.assert_file_data(filename, file_type, duration, tags, cover_art)

# this creates a separate test method in FileTagsTest for each test
# in the filetags.json file.  makes it easier to debug tests that
# go awry, makes it easier to see test progress from the command line
# (lots of little tests rather than one big test), and increases the
# test count appropriately.
results_path = resources.path(path.join('testdata', 'filetags.json'))
expected_results = json.load(open(results_path))
for filename, expected in expected_results.iteritems():
    setattr(FileTagsTest, 'test_%s' % filename.replace(".", ""),
            lambda self: _test_closure(self, filename, expected))
