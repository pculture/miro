import collections
import itertools
import logging
import os
import urllib
import urlparse
import random
import shutil
import string
import time
import json

from miro.test import mock
from miro.test.framework import MiroTestCase, EventLoopTest, MatchAny
from miro import app
from miro import database
from miro import devices
from miro import echonest
from miro import item
from miro import httpclient
from miro import messages
from miro import models
from miro import prefs
from miro import schema
from miro import filetypes
from miro import metadata
from miro import workerprocess
from miro.plat import resources
from miro.plat.utils import (PlatformFilenameType,
                             get_enmfp_executable_info,
                             utf8_to_filename, unicode_to_filename)

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

    def exec_codegen(self, codegen_info, path, callback, errback):
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
        # remove the echonest query code in case we retry it
        del self.query_echonest_codes[source_path]
        errback(source_path, error)

class MetadataManagerTest(MiroTestCase):
    # Test the MetadataManager class
    def setUp(self):
        MiroTestCase.setUp(self)
        self.mutagen_data = collections.defaultdict(dict)
        self.movieprogram_data = collections.defaultdict(dict)
        self.echonest_data = collections.defaultdict(dict)
        self.echonest_ids = {}
        self.user_info_data = collections.defaultdict(dict)
        # maps paths -> should we do an interent lookup
        self.net_lookup_enabled = {}
        self.processor = MockMetadataProcessor()
        self.patch_function('miro.workerprocess.send', self.processor.send)
        self.patch_function('miro.echonest.exec_codegen',
                            self.processor.exec_codegen)
        self.patch_function('miro.echonest.query_echonest',
                            self.processor.query_echonest)
        self.metadata_manager = metadata.LibraryMetadataManager(self.tempdir,
                                                                self.tempdir)
        # For these examples we want to run echonest by default
        app.config.set(prefs.NET_LOOKUP_BY_DEFAULT, True)
        # Don't wait in-between runs of the echonest codegen
        metadata._EchonestProcessor.CODEGEN_COOLDOWN_TIME = 0.0

    def tearDown(self):
        metadata._EchonestProcessor.CODEGEN_COOLDOWN_TIME = 5.0
        MiroTestCase.tearDown(self)

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
            cover_art = self.cover_art_for_album(metadata['album'])
            if cover_art:
                metadata['cover_art'] = cover_art
        # created_cover_art is used by MetadataManager, but it's not saved to
        # the metadata table
        if 'created_cover_art' in metadata:
            del metadata['created_cover_art']
        return metadata

    def check_set_net_lookup_enabled(self, filename, enabled):
        path = self.make_path(filename)
        self.net_lookup_enabled[path] = enabled
        self.metadata_manager.set_net_lookup_enabled([path], enabled)
        self.check_metadata(path)

    def cover_art_for_album(self, album_name):
        mutagen_cover_art = None
        echonest_cover_art = None
        for metadata in self.mutagen_data.values():
            if ('album' in metadata and 'cover_art' in metadata and
                metadata['album'] == album_name):
                if (mutagen_cover_art is not None and
                    metadata['cover_art'] != mutagen_cover_art):
                    raise AssertionError("Different mutagen cover_art "
                                         "for " + album_name)
                mutagen_cover_art = metadata['cover_art']
        for metadata in self.echonest_data.values():
            if ('album' in metadata and 'cover_art' in metadata and
                metadata['album'] == album_name):
                if (echonest_cover_art is not None and
                    metadata['cover_art'] != echonest_cover_art):
                    raise AssertionError("Different mutagen cover_art "
                                         "for " + album_name)
                echonest_cover_art = metadata['cover_art']
        if echonest_cover_art:
            return echonest_cover_art
        else:
            return mutagen_cover_art

    def check_metadata(self, filename):
        path = self.make_path(filename)
        correct_metadata = self._calc_correct_metadata(path)
        self.metadata_manager._process_metadata_finished()
        with self.allow_warnings():
            self.metadata_manager._process_metadata_errors()
        metadata_for_path = self.metadata_manager.get_metadata(path)
        # don't check has_drm, we have a special test for that
        for dct in (metadata_for_path, correct_metadata):
            for key in ('has_drm', 'drm'):
                if key in dct:
                    del dct[key]
        self.assertDictEquals(metadata_for_path, correct_metadata)
        # check echonest ids
        status = metadata.MetadataStatus.get_by_path(path)
        self.assertEquals(status.echonest_id,
                          self.echonest_ids.get(path))

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
        with self.allow_warnings():
            self.assertRaises(ValueError, self.metadata_manager.add_file, path)

    def cover_art(self, album_name, echonest=False):
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
            cover_art = self.cover_art(album)
            mutagen_data['cover_art'] = cover_art
            if not os.path.exists(cover_art):
                # simulate read_metadata() writing the mutagen_data file
                open(cover_art, 'wb').write("FAKE FILE")
                mutagen_data['created_cover_art'] = True
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

    def check_queued_echonest_calls(self, filenames):
        correct_paths = ['/videos/' + f for f in filenames]
        self.assertSameSet(correct_paths,
                           self.processor.echonest_paths())

    def get_metadata(self, filename):
        path = self.make_path(filename)
        return self.metadata_manager.get_metadata(path)

    def check_mutagen_error(self, filename):
        path = self.make_path(filename)
        with self.allow_warnings():
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
            moviedata_data['screenshot'] = ss_path
        self.movieprogram_data[path] = moviedata_data
        self.processor.run_movie_data_callback(path, moviedata_data)
        self.check_metadata(path)

    def check_movie_data_error(self, filename):
        path = self.make_path(filename)
        with self.allow_warnings():
            self.processor.run_movie_data_errback(path, ValueError())
        # movie data failing shouldn't change the metadata
        self.check_metadata(path)

    def check_echonest_not_scheduled(self, filename):
        """check that echonest is not running and that it won't be when
        mutagen/moviedata finishes.
        """
        self.check_echonest_not_running(filename)
        path = self.make_path(filename)
        status = metadata.MetadataStatus.get_by_path(path)
        self.assertEquals(status.echonest_status, status.STATUS_SKIP)

    def check_echonest_not_running(self, filename):
        path = self.make_path(filename)
        if path in self.processor.echonest_codegen_paths():
            raise AssertionError("echonest_codegen scheduled for %s" %
                                 filename)
        if path in self.processor.echonest_paths():
            raise AssertionError("echonest scheduled for %s" %
                                 filename)

    def check_fetch_album_not_scheduled(self, filename):
        path = self.make_path(filename)
        if path in self.processor.fetch_album_paths():
            raise AssertionError("fetch_album scheduled for %s" %
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

    def allow_additional_echonest_query(self, filename):
        path = self.make_path(filename)
        del self.processor.query_echonest_codes[path]

    def check_echonest_codegen_error(self, filename):
        path = self.make_path(filename)
        error = IOError()
        with self.allow_warnings():
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
            cover_art = self.cover_art(album, True)
            echonest_data['cover_art'] = cover_art
            # simulate grab_url() writing the mutagen_data file
            if not os.path.exists(cover_art):
                open(cover_art, 'wb').write("FAKE FILE")
                echonest_data['created_cover_art'] = True
        # if any data is present, generate a fake echonest id
        result_data = echonest_data.copy()
        if (title, artist, album) != (None, None, None):
            if self.echonest_ids.get(path) is None:
                echonest_id = u''.join(random.choice(string.ascii_letters)
                                      for i in xrange(10))
                self.echonest_ids[path] = echonest_id
            else:
                echonest_id = self.echonest_ids[path]
            result_data['echonest_id'] = echonest_id
        self.echonest_data[path] = echonest_data
        self.processor.run_echonest_callback(path, result_data)
        self.check_metadata(path)

    def check_echonest_error(self, filename, http_error=False):
        path = self.make_path(filename)
        if http_error:
            error = httpclient.UnknownHostError('fake.echonest.host')
        else:
            error = IOError()
        with self.allow_warnings():
            self.processor.run_echonest_errback(path, error)
        self.check_metadata(path)

    def check_set_user_info(self, filename, **info):
        path = self.make_path(filename)
        self.user_info_data[path].update(info)
        self.metadata_manager.set_user_data(path, info)
        # force the entry for the user data to be reloaded.  This ensures that
        # the changes are actually reflected in the database
        status = metadata.MetadataStatus.get_by_path(path)
        entry = metadata.MetadataEntry.get_entry(u'user-data', status)
        self.reload_object(entry)
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
        self.check_run_echonest('foo.mp3', 'Bar', 'Artist', 'Fights')

    def test_audio_without_tags(self):
        # Test audio files without any metadata for echonest
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, None, None)
        self.check_movie_data_not_scheduled('foo.mp3')
        # Since there wasn't any metadata to send echonest, we should have
        # scheduled running the codegen
        self.check_run_echonest_codegen('foo.mp3')
        # After we run the codegen, we should run an echonest_query
        self.check_run_echonest('foo.mp3', 'Bar', 'Artist', 'Fights')

    def test_echonest_codegen_error(self):
        # Test audio files that echonest_codegen bails on
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, None)
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
        self.check_run_echonest('foo.mp3', 'Bar', 'Artist', 'Fights2')

    def test_net_lookup_enabled_signals(self):
        # test that we don't run the echonest processor if if it's not enabled
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'Bar', 'Fights')
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
        self.check_echonest_error('foo.mp3')

    def test_echonest_http_error(self):
        # Test echonest failing
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'Bar', 'Fights')
        self.check_movie_data_not_scheduled('foo.mp3')
        # If echonest sees an HTTP error, it should log it an a temporary
        # failure
        mock_retry_temporary_failure_caller = mock.Mock()
        patcher = mock.patch.object(self.metadata_manager,
                                    '_retry_temporary_failure_caller',
                                    mock_retry_temporary_failure_caller)
        with patcher:
            self.check_echonest_error('foo.mp3', http_error=True)
        path = self.make_path('foo.mp3')
        status = metadata.MetadataStatus.get_by_path(path)
        self.assertEquals(status.echonest_status,
                          status.STATUS_TEMPORARY_FAILURE)
        # check that we scheduled an attempt to retry the request
        mock_call = mock_retry_temporary_failure_caller.call_after_timeout
        mock_call.assert_called_once_with(3600)
        # check that success after retrying
        self.metadata_manager.retry_temporary_failures()
        status = metadata.MetadataStatus.get_by_path(path)
        self.assertEquals(status.echonest_status,
                          status.STATUS_NOT_RUN)
        self.check_run_echonest('foo.mp3', 'Bar', 'Artist', 'Fights')

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
        self.check_echonest_not_scheduled('foo.avi')

    def test_movie_data_skips_other(self):
        # Check that we don't run movie data if mutagen can't read the file
        # and the extension indicates it's not a media file (#18840)
        self.check_add_file('foo.pdf')
        self.check_run_mutagen('foo.pdf', None, None, None)
        self.check_movie_data_not_scheduled('foo.pdf')

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

    def test_cover_art_and_new_metadata(self):
        # Test that when we get cover art for one item, we update it for all
        # items for that album
        self.check_add_file('foo.mp3')
        self.check_add_file('foo-2.mp3')
        self.check_add_file('foo-3.mp3')
        self.check_add_file('foo-4.mp3')
        self.check_add_file('foo-5.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'Bar', 'AlbumOne',
                               cover_art=False)
        self.check_run_mutagen('foo-2.mp3', 'audio', 200, 'Bar', 'AlbumOne',
                               cover_art=False)
        self.check_run_mutagen('foo-3.mp3', 'audio', 200, 'Bar',
                               'DifferentAlbum', cover_art=False)
        # send new-metadata for all of the current changes
        self.metadata_manager.run_updates()
        # set up a signal handle to handle the next new-metadata signal
        signal_handler = mock.Mock()
        self.metadata_manager.connect("new-metadata", signal_handler)
        # Simulate mutagen getting cover art.  We should send new-metadata for
        # all items in the album
        self.check_run_mutagen('foo-4.mp3', 'audio', 200, 'Bar', 'AlbumOne',
                               cover_art=True)

        # make our metadata manager send the new-metadata signal and check the
        # result
        def check_new_metadata_for_album(album_name, *correct_paths):
            """Check that the new-metadata signal emits for all items in an
            album.

            :param album_name: name of the album
            :param correct_paths: paths for all items in the album
            """

            signal_handler.reset_mock()
            self.metadata_manager.run_updates()
            self.assertEquals(signal_handler.call_count, 1)
            args = signal_handler.call_args[0]
            self.assertEquals(args[0], self.metadata_manager)
            new_metadata = args[1]
            self.assertSameSet(new_metadata.keys(), correct_paths)
            correct_cover_art = self.cover_art_for_album(album_name)
            for key, value in new_metadata.items():
                self.assertEquals(value['cover_art'], correct_cover_art)
        check_new_metadata_for_album('AlbumOne',
            self.make_path('foo.mp3'),
            self.make_path('foo-2.mp3'),
            self.make_path('foo-4.mp3'),
        )
        # test that if we get more cover art for the same file, we don't
        # re-update the other items
        signal_handler.reset_mock()
        self.check_run_mutagen('foo-5.mp3', 'audio', 200, 'Bar', 'AlbumOne',
                               cover_art=True)
        self.metadata_manager.run_updates()
        self.assertEquals(signal_handler.call_count, 1)
        args = signal_handler.call_args[0]
        self.assertEquals(args[0], self.metadata_manager)
        new_metadata = args[1]
        self.assertSameSet(new_metadata.keys(), [
            self.make_path('foo-5.mp3'),
        ])

        # Test cover art from echonest
        signal_handler.reset_mock()
        self.check_run_echonest('foo.mp3', 'NewTitle', 'NewArtist',
                                'AlbumOne')
        check_new_metadata_for_album('AlbumOne',
            self.make_path('foo.mp3'),
            self.make_path('foo-2.mp3'),
            self.make_path('foo-4.mp3'),
            self.make_path('foo-5.mp3'),
        )

    def test_restart_incomplete(self):
        # test restarting incomplete 
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'video', 100, 'Foo')
        self.check_add_file('bar.avi')
        self.check_add_file('baz.mp3')
        self.check_run_mutagen('baz.mp3', 'audio', 100, None)
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
        self.metadata_manager = metadata.LibraryMetadataManager(self.tempdir,
                                                                self.tempdir)
        self.metadata_manager.restart_incomplete()
        self.check_queued_moviedata_calls(['foo.avi'])
        self.check_queued_mutagen_calls(['bar.avi'])
        self.check_queued_echonest_codegen_calls(['baz.mp3'])
        # Theck that when things finish, we get other incomplete metadata
        self.check_run_mutagen('bar.avi', 'audio', None, None)
        # None for both duration and title will cause bar.avi to go through
        # both movie data and the echonest codegen
        self.check_queued_moviedata_calls(['foo.avi', 'bar.avi'])
        self.check_run_movie_data('bar.avi', 'audio', 100, None)
        self.check_run_echonest_codegen('baz.mp3')
        self.check_run_echonest('baz.mp3', 'Foo')
        self.check_queued_echonest_codegen_calls(['bar.avi'])

    def test_restart_incomplete_restarts_http_errors(self):
        # test restarting incomplete 
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 100, 'Foo')
        self.check_echonest_error('foo.mp3', http_error=True)
        self.processor.reset()
        self.metadata_manager = metadata.LibraryMetadataManager(self.tempdir,
                                                                self.tempdir)
        self.metadata_manager.restart_incomplete()
        self.check_queued_echonest_calls(['foo.mp3'])

    @mock.patch('time.time')
    @mock.patch('miro.eventloop.add_timeout')
    def test_schedule_retry_net_lookup(self, mock_add_timeout, mock_time):
        # make time stand still for this test to make checking add_timeout
        # simpler
        mock_time.return_value = 1000.0

        caller = self.metadata_manager._retry_net_lookup_caller

        # the first time the user starts up miro, the check should be
        # scheduled in 10 minutes.
        self.metadata_manager.schedule_retry_net_lookup()
        mock_add_timeout.assert_called_once_with(
            600, caller.call_now, MatchAny(),
            args=(), kwargs={})
        # test calling it once the timeout fires.  The next time it should be
        # scheduled for 1 week later
        self.metadata_manager.retry_net_lookup()
        mock_add_timeout.reset_mock()
        self.metadata_manager.schedule_retry_net_lookup()
        mock_add_timeout.assert_called_once_with(
            60 * 60 * 24 * 7, caller.call_now, MatchAny(),
            args=(), kwargs={})

    def test_retry_net_lookup(self):
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'title', 'album')
        self.check_run_echonest('foo.mp3', 'title', 'Artist', None)
        self.allow_additional_echonest_query('foo.mp3')
        self.metadata_manager.retry_net_lookup()
        self.check_run_echonest('foo.mp3', 'title', 'Artist', 'Album')
        path = self.make_path('foo.mp3')
        query_metadata = self.processor.query_echonest_metadata[path]
        self.assertEquals(query_metadata['echonest_id'],
                          self.echonest_ids[path])

    def test_retry_net_lookup_no_echonest_id(self):
        # test calling retry_net_lookup for items without an echonest id
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'title', 'album')
        # this will simulates echonest not finding the album, so echonest_id
        # will not be set
        self.check_run_echonest('foo.mp3', None, None, None)
        self.allow_additional_echonest_query('foo.mp3')
        self.metadata_manager.retry_net_lookup()
        self.check_run_echonest('foo.mp3', 'title', 'Artist', 'Album')
        path = self.make_path('foo.mp3')
        query_metadata = self.processor.query_echonest_metadata[path]
        self.assert_('echonest_id' not in query_metadata)
        # now that the second run worked, we should have an echonest id
        status = metadata.MetadataStatus.get_by_path(path)
        self.assertNotEquals(status.echonest_id, None)

    def test_retry_net_lookup_errors(self):
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'title', 'album')
        self.check_run_echonest('foo.mp3', 'title', 'Artist', None)
        self.allow_additional_echonest_query('foo.mp3')
        self.metadata_manager.retry_net_lookup()
        self.check_echonest_error('foo.mp3')
        path = self.make_path('foo.mp3')
        query_metadata = self.processor.query_echonest_metadata[path]
        self.assertEquals(query_metadata['echonest_id'],
                          self.echonest_ids[path])
        # test that the progress counter is updated
        count_tracker = self.metadata_manager.count_tracker
        self.assertEquals(count_tracker.get_count_info(u'audio'),
                          (0, 0, 0))

    def test_retry_net_lookup_called_twice(self):
        # test if retry_net_lookup() is called a second time before the first
        # pass finishes.  This seems pretty unlikely to happen in real life,
        # but it's a good check for robustness anyways.
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'title', 'album')
        self.check_run_echonest('foo.mp3', 'title', 'Artist', None)
        self.allow_additional_echonest_query('foo.mp3')
        self.metadata_manager.retry_net_lookup()
        self.metadata_manager.retry_net_lookup()
        self.check_run_echonest('foo.mp3', 'title', 'Artist', 'Album')
        path = self.make_path('foo.mp3')
        query_metadata = self.processor.query_echonest_metadata[path]
        self.assertEquals(query_metadata['echonest_id'],
                          self.echonest_ids[path])

    def test_retry_net_lookup_checks_net_lookup_enabled(self):
        # test that retry_net_lookup() honors net_lookup_enabled being False
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'title', 'album')
        self.check_run_echonest('foo.mp3', 'title', 'Artist', None)
        self.check_set_net_lookup_enabled('foo.mp3', False)
        self.allow_additional_echonest_query('foo.mp3')
        self.metadata_manager.retry_net_lookup()
        self.check_echonest_not_running('foo.mp3')
        # test that the progress counter is not updated
        count_tracker = self.metadata_manager.count_tracker
        self.assertEquals(count_tracker.get_count_info(u'audio'),
                          (0, 0, 0))

    def test_retry_net_lookup_with_many_items(self):
        should_retry = []
        shouldnt_retry = []
        # make items missing album data
        for i in range(10):
            name = 'noalbum-song-%d.mp3' % i
            self.check_add_file(name)
            self.check_run_mutagen(name,
                                   'audio', 200, 'title', 'album')
            self.check_run_echonest(name,
                                    'title', 'better-artist-name', None)
            should_retry.append(name)
        # make items with album data
        for i in range(10):
            name = 'withalbum-song-%d.mp3' % i
            self.check_add_file(name)
            self.check_run_mutagen(name,
                                   'audio', 200, 'title', 'album')
            self.check_run_echonest(name,
                                    'title', 'better-artist-name',
                                    'better-album-title')
            shouldnt_retry.append(name)

        # check what happens when retry_net_lookup is called
        for name in should_retry:
            self.allow_additional_echonest_query(name)
        self.metadata_manager.retry_net_lookup()

        for name in shouldnt_retry:
            self.check_echonest_not_running(name)
        # make some of the retries succeed
        for i in range(5):
            name = should_retry.pop(0)
            self.check_run_echonest(name, 'title', 'better-artist-name',
                                    'better-album-title')
            shouldnt_retry.append(name)
        # make some of them fail
        for name in should_retry:
            self.check_run_echonest(name, 'title', 'better-artist-name', None)

        # check what happens when retry_net_lookup is called again
        for name in should_retry:
            self.allow_additional_echonest_query(name)
        self.metadata_manager.retry_net_lookup()
        for name in shouldnt_retry:
            self.check_echonest_not_running(name)
        # this time let all the album succeed
        for name in should_retry:
            self.check_run_echonest(name, 'title', 'better-artist-name',
                                    'better-album-title')

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
        self.metadata_manager = metadata.LibraryMetadataManager(self.tempdir,
                                                                self.tempdir)
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
            # Use None for title to force the files to go through the codegen
            self.check_run_mutagen(filename, 'audio', 100, None)

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
        with self.allow_warnings():
            self.processor.run_mutagen_errback(
                files_in_mutagen[0], ValueError())

    def test_restore(self):
        db_path = os.path.join(self.tempdir, 'testdb');
        self.reload_database(db_path)
        self.metadata_manager.db_info = app.db_info
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'Bar', 'Fights')
        self.check_movie_data_not_scheduled('foo.mp3')
        self.check_run_echonest('foo.mp3', 'Bar', 'Artist', 'Fights')
        # reload our database to force restoring metadata items
        self.reload_database(db_path)
        self.metadata_manager.db_info = app.db_info
        self.check_metadata('foo.mp3')

    def test_set_user_info(self):
        self.check_add_file('foo.avi')
        self.check_set_user_info('foo.avi', title=u'New Foo',
                                 album=u'First Name')
        self.check_set_user_info('foo.avi', title=u'New Foo',
                                 album=u'Second Name')

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
                    # Don't send title to force items to go through the
                    # echonest codegen
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
        with self.allow_warnings():
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

