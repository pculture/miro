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

"""Code to handle resizing images.  """

import logging
import os
import traceback

from miro.platform.utils import resizeImage
from miro import fileutil

def _resizedKey(width, height):
    return u'%sx%s' % (width, height)

def _makeResizedPath(filename, width, height):
    path, ext = os.path.splitext(filename)
    path += '.%sx%s' % (width, height)
    return path + ext

def multiResizeImage(source_filename, sizes):
    """Resize an image to several sizes.

    Arguments:
        source_filename -- image to resize
        sizes -- list of (width, height) tuples to resize to.
    
    Returns a dict storing the images successfully resized.  The keys are
    "<width>x<height>" and the values are the paths to the image.
    """

    results = {}
    for width, height in sizes:
        resizedPath = _makeResizedPath(source_filename, width, height)
        try:
            resizeImage(fileutil.expand_filename(source_filename), fileutil.expand_filename(resizedPath), width, height)
        except:
            logging.warn("Error resizing %s to %sx%s:\n%s", source_filename,
                    width, height, traceback.format_exc())
        else:
            results[_resizedKey(width, height)] = resizedPath
    return results

def getImage(resized_filenames, width, height):
    """Fetch a image from the results of multiResizeImage().  If (width,
    height) wasn't one of the combinations passed to multiResizeImage(), or
    the image wasn't successfully resized, a KeyError will be thrown.
    """
    return resized_filenames[_resizedKey(width, height)]

def removeResizedFiles(resized_filenames):
    """Delete the files returned by multiResizeImage()."""

    for filename in resized_filenames.values():
        try:
            if (fileutil.exists(filename)):
                fileutil.remove (filename)
        except:
            logging.warn("Error deleted resized image: %s\n%s", filename,
                    traceback.format_exc())
