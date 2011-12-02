# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

"""``miro.metadata`` -- Handle metadata properties for *Items. Generally the
frontend cares about these and the backend doesn't.

Module properties:
    attribute_names -- set of attribute names for metadata
"""

import logging
import os.path

import sqlite3

from miro import app
from miro import database
from miro import eventloop
from miro import filetypes
from miro import prefs
from miro import signals
from miro import workerprocess
from miro.plat.utils import filename_to_unicode

attribute_names = set([
    'file_type', 'duration', 'album', 'album_artist', 'album_tracks',
    'artist', 'cover_art_path', 'screenshot_path', 'has_drm', 'genre',
    'title', 'track', 'year', 'description', 'rating', 'show', 'episode_id',
    'episode_number', 'season_number', 'kind',
])

class MetadataStatus(database.DDBObject):
    """Stores the status of different metadata extractors for a file

    For each metadata extractor (mutagen, movie data program, echoprint, etc),
    we store if that extractor has run yet, has failed, is being skipped, etc.
    """

    # constants for the *_status columns
    STATUS_NOT_RUN = u'N'
    STATUS_COMPLETE = u'C'
    STATUS_FAILURE = u'F'
    STATUS_SKIP = u'S'

    def setup_new(self, path):
        self.path = path
        self.mutagen_status = self.STATUS_NOT_RUN
        self.moviedata_status = self.STATUS_NOT_RUN
        self._add_to_cache()

    @classmethod
    def get_by_path(cls, path):
        """Get an object by its path attribute.

        We use the DatabaseObjectCache to cache status by path, so this method
        is fairly quick.
        """
        try:
            return app.db.cache.get('metadata', path)
        except KeyError:
            view = cls.make_view('path=?', (filename_to_unicode(path),))
            return view.get_singleton()

    def setup_restored(self):
        app.db.cache.set('metadata', self.path, self)

    def _add_to_cache(self):
        if app.db.cache.key_exists('metadata', self.path):
            # duplicate path.  Lets let sqlite raise the error when we try to
            # insert things.
            logging.warn("self.path already in cache (%s)", self.path)
            return
        app.db.cache.set('metadata', self.path, self)

    def removed_from_db(self):
        app.db.cache.remove('metadata', self.path)
        database.DDBObject.removed_from_db(self)

    def update_after_mutagen(self, data):
        self.mutagen_status = self.STATUS_COMPLETE
        if self._should_skip_movie_data(data):
            self.moviedata_status = self.STATUS_SKIP
        self.signal_change()

    def _should_skip_movie_data(self, mutagen_data):
        my_ext = os.path.splitext(self.path)[1].lower()
        # we should skip movie data if:
        #   - we're sure the file is audio (mutagen misreports .ogg videos as
        #     audio)
        #   - mutagen was able to get the duration for the file
        #   - mutagen doesn't think the file has DRM
        return ((my_ext == '.oga' or not my_ext.startswith('.og')) and
                mutagen_data.get('file_type') == 'audio' and
                mutagen_data.get('duration') is not None and
                not mutagen_data.get('drm'))

    def update_after_movie_data(self, data):
        self.moviedata_status = self.STATUS_COMPLETE
        self.signal_change()

    def update_after_mutagen_error(self):
        self.mutagen_status = self.STATUS_FAILURE
        self.signal_change()

    def update_after_movie_data_error(self):
        self.moviedata_status = self.STATUS_FAILURE
        self.signal_change()

    def rename(self, new_path):
        """Change the path for this object."""
        if app.db.cache.key_exists('metadata', new_path):
            raise KeyError("MetadataStatus.rename: already an object for "
                           "%s (old path: %s)" % (new_path, self.path))
        app.db.cache.remove('metadata', self.path)
        app.db.cache.set('metadata', new_path, self)
        self.path = new_path
        self.signal_change()

    @classmethod
    def needs_mutagen_view(cls):
        return cls.make_view('mutagen_status=?', (cls.STATUS_NOT_RUN,))

    @classmethod
    def needs_moviedata_view(cls):
        return cls.make_view('mutagen_status != ? AND moviedata_status=?',
                             (cls.STATUS_NOT_RUN, cls.STATUS_NOT_RUN))

