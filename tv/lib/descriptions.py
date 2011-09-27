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

import logging
from datetime import datetime

from miro.database import DDBObject, ObjectNotFoundError
from miro import app

## item framework ##

# additional persistence functionality

class QuickFindable(object):
    """DDBObject-extending mixin providing quick_find support."""
    @classmethod
    def quick_find(cls, conditions):
        """Yields the objects matching the given condition dictionary, whether
        or not they have been committed yet. Dictionary contains only key=value
        conditions, which will all be ANDed together.

        This is useful for finding objects created in the current bulk
        transaction, but doesn't support complex SQL queries.
        """

        # committed matches; just run the SQL query
        where = ' AND '.join(key + '=?' for key in conditions.keys())
        committed = list(cls.make_view(where, conditions.values()))

        # uncommitted matches; check each instance in bulk_sql_manager's queue
        # N.B. No attempt is made to remove objects that are in the to_remove
        #      queue; that may eventually be necessary to implement.
        #      Anything using quick_find until then must take care to degrade
        #      acceptably gracefully in that case.
        is_match = lambda x: all((getattr(x, k) == v) for k, v in conditions.items())
        try:
            uncommitted = app.bulk_sql_manager.to_insert[app.db.table_name(cls)]
            uncommitted = [x for x in uncommitted if is_match(x)]
        except KeyError:
            # no objects of this type waiting for commit
            uncommitted = []

        return uncommitted + committed

class Referenceable(QuickFindable):
    """Mixin that allows creating a read-only alias for whatever object a
    SchemaId points to.
    """
    @classmethod
    def IdReference(cls, attr):
        """Reference to an object, stored as an ID."""
        @property
        def accessor(self):
            """Return the referenced object, or None."""
            try:
                (result,) = cls.quick_find({'id': getattr(self, attr)})
                return result
            except ValueError:
                return None

        return accessor

class ReferenceableByValue(Referenceable):
    """Mixin that supports finding objects by property values.

    Each class's UNIQUE property specifies a sequence of sets of properties that
    at most one object can match; objects should be created using with_values
    rather than directly, which returns the existing object when applicable.

    N.B. it's probably a good idea to have an index in the schema for any set of
    properties in a class's UNIQUE list.
    """
    UNIQUE = NotImplemented

    @classmethod
    def with_values(cls, **kwargs):
        """Find or create an object with the given values, based on whether the
        given values match any set of any known object's UNIQUE properties.
        """
        given = set(kwargs.keys())
        matches = set()
        for unique_set in cls.UNIQUE:
            if unique_set.issubset(given):
                # each unique_set included in given must match at most 1 object
                try:
                    match ,= cls.quick_find(dict((k, kwargs[k]) for k in unique_set))
                except ValueError:
                    # probably no matches
                    # TODO: assert that multiple matches never happen
                    pass
                else:
                    matches.add(match)
        if len(matches) == 0:
            # didn't match any existing object; create a new one
            return cls(**kwargs)
        elif len(matches) == 1:
            # matched an existing object; if this object is exactly the same,
            # return the new object; otherwise, create a new Description with
            # our values and attach it to the same Entity as the matched
            # Description.
            logging.warn("not implemented: len(matches) == 1")
        else:
            # matched more than one existing object; ensure that they all point
            # to the same Entity, and return the correct reference
            logging.warn("not implemented: len(matches) > 1")
        return cls(**kwargs)

# metametadata

class DataSource(ReferenceableByValue, DDBObject):
    """Anything that provides metadata"""
    UNIQUE = (
        {'name', 'version'},
    )
    def __repr__(self):
        return '<DataSource: %s %r>' % (self.name, self.version)

    def setup_new(self, name, version, priority):
        self.name = name
        self.version = version
        self.priority = priority

class DataSourceStatus(ReferenceableByValue, DDBObject):
    """The status of a DataSource as applies to tracking one block type."""
    UNIQUE = (
        {'datasource_id', 'description_type'},
    )
    def setup_new(self, datasource, description_type, max_examined=0):
        self.datasource_id = datasource.id
        self.description_type = description_type
        self.max_examined = max_examined

class Record(ReferenceableByValue, DDBObject):
    """An instance of data acquisition, encompassing both data source and
    acquisition date.

    Together, (source priority, date of acquisition) can be used to determine
    what data is "most authoritative". The date is necessary because ensuring
    that older data is priviledged over data with the same source priority
    allows "stability" of data - i.e. if mutually exclusive blocks of equal
    priority A and B exist, and A is added before B, and higher priority block C
    is added but later deleted, we want to make sure that we revert back to A
    rather than "reverting" to B (since "reverting" to a state that we were
    never in would be confusing, even though other than that A and B are equally
    legitimate).
    """
    UNIQUE = (
    )
    source = DataSource.IdReference('source_id')
    def setup_new(self, source, acquired=None, created=None):
        self.source_id = source.id if source is not None else None
        self.acquired = acquired if acquired is not None else datetime.now()
        self.created = created

