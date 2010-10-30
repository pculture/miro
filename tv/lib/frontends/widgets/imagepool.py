# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""``miro.frontends.widgets.imagepool`` -- Get Image objects for image
filenames.

imagepool handles creating Image and ImageSurface objects for image
filenames.  It caches Image/ImageSurface objecsts so to avoid re-creating
them.
"""

import logging
import traceback
import weakref

from miro import util
from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

broken_image = widgetset.Image(resources.path('images/broken-image.gif'))

def scaled_size(image, size):
    """Takes an image which has a width and a height and a size tuple
    that specifies the space available and returns the new width
    and height that allows the image to fit into the sized space
    at the correct height/width ratio.

    :param image: the Image (must have width and height properties)
    :param size: (width, height) tuple of space you want the image
                 to fit in
    """
    if image.width == 0 or image.height == 0:
        image = broken_image
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

CACHE_SIZE = 2000 # number of objects to keep in memory

class ImagePool(util.Cache):
    def create_new_value(self, (path, size)):
        try:
            image = widgetset.Image(path)
        except StandardError:
            logging.warn("error loading image %s:\n%s", path,
                    traceback.format_exc())
            image = broken_image
        if size is not None:
            image = image.resize(*scaled_size(image, size))
        return image

class ImageSurfacePool(util.Cache):
    def create_new_value(self, (path, size)):
        image = _imagepool.get((path, size))
        return widgetset.ImageSurface(image)

_imagepool = ImagePool(CACHE_SIZE)
_image_surface_pool = ImageSurfacePool(CACHE_SIZE)

def get(path, size=None):
    """Returns an Image for path.

    :param path: the filename for the image
    :param size: if the image needs to fit into a specified sized
                 space, then specify this and get will return a
                 scaled image; if size is not specified, then this
                 returns the default sized image
    """
    return _imagepool.get((path, size))

def get_surface(path, size=None):
    """Returns an ImageSurface for path.

    :param path: the filename for the image
    :param size: if the image needs to fit into a specified sized
                 space, then specify this and get will return a
                 scaled image; if size is not specified, then this
                 returns the default sized image
    """
    return _image_surface_pool.get((path, size))

class LazySurface(object):
    """Lazily loaded ImageSurface.  
    
    LazySurface objects only create ImageSurfaces as needed.  If multiple
    LazySurface objects are created for the same path, then they will share
    the underlying ImageSurface object.
    """
    def __init__(self, path, size=None):
        self.path = path
        self.size = size
        self._get_surface_if_available()

    def _get_surface_if_available(self):
        """Try to get the ImageSurface for this object if it's already
        created.  This ensures that if the other ImageSurface is destroyed, we
        will still have a reference.
        """
        try:
            self._surface = path_to_surface[(self.path, self.size)]
        except KeyError:
            pass

    def _ensure_surface(self):
        if not hasattr(self, '_surface'):
            self._surface = get_surface(self.path, self.size)

    def get_width(self):
        self._ensure_surface()
        return self._surface.width
    width = property(get_width)

    def get_height(self):
        self._ensure_surface()
        return self._surface.height
    height = property(get_height)

    def draw(self, context, x, y, width, height, fraction=1.0):
        self._ensure_surface()
        self._surface.draw(context, x, y, width, height, fraction)
