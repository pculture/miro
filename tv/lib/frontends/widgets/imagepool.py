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

"""``miro.frontends.widgets.imagepool`` -- Get Image objects for image
filenames.

imagepool handles creating Image and ImageSurface objects for image
filenames.  It caches Image/ImageSurface objecsts so to avoid re-creating
them.
"""

import logging
import traceback

from miro import util
from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

broken_image = widgetset.Image(resources.path('images/broken-image.gif'))

CACHE_SIZE = 2000 # number of objects to keep in memory

def resize_image(image, dest_width, dest_height, upsize_threshold=1.5):
    # handle corner case of empty dest
    if (dest_width * dest_height) == 0:
        return broken_image
    # calculate how much we need to enlarge/shrink the image so that a
    # dimension lines up with the destination size
    width_scale = float(dest_width) / image.width
    height_scale = float(dest_height) / image.height
    # scale such that one dimension lines up and one is overlapping
    scale = max(width_scale, height_scale)
    # check that we don't upsize too much
    if scale > upsize_threshold:
        return resize_one_dimension(image, width_scale, height_scale)
    if width_scale > height_scale:
        # crop top/bottom
        src_x = 0
        src_width = image.width
        src_height = dest_height / scale
        src_y = (image.height - src_height) / 2
    else:
        # crop left/right
        src_y = 0
        src_height = image.height
        src_width = dest_width / scale
        src_x = (image.width - src_width) / 2
    return image.crop_and_scale(src_x, src_y, src_width, src_height,
            dest_width, dest_height)

def resize_one_dimension(image, width_scale, height_scale,
                         upsize_threshold=1.5):
    """Try to resize only 1 dimension on an image."""
    lesser_scale = min(width_scale, height_scale)
    if lesser_scale <= upsize_threshold:
        # round() then int(), don't return floats here.
        return image.resize(int(round(lesser_scale * image.width)),
                int(round(lesser_scale * image.height)))
    # okay, give up on scaling and just return the image
    return image

class ImagePool(util.Cache):
    def create_new_value(self, (path, size)):
        try:
            image = widgetset.Image(path)
        except StandardError:
            logging.warn("error loading image %s:\n%s", path,
                    traceback.format_exc())
            image = broken_image
        if size is not None:
            image = resize_image(image, *size)
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

def get_image_display(path, size=None):
    """Returns an ImageDisplay for path.

    :param path: the filename for the image
    :param size: if the image needs to fit into a specified sized
                 space, then specify this and get will return a
                 scaled image; if size is not specified, then this
                 returns the default sized image
    """
    return widgetset.ImageDisplay(_imagepool.get((path, size)))

# XXX have a way to remove a path from the cache? (re: #16573)