# glue

class Entry(DDBObject, QuickFindable):
    """Association between a description and the described

    Functionally this is a one-to-many mapping (each describable "subject" can
    have multiple "descriptions", but not visa versa), in which whatever mapping
    is highest-priority is the one that is actually used.
    """
    def setup_new(self, subject, description):
        self.subject_id = subject.id
        self.subject_type = subject.__class__.__name__
        self.description_id = description.id
        self.description_type = description.__class__.__name__

# base of metadata-containing objects

class Describeable(object):
    """Something to which Descriptions can be added - this includes Entries and
    other Descriptions.
    """
    def setup_new(self):
        app.metadata_manager.describeable_created(self)

    def add_description(self, description):
        Entry(self, description)
        self._signal_change()
        print('added a description of type %s!' % (self.__class__.__name__,))

    def get_descriptions(self):
        for entry in Entry.quick_find({'subject_id': self.id}):
            DescriptionClass = Description.get_type(entry.description_type)
            assert entry.subject_id == self.id
            try:
                (description,) = DescriptionClass.quick_find({'id': entry.description_id})
                yield description
            except ValueError:
                # referenced description has been deleted?
                logging.warn('no description of type %s found for id %s',
                        description_type, description_id)

    def clear_descriptions(self, DescriptionClass):
        print('TODO TODO TODO TODO TODO')

    def get_active_description(self, DescriptionClass):
        """Return the highest-priority description of the given class referring
        to this object.
        """
        for entry in Entry.quick_find({'subject_id': self.id}):
            try:
                (description,) = DescriptionClass.quick_find({'id': entry.description_id})
                yield description
            except ValueError:
                # referenced description has been deleted?
                logging.warn('no description of type %s found for id %s',
                        description_type, description_id)

    def get_info_provided(self):
        """Return a dict of the properties this Description provides."""
        return {}

    def get_info(self):
        """Return a dict of all info properties for this object, whether from
        this object itself or associated Descriptions.
        """
        # order shouldn't matter, since each property is provided by exactly one
        # source
        # XXX: that doesn't work for weird properties like Genre (TODO)
        info = self.get_info_provided()
        logging.debug('getting info for a %s', self.__class__.__name__)
        for description in self.get_descriptions():
            logging.debug('got a %s', description.__class__.__name__)
            info.update(description.get_info())
        return info

# base of metadata-providing objects
class Description(Describeable, ReferenceableByValue):
    """Something that provides info properties about something else"""
    UNIQUE = NotImplemented
    _types = None
    def setup_new(self, record):
        Describeable.setup_new(self)
        self.record_id = record.id if record is not None else None

    @classmethod
    def get_type(cls, type_):
        if cls._types is None:
            cls._types = dict((klass.__name__, klass)
                for klass in cls.__subclasses__())
        return cls._types[type_]

    def _signal_change(self):
        print('_signal_change for a %s' % (self.__class__.__name__,))
        self.signal_change()
        for reference in Entry.make_view('description_id = ?', (self.id,)):
            Class = Description.get_type(reference.subject_type)
            subject ,= Class.quick_find({'id': reference.subject_id})
            subject._signal_change()

# Entity holds together matching Descriptions
def Entity(klass):
    """Something that can be Described."""
    class _Entity(Describeable, Referenceable, DDBObject):
        def __init__(self):
            DDBObject.__init__(self)
            Describeable.__init__(self)
            Referenceable.__init__(self)

    _Entity.__name__ = klass.__name__ + 'Entity'
    return _Entity

## data ##

class LibraryItem(Description, DDBObject):
    """Each library item."""
    UNIQUE = (
    )
    def setup_new(self):
        Description.setup_new(self, None)
        # XXX TODO: entity_id
        self.entity_id = 0

    def get_info_provided(self):
        return dict(
        )

LibraryEntity = Entity(LibraryItem)

class Label(Description, DDBObject):
    """Title and description."""
    UNIQUE = (
    )
    def setup_new(self, record, title=None, description=None):
        Description.setup_new(self, record)
        self.title = title
        self.description = description

    def get_info_provided(self):
        return dict(
            name = self.title if self.title is not None else u"",
            description = self.description if self.description is not None else u"",
        )

