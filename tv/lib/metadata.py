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

import collections
import contextlib
import logging
import os.path

import sqlite3

from miro import app
from miro import database
from miro import echonest
from miro import eventloop
from miro import filetags
from miro import filetypes
from miro import fileutil
from miro import messages
from miro import prefs
from miro import signals
from miro import workerprocess
from miro.plat.utils import (filename_to_unicode,
                             get_enmfp_executable_path)

attribute_names = set([
    'file_type', 'duration', 'album', 'album_artist', 'album_tracks',
    'artist', 'cover_art_path', 'screenshot_path', 'has_drm', 'genre',
    'title', 'track', 'year', 'description', 'rating', 'show', 'episode_id',
    'episode_number', 'season_number', 'kind',
])

class MetadataStatus(database.DDBObject):
    """Stores the status of different metadata extractors for a file

    For each metadata extractor (mutagen, movie data program, echonest, etc),
    we store if that extractor has run yet, has failed, is being skipped, etc.
    """

    # NOTE: this class uses the database cache to store MetadataStatus objects
    # for quick access.  The category is "metadata", the key is the path to
    # the metadata and the value is the MetadataStatus object.
    #
    # If the value is None, that means there's a MetadataStatus object in the
    # database, but we haven't loaded it yet.

    # constants for the *_status columns
    STATUS_NOT_RUN = u'N'
    STATUS_COMPLETE = u'C'
    STATUS_FAILURE = u'F'
    STATUS_SKIP = u'S'

    _source_name_to_status_column = {
        u'mutagen': 'mutagen_status',
        u'movie-data': 'moviedata_status',
        u'echonest': 'echonest_status',
    }

    def setup_new(self, path):
        self.path = path
        self.mutagen_status = self.STATUS_NOT_RUN
        self.moviedata_status = self.STATUS_NOT_RUN
        self.echonest_status = self.STATUS_NOT_RUN
        self.mutagen_thinks_drm = False
        self.echonest_id = None
        self.max_entry_priority = -1
        self._add_to_cache()

    @classmethod
    def get_by_path(cls, path):
        """Get an object by its path attribute.

        We use the DatabaseObjectCache to cache status by path, so this method
        is fairly quick.
        """
        try:
            cache_value = app.db.cache.get('metadata', path)
        except KeyError:
            cache_value = None

        if cache_value is not None:
            return cache_value
        else:
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

    def get_has_drm(self):
        """Does this media file have DRM preventing us from playing it?

        has_drm is True when all of these are True
        - mutagen thinks the object has DRM
        - movie data failed to open the file, or we're not going to run movie
          data (this is only true for items created before the MetadataManager
          existed)
        """
        return (self.mutagen_thinks_drm and
                self.moviedata_status in
                (MetadataStatus.STATUS_FAILURE or MetadataStatus.STATUS_SKIP))

    def _set_status_column(self, source_name, value):
        column_name = self._source_name_to_status_column[source_name]
        setattr(self, column_name, value)

    def update_after_success(self, entry):
        """Update after we succussfully extracted some metadata

        :param entry: MetadataEntry for the new data
        """
        self._set_status_column(entry.source, self.STATUS_COMPLETE)
        if entry.source == 'mutagen':
            if self._should_skip_movie_data(entry):
                self.moviedata_status = self.STATUS_SKIP
            thinks_drm = entry.drm if entry.drm is not None else False
            self.mutagen_thinks_drm = thinks_drm
        elif entry.source == 'movie-data':
            if entry.file_type != u'audio':
                self.echonest_status = self.STATUS_SKIP
        self.max_entry_priority = max(self.max_entry_priority, entry.priority)
        self.signal_change()

    def _should_skip_movie_data(self, entry):
        my_ext = os.path.splitext(self.path)[1].lower()
        # we should skip movie data if:
        #   - we're sure the file is audio (mutagen misreports .ogg videos as
        #     audio)
        #   - mutagen was able to get the duration for the file
        #   - mutagen doesn't think the file has DRM
        return ((my_ext == '.oga' or not my_ext.startswith('.og')) and
                entry.file_type == 'audio' and
                entry.duration is not None and
                not entry.drm)

    def update_after_error(self, source_name):
        """Update after we failed to extract some metadata."""
        self._set_status_column(source_name, self.STATUS_FAILURE)
        if (source_name == u'movie-data' and
            self.mutagen_status == self.STATUS_FAILURE):
            # If both mutagen and moviedata couldn't read the file, don't
            # bother sending it to the ENMFP.  If we can't get the code, then
            # we have to skip echonest.
            self.echonest_status = self.STATUS_SKIP
        self.signal_change()

    def rename(self, new_path):
        """Change the path for this object."""
        app.db.cache.remove('metadata', self.path)
        app.db.cache.set('metadata', new_path, self)
        self.path = new_path
        self.signal_change()

    @classmethod
    def needs_mutagen_select(cls, columns):
        return cls.select(columns, 'mutagen_status=?', (cls.STATUS_NOT_RUN,))

    @classmethod
    def needs_moviedata_select(cls, columns):
        return cls.select(columns,
                          'mutagen_status != ? AND moviedata_status=?',
                          (cls.STATUS_NOT_RUN, cls.STATUS_NOT_RUN))

    @classmethod
    def needs_echonest_select(cls, columns):
        return cls.select(columns,
                          'mutagen_status != ? AND moviedata_status != ? AND '
                          'echonest_status = ?',
                          (cls.STATUS_NOT_RUN, cls.STATUS_NOT_RUN,
                           cls.STATUS_NOT_RUN))

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
        'echonest': 40,
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
    # cover_art_path is handled implicitly by saving the cover art using the
    # album name
    metadata_columns.discard('cover_art_path')

    def setup_new(self, path, source, data):
        self.path = path
        self.source = source
        self.priority = MetadataEntry.source_priority_map[source]
        self.disabled = False
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
        return cls.make_view('path=? AND NOT disabled',
                             (filename_to_unicode(path),),
                             order_by='priority ASC')

    @classmethod
    def get_entry(cls, source, path):
        view = cls.make_view('source=? AND path=?',
                             (source, filename_to_unicode(path)))
        return view.get_singleton()

    @classmethod
    def set_disabled(cls, source, path, disabled):
        """Set/Unset the disabled flag for metadata entry."""
        try:
            entry = cls.get_entry(source, path)
        except database.ObjectNotFoundError:
            pass
        else:
            entry.disabled = disabled
            entry.signal_change()

