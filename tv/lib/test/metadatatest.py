import collections
import itertools
import os

from miro.test import mock
from miro.test.framework import MiroTestCase
from miro import app
from miro import databaseupgrade
from miro import schema
from miro import filetypes
from miro import metadata
from miro import workerprocess
from miro.plat import resources
from miro.plat.utils import PlatformFilenameType

class TestSource(metadata.Source):
    pass

class TestStore(metadata.Store):
    def confirm_db_thread(self): pass
    def signal_change(self): pass
    # doesn't need a get_filename() because no coverart file will be written

class Metadata(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)

    def test_iteminfo_round_trip(self):
        """Test that properties changed by ItemInfo name affect the right
        attributes. Test will also fail with errors if setup_new doesn't
        initialize all the properties that are used by ItemInfo.
        """
        source = TestSource()
        source.setup_new()
        info = source.get_iteminfo_metadata()

        store = TestStore()
        store.setup_new()
        store.set_metadata_from_iteminfo(info)

        original_dict = info
        after_round_trip = store.get_iteminfo_metadata()

        if hasattr(self, 'assertDictEqual'):
            # python2.7 includes helpful details
            self.assertDictEqual(original_dict, after_round_trip)
        else:
            original_items = sorted(original_dict.items())
            round_trip_items = sorted(after_round_trip.items())
            self.assertEqual(original_items, round_trip_items)