class EchonestNetErrorTest(EventLoopTest):
    # Test our pause/retry logic when we get HTTP errors from echonest

    def setUp(self):
        EventLoopTest.setUp(self)
        self.processor = MockMetadataProcessor()
        self.patch_function('miro.echonest.query_echonest',
                            self.processor.query_echonest)

    @mock.patch('miro.eventloop.add_timeout')
    def test_pause_on_http_errors(self, mock_add_timeout):
        _echonest_processor = metadata._EchonestProcessor(1, self.tempdir)
        paths = [PlatformFilenameType('/videos/item-%s.mp3' % i)
                 for i in xrange(100)]
        error_count = _echonest_processor.PAUSE_AFTER_HTTP_ERROR_COUNT
        timeout = _echonest_processor.PAUSE_AFTER_HTTP_ERROR_TIMEOUT
        for i, path in enumerate(paths):
            # give enough initial metadata so that we skip the codegen step
            fetcher = lambda: { u'title': "Song-%i" % i }
            _echonest_processor.add_path(path, fetcher)
        path_iter = iter(paths)

        for i in xrange(error_count):
            http_error = httpclient.UnknownHostError('fake.echonest.host')
            with self.allow_warnings():
                _echonest_processor._echonest_errback(path_iter.next(),
                                                      http_error)
        # after we get enough error, we should stop querying echonest
        self.assertEquals(_echonest_processor._querying_echonest, False)
        # we should also set a timeout to re-run the queue once enough time
        # has passed
        mock_add_timeout.assert_called_once_with(
            timeout, _echonest_processor._restart_after_http_errors,
            MatchAny())
        # simulate time passing then run _restart_after_http_errors().  We
        # should schedule a new echonest call
        for i in xrange(len(_echonest_processor._http_error_times)):
            _echonest_processor._http_error_times[i] -= timeout
        mock_add_timeout.reset_mock()
        _echonest_processor._restart_after_http_errors()
        self.assertEquals(_echonest_processor._querying_echonest, True)
        # test that if this call is sucessfull, we keep going
        _echonest_processor._echonest_callback(path_iter.next(),
                                               {'album': u'Album'})
        self.assertEquals(_echonest_processor._querying_echonest, True)
        # test that if we get enough errors, we halt again
        for i in xrange(error_count):
            http_error = httpclient.UnknownHostError('fake.echonest.host')
            with self.allow_warnings():
                _echonest_processor._echonest_errback(path_iter.next(),
                                                      http_error)
        self.assertEquals(_echonest_processor._querying_echonest, False)
        mock_add_timeout.assert_called_once_with(
            timeout, _echonest_processor._restart_after_http_errors,
            MatchAny())

class DeviceMetadataTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        messages.FrontendMessage.handler = mock.Mock()
        # setup a device database
        device_db = devices.DeviceDatabase()
        device_db[u'audio'] = {}
        device_db[u'video'] = {}
        device_db[u'other'] = {}
        # setup a device object
        device_info = mock.Mock()
        device_info.name = 'DeviceName'
        mount = self.tempdir + "/"
        device_id = 123
        os.makedirs(os.path.join(mount, '.miro'))
        self.cover_art_dir = os.path.join(self.tempdir, 'cover-art')
        os.makedirs(self.cover_art_dir)
        sqlite_db = devices.load_sqlite_database(':memory:', 1024)
        db_info = database.DBInfo(sqlite_db)
        metadata_manager = devices.make_metadata_manager(
            self.tempdir, db_info, device_id)
        self.device = messages.DeviceInfo(device_id, device_info, mount,
                                          device_info, db_info,
                                          metadata_manager, 1000, 0, False)
        # copy a file to our device
        src = resources.path('testdata/Wikipedia_Song_by_teddy.ogg')
        dest = os.path.join(self.tempdir, 'test-song.ogg')
        shutil.copyfile(src, dest)
        self.mutagen_metadata = {
            'file_type': u'audio',
            'title': u'Title',
            'album': u'Album',
            'artist': u'Artist',
        }
        self.moviedata_metadata = { 'duration': 100 }
        # make a device manager
        app.device_manager = mock.Mock()
        app.device_manager.connected = {self.device.id: self.device}
        app.device_manager._is_hidden.return_value = False
        # Set NET_LOOKUP_BY_DEFAULT to True.  We should ignore it for device
        # items and always set net_lookup_enabled to False.
        app.config.set(prefs.NET_LOOKUP_BY_DEFAULT, True)

    def tearDown(self):
        app.device_manager = None
        EventLoopTest.tearDown(self)

    def make_device_item(self):
        return item.DeviceItem(self.device,
                               unicode_to_filename(u'test-song.ogg'))

    def run_processors(self):
        self._run_processors(self.device.metadata_manager,
                             os.path.join(self.tempdir, 'test-song.ogg'))

    def run_processors_for_file_item(self, item):
        self._run_processors(app.local_metadata_manager,
                             item.get_filename())

    def _run_processors(self, metadata_manager, path):
        metadata_manager.mutagen_processor.emit("task-complete", path,
                                                self.mutagen_metadata)
        metadata_manager.run_updates()
        metadata_manager.moviedata_processor.emit("task-complete", path,
                                                 self.moviedata_metadata)
        metadata_manager.run_updates()

    def get_metadata_for_item(self):
        return self.device.metadata_manager.get_metadata('test-song.ogg')

    def test_new_item(self):
        # Test that we create metadata entries for new DeviceItems.
        device_item = self.make_device_item()
        self.assertDictEquals(self.get_metadata_for_item(), {
            u'file_type': u'audio',
            u'net_lookup_enabled': False,
            u'has_drm': False,
        })
        self.assertEquals(device_item.file_type, u'audio')
        self.assertEquals(device_item.net_lookup_enabled, False)

    def test_update(self):
        # Test that we update DeviceItems as we get metadata
        self.make_device_item()
        self.run_processors()
        # check data in MetadataManager
        self.assertDictEquals(self.get_metadata_for_item(), {
            'file_type': u'audio',
            'title': u'Title',
            'album': u'Album',
            'duration': 100,
            'artist': 'Artist',
            'has_drm': False,
            'net_lookup_enabled': False,
        })
        # check data in the DeviceItem
        device_item = item.DeviceItem.get_by_path(
            unicode_to_filename(u'test-song.ogg'), self.device.db_info)
        self.assertEquals(device_item.title, u'Title')
        self.assertEquals(device_item.artist, u'Artist')
        self.assertEquals(device_item.album, u'Album')

    def test_image_paths(self):
        # Test that screenshot and cover_art are relative to the
        # device
        screenshot = os.path.join(self.device.mount, '.miro',
                                       'icon-cache', 'extracted',
                                       'screenshot.png')
        cover_art = os.path.join(self.device.mount, '.miro', 'cover-art',
                                      unicode_to_filename(u'Album'))
        self.moviedata_metadata['screenshot'] = screenshot
        for path in (screenshot, cover_art):
            if not os.path.exists(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))
            open(path, 'w').write("FAKE DATA")

        self.make_device_item()
        self.run_processors()
        item_metadata = self.get_metadata_for_item()
        self.assertEquals(item_metadata['screenshot'],
                          os.path.relpath(screenshot, self.device.mount))
        self.assertEquals(item_metadata['cover_art'],
                          os.path.relpath(cover_art, self.device.mount))

    def test_remove(self):
        # Test that we remove metadata entries for removed DeviceItems.
        device_item = self.make_device_item()
        self.run_processors()
        device_item.remove(self.device)
        self.assertRaises(KeyError, self.get_metadata_for_item)

    def test_restart_incomplete(self):
        # test that when we create our metadata manager it restarts the
        # pending metadata
        self.make_device_item()
        mock_send = mock.Mock()
        patcher = mock.patch('miro.workerprocess.send', mock_send)
        with patcher:
            self.device.metadata_manager = devices.make_metadata_manager(
                self.tempdir, self.device.db_info, self.device.id)
        self.assertEquals(mock_send.call_count, 1)
        task = mock_send.call_args[0][0]
        self.assertEquals(task.source_path,
                          os.path.join(self.tempdir, 'test-song.ogg'))

    @mock.patch('miro.fileutil.migrate_file')
    def test_copy(self, mock_migrate_file):
        # Test copying/converting existing files into the device
        source_path = resources.path('testdata/Wikipedia_Song_by_teddy.ogg')
        feed = models.Feed(u'dtv:manualFeed')
        item = models.FileItem(source_path, feed.id)
        self.run_processors_for_file_item(item)
        item_metadata = app.local_metadata_manager.get_metadata(
            item.get_filename())
        source_info = self.make_item_info(item)
        copy_path = os.path.join(self.tempdir, 'copied-file-dest.ogg')

        shutil.copyfile(source_path, copy_path)
        dsm = devices.DeviceSyncManager(self.device)
        dsm._add_item(copy_path, source_info)
        self.runPendingIdles()
        self.assertEquals(mock_migrate_file.call_count, 1)
        current_path, final_path, callback = mock_migrate_file.call_args[0]
        shutil.copyfile(current_path, final_path)
        copied_item_path = os.path.relpath(final_path, self.device.mount)
        callback()
        # we shouldn't have any metadata processing scheduled for the device
        device_db_info = self.device.metadata_manager.db_info
        status = metadata.MetadataStatus.get_by_path(copied_item_path,
                                                     device_db_info)
        self.assertEquals(status.current_processor, None)
        self.assertEquals(status.mutagen_status, status.STATUS_COMPLETE)
        self.assertEquals(status.moviedata_status, status.STATUS_COMPLETE)
        self.assertEquals(status.echonest_status, status.STATUS_SKIP)
        # test that we made MetadataEntry rows
        for source in (u'mutagen', u'movie-data'):
            # this will raise an exception if the entry is not there
            metadata.MetadataEntry.get_entry(source, status,
                                             device_db_info)
        # the device item should have the original items metadata, except
        # we shouldn't copy net_lookup_enabled
        device_item_metadata = self.device.metadata_manager.get_metadata(
            copied_item_path)
        self.assertEquals(item_metadata['net_lookup_enabled'], True)
        self.assertEquals(device_item_metadata['net_lookup_enabled'], False)
        del item_metadata['net_lookup_enabled']
        del device_item_metadata['net_lookup_enabled']
        self.assertDictEquals(device_item_metadata, item_metadata)