class Production(Description, DDBObject):
    """Production details - release date and copyright info."""
    def setup_new(self, record, release_year=None, copyright=None):
        Description.setup_new(self, record)
        self.release_year = release_year
        self.copyright = copyright

    def get_info_provided(self):
        return dict(
        )

class Genre(Description, DDBObject):
    def setup_new(self, record, genre):
        Description.setup_new(self, record)
        self.genre = genre

    def get_info_provided(self):
        return dict(
        )

class Rating(Description, DDBObject):
    # TODO: there should be two DataSources providing this: user-specified
    # (which is, as anywhere else, the highest priority) and
    # automatically-guessed. Automatic values should actually be different
    # values, so that they can be displayed differently.
    def setup_new(self, record, rating):
        Description.setup_new(self, record)
        self.rating = rating
        # TODO: boolean is_guess property

    def get_info_provided(self):
        return dict(
            rating = self.rating,
        )

class Artist(Description, DDBObject):
    """An Artist."""
    UNIQUE = (
        {'name'},
        {'echonest_id'},
    )
    def setup_new(self, record, name, echonest_id=None):
        Description.setup_new(self, record)
        self.name = name
        # XXX TODO: entity_id
        self.entity_id = 0
        self.echonest_id = echonest_id

    def get_info_provided(self):
        return dict(
            artist = self.name,
        )

ArtistEntity = Entity(Artist)

class Album(Description, DDBObject):
    """A Album."""
    UNIQUE = (
        {'name'},
    )
    artist = Artist.IdReference('artist_id')
    def setup_new(self, record, name=None, artist=None):
        Description.setup_new(self, record)
        self.name = name
        self.artist_id = artist.id if artist is not None else None
        # XXX TODO: entity_id
        self.entity_id = 0

    def get_info_provided(self):
        return dict(
            album = self.name,
            album_artist = self.artist.name if self.artist is not None else u'',
        )

AlbumEntity = Entity(Album)

class AlbumEntry(Description, DDBObject):
    """Information about an item's Album membership."""
    UNIQUE = (
        {'album', 'track'},
    )
    album = Album.IdReference('album_id')
    def setup_new(self, record, album, track=None):
        Description.setup_new(self, record)
        self.album_id = album.id if album is not None else None
        self.track = track

    def get_info_provided(self):
        """An an Entry type, we actually grab most of our data from the Album
        we're pointing to.
        """
        if self.album is not None:
            data = self.album.get_info_provided()
        else:
            data = {}
        data['track'] = self.track
        return data

class CoverArt(Description, DDBObject):
    """An Album's cover art"""
    UNIQUE = (
        {'path'},
    )
    album = Album.IdReference('album_id')
    def setup_new(self, record, album, path):
        Description.setup_new(self, record)
        self.album_id = album.id if album is not None else None
        self.path = path

    def get_info_provided(self):
        return dict(
            cover_art = self.path,
        )

class File(Description, DDBObject):
    """A local file."""
    UNIQUE = (
    )
    def setup_new(self, record, path):
        Description.setup_new(self, record)
        self.path = path

    def get_info_provided(self):
        return dict(
#            video_path = self.path,
        )

class MediaType(Description, DDBObject):
    """The type of a media file."""
    AUDIO, VIDEO, OTHER = 0, 1, 2
    TYPES = u'audio', u'video', u'other'
    UNIQUE = (
    )
    def setup_new(self, record, mediatype):
        Description.setup_new(self, record)
        self.mediatype = mediatype

    def get_info_provided(self):
        return dict(
            file_type = MediaType.TYPES[self.mediatype],
        )

class Duration(Description, DDBObject):
    """The duration of a media file."""
    UNIQUE = (
    )
    def setup_new(self, record, milliseconds):
        Description.setup_new(self, record)
        self.milliseconds = milliseconds

    def get_info_provided(self):
        return dict(
            duration = self.milliseconds / 1000,
        )

class Media(Description, DDBObject):
    """Information about a file's audio or video data itself."""
    UNIQUE = (
    )
#    file = File.IdReference('file_id')
    def setup_new(self, record, file_type=None, duration=None, has_drm=None):
        Description.setup_new(self, record)
        self.file_type = file_type
        self.duration = duration
        self.has_drm = has_drm

    def get_info_provided(self):
        return dict(
#            file_type = FILE_TYPE_TO_STRING[self.file_type],
#            duration = self.duration,
            has_drm = self.has_drm,
        )

#    library_item = LibraryEntity.IdReference('library_item_id')

class Download(Description, DDBObject):
    """The information necessary to acquire a new File from an external source."""
    UNIQUE = (
    )
    def setup_new(self, record):
        Description.setup_new(self, record)
        self.url = url
        # download status stuff ?

    def get_info_provided(self):
        return dict(
        )