class _MetadataProcessor(signals.SignalEmitter):
    """Base class for processors that handle getting metadata somehow.

    Responsible for:
        - starting the extraction processes
        - queueing messages after we reach a limit
        - handling callbacks and errbacks

    Attributes:

    source_name -- Name to identify the source name.  This should match the
                   Metadata.source attribute

    Signals:

    - task-complete(path, results) -- we successfully extracted metadata
    - task-error(path) -- we failed to extract metadata
    """
    def __init__(self, source_name):
        signals.SignalEmitter.__init__(self)
        self.create_signal('task-complete')
        self.create_signal('task-error')
        self.source_name = source_name

    def remove_tasks_for_paths(self, paths):
        """Cancel any pending tasks for paths

        _MetadataProcessors should make their best attempt to stop the task,
        but since they are all using threads and/or different processes,
        there's always a chance that the task will still be processed
        """
        pass

class _TaskProcessor(_MetadataProcessor):
    """Handle sending tasks to the worker process.  """

    def __init__(self, source_name, limit):
        _MetadataProcessor.__init__(self, source_name)
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

    def remove_task_for_path(self, path):
        self.remove_tasks_for_paths([path])

    def remove_tasks_for_paths(self, paths):
        for path in paths:
            try:
                del self._active_tasks[path]
            except KeyError:
                # task isn't in our system, maybe it's pending?
                try:
                    del self._pending_tasks[path]
                except KeyError:
                    pass

        while len(self._active_tasks) < self.limit and self._pending_tasks:
            path, task = self._pending_tasks.popitem()
            self._send_task(task)

    def _callback(self, task, result):
        logging.debug("%s done: %s", self.source_name, task.source_path)
        self._check_for_none_values(result)
        self.emit('task-complete', task.source_path, result)
        self.remove_task_for_path(task.source_path)

    def _check_for_none_values(self, result):
        """Check that result dicts don't have keys for None values."""
        # FIXME: we shouldn't need this function, metadata extractors should
        # only send keys for values that it actually has, not None values.
        for key, value in result.items():
            if value is None:
                app.controller.failed_soft('_check_for_none_values',
                                           '%s has None Value' % key,
                                           with_exception=False)
                del result[key]

    def _errback(self, task, error):
        logging.warn("Error running %s for %s: %s", task, task.source_path,
                     error)
        self.emit('task-error', task.source_path)
        self.remove_task_for_path(task.source_path)

