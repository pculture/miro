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

"""``miro.filetags`` -- Read and write metadata stored in files."""

import os.path
import logging
import struct
import mutagen

from miro import coverart
from miro import filetypes
from miro import app

# increment this after adding to TAGS_FOR_ATTRIBUTE or changing read_metadata() in a way
# that will increase data identified (will not change values already extracted)
METADATA_VERSION = 5

TAGS_FOR_ATTRIBUTE = dict(
    album=frozenset(['album', 'talb', 'wm/albumtitle', u'\uFFFDalb']),
    album_artist=frozenset(['aart', 'albumartist', 'album artist', 'tpe2', 'band',
        'ensemble']),
    album_tracks=frozenset([]),
    artist=frozenset(['artist', 'tpe1', 'tpe2', 'tpe3', 'author', 'albumartist',
        'composer', u'\uFFFDart', 'album artist']),
    cover_art=frozenset(['\uFFFDart', 'apic', 'covr']),
    drm=frozenset(['itunmovi', 'apid']),
    genre=frozenset(['genre', 'tcon', 'providerstyle', u'\uFFFDgen']),
    title=frozenset(['tit2', 'title', u'\uFFFDnam']),
    track=frozenset(['trck', 'tracknumber', 'trkn']),
    year=frozenset(['tdrc', 'tyer', 'date', 'year', 'purd']),
)
# values will be coerced to given type, or left untouched if type is None
ATTRIBUTE_TYPES = dict(
    album=unicode,
    album_artist=unicode,
    album_tracks=int,
    artist=unicode,
    cover_art=None,
    drm=bool,
    genre=unicode,
    title=unicode,
    track=int,
    year=int,
)
# don't forget to put something in ATTRIBUTE_TYPES when adding to 
# TAGS_FOR_ATTRIBUTE
assert TAGS_FOR_ATTRIBUTE.keys() == ATTRIBUTE_TYPES.keys()
NOFLATTEN_ATTRIBUTES = frozenset(['cover_art'])

# For most files, the extension is the most reliable indicator of format;
# see 16436#c14.
UNRELIABLE_EXTENSIONS = frozenset(['ogg','ogm', 'ogx', 'oga', 'ogv'])

def _get_duration(muta, info):
    """This function attempts to determine the length of an item from its
    mutagen properties. If this function fails, movie_data_program will be used
    for this file.

    NOTE: this method is currently somewhat inaccurate for FLAC files (#16100)
    """
    if 'length' in info:
        return int(round(info['length'] * 1000))
    try: # find approximate length of FLAC file
        return int(round(muta.seektable.seekpoints[-1][1] / 100.0))
    except (KeyError, AttributeError, TypeError, IndexError):
        logging.debug(muta.seektable.seekpoints[-1][1] / 100.0)
        return None

def _mediatype_from_mime(mimes):
    """Used as a fallback if the extension isn't specific."""
    types = frozenset(mime.split('/', 2)[0] for mime in mimes)
    if 'video' in types:
        return u'video'
    elif 'audio' in types:
        return u'audio'
    elif types.intersection(['other', 'application']):
        return u'other'

def _get_mediatype(muta, filename, info, tags):
    """This function is the sole determinant of an object's initial file_type,
    except when the file is not mutagen-compatible (in which case
    movie_data_program's data overrides anything set here).
    """
    if 'fps' in info or 'gsst' in tags:
        mediatype = u'video'
    elif filetypes.is_video_filename(filename):
        mediatype = u'video'
    elif filetypes.is_audio_filename(filename):
        mediatype = u'audio'
    else:
        mediatype = None
    extension = os.path.splitext(filename)[-1].lstrip('.').lower()
    if hasattr(muta, 'mime') and (extension in UNRELIABLE_EXTENSIONS
            or not mediatype):
        mediatype = _mediatype_from_mime(muta.mime) or mediatype
    return mediatype

def _str_or_object_to_unicode(thing):
    """Whatever thing is, get a unicode out of it at all costs."""
    if not isinstance(thing, basestring):
        # with try/except because mutagen objects that can be unicode()d
        # often don't haveattr __unicode__
        try:
            thing = unicode(thing)
        except ValueError:
            try:
                thing = str(thing)
            except ValueError:
                pass
    if not isinstance(thing, unicode):
        # thing is a str, or thing cannot be converted to unicode or str cleanly
        # if this fails, it is caught higher up
        thing = unicode(thing, errors='replace')
    return thing.replace(u'\u0000', u'')

