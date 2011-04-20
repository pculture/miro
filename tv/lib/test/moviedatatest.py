"""This module tests miro.moviedata for use of the data provided by
miro.filetags and the moviedataprogram.
"""

from miro.test.framework import EventLoopTest, skipping

import json
from os import path

from miro import moviedata
from miro import metadata
from miro import app
from miro.item import FileItem
from miro.feed import Feed
from miro.plat import resources
from miro.plat import renderers
from miro.fileobject import FilenameType

moviedata.MOVIE_DATA_UTIL_TIMEOUT = 10 # shouldn't break any other tests
renderers.init_renderer() # won't break other tests since nothing else touches
                          # plat.renderers

class Namespace(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
    __hasattr__ = dict.__contains__

class FakeItem(Namespace, metadata.Source):
    """Acts like an item, but uses the Namespace class to become a dict of any
    properties set on it.
    """
    def __init__(self, filename):
        Namespace.__init__(self)
        metadata.Source.__init__(self)
        filename = resources.path(path.join('testdata', 'metadata', filename))
        self.__dict__['_filename'] = filename
        self.__dict__['id'] = 9999

    def get_filename(self): return self._filename
    def id_exists(self): return True
    def signal_change(self): pass

class MovieDataTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.mdu = moviedata.MovieDataUpdater()

    def _make_mdi(self, item):
        mdi = moviedata.MovieDataInfo(item)
        del mdi._program_info # foil anti-testing measures
        return mdi

    def mutagen_read_item(self, item):
        item.read_metadata(item.get_filename())

    def mdu_read_item(self, item):
        self.mdu.in_progress.add(item.id)
        mdi = self._make_mdi(item)
        self.mdu.process_with_movie_data_program(mdi)
        self.process_idles()

    def process_file(self, test):
        item = FakeItem(test)
        self.mutagen_read_item(item)
        self.mdu_read_item(item)
        return item

    def test_media_with_mdp(self):
        results_path = resources.path(path.join('testdata', 'moviedata.json'))
        expected_results = json.load(open(results_path))
        for filename, expected in expected_results.iteritems():
            actual = self.process_file(FilenameType(filename))
            expected['media_type_checked'] = True
            expected['metadata_version'] = moviedata.METADATA_VERSION
            expected['test'], actual.test = filename, filename
            if hasattr(actual, 'cover_art'):
                actual.cover_art = bool(actual.cover_art)
            expected = dict((str(k), v) for k, v in expected.iteritems())
            actual.screenshot = actual.screenshot and bool(actual.screenshot)
            self.assertEqual(dict(actual), expected)

# FIXME
# theora_with_ogg_extension test case expected to have a screenshot")
# mp4-0 test case expected to have a screenshot")
# drm.m4v test case expected to have a screenshot")
# webm-0.assertEqual(item.duration, *something*)