class MetadataEntry(database.DDBObject):
    """Stores metadata from a single source.

    Each metadata extractor (mutagen, movie data, echonest, etc), we create a
    MetadataEntry object for each path that it got metadata from.
    """

    # stores the priorities for each source type
    source_priority_map = {
        'old-item': 10,
        'mutagen': 20,
        'movie-data': 30,
        'user-data': 50,
    }

    # metadata columns stores the set of column names that store actual
    # metadata (as opposed to things like source and path)
    metadata_columns = attribute_names.copy()
    # has_drm is a tricky column.  In MetadataEntry objects it's just called
    # 'drm'.  Then MetadataManager calculates has_drm based on a variety of
    # factors.
    metadata_columns.discard('has_drm')
    metadata_columns.add('drm')

    def setup_new(self, path, source, data):
        self.path = path
        self.source = source
        self.priority = MetadataEntry.source_priority_map[source]
        # set all metadata to None by default
        for name in self.metadata_columns:
            setattr(self, name, None)
        self.__dict__.update(data)

    def update_metadata(self, new_data):
        """Update the values for this object."""
        self.__dict__.update(new_data)
        self.signal_change()

    def get_metadata(self):
        """Get the metadata stored in this object as a dict."""
        rv = {}
        for name in self.metadata_columns:
            value = getattr(self, name)
            if value is not None:
                rv[name] = value
        return rv

    def rename(self, new_path):
        """Change the path for this object."""
        self.path = new_path
        self.signal_change()

    @classmethod
    def metadata_for_path(cls, path):
        return cls.make_view('path=?', (filename_to_unicode(path),),
                             order_by='priority ASC')

    @classmethod
    def get_entry(cls, source, path):
        view = cls.make_view('source=? AND path=?',
                             (source, filename_to_unicode(path)))
        return view.get_singleton()

class _TaskProcessor(signals.SignalEmitter):
    """Handle sending tasks to the worker process.

    Responsible for:
        - sending messages
        - queueing messages after we reach a limit
        - handling callbacks and errbacks

    This class is the base class for this.  Subclasses need to define
    handle_callback() and handle_errback().

    Signals:

    - task-complete(status) -- we're done with a metadata entry
    """
    def __init__(self, limit):
        signals.SignalEmitter.__init__(self)
        self.create_signal('task-complete')
        self.limit = limit
        # map source paths to tasks
        self._active_tasks = {}
        self._pending_tasks = {}

    def add_task(self, task):
        if len(self._active_tasks) < self.limit:
            self._send_task(task)
        else:
            self._pending_tasks[task.source_path] = task

    def _send_task(self, task):
        self._active_tasks[task.source_path] = task
        workerprocess.send(task, self._callback, self._errback)

    def _on_task_complete(self, status, task):
        self.remove_task_for_path(task.source_path)
        self.emit('task-complete', status)

    def remove_task_for_path(self, path):
        try:
            del self._active_tasks[path]
        except KeyError:
            # task isn't in our system, maybe it's pending?
            try:
                del self._pending_tasks[path]
            except KeyError:
                pass
        else:
            if self._pending_tasks:
                path, task = self._pending_tasks.popitem()
                self._send_task(task)

    def _callback(self, task, result):
        try:
            status = MetadataStatus.get_by_path(task.source_path)
        except database.ObjectNotFoundError:
            logging.warn("got callback for removed path: %s", task.source_path)
            return
        self.handle_callback(status, task, result)
        self._on_task_complete(status, task)

    def _errback(self, task, error):
        logging.warn("Error running %s for %s: %s", task, task.source_path,
                     error)
        try:
            status = MetadataStatus.get_by_path(task.source_path)
        except database.ObjectNotFoundError:
            logging.warn("got errback for removed path: %s", task.source_path)
            return
        self.handle_errback(status, task, error)
        self._on_task_complete(status, task)

    def handle_callback(self, status, task, result):
        """Handle a successfull task."""
        raise NotImplementedError()

    def handle_errback(self, status, task, error):
        """Handle a successfull task."""
        raise NotImplementedError()


class _MutagenTaskProcessor(_TaskProcessor):
    def handle_callback(self, status, task, result):
        """Handle a successfull task."""
        logging.debug("mutagen done: %s", status.path)
        # Store the metadata
        MetadataEntry(task.source_path, u'mutagen', result)
        # Update MetadataStatus
        status.update_after_mutagen(result)

    def handle_errback(self, status, task, error):
        """Handle a successfull task."""
        status.update_after_mutagen_error()