def _sanitize_key(key):
    """Strip useless components and strange characters from tag names"""
    key = _str_or_object_to_unicode(key)
    if key.startswith('PRIV:'):
        key = key.split('PRIV:')[-1]
    if key.startswith('TXXX:'):
        key = key.split('TXXX:')[-1]
    if key.startswith('----:com.apple.iTunes:'):
        # iTunes M4V
        key = key.split('----:com.apple.iTunes:')[-1]
    key = key.split(':')[0]
    if key.startswith('WM/'):
        key = key.split('WM/')[-1]
    key = key.lower()
    return key

def _convert_to_type(value, proper_type):
    """Flatten a value into a simple unicode string, then convert it to the
    given type.
    """
    while isinstance(value, (list, tuple)):
        if not value:
            return None
        value = value[0]
    if hasattr(value, 'value'):
        value = value.value
    if value is not None:
        value = _str_or_object_to_unicode(value).lstrip()
    if proper_type is int:
        value = value.split('-', 2)[0] # YYYY-MM-DD
        value = value.split(' ', 2)[0] # YYYY MM DD
        value = value.split('/', 2)[0] # track/total
    if proper_type is not unicode:
        value = proper_type(value)
    return value

def _track_from_filename(full_path):
    """When metadata doesn't have a track number, this checks whether the file
    starts with a number, and uses it as the track number if it does.
    """
    initial_int = []
    for char in os.path.basename(full_path):
        if not char.isdigit():
            break
        initial_int.append(char)
    if len(initial_int) > 0 and len(initial_int) < 4:
        number = ''.join(initial_int[-2:]) # e.g. '204' is disc 2, track 04
        return int(number)

def _make_cover_art_file(track_path, objects, cover_art_directory=None):
    """Given an iterable of mutagen cover art objects, returns the path to a
    newly-created file created from one of the objects. If given more than one
    object, uses the one most likely to be cover art. If none of the objects are
    usable, returns None.
    """
    if not isinstance(objects, list):
        objects = [objects]

    images = []
    for image_object in objects:
        try:
            image = coverart.Image(image_object)
        except coverart.UnknownImageObjectException as error:
            logging.debug("Couldn't parse image object of type %s",
                          error.get_type())
        else:
            images.append(image)
    if not images:
        return

    cover_image = None
    for candidate in images:
        if candidate.is_cover_art() is not False:
            cover_image = candidate
            break
    if cover_image is None:
        # no attached image is definitively cover art. use the first one.
        cover_image = images[0]

    path = cover_image.write_to_file(track_path, cover_art_directory)
    return path

MUTAGEN_ERRORS = None
def _setup_mutagen_errors():
    from mutagen import (apev2, asf, flac, id3, m4a, mp3, mp4, oggflac, ogg,
            oggspeex, oggtheora, oggvorbis, trueaudio, _vorbis)
    global MUTAGEN_ERRORS
    MUTAGEN_ERRORS = (apev2.error, asf.error, flac.error, id3.error, m4a.error,
            mp3.error, mp4.error, oggflac.error, ogg.error, oggspeex.error,
            oggtheora.error, oggvorbis.error, trueaudio.error, _vorbis.error)
_setup_mutagen_errors()