class _EchonestQueue(object):
    """Queue for echonest tasks.

    _EchonestQueue is a modified FIFO.  Each queue item is stored as a path +
    optional additional data.
    """
    def __init__(self):
        self.queue = collections.deque()

    def add(self, path, *extra_data):
        """Add a path to the queue.

        *extra_data can be used to store related data to the path.  It will be
        returned along with the path in pop()
        """
        self.queue.append((path, extra_data))

    def pop(self):
        """Pop a path from the active queue.

        If any positional arguments were passed in to add(), then return the
        tuple (path, extra_data1, extra_data2, ...).  If not, just return
        path.

        :raises IndexError: no path to pop
        """
        path, extra_data = self.queue.popleft()
        if extra_data:
            return (path,) + extra_data
        else:
            return path

    def remove_paths(self, path_set):
        """Remove all paths that are in a set."""

        def filter_removed(item):
            return item[0] not in path_set
        new_items = filter(filter_removed, self.queue)
        self.queue.clear()
        self.queue.extend(new_items)

    def __len__(self):
        """Get the number of items in the queue that are not disabled because
        of the config value.
        """
        return len(self.queue)

class _EchonestProcessor(_MetadataProcessor):
    """Processor runs echonest queries

    Currently we use ENMF to generate codes, but we may switch to echoprint in
    the future

    _EchonestProcessor stops calling the codegen processor once a certain
    buffer of codes to be sent to echonest is built up.
    """

    def __init__(self, code_buffer_size, cover_art_dir):
        _MetadataProcessor.__init__(self, u'echonest')
        self._code_buffer_size = code_buffer_size
        self._cover_art_dir = cover_art_dir
        self._codegen_queue = _EchonestQueue()
        self._echonest_queue = _EchonestQueue()
        self._running_codegen = False
        self._querying_echonest = False
        self._codegen_path = get_enmfp_executable_path()
        self._enabled = app.config.get(prefs.ECHONEST_ENABLED)
        self._metadata_for_path = {}
        app.backend_config_watcher.connect("changed", self._on_config_change)

    def add_path(self, path, current_metadata):
        self._metadata_for_path[path] = current_metadata
        self._codegen_queue.add(path)
        self._process_queue()

    def _run_codegen(self, path):
        echonest.exec_codegen(self._codegen_path, path, self._codegen_callback,
                                self._codegen_errback)
        self._running_codegen = True

    def _codegen_callback(self, path, code):
        self._running_codegen = False
        self._echonest_queue.add(path, code)
        self._process_queue()

    def _codegen_errback(self, path, error):
        logging.warn("Error running echonest codegen for %s (%s)" %
                     (path, error))
        self.emit('task-error', path)
        self._running_codegen = False
        del self._metadata_for_path[path]
        self._process_queue()

    def _query_echonest(self, path, code):
        version = 3.15 # change to 4.11 for echoprint
        metadata = self._metadata_for_path.pop(path)
        echonest.query_echonest(path, self._cover_art_dir, code, version,
                                metadata, self._echonest_callback,
                                self._echonest_errback)
        self._querying_echonest = True

    def _echonest_callback(self, path, metadata):
        logging.debug("Got echonest data for %s:\n%s", path, metadata)
        self._querying_echonest = False
        self.emit('task-complete', path, metadata)
        self._process_queue()

    def _echonest_errback(self, path, error):
        logging.warn("Error running echonest for %s (%s)" % (path, error))
        self._querying_echonest = False
        self.emit('task-error', path)
        self._process_queue()

    def _on_config_change(self, watcher, key, value):
        if key == prefs.ECHONEST_ENABLED.key:
            self._enabled = value
            if value:
                self._process_queue()

    def _process_queue(self):
        if not self._enabled:
            return

        # process echonest queue
        if (self._echonest_queue and not self._querying_echonest):
            self._query_echonest(*self._echonest_queue.pop())

        # process codegen queue
        if (self._codegen_queue and
            not self._running_codegen and
            len(self._echonest_queue) < self._code_buffer_size):
            self._run_codegen(self._codegen_queue.pop())

    def remove_tasks_for_paths(self, paths):
        path_set = set(paths)
        self._echonest_queue.remove_paths(path_set)
        self._codegen_queue.remove_paths(path_set)
        # since we may have deleted active paths, process the new ones
        self._process_queue()