class TestCodegen(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.callback_data = self.errback_data = None
        self.codegen_info = get_enmfp_executable_info()

    def callback(self, *args):
        self.callback_data = args
        self.stopEventLoop(abnormal=False)

    def errback(self, *args):
        self.errback_data = args
        self.stopEventLoop(abnormal=False)

    def run_codegen(self, song_path):
        echonest.exec_codegen(self.codegen_info, song_path,
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
        self.setup_query_metadata_for_rock_music()
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
        self.thriller_release_id = 282494
        echonest._EchonestQuery.seven_digital_cache = {}

    def callback(self, *args):
        self.callback_data = args

    def errback(self, *args):
        self.errback_data = args

    def setup_query_metadata_for_billie_jean(self):
        self.query_metadata = {
            "artist": "Michael jackson",
            "album": "Thriller",
            "title": "Billie jean",
            "duration": 168400,
        }

    def setup_query_metadata_for_rock_music(self):
        self.query_metadata = {
            "artist": "Pixies",
            "album": "Bossanova",
            "title": "Rock Music",
            "duration": 168400,
        }

    def setup_query_metadata_for_break_like_the_wind(self):
        self.query_metadata = {
            "artist": u'Sp\u0131n\u0308al Tap',
            "album": "Break Like The Wind",
            "title": "Break Like The Wind",
            "duration": 168400,
        }

    def start_query_with_tags(self):
        """Send ID3 tags echonest.query_echonest()."""
        # This tracks the metadata we expect to see back from query_echonest()
        self.reply_metadata = {}
        echonest.query_echonest(self.path, self.album_art_dir,
                                None, 3.15, self.query_metadata,
                                self.callback, self.errback)

    def start_query_with_echonest_id(self):
        """Send an echonest id to echonest.query_echonest()."""
        # This tracks the metadata we expect to see back from query_echonest()
        self.query_metadata['echonest_id'] = 'abcdef'
        self.reply_metadata = {}
        echonest.query_echonest(self.path, self.album_art_dir,
                                None, 3.15, self.query_metadata,
                                self.callback, self.errback)

    def start_query_with_code(self):
        """Send a generated code to echonest.query_echonest()."""
        # This tracks the metadata we expect to see back from query_echonest()
        self.reply_metadata = {}
        # we only call echonest codegen if we don't have a lot of metadata
        del self.query_metadata['title']
        del self.query_metadata['album']
        echonest.query_echonest(self.path, self.album_art_dir,
                                self.echonest_code, 3.15, self.query_metadata,
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

    def check_grab_url_multiple(self, calls_to_check):
        """Check that grab_url was called with multiple urls

        :param calls_to_check: list of (url, query) tuples to check.  The order
        doesn't matter.
        """

        def query_to_set(query_dict):
            """Make a frozenset that represets a query dict.

            This allows us to have something hashable, which is needed for
            assertSameSet.
            """
            return frozenset((key, tuple(values))
                             for key, values in query.iteritems())

        grabbed_urls_parsed = []
        for args, kwargs in mock_grab_url.call_args_list:
            grabbed_url = urlparse.urlparse(args[0])
            query = urlparse.parse_qs(grabbed_url.query)
            grabbed_urls_parsed.append((grabbed_url.scheme,
                                        grabbed_url.netloc,
                                        grabbed_url.path,
                                        grabbed_url.fragment,
                                        query_to_set(query)))
        calls_to_check_parsed = []
        for url, query in calls_to_check:
            parsed_url = urlparse.urlparse(url)
            calls_to_check_parsed.append((parsed_url.scheme,
                                        parsed_url.netloc,
                                        parsed_url.path,
                                        parsed_url.fragment,
                                        query_to_set(query)))
        self.assertSameSet(grabbed_urls_parsed, calls_to_check_parsed)

    def check_echonest_grab_url_call(self):
        search_url = 'http://echonest.pculture.org/api/v4/song/search'
        query_dict = {
            'api_key': [echonest.ECHO_NEST_API_KEY],
            # NOTE: either order of the bucket params is okay
            'bucket': ['tracks', 'id:7digital'],
            'results': ['1'],
            'sort': ['song_hotttnesss-desc'],
            'artist': [self.query_metadata['artist'].encode('utf-8')],
            'title': [self.query_metadata['title'].encode('utf-8')],
        }
        self.check_grab_url(search_url, query_dict)

    def check_echonest_grab_url_call_with_code(self):
        """Check the url sent to grab_url to perform our echonest query."""
        identify_url = 'http://echonest.pculture.org/api/v4/song/identify'
        post_vars = {
            'api_key': echonest.ECHO_NEST_API_KEY,
            # NOTE: either order of the bucket params is okay
            'bucket': ['tracks', 'id:7digital'],
            'query': {
                'code': self.echonest_code,
                'metadata': {
                    'version': 3.15,
                    'artist': self.query_metadata['artist'].encode('utf-8'),
                    'duration': self.query_metadata['duration'] // 1000,
                },
            },
        }
        self.check_grab_url(identify_url, post_vars=post_vars)

    def check_echonest_grab_url_call_with_echonest_id(self):
        """Check the url sent to grab_url to perform our echonest query."""

        profile_url = 'http://echonest.pculture.org/api/v4/song/profile'
        query_dict = {
            'api_key': [echonest.ECHO_NEST_API_KEY],
            # NOTE: either order of the bucket params is okay
            'bucket': ['tracks', 'id:7digital'],
            'id': [self.query_metadata['echonest_id']],
        }
        self.check_grab_url(profile_url, query_dict)

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
        elif response_file == 'break-like-the-wind':
            self.reply_metadata['artist'] = u'Sp\u0131n\u0308al Tap'
            self.reply_metadata['title'] = 'Break Like The Wind'
            self.reply_metadata['echonest_id'] = 'SOBKZUR12B0B80C2C1'

    def check_7digital_grab_url_calls(self, release_ids):
        """Check the url sent to grab_url to perform our 7digital query."""
        calls_to_check = []
        seven_digital_url = 'http://7digital.pculture.org/1.2/release/details'
        for releaseid in release_ids:
            calls_to_check.append((seven_digital_url, {
                'oauth_consumer_key': [echonest.SEVEN_DIGITAL_API_KEY],
                'imageSize': ['350'],
                'releaseid': [str(releaseid)],
            }))
        self.check_grab_url_multiple(calls_to_check)

    def send_7digital_reply(self, response_file, call_index=0,
                            reset_mock=True, best_reply=True):
        """Send a reply back from 7digital.

        :param response_file: which file to use for response data
        :param call_index: if we called grab_url multiple times, use this to
        pick which callback to send
        :param reset_mock: should we reset mock_grab_url?
        :param best_reply: is this the reply that we should choose?
        """
        response_path = resources.path('testdata/7digital-replies/%s' %
                                       response_file)
        response_data = open(response_path).read()
        callback = mock_grab_url.call_args_list[call_index][0][1]
        if reset_mock:
            mock_grab_url.reset_mock()
        callback({'body': response_data})
        if not best_reply:
            return
        if response_file == self.bossanova_release_id:
            self.reply_metadata['album'] = 'Bossanova'
            self.reply_metadata['cover_art'] = os.path.join(
                self.album_art_dir, 'Bossanova')
            self.reply_metadata['created_cover_art'] = True
            self.reply_metadata['album_artist'] = 'Pixies'
            self.album_art_url = (
                'http://cdn.7static.com/static/img/sleeveart/'
                '00/001/898/0000189844_350.jpg')
        elif response_file == self.thriller_release_id:
            # NOTE: there are multiple thriller relaseses.  We just pick one
            # arbitrarily
            self.reply_metadata['album'] = 'Thriller'
            self.reply_metadata['album_artist'] = 'Michael Jackson'
            self.reply_metadata['cover_art'] = os.path.join(
                self.album_art_dir, 'Thriller')
            self.reply_metadata['created_cover_art'] = True
            self.album_art_url = (
                'http://cdn.7static.com/static/img/sleeveart/'
                '00/002/840/0000284075_350.jpg')

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

    def send_http_error(self, call_index=0, reset_mock=False):
        errback = mock_grab_url.call_args_list[call_index][0][2]
        if reset_mock:
            mock_grab_url.reset_mock()
        error = httpclient.UnexpectedStatusCode(404)
        with self.allow_warnings():
            errback(error)

    def test_query_with_tags(self):
        # test normal operations
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_calls([self.bossanova_release_id])
        self.send_7digital_reply(self.bossanova_release_id)
        self.check_album_art_grab_url_call()
        self.send_album_art_reply()
        self.check_callback()

    def test_query_with_code(self):
        # test normal operations
        self.start_query_with_code()
        self.check_echonest_grab_url_call_with_code()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_calls([self.bossanova_release_id])
        self.send_7digital_reply(self.bossanova_release_id)
        self.check_album_art_grab_url_call()
        self.send_album_art_reply()
        self.check_callback()

    def test_query_with_echonest_id(self):
        # test queries where we already have an echonest id
        self.start_query_with_echonest_id()
        self.check_echonest_grab_url_call_with_echonest_id()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_calls([self.bossanova_release_id])
        self.send_7digital_reply(self.bossanova_release_id)
        self.check_album_art_grab_url_call()
        self.send_album_art_reply()
        self.check_callback()

    def test_album_art_error(self):
        # test normal operations
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_calls([self.bossanova_release_id])
        self.send_7digital_reply(self.bossanova_release_id)
        self.check_album_art_grab_url_call()
        self.send_http_error()
        # we shouldn't have cover_art in the reply, since the request
        # failed
        del self.reply_metadata['cover_art']
        del self.reply_metadata['created_cover_art']
        self.check_callback()

    def test_not_found(self):
        # test echonest not finding our song
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        with self.allow_warnings():
            self.send_echonest_reply('no-match')
        self.check_callback()

    def test_echonest_http_error(self):
        # test http errors with echonest
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        self.send_http_error()
        mock_grab_url.reset_mock()
        self.check_grab_url_not_called()
        self.check_errback()

    def test_no_releases(self):
        # test no releases for a song
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        with self.allow_warnings():
            self.send_echonest_reply('no-releases')
        self.check_grab_url_not_called()
        self.check_callback()

    def test_7digital_http_error(self):
        # test http errors with 7digital
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_calls([self.bossanova_release_id])
        self.send_http_error()
        self.check_callback()

    def test_7digital_no_match(self):
        # test 7digital not matching our release id
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_calls([self.bossanova_release_id])
        with self.allow_warnings():
            self.send_7digital_reply('no-matches')
        self.check_callback()

    def test_7digital_invalid_xml(self):
        # test 7digital sending back invalid XML
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_calls([self.bossanova_release_id])
        with self.allow_warnings():
            self.send_7digital_reply('invalid-xml')
        self.check_callback()

    def test_multiple_releases(self):
        # test multiple 7digital releases
        self.setup_query_metadata_for_billie_jean()
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('billie-jean')
        release_ids = [ 518377, 280410, 307167, 289401, 282494, 282073,
                       624250, 312343, 391641, 341656, 284075, 280538, 283379,
                       312343, 669160, 391639,
                      ]
        replys_with_errors = set([283379, 307167, 312343, 391641, 518377, ])

        self.check_7digital_grab_url_calls(release_ids)

        # send replies
        for i, release_id in enumerate(release_ids):
            # For the last reply, send an HTTP error.  We should just skip
            # over this and use the rest of the replies.
            # Also, reset our mock_grab_url call to get ready for the album
            # art grab_url calls
            if i == len(release_ids) - 1:
                self.send_http_error(i, reset_mock=True)
                continue
            if release_id == self.thriller_release_id:
                best_reply = True
            else:
                best_reply = False
            if release_id in replys_with_errors:
                self.log_filter.set_exception_level(logging.CRITICAL)
            self.send_7digital_reply(release_id, i, reset_mock=False,
                                     best_reply=best_reply)
            # reset log filter
            self.log_filter.set_exception_level(logging.WARNING)

        self.check_album_art_grab_url_call()
        self.send_album_art_reply()
        self.check_callback()

    def test_multiple_releases_error(self):
        # test multiple 7digital releases and all of them resulting in an HTTP
        # error
        self.setup_query_metadata_for_billie_jean()
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('billie-jean')
        release_ids = [ 518377, 280410, 307167, 289401, 282494, 282073,
                       624250, 312343, 391641, 341656, 284075, 280538, 283379,
                       312343, 669160, 391639,
                      ]
        # send HTTP errors for all results
        for i in xrange(len(release_ids) - 1):
            self.send_http_error(i, reset_mock=False)
        self.send_http_error(len(release_ids)-1, reset_mock=True)
        # we should still get our callback with echonest data
        self.check_callback()

    def test_multiple_releases_no_album_name(self):
        # test multiple 7digital releases and when we don't have a album name
        self.setup_query_metadata_for_billie_jean()
        del  self.query_metadata['album']
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        with self.allow_warnings():
            self.send_echonest_reply('billie-jean')
        # since there's no good way to pick from multiple releases, we should
        # skipn the 7digital step
        self.check_callback()

    def test_7digital_caching(self):
        # test that we cache 7digital results
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_calls([self.bossanova_release_id])
        self.send_7digital_reply(self.bossanova_release_id)
        self.check_album_art_grab_url_call()
        self.send_album_art_reply()
        self.check_callback()
        old_metadata = self.reply_metadata
        # start a new query that results in the same release id.
        self.echonest_code = 'fake-code-2'
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        # we shouldn't call grab_URL
        self.check_grab_url_not_called()
        self.reply_metadata = old_metadata
        del self.reply_metadata['created_cover_art']
        self.check_callback()

    def test_avoid_redownloading_album_art(self):
        # test that we don't download album art that we already have
        album_art_path = os.path.join(self.album_art_dir, 'Bossanova')
        open(album_art_path, 'w').write('FAKE DATA')
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        self.send_echonest_reply('rock-music')
        self.check_7digital_grab_url_calls([self.bossanova_release_id])
        self.send_7digital_reply(self.bossanova_release_id)
        # we shouldn't try to download the album art, since that file is
        # already there
        self.check_grab_url_not_called()
        del self.reply_metadata['created_cover_art']
        self.check_callback()

    def test_query_encoding(self):
        # test that we send parameters as unicode to echonest/7digital
        self.query_metadata['artist'] = u'Pixi\u00e9s jackson'
        self.query_metadata['album'] = u'Bossan\u00f6va'
        self.query_metadata['title'] = u"Rock Mus\u0129c"
        self.test_query_with_tags()

    def test_reply_encoding(self):
        # test that we handle extended unicode chars from echonest
        self.setup_query_metadata_for_break_like_the_wind()
        self.start_query_with_tags()
        self.check_echonest_grab_url_call()
        with self.allow_warnings():
            self.send_echonest_reply('break-like-the-wind')
        # break like the wind contains no tracks, so we don't need to deal
        # with the 7digital stuff.  Just check that we properly parsed the
        # echonest query
        self.check_callback()

class ProgressUpdateTest(MiroTestCase):
    # Test the objects used to send the MetadataProgressUpdate messages
    def test_count_tracker(self):
        # test the ProgressCountTracker
        counter = metadata.ProgressCountTracker()
        # test as the total goes up
        files = ["foo.avi", "bar.avi", "baz.avi"]
        files = [PlatformFilenameType(f) for f in files]
        for i, f in enumerate(files):
            counter.file_started(f, {})
            self.assertEquals(counter.get_count_info(), (i+1, 0, 0))
        # test as files finish moviedata/mutagen and move to echonest
        for i, f in enumerate(files):
            counter.file_finished_local_processing(f)
            self.assertEquals(counter.get_count_info(), (3, i+1, 0))
        # test as files finish echonest
        for i, f in enumerate(files):
            counter.file_finished(f)
            if i < 2:
                self.assertEquals(counter.get_count_info(), (3, 3, i+1))
            else:
                # all files completely done.  We should reset the counts
                self.assertEquals(counter.get_count_info(), (0, 0, 0))

    def test_count_tracker_no_net_lookup(self):
        # test the ProgressCountTracker when files skip the net lookup stage

        counter = metadata.ProgressCountTracker()
        # test as the total goes up
        files = ["foo.avi", "bar.avi", "baz.avi"]
        files = [PlatformFilenameType(f) for f in files]
        for i, f in enumerate(files):
            counter.file_started(f, {})
            self.assertEquals(counter.get_count_info(), (i+1, 0, 0))
        # test as files finish processing
        for i, f in enumerate(files):
            counter.file_finished(f)
            if i < 2:
                self.assertEquals(counter.get_count_info(), (3, i+1, i+1))
            else:
                # all files completely done.  We should reset the counts
                self.assertEquals(counter.get_count_info(), (0, 0, 0))

    def test_count_tracker_file_moved(self):
        # test the ProgressCountTracker after a file move

        counter = metadata.ProgressCountTracker()
        # add some files
        for i in xrange(10):
            f = PlatformFilenameType("file-%s.avi" % i)
            counter.file_started(f, {})
            self.assertEquals(counter.get_count_info(), (i+1, 0, 0))
        # check calling file_updated.  It should be a no-op
        for i in xrange(10):
            f = PlatformFilenameType("file-%s.avi" % i)
            counter.file_updated(f, {
                'duration': 10,
                'file_type': u'audio',
                'title': u'Title',
            })

        # move some of those files
        for i in xrange(5, 10):
            old = PlatformFilenameType("file-%s.avi" % i)
            new = PlatformFilenameType("new-file-%s.avi" % i)
            counter.file_moved(old, new)
        # check as the files finished
        for i in xrange(0, 10):
            if i < 5:
                f = PlatformFilenameType("file-%s.avi" % i)
            else:
                f = PlatformFilenameType("new-file-%s.avi" % i)
            counter.file_finished(f)
            if i < 9:
                self.assertEquals(counter.get_count_info(), (10, i+1, i+1))
            else:
                self.assertEquals(counter.get_count_info(), (0, 0, 0))

    def test_library_count_tracker(self):
        # test the LibraryProgressCountTracker
        counter = metadata.LibraryProgressCountTracker()
        # add a couple files that we will never finish.  These will keep it so
        # the counts don't get reset
        counter.file_started(PlatformFilenameType("sentinal.avi"),
                             {'file_type': u"video"})
        counter.file_started(PlatformFilenameType("sentinal.mp3"),
                             {'file_type': u"audio"})
        # add a file whose filetype changes as it runs through the processors
        self.assertEquals(counter.get_count_info('video'), (1, 0, 0))
        self.assertEquals(counter.get_count_info('audio'), (1, 0, 0))

        foo = PlatformFilenameType("foo.mp3")

        counter.file_started(foo, {'file_type': u"audio"})
        self.assertEquals(counter.get_count_info('video'), (1, 0, 0))
        self.assertEquals(counter.get_count_info('audio'), (2, 0, 0))

        counter.file_updated(foo, {'file_type': u"video"})
        self.assertEquals(counter.get_count_info('video'), (2, 0, 0))
        self.assertEquals(counter.get_count_info('audio'), (1, 0, 0))

        # change the name, this shouldn't affect the counts at all
        bar = PlatformFilenameType("bar.mp3")
        counter.file_moved(foo, bar)
        self.assertEquals(counter.get_count_info('video'), (2, 0, 0))
        self.assertEquals(counter.get_count_info('audio'), (1, 0, 0))

        # check calling file_updated after file_moved
        counter.file_updated(bar, {'file_type': u"audio"})
        self.assertEquals(counter.get_count_info('video'), (1, 0, 0))
        self.assertEquals(counter.get_count_info('audio'), (2, 0, 0))

        # check finishing the file after all of the changes
        counter.file_finished(bar)
        self.assertEquals(counter.get_count_info('video'), (1, 0, 0))
        self.assertEquals(counter.get_count_info('audio'), (2, 1, 1))

        # check file_updated for the last item
        counter.file_updated(PlatformFilenameType("sentinal.avi"),
                             {'file_type': u"audio"})
        self.assertEquals(counter.get_count_info('video'), (0, 0, 0))
        self.assertEquals(counter.get_count_info('audio'), (3, 1, 1))
