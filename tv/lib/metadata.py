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

import fileutil
import os.path
import logging

from miro.util import returns_unicode
from miro import coverart
from miro import filetags
from miro import descriptions
from miro import app

class Source(object):
    """Object with readable metadata properties."""
    library_entity = descriptions.LibraryItem.IdReference('library_entity_id')
    def get_iteminfo_metadata(self):
        # until MDP has run, has_drm is very uncertain; by letting it be True in
        # the backend but False in the frontend while waiting for MDP, we keep
        # is_playable False but don't show "DRM Locked" until we're sure.
        has_drm = self.has_drm and self.mdp_state is not None
        # get old-style monolithic data
        data = dict(
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
            show = self.show,
            episode_id = self.episode_id,
            episode_number = self.episode_number,
            season_number = self.season_number,
            kind = self.kind,
            metadata_version = self.metadata_version,
            mdp_state = self.mdp_state,
        )
        # add new-style modular data (takes precedence)
        if self.library_entity is not None:
            data.update(self.library_entity.get_info())
        # XXX: hacky transitional code
        # here's where we convert some properties that we may only have as
        # ItemInfo values and modular values back into monolithic values, so
        # that Item's sql queries can find them
        if 'file_type' in data:
            self.file_type = data['file_type']
        return data

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
        self.library_entity_id = descriptions.LibraryItem().id
        self.library_entity.connect('changed', self.signal_change)

    def setup_restored(self):
        if self.library_entity is not None:
            self.library_entity.connect('changed', self.signal_change)

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

    def set_file(self, path):
        """Associate with this library item a File object"""
        # path is a UNIQUE value to File, so anything else with the same path
        # raises an error here
        fil = descriptions.File(None, path)

        # de-associate any previous File, associate the new File
        self.library_entity.clear_descriptions(descriptions.File)
        self.library_entity.add_description(fil)

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

class MetadataManager(object):
    def __init__(self):
        self.providers = {}

    def load_extractors(self):
        from miro.extractor import *

    def add_provider(self, datasource, DescriptionClass, provider):
        # TODO: order providers for DescriptionClass by datasource priority
        self.providers.setdefault(DescriptionClass.__name__, [])
        self.providers[DescriptionClass.__name__].append((datasource, provider))
        logging.info('extractor registered: %r', datasource)

    def run_extractors(self):
        """Catch up each extractor to the existing items, in order of id. """
        print('run_extractors')
        for class_name in self.providers:
            self.run_extractors_for_type(class_name)
        logging.info("known exctractors: %r", self.providers)

    def run_extractors_for_type(self, class_name):
        """Run extractors that respond to a certain type of Describebable."""
        print('checking for extractors for %r' % (class_name,))
        DescriptionClass = descriptions.Description.get_type(class_name)
        for datasource, get_descriptions in self.providers.get(class_name, ()):
            print('running extractor %s for %r' % (datasource.name, class_name))
            status_query = {'datasource_id': datasource.id,
                    'description_type': class_name}
            status ,= descriptions.DataSourceStatus.quick_find(status_query)
            new_items = DescriptionClass.make_view(
                    'id > ?', (status.max_examined,), order_by='id')
            for new_item in new_items:
                print('processing an item...')
                try:
                    for description in get_descriptions(new_item):
                        print('adding description of type %s' %
                                (description.__class__.__name__,))
                        new_item.add_description(description)
                    status.max_examined = new_item.id
                    status.signal_change()
                except ExtractionFailed:
                    # TODO: distinguish between "temporary" errors and errors
                    # that are expected to persist for rest of session?
                    break

    def describeable_created(self, describeable):
        self.run_extractors_for_type(describeable.__class__.__name__)

# extraction process

class ExtractionFailed(Exception):
    pass

class ExtractorInvalid(ExtractionFailed):
    pass
