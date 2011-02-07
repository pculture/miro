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
from mutagen import id3, mp4, flac

from miro import app
from miro import prefs
from miro import util
from miro import fileutil

class UnknownImageObjectException(Exception):
    """Image uses this when mutagen gives us something strange.
    """
    def __init__(self, object_type, known_types):
        Exception.__init__()
        self.object_type = object_type
        self.known_types = known_types

    def get_type(self):
        """Return the type() of the object that could not be processed."""
        return self.object_type

    def get_known_types(self):
        """The types that Image does know how to handle."""
        return self.known_types

class Image(object):
    """Class to represent an Image created from a mutagen image.
    Normalizes mutagen's various image objects into one class structure so that
    we can use them all the same way.
    """
    PROCESSES_TYPE = None
    JPEG_EXTENSION = 'jpg'
    PNG_EXTENSION = 'png'
    UNKNOWN_EXTENSION = 'bin'
    MIME_EXTENSION_MAP = {
        'image/jpeg': JPEG_EXTENSION,
        'image/jpg': JPEG_EXTENSION,
        'image/png': PNG_EXTENSION,
    }
    COVER_ART_TYPE = 3
    def __init__(self, image_object):
        """Given a mutagen image object of any type, looks for a subclass that
        can process it. Returns an Image of the appropriate subclass, if
        available. Raises UnknownImageObjectException if there is no
        subclass capable of handling the type given.
        """
        self.is_cover = None
        self.extension = None
        self.data = None
        for cls in type(self).__subclasses__():
            if cls.can_process(image_object):
                self.__class__ = cls
                break
        self.parse(image_object)

    @classmethod
    def can_process(cls, image_object):
        """Return whether this class can process the given image object.
        Subclasses should just set cls.PROCESSES_TYPE.
        """
        return isinstance(image_object, cls.PROCESSES_TYPE)

    def parse(self, image_object):
        """Extract Image data from a given mutagen object."""
        # If this method hasn't been overriden, nothing groks this image_object
        known_types = [c.PROCESSES_TYPE for c in type(self).__subclasses__()]
        raise UnknownImageObjectException(type(image_object), known_types)

    def get_extension(self):
        """Get the extension appropriate for this file's data."""
        return self.extension or Image.UNKNOWN_EXTENSION

    def is_cover_art(self):
        """Returns True or False if the file specifies whether it is actually
        cover art; returns None otherwies.
        """
        return self.is_cover

    def write_to_file(self, track_path):
        """Creates a new file containing this image's data.
        Returns the file's path.
        """
        filename = "{0}.{1}.{2}".format(os.path.basename(track_path),
                         util.random_string(5), self.get_extension())
        directory = Image.get_destination_directory()
        path = os.path.join(directory, filename)
        try:
            file_handle = fileutil.open_file(path, 'wb')
            file_handle.write(self.data) 
        except IOError:
            logging.warn(
                "Couldn't write cover art file: {0}".format(path))
            return None
        return path

    def _set_extension_by_mime(self, mime):
        """If a subclasss can determine its data's mime type, this function will
        set the extension appropriately.
        """
        mime = mime.lower()
        if not '/' in mime:
            # some files arbitrarily drop the 'image/' component
            mime = "image/{0}".format(mime)
        if mime in Image.MIME_EXTENSION_MAP:
            self.extension = Image.MIME_EXTENSION_MAP[mime]
        else:
            logging.warn("Unknown image mime type: %s", mime)

    @staticmethod
    def get_destination_directory():
        """Get the cover-art directory, creating it if necessary."""
        dir_ = app.config.get(prefs.COVER_ART_DIRECTORY)
        try:
            fileutil.makedirs(dir_)
        except StandardError:
            pass
        return dir_

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
