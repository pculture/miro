import collections
import itertools
import os
import urllib
import urlparse
import random
import string
import json

from miro.test import mock
from miro.test.framework import MiroTestCase, EventLoopTest
from miro import app
from miro import databaseupgrade
from miro import echonest
from miro import httpclient
from miro import prefs
from miro import schema
from miro import filetypes
from miro import metadata
from miro import workerprocess
from miro.plat import resources
from miro.plat.utils import (PlatformFilenameType,
                             get_enmfp_executable_path)

class MockMetadataProcessor(object):
    """Replaces the mutagen and movie data code with test values."""
    def __init__(self):
        self.reset()

    def reset(self):
        # each dict in task_data maps source paths to callback/errback/task
        # data the call to that path.  For example, for each MutagenTask that
        # we intercept, we store that task, the callback, and the errback.
        self.task_data = {
            'mutagen': {},
            'movie-data': {},
            'echonest-codegen': {},
            'echonest': {},
        }
        self.canceled_files = set()
        # store the codes we see in query_echonest calls
        self.query_echonest_codes = {}
        self.query_echonest_metadata = {}

    def mutagen_paths(self):
        """Get the paths for mutagen calls currently in the system."""
        return self.task_data['mutagen'].keys()

    def movie_data_paths(self):
        """Get the paths for movie data calls currently in the system."""
        return self.task_data['movie-data'].keys()

    def echonest_codegen_paths(self):
        """Get the paths for ecohnest codegen calls currently in the system."""
        return self.task_data['echonest-codegen'].keys()

    def echonest_paths(self):
        """Get the paths for ecohnest codegen calls currently in the system."""
        return self.task_data['echonest'].keys()

    def add_task_data(self, source_path, name, data):
        task_data_dict = self.task_data[name]
        if source_path in task_data_dict:
            raise ValueError("Already processing %s (path: %s)" %
                             (name, source_path))
        task_data_dict[source_path] = data

    def pop_task_data(self, source_path, name):
        task_data_dict = self.task_data[name]
        try:
            return task_data_dict.pop(source_path)
        except KeyError:
            raise ValueError("No %s run scheduled for %s" %
                             (name, source_path))

    def send(self, task, callback, errback):
        task_data = (task, callback, errback)

        if isinstance(task, workerprocess.MutagenTask):
            self.add_task_data(task.source_path, 'mutagen', task_data)
        elif isinstance(task, workerprocess.MovieDataProgramTask):
            self.add_task_data(task.source_path, 'movie-data', task_data)
        elif isinstance(task, workerprocess.CancelFileOperations):
            self.canceled_files.update(task.paths)
        else:
            raise TypeError(task)

    def exec_codegen(self, codegen_path, path, callback, errback):
        task_data = (callback, errback)
        self.add_task_data(path, 'echonest-codegen', task_data)

    def query_echonest(self, path, album_art_dir, code, version, metadata,
                       callback, errback):
        if path in self.query_echonest_codes:
            raise ValueError("query_echonest already called for %s" % path)
        self.query_echonest_codes[path] = code
        self.query_echonest_metadata[path] = metadata
        self.add_task_data(path, 'echonest', (callback, errback))

    def run_mutagen_callback(self, source_path, metadata):
        task, callback, errback = self.pop_task_data(source_path, 'mutagen')
        callback_data = {'source_path': source_path}
        callback_data.update(metadata)
        callback(task, callback_data)

    def run_mutagen_errback(self, source_path, error):
        task, callback, errback = self.pop_task_data(source_path, 'mutagen')
        errback(task, error)

    def run_movie_data_callback(self, source_path, metadata):
        task, callback, errback = self.pop_task_data(source_path, 'movie-data')
        callback_data = {'source_path': source_path}
        callback_data.update(metadata)
        callback(task, callback_data)

    def run_movie_data_errback(self, source_path, error):
        task, callback, errback = self.pop_task_data(source_path, 'movie-data')
        errback(task, error)

    def run_echonest_codegen_callback(self, source_path, code):
        callback, errback = self.pop_task_data(source_path,
                                               'echonest-codegen')
        callback(source_path, code)

    def run_echonest_codegen_errback(self, source_path, error):
        callback, errback = self.pop_task_data(source_path,
                                               'echonest-codegen')
        errback(source_path, error)

    def run_echonest_callback(self, source_path, metadata):
        callback, errback = self.pop_task_data(source_path, 'echonest')
        callback(source_path, metadata)

    def run_echonest_errback(self, source_path, error):
        callback, errback = self.pop_task_data(source_path, 'echonest')
        errback(source_path, error)

