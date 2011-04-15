"""This module tests miro.moviedata for use of the data provided by
miro.filetags and the moviedataprogram.
"""

from miro.test.framework import EventLoopTest, skipping

from os import path

from miro import moviedata
from miro import app
from miro.item import FileItem
from miro.feed import Feed
from miro.plat import resources
from miro.plat import renderers

class _FakeProgressUpdater(object):
    def path_processed(self, path):
        pass

moviedata.MOVIE_DATA_UTIL_TIMEOUT = 10 # shouldn't break any other tests
renderers.init_renderer() # won't break other tests since nothing else touches
                          # plat.renderers
app.metadata_progress_updater = _FakeProgressUpdater() # won't break other tests
                                                       # since nothing tests mpu

class _FakeFeed(object):
    origURL = u''
    is_autodownloadable = lambda x: False
    thumbnail_valid = lambda x: False
    get_license = lambda x: u''
    userTitle = u'non-empty string'

class _TestFileItem(FileItem):
    """Monkey-patches some non-functionality into FileItem - we need to override
    it to test things, but schema doesn't like a real subclass.
    """
    def __new__(cls, filename):
        # modify instance between __new__ and __init__:
        item = FileItem.__new__(FileItem, filename, feed_id=1)
        item._feed = Feed(u'')
        # because we're not returning an instance of this class, __init__ won't
        # be called automatically
        FileItem.__init__(item, filename, feed_id=1)
        return item

class MovieDataTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.mdu = moviedata.MovieDataUpdater()
        def break_mdu_loop(x): self.mdu.in_shutdown = True
        self.mdu.connect('end-loop', break_mdu_loop)

    def mdu_read_file(self, test):
        filename = resources.path(path.join('testdata', 'metadata', test))
        item = _TestFileItem(filename)
        self.mdu.in_shutdown = False
        self.mdu.request_update(item)

        # MDI disables itself when it detects that it's in a unittest; this
        # workaround pops off the MDI, re-enables it, and puts it back in the
        # queue. There is certainly a better way.
        mdi = self.mdu.queue.get()
        del mdi._program_info
        self.mdu.queue.put(mdi)
        
        self.assertFalse(self.mdu.queue.empty()) # this will fail if:
                                                 # - the file cannot be found
                                                 # - other things: see request_update
        self.mdu.thread_loop()
        self.assertTrue(self.mdu.queue.empty())
        self.process_idles()
        return item

    def assert_metadata(self, item, data):
        for key, value in data.iteritems():
            self.assertEqual(getattr(item, key), value)

    # NOTE: tests fail if the moviedataprogram times out; it seems gst_extrator
    # has a propensity toward infinite loops or godot conditions when it doesn't
    # like its input file

    def test_video_with_ogg_extension(self):
        item = self.mdu_read_file('theora_with_ogg_extension.ogg')
        self.assertEqual(item.file_type, 'video')
        self.assertTrue(item.screenshot,
            "theora_with_ogg_extension test case expected to have a screenshot")

    @skipping("hangs indefinitely (#16781)")
    def test_mp3(self):
        mp3_0 = dict(
            album=u'Increase The Dosage',
            artist=u'Revolution Void',
            genre=u'Blues',
            title_tag=u'Invisible Walls',
            track=1,
        )
        item = self.mdu_read_file('mp3-0.mp3')
        self.assertEqual(item.duration, 1055)
        self.assertEqual(item.file_type, 'audio')
        self.assertEqual(item.cover_art, None)
        self.assertFalse(item.screenshot)
        self.assert_metadata(item, mp3_0)

    # failed on screenshot before a60e5ce, but got duration
    @skipping("can't find duration after a60e5ce")
    def test_mp4(self):
        mp4_0 = dict(
            title_tag=u'Africa: Cash for Climate Change?',
        )
        item = self.mdu_read_file('mp4-0.mp4')
        self.assertEqual(item.duration, 312308)
        self.assertEqual(item.file_type, 'video')
        self.assertEqual(item.cover_art, None)
        self.assertTrue(item.screenshot,
            "mp4-0 test case expected to have a screenshot")
        self.assert_metadata(item, mp4_0)

    # failed on file_type before a60e5ce, but got duration
    @skipping("can't find duration after a60e5ce")
    def test_m4v_drm(self):
        m4v = dict(
            album=u'The Most Extreme, Season 1',
            album_artist=u'The Most Extreme',
            artist=u'The Most Extreme',
            has_drm=True,
            genre=u'Nonfiction',
            title_tag=u'Thinkers',
            track=10,
            year=2000,
        )
        item = self.mdu_read_file('drm.m4v')
        self.assertEqual(item.duration, 2668832)
        self.assertEqual(item.file_type, 'other')
        self.assertEqual(item.cover_art, None)
        self.assertTrue(item.screenshot,
            "drm.m4v test case expected to have a screenshot")
        self.assert_metadata(item, m4v)
