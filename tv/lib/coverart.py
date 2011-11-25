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

"""``miro.coverart`` -- Handles image data extracted from mutagen, for
MovieDataUpdater.
"""

import logging
import os
import shutil
import string
from mutagen import id3, mp4, flac

from miro import app
from miro import prefs
from miro import util
from miro import fileutil

class UnknownImageObjectException(Exception):
    """Image uses this when mutagen gives us something strange.
    """
    def __init__(self, object_type, known_types):
        Exception.__init__(self)
        self.object_type = object_type
        self.known_types = known_types

    def get_type(self):
        """Return the type() of the object that could not be processed."""
        return self.object_type

    def get_known_types(self):
        """The types that Image does know how to handle."""
        return self.known_types

MIME_CHARS = frozenset(string.ascii_letters + '/-')
def _text_to_mime_chars(text):
    """Given a unicode or str containing arbitrary data, return an ascii str
    containing only the characters valid in a mime type.
    """
    # make it a unicode if it's a str
    if not isinstance(text, unicode):
        text = text.decode('ascii', errors='ignore')
    # drop non-mime chars, then convert to ascii str
    return ''.join([x for x in text if x in MIME_CHARS]).encode('ascii')

class Image(object):
    """Class to represent an Image created from a mutagen image.
    Normalizes mutagen's various image objects into one class structure so that
    we can use them all the same way.
    """
    PROCESSES_TYPE = None
    JPEG_EXTENSION = 'jpg'
    PNG_EXTENSION = 'png'
    UNKNOWN_EXTENSION = 'bin'
    # XXX when adding a mime type below, be sure its chars are all in MIME_CHARS
    # and use lowercase only
    MIME_EXTENSION_MAP = {
        'image/jpeg': JPEG_EXTENSION,
        'image/jpg': JPEG_EXTENSION,
        'image/png': PNG_EXTENSION,
    }
    COVER_ART_TYPE = 3
    def __new__(cls, image_object):
        """Given a mutagen image object of any type, looks for a subclass that
        can process it. Returns an Image of the appropriate subclass, if
        available. Raises UnknownImageObjectException if there is no
        subclass capable of handling the type given.
        """
        for subclass in cls.__subclasses__():
            if subclass.can_process(image_object):
                return super(cls, cls).__new__(subclass)
        known_types = [c.PROCESSES_TYPE for c in cls.__subclasses__()]
        raise UnknownImageObjectException(type(image_object), known_types)

    def __init__(self, image_object):
        self.is_cover = None
        self.extension = None
        self.data = None
        self.parse(image_object)

    def parse(self, image_object):
        """Should set data, extension, and optionally is_cover based on the
        image_object.
        """
        raise NotImplementedError()

    @classmethod
    def can_process(cls, image_object):
        """Return whether this class can process the given image object.
        Subclasses should just set cls.PROCESSES_TYPE.
        """
        return isinstance(image_object, cls.PROCESSES_TYPE)

    @staticmethod
    def _get_destination_path(extension, track_path, directory=None):
        filename = "{0}.{1}.{2}".format(os.path.basename(track_path),
                   util.random_string(5), extension)
        if directory is None:
            directory = app.config.get(prefs.COVER_ART_DIRECTORY)
        # make the directory if necessary:
        try:
            fileutil.makedirs(directory)
        except StandardError:
            pass
        return os.path.join(directory, filename)

    @staticmethod
    def from_file(source, track_path):
        """Copy a file to use as cover art."""
        if not fileutil.isfile(source):
            raise ValueError('cover_art must be a file')
        path = Image._get_destination_path(
                     os.path.splitext(source)[1], track_path)
        try:
            shutil.copyfile(source, path)
        except IOError:
            logging.warn(
                "Couldn't write cover art file: {0}".format(path))
            return None
        return path

    def get_extension(self):
        """Get the extension appropriate for this file's data."""
        return self.extension or Image.UNKNOWN_EXTENSION

    def is_cover_art(self):
        """Returns True or False if the file specifies whether it is actually
        cover art; returns None otherwies.
        """
        return self.is_cover

    def write_to_file(self, track_path, directory=None):
        """Creates a new file containing this image's data.
        Returns the file's path.
        """
        path = self._get_destination_path(self.get_extension(), track_path,
                                          directory)
        try:
            file_handle = fileutil.open_file(path, 'wb')
            file_handle.write(self.data) 
        except IOError:
            logging.warn(
                "Couldn't write cover art file: {0}".format(path))
            return None
        return path

    def _set_extension_by_mime(self, raw_mime):
        """If a subclasss can determine its data's mime type, this function will
        set the extension appropriately.
        """
        mime = _text_to_mime_chars(raw_mime).lower()
        dropped_chars = len(raw_mime) - len(mime)
        if not '/' in mime:
            # some files arbitrarily drop the 'image/' component
            mime = "image/{0}".format(mime)
        if dropped_chars:
            logging.debug("coverart: coerced mime %r to %r", raw_mime, mime)
        if mime in Image.MIME_EXTENSION_MAP:
            self.extension = Image.MIME_EXTENSION_MAP[mime]
        else:
            logging.warn("Unknown image mime type: %s", mime)

class ID3Image(Image):
    """The kind of image mutagen returns from an ID3 APIC tag."""
    PROCESSES_TYPE = id3.APIC
    def parse(self, image_object):
        if hasattr(image_object, 'type') and image_object.type:
            self.is_cover = image_object.type == Image.COVER_ART_TYPE
        if hasattr(image_object, 'mime'):
            self._set_extension_by_mime(image_object.mime)
        else:
            logging.warn("APIC tag without a mime type")
        self.data = image_object.data

class MP4Image(Image):
    """The kind of image mutagen returns from an MP4 file."""
    PROCESSES_TYPE = mp4.MP4Cover
    MP4_EXTENSION_MAP = {
        mp4.MP4Cover.FORMAT_JPEG: Image.JPEG_EXTENSION,
        mp4.MP4Cover.FORMAT_PNG: Image.PNG_EXTENSION,
    }
    def parse(self, image_object):
        if hasattr(image_object, 'imageformat'):
            image_format = image_object.imageformat
            if image_format in MP4Image.MP4_EXTENSION_MAP:
                self.extension = MP4Image.MP4_EXTENSION_MAP[image_format]
            else:
                logging.warn("Unknown MP4 image type code: %s", image_format)
        else:
            logging.warn("MP4 image without a type code")
        self.data = str(image_object)

class FLACImage(Image):
    """The kind of image mutagen returns from a FLAC file."""
    PROCESSES_TYPE = flac.Picture
    def parse(self, image_object):
        if hasattr(image_object, 'type') and image_object.type:
            self.is_cover = image_object.type == Image.COVER_ART_TYPE
        if hasattr(image_object, 'mime') and image_object.mime:
            self._set_extension_by_mime(image_object.mime)
        elif not (hasattr(image_object, 'colors') and image_object.colors > 0):
            # Sometimes the tag doesn't have a mime type; most are jpegs anyway.
            # Let's check whether it has an indexed palette, and assume it's a
            # jpeg if it doesn't.
            self.extension = Image.JPEG_EXTENSION
        else:
            logging.warn("FLAC image without an identifiable type")
        self.data = image_object.data