class MetadataManagerTest(MiroTestCase):
    # Test the MetadataManager class
    def setUp(self):
        MiroTestCase.setUp(self)
        self.mutagen_data = collections.defaultdict(dict)
        self.movieprogram_data = collections.defaultdict(dict)
        self.echonest_data = collections.defaultdict(dict)
        self.user_info_data = collections.defaultdict(dict)
        # maps paths -> should we do an interent lookup
        self.net_lookup_enabled = {}
        self.processor = MockMetadataProcessor()
        self.patch_function('miro.workerprocess.send', self.processor.send)
        self.patch_function('miro.echonest.exec_codegen',
                            self.processor.exec_codegen)
        self.patch_function('miro.echonest.query_echonest',
                            self.processor.query_echonest)
        self.metadata_manager = metadata.MetadataManager(self.tempdir)
        # For these examples we want to run echonest by default
        app.config.set(prefs.NET_LOOKUP_BY_DEFAULT, True)

    def _calc_correct_metadata(self, path):
        """Calculate what the metadata should be for a path."""
        metadata = {
            'file_type': filetypes.item_file_type_for_filename(path),
        }
        metadata.update(self.mutagen_data[path])
        metadata.update(self.movieprogram_data[path])
        if self.net_lookup_enabled[path]:
            metadata.update(self.echonest_data[path])
            metadata['net_lookup_enabled'] = True
        else:
            metadata['net_lookup_enabled'] = False
        metadata.update(self.user_info_data[path])
        if 'album' in metadata:
            cover_art_path = self.cover_art_for_album(metadata['album'])
            if cover_art_path:
                metadata['cover_art_path'] = cover_art_path
        return metadata

    def check_set_net_lookup_enabled(self, filename, enabled):
        path = self.make_path(filename)
        self.net_lookup_enabled[path] = enabled
        self.metadata_manager.set_net_lookup_enabled([path], enabled)
        self.check_metadata(path)

    def cover_art_for_album(self, album_name):
        mutagen_cover_art_path = None
        echonest_cover_art_path = None
        for metadata in self.mutagen_data.values():
            if ('album' in metadata and 'cover_art_path' in metadata and
                metadata['album'] == album_name):
                if (mutagen_cover_art_path is not None and
                    metadata['cover_art_path'] != mutagen_cover_art_path):
                    raise AssertionError("Different mutagen cover_part_paths "
                                         "for " + album_name)
                mutagen_cover_art_path = metadata['cover_art_path']
        for metadata in self.echonest_data.values():
            if ('album' in metadata and 'cover_art_path' in metadata and
                metadata['album'] == album_name):
                if (echonest_cover_art_path is not None and
                    metadata['cover_art_path'] != echonest_cover_art_path):
                    raise AssertionError("Different mutagen cover_part_paths "
                                         "for " + album_name)
                echonest_cover_art_path = metadata['cover_art_path']
        if echonest_cover_art_path:
            return echonest_cover_art_path
        else:
            return mutagen_cover_art_path

    def check_metadata(self, filename):
        path = self.make_path(filename)
        correct_metadata = self._calc_correct_metadata(path)
        self.metadata_manager._process_metadata_finished()
        self.metadata_manager._process_metadata_errors()
        metadata = self.metadata_manager.get_metadata(path)
        # don't check has_drm, we have a special test for that
        for dct in (metadata, correct_metadata):
            for key in ('has_drm', 'drm'):
                if key in dct:
                    del dct[key]
        self.assertDictEquals(metadata, correct_metadata)

    def make_path(self, filename):
        """Create a pathname for that file in the "/videos" directory
        """
        if not filename.startswith('/'):
            return '/videos/' + filename
        else:
            # filename is already absolute
            return filename

    def check_add_file(self, filename):
        path = self.make_path(filename)
        pref_value = app.config.get(prefs.NET_LOOKUP_BY_DEFAULT)
        self.net_lookup_enabled[path] = pref_value
        # before we add the path, get_metadata() should raise a KeyError
        self.assertRaises(KeyError, self.metadata_manager.get_metadata, path)
        # after we add the path, we should have only have metadata that we can
        # guess from the file
        self.metadata_manager.add_file(path)
        self.check_metadata(path)
        # after we add the path, calling add file again should raise a
        # ValueError
        self.assertRaises(ValueError, self.metadata_manager.add_file, path)

    def cover_art_path(self, album_name, echonest=False):
        path_parts = [self.tempdir]
        if echonest:
            path_parts.append('echonest')
        path_parts.append(urllib.quote(album_name, safe=" ,"))
        return os.path.join(*path_parts)

    def check_run_mutagen(self, filename, file_type, duration, title,
                          album=None, drm=False, cover_art=True):
        # NOTE: real mutagen calls send more metadata, but this is enough to
        # test
        path = self.make_path(filename)
        mutagen_data = {}
        if file_type is not None:
            mutagen_data['file_type'] = unicode(file_type)
        if duration is not None:
            mutagen_data['duration'] = duration
        if title is not None:
            mutagen_data['title'] = unicode('title')
        if album is not None:
            mutagen_data['album'] = unicode(album)
        mutagen_data['drm'] = drm
        if cover_art and album is not None:
            mutagen_data['cover_art_path'] = self.cover_art_path(album)
            # simulate read_metadata() writing the mutagen_data file
            open(mutagen_data['cover_art_path'], 'wb').write("FAKE FILE")
        self.mutagen_data[path] = mutagen_data
        self.processor.run_mutagen_callback(path, mutagen_data)
        self.check_metadata(path)

    def check_queued_mutagen_calls(self, filenames):
        correct_paths = ['/videos/' + f for f in filenames]
        self.assertSameSet(correct_paths, self.processor.mutagen_paths())

    def check_queued_moviedata_calls(self, filenames):
        correct_paths = ['/videos/' + f for f in filenames]
        self.assertSameSet(correct_paths, self.processor.movie_data_paths())

    def check_queued_echonest_codegen_calls(self, filenames):
        correct_paths = ['/videos/' + f for f in filenames]
        self.assertSameSet(correct_paths,
                           self.processor.echonest_codegen_paths())

    def get_metadata(self, filename):
        path = self.make_path(filename)
        return self.metadata_manager.get_metadata(path)

    def check_mutagen_error(self, filename):
        path = self.make_path(filename)
        self.processor.run_mutagen_errback(path, ValueError())
        # mutagen failing shouldn't change the metadata
        self.check_metadata(path)

    def check_movie_data_not_scheduled(self, filename):
        if self.make_path(filename) in self.processor.movie_data_paths():
            raise AssertionError("movie data scheduled for %s" % filename)

    def get_screenshot_path(self, filename):
        return '/tmp/' + filename + '.png'

    def check_run_movie_data(self, filename, file_type, duration,
                             screenshot_worked):
        path = self.make_path(filename)
        moviedata_data = {}
        if file_type is not None:
            moviedata_data['file_type'] = unicode(file_type)
        if duration is not None:
            moviedata_data['duration'] = duration
        if screenshot_worked:
            ss_path = self.get_screenshot_path(filename)
            moviedata_data['screenshot_path'] = ss_path
        self.movieprogram_data[path] = moviedata_data
        self.processor.run_movie_data_callback(path, moviedata_data)
        self.check_metadata(path)

    def check_movie_data_error(self, filename):
        path = self.make_path(filename)
        self.processor.run_movie_data_errback(path, ValueError())
        # movie data failing shouldn't change the metadata
        self.check_metadata(path)

    def check_echonest_not_scheduled(self, filename):
        self.check_echonest_not_running(filename)
        path = self.make_path(filename)
        status = metadata.MetadataStatus.get_by_path(path)
        if status.echonest_status not in (status.STATUS_SKIP,
                                          status.STATUS_COMPLETE):
            raise AssertionError("Bad status in "
                                 "check_echonest_not_scheduled(): %s" %
                                 status.echonest_status)

    def check_echonest_not_running(self, filename):
        path = self.make_path(filename)
        if path in self.processor.echonest_codegen_paths():
            raise AssertionError("echonest_codegen scheduled for %s" %
                                 filename)

    def calc_fake_echonest_code(self, path):
        """Echoprint codes are huge strings of ascii data.  Generate a unique
        one for a path.
        """
        random.seed(path)
        length = random.randint(3000, 4000)
        return ''.join(random.choice(string.ascii_letters)
                       for i in xrange(length))

    def check_run_echonest_codegen(self, filename):
        path = self.make_path(filename)
        code = self.calc_fake_echonest_code(path)
        self.processor.run_echonest_codegen_callback(path, code)
        self.check_metadata(path)
        # check that the data sent to echonest is correct
        metadata = self._calc_correct_metadata(path)
        echonest_metadata = {}
        for key in ('title', 'artist', 'duration'):
            if key in metadata:
                echonest_metadata[key] = metadata[key]
        if 'album' in metadata:
            echonest_metadata['release'] = metadata['album']
        self.assertEquals(self.processor.query_echonest_codes[path], code)
        self.assertDictEquals(self.processor.query_echonest_metadata[path],
                              echonest_metadata)

    def check_echonest_codegen_error(self, filename):
        path = self.make_path(filename)
        error = IOError()
        self.processor.run_echonest_codegen_errback(path, error)
        self.check_metadata(path)

    def check_run_echonest(self, filename, title, artist=None, album=None):
        path = self.make_path(filename)
        echonest_data = {}
        echonest_data['title'] = unicode('title')
        if artist is not None:
            echonest_data['artist'] = unicode(artist)
        if album is not None:
            echonest_data['album'] = unicode(album)
            echonest_data['cover_art_path'] = self.cover_art_path(album, True)
            # simulate grab_url() writing the mutagen_data file
            open(echonest_data['cover_art_path'], 'wb').write("FAKE FILE")
        self.echonest_data[path] = echonest_data
        self.processor.run_echonest_callback(path, echonest_data)
        self.check_metadata(path)

    def check_echonest_error(self, filename):
        path = self.make_path(filename)
        error = IOError()
        self.processor.run_echonest_errback(path, error)
        self.check_metadata(path)

    def check_set_user_info(self, filename, **info):
        path = self.make_path(filename)
        self.user_info_data[path].update(info)
        self.metadata_manager.set_user_data(path, info)
        self.check_metadata(path)

    def test_video(self):
        # Test video files with no issues
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'video', 101, 'Foo', 'Fight Vids')
        self.check_run_movie_data('foo.avi', 'video', 100, True)
        self.check_echonest_not_scheduled('foo.avi')

    def test_video_no_screenshot(self):
        # Test video files where the movie data program fails to take a
        # screenshot
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'video', 100, 'Foo')
        self.check_run_movie_data('foo.avi', 'video', 100, False)
        self.check_echonest_not_scheduled('foo.avi')

    def test_audio(self):
        # Test audio files with no issues
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'Bar', 'Fights')
        self.check_movie_data_not_scheduled('foo.mp3')
        self.check_run_echonest_codegen('foo.mp3')
        self.check_run_echonest('foo.mp3', 'Bar', 'Artist', 'Fights')

    def test_echonest_codegen_error(self):
        # Test audio files that echonest_codegen bails on
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'Bar', 'Fights')
        self.check_movie_data_not_scheduled('foo.mp3')
        self.check_echonest_codegen_error('foo.mp3')

    def test_internet_lookup_pref(self):
        # Test that the NET_LOOKUP_BY_DEFAULT pref works
        app.config.set(prefs.NET_LOOKUP_BY_DEFAULT, False)
        self.check_add_file('foo.mp3')
        metadata = self.get_metadata('foo.mp3')
        self.assertEquals(metadata['net_lookup_enabled'], False)
        app.config.set(prefs.NET_LOOKUP_BY_DEFAULT, True)
        self.check_add_file('bar.mp3')
        metadata = self.get_metadata('bar.mp3')
        self.assertEquals(metadata['net_lookup_enabled'], True)

    def test_set_net_lookup_enabled(self):
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'Bar', 'Fights')
        self.check_movie_data_not_scheduled('foo.mp3')
        self.check_run_echonest_codegen('foo.mp3')
        self.check_run_echonest('foo.mp3', 'Bar', 'Artist', 'Fights')
        self.check_set_net_lookup_enabled('foo.mp3', False)
        self.check_set_net_lookup_enabled('foo.mp3', True)

    def test_set_net_lookup_for_all(self):
        for x in xrange(10):
            self.check_add_file('foo-%s.mp3' % x)

        self.metadata_manager.set_net_lookup_enabled_for_all(False)
        for x in xrange(10):
            path = self.make_path('foo-%s.mp3' % x)
            metadata = self.metadata_manager.get_metadata(path)
            self.assertEquals(metadata['net_lookup_enabled'], False)

        self.metadata_manager.set_net_lookup_enabled_for_all(True)
        for x in xrange(10):
            path = self.make_path('foo-%s.mp3' % x)
            metadata = self.metadata_manager.get_metadata(path)
            self.assertEquals(metadata['net_lookup_enabled'], True)

    def test_net_lookup_enabled_stops_processor(self):
        # test that we don't run the echonest processor if if it's not enabled
        app.config.set(prefs.NET_LOOKUP_BY_DEFAULT, False)
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'Bar', 'Fights')
        self.check_movie_data_not_scheduled('foo.mp3')
        self.check_echonest_not_running('foo.mp3')
        self.check_echonest_not_scheduled('foo.mp3')
        # test that it starts running if we set the value to true
        self.check_set_net_lookup_enabled('foo.mp3', True)
        self.check_run_echonest_codegen('foo.mp3')
        self.check_run_echonest('foo.mp3', 'Bar', 'Artist', 'Fights2')

    def test_net_lookup_enabled_signals(self):
        # test that we don't run the echonest processor if if it's not enabled
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'Bar', 'Fights')
        self.check_run_echonest_codegen('foo.mp3')
        self.check_run_echonest('foo.mp3', 'Bar', 'Artist', 'Fights2')
        # test that we get the new-metadata signal when we set/unset the
        # set_lookup_enabled flag
        foo_path = self.make_path('foo.mp3')
        signal_handler = mock.Mock()
        self.metadata_manager.connect("new-metadata", signal_handler)
        def check_callback_data():
            args, kwargs = signal_handler.call_args
            self.assertEquals(kwargs, {})
            self.assertEquals(args[0], self.metadata_manager)
            # _calc_correct_metadata doesn't calculate has_drm.  Just ignore
            # it for this telt
            del args[1][foo_path]['has_drm']
            self.assertEquals(args[1].keys(), [foo_path])
            correct_metadata = self._calc_correct_metadata(foo_path)
            # we include None values for this signal because we may be erasing
            # metadata
            for name in metadata.attribute_names:
                if name not in correct_metadata and name != 'has_drm':
                    correct_metadata[name] = None
            self.assertDictEquals(args[1][foo_path], correct_metadata)

        self.check_set_net_lookup_enabled('foo.mp3', False)
        self.assertEquals(signal_handler.call_count, 1)
        check_callback_data()

        self.check_set_net_lookup_enabled('foo.mp3', True)
        self.assertEquals(signal_handler.call_count, 2)
        check_callback_data()

    def test_echonest_error(self):
        # Test echonest failing
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'Bar', 'Fights')
        self.check_movie_data_not_scheduled('foo.mp3')
        self.check_run_echonest_codegen('foo.mp3')
        self.check_echonest_error('foo.mp3')

    def test_audio_shares_cover_art(self):
        # Test that if one audio file in an album has cover art, they all will
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'Bar', 'Fights')
        self.check_add_file('foo2.mp3')
        self.check_run_mutagen('foo2.mp3', 'audio', 300, 'Foo', 'Fights',
                               cover_art=False)
        self.check_add_file('foo3.mp3')
        self.check_run_mutagen('foo3.mp3', 'audio', 400, 'Baz', 'Fights',
                               cover_art=False)

    def test_audio_no_duration(self):
        # Test audio files where mutagen can't get the duration
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', None, 'Bar', 'Fights')
        # Because mutagen failed to get the duration, we should have a movie
        # data call scheduled
        self.check_run_movie_data('foo.mp3', 'audio', 100, False)
        self.check_run_echonest_codegen('foo.mp3')
        self.check_run_echonest('foo.mp3', 'Bar', 'Artist', 'Fights')

    def test_audio_no_duration2(self):
        # same as test_audio_no_duration, but have movie data return that the
        # file is actually a video file.  In this case, we shouldn't run
        # echonest_codegen
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', None, 'Bar', 'Fights')
        # Because mutagen failed to get the duration, we should have a movie
        # data call scheduled
        self.check_run_movie_data('foo.mp3', 'video', 100, False)
        # since movie data returned video, we shouldn't run echonest_codegen
        self.check_echonest_not_scheduled('foo.mp3')

    def test_ogg(self):
        # Test ogg files
        self.check_add_file('foo.ogg')
        self.check_run_mutagen('foo.ogg', 'audio', 100, 'Bar', 'Fights')
        # Even though mutagen thinks this file is audio, we should still run
        # mutagen because it might by a mis-identified ogv file
        self.check_run_movie_data('foo.ogg', 'video', 100, True)
        self.check_echonest_not_scheduled('foo.ogg')

    def test_other(self):
        # Test non media files
        self.check_add_file('foo.pdf')
        self.check_run_mutagen('foo.pdf', 'other', None, None, None)
        # Since mutagen couldn't determine the file type, we should run movie
        # data
        self.check_run_movie_data('foo.pdf', 'other', None, False)
        # since neither could determine the filename, we shouldn't run
        # echonest_codegen
        self.check_echonest_not_scheduled('foo.pdf')

    def test_mutagen_failure(self):
        # Test mutagen failing
        self.check_add_file('foo.avi')
        self.check_mutagen_error('foo.avi')
        # We should run movie data since mutagen failed
        self.check_run_movie_data('foo.avi', 'other', 100, True)
        self.check_echonest_not_scheduled('foo.avi')

    def test_movie_data_failure(self):
        # Test video files where movie data fails
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'video', 100, 'Foo')
        self.check_movie_data_error('foo.avi')

    def test_has_drm(self):
        # check the has_drm flag
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'audio', 100, 'Foo', 'Fighters',
                               drm=True)
        # if mutagen thinks a file has drm, we still need to check with movie
        # data to make sure
        self.assertEquals(self.get_metadata('foo.avi')['has_drm'], False)
        # if we get a movie data error, than we know there's DRM
        self.check_movie_data_error('foo.avi')
        self.assertEquals(self.get_metadata('foo.avi')['has_drm'], True)

        # let's try that whole process again, but make movie data succeed.  In
        # that case has_drm should be false
        self.check_add_file('foo2.avi')
        self.check_run_mutagen('foo2.avi', 'audio', 100, 'Foo', 'Fighters',
                               drm=True)
        self.assertEquals(self.get_metadata('foo2.avi')['has_drm'], False)
        self.check_run_movie_data('foo2.avi', 'audio', 100, True)
        self.assertEquals(self.get_metadata('foo2.avi')['has_drm'], False)

    def test_restart_incomplete(self):
        # Test restarting incomplete 
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'video', 100, 'Foo')
        self.check_add_file('bar.avi')
        self.check_add_file('baz.mp3')
        self.check_run_mutagen('baz.mp3', 'audio', 100, 'Foo', 'Fighters')
        self.check_add_file('qux.avi')
        self.check_run_mutagen('qux.avi', 'video', 100, 'Foo')
        self.check_run_movie_data('qux.avi', 'video', 100, True)
        # At this point, foo is waiting for moviedata, bar is waiting for
        # mutagen and baz is waiting for echonest_codegen.
        self.check_queued_moviedata_calls(['foo.avi'])
        self.check_queued_mutagen_calls(['bar.avi'])
        self.check_queued_echonest_codegen_calls(['baz.mp3'])
        # Check that if we call restart_incomplete now, we don't get queue
        # mutagen or movie data twice.
        self.processor.reset()
        self.metadata_manager.restart_incomplete()
        self.check_queued_moviedata_calls([])
        self.check_queued_mutagen_calls([])
        self.check_queued_echonest_codegen_calls([])
        # Create a new MetadataManager and call restart_incomplete on that.
        # That should invoke mutagen and movie data
        self.metadata_manager = metadata.MetadataManager(self.tempdir)
        self.metadata_manager.restart_incomplete()
        self.check_queued_moviedata_calls(['foo.avi'])
        self.check_queued_mutagen_calls(['bar.avi'])
        self.check_queued_echonest_codegen_calls(['baz.mp3'])
        # Theck that when things finish, we get other incomplete metadata
        self.check_run_mutagen('bar.avi', 'audio', None, 'Foo')
        self.check_queued_moviedata_calls(['foo.avi', 'bar.avi'])
        self.check_run_movie_data('bar.avi', 'audio', 100, 'Foo')
        self.check_run_echonest_codegen('baz.mp3')
        self.check_run_echonest('baz.mp3', 'Foo')
        self.check_queued_echonest_codegen_calls(['bar.avi'])

    def check_path_in_system(self, filename, correct_value):
        path = self.make_path(filename)
        self.assertEquals(self.metadata_manager.path_in_system(path),
                          correct_value)

    def test_path_in_system(self):
        # Test the path_in_system() call
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'video', 100, 'Foo')
        self.check_add_file('bar.avi')
        self.check_add_file('baz.mp3')
        self.check_run_mutagen('baz.mp3', 'audio', 100, 'Foo', 'Fighters')
        self.check_add_file('qux.avi')
        self.check_run_mutagen('qux.avi', 'video', 100, 'Foo')
        self.check_run_movie_data('qux.avi', 'video', 100, True)
        self.check_path_in_system('foo.avi', True)
        self.check_path_in_system('bar.avi', True)
        self.check_path_in_system('baz.mp3', True)
        self.check_path_in_system('qux.avi', True)
        self.check_path_in_system('other-file.avi', False)
        # Test path_in_system() for objects in the DB, but not in cache
        self.clear_ddb_object_cache()
        self.metadata_manager = metadata.MetadataManager(self.tempdir)
        self.check_path_in_system('foo.avi', True)
        self.check_path_in_system('bar.avi', True)
        self.check_path_in_system('baz.mp3', True)
        self.check_path_in_system('qux.avi', True)
        self.check_path_in_system('other-file.avi', False)

    def test_delete(self):
        # add many files at different points in the metadata process
        files_in_mutagen = []
        for x in range(10):
            filename = 'in-mutagen-%i.mp3' % x
            files_in_mutagen.append(self.make_path(filename))
            self.check_add_file(filename)

        files_in_moviedata = []
        for x in range(10):
            filename = 'in-movie-data-%i.avi' % x
            files_in_moviedata.append(self.make_path(filename))
            self.check_add_file(filename)
            self.check_run_mutagen(filename, 'video', 100, 'Foo')

        files_in_echonest = []
        for x in range(10):
            filename = 'in-echonest-%i.mp3' % x
            files_in_echonest.append(self.make_path(filename))
            self.check_add_file(filename)
            self.check_run_mutagen(filename, 'audio', 100, 'Foo')

        files_finished = []
        for x in range(10):
            filename = 'finished-%i.avi' % x
            files_finished.append(self.make_path(filename))
            self.check_add_file(filename)
            self.check_run_mutagen(filename, 'video', 100, 'Foo')
            self.check_run_movie_data(filename, 'video', 100, True)

        # remove the files using both api calls
        all_paths = (files_in_mutagen + files_in_moviedata +
                     files_in_echonest + files_finished)

        self.metadata_manager.remove_file(all_paths[0])
        self.metadata_manager.remove_files(all_paths[1:])
        # check that the metadata manager sent a CancelFileOperations message
        self.assertEquals(self.processor.canceled_files, set(all_paths))
        # check that echonest calls were canceled
        echonest_processor = self.metadata_manager.echonest_processor
        self.assertEquals(len(echonest_processor._codegen_queue), 0)
        self.assertEquals(len(echonest_processor._echonest_queue), 0)
        # check that none of the videos are in the metadata manager
        for path in all_paths:
            self.assertRaises(KeyError, self.metadata_manager.get_metadata,
                              path)
        # check that callbacks/errbacks for those files don't result in
        # errors.  The metadata system may have already been processing the
        # file when it got the CancelFileOperations message.
        metadata = {
            'file_type': u'video',
            'duration': 100
        }
        self.processor.run_movie_data_callback(files_in_moviedata[0],
                                               metadata)
        self.processor.run_mutagen_errback(
            files_in_mutagen[0], ValueError())

    def test_restore(self):
        db_path = os.path.join(self.tempdir, 'testdb');
        self.reload_database(db_path)
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'Bar', 'Fights')
        self.check_movie_data_not_scheduled('foo.mp3')
        self.check_run_echonest_codegen('foo.mp3')
        self.check_run_echonest('foo.mp3', 'Bar', 'Artist', 'Fights')
        # reload our database to force restoring metadata items
        self.reload_database(db_path)
        self.check_metadata('foo.mp3')

    def test_user_and_torrent_data(self):
        self.check_add_file('foo.avi')
        self.check_set_user_info('foo.avi', title=u'New Foo',
                                 album=u'The best')
        self.check_run_mutagen('foo.avi', 'video', 100, 'Foo')
        self.check_set_user_info('foo.avi', title=u'Newer Foo')
        self.check_run_movie_data('foo.avi', 'video', 100, True)
        self.check_set_user_info('foo.avi', album=u'The bestest')
        # check the final metadata one last time
        metadata = self.get_metadata('foo.avi')
        self.assertEquals(metadata['title'], 'Newer Foo')
        self.assertEquals(metadata['album'], 'The bestest')

    def test_queueing(self):
        # test that if we don't send too many requests to the worker process
        paths = ['/videos/video-%d.avi' % i for i in xrange(200)]

        def run_mutagen(start, stop):
            for p in paths[start:stop]:
                # this ensures that both moviedata and echonest will be run
                # for this file
                metadata = {
                    'file_type': u'audio',
                    'title': u'Title',
                    'album': u'Album',
                    'drm': False,
                }
                self.processor.run_mutagen_callback(p, metadata)

        def run_movie_data(start, stop):
            for p in paths[start:stop]:
                metadata = {
                    'file_type': u'audio',
                    'duration': 100,
                }
                self.processor.run_movie_data_callback(p, metadata)

        def run_echonest_codegen(start, stop):
            for p in paths[start:stop]:
                code = self.calc_fake_echonest_code(p)
                self.processor.run_echonest_codegen_callback(p, code)

        def run_echonest(start, stop):
            for p in paths[start:stop]:
                metadata = {
                    'title': u'Title',
                    'album': u'Album',
                }
                self.processor.run_echonest_callback(p, metadata)

        def check_counts(mutagen_calls, movie_data_calls,
                         echonest_codegen_calls, echonest_calls):
            self.metadata_manager._process_metadata_finished()
            self.metadata_manager._process_metadata_errors()
            self.assertEquals(len(self.processor.mutagen_paths()),
                              mutagen_calls)
            self.assertEquals(len(self.processor.movie_data_paths()),
                              movie_data_calls)
            self.assertEquals(len(self.processor.echonest_codegen_paths()),
                              echonest_codegen_calls)
            self.assertEquals(len(self.processor.echonest_paths()),
                              echonest_calls)

        # Add all 200 paths to the metadata manager.  Only 100 should be
        # queued up to mutagen
        for p in paths:
            self.metadata_manager.add_file(p)
        check_counts(100, 0, 0, 0)

        # let 50 mutagen tasks complete, we should queue up 50 more
        run_mutagen(0, 50)
        check_counts(100, 50, 0, 0)
        # let 75 more complete, we should be hitting our movie data max now
        run_mutagen(50, 125)
        check_counts(75, 100, 0, 0)
        # run a bunch of movie data calls.  This will let us test the echonest
        # queueing
        run_movie_data(0, 100)
        # we should only have 1 echonest codegen program running at once
        check_counts(75, 25, 1, 0)
        # when that gets done, we should only have 1 echonest query running at
        # once
        run_echonest_codegen(0, 2)
        check_counts(75, 25, 1, 1)
        # we should stop running echonest codegen once we have 5 codes queued
        # up
        run_echonest_codegen(2, 6)
        check_counts(75, 25, 0, 1)
        # looks good, just double check that we finish our queues okay
        run_mutagen(125, 200)
        check_counts(0, 100, 0, 1)
        run_movie_data(100, 200)
        check_counts(0, 0, 0, 1)
        for i in xrange(195):
            run_echonest(i, i+1)
            run_echonest_codegen(i+6, i+7)
        run_echonest(195, 200)

    def test_move(self):
        # add a couple files at different points in the metadata process
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'video', 100, 'Foo')
        self.check_add_file('bar.mp3')
        self.check_add_file('baz.avi')
        self.check_run_mutagen('baz.avi', 'video', 100, 'Foo')
        self.check_run_movie_data('baz.avi', 'video', 100, True)
        self.check_queued_moviedata_calls(['foo.avi'])
        self.check_queued_mutagen_calls(['bar.mp3'])
        # Move some of the files to new names
        def new_path_name(old_path):
            return '/videos2/' + os.path.basename(old_path)
        to_move = ['/videos/foo.avi', '/videos/bar.mp3', '/videos/baz.avi' ]
        old_metadata = dict((p, self.metadata_manager.get_metadata(p))
                             for p in to_move)
        self.metadata_manager.will_move_files(to_move)
        # check that the metadata manager sent a CancelFileOperations message
        self.assertEquals(self.processor.canceled_files, set(to_move))
        # tell metadata manager that the move is done
        for path in to_move:
            new_path = new_path_name(path)
            self.metadata_manager.file_moved(path, new_path)
            self.net_lookup_enabled[new_path] = \
                    self.net_lookup_enabled.pop(path)
        # check that the metadata stored with the new path and not the old one
        for path in to_move:
            new_path = new_path_name(path)
            for dct in (self.mutagen_data, self.movieprogram_data,
                        self.user_info_data):
                dct[new_path] = dct.pop(path)
            self.assertEquals(old_metadata[path],
                              self.metadata_manager.get_metadata(new_path))
            self.assertRaises(KeyError, self.metadata_manager.get_metadata,
                              path)
        # check that callbacks/errbacks for the old paths don't result in
        # errors.  The metadata system may have already been processing the
        # file when it got the CancelFileOperations message.
        metadata = {
            'file_type': u'video',
            'duration': 100,
        }
        self.processor.run_movie_data_callback('/videos/foo.avi', metadata)
        self.processor.run_mutagen_errback('/videos/bar.mp3', ValueError())
        # check that callbacks work for new paths
        self.check_run_movie_data('/videos2/foo.avi', 'video', 100, True)
        self.check_run_mutagen('/videos2/bar.mp3', 'audio', 120, 'Bar',
                               'Fights')

    def test_queueing_with_delete(self):
        # test that we remove files that are queued as well
        paths = ['/videos/video-%d.avi' % i for i in xrange(200)]
        for p in paths:
            self.metadata_manager.add_file(p)
        # we now have 200 mutagen calls so 100 of them should be pending

        # if some files get removed, then we should start new ones
        self.metadata_manager.remove_files(paths[:25])
        self.assertEquals(len(self.processor.mutagen_paths()), 125)

        # If pending files get removed, we should remove them from the pending
        # queues
        self.metadata_manager.remove_files(paths[25:])
        mm = self.metadata_manager
        self.assertEquals(len(mm.mutagen_processor._pending_tasks), 0)
        self.assertEquals(len(mm.moviedata_processor._pending_tasks), 0)

    def test_queueing_with_move(self):
        # test moving queued files
        paths = ['/videos/video-%d.avi' % i for i in xrange(200)]
        for p in paths:
            self.metadata_manager.add_file(p)
        # we now have 200 mutagen calls so 100 of them should be pending

        # if pending files get moved, the paths should be updated
        moved = paths[150:]
        new_paths = ['/new' + p for p in moved]
        self.metadata_manager.will_move_files(moved)
        for old_path, new_path in zip(moved, new_paths):
            self.metadata_manager.file_moved(old_path, new_path)
        # send mutagen call backs so the pending calls start
        for p in paths[:100]:
            metadata = {
                'file_type': u'video',
                'duration': 100,
                'title': u'Title',
                'album': u'Album',
                'drm': False,
            }
            self.processor.run_mutagen_callback(p, metadata)
        correct_paths = paths[100:150] + new_paths
        self.assertSameSet(self.processor.mutagen_paths(), correct_paths)

