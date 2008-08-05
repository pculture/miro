# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

"""imagepool -- Get Image objects for image filenames.

imagepool handles creating Image and ImageSurface objects for image filenames.
It remembers images that have been created, and doesn't create duplicate
Image/ImageSurface objects for a single path. 
"""

import logging
import traceback
import weakref

from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

# path_to_image and path_to_surface maps (path, size) tuples to
# Image/ImageSurface objects.
# Uses weak references so that once the Image/ImageSurface is not being used
# it will be deleted.
path_to_image = weakref.WeakValueDictionary()
path_to_surface = weakref.WeakValueDictionary()

broken_image = widgetset.Image(resources.path('wimages/broken-image.gif'))

def scaled_size(image, size):
    image_ratio = float(image.width) / image.height
    new_ratio = float(size[0]) / size[1]
    if image_ratio == new_ratio:
        return size
    elif image_ratio > new_ratio:
        # The scaled image has a wider aspect ratio than the old one.
        height = int(round(float(size[0]) / image.width * image.height))
        return size[0], height
    else:
        # The scaled image has a taller aspect ratio than the old one.
        width = int(round(float(size[1]) / image.height * image.width))
        return width, size[1]

def get(path, size=None):
    """Returns an Image for path.
    
    size is an optional argument that can be used to get resized images.  If
    given it should be a (width, height) tuple.  By default we return the
    native size of the widget.
    """
    try:
        return path_to_image[(path, size)]
    except KeyError:
        try:
            image = widgetset.Image(path)
        except:
            logging.warn("error loading image %s:\n%s", path,
                    traceback.format_exc())
            image = broken_image
        if size is not None:
            image = image.resize(*scaled_size(image, size))
            path_to_image[(path, size)] = image
        else:
            path_to_image[(path, None)] = image
            path_to_image[(path, (image.width, image.height))] = image
        return image

def get_surface(path, size=None):
    """Returns an ImageSurface for path."""
    try:
        return path_to_surface[(path, size)]
    except KeyError:
        image = get(path, size)
        surface = widgetset.ImageSurface(image)
        path_to_surface[(path, size)] = surface
        if size is None:
            path_to_surface[(path, (image.width, image.height))] = surface
        return surface