class _ProcessingCountTracker(object):
    """Helps MetadataManager keep track of counts for MetadataProgressUpdate

    For each file type, this class tracks the number of files that we're
    still getting metadata for.
    """
    def __init__(self):
        # map file type to the count for that type
        self.counts = collections.defaultdict(int)
        # map file type to the total for that type.  The total should track
        # the number of file_started() calls, without ever going down.  Once
        # the counts goes down to zero, it should be reset
        self.totals = collections.defaultdict(int)
        # map paths to the file type we currently think they are
        self.file_types = {}

    def get_count(self, file_type):
        return self.counts[file_type]

    def get_total(self, file_type):
        return self.totals[file_type]

    def file_started(self, path, metadata=None):
        """Add a path to our counts.

        metadata is an optional dict of metadata for that file.
        """
        if metadata is not None:
            file_type = metadata['file_type']
        else:
            file_type = filetypes.item_file_type_for_filename(path)
        self.file_types[path] = file_type
        self.counts[file_type] += 1
        self.totals[file_type] += 1

    def check_file_type(self, path, metadata):
        """Check we have the right file type for a path.

        Call this whenever the metadata changes for a path.
        """
        new_file_type = metadata['file_type']
        try:
            old_file_type = self.file_types[path]
        except KeyError:
            # not a big deal, we probably finished the file at the same time
            # as the metadata update.
            return
        if new_file_type != old_file_type:
            self.counts[old_file_type] -= 1
            self.counts[new_file_type] += 1
            # change total value too, since the original guess was wrong
            self.totals[old_file_type] -= 1
            self.totals[new_file_type] += 1
            self.file_types[path] = new_file_type

    def file_finished(self, path):
        """Remove a file from our counts."""
        try:
            file_type = self.file_types.pop(path)
        except KeyError:
            # Not tracking this path, just ignore
            return
        self.counts[file_type] -= 1
        if self.counts[file_type] == 0:
            self.totals[file_type] = 0

    def file_moved(self, old_path, new_path):
        """Change the name for a file."""
        try:
            self.file_types[new_path] = self.file_types.pop(old_path)
        except KeyError:
            # not tracking this path, just ignore
            return