class TestCodegen(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.callback_data = self.errback_data = None
        self.codegen_path = get_enmfp_executable_path()

    def callback(self, *args):
        self.callback_data = args
        self.stopEventLoop(abnormal=False)

    def errback(self, *args):
        self.errback_data = args
        self.stopEventLoop(abnormal=False)

    def run_codegen(self, song_path):
        echonest.exec_codegen(self.codegen_path, song_path,
                              self.callback, self.errback)
        self.processThreads()
        self.runEventLoop()

    def test_codegen(self):
        song_path = resources.path('testdata/Wikipedia_Song_by_teddy.ogg')
        self.run_codegen(song_path)

        self.assertEquals(self.errback_data, None)
        correct_code = ('eJwdkIkRBCEIBFPiEzEcRDb_EG64LavV5pFaov8nAejA5moFrD'
                        'n6YE8gBkeAnFM58Cb5JdBwLHCsg6liH7cbOOjHiTyexlwI84eA'
                        'TDuZ18R9phicJn7r1afGwXvtrfSZ03qLUvVB0mWJ-gwjS1mqyK'
                        'KGVDlxTAOVlS4LXR9tOdT3nGvMzprtrl4rrC_nfReS8nOs0q1y'
                        'X17Z8aryw34aEnmnceG3PXuHRuyFPIRaIEkF8-IPmVFd5Mdhhi'
                        'S9LmYmndQvMEfdDL3aiECqoAryB-OLX8E=')
        self.assertEquals(self.callback_data, (song_path, correct_code))

    def test_codegen_error(self):
        song_path =resources.path('/file/not/found')
        self.run_codegen(song_path)
        self.assertEquals(self.callback_data, None)
        self.assertEquals(self.errback_data[0], song_path)
        self.assert_(isinstance(self.errback_data[1], Exception))


mock_grab_url = mock.Mock()
@mock.patch('miro.httpclient.grab_url', new=mock_grab_url)
class TestEchonestQueries(MiroTestCase):
    """Test our echonest handling code"""

    def setUp(self):
        MiroTestCase.setUp(self)
        mock_grab_url.reset_mock()
        self.callback_data = self.errback_data = None
        self.path = "/videos/FakeSong.mp3"
        self.album_art_dir = os.path.join(self.tempdir, 'echonest-album-art')
        os.makedirs(self.album_art_dir)
        # data to send to echonest.  Note that the metadata we pass to
        # query_echonest() doesn't neseccarily relate to the fake reply we
        # send back.
        self.echonest_code = "FaKe=EChoNEST+COdE"
        self.query_metadata = {
            "artist": "Michael jackson",
            "album": "800 chansons des annes 80",
            "title": "Billie jean",
            "duration": 294000,
        }
        self.echonest_id = "fake-id-echonest"
        self.seven_digital_id = "fake-id-7digital"
        self.album_art_url = None
        self.album_art_data = "fake-album-art-data"
        # 7digital release ids
        self.bossanova_release_id = 189844
        self.release_ids_for_billie_jean = [
            518377, 280410, 307167, 289401, 282494, 282073, 624250, 312343,
            391641, 341656, 284075, 280538, 283379, 312343, 669160, 391639,
        ]
        echonest._EchonestQuery.seven_digital_cache = {}

    def callback(self, *args):
        self.callback_data = args

    def errback(self, *args):
        self.errback_data = args

    def start_query(self):
        """Call echonest.query_echonest()."""
        # This tracks the metadata we expect to see back from query_echonest()
        self.reply_metadata = {}
        echonest.query_echonest(self.path, self.album_art_dir,
                                self.echonest_code, 3.15,
                                self.query_metadata,
                                self.callback, self.errback)

    def check_grab_url(self, url, query_dict=None, post_vars=None,
                       write_file=None):
        """Check that grab_url was called with a given URL.
        """
        self.assertEquals(mock_grab_url.call_count, 1)
        args, kwargs = mock_grab_url.call_args
        if post_vars is not None:
            grab_url_post_vars = kwargs.pop('post_vars')
            # handle query specially, since it's a json encoded dict so it can
            # be formatted different ways
            if 'query' in post_vars:
                self.assertDictEquals(
                    json.loads(grab_url_post_vars.pop('query')),
                    post_vars.pop('query'))
            self.assertDictEquals(grab_url_post_vars, post_vars)
        if write_file is None:
            self.assertDictEquals(kwargs, {})
        else:
            self.assertDictEquals(kwargs, {'write_file': write_file})
        self.assertEquals(len(args), 3)
        grabbed_url = urlparse.urlparse(args[0])
        parsed_url = urlparse.urlparse(url)
        self.assertEquals(grabbed_url.scheme, parsed_url.scheme)
        self.assertEquals(grabbed_url.netloc, parsed_url.netloc)
        self.assertEquals(grabbed_url.path, parsed_url.path)
        self.assertEquals(grabbed_url.fragment, parsed_url.fragment)
        if query_dict:
            self.assertDictEquals(urlparse.parse_qs(grabbed_url.query),
                                  query_dict)
        else:
            self.assertEquals(grabbed_url.query, '')

    def check_echonest_grab_url_call(self):
        """Check the url sent to grab_url to perform our echonest query."""
        echonest_url = 'http://developer.echonest.com/api/v4/song/identify'
        post_vars = {
            'api_key': echonest.ECHO_NEST_API_KEY,
            # NOTE: either order of the bucket params is okay
            'bucket': ['tracks', 'id:7digital'],
            'query': {
                'code': self.echonest_code,
                'metadata': {
                    'artist': self.query_metadata['artist'].encode('utf-8'),
                    'title': self.query_metadata['title'].encode('utf-8'),
                    'release': self.query_metadata['album'].encode('utf-8'),
                    'duration': self.query_metadata['duration'] // 1000,
                    'version': 3.15,
                },
            },
        }
        self.check_grab_url(echonest_url, post_vars=post_vars)

    def send_echonest_reply(self, response_file):
        """Send a reply back from echonest.

        As a side-effect we reset mock_grab_url before sending the reply to
        get ready for the 7digital grab_url call

        :param response_file: which file to use for response data
        """
        response_path = resources.path('testdata/echonest-replies/' +
                                       response_file)
        response_data = open(response_path).read()
        callback = mock_grab_url.call_args[0][1]
        mock_grab_url.reset_mock()
        callback({'body': response_data})
        if response_file in ('rock-music', 'no-releases'):
            self.reply_metadata['artist'] = 'Pixies'
            self.reply_metadata['title'] = 'Rock Music'
            self.reply_metadata['echonest_id'] = 'SOGQSXU12AF72A2615'
        elif response_file == 'billie-jean':
            self.reply_metadata['artist'] = 'Michael Jackson'
            self.reply_metadata['title'] = 'Billie Jean'
            self.reply_metadata['echonest_id'] = 'SOJIZLV12A58A78309'

    def check_7digital_grab_url_call(self, release_id):
        """Check the url sent to grab_url to perform our 7digital query."""
        seven_digital_url = 'http://api.7digital.com/1.2/release/details'
        correct_query = {
            'oauth_consumer_key': [echonest.SEVEN_DIGITAL_API_KEY],
            'imageSize': ['350'],
            'releaseid': [str(release_id)],
        }
        self.check_grab_url(seven_digital_url, correct_query)

    def send_7digital_reply(self, response_file):
        """Send a reply back from 7digital.

        As a side-effect we reset the mock_grab_url object.

        :param response_file: which file to use for response data
        """
        response_path = resources.path('testdata/7digital-replies/%s' %
                                       response_file)
        response_data = open(response_path).read()
        callback = mock_grab_url.call_args[0][1]
        mock_grab_url.reset_mock()
        callback({'body': response_data})
        if response_file == self.bossanova_release_id:
            self.reply_metadata['album'] = 'Bossanova'
            self.reply_metadata['cover_art_path'] = os.path.join(
                self.album_art_dir, 'Bossanova')
            self.album_art_url = (
                'http://cdn.7static.com/static/img/sleeveart/'
                '00/001/898/0000189844_350.jpg')

    def check_album_art_grab_url_call(self):
        if self.album_art_url is None:
            raise ValueError("album_art_url not set")
        album_art_path = os.path.join(self.album_art_dir,
                                      self.reply_metadata['album'])
        self.check_grab_url(self.album_art_url, write_file=album_art_path)

    def send_album_art_reply(self):
        """Send a reply back from the album art webserver

        As a side-effect we reset mock_grab_url.
        """
        callback = mock_grab_url.call_args[0][1]
        cover_art_file = mock_grab_url.call_args[1]['write_file']
        open(cover_art_file, 'w').write("fake data")
        mock_grab_url.reset_mock()
        # don't send the body since we write a file instead
        callback({})

    def check_callback(self):
        """Check that echonest.query_echonest() sent the right data to our
        callback.
        """
        self.assertNotEquals(self.callback_data, None)
        self.assertEquals(self.errback_data, None)
        self.assertEquals(self.callback_data[0], self.path)
        self.assertDictEquals(self.callback_data[1], self.reply_metadata)
        for key, value in self.callback_data[1].items():
            if (key in ('title', 'artist', 'album') and
                not isinstance(value, unicode)):
                raise AssertionError("value for %s not unicode" % key)

    def check_errback(self):
        """Check that echonest.query_echonest() called our errback instead of
        our callback.
        """
        self.assertEquals(self.callback_data, None)
        self.assertNotEquals(self.errback_data, None)

    def check_grab_url_not_called(self):
        self.assertEquals(mock_grab_url.call_count, 0)

    def send_http_error(self):
        errback = mock_grab_url.call_args[0][2]
        error = httpclient.UnexpectedStatusCode(404)
        errback(error)

    def test_normal_query(self):
        # test normal operations
        self.start_query()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_call(self.bossanova_release_id)
        self.send_7digital_reply(self.bossanova_release_id)
        self.check_album_art_grab_url_call()
        self.send_album_art_reply()
        self.check_callback()

    def test_album_art_error(self):
        # test normal operations
        self.start_query()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_call(self.bossanova_release_id)
        self.send_7digital_reply(self.bossanova_release_id)
        self.check_album_art_grab_url_call()
        self.send_http_error()
        # we shouldn't have cover_art_path in the reply, since the request
        # failed
        del self.reply_metadata['cover_art_path']
        self.check_callback()

    def test_not_found(self):
        # test echonest not finding our song
        self.start_query()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('no-match')
        self.check_callback()

    def test_echonest_http_error(self):
        # test http errors with echonest
        self.start_query()
        self.check_echonest_grab_url_call()
        self.send_http_error()
        mock_grab_url.reset_mock()
        self.check_grab_url_not_called()
        self.check_errback()

    def test_no_releases(self):
        # test no releases for a song
        self.start_query()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('no-releases')
        self.check_grab_url_not_called()
        self.check_callback()

    def test_7digital_http_error(self):
        # test http errors with 7digital
        self.start_query()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_call(self.bossanova_release_id)
        self.send_http_error()
        self.check_callback()

    def test_7digital_no_match(self):
        # test 7digital not matching our release id
        self.start_query()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_call(self.bossanova_release_id)
        self.send_7digital_reply('no-matches')
        self.check_callback()

    def test_multiple_releases(self):
        # test multple releases when one matches our ID3 tag
        self.start_query()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('billie-jean')
        # When we have multiple releases, we don't have a good way of finding
        # which one is correct.  We should skip querying 7digital.
        self.check_grab_url_not_called()
        self.check_callback()

    def test_7digital_caching(self):
        # test that we cache 7digital results
        self.start_query()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_call(self.bossanova_release_id)
        self.send_7digital_reply(self.bossanova_release_id)
        self.check_album_art_grab_url_call()
        self.send_album_art_reply()
        self.check_callback()
        old_metadata = self.reply_metadata
        # start a new query that results in the same release id.
        self.echonest_code = 'fake-code-2'
        self.start_query()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        # we shouldn't call grab_URL
        self.check_grab_url_not_called()
        self.reply_metadata = old_metadata
        self.check_callback()

    def test_avoid_redownloading_album_art(self):
        # test that we don't download album art that we already have
        album_art_path = os.path.join(self.album_art_dir, 'Bossanova')
        open(album_art_path, 'w').write('FAKE DATA')
        self.start_query()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_call(self.bossanova_release_id)
        self.send_7digital_reply(self.bossanova_release_id)
        # we shouldn't try to download the album art, since that file is
        # already there
        self.check_grab_url_not_called()
        self.check_callback()

    def test_query_encoding(self):
        # test that we send parameters as unicode to echonest/7digital
        self.query_metadata['artist'] = "M\u0129chael jackson"
        self.query_metadata['album'] = "Thr\u0129ller"
        self.query_metadata['title'] = u"B\u0129llie jean"
        self.test_normal_query()
