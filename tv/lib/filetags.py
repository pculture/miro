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

"""``miro.filetags`` -- Read and write metadata stored in files.

This module is stateless; it is used by MovieDataUpdater and Item.
"""

import os.path
import logging
import struct
import mutagen

from miro import coverart
from miro import filetypes

# increment this after adding to TAG_MAP or changing read_metadata() in a way
# that will increase data identified (will not change values already extracted)
METADATA_VERSION = 5

TAG_MAP = {
    'album': ('album', 'talb', 'wm/albumtitle', u'\uFFFDalb'),
    'album_artist': ('aart', 'albumartist', 'album artist', 'tpe2', 'band',
        'ensemble'),
    'artist': ('artist', 'tpe1', 'tpe2', 'tpe3', 'author', 'albumartist',
        'composer', u'\uFFFDart', 'album artist'),
    'drm': ('itunmovi',),
    'title': ('tit2', 'title', u'\uFFFDnam'),
    'track': ('trck', 'tracknumber'),
    'album_tracks': (),
    'year': ('tdrc', 'tyer', 'date', 'year'),
    'genre': ('genre', 'tcon', 'providerstyle', u'\uFFFDgen'),
    'cover-art': ('\uFFFDart', 'apic', 'covr'),
}
TAG_TYPES = {
    'album': unicode, 'album_artist': unicode, 'artist': unicode, 'drm': bool,
    'title': unicode, 'track': int, 'album_tracks': int, 'year': int,
    'genre': unicode,
}
NOFLATTEN_TAGS = ('cover-art',)

def _mediatype_from_mime(mimes):
    """Used as a fallback if the extension isn't specific."""
    audio = False
    other = False
    for mime in mimes:
        ext = filetypes.guess_extension(mime)
        if ext in filetypes.VIDEO_EXTENSIONS:
            return 'video'
        if ext in filetypes.AUDIO_EXTENSIONS:
            audio = True
        if ext in filetypes.OTHER_EXTENSIONS:
            other = True
    if audio:
        return 'audio'
    elif other:
        return 'other'
    else:
        return None

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
    return thing

def _sanitize_keys(tags):
    """Strip useless components and strange characters from tag names
    """
    tags_cleaned = {}
    for key, value in tags.iteritems():
        try:
            key = _str_or_object_to_unicode(key)
        except ValueError:
            logging.warn("cannot convert key %s to any kind of string",
                         repr(key))
            continue
        if key.startswith('PRIV:'):
            key = key.split('PRIV:')[1]
        if key.startswith('TXXX:'):
            key = key.split('TXXX:')[1]
        if key.startswith('----:com.apple.iTunes:'):
            # iTunes M4V
            key = key.split('----:com.apple.iTunes:')[1]
        key = key.split(':')[0]
        if key.startswith('WM/'):
            key = key.split('WM/')[1]
        key = key.lower()
        tags_cleaned[key] = value
    return tags_cleaned

def _sanitize_values(tags):
    """Flatten values into simple unicode strings
    """
    tags_cleaned = {}
    for key, value in tags.iteritems():
        while isinstance(value, list):
            if not value:
                value = None
                break
            value = value[0]
        if hasattr(value, 'value'):
            value = value.value
        if value is not None:
            try:
                value = _str_or_object_to_unicode(value)
            except ValueError:
                logging.warn("cannot convert value %s (for key %s) to any kind"
                             "of string", repr(value), repr(key))
                continue
            tags_cleaned[key] = value.lstrip()
    return tags_cleaned

def _special_mappings(data, item):
    """Handle tags that need more than a simple TAG_MAP entry
    """
    if 'purd' in data:
        data[u'year'] = data['purd'].split('-')[0]
    if 'year' in data:
        if not data['year'].isdigit():
            del data['year']
    if 'track' in data:
        track = data['track'].split('/')[0]
        if track.isdigit():
            data[u'track'] = unicode(int(track))
        else:
            del data['track']
    if 'trkn' in data:
        track = data['trkn']
        if isinstance(track, tuple):
            track = track[0]
        data[u'track'] = unicode(track)
    if 'track' not in data:
        num = ''
        full_path = item.get_url() or item.get_filename()
        filename = os.path.basename(full_path)
        
        for char in filename:
            if not char.isdigit():
                break
            num += char
        if num.isdigit():
            num = int(num)
            if num > 0:
                while num > 100:
                    num -= 100
                data[u'track'] = unicode(num)
    return data

def _make_cover_art_file(track_path, objects):
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
        except coverart.UnknownImageObjectException as e:
            logging.debug("Couldn't parse image object of type %s",
                          e.get_type())
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

    path = cover_image.write_to_file(track_path)
    return path

def read_metadata(item):
    mediatype = None
    duration = -1
    cover_art = None
    tags = {}
    info = {}
    data = {}

    try:
        muta = mutagen.File(item.get_filename())
        meta = muta.__dict__
    except (ArithmeticError):
        # mutagen doesn't catch these errors internally
        logging.warn("malformed file: %s", item.get_filename())
        return (mediatype, duration, data, cover_art)
    except (AttributeError, IOError):
        return (mediatype, duration, data, cover_art)
    except struct.error:
        logging.warn("read_metadata on incomplete file: %s",
                     item.get_filename())
        return (mediatype, duration, data, cover_art)

    filename = item.get_filename()
    if filetypes.is_video_filename(filename):
        mediatype = 'video'
    elif filetypes.is_audio_filename(filename):
        mediatype = 'audio'
    elif hasattr(muta, 'mime'):
        mediatype = _mediatype_from_mime(muta.mime)

    tags = meta['tags']
    if hasattr(tags, '__dict__') and '_DictProxy__dict' in tags.__dict__:
        tags = tags.__dict__['_DictProxy__dict']
    tags = tags or {}

    if 'info' in meta:
        info = meta['info'].__dict__
    if 'fps' in info or 'gsst' in tags:
        mediatype = 'video'
    if 'length' in info:
        duration = int(info['length'] * 1000)
    else:
        try:
            dur = meta['seektable'].__dict__['seekpoints'].pop()[1]
            duration = int(dur / 100)
        except (KeyError, AttributeError, TypeError, IndexError):
            pass

    tags = _sanitize_keys(tags)
    nonflattened_tags = tags.copy()
    tags = _sanitize_values(tags)

    for tag, sources in TAG_MAP.iteritems():
        for source in sources:
            if source in tags:
                if tag in NOFLATTEN_TAGS:
                    data[unicode(tag)] = nonflattened_tags[source]
                else:
                    data[unicode(tag)] = tags[source]
                break

    data = _special_mappings(data, item)

    if hasattr(muta, 'pictures'):
        image_data = muta.pictures
        cover_art = _make_cover_art_file(item.get_filename(), image_data)
    elif 'cover-art' in data:
        image_data = data['cover-art']
        cover_art = _make_cover_art_file(item.get_filename(), image_data)
        del data['cover-art']

    for tag, value in data.iteritems():
        if not isinstance(value, TAG_TYPES[tag]):
            try:
                data[tag] = TAG_TYPES[tag](value)
            except ValueError:
                logging.debug("Invalid type for tag %s: %s", tag, repr(value))
                del data[tag]
    return (mediatype, duration, data, cover_art)