class MetadataManager(signals.SignalEmitter):
    """Extract and track metadata for files.

    This class is responsible for:
    - creating/updating MetadataStatus and MetadataEntry objects
    - invoking mutagen, moviedata, echonest, and other extractors
    - combining all the metadata we have for a path into a single dict.

    Signals:

    - new-metadata(dict) -- We have new metadata for files. dict is a
                            dictionary mapping paths to the new metadata.
                            Note: the new metadata only contains changed
                            values, not the entire metadata dict.
    """

    # how long to wait before emiting the new-metadata signal.  Shorter times
    # mean more responsiveness, longer times allow us to bulk update many
    # items at once.
    UPDATE_INTERVAL = 1.0

    def __init__(self, cover_art_dir):
        signals.SignalEmitter.__init__(self)
        self.create_signal('new-metadata')
        self.cover_art_dir = cover_art_dir
        self.echonest_cover_art_dir = os.path.join(cover_art_dir, 'echonest')
        if not fileutil.exists(self.echonest_cover_art_dir):
            fileutil.makedirs(self.echonest_cover_art_dir)
        icon_cache_dir = app.config.get(prefs.ICON_CACHE_DIRECTORY)
        self.mutagen_processor = _TaskProcessor(u'mutagen', 100)
        self.moviedata_processor = _TaskProcessor(u'movie-data', 100)
        self.echonest_processor = _EchonestProcessor(
            5, self.echonest_cover_art_dir)
        self.screenshot_dir = os.path.join(icon_cache_dir, 'extracted')
        self.pending_mutagen_tasks = []
        self.bulk_add_count = 0
        self.metadata_processors = [
            self.mutagen_processor,
            self.moviedata_processor,
            self.echonest_processor,
        ]
        for processor in self.metadata_processors:
            processor.connect("task-complete", self._on_task_complete)
            processor.connect("task-error", self._on_task_error)
        self.count_tracker = _ProcessingCountTracker()
        # List of (processor, path, metadata) tuples for metadata since the
        # last _run_updates() call
        self.metadata_finished = []
        # List of (processor, path) tuples for failed metadata since the last
        # _run_updates() call
        self.metadata_errors = []
        self._reset_new_metadata()
        self._update_scheduled = False
        self._calc_incomplete()
        self._setup_path_placeholders()

    def _reset_new_metadata(self):
        self.new_metadata = collections.defaultdict(dict)

    def _setup_path_placeholders(self):
        """Add None values to the cache for all MetadataStatus objects

        This makes path_in_system() work since it checks if the key exists.
        However, we don't actually want to load the objects yet, since this is
        called pretty early in the startup process.
        """
        for row in MetadataStatus.select(["path"]):
            app.db.cache.set('metadata', row[0], None)

    @contextlib.contextmanager
    def bulk_add(self):
        """Context manager to use when adding lots of files

        While this context manager is active, we will delay calling mutagen.
        bulk_add() contexts can be nested, we will delay processing metadata
        until the last one finishes.

        Example:

        >>> with metadata_manager.bulk_add()
        >>>     add_lots_of_videos()
        >>>     add_lots_of_videos()
        >>> # at this point mutagen calls will start
        """
        # initialize context
        self.bulk_add_count += 1
        yield
        # cleanup context
        self.bulk_add_count -= 1
        if not self.in_bulk_add():
            self._send_pending_mutagen_tasks()

    def in_bulk_add(self):
        return self.bulk_add_count != 0

    def _send_pending_mutagen_tasks(self):
        for task in self.pending_mutagen_tasks:
            self.mutagen_processor.add_task(task)
        self.pending_mutagen_tasks = []

    def add_file(self, path):
        """Add a new file to the metadata syestem

        :param path: path to the file
        :returns initial metadata for the file
        :raises ValueError: path is already in the system
        """
        try:
            MetadataStatus(path)
        except sqlite3.IntegrityError:
            raise ValueError("%s already added" % path)
        self._run_mutagen(path)
        self.count_tracker.file_started(path)
        self._schedule_update()
        return self._get_metadata_from_filename(path)

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
            self.count_tracker.file_finished(path)
        for processor in self.metadata_processors:
            processor.remove_tasks_for_paths(paths)
        self._schedule_update()

    def will_move_files(self, paths):
        """Prepare for files to be moved

        All queued mutagen and movie data calls will be put on hold until
        file_moved() is called.

        :param paths: list of paths that will be moved
        """
        workerprocess.cancel_tasks_for_files(paths)
        for processor in self.metadata_processors:
            processor.remove_tasks_for_paths(paths)

    def file_moved(self, old_path, new_path):
        """Call this after a file has been moved to a new location.

        Queued mutagen and movie data calls will be restarted.

        :param move_info: list of (old_path, new_path) tuples
        """
        restart_mutagen_for = []
        restart_moviedata_for = []
        try:
            status = self._get_status_for_path(old_path)
        except KeyError:
            logging.warn("_process_files_moved: %s not in DB", old_path)
            return
        if app.db.cache.key_exists('metadata', new_path):
            # There's already an entry for the new status.  What to do
            # here?  Let's use the new one
            logging.warn("_process_files_moved: already an object for "
                         "%s (old path: %s)" % (new_path, status.path))
            self.count_tracker.file_finished(status.path)
            self.remove_file(status.path)
            return

        status.rename(new_path)
        for entry in MetadataEntry.metadata_for_path(old_path):
            entry.rename(new_path)
        if status.mutagen_status == MetadataStatus.STATUS_NOT_RUN:
            self._run_mutagen(new_path)
        elif status.moviedata_status == MetadataStatus.STATUS_NOT_RUN:
            self._run_movie_data(new_path)
            restart_moviedata_for.append(new_path)
        self.count_tracker.file_moved(old_path, new_path)

    def get_metadata(self, path):
        """Get metadata for a path

        :param path: path to the file
        :returns: dict of metadata
        :raises KeyError: path not in the metadata system
        """
        status = self._get_status_for_path(path)

        metadata = self._get_metadata_from_filename(path)
        for entry in MetadataEntry.metadata_for_path(path):
            if (not app.config.get(prefs.ECHONEST_ENABLED) and
                entry.source == 'echonest'):
                continue
            entry_metadata = entry.get_metadata()
            metadata.update(entry_metadata)
        metadata['has_drm'] = status.get_has_drm()
        self._add_cover_art_path(metadata)
        return metadata

    def _add_cover_art_path(self, metadata):
        """Add the cover art path to a metadata dict """
        if 'album' in metadata:
            filename = filetags.calc_cover_art_filename(metadata['album'])
            mutagen_path = os.path.join(self.cover_art_dir, filename)
            echonest_path = os.path.join(self.cover_art_dir, 'echonest',
                                         filename)
            if os.path.exists(echonest_path):
                metadata['cover_art_path'] = echonest_path
            elif os.path.exists(mutagen_path):
                metadata['cover_art_path'] = mutagen_path

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

    def _calc_incomplete(self):
        """Figure out which metadata status objects we should restart.

        We have to call this method on startup, but we don't want to start
        doing any work until restart_incomplete() is called.  So we just save
        the IDs of the rows to restart.
        """
        self.restart_mutagen_ids = [row[0] for row in
                                    MetadataStatus.needs_mutagen_select(['id'])]
        self.restart_moviedata_ids = [row[0] for row in
                                      MetadataStatus.needs_moviedata_select(['id'])]
        self.restart_echonest_ids = [row[0] for row in
                                      MetadataStatus.needs_echonest_select(['id'])]

    def restart_incomplete(self):
        """Restart extractors for files with incomplete metadata

        This method queues calls to mutagen, movie data, etc.
        """
        for id_ in self.restart_mutagen_ids:
            try:
                status = MetadataStatus.get_by_id(id_)
            except database.ObjectNotFoundError:
                pass # just ignore deleted objects
            self._run_mutagen(status.path)
            # Add file to our _ProcessingCountTracker, but don't call
            # get_metadata().  If we need mutagen, it's safe to say we don't
            # have any metadata
            self.count_tracker.file_started(status.path)

        for id_ in self.restart_moviedata_ids:
            try:
                status = MetadataStatus.get_by_id(id_)
            except database.ObjectNotFoundError:
                pass # just ignore deleted objects
            self._run_movie_data(status.path)
            # Add file to our _ProcessingCountTracker.
            self.count_tracker.file_started(status.path,
                                            self.get_metadata(status.path))

        for id_ in self.restart_echonest_ids:
            try:
                status = MetadataStatus.get_by_id(id_)
            except database.ObjectNotFoundError:
                pass # just ignore deleted objects
            self._run_echonest(status.path)
            # Add file to our _ProcessingCountTracker.
            self.count_tracker.file_started(status.path,
                                            self.get_metadata(status.path))
        self.restart_mutagen_ids = []
        self.restart_moviedata_ids = []
        self.restart_echonest_ids = []
        self._schedule_update()

    def _get_status_for_path(self, path):
        """Get a MetadataStatus object for a given path."""
        try:
            return MetadataStatus.get_by_path(path)
        except database.ObjectNotFoundError:
            raise KeyError(path)

    def _run_mutagen(self, path):
        """Run mutagen on a path."""
        task = workerprocess.MutagenTask(path, self.cover_art_dir)
        if not self.in_bulk_add():
            self.mutagen_processor.add_task(task)
        else:
            self.pending_mutagen_tasks.append(task)

    def _run_movie_data(self, path):
        """Run the movie data program on a path."""
        task = workerprocess.MovieDataProgramTask(path, self.screenshot_dir)
        self.moviedata_processor.add_task(task)

    def _run_echonest(self, path):
        # FIXME: calling get_metadata() probably slows things down
        metadata = self.get_metadata(path)
        # make sure to get metadata that we just created but haven't saved yet
        # because we're doing a bulk insert
        if path in self.new_metadata:
            metadata.update(self.new_metadata[path])
        # we only send a subset of the metadata to echonest and some of the
        # key names are different
        echonest_metadata = {}
        for key in ('title', 'artist', 'duration'):
            try:
                echonest_metadata[key] = metadata[key]
            except KeyError:
                pass
        try:
            echonest_metadata['release'] = metadata['album']
        except KeyError:
            pass
        self.echonest_processor.add_path(path, echonest_metadata)

    def _on_task_complete(self, processor, path, result):
        self.metadata_finished.append((processor, path, result))
        self._schedule_update()

    def _on_task_error(self, processor, path):
        self.metadata_errors.append((processor, path))
        self._schedule_update()

    def _get_metadata_from_filename(self, path):
        """Get metadata that we know from a filename alone."""
        return {
            'file_type': filetypes.item_file_type_for_filename(path),
        }

    def _schedule_update(self):
        """Scheduling sending updates.

        For performance reasons we try to group together database updates and
        progress updates so that we can perform them in bulk.

        Call this when we have updates from our metadata processors, or when
        we may nede to change the MetadataProgressUpdate counts.
        """
        if not self._update_scheduled:
            eventloop.add_timeout(self.UPDATE_INTERVAL,
                                  self._run_updates,
                                  'send metadata updates')
            self._update_scheduled = True

    def _run_updates(self):
        # Should this be inside an idle iterator?  It definitely runs slowly
        # when we're running mutagen on a music library, but I think that's to
        # be expected.  It seems fast enough in other cases to me - BDK
        self._update_scheduled = False
        app.bulk_sql_manager.start()
        try:
            self._process_metadata_finished()
            self._process_metadata_errors()
            self.emit('new-metadata', self.new_metadata)
        finally:
            app.bulk_sql_manager.finish()
            self._reset_new_metadata()
        self._send_progress_updates()

    def _process_metadata_finished(self):
        for (processor, path, result) in self.metadata_finished:
            try:
                status = MetadataStatus.get_by_path(path)
            except database.ObjectNotFoundError:
                logging.warn("_process_metadata_finished -- path removed: %s",
                             path)
                continue
            self._make_new_metadata_entry(status, processor, path, result)
            self.run_next_processor(status)
        self.metadata_finished = []

    def _make_new_metadata_entry(self, status, processor, path, result):
        entry = MetadataEntry(path, processor.source_name, result)
        if entry.priority >= status.max_entry_priority:
            # If this entry is going to overwrite all other metadata, then
            # we don't have to call get_metadata().  Just send the new
            # values.
            can_skip_get_metadata = True
        else:
            can_skip_get_metadata = False
        status.update_after_success(entry)
        if can_skip_get_metadata:
            self.new_metadata[path].update(result)
        else:
            self.new_metadata[path] = self.get_metadata(path)

    def _process_metadata_errors(self):
        for (processor, path) in self.metadata_errors:
            try:
                status = MetadataStatus.get_by_path(path)
            except database.ObjectNotFoundError:
                logging.warn("_process_metadata_finished -- path removed: %s",
                             path)
                continue
            status.update_after_error(processor.source_name)
            self.run_next_processor(status)
            # we only have new metadata if the error means we can set the
            # has_drm flag now
            if processor is self.moviedata_processor and status.get_has_drm():
                self.new_metadata[path].update({'has_drm': True})
        self.metadata_errors = []

    def run_next_processor(self, status):
        """Called after both success and failure of a metadata processor
        """
        # check what the next processor we should run is
        if status.mutagen_status == MetadataStatus.STATUS_NOT_RUN:
            self._run_mutagen(status.path)
        elif status.moviedata_status == MetadataStatus.STATUS_NOT_RUN:
            self._run_movie_data(status.path)
        elif status.echonest_status == MetadataStatus.STATUS_NOT_RUN:
            self._run_echonest(status.path)
        else:
            self.count_tracker.file_finished(status.path)

    def _send_progress_updates(self):
        for file_type in (u'audio', u'video'):
            target = (u'library', file_type)
            count = self.count_tracker.get_count(file_type)
            total = self.count_tracker.get_total(file_type)
            eta = None
            msg = messages.MetadataProgressUpdate(target, count, eta, total)
            msg.send_to_frontend()