def read_metadata(filename, test=False, cover_art_directory=None):
    """This is the external interface of the filetags module. Given a filename,
    this function returns a tuple of (mediatype [a string], duration [integer
    number of milliseconds(?)], data [dict of attributes to set on the item],
    cover_art [filename]).

    Both the interface and the implementation are in need of substantial
    reworking. I have a replacement in the works (with write support!) but have
    pushed it off for 4.1 since this is generally functional. The root of the
    problem is that I have tried to write one function that handles all the
    different mutagen metadata objects; the new approach will be to wrap each
    mutagen object in a different wrapper subclass, with all the wrappers
    sharing a common interface. --KCW
    """
    # FIXME: we should probably drop the test parameter and set
    # cover_art_directory in the unittests
    try:
        muta = mutagen.File(filename)
    except MUTAGEN_ERRORS:
        # most likely just unsupported format or file with no metadata
        pass
    except IOError:
        # important to catch MUTAGEN_ERRORS before this - mutagen has IOError
        # subclasses that have nothing to do with I/O, but they also subclass
        # MUTAGEN_ERRORS types.
        logging.error("mutagen: IOError for file: %s", filename, exc_info=True)
    except MemoryError:
        # apparently mutagen raises this for
        # mozilla/content/media/test/bug504644.ogv in the XULRunner source;
        # I find that extremely disconcerting
        logging.error("mutagen: MemoryError - may be bad file?: %s", filename,
                exc_info=True)
    except EOFError:
        # probably incomplete, so this should be rare!
        logging.warn("mutagen: incomplete file?: %s", filename, exc_info=True)
    except struct.error:
        # probably incomplete, so this should be rare!
        logging.warn("mutagen: incomplete file?: %s", filename, exc_info=True)
    except ArithmeticError:
        # likely malformed, though possibly incomplete
        logging.warn("mutagen: malformed file?: %s", filename)
    except AttributeError:
        # definitely a mutagen bug, likely poor handling of bad file
        logging.debug("mutagen bug; possible malformed file: %s", filename,
                exc_info=True)
    except UnicodeDecodeError: #17257
        # probably bad encoding in file or mutagen bug
        logging.debug("mutagen: bad encoding: %s", filename)
    except ValueError: #17285
        logging.debug("mutagen: malformed file: %s", filename)
    except StandardError:
        # unknown error; soft fail because I think we should identify the error
        # types mutagen can raise - some of them hint as to what went wrong
        app.controller.failed_soft("mutagen",
                "unexpected Exception type in mutagen.File",
                with_exception=True)
    else:
        if muta:
            return _parse_mutagen(filename, muta, test, cover_art_directory)

def _parse_mutagen(filename, muta, test, cover_art_directory):
    meta = muta.__dict__
    tags = meta['tags']
    if hasattr(tags, '__dict__') and '_DictProxy__dict' in tags.__dict__:
        tags = tags.__dict__['_DictProxy__dict']
    tags = tags or {}

    info = {}
    if hasattr(muta, 'info'):
        info = muta.info.__dict__

    duration = _get_duration(muta, info)
    mediatype = _get_mediatype(muta, filename, info, tags)

    data = {}
    for file_tag, value in tags.iteritems():
        try:
            file_tag = _sanitize_key(file_tag)
        except ValueError:
            if file_tag:
                logging.warn("cannot convert key %s to any kind of string",
                             repr(file_tag))
            continue
        for attribute, attribute_tags in TAGS_FOR_ATTRIBUTE.iteritems():
            if file_tag in attribute_tags:
                if attribute == 'drm':
                    if file_tag == 'itunmovi':
                        # '----:com.apple.iTunes:iTunMOVI' uses a silly
                        # dict-as-XML format. The 'asset-info' key seems a
                        # sensitive but non-specific indicator of DRM'd files
                        value = '<key>asset-info</key>' in value
                    # else it's apID, which indicates possible DRM by its
                    # presence; the contents don't matter
                proper_type = ATTRIBUTE_TYPES[attribute]
                if proper_type:
                    try:
                        value = _convert_to_type(value, proper_type)
                    except ValueError:
                        if value:
                            logging.warn("cannot convert value %s to the proper type",
                                         repr(value))
                        break
                data[unicode(attribute)] = value
                break
    if not 'track' in data:
        guessed_track = _track_from_filename(filename)
        if guessed_track:
            data['track'] = guessed_track

    cover_art = None
    if hasattr(muta, 'pictures'):
        image_data = muta.pictures
        if test:
            cover_art = True
        else:
            cover_art = _make_cover_art_file(filename, image_data,
                                             cover_art_directory)
    elif 'cover_art' in data:
        image_data = data['cover_art']
        if test:
            cover_art = True
        else:
            cover_art = _make_cover_art_file(filename, image_data,
                                             cover_art_directory)
        del data['cover_art']
    return mediatype, duration, data, cover_art

def process_file(source_path, cover_art_directory):
    """Send a file through mutagen

    :param source_path: path to the media file
    :param cover_art_directory: directory to store cover art in
    :returns: dict of metadata
    """
    result = read_metadata(source_path,
                           cover_art_directory=cover_art_directory)
    if result is None:
        return {}
    file_type, duration, data, cover_art = result
    # combine everything into a single dict
    # FIXME: we should refactor read_metadata() to return data in this way
    data['source_path'] = source_path
    data['file_type'] = file_type
    if duration >= 0:
        data['duration'] = duration
    else:
        data['duration'] = None
    data['cover_art_path'] = cover_art
    return data
