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
import time

from miro import app
from miro import clock
from miro import database
from miro import echonest
from miro import eventloop
from miro import filetags
from miro import filetypes
from miro import fileutil
from miro import messages
from miro import net
from miro import prefs
from miro import signals
from miro import workerprocess
from miro.plat.utils import (filename_to_unicode,
                             get_enmfp_executable_info)

attribute_names = set([
    'file_type', 'duration', 'album', 'album_artist', 'album_tracks',
    'artist', 'cover_art', 'screenshot', 'has_drm', 'genre',
    'title', 'track', 'year', 'description', 'rating', 'show', 'episode_id',
    'episode_number', 'season_number', 'kind', 'net_lookup_enabled',
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
    STATUS_TEMPORARY_FAILURE = u'T'
    STATUS_SKIP = u'S'

    FINISHED_STATUS_VERSION = 1

    _source_name_to_status_column = {
        u'mutagen': 'mutagen_status',
        u'movie-data': 'moviedata_status',
        u'echonest': 'echonest_status',
    }

    def setup_new(self, path, net_lookup_enabled):
        self.path = path
        self.net_lookup_enabled = net_lookup_enabled
        self.file_type = u'other'
        self.mutagen_status = self.STATUS_NOT_RUN
        self.moviedata_status = self.STATUS_NOT_RUN
        if self.net_lookup_enabled:
            self.echonest_status = self.STATUS_NOT_RUN
        else:
            self.echonest_status = self.STATUS_SKIP
        self.mutagen_thinks_drm = False
        self.echonest_id = None
        self.max_entry_priority = -1
        # current processor tracks what processor we should be running for
        # this status.  We don't save it to the database.
        self.current_processor = u'mutagen'
        # finished_status tracks if we are done running metadata processors on
        # an item.  finished status is:
        # - 0 if we haven't finished running metadata on it.
        # - A positive version code once we are done.  This version code
        #   increases as we add more metadata processors.
        # This hopefully is allows us to track if metadata processing is
        # finished, even as the database schema changes between miro versions.
        self.finished_status = 0
        self._add_to_cache()

    def setup_restored(self):
        self._set_current_processor(update_finished_status=False)
        self.db_info.db.cache.set('metadata', self.path, self)

    def copy_status(self, other_status):
        """Copy values from another metadata status object."""
        for name, field in app.db.schema_fields(MetadataStatus):
            # don't copy id or path for obvious resons.  Don't copy
            # net_lookup_enabled because we don't want the other status's
            # value to overwrite ours.  The main reason is that for device
            # items, when we copy the local item's metadata, we don't want to
            # set net_lookup_enabled to True.
            if name not in ('id', 'path', 'net_lookup_enabled'):
                setattr(self, name, getattr(other_status, name))
        # also copy current_processor, which doesn't get stored in the DB and
        # thus isn't returned by schema_fields()
        self.current_processor = other_status.current_processor
        self.signal_change()

    @classmethod
    def get_by_path(cls, path, db_info=None):
        """Get an object by its path attribute.

        We use the DatabaseObjectCache to cache status by path, so this method
        is fairly quick.
        """
        if db_info is None:
            db_info = app.db_info

        try:
            cache_value = db_info.db.cache.get('metadata', path)
        except KeyError:
            cache_value = None

        if cache_value is not None:
            return cache_value
        else:
            view = cls.make_view('path=?', (filename_to_unicode(path),),
                                 db_info=db_info)
            return view.get_singleton()

    @classmethod
    def paths_for_album(cls, album, db_info=None):
        rows = cls.select(['path',],
                          'id IN '
                          '(SELECT status_id FROM metadata p WHERE '
                          'album=? AND priority='
                          '(SELECT MAX(priority) FROM metadata c '
                          'WHERE p.status_id=c.status_id AND '
                          'NOT disabled AND album IS NOT NULL))',
                          (album,), db_info=db_info)
        return [r[0] for r in rows]

    @classmethod
    def net_lookup_enabled_view(cls, net_lookup_enabled, db_info=None):
        return cls.make_view('net_lookup_enabled=?',
                             (net_lookup_enabled,),
                             db_info=db_info)

    @classmethod
    def failed_temporary_view(cls, db_info=None):
        return cls.make_view('echonest_status=?',
                             (cls.STATUS_TEMPORARY_FAILURE,),
                             db_info=db_info)

    def _add_to_cache(self):
        if self.db_info.db.cache.key_exists('metadata', self.path):
            # duplicate path.  Lets let sqlite raise the error when we try to
            # insert things.
            logging.warn("self.path already in cache (%s)", self.path)
            return
        self.db_info.db.cache.set('metadata', self.path, self)

    def insert_into_db_failed(self):
        self.db_info.db.cache.remove('metadata', self.path)

    def remove(self):
        self.db_info.db.cache.remove('metadata', self.path)
        database.DDBObject.remove(self)

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

    def need_metadata_for_source(self, source_name):
        column_name = self._source_name_to_status_column[source_name]
        return getattr(self, column_name) == self.STATUS_NOT_RUN

    def update_after_success(self, entry, result):
        """Update after we succussfully extracted some metadata

        :param entry: MetadataEntry for the new data
        :param result: dictionary from the processor
        """
        self._set_status_column(entry.source, self.STATUS_COMPLETE)
        if (entry.priority >= self.max_entry_priority and
            entry.file_type is not None):
            self.file_type = entry.file_type
        if entry.source == 'mutagen':
            if self._should_skip_movie_data(entry):
                self.moviedata_status = self.STATUS_SKIP
            thinks_drm = entry.drm if entry.drm is not None else False
            self.mutagen_thinks_drm = thinks_drm
        elif entry.source == 'movie-data':
            if entry.file_type != u'audio':
                self.echonest_status = self.STATUS_SKIP
        elif entry.source == 'echonest' and 'echonest_id' in result:
            self.echonest_id = result['echonest_id']
        self.max_entry_priority = max(self.max_entry_priority, entry.priority)
        self._set_current_processor()
        self.signal_change()

    def set_echonest_id(self, echonest_id):
        self.echonest_id = echonest_id
        self.signal_change()

    def retry_echonest(self):
        if self.echonest_status == self.STATUS_TEMPORARY_FAILURE:
            self.echonest_status = self.STATUS_NOT_RUN
            self.signal_change()
        else:
            logging.warn("MetadataEntry.retry_echonest() called, but "
                         "echonest_status is %r", self.echonest_status)

    def _should_skip_movie_data(self, entry):
        my_ext = os.path.splitext(self.path)[1].lower()
        # we should skip movie data if:
        #   - we're sure the file is audio (mutagen misreports .ogg videos as
        #     audio)
        #   - mutagen was able to get the duration for the file
        #   - mutagen doesn't think the file has DRM
        if ((my_ext == '.oga' or not my_ext.startswith('.og')) and
            entry.file_type == 'audio' and
            entry.duration is not None and
            not entry.drm):
            return True
        # We should also skip it if mutagen couldn't identify the file and the
        # extension indicates it's a non-media file
        if entry.file_type is None and filetypes.is_other_filename(self.path):
            return True
        return False

    def update_after_error(self, source_name, error):
        """Update after we failed to extract some metadata.

        Returns the new status column value
        """
        if source_name == 'echonest' and isinstance(error, net.NetworkError):
            new_status = self.STATUS_TEMPORARY_FAILURE
        else:
            new_status = self.STATUS_FAILURE
        self._set_status_column(source_name, new_status)
        if (source_name == u'movie-data' and
            (self.mutagen_status == self.STATUS_FAILURE or
             self.file_type != u'audio')):
            # if moviedata failed and mutagen either thought the file was
            # video, or it couldn't read it, then don't
            # bother sending it to echonest.  We don't want to run the codegen
            # program.
            self.echonest_status = self.STATUS_SKIP
        if new_status != self.STATUS_TEMPORARY_FAILURE:
            self._set_current_processor()
        self.signal_change()
        return new_status

    def _set_current_processor(self, update_finished_status=True):
        """Calculate and set the current_processor attribute """
        # check what the next processor we should run is
        if self.mutagen_status == MetadataStatus.STATUS_NOT_RUN:
            self.current_processor = u'mutagen'
        elif self.moviedata_status == MetadataStatus.STATUS_NOT_RUN:
            self.current_processor = u'movie-data'
        elif self.echonest_status == MetadataStatus.STATUS_NOT_RUN:
            self.current_processor = u'echonest'
        else:
            self.current_processor = None
            if (update_finished_status and
                self.FINISHED_STATUS_VERSION > self.finished_status):
                self.finished_status = self.FINISHED_STATUS_VERSION

    def set_net_lookup_enabled(self, enabled):
        self.net_lookup_enabled = enabled
        if (enabled and
            self.echonest_status == self.STATUS_SKIP
            and self.file_type == u'audio'):
            self.echonest_status = self.STATUS_NOT_RUN
        elif not enabled and self.echonest_status == self.STATUS_NOT_RUN:
            self.echonest_status = self.STATUS_SKIP
        self._set_current_processor()
        self.signal_change()

    def rename(self, new_path):
        """Change the path for this object."""
        self.db_info.db.cache.remove('metadata', self.path)
        self.db_info.db.cache.set('metadata', new_path, self)
        self.path = new_path
        self.signal_change()

    @classmethod
    def was_running_select(cls, columns, db_info=None):
        return cls.select(columns, 'finished_status < ?',
                          values=(cls.FINISHED_STATUS_VERSION,),
                          db_info=db_info)

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
    # net_lookup_enabled is proveded by the metadata_status table, not the
    # actual metadata tables
    metadata_columns.discard('net_lookup_enabled')

    def setup_new(self, status, source, data):
        self.status_id = status.id
        self.source = source
        self.priority = MetadataEntry.source_priority_map[source]
        self.disabled = False
        # set all metadata to None by default
        for name in self.metadata_columns:
            setattr(self, name, None)
        self.__dict__.update(data)
        if source != 'user-data':
            # we only save cover_art for user-data.  Other sources save the
            # cover art using a per-album filename.
            self.cover_art = None

    def update_metadata(self, new_data):
        """Update the values for this object."""
        for name in self.metadata_columns:
            if name in new_data:
                setattr(self, name, new_data[name])
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
    def metadata_for_status(cls, status, db_info=None):
        return cls.make_view('status_id=? AND NOT disabled',
                             (status.id,),
                             order_by='priority ASC',
                             db_info=db_info)

    @classmethod
    def get_entry(cls, source, status, db_info=None):
        view = cls.make_view('source=? AND status_id=?',
                             (source, status.id),
                             db_info=db_info)
        return view.get_singleton()

    @classmethod
    def incomplete_echonest_view(cls, db_info=None):
        # if echonest didn't find the song, then title will be NULL if
        # 7digital didn't find the album, then album will be NULL.  If either
        # of those are true, then we want to retry re-querying
        return cls.make_view('source="echonest" AND '
                             '(album IS NULL or title IS NULL)',
                             db_info=None)

    @classmethod
    def set_disabled(cls, source, status, disabled, db_info=None):
        """Set/Unset the disabled flag for metadata entry.

        :returns: True if there was an entry to change
        """
        try:
            entry = cls.get_entry(source, status, db_info=None)
        except database.ObjectNotFoundError:
            return False
        else:
            entry.disabled = disabled
            entry.signal_change()
            return True

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

    - task-complete(path, result) -- we successfully extracted metadata
    - task-error(path, error) -- we failed to extract metadata
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

    def task_count(self):
        return len(self._active_tasks) + len(self._pending_tasks)

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
        if task.source_path not in self._active_tasks:
            logging.debug("%s done but already removed: %r", self.source_name,
                          task.source_path)
            return
        logging.debug("%s done: %r", self.source_name, task.source_path)
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
        logging.warn("Error running %s for %r: %s", task, task.source_path,
                     error)
        self.emit('task-error', task.source_path, error)
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

    # Cooldown time for our codegen process
    CODEGEN_COOLDOWN_TIME = 5.0

    # constants that control pausing after we get a bunch of HTTP errors.
    # These settings mean that if we get 3 errors in 5 minutes, then we will
    # pause.
    PAUSE_AFTER_HTTP_ERROR_COUNT = 3
    PAUSE_AFTER_HTTP_ERROR_TIMEOUT = 60 * 5

    # NOTE: _EchonestProcessor dosen't inherity from _TaskProcessor because it
    # handles it's work using httpclient rather than making tasks and sending
    # them to workerprocess.

    def __init__(self, code_buffer_size, cover_art_dir):
        _MetadataProcessor.__init__(self, u'echonest')
        self._code_buffer_size = code_buffer_size
        self._cover_art_dir = cover_art_dir
        # We create 3 queues to handle items at various stages of the process.
        # - _metadata_fetch_queue holds paths that we need to fetch the
        #    metadata for.  It's the first queue that paths go to
        # - _codegen_queue contains paths that we need to run the codegen
        #   executable on
        # - _echonest_queue contains paths that we need to query echonest for
        self._metadata_fetch_queue = _EchonestQueue()
        self._codegen_queue = _EchonestQueue()
        self._echonest_queue = _EchonestQueue()
        self._running_codegen = False
        self._querying_echonest = False
        self._codegen_info = get_enmfp_executable_info()
        self._codegen_cooldown_end = 0
        self._codegen_cooldown_caller = eventloop.DelayedFunctionCaller(
            self._process_queue)
        self._metadata_for_path = {}
        self._paths_in_system = set()
        self._http_error_times = collections.deque()
        self._waiting_from_http_errors = False

    def add_path(self, path, metadata_fetcher):
        """Add a path to the system.

        metadata_fetcher is used to get the metadata for that path to send to
        echonest.  We use a callable object that returns the metadata instead
        of a straight dict because we want to fetch things lazily.
        metadata_fetcher should raise a KeyError if the path is not in the
        metadata system when its called.

        :param path: path to add
        :param metadata_fetcher: callable that will return a metadata dict
        """
        if path in self._paths_in_system:
            logging.warn("_EchonestProcessor.add_path: attempt to add "
                         "duplicate path: %r", path)
            return
        self._paths_in_system.add(path)
        self._metadata_fetch_queue.add(path, metadata_fetcher)
        self._process_queue()

    def should_skip_codegen(self, metadata):
        """Determine if a file can skip the code generator.

        This is true when we have enough metadata to send to echonest.
        """
        # This check is actually pretty easy.  If we have a title, then
        # there's a good chance for a match.  If we don't then there's no
        # chance.
        return 'title' in metadata

    def _run_codegen(self, path):
        echonest.exec_codegen(self._codegen_info, path, self._codegen_callback,
                                self._codegen_errback)
        self._running_codegen = True

    def _codegen_callback(self, path, code):
        if path in self._paths_in_system:
            self._echonest_queue.add(path, code)
        else:
            logging.warn("_EchonestProcessor._codegen_callback called for "
                         "path not in system: %r", path)
        self._codegen_finished()

    def _codegen_errback(self, path, error):
        logging.warn("Error running echonest codegen for %r (%s)" %
                     (path, error))
        self.emit('task-error', path, error)
        del self._metadata_for_path[path]
        self._paths_in_system.discard(path)
        self._codegen_finished()

    def _query_echonest(self, path, code):
        if path not in self._paths_in_system:
            logging.warn("_EchonestProcessor._query_echonest() called for "
                         "path not in system: %r", path)
            return
        version = 3.15 # change to 4.11 for echoprint
        metadata = self._metadata_for_path.pop(path)
        echonest.query_echonest(path, self._cover_art_dir, code, version,
                                metadata, self._echonest_callback,
                                self._echonest_errback)
        self._querying_echonest = True

    def _echonest_callback(self, path, metadata):
        if path in self._paths_in_system:
            logging.debug("Got echonest data for %s:\n%s", path, metadata)
            self._paths_in_system.discard(path)
            self.emit('task-complete', path, metadata)
        else:
            logging.warn("_EchonestProcessor._echonest_callback called for "
                         "path not in system: %r", path)
        self._querying_echonest = False
        self._process_queue()

    def _echonest_errback(self, path, error):
        logging.warn("Error running echonest for %s (%s)" % (path, error))
        self._paths_in_system.discard(path)
        self._querying_echonest = False
        if isinstance(error, net.NetworkError):
            self._http_error_times.append(clock.clock())
            if (len(self._http_error_times) >
                self.PAUSE_AFTER_HTTP_ERROR_COUNT):
                self._http_error_times.popleft()
        self.emit('task-error', path, error)
        self._process_queue()

    def _process_queue(self):
        if self._should_process_metadata_fetch_queue():
            self._process_metadata_fetch_queue()
        if self._should_process_echonest_queue():
            self._process_echonest_queue()
        if self._should_process_codegen_queue():
            self._run_codegen(self._codegen_queue.pop())

    def _should_process_metadata_fetch_queue(self):
        # Try not to fetch metadata more quickly than we need to.  Only do it
        # if the other queues waiting for us
        return (self._metadata_fetch_queue and
                len(self._codegen_queue) + len(self._echonest_queue) < 10)

    def _should_process_codegen_queue(self):
        if not (self._codegen_queue and
                not self._running_codegen and
                len(self._echonest_queue) < self._code_buffer_size):
            return False
        cooldown_left = self._codegen_cooldown_end - clock.clock()
        if cooldown_left > 0:
            self._codegen_cooldown_caller.call_after_timeout(cooldown_left)
            return False
        return True

    def _should_process_echonest_queue(self):
        return (self._echonest_queue and not self._querying_echonest and
                not self._waiting_from_http_errors)

    def _process_echonest_queue(self):
        if not self._should_pause_from_http_errors():
            self._query_echonest(*self._echonest_queue.pop())
        else:
            # we've gotten too many HTTP errors recently and are backing
            # off sending new requests.  Add a timeout and try again then
            if not self._waiting_from_http_errors:
                name = 'restart echonest queue after http error'
                eventloop.add_timeout(self.PAUSE_AFTER_HTTP_ERROR_TIMEOUT,
                                      self._restart_after_http_errors, name)
                self._waiting_from_http_errors = True

    def _process_metadata_fetch_queue(self):
        while self._metadata_fetch_queue:
            path, metadata_fetcher = self._metadata_fetch_queue.pop()
            try:
                metadata = metadata_fetcher()
            except StandardError:
                # log exceptions and try the next item in the queue.
                logging.warn("_process_metadata_fetch_queue: metadata_fetcher "
                             "raised exception (path: %r, fetcher: %s)",
                             path, metadata_fetcher, exc_info=True)
                continue
            else:
                self._metadata_for_path[path] = metadata
                if not self.should_skip_codegen(metadata):
                    self._codegen_queue.add(path)
                else:
                    self._echonest_queue.add(path, None)
                return

    def _codegen_finished(self):
        self._running_codegen = False
        self._codegen_cooldown_end = (clock.clock() +
                                      self.CODEGEN_COOLDOWN_TIME)
        self._process_queue()

    def _should_pause_from_http_errors(self):
        """Have we seen enough HTTP errors recently that we should pause
        running the queue?
        """
        return ((len(self._http_error_times) ==
                self.PAUSE_AFTER_HTTP_ERROR_COUNT) and
                self._http_error_times[0] > clock.clock() -
                self.PAUSE_AFTER_HTTP_ERROR_TIMEOUT)

    def _restart_after_http_errors(self):
        self._waiting_from_http_errors = False
        self._process_queue()

    def task_count(self):
        return (len(self._metadata_fetch_queue) +
                len(self._codegen_queue) +
                len(self._echonest_queue))

    def remove_tasks_for_paths(self, paths):
        path_set = set(paths)
        self._metadata_fetch_queue.remove_paths(path_set)
        self._echonest_queue.remove_paths(path_set)
        self._codegen_queue.remove_paths(path_set)
        self._paths_in_system -= path_set
        for path in path_set.intersection(self._metadata_for_path.keys()):
            del self._metadata_for_path[path]
        # since we may have deleted active paths, process the new ones
        self._process_queue()

class ProgressCountTracker(object):
    """Helps MetadataManager keep track of counts for MetadataProgressUpdate

    ProgressCountTracker counts the total number of items that need metadata
    processing, the number of items finished, and the number of items that
    have finished mutagen/movie-data but still need internet metadata.  Once
    all items are finished, then the counts reset.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset the counts."""
        self.all_files = set()
        self.finished_local = set()
        self.finished = set()
        self.all_sets = (self.all_files, self.finished_local, self.finished)

    def get_count_info(self):
        """Get the current count info.

        This method gets three counts:
        - total count: total number of files to be processed
        - finished_local count: number of files that have finished
        mutagen/moviedata, but not echonest
        - finished_count count: number of files that have finished all
        processing

        :returns: the tuple (total, finished_local, finished_count)
        """
        return (len(self.all_files),
                len(self.finished_local),
                len(self.finished))

    def file_started(self, path, initial_metadata):
        """Add a file to the counts."""
        self.all_files.add(path)

    def file_net_lookup_restarted(self, path):
        self.file_started(path, {})
        self.file_finished_local_processing(path)

    def file_updated(self, path, new_metadata):
        """Call this as we get new metadata."""
        # subclasses can deal with this, but we don't
        pass

    def file_finished_local_processing(self, path):
        """Remove a file from our counts."""
        if path not in self.all_files:
            logging.warn("file_finished_local_processing called for a file "
                         "that we're not tracking: %s", path)
            return
        self.finished_local.add(path)

    def file_finished(self, path):
        """Remove a file from our counts."""
        if path not in self.all_files:
            logging.warn("file_finished called for a file that we're "
                         "not tracking: %s", path)
            return
        self.finished.add(path)
        self.finished_local.add(path)
        if len(self.finished) == len(self.all_files):
            self.reset()

    def file_moved(self, old_path, new_path):
        """Handle a file changing names."""
        if old_path not in self.all_files:
            logging.warn("file_moved called for a file that we're "
                         "not tracking: %s", old_path)
            return
        for count_set in self.all_sets:
            if old_path in count_set:
                count_set.remove(old_path)
                count_set.add(new_path)

    def remove_file(self, path):
        """Remove a file from the counts.

        This is different than finishing the file, since this will lower the
        total count, rather than increase the finished count.
        """
        for count_set in self.all_sets:
            count_set.discard(path)
        if len(self.finished) == len(self.all_files):
            self.reset()

class LibraryProgressCountTracker(object):
    """Tracks progress counts for the library tabs.

    This has the same API as ProgressCountTracker for file tracking (the
    functions file_started, file_updated, file_finished, etc), but
    get_count_info() is different because it keeps separate counts for the
    video and audio tabs, based on the file_type for each path.
    """
    def __init__(self):
        self.trackers = collections.defaultdict(ProgressCountTracker)
        self.file_types = {}

    def get_count_info(self, file_type):
        """Get the count info for the audio, video, or other tabs

        :param file_type: file type to get the count info for
        :returns: the tuple (total, finished_local, finished_count)
        """
        return self.trackers[file_type].get_count_info()

    def file_started(self, path, initial_metadata):
        file_type = initial_metadata.get('file_type', u'other')
        self.trackers[file_type].file_started(path, initial_metadata)
        self.file_types[path] = file_type

    def file_net_lookup_restarted(self, path):
        # assume that the file is audio, since we're only do internet lookups
        # for those files
        file_type = u'audio'
        # start the file, then immediately move it to the net lookup stage.
        tracker = self.trackers[file_type]
        tracker.file_started(path, {})
        tracker.file_finished_local_processing(path)
        self.file_types[path] = file_type

    def file_moved(self, old_path, new_path):
        try:
            tracker = self._get_tracker_for_path(old_path)
        except KeyError:
            logging.warn("_get_tracker_for_path raised KeyError in "
                         "file_moved() old: %s new: %s", old_path, new_path)
        else:
            file_type = self.file_types.pop(old_path)
            tracker.file_moved(old_path, new_path)
            self.file_types[new_path] = file_type

    def file_finished(self, path):
        try:
            tracker = self._get_tracker_for_path(path)
        except KeyError:
            logging.warn("_get_tracker_for_path raised KeyError in "
                         "file_finished (%s)", path)
        else:
            tracker.file_finished(path)

    def file_finished_local_processing(self, path):
        try:
            tracker = self._get_tracker_for_path(path)
        except KeyError:
            logging.warn("_get_tracker_for_path raised KeyError in "
                         "file_finished_local_processing (%s)", path)
        else:
            tracker.file_finished_local_processing(path)

    def _get_tracker_for_path(self, path):
        """Get the ProgressCountTracker for a file.

        :returns: ProgressCountTracker or None if we couldn't look it up
        :raises: KeyError path not in our file_types dict
        """
        return self.trackers[self.file_types[path]]

    def file_updated(self, path, metadata):
        if 'file_type' not in metadata:
            # no new file type, we don't have to change anything
            return
        new_file_type = metadata['file_type']
        try:
            old_file_type = self.file_types[path]
        except KeyError:
            logging.warn("file_updated: couldn't lookup file type for: %s",
                         path)
            return
        if old_file_type == new_file_type:
            return
        old_tracker = self.trackers[old_file_type]
        new_tracker = self.trackers[new_file_type]

        if path not in old_tracker.all_files:
            logging.warn("file_changed_type called for a file we're not "
                         "tracking: %s", path)
            return

        new_tracker.file_started(path, metadata)
        if path in old_tracker.finished:
            new_tracker.file_finished(path)
        elif path in old_tracker.finished_local:
            new_tracker.file_finished_local_processing(path)

        old_tracker.remove_file(path)
        self.file_types[path] = new_file_type

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

    def file_being_processed(self, path):
        return path in self.file_types

class MetadataManagerBase(signals.SignalEmitter):
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
    RETRY_TEMPORARY_INTERVAL = 3600
    # how often to re-try net lookups that have failed
    NET_LOOKUP_RETRY_INTERVAL = 60 * 60 * 24 * 7 # 1 week

    def __init__(self, cover_art_dir, screenshot_dir, db_info=None):
        signals.SignalEmitter.__init__(self)
        if db_info is None:
            self.db_info = app.db_info
        else:
            self.db_info = db_info
        self.closed = False
        self.create_signal('new-metadata')
        self.cover_art_dir = cover_art_dir
        self.screenshot_dir = screenshot_dir
        self.echonest_cover_art_dir = os.path.join(cover_art_dir, 'echonest')
        self.mutagen_processor = _TaskProcessor(u'mutagen', 100)
        self.moviedata_processor = _TaskProcessor(u'movie-data', 100)
        self.echonest_processor = _EchonestProcessor(
            5, self.echonest_cover_art_dir)
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
        self.count_tracker = self.make_count_tracker()
        self._send_net_lookup_counts_caller = eventloop.DelayedFunctionCaller(
            self._send_net_lookup_counts)
        # List of (processor, path, metadata) tuples for metadata since the
        # last run_updates() call
        self.metadata_finished = []
        # List of (processor, path) tuples for failed metadata since the last
        # run_updates() call
        self.metadata_errors = []
        self._reset_new_metadata()
        self._run_update_caller = eventloop.DelayedFunctionCaller(
            self.run_updates)
        self._retry_temporary_failure_caller = \
                eventloop.DelayedFunctionCaller(self.retry_temporary_failures)
        self._calc_incomplete()
        self._retry_net_lookup_caller = \
                eventloop.DelayedFunctionCaller(self.retry_net_lookup)
        self._retry_net_lookup_entries = {}
        self._setup_path_placeholders()
        self._setup_net_lookup_count()
        # send initial NetLookupCounts message
        self._send_net_lookup_counts()

    def _reset_new_metadata(self):
        self.new_metadata = collections.defaultdict(dict)

    def check_image_directories(self, log_warnings=False):
        """Check that our echonest and screenshot directories exist

        If they don't, we will try to create them.

        This method should be called often so that we recover quickly.  The
        current policy is to call it before adding a task that might need to
        write to the directories.

        :param log_warnings: should we print errors out to the log file?
        """
        directories = (
            self.cover_art_dir, 
            self.echonest_cover_art_dir,
            self.screenshot_dir,
        )
        for path in directories:
            if not fileutil.exists(path):
                try:
                    fileutil.makedirs(path)
                except EnvironmentError, e:
                    if log_warnings:
                        logging.warn("MetadataManager: error creating: %s" 
                                     "(%s)", path, e)

    def _setup_path_placeholders(self):
        """Add None values to the cache for all MetadataStatus objects

        This makes path_in_system() work since it checks if the key exists.
        However, we don't actually want to load the objects yet, since this is
        called pretty early in the startup process.
        """
        rows = MetadataStatus.select(["path"], db_info=self.db_info)
        for row in rows:
            self.db_info.db.cache.set('metadata', row[0], None)
        # also set up total_count here, since it's convenient.  total_count
        # tracks the total number of paths in the system
        self.total_count = len(rows)

    def _setup_net_lookup_count(self):
        """Set up net_lookup_count

        net_lookup_count tracks the number of paths in the system with
        net_lookup_enabled=True.
        """
        cursor = self.db_info.db.cursor
        cursor.execute("SELECT COUNT(1) "
                       "FROM metadata_status "
                       "WHERE net_lookup_enabled=1")
        self.net_lookup_count = cursor.fetchone()[0]

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

    def _translate_path(self, path):
        """Translate a path value from the db to a filesystem path.
        """
        return path

    def _untranslate_path(self, path):
        """Reverse the work of _translate_path."""
        return path

    def add_file(self, path, local_path=None):
        """Add a new file to the metadata syestem

        :param path: path to the file
        :param local_path: path to a local file to get initial metadata for
        :returns initial metadata for the file
        :raises ValueError: path is already in the system
        """
        if self.closed:
            raise ValueError("%r added to closed MetadataManager" % path)
        if self.path_in_system(path):
            raise ValueError("%r already added" % path)

        status = MetadataStatus(path, self.net_lookup_enabled_default(),
                                db_info=self.db_info)
        if status.net_lookup_enabled:
            self.net_lookup_count += 1
        self.total_count += 1
        initial_metadata = self._get_metadata_from_filename(path)
        initial_metadata['net_lookup_enabled'] = status.net_lookup_enabled
        if local_path is not None:
            local_status = MetadataStatus.get_by_path(local_path)
            status.copy_status(MetadataStatus.get_by_path(local_path))
            for entry in MetadataEntry.metadata_for_status(local_status):
                entry_metadata = entry.get_metadata()
                initial_metadata.update(entry_metadata)
                MetadataEntry(status, entry.source, entry_metadata,
                              db_info=self.db_info)
        if status.current_processor is not None:
            self.count_tracker.file_started(path, initial_metadata)
            self.run_next_processor(status)
        self._run_update_caller.call_after_timeout(self.UPDATE_INTERVAL)
        self._send_net_lookup_counts_caller.call_when_idle()
        return initial_metadata

    def net_lookup_enabled_default(self):
        """net_lookup_enabled value for new MetadataStatus objects."""
        return app.config.get(prefs.NET_LOOKUP_BY_DEFAULT)

    def path_in_system(self, path):
        """Test if a path is in the metadata system."""
        return self.db_info.db.cache.key_exists('metadata', path)

    def worker_task_count(self):
        return (self.mutagen_processor.task_count() +
                self.moviedata_processor.task_count() +
                self.echonest_processor.task_count())

    def _cancel_processing_paths(self, paths):
        paths = [self._translate_path(p) for p in paths]
        workerprocess.cancel_tasks_for_files(paths)
        for processor in self.metadata_processors:
            processor.remove_tasks_for_paths(paths)

    def remove_file(self, path):
        """Remove a file from the metadata system.

        This is basically equivelent to calling remove_files([path]), except
        that it doesn't start the bulk_sql_manager.
        """
        paths = [path]
        self._remove_files(paths)

    def remove_files(self, paths):
        """Remove files from the metadata system.

        All queued mutagen and movie data calls will be canceled.

        :param paths: paths to remove
        :raises KeyError: path not in the metadata system
        """
        app.bulk_sql_manager.start()
        try:
            self._remove_files(paths)
        finally:
            app.bulk_sql_manager.finish()

    def close(self):
        """
        Close the MetadataExtractor.  Cancel anything in progress, and don't
        allow new requests.
        """
        if self.closed: # already closed
            return
        self.closed = True
        paths = [r[0] for r in
                 MetadataStatus.select(['path'], db_info=self.db_info)]
        self._cancel_processing_paths(paths)

    def _remove_files(self, paths):
        """Does the work for remove_file and remove_files"""
        self._cancel_processing_paths(paths)
        for path in paths:
            try:
                status = self._get_status_for_path(path)
            except KeyError:
                logging.warn("MetadataManager._remove_files: KeyError "
                             "getting status for %r", path)
                continue
            if status.net_lookup_enabled:
                self.net_lookup_count -= 1
            self.total_count -= 1
            for entry in MetadataEntry.metadata_for_status(status,
                                                           self.db_info):
                if entry.screenshot is not None:
                    self.remove_screenshot(entry.screenshot)
                entry.remove()
            status.remove()
            if status.current_processor is not None:
                self.count_tracker.file_finished(path)
        self._run_update_caller.call_after_timeout(self.UPDATE_INTERVAL)
        self._send_net_lookup_counts_caller.call_when_idle()

    def remove_screenshot(self, screenshot):
        fileutil.delete(screenshot)

    def will_move_files(self, paths):
        """Prepare for files to be moved

        All queued mutagen and movie data calls will be put on hold until
        file_moved() is called.

        :param paths: list of paths that will be moved
        """
        self._cancel_processing_paths(paths)

    def file_moved(self, old_path, new_path):
        """Call this after a file has been moved to a new location.

        Queued mutagen and movie data calls will be restarted.

        :param move_info: list of (old_path, new_path) tuples
        """
        if self.closed:
            raise ValueError("%r moved to %r on closed MetadataManager" % (
                    old_path, new_path))

        try:
            status = self._get_status_for_path(old_path)
        except KeyError:
            logging.warn("_process_files_moved: %s not in DB", old_path)
            return
        if self.db_info.db.cache.key_exists('metadata', new_path):
            # There's already an entry for the new status.  What to do
            # here?  Let's use the new one
            logging.warn("_process_files_moved: already an object for "
                         "%s (old path: %s)" % (new_path, status.path))
            self.count_tracker.file_finished(status.path)
            self.remove_file(status.path)
            return

        status.rename(new_path)
        if status.mutagen_status == MetadataStatus.STATUS_NOT_RUN:
            self._run_mutagen(new_path)
        elif status.moviedata_status == MetadataStatus.STATUS_NOT_RUN:
            self._run_movie_data(new_path)
        self.count_tracker.file_moved(old_path, new_path)

    def get_metadata(self, path):
        """Get metadata for a path

        :param path: path to the file
        :returns: dict of metadata
        :raises KeyError: path not in the metadata system
        """
        status = self._get_status_for_path(path)

        metadata = self._get_metadata_from_filename(path)
        for entry in MetadataEntry.metadata_for_status(status, self.db_info):
            entry_metadata = entry.get_metadata()
            metadata.update(entry_metadata)
        metadata['has_drm'] = status.get_has_drm()
        metadata['net_lookup_enabled'] = status.net_lookup_enabled
        self._add_cover_art(metadata)
        return metadata

    def refresh_metadata_for_paths(self, paths):
        """Send the new-metadata signal with the full metadata for paths.

        The metadata dicts will include None values to indicate metadata we
        don't have, unlike normal.  This means that we can erase metadata
        from items if it is no longer present.
        """

        new_metadata = {}
        for p in paths:
            # make sure we include None values
            metadata = dict((name, None) for name in attribute_names)
            metadata.update(self.get_metadata(p))
            new_metadata[p] = metadata
        self.emit("new-metadata", new_metadata)

    def _add_cover_art(self, metadata):
        """Add the cover art path to a metadata dict """

        # if the user hasn't explicitly set the cover art for an item, get it
        # using the album.
        if 'album' in metadata and 'cover_art' not in metadata:
            filename = filetags.calc_cover_art_filename(metadata['album'])
            mutagen_path = os.path.join(self.cover_art_dir, filename)
            echonest_path = os.path.join(self.cover_art_dir, 'echonest',
                                         filename)
            if os.path.exists(echonest_path):
                metadata['cover_art'] = echonest_path
            elif os.path.exists(mutagen_path):
                metadata['cover_art'] = mutagen_path

    def set_user_data(self, path, user_data):
        """Update metadata based on user-inputted data

        :raises KeyError: path not in the metadata system
        """
        if self.closed:
            raise ValueError(
                "%r called set_user_data on closed MetadataManager" % path)
        # make sure that our MetadataStatus object exists
        status = self._get_status_for_path(path)
        try:
            # try to update the current entry
            current_entry = MetadataEntry.get_entry(u'user-data', status,
                                                    self.db_info)
            current_entry.update_metadata(user_data)
        except database.ObjectNotFoundError:
            # make a new entry if none exists
            MetadataEntry(status, u'user-data', user_data, db_info=self.db_info)

    def set_net_lookup_enabled(self, paths, enabled):
        """Set if we should do an internet lookup for a list of paths

        :param paths: paths to change or None to change it for all entries
        :param enabled: should we do internet lookups for paths?
        """
        paths_to_refresh = []
        paths_to_cancel = []
        paths_to_start = []
        to_change = []

        if paths is not None:
            for path in paths:
                try:
                    status = MetadataStatus.get_by_path(path, self.db_info)
                    if status.net_lookup_enabled != enabled:
                        to_change.append(status)
                except database.ObjectNotFoundError:
                    logging.warn("set_net_lookup_enabled() "
                                 "path not in system: %s", path)
        else:
            view = MetadataStatus.net_lookup_enabled_view(not enabled,
                                                          self.db_info)
            to_change = list(view)

        app.bulk_sql_manager.start()
        try:
            for status in to_change:
                old_current_processor = status.current_processor
                status.set_net_lookup_enabled(enabled)
                if MetadataEntry.set_disabled('echonest', status, not enabled,
                                              self.db_info):
                    paths_to_refresh.append(status.path)
                # Changing the net_lookup value may mean we have to send the
                # path through echonest
                if (old_current_processor is None and
                    status.current_processor == 'echonest'):
                    paths_to_start.append(status.path)
                elif (status.current_processor is None and
                      old_current_processor == 'echonest'):
                    paths_to_cancel.append(status.path)
        finally:
            app.bulk_sql_manager.finish()

        if paths_to_cancel:
            self.echonest_processor.remove_tasks_for_paths(paths_to_cancel)

        for path in paths_to_start:
            # get_metadata() is sometimes more accurate than
            # _get_metadata_from_filename() but slower.  Let's go for speed.
            metadata = self._get_metadata_from_filename(path)
            self.count_tracker.file_started(path, metadata)
            self._run_echonest(path)

        if paths_to_refresh:
            self.refresh_metadata_for_paths(paths_to_refresh)

        if enabled:
            self.net_lookup_count += len(to_change)
        else:
            self.net_lookup_count -= len(to_change)
        # call _send_net_lookup_counts() immediately because we want the
        # frontend to update the counts before it un-disables the buttons.
        self._send_net_lookup_counts_caller.call_now()
        self._send_progress_updates()

    def set_net_lookup_enabled_for_all(self, enabled):
        """Set if we should do an internet lookup for all current paths"""
        self.set_net_lookup_enabled(None, enabled)
        messages.SetNetLookupEnabledFinished().send_to_frontend()

    def _send_net_lookup_counts(self):
        m = messages.NetLookupCounts(self.net_lookup_count, self.total_count)
        m.send_to_frontend()

    def _calc_incomplete(self):
        """Figure out which metadata status objects we should restart.

        We have to call this method on startup, but we don't want to start
        doing any work until restart_incomplete() is called.  So we just save
        the IDs of the rows to restart.
        """
        results = MetadataStatus.was_running_select(['id'], self.db_info)
        self.restart_ids = [row[0] for row in results]

    def restart_incomplete(self):
        """Restart extractors for files with incomplete metadata

        This method queues calls to mutagen, movie data, etc.
        """
        for id_ in self.restart_ids:
            try:
                status = MetadataStatus.get_by_id(id_, self.db_info)
            except database.ObjectNotFoundError:
                continue # just ignore deleted objects
            self.run_next_processor(status)
            # get_metadata() is sometimes more accurate than
            # _get_metadata_from_filename() but slower.  Let's go for speed.
            metadata = self._get_metadata_from_filename(status.path)
            self.count_tracker.file_started(status.path, metadata)

        del self.restart_ids
        self._run_update_caller.call_after_timeout(self.UPDATE_INTERVAL)

    def schedule_retry_net_lookup(self):
        last_refetch = app.config.get(prefs.LAST_RETRY_NET_LOOKUP)
        if not last_refetch:
            # never have done a refetch, do it in 10 minutes
            timeout = 600
        else:
            timeout = (last_refetch + self.NET_LOOKUP_RETRY_INTERVAL -
                       time.time())
        self._retry_net_lookup_caller.call_after_timeout(timeout)

    def retry_net_lookup(self):
        """Re-download incomplete data from internet sources.  """
        logging.info("Retrying incomplete internet lookups")
        self._retry_net_lookup_caller.cancel_call()
        for entry in MetadataEntry.incomplete_echonest_view(self.db_info):
            try:
                status = MetadataStatus.get_by_id(entry.status_id,
                                                  self.db_info)
            except database.ObjectNotFoundError:
                logging.warn("retry_net_lookup: MetadataStatus not found: %i",
                             entry.status_id)
                continue
            # check that we aren't already running metadata lookups for the
            # file
            if status.current_processor is not None:
                logging.warn("retry_net_lookup: current_processor is %s",
                             status.current_processor)
                continue
            if not status.net_lookup_enabled:
                continue
            if status.path in self._retry_net_lookup_entries:
                # already retrying
                logging.info("retry_net_lookup: already retrying %r",
                             status.path)
                continue
            self.count_tracker.file_net_lookup_restarted(status.path)
            self._run_echonest(status.path, status.echonest_id)
            self._retry_net_lookup_entries[status.path] = entry

        app.config.set(prefs.LAST_RETRY_NET_LOOKUP, int(time.time()))

    def retry_temporary_failures(self):
        app.bulk_sql_manager.start()
        try:
            for status in MetadataStatus.failed_temporary_view(self.db_info):
                status.retry_echonest()
                self.run_next_processor(status)
        finally:
            app.bulk_sql_manager.finish()

    def _get_status_for_path(self, path):
        """Get a MetadataStatus object for a given path."""
        try:
            return MetadataStatus.get_by_path(path, self.db_info)
        except database.ObjectNotFoundError:
            raise KeyError(path)

    def _run_mutagen(self, path):
        """Run mutagen on a path."""
        self.check_image_directories()
        path = self._translate_path(path)
        task = workerprocess.MutagenTask(path, self.cover_art_dir)
        if not self.in_bulk_add():
            self.mutagen_processor.add_task(task)
        else:
            self.pending_mutagen_tasks.append(task)

    def _run_movie_data(self, path):
        """Run the movie data program on a path."""
        self.check_image_directories()
        path = self._translate_path(path)
        task = workerprocess.MovieDataProgramTask(path, self.screenshot_dir)
        self.moviedata_processor.add_task(task)

    def _run_echonest(self, path, echonest_id=None):
        """Run echonest and other internet queries on a path."""
        self.check_image_directories()
        def metadata_fetcher():
            metadata = self.get_metadata(path)
            # make sure to get metadata that we just created but haven't saved
            # yet because we're doing a bulk insert
            if path in self.new_metadata:
                metadata.update(self.new_metadata[path])

            # we only send a subset of the metadata to echonest and some of
            # the key names are different
            echonest_metadata = {}
            for key in ('title', 'artist', 'album', 'duration'):
                try:
                    echonest_metadata[key] = metadata[key]
                except KeyError:
                    pass
            if echonest_id:
                echonest_metadata['echonest_id'] = echonest_id
            return echonest_metadata
        self.echonest_processor.add_path(self._translate_path(path),
                                         metadata_fetcher)

    def _on_task_complete(self, processor, path, result):
        path = self._untranslate_path(path)
        self.metadata_finished.append((processor, path, result))
        self._run_update_caller.call_after_timeout(self.UPDATE_INTERVAL)

    def _on_task_error(self, processor, path, error):
        path = self._untranslate_path(path)
        self.metadata_errors.append((processor, path, error))
        self._run_update_caller.call_after_timeout(self.UPDATE_INTERVAL)

    def _get_metadata_from_filename(self, path):
        """Get metadata that we know from a filename alone."""
        return {
            'file_type': filetypes.item_file_type_for_filename(path),
        }

    def run_updates(self):
        """Run any pending metadata updates.

        As we get metadata in from extractors, we store it up and send one big
        update at a time.  Normally this is scheduled using a timeout, we also
        need to call it at shutdown to flush the pending updates.
        """
        if self.closed:
            return
        # Should this be inside an idle iterator?  It definitely runs slowly
        # when we're running mutagen on a music library, but I think that's to
        # be expected.  It seems fast enough in other cases to me - BDK
        new_metadata_copy = self.new_metadata
        app.bulk_sql_manager.start()
        try:
            self._process_metadata_finished()
            self._process_metadata_errors()
            self.emit('new-metadata', self.new_metadata)
        finally:
            self._reset_new_metadata()
            try:
                app.bulk_sql_manager.finish()
            except StandardError, e:
                new_metadata_debug_string = '\n'.join(
                    '%s: %s' % (os.path.basename(k), v)
                    for k, v in new_metadata_copy.items())
                logging.warn("Error adding new metadata: %s. new_metadata\n%s",
                             e, new_metadata_debug_string)
                raise
        self._send_progress_updates()

    def _process_metadata_finished(self):
        for (processor, path, result) in self.metadata_finished:
            try:
                status = MetadataStatus.get_by_path(path, self.db_info)
            except database.ObjectNotFoundError:
                logging.warn("_process_metadata_finished -- path removed: %r",
                             path)
                continue
            if path not in self._retry_net_lookup_entries:
                self._process_metadata_result(status, processor, path, result)
            else:
                retry_entry = self._retry_net_lookup_entries.pop(path)
                if retry_entry.id_exists():
                    self._process_metadata_result_net_retry(status,
                                                            retry_entry, path,
                                                            result)
                else:
                    logging.warn("_process_metadata_finished -- entry "
                                 "removed while retrying net lookup: %r",
                                 path)

        self.metadata_finished = []

    def _process_metadata_result(self, status, processor, path, result):
        if not status.need_metadata_for_source(processor.source_name):
            logging.warn("_process_metadata_finished -- got duplicate "
                         "metadata for %s (source: %s)", path,
                         processor.source_name)
            return
        self._make_new_metadata_entry(status, processor, path, result)
        self.count_tracker.file_updated(path, result)
        self.run_next_processor(status)
        if status.current_processor == u'echonest':
            self.count_tracker.file_finished_local_processing(status.path)

    def _process_metadata_result_net_retry(self, status, entry, path, result):
        if status.echonest_id is None and 'echonest_id' in result:
            status.set_echonest_id(result['echonest_id'])
        entry.update_metadata(result)
        self.count_tracker.file_finished(path)
        self.new_metadata[path].update(result)

    def _make_new_metadata_entry(self, status, processor, path, result):
        # pop off created_cover_art, that's for us not the MetadataEntry
        created_cover_art = result.pop('created_cover_art', False)
        entry = MetadataEntry(status, processor.source_name, result,
                              db_info=self.db_info)
        if entry.priority >= status.max_entry_priority:
            # If this entry is going to overwrite all other metadata, then
            # we don't have to call get_metadata().  Just send the new
            # values.
            can_skip_get_metadata = True
        else:
            can_skip_get_metadata = False
        status.update_after_success(entry, result)
        if can_skip_get_metadata:
            self.new_metadata[path].update(result)
        else:
            self.new_metadata[path] = self.get_metadata(path)
        # add cover-art-path for other items in the same album
        if created_cover_art and 'album' in self.new_metadata[path]:
            album = self.new_metadata[path]['album']
            cover_art = self.new_metadata[path]['cover_art']
            for path in MetadataStatus.paths_for_album(album, self.db_info):
                self.new_metadata[path]['cover_art'] = cover_art

    def _process_metadata_errors(self):
        for (processor, path, error) in self.metadata_errors:
            try:
                status = MetadataStatus.get_by_path(path, self.db_info)
            except database.ObjectNotFoundError:
                logging.warn("_process_metadata_finished -- path removed: %s",
                             path)
                continue
            processor_status = status.update_after_error(
                processor.source_name, error)
            if processor_status != status.STATUS_TEMPORARY_FAILURE:
                self.run_next_processor(status)
            if status.current_processor == u'echonest':
                self.count_tracker.file_finished_local_processing(status.path)
            # we only have new metadata if the error means we can set the
            # has_drm flag now
            if processor is self.moviedata_processor and status.get_has_drm():
                self.new_metadata[path].update({'has_drm': True})
            if processor_status == status.STATUS_TEMPORARY_FAILURE:
                self._retry_temporary_failure_caller.call_after_timeout(
                    self.RETRY_TEMPORARY_INTERVAL)
        self.metadata_errors = []

    def run_next_processor(self, status):
        """Called after both success and failure of a metadata processor
        """
        # check what the next processor we should run is
        if status.current_processor == u'mutagen':
            self._run_mutagen(status.path)
        elif status.current_processor == u'movie-data':
            self._run_movie_data(status.path)
        elif status.current_processor == u'echonest':
            self._run_echonest(status.path)
        else:
            self.count_tracker.file_finished(status.path)

    def _send_progress_updates(self):
        for file_type in (u'audio', u'video'):
            target = (u'library', file_type)
            count_info = self.count_tracker.get_count_info(file_type)
            total, finished_local, finished = count_info
            eta = None
            msg = messages.MetadataProgressUpdate(target, finished,
                                                  finished_local, eta, total)
            msg.send_to_frontend()

class LibraryMetadataManager(MetadataManagerBase):
    """MetadataManager for the user's audio/video library."""

    def make_count_tracker(self):
        return LibraryProgressCountTracker()

class DeviceMetadataManager(MetadataManagerBase):
    """MetadataManager for devices."""

    def __init__(self, db_info, device_id, mount):
        cover_art_dir = os.path.join(mount, '.miro', 'cover-art')
        screenshot_dir = os.path.join(mount, '.miro', 'screenshots')
        MetadataManagerBase.__init__(self, cover_art_dir, screenshot_dir,
                                     db_info)
        self.mount = mount
        self.device_id = device_id
        # FIXME: should we wait to restart incomplete metadata?
        self.restart_incomplete()

    def net_lookup_enabled_default(self):
        """For devices we always want net_lookup_enabled to be False.

        See #18788.
        """
        return False

    def set_net_lookup_enabled(self, paths, enabled):
        # net_lookup_enabled should be False for device items and never
        # change.  Log a warning if we call set_net_lookup_enabled
        logging.warn("DeviceMetadataManager.set_net_lookup_enabled() called")
        return

    def make_count_tracker(self):
        # for devices we just use a simple count tracker
        return ProgressCountTracker()

    def get_metadata(self, path):
        metadata = MetadataManagerBase.get_metadata(self, path)
        # device items expect cover art and screenshots to be relative to
        # the device mount
        for key in ('cover_art', 'screenshot'):
            if key in metadata:
                metadata[key] = self._untranslate_path(metadata[key])
        return metadata

    def _translate_path(self, path):
        """Translate a path value from the db to a filesystem path.
        """
        return os.path.join(self.mount, path)

    def _untranslate_path(self, path):
        """Translate a path value from the db to a filesystem path.
        """
        if path.startswith(self.mount):
            return os.path.relpath(path, self.mount)
        else:
            raise ValueError("%s is not relative to %s" % (path, self.mount))

    def _send_progress_updates(self):
        target = (u'device', self.device_id)
        count_info = self.count_tracker.get_count_info()
        total, finished_local, finished = count_info
        eta = None
        msg = messages.MetadataProgressUpdate(target, finished,
                                              finished_local, eta, total)
        msg.send_to_frontend()

    def _send_net_lookup_counts(self):
        # This isn't supported for devices yet
        pass

def remove_invalid_device_metadata(device):
    """Remove Metadata objects that don't correspond to DeviceItems.

    If we have a path in the metadata_status table, but not in the device_item
    table, then we get an error when trying to add the device item (see
    #19847).  So remove the metadata status objects.
    """
    where = 'path not in (SELECT filename FROM device_item)'
    for status in MetadataStatus.make_view(where, db_info=device.db_info):
        logging.warn("removing invalid metadata status (%s, %s)", device.mount,
                     status.path)
        status.remove()
