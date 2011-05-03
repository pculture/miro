"""This module tests miro.moviedata for use of the data provided by
miro.filetags and the moviedataprogram.
"""

from miro.test.framework import EventLoopTest, MiroTestCase

import json
from os import path

from miro import moviedata
from miro import metadata
from miro import app
from miro import models
from miro import filetypes
from miro.feed import Feed
from miro.plat import resources
from miro.plat import renderers
from miro.fileobject import FilenameType

import time

moviedata.MOVIE_DATA_UTIL_TIMEOUT = 10 # shouldn't break any other tests
renderers.init_renderer() # won't break other tests since nothing else touches
                          # plat.renderers

class Namespace(dict):
    __getattr__ = dict.__getitem__
    def __setattr__(self, a, v):
        if a in self.__dict__:
            dict.__setattr__(self, a, v)
        else:
            dict.__setitem__(self, a, v)
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
        self.mdp_state = None
        self.file_type = None

    def get_filename(self): return self._filename
    def id_exists(self): return True
    def signal_change(self): pass

class MovieDataTest(EventLoopTest):
    def setUp(self):
        app.testing_mdp = True # hack to override moviedata's in_unit_tests hack
        EventLoopTest.setUp(self)
        self.mdu = moviedata.MovieDataUpdater()

    def tearDown(self):
        del app.testing_mdp
        EventLoopTest.tearDown(self)

    def check_media_file(self, item):
        # this is much like Item.check_media_file, be we don't want to catch any
        # exceptions here
        item.file_type = filetypes.item_file_type_for_filename(item._filename)
        item.read_metadata()
        item.signal_change()

        self.assertTrue(self.mdu.queue.empty())
        self.mdu.request_update(item)
        if not self.mdu.queue.empty():
            self.mdu.process_item()
        self.process_idles()
        self.assertTrue(self.mdu.queue.empty())
        if item.file_type is None:
            item.file_type = u'other'
        item.signal_change()

    def process_file(self, test):
        item = FakeItem(test)
        self.check_media_file(item)
        return item

    def test_media_with_mdp(self):
        results_path = resources.path(path.join('testdata', 'moviedata.json'))
        expected_results = json.load(open(results_path))
        for filename, expected in expected_results.iteritems():
            actual = self.process_file(FilenameType(filename))
            self.assertNotEqual(actual.mdp_state, None, filename)
            del actual['mdp_state']
            expected['metadata_version'] = moviedata.METADATA_VERSION
            expected['test'], actual.test = filename, filename
            if hasattr(actual, 'cover_art'):
                actual.cover_art = bool(actual.cover_art)
            if hasattr(actual, 'screenshot'):
                actual.screenshot = bool(actual.screenshot)
            expected = dict((str(k), v) for k, v in expected.iteritems())
            actual = dict(actual)
            self.assertEqual(actual, expected)
            assert actual == expected, ("metadata wrong for %s "
                    "actual: %r expected: %r" % (filename, actual, expected))

class MovieDataRequestTest(MiroTestCase):
    """Test when we choose to invoke our moviedata programs."""
    def setUp(self):
        app.testing_mdp = True # hack to override moviedata's in_unit_tests hack
        MiroTestCase.setUp(self)
        self.feed = models.Feed(u'dtv:manualFeed')
        mp3_path = resources.path("testdata/metadata/mp3-0.mp3")
        webm_path = resources.path("testdata/metadata/webm-0.webm")
        jpg_path = resources.path("testdata/dean.jpg")

        self.audio_item = models.FileItem(mp3_path, self.feed.id)
        self.video_item = models.FileItem(webm_path, self.feed.id)
        self.other_item = models.FileItem(jpg_path, self.feed.id)

    def tearDown(self):
        del app.testing_mdp
        MiroTestCase.tearDown(self)

    def signal_changes(self):
        self.audio_item.signal_change()
        self.video_item.signal_change()
        self.other_item.signal_change()

    def check_will_run_moviedata(self, item, should_run):
        # check MovieDataUpdater._should_process_item()
        mdu = moviedata.movie_data_updater
        self.assertEquals(mdu._should_process_item(item), should_run)
        # check incomplete_mdp_view; this should be True for all items, since
        # each needs to be marked as seen
        incomplete_view = set(
                models.Item.incomplete_mdp_view())
        self.assertEquals(item in incomplete_view, True)

    def check_path_processed(self, item, should_run):
        # Check if path_processed was called.  Note: this can only test based
        # on the initial state of the item.  If we fiddle with it's
        # attributes, then we shouldn't call this.

        paths_processed = self.metadata_progress_updater.paths_processed
        if should_run:
            # If we will call movie data, then path_processed shouldn't be
            # called until that happens, which is never in the unit tests.
            if item.filename in paths_processed:
                raise AssertionError("path_processed() called for %s when "
                        "it shouldn't have been (path_processed: %s)" %
                        (item.filename, paths_processed))
        else:
            if item.filename not in paths_processed:
                raise AssertionError("path_processed() not called for %s when "
                        "it shouldn't have been (paths_processed: %s)" % 
                        (item.filename, paths_processed))

    def test_initial_mutagan_worked_audio(self):
        # shouldn't run moviedata for audio that mutagen can process
        self.check_will_run_moviedata(self.audio_item, False)
        self.check_path_processed(self.audio_item, False)

    def test_initial_mutagan_worked_video(self):
        # should run moviedata for video that mutagen can process
        self.check_will_run_moviedata(self.video_item, True)
        self.check_path_processed(self.video_item, True)

    def test_initial_mutagan_failed_other(self):
        # shouldn't run moviedata for other filenames
        self.check_will_run_moviedata(self.other_item, False)
        self.check_path_processed(self.other_item, False)

    def test_run_moviedata_no_duration(self):
        # we should always run moviedata if mutagen can't determine the
        # duration
        self.audio_item.duration = self.video_item.duration = None
        self.signal_changes()
        self.check_will_run_moviedata(self.video_item, True)
        self.check_will_run_moviedata(self.audio_item, True)

    def test_run_moviedata_no_screenshot(self):
        # we should run moviedata if it's a video item and we haven't captured
        # a screenshot
        self.audio_item.screenshot = self.video_item.screenshot = None
        self.signal_changes()
        self.check_will_run_moviedata(self.video_item, True)
        self.check_will_run_moviedata(self.audio_item, False)

# FIXME
# theora_with_ogg_extension test case expected to have a screenshot")
# mp4-0 test case expected to have a screenshot")
# drm.m4v test case expected to have a screenshot")
# webm-0.assertEqual(item.duration, *something*)
