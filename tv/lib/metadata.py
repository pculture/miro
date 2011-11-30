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
"""

import logging
import fileutil
import os.path

import sqlite3

from miro.util import returns_unicode
from miro import app
from miro import coverart
from miro import database
from miro import filetags
from miro import filetypes
from miro import prefs
from miro import signals
from miro import workerprocess

class Source(object):
    """Object with readable metadata properties."""

    def get_iteminfo_metadata(self):
        # until MDP has run, has_drm is very uncertain; by letting it be True in
        # the backend but False in the frontend while waiting for MDP, we keep
        # is_playable False but don't show "DRM Locked" until we're sure.
        has_drm = self.has_drm and self.mdp_state is not None
        return dict(
            name = self.get_title(),
            title_tag = self.title_tag,
            description = self.get_description(),
            album = self.album,
            album_artist = self.album_artist,
            artist = self.artist,
            track = self.track,
            album_tracks = self.album_tracks,
            year = self.year,
            genre = self.genre,
            rating = self.rating,
            cover_art = self.cover_art,
            has_drm = has_drm,
            show = self.show if self.show is not None else self.artist,
            episode_id = self.episode_id if self.episode_id is not None else self.get_title(),
            episode_number = self.episode_number,
            season_number = self.season_number if self.season_number is not None else self.album,
            kind = self.kind,
            metadata_version = self.metadata_version,
            mdp_state = self.mdp_state,
        )

    def setup_new(self):
        self.title = u""
        self.title_tag = None
        self.description = u""
        self.album = None
        self.album_artist = None
        self.artist = None
        self.track = None
        self.album_tracks = None
        self.year = None
        self.genre = None
        self.rating = None
        self.cover_art = None
        self.has_drm = None
        self.file_type = None
        self.show = None
        self.episode_id = None
        self.episode_number = None
        self.season_number = None
        self.kind = None
        self.metadata_version = 0
        self.mdp_state = None # moviedata.State.UNSEEN

    @property
    def media_type_checked(self):
        """This was previously tracked as a real property; it's used by
        ItemInfo. Provided for compatibility with the previous API.
        """
        return self.file_type is not None

    @returns_unicode
    def get_title(self):
        if self.title:
            return self.title
        else:
            return self.title_tag if self.title_tag else u''

    @returns_unicode
    def get_description(self):
        return self.description

    def read_metadata(self):
        # always mark the file as seen
        self.metadata_version = filetags.METADATA_VERSION

        if self.file_type == u'other':
            return

        path = self.get_filename()
        rv = filetags.read_metadata(path)
        if not rv:
            return

        mediatype, duration, metadata, cover_art = rv
        self.file_type = mediatype
        # FIXME: duration isn't actually a attribute of metadata.Source.
        # This currently works because Item and Device item are the only
        # classes that call read_metadata(), and they both define duration
        # the same way.
        #
        # But this is pretty fragile.  We should probably refactor
        # duration to be an attribute of metadata.Source.
        self.duration = duration
        self.cover_art = cover_art
        self.album = metadata.get('album', None)
        self.album_artist = metadata.get('album_artist', None)
        self.artist = metadata.get('artist', None)
        self.title_tag = metadata.get('title', None)
        self.track = metadata.get('track', None)
        self.year = metadata.get('year', None)
        self.genre = metadata.get('genre', None)
        self.has_drm = metadata.get('drm', False)

        # 16346#c26 - run MDP for all OGG files in case they're videos
        extension = os.path.splitext(path)[1].lower()
        # oga is the only ogg-ish extension guaranteed to be audio
        if extension.startswith('.og') and extension != '.oga':
            # None because we need is_playable to be False until MDP has
            # determined the real file type, or newly-downloaded videos will
            # always play as audio; MDP always looks at file_type=None files
            self.file_type = None

def metadata_setter(attribute, type_=None):
    def set_metadata(self, value, _bulk=False):
        if value is not None and type_ is not None:
            # None is always an acceptable value for metadata properties
            value = type_(value)
        if not _bulk:
            self.confirm_db_thread()
        setattr(self, attribute, value)
        if not _bulk:
            self.signal_change()
            self.write_back((attribute,))
    return set_metadata

class Store(Source):
    """Object with read/write metadata properties."""

    set_title = metadata_setter('title', unicode)
    set_title_tag = metadata_setter('title_tag', unicode)
    set_description = metadata_setter('description', unicode)
    set_album = metadata_setter('album', unicode)
    set_album_artist = metadata_setter('album_artist', unicode)
    set_artist = metadata_setter('artist', unicode)
    set_track = metadata_setter('track', int)
    set_album_tracks = metadata_setter('album_tracks')
    set_year = metadata_setter('year', int)
    set_genre = metadata_setter('genre', unicode)
    set_rating = metadata_setter('rating', int)
    set_file_type = metadata_setter('file_type', unicode)
    set_has_drm = metadata_setter('has_drm', bool)
    set_show = metadata_setter('show', unicode)
    set_episode_id = metadata_setter('episode_id', unicode)
    set_episode_number = metadata_setter('episode_number', int)
    set_season_number = metadata_setter('season_number', int)
    set_kind = metadata_setter('kind', unicode)
    set_metadata_version = metadata_setter('metadata_version', int)
    set_mdp_state = metadata_setter('mdp_state', int)

    def set_cover_art(self, new_file, _bulk=False):
        """Set new cover art. Deletes any old cover art.

        Creates a copy of the image in our cover art directory.
        """
        if not _bulk:
            self.confirm_db_thread()
        if new_file:
            new_cover = coverart.Image.from_file(new_file, self.get_filename())
        self.delete_cover_art()
        if new_file:
            self.cover_art = new_cover
        if not _bulk:
            self.signal_change()
            self.write_back(('cover_art',))

    def delete_cover_art(self):
        """Delete the cover art file and unset cover_art."""
        try:
            fileutil.remove(self.cover_art)
        except (OSError, TypeError):
            pass
        self.cover_art = None

    def setup_new(self):
        Source.setup_new(self)
        self._deferred_update = {}

    def set_metadata_from_iteminfo(self, changes, _deferrable=True):
        self.confirm_db_thread()
        for field, value in changes.iteritems():
            Store.ITEM_INFO_TO_ITEM[field](self, value, _bulk=True)
        self.signal_change()
        self.write_back(changes.keys())

    def write_back(self, _changed):
        """Write back metadata changes to the original source, if supported. If
        this method fails because the item is playing, it should add the changed
        fields to _deferred_update.
        """
        # not implemented yet
        #logging.debug("%s can't write back changes", self.__class__.__name__)

    def set_is_playing(self, playing):
        """Hook so that we can defer updating an item's data if we can't change
        it while it's playing.
        """
        if not playing and self._deferred_update:
            self.set_metadata_from_iteminfo(self._deferred_update, _deferrable=False)
            self._deferred_update = {}
        super(Store, self).set_is_playing(playing)

    ITEM_INFO_TO_ITEM = dict(
        name = set_title,
        title_tag = set_title_tag,
        description = set_description,
        album = set_album,
        album_artist = set_album_artist,
        artist = set_artist,
        track = set_track,
        album_tracks = set_album_tracks,
        year = set_year,
        genre = set_genre,
        rating = set_rating,
        file_type = set_file_type,
        cover_art = set_cover_art,
        has_drm = set_has_drm,
        show = set_show,
        episode_id = set_episode_id,
        episode_number = set_episode_number,
        season_number = set_season_number,
        kind = set_kind,
        metadata_version = set_metadata_version,
        mdp_state = set_mdp_state,
    )

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

    @classmethod
    def get_by_path(cls, path):
        """Get an object by its path attribute.

        We use the DatabaseObjectCache to cache status by path, so this method
        is fairly quick.
        """
        try:
            return app.db.cache.get('metadata', path)
        except KeyError:
            return cls.make_view('path=?', (path,)).get_singleton()

    def setup_restored(self):
        app.db.cache.set('metadata', self.path, self)

    def on_db_insert(self):
        app.db.cache.set('metadata', self.path, self)
        database.DDBObject.on_db_insert(self)

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
                mutagen_data['file_type'] == 'audio' and
                mutagen_data['duration'] is not None and not
                mutagen_data['drm'])

    def update_after_movie_data(self, data):
        self.moviedata_status = self.STATUS_COMPLETE
        self.signal_change()

    def update_after_mutagen_error(self):
        self.mutagen_status = self.STATUS_FAILURE
        self.signal_change()

    def update_after_movie_data_error(self):
        self.moviedata_status = self.STATUS_FAILURE
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
        'mutagen': 20,
        'movie-data': 30,
        'user-data': 50,
    }

    @staticmethod
    def metadata_columns():
        return ('file_type', 'duration', 'album', 'album_artist',
                'album_tracks', 'artist', 'cover_art_path', 'screenshot_path',
                'drm', 'genre', 'title', 'track', 'year', 'description',
                'rating', 'show', 'episode_id', 'episode_number',
                'season_number', 'kind',)

    def setup_new(self, path, source, data):
        self.path = path
        self.source = source
        self.priority = MetadataEntry.source_priority_map[source]
        # set all metadata to None by default
        for name in self.metadata_columns():
            setattr(self, name, None)
        self.__dict__.update(data)

    def update_metadata(self, new_data):
        """Update the values for this object."""
        self.__dict__.update(new_data)
        self.signal_change()

    def get_metadata(self):
        """Get the metadata stored in this object as a dict."""
        rv = {}
        for name in self.metadata_columns():
            value = getattr(self, name)
            if value is not None:
                rv[name] = value
        return rv

    @classmethod
    def metadata_for_path(cls, path):
        return cls.make_view('path=?', (path,), order_by='priority ASC')

    @classmethod
    def get_entry(cls, source, path):
        view = cls.make_view('source=? AND path=?', (source, path))
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
        del self._active_tasks[task.source_path]
        if self._pending_tasks:
            path, task = self._pending_tasks.popitem()
            self._send_task(task)
        self.emit('task-complete', status)

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
        # Store the metadata
        MetadataEntry(task.source_path, u'mutagen', result)
        # Update MetadataStatus
        status.update_after_mutagen(result)

    def handle_errback(self, status, task, error):
        """Handle a successfull task."""
        status.update_after_mutagen_error()

class _MovieDataTaskProcessor(_TaskProcessor):
    def handle_callback(self, status, task, result):
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
    """

    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.mutagen_processor = _MutagenTaskProcessor(100)
        self.moviedata_processor = _MovieDataTaskProcessor(100)
        self.cover_art_dir = app.config.get(prefs.COVER_ART_DIRECTORY)
        icon_cache_dir = app.config.get(prefs.ICON_CACHE_DIRECTORY)
        self.screenshot_dir = os.path.join(icon_cache_dir, 'extracted')
        self.mutagen_processor.connect("task-complete",
                                       self._on_task_complete)

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

    def remove_file(self, path):
        """Remove a file from the metadata system.

        All queued mutagen and movie data calls will be canceled.
        :raises KeyError: path not in the metadata system
        """
        status = self._get_status_for_path(path)
        for entry in MetadataEntry.metadata_for_path(path):
            entry.remove()
        status.remove()
        # TODO: we should inform the worker process that this path has been removed so 
        # that it can cancel the any queued calls to mutagen/movie data

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
        metadata['has_drm'] = self._calc_has_drm(drm_by_source.get('mutagen'),
                                                 status)
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

    def _calc_has_drm(self, mutagen_drm, metadata_status):
        """Calculate the value of has_drm.

        has_drm is True when all of these are True
        - mutagen thinks the object has DRM
        - movie data failed to open the file
        """
        return (mutagen_drm and metadata_status.moviedata_status ==
                MetadataStatus.STATUS_FAILURE)

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

    def _get_metadata_from_filename(self, path):
        """Get metadata that we know from a filename alone."""
        return {
            'file_type': filetypes.item_file_type_for_filename(path),
        }