class MockMetadataProcessor(object):
    """Replaces the mutagen and movie data code with test values."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.mutagen_calls = {}
        self.movie_data_calls = {}
        self.canceled_files = set()

    def send(self, task, callback, errback):
        task_data = (task, callback, errback)

        if isinstance(task, workerprocess.MutagenTask):
            if task.source_path in self.mutagen_calls:
                raise ValueError("Already processing %s" % task.source_path)
            self.mutagen_calls[task.source_path] = task_data
        elif isinstance(task, workerprocess.MovieDataProgramTask):
            if task.source_path in self.movie_data_calls:
                raise ValueError("Already processing %s" % task.source_path)
            self.movie_data_calls[task.source_path] = task_data
        elif isinstance(task, workerprocess.CancelFileOperations):
            self.canceled_files.update(task.paths)
        else:
            raise TypeError(task)

    def run_mutagen_callback(self, source_path, file_type, duration, title,
                             drm):
        task, callback, errback = self.mutagen_calls.pop(source_path)
        data = {
            'source_path': task.source_path,
            'file_type': unicode(file_type),
            'duration': duration,
            'title': unicode(title) if title is not None else None,
            'drm': drm,
            'cover_art_path': None,
        }
        # Real mutagen calls send much more than the title for metadata, but
        # this is enough to test
        if file_type == 'audio':
            data['cover_art_path'] = self._cover_art_path(task.source_path)
        callback(task, data)

    def _cover_art_path(self, media_path):
        return '/tmp/' + os.path.basename(media_path) + '.png'

    def run_mutagen_errback(self, source_path, error):
        task, callback, errback = self.mutagen_calls.pop(source_path)
        errback(task, error)

    def run_movie_data_callback(self, source_path, file_type, duration,
                                screenshot_worked):
        try:
            task, callback, errback = self.movie_data_calls.pop(source_path)
        except KeyError:
            raise ValueError("No movie data run scheduled for %s" %
                             source_path)
        data = {
            'source_path': task.source_path,
            'file_type': unicode(file_type),
            'duration': duration,
            'screenshot_path': None,
        }
        if screenshot_worked:
            screenshot_path = self.get_screenshot_path(task.source_path)
            data['screenshot_path'] = screenshot_path
        callback(task, data)

    def run_movie_data_errback(self, source_path, error):
        task, callback, errback = self.movie_data_calls.pop(source_path)
        errback(task, error)

    def get_screenshot_path(self, source_path):
        filename = os.path.basename(source_path) + ".png"
        return '/tmp/' + filename

class MetadataManagerTest(MiroTestCase):
    # Test the MetadataManager class
    def setUp(self):
        MiroTestCase.setUp(self)
        self.mutagen_data = collections.defaultdict(dict)
        self.movieprogram_data = collections.defaultdict(dict)
        self.user_info_data = collections.defaultdict(dict)
        self.processor = MockMetadataProcessor()
        self.patch_function('miro.workerprocess.send', self.processor.send)
        self.metadata_manager = metadata.MetadataManager()

    def reload_database(self, path=':memory:', schema_version=None,
                        object_schemas=None, upgrade=True):
        if object_schemas is None:
            # add schemas for the metadata system.  These are not in the
            # regular DB schema because we haven't written database upgrades
            # for them.
            object_schemas = schema.object_schemas + [
                schema.MetadataStatusSchema, schema.MetadataEntrySchema,
            ]
        MiroTestCase.reload_database(self, path, schema_version,
                                     object_schemas, upgrade)

    def _calc_correct_metadata(self, path):
        """Calculate what the metadata should be for a path."""
        metadata = {
            'file_type': filetypes.item_file_type_for_filename(path),
        }
        metadata.update(self.mutagen_data[path])
        metadata.update(self.movieprogram_data[path])
        metadata.update(self.user_info_data[path])
        # Handle fallback columns
        if 'show' not in metadata and 'artist' in metadata:
            metadata['show'] = metadata['artist']
        if 'episode_id' not in metadata and 'title' in metadata:
            metadata['episode_id'] = metadata['title']
        return metadata

    def check_metadata(self, path):
        correct_metadata = self._calc_correct_metadata(path)
        metadata = self.metadata_manager.get_metadata(path)
        # don't check has_drm, we have a special test for that
        for dct in (metadata, correct_metadata):
            for key in ('has_drm', 'drm'):
                if key in dct:
                    del dct[key]
        self.assertDictEquals(metadata, correct_metadata)

    def check_add_file(self, filename):
        path = '/videos/' + filename
        # before we add the path, get_metadata() should raise a KeyError
        self.assertRaises(KeyError, self.metadata_manager.get_metadata, path)
        # after we add the path, we should have only have metadata that we can
        # guess from the file
        self.metadata_manager.add_file(path)
        self.check_metadata(path)
        # after we add the path, calling add file again should raise a
        # ValueError
        self.assertRaises(ValueError, self.metadata_manager.add_file, path)

    def check_run_mutagen(self, filename, file_type, duration, title,
                          drm=False):
        path = '/videos/' + filename
        if not filename.startswith('/'):
            path = '/videos/' + filename
        else:
            path = filename
        mutagen_data = {
            'file_type': file_type,
            'duration': duration,
            'title': title,
            'drm': drm,
        }
        # Remove None keys
        for k in mutagen_data.keys():
            if mutagen_data[k] is None:
                del mutagen_data[k]
        if file_type == 'audio':
            mutagen_data['cover_art_path'] = \
                    self.processor._cover_art_path(path)
        self.mutagen_data[path] = mutagen_data
        self.processor.run_mutagen_callback(path, file_type, duration, title,
                                            drm)
        self.check_metadata(path)

    def check_queued_mutagen_calls(self, filenames):
        correct_keys = ['/videos/' + f for f in filenames]
        self.assertSameSet(correct_keys, self.processor.mutagen_calls.keys())

    def check_queued_moviedata_calls(self, filenames):
        correct_keys = ['/videos/' + f for f in filenames]
        self.assertSameSet(correct_keys,
                           self.processor.movie_data_calls.keys())

    def get_metadata(self, filename):
        path = '/videos/' + filename
        return self.metadata_manager.get_metadata(path)

    def check_mutagen_error(self, filename):
        path = '/videos/' + filename
        self.processor.run_mutagen_errback(path, ValueError())
        # mutagen failing shouldn't change the metadata
        self.check_metadata(path)

    def check_run_movie_data(self, filename, file_type, duration,
                             screenshot_worked):
        if not filename.startswith('/'):
            path = '/videos/' + filename
        else:
            path = filename
        self.processor.run_movie_data_callback(path, file_type, duration,
                                               screenshot_worked)
        # check that the metadata is updated based on the values from mutagen
        movieprogram_data = {
            'file_type': file_type,
            'duration': duration,
        }
        # remove keys with null values
        for key in movieprogram_data.keys():
            if movieprogram_data[key] is None:
                del movieprogram_data[key]
        if screenshot_worked:
            movieprogram_data['screenshot_path'] = \
                    self.processor.get_screenshot_path(path)
        self.movieprogram_data[path] = movieprogram_data
        self.check_metadata(path)

    def check_movie_data_error(self, filename):
        path = '/videos/' + filename
        self.processor.run_movie_data_errback(path, ValueError())
        # movie data failing shouldn't change the metadata
        self.check_metadata(path)

    def check_set_user_info(self, filename, **info):
        path = '/videos/' + filename
        self.user_info_data[path].update(info)
        self.metadata_manager.set_user_data(path, info)
        self.check_metadata(path)

    def test_video(self):
        # Test video files with no issuse
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'video', 100, 'Foo')
        self.check_run_movie_data('foo.avi', 'video', 100, True)

    def test_video_no_screenshot(self):
        # Test video files where the movie data program fails to take a
        # screenshot
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'video', 100, 'Foo')
        self.check_run_movie_data('foo.avi', 'video', 100, False)

    def test_audio(self):
        # Test audio files with no issuse
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', 200, 'Bar')

    def test_audio_no_duration(self):
        # Test audio files where mutagen can't get the duration
        self.check_add_file('foo.mp3')
        self.check_run_mutagen('foo.mp3', 'audio', None, 'Bar')
        # Because mutagen failed to get the duration, we should have a movie
        # data call scheduled
        self.check_run_movie_data('foo.mp3', 'video', 100, False)

    def test_ogg(self):
        # Test ogg files
        self.check_add_file('foo.ogg')
        self.check_run_mutagen('foo.ogg', 'audio', 100, 'Bar')
        # Even though mutagen thinks this file is audio, we should still run
        # mutagen because it might by a mis-identified ogv file
        self.check_run_movie_data('foo.ogg', 'video', 100, True)

    def test_other(self):
        # Test non media files
        self.check_add_file('foo.pdf')
        self.check_run_mutagen('foo.pdf', 'other', None, None)
        # Since mutagen couldn't determine the file type, we should run movie
        # data
        self.check_run_movie_data('foo.pdf', 'other', None, False)

    def test_mutagen_failure(self):
        # Test mutagen failing
        self.check_add_file('foo.avi')
        self.check_mutagen_error('foo.avi')
        # We should run movie data since mutagen failed
        self.check_run_movie_data('foo.avi', 'other', 100, True)

    def test_movie_data_failure(self):
        # Test video files where movie data fails
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'video', 100, 'Foo')
        self.check_movie_data_error('foo.avi')

    def test_has_drm(self):
        # check the has_drm flag
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'audio', 100, 'Foo', drm=True)
        # if mutagen thinks a file has drm, we still need to check with movie
        # data to make sure
        self.assertEquals(self.get_metadata('foo.avi')['has_drm'], False)
        # if we get a movie data error, than we know there's DRM
        self.check_movie_data_error('foo.avi')
        self.assertEquals(self.get_metadata('foo.avi')['has_drm'], True)

        # let's try that whole process again, but make movie data succeed.  In
        # that case has_drm should be false
        self.check_add_file('foo2.avi')
        self.check_run_mutagen('foo2.avi', 'audio', 100, 'Foo', drm=True)
        self.assertEquals(self.get_metadata('foo2.avi')['has_drm'], False)
        self.check_run_movie_data('foo2.avi', 'audio', 100, True)
        self.assertEquals(self.get_metadata('foo2.avi')['has_drm'], False)

    def test_restart_incomplete(self):
        # check the has_drm flag
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'video', 100, 'Foo')
        self.check_add_file('bar.avi')
        self.check_add_file('baz.mp3')
        self.check_run_mutagen('baz.mp3', 'audio', 100, 'Foo')
        self.check_add_file('qux.avi')
        self.check_run_mutagen('qux.avi', 'video', 100, 'Foo')
        self.check_run_movie_data('qux.avi', 'video', 100, True)
        # At this point, foo needs movie data to be run, bar needs mutagen and
        # movie data to be run and baz/qux are complete
        self.processor.reset()
        self.metadata_manager.restart_incomplete()
        # check that the correct calls are queed up
        self.check_queued_moviedata_calls(['foo.avi'])
        self.check_queued_mutagen_calls(['bar.avi'])
        # after mutagen finishes for bar, it should be queud for movie data
        self.check_run_mutagen('bar.avi', 'video', 100, 'Foo')
        self.check_queued_moviedata_calls(['foo.avi', 'bar.avi'])

    def test_delete(self):
        # add a couple files at different points in the metadata process
        self.check_add_file('foo.avi')
        self.check_run_mutagen('foo.avi', 'video', 100, 'Foo')
        self.check_add_file('bar.mp3')
        self.check_add_file('baz.avi')
        self.check_run_mutagen('baz.avi', 'video', 100, 'Foo')
        self.check_run_movie_data('baz.avi', 'video', 100, True)
        self.check_queued_moviedata_calls(['foo.avi'])
        self.check_queued_mutagen_calls(['bar.mp3'])
        # remove the files
        to_remove = ['/videos/foo.avi', '/videos/bar.mp3', '/videos/baz.avi' ]
        self.metadata_manager.remove_file(to_remove[0])
        self.metadata_manager.remove_files(to_remove[1:])
        # check that the metadata manager sent a CancelFileOperations message
        self.assertEquals(self.processor.canceled_files, set(to_remove))
        # check that none of the videos are in the metadata manager
        for path in to_remove:
            self.assertRaises(KeyError, self.metadata_manager.get_metadata,
                              path)
        # check that callbacks/errbacks for those files don't result in
        # errors.  The metadata system may have already been processing the
        # file when it got the CancelFileOperations message.
        self.processor.run_movie_data_callback('/videos/foo.avi', 'video',
                                               100, True)
        self.processor.run_mutagen_errback('/videos/bar.mp3', ValueError())

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

    def test_metadata_fallbacks(self):
        # Check our fallback logic.  See MetadataManager._add_fallbacks() for
        # details.
        self.check_add_file('foo.avi')
        self.check_set_user_info('foo.avi', artist=u'miro',
                                 title=u'Four point Five', album=u'PCF')

    def test_queueing(self):
        # test that if we don't send too many requests to the worker process
        paths = ['/videos/video-%d.avi' % i for i in xrange(200)]
        for p in paths:
            self.metadata_manager.add_file(p)
        # 200 paths are ready to go, but only 100 should be queued up to
        # mutagen
        self.assertEquals(len(self.processor.mutagen_calls), 100)

        def run_mutagen(start, stop):
            for p in paths[start:stop]:
                self.processor.run_mutagen_callback(p, 'video', 100, u'Title',
                                                    False)
        def run_movie_data(start, stop):
            for p in paths[start:stop]:
                self.processor.run_movie_data_callback(p, 'video', 100, True)

        # let 50 mutagen tasks complete, we should queue up 50 more
        run_mutagen(0, 50)
        self.assertEquals(len(self.processor.mutagen_calls), 100)
        self.assertEquals(len(self.processor.movie_data_calls), 50)
        # let 75 more complete, we should be hitting our movie data max now
        run_mutagen(50, 125)
        self.assertEquals(len(self.processor.mutagen_calls), 75)
        self.assertEquals(len(self.processor.movie_data_calls), 100)
        # looks good, just double check that we finish both queues okay
        run_movie_data(0, 100)
        self.assertEquals(len(self.processor.movie_data_calls), 25)
        run_mutagen(125, 200)
        self.assertEquals(len(self.processor.mutagen_calls), 0)
        self.assertEquals(len(self.processor.movie_data_calls), 100)
        run_movie_data(100, 200)
        self.assertEquals(len(self.processor.mutagen_calls), 0)
        self.assertEquals(len(self.processor.movie_data_calls), 0)

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
        new_paths = [new_path_name(p) for p in to_move]
        self.metadata_manager.files_moved(zip(to_move, new_paths))
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
        self.processor.run_movie_data_callback('/videos/foo.avi', 'video',
                                               100, True)
        self.processor.run_mutagen_errback('/videos/bar.mp3', ValueError())
        # check that callbacks work for new paths
        self.check_run_movie_data('/videos2/foo.avi', 'video', 100, True)
        self.check_run_mutagen('/videos2/bar.mp3', 'audio', 120, 'Bar')

    def test_queueing_with_delete(self):
        # test that we remove files that are queued as well
        paths = ['/videos/video-%d.avi' % i for i in xrange(200)]
        for p in paths:
            self.metadata_manager.add_file(p)
        # we now have 200 mutagen calls so 100 of them should be pending

        # if some files get removed, then we should start new ones
        self.metadata_manager.remove_files(paths[:25])
        self.assertEquals(len(self.processor.mutagen_calls), 125)

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
        changes = [(p, '/new' + p) for p in moved]
        self.metadata_manager.will_move_files(moved)
        self.metadata_manager.files_moved(changes)
        # send mutagen call backs so the pending calls start
        for p in paths[:100]:
            self.processor.run_mutagen_callback(p, 'video', 100, u'Title',
                                                False)
        correct_paths = paths[100:150] + [p[1] for p in changes]
        self.assertSameSet(self.processor.mutagen_calls.keys(), correct_paths)

# Create ItemSchema circa version 165 for Upgrade166Test
from miro.schema import *

class ItemSchemaV165(MultiClassObjectSchema):
    table_name = 'item'

    @classmethod
    def ddb_object_classes(cls):
        return (Item, FileItem)

    @classmethod
    def get_ddb_class(cls, restored_data):
        if restored_data['is_file_item']:
            return FileItem
        else:
            return Item

    fields = DDBObjectSchema.fields + [
        ('is_file_item', SchemaBool()),
        ('feed_id', SchemaInt(noneOk=True)),
        ('downloader_id', SchemaInt(noneOk=True)),
        ('parent_id', SchemaInt(noneOk=True)),
        ('seen', SchemaBool()),
        ('autoDownloaded', SchemaBool()),
        ('pendingManualDL', SchemaBool()),
        ('pendingReason', SchemaString()),
        ('expired', SchemaBool()),
        ('keep', SchemaBool()),
        ('creationTime', SchemaDateTime()),
        ('linkNumber', SchemaInt(noneOk=True)),
        ('icon_cache_id', SchemaInt(noneOk=True)),
        ('downloadedTime', SchemaDateTime(noneOk=True)),
        ('watchedTime', SchemaDateTime(noneOk=True)),
        ('lastWatched', SchemaDateTime(noneOk=True)),
        ('subtitle_encoding', SchemaString(noneOk=True)),
        ('isContainerItem', SchemaBool(noneOk=True)),
        ('releaseDateObj', SchemaDateTime()),
        ('eligibleForAutoDownload', SchemaBool()),
        ('duration', SchemaInt(noneOk=True)),
        ('screenshot', SchemaFilename(noneOk=True)),
        ('resumeTime', SchemaInt()),
        ('channelTitle', SchemaString(noneOk=True)),
        ('license', SchemaString(noneOk=True)),
        ('rss_id', SchemaString(noneOk=True)),
        ('thumbnail_url', SchemaURL(noneOk=True)),
        ('entry_title', SchemaString(noneOk=True)),
        ('entry_description', SchemaString(noneOk=False)),
        ('link', SchemaURL(noneOk=False)),
        ('payment_link', SchemaURL(noneOk=False)),
        ('comments_link', SchemaURL(noneOk=False)),
        ('url', SchemaURL(noneOk=False)),
        ('enclosure_size', SchemaInt(noneOk=True)),
        ('enclosure_type', SchemaString(noneOk=True)),
        ('enclosure_format', SchemaString(noneOk=True)),
        ('was_downloaded', SchemaBool()),
        ('filename', SchemaFilename(noneOk=True)),
        ('deleted', SchemaBool(noneOk=True)),
        ('shortFilename', SchemaFilename(noneOk=True)),
        ('offsetPath', SchemaFilename(noneOk=True)),
        ('play_count', SchemaInt()),
        ('skip_count', SchemaInt()),
        ('cover_art', SchemaFilename(noneOk=True)),
        ('mdp_state', SchemaInt(noneOk=True)),
        # metadata:
        ('metadata_version', SchemaInt()),
        ('title', SchemaString(noneOk=True)),
        ('title_tag', SchemaString(noneOk=True)),
        ('description', SchemaString(noneOk=True)),
        ('album', SchemaString(noneOk=True)),
        ('album_artist', SchemaString(noneOk=True)),
        ('artist', SchemaString(noneOk=True)),
        ('track', SchemaInt(noneOk=True)),
        ('album_tracks', SchemaInt(noneOk=True)),
        ('year', SchemaInt(noneOk=True)),
        ('genre', SchemaString(noneOk=True)),
        ('rating', SchemaInt(noneOk=True)),
        ('file_type', SchemaString(noneOk=True)),
        ('has_drm', SchemaBool(noneOk=True)),
        ('show', SchemaString(noneOk=True)),
        ('episode_id', SchemaString(noneOk=True)),
        ('episode_number', SchemaInt(noneOk=True)),
        ('season_number', SchemaInt(noneOk=True)),
        ('kind', SchemaString(noneOk=True)),
    ]

    indexes = (
            ('item_feed', ('feed_id',)),
            ('item_feed_visible', ('feed_id', 'deleted')),
            ('item_parent', ('parent_id',)),
            ('item_downloader', ('downloader_id',)),
            ('item_feed_downloader', ('feed_id', 'downloader_id',)),
            ('item_file_type', ('file_type',)),
    )

class MetadataStatusSchemaV166(DDBObjectSchema):
    klass = MetadataStatus
    table_name = 'metadata_status'
    fields = DDBObjectSchema.fields + [
        ('path', SchemaFilename()),
        ('mutagen_status', SchemaString()),
        ('moviedata_status', SchemaString()),
    ]

    indexes = (
        ('metadata_mutagen', ('mutagen_status',)),
        ('metadata_moviedata', ('moviedata_status',))
    )

    unique_indexes = (
        ('metadata_path', ('path',)),
    )

class MetadataEntrySchemaV166(DDBObjectSchema):
    klass = MetadataEntry
    table_name = 'metadata'
    fields = DDBObjectSchema.fields + [
        ('path', SchemaFilename()),
        ('source', SchemaString()),
        ('priority', SchemaInt()),
        ('file_type', SchemaString(noneOk=True)),
        ('duration', SchemaInt(noneOk=True)),
        ('album', SchemaString(noneOk=True)),
        ('album_artist', SchemaString(noneOk=True)),
        ('album_tracks', SchemaInt(noneOk=True)),
        ('artist', SchemaString(noneOk=True)),
        ('cover_art_path', SchemaFilename(noneOk=True)),
        ('screenshot_path', SchemaFilename(noneOk=True)),
        ('drm', SchemaBool(noneOk=True)),
        ('genre', SchemaString(noneOk=True)),
        ('title', SchemaString(noneOk=True)),
        ('track', SchemaInt(noneOk=True)),
        ('year', SchemaInt(noneOk=True)),
        ('description', SchemaString(noneOk=True)),
        ('rating', SchemaInt(noneOk=True)),
        ('show', SchemaString(noneOk=True)),
        ('episode_id', SchemaString(noneOk=True)),
        ('episode_number', SchemaInt(noneOk=True)),
        ('season_number', SchemaInt(noneOk=True)),
        ('kind', SchemaString(noneOk=True)),
    ]

    indexes = (
        ('metadata_entry_path', ('path',)),
    )

    unique_indexes = (
        ('metadata_entry_path_and_source', ('path', 'source')),
    )

class Upgrade166Test(MiroTestCase):
    """Test upgrade 166, which migrates metadata from the item table to the
    metadata table.
    """

    # values for the old mdp_state column
    MDP_UNSEEN = None
    MDP_SKIPPED = 0
    MDP_RAN = 1
    MDP_FAILED = 2

    def setUp(self):
        MiroTestCase.setUp(self)
        self.metadata_manager = metadata.MetadataManager()
        self.id_counter = itertools.count(1)
        self.old_item_data = {}
        self.unicode_filenames = (PlatformFilenameType is unicode)

    def test_upgrade(self):
        self.setup_db()
        self.populate_db()
        self.upgrade_db()
        self.check_db()

    def setup_db(self):
        self.reload_database(object_schemas = [ItemSchemaV165],
                            schema_version=165)

    def populate_db(self):
        # make a couple items, trying to test permutations of the following
        #   - Different values / None for metadata
        #   - Cover art present or none
        #   - downloaded items, undownloaded items and file items
        #   - has DRM or not
        #   - different MDP states
        cover_art_choices = [True, False]
        item_type_choices = ['downloaded', 'undownloaded', 'file', 'duplicate']
        has_drm_choices = [True, False]
        metadata_present_choices = ['all', 'no-artist', 'no-duration']
        mdp_state_choices = [None, 0, 1, 2]
        null_title_choices = [True, False]

        i = 0
        for (has_cover_art, item_type, metadata_present, has_drm,
             mdp_state, null_title) in itertools.product(
                 cover_art_choices, item_type_choices,
                 metadata_present_choices, has_drm_choices,
                 mdp_state_choices, null_title_choices):
            if item_type == 'undownloaded':
                filename = None
            elif item_type == 'duplicate':
                filename = '/videos/video-%s.avi' % (i - 1)
            else:
                filename = '/videos/video-%s.avi' % i
            album = 'Album %s' % i
            title = 'Title %s' % i
            artist = 'Artist %s' % i
            duration = 100
            if has_cover_art:
                cover_art = '/cover-art/video-%s.png' % i
            else:
                cover_art = None
            if metadata_present == 'no-duration':
                duration = None
            elif metadata_present == 'no-artist':
                artist = None
            is_file_item = (item_type == 'file')
            self.add_old_item_to_db(filename, is_file_item, duration,
                                    cover_art, title, artist, album, has_drm,
                                    mdp_state, null_title)
            i += 1

    def add_old_item_to_db(self, filename, is_file_item, duration, cover_art,
                           album, artist, title, has_drm, mdp_state,
                           null_title):
        """Add an item to our database to test upgrading """
        data = {
            'id': self.id_counter.next(),
            'is_file_item': is_file_item,
            'filename': filename,
            'duration': duration,
            'cover_art': cover_art,
            'album': album,
            'has_drm': has_drm,
            'mdp_state': mdp_state,
            'seen': False,
            'autoDownloaded': False,
            'pendingManualDL': False,
            'expired': False,
            'keep': False,
            'eligibleForAutoDownload': False,
            'pendingReason': '',
            'creationTime': '2011-12-01',
            'releaseDateObj': '2011-12-01',
            'resumeTime': 0,
            'was_downloaded': (filename is not None),
            'play_count': 0,
            'skip_count': 0,
            'metadata_version': 5,
        }
        if null_title:
            data['title_tag'] = artist
        else:
            data['title'] = artist
        if not is_file_item:
            data['downloader_id'] = 9999
        if self.unicode_filenames and data['filename']:
            data['filename'] = data['filename'].decode('utf-8')
        for name, schema_type in ItemSchemaV165.fields:
            if name not in data:
                data[name] = None
        sql = "INSERT INTO item (%s) VALUES (%s)" % (
            ', '.join(data.keys()),
            ', '.join('?' for i in xrange(len(data))))
        app.db.cursor.execute(sql, [data[k] for k in data.keys()])
        # store data if this will be put into the metadata system, and if it's
        # the first item with this filename
        if filename is not None:
            if filename not in self.old_item_data:
                self.old_item_data[filename] = data

    def upgrade_db(self):
        "Simulate ugrading from db version 165 to 166."""
        databaseupgrade.upgrade166(app.db.cursor)
        app.db._set_version(166)
        app.db._schema_map[metadata.MetadataStatus] = MetadataStatusSchemaV166
        app.db._schema_map[metadata.MetadataEntry] = MetadataEntrySchemaV166

    def check_db(self):
        # check that we created 1 metadata status for each downloaded item
        file_count = len(self.old_item_data)
        self.assertEquals(MetadataStatus.make_view().count(), file_count)
        # check that we created 1 metadata entry for each downloaded item
        self.assertEquals(MetadataEntry.make_view().count(), file_count)
        # check that all metadata entries have type == 'old-item'
        for entry in MetadataEntry.make_view():
            self.assertEquals(entry.source, 'old-item')

        # check the actual item data
        for path, old_data in self.old_item_data.items():
            self.check_item_migration(path, old_data)

        # check that the mdp_state and metadata_version columns are gone now
        # that we don't need it anymore.
        app.db.cursor.execute("SELECT sql FROM sqlite_master "
                              "WHERE type='table' AND name == 'item'")
        table_sql = app.db.cursor.fetchone()[0]
        if 'mdp_state' in table_sql:
            raise AssertionError("mdp_state not removed from item table")
        if 'metadata_version' in table_sql:
            raise AssertionError("metadata_version not removed from item table")

    def check_item_migration(self, path, old_data):
        correct_data = {}
        for column in ('duration', 'album', 'artist'):
            correct_data[column] = old_data[column]
        correct_data['cover_art_path'] = old_data['cover_art']
        if old_data.get('title') is not None:
            correct_data['title'] = old_data['title']
        else:
            correct_data['title'] = old_data['title_tag']
        if old_data['has_drm'] and old_data['mdp_state'] == self.MDP_FAILED:
            correct_data['has_drm'] = True
        else:
            correct_data['has_drm'] = False
        new_data = self.metadata_manager.get_metadata(path)
        for key, value in correct_data.items():
            if new_data.get(key) != value:
                raise AssertionError("conversion failed for %s "
                                     "(correct: %s, actual: %s)" %
                                     (key, value, new_data.get(key)))

        status = metadata.MetadataStatus.get_by_path(path)
        self.assertEquals(status.mutagen_status,
                          metadata.MetadataStatus.STATUS_SKIP)
        if old_data['mdp_state'] == self.MDP_UNSEEN:
            correct_mdp_status = metadata.MetadataStatus.STATUS_NOT_RUN
        elif old_data['mdp_state'] == self.MDP_SKIPPED:
            correct_mdp_status = metadata.MetadataStatus.STATUS_SKIP
        elif old_data['mdp_state'] == self.MDP_FAILED:
            correct_mdp_status = metadata.MetadataStatus.STATUS_FAILURE
        elif old_data['mdp_state'] == self.MDP_RAN:
            correct_mdp_status = metadata.MetadataStatus.STATUS_COMPLETE
        if status.moviedata_status != correct_mdp_status:
            raise AssertionError("error converting moviedata_status "
                                 "(old: %s, new moviedata_status: %s" %
                                 (old_data, status.moviedata_status))
