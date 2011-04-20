"""This module tests miro.filetags for correct and complete extraction (and
writing - to be implemented) of metadata tags.
"""

from miro.test.framework import MiroTestCase

from os import path

from miro.plat import resources
from miro.filetags import read_metadata


# NOTE: moviedatatest has expanded to make this redundant, but there's some data
# here that's not there yet. TODO: merge useful parts of this into moviedatatest
# and scrap this module.


# FIXME: cover art detection is currently tested, but content is not

class FileTagsTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)

    def assert_file_data(self, test,
            mediatype='*', duration='*', data='*', cover_art='*'):
        if data != '*':
            data = dict((unicode(key), value) for key, value in data.iteritems())
        filename = resources.path(path.join('testdata', 'metadata', test))
        expected = (mediatype, duration, data, cover_art)
        for observed, expected in zip(read_metadata(filename, True), expected):
            if expected != '*':
                self.assertEquals(observed, expected)

    def test_video_with_ogg_extension(self):
        self.assert_file_data('theora_with_ogg_extension.ogg', mediatype='video')

    def test_mp3(self):
        mp3_0 = dict(
            album=u'Increase The Dosage',
            artist=u'Revolution Void',
            genre=u'Blues',
            title=u'Invisible Walls',
            track=1,
        )
        self.assert_file_data('mp3-0.mp3', 'audio', 1055, mp3_0, None)
        mp3_1 = dict(
            album=u'The Heart EP',
            artist=u'Ckz',
            title=u'Race Lieu',
            track=2,
            year=2008,
        )
        self.assert_file_data('mp3-1.mp3', 'audio', 1055, mp3_1, None)
        mp3_2 = dict(
            # FIXME: losing data - TPE2="Chicago Public Media"
            artist=u'This American Life', # TPE1
            genre=u'Podcast',
            title=u'#426: Tough Room 2011',
            year=2011,
        )
        self.assert_file_data('mp3-2.mp3', 'audio', 1066, mp3_2, None)

    def test_mp4(self):
        mp4_0 = dict(
            title=u'Africa: Cash for Climate Change?',
        )
        self.assert_file_data('mp4-0.mp4', 'video', 312308, mp4_0, None)

    def test_m4v_drm(self):
        m4v = dict(
            # FIXME: losing data - CPRT='\xa9 2002 Discovery Communications Inc.'
            # FIXME: losing data - DESC='When it comes to sorting out some'...
            # FIXME: losing data - LDES='When it comes to sorting out some'...
            # FIXME: we should probably not include an album_artist field when
            # FIXME: we should probably not include an album_artist field when
            # its origin is the same field as artist
            # FIXME: losing data - TVSH='The Most Extreme'
            # FIXME: losing data - TVNN='Animal Planet'
            album=u'The Most Extreme, Season 1',
            album_artist=u'The Most Extreme',
            artist=u'The Most Extreme',
            drm=True,
            genre=u'Nonfiction',
            title=u'Thinkers',
            track=10,
            year=2000,
        )
        self.assert_file_data('drm.m4v', 'video', 2668832, m4v, True)