class _MovieDataTaskProcessor(_TaskProcessor):
    def handle_callback(self, status, task, result):
        logging.debug("movie data done: %s", status.path)
        MetadataEntry(task.source_path, u'movie-data', result)
        status.update_after_movie_data(result)

    def handle_errback(self, status, task, error):
        status.update_after_movie_data_error()

class MetadataManager(signals.SignalEmitter):
    """Extract and track metadata for files.

    This class is responsible for:
    - creating/updating MetadataStatus and MetadataEntry objects
    - invoking mutagen, moviedata, echoprint, and other extractors
    - combining all the metadata we have for a path into a single dict.

    Signals:

    - new-metadata(dict) -- We have new metadata for files.  dict is a
                            dictionary mapping paths to the metadata.
    """

    # how long to wait before emiting the new-metadata signal.  Shorter times
    # mean more responsiveness, longer times allow us to bulk update many
    # items at once.
    UPDATE_INTERVAL = 1.0


    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.create_signal('new-metadata')
        self.mutagen_processor = _MutagenTaskProcessor(100)
        self.moviedata_processor = _MovieDataTaskProcessor(100)
        self.cover_art_dir = app.config.get(prefs.COVER_ART_DIRECTORY)
        icon_cache_dir = app.config.get(prefs.ICON_CACHE_DIRECTORY)
        self.screenshot_dir = os.path.join(icon_cache_dir, 'extracted')
        self.all_task_processors = [
            self.mutagen_processor,
            self.moviedata_processor
        ]
        for processor in self.all_task_processors:
            processor.connect("task-complete", self._on_task_complete)
        # paths that have new metadata since the last time we emitted the
        # "new-metadata" signal
        self.updated_paths = set()
        self._new_metadata_scheduled = False

    def add_file(self, path):
        """Add a new file to the metadata syestem

        :param path: path to the file
        :raises ValueError: path is already in the system
        """
        try:
            MetadataStatus(path)
        except sqlite3.IntegrityError:
            raise ValueError("%s already added" % path)
        self._run_mutagen(path)

    def path_in_system(self, path):
        """Test if a path is in the metadata system."""
        return app.db.cache.key_exists('metadata', path)

    def remove_file(self, path):
        """Remove a file from the metadata system.

        This is basically equivelent to calling remove_files([path]), except
        that it doesn't start the bulk_sql_manager.
        """
        paths = [path]
        workerprocess.cancel_tasks_for_files(paths)
        self._remove_files(paths)

    def remove_files(self, paths):
        """Remove files from the metadata system.

        All queued mutagen and movie data calls will be canceled.

        :param paths: paths to remove
        :raises KeyError: path not in the metadata system
        """
        workerprocess.cancel_tasks_for_files(paths)
        app.bulk_sql_manager.start()
        try:
            self._remove_files(paths)
        finally:
            app.bulk_sql_manager.finish()

    def _remove_files(self, paths):
        """Does the work for remove_file and remove_files"""
        for path in paths:
            self._get_status_for_path(path).remove()
            for entry in MetadataEntry.metadata_for_path(path):
                entry.remove()
        for processor in self.all_task_processors:
            for path in paths:
                processor.remove_task_for_path(path)

    def will_move_files(self, paths):
        """Prepare for files to be moved

        All queued mutagen and movie data calls will be put on hold until
        files_moved() is called.

        :param paths: list of paths that will be moved
        """
        workerprocess.cancel_tasks_for_files(paths)
        for processor in self.all_task_processors:
            for path in paths:
                processor.remove_task_for_path(path)

    def files_moved(self, move_info):
        """Call this after files have been moved to a new location.

        Queued mutagen and movie data calls will be restarted.

        :param move_info: list of (old_path, new_path) tuples
        """
        restart_mutagen_for = []
        restart_moviedata_for = []
        app.bulk_sql_manager.start()
        try:
            for old_path, new_path in move_info:
                status = self._get_status_for_path(old_path)
                status.rename(new_path)
                for entry in MetadataEntry.metadata_for_path(old_path):
                    entry.rename(new_path)
                if status.mutagen_status == MetadataStatus.STATUS_NOT_RUN:
                    restart_mutagen_for.append(new_path)
                elif status.moviedata_status == MetadataStatus.STATUS_NOT_RUN:
                    restart_moviedata_for.append(new_path)
        finally:
            app.bulk_sql_manager.finish()
        for p in restart_mutagen_for:
            self._run_mutagen(p)
        for p in restart_moviedata_for:
            self._run_movie_data(p)

    def get_metadata(self, path):
        """Get metadata for a path

        :param path: path to the file
        :returns: dict of metadata
        :raises KeyError: path not in the metadata system
        """
        status = self._get_status_for_path(path)

        metadata = self._get_metadata_from_filename(path)
        drm_by_source = {}
        for entry in MetadataEntry.metadata_for_path(path):
            entry_metadata = entry.get_metadata()
            metadata.update(entry_metadata)
            drm_by_source[entry.source] = entry.drm
        metadata['has_drm'] = self._calc_has_drm(drm_by_source, status)
        self._add_fallback_columns(metadata)
        return metadata

    def _add_fallback_columns(self, metadata_dict):
        """If we don't have data for some keys, fallback to a different key
        """
        fallbacks = [
            ('show', 'artist'),
            ('episode_id', 'title')
        ]
        for name, fallback in fallbacks:
            if name not in metadata_dict:
                try:
                    metadata_dict[name] = metadata_dict[fallback]
                except KeyError:
                    # nothing in the fallback key either, too bad
                    pass

    def set_user_data(self, path, user_data):
        """Update metadata based on user-inputted data

        :raises KeyError: path not in the metadata system
        """
        # make sure that our MetadataStatus object exists
        status = self._get_status_for_path(path)
        try:
            # try to update the current entry
            current_entry = MetadataEntry.get_entry(u'user-data', path)
            current_entry.update_metadata(user_data)
        except database.ObjectNotFoundError:
            # make a new entry if none exists
            MetadataEntry(path, u'user-data', user_data)

    def restart_incomplete(self):
        """Restart extractors for files with incomplete metadata

        This method queues calls to mutagen, movie data, etc.  It should only
        be called once per miro run
        """
        for status in MetadataStatus.needs_mutagen_view():
            self._run_mutagen(status.path)
        for status in MetadataStatus.needs_moviedata_view():
            self._run_movie_data(status.path)

    def _get_status_for_path(self, path):
        """Get a MetadataStatus object for a given path."""
        try:
            return MetadataStatus.get_by_path(path)
        except database.ObjectNotFoundError:
            raise KeyError(path)

    def _calc_has_drm(self, drm_by_source, metadata_status):
        """Calculate the value of has_drm.

        has_drm is True when all of these are True
        - mutagen thinks the object has DRM
        - movie data failed to open the file, or we're not going to run movie
          data (this is only true for items created before the MetadataManager
          existed)
        """
        try:
            mutagen_thinks_drm = drm_by_source['mutagen']
        except KeyError:
            mutagen_thinks_drm = drm_by_source.get('old-item', False)
        return (mutagen_thinks_drm and
                metadata_status.moviedata_status in
                (MetadataStatus.STATUS_FAILURE or MetadataStatus.STATUS_SKIP))

    def _run_mutagen(self, path):
        """Run mutagen on a path."""
        task = workerprocess.MutagenTask(path, self.cover_art_dir)
        self.mutagen_processor.add_task(task)

    def _run_movie_data(self, path):
        """Run the movie data program on a path."""
        task = workerprocess.MovieDataProgramTask(path, self.screenshot_dir)
        self.moviedata_processor.add_task(task)

    def _on_task_complete(self, processor, status):
        if (processor is self.mutagen_processor and 
            status.moviedata_status == MetadataStatus.STATUS_NOT_RUN):
            self._run_movie_data(status.path)
        self.updated_paths.add(status.path)
        self._schedule_emit_new_metadata()

    def _get_metadata_from_filename(self, path):
        """Get metadata that we know from a filename alone."""
        return {
            'file_type': filetypes.item_file_type_for_filename(path),
        }

    def _schedule_emit_new_metadata(self):
        if not self._new_metadata_scheduled:
            eventloop.add_timeout(self.UPDATE_INTERVAL,
                                  self._emit_new_metadata,
                                  'emit new-metadata signal')
            self._new_metadata_scheduled =  True

    def _emit_new_metadata(self):
        self._new_metadata_scheduled = False
        new_metadata = dict((p, self.get_metadata(p))
                             for p in self.updated_paths)
        self.updated_paths.clear()
        self.emit('new-metadata', new_metadata)
