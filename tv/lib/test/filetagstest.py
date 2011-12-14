"""This module tests miro.filetags for correct and complete extraction (and
writing - to be implemented) of metadata tags.
"""

try:
    import simplejson as json
except ImportError:
    import json

from miro.test.framework import MiroTestCase, dynamic_test

import shutil
from os import path, stat

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
        cover_art = expected.pop('cover_art')
        if cover_art:
            # cover art should be stored using the album name as its file
            correct_path = path.join(self.tempdir, results['album'])
            self.assertEquals(results.pop('cover_art_path'), correct_path)
        else:
            self.assert_('cover_art_path' not in results)
        # for the rest, we just compare the dicts
        self.assertEquals(results, expected)

    def test_shared_cover_art(self):
        # test what happens when 2 files with coverart share the same album.
        # In this case the first one we process should create the cover art
        # file and the next one should just skip cover art processing.
        src_path = resources.path(path.join('testdata', 'metadata',
                                            'drm.m4v'))
        dest_paths = []
        for x in range(3):
            new_filename = 'drm-%s.m4v' % x
            dest_path = path.join(self.tempdir, new_filename)
            shutil.copyfile(src_path, dest_path)
            dest_paths.append(dest_path)

        # process the first file
        result_1 = process_file(dest_paths[0], self.tempdir)
        self.assertEquals(result_1['cover_art_path'],
                          path.join(self.tempdir, result_1['album']))
        self.assert_(path.exists(result_1['cover_art_path']))
        org_mtime = stat(result_1['cover_art_path']).st_mtime

        # process the rest, they should fill in the cover_art_path value, but
        # not rewrite the file
        for dup_path in dest_paths[1:]:
            results = process_file(dup_path, self.tempdir)
            self.assertEquals(results['cover_art_path'],
                              result_1['cover_art_path'])
            self.assert_(path.exists(results['cover_art_path']))
            self.assertEquals(stat(results['cover_art_path']).st_mtime,
                              org_mtime)
