# Miro - an RSS based video player application
# Copyright (C) 2006, 2006, 2007, 2008, 2009, 2010, 2011
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

import os.path

from miro import download_utils
from miro import fileutil
from miro.plat.utils import run_media_metadata_extractor

def convert_mdp_result(source_path, screenshot_path, result):
    """Convert the movie data program result for the metadata manager
    """
    converted_result = { 'source_path': source_path }
    file_type, duration, success = result

    # MDP retuturns durations in millseconds, convert to seconds
    if duration >= 0:
        converted_result['duration'] = duration
    else:
        converted_result['duration'] = None

    # Make file_type is unicode, or else database validation will fail on
    # insert!
    converted_result['file_type'] = unicode(file_type)

    if os.path.splitext(source_path)[1] == '.flv':
        # bug #17266.  if the extension is .flv, we ignore the file type
        # we just got from the movie data program.  this is
        # specifically for .flv files which the movie data
        # extractors have a hard time with.
        converted_result['file_type'] = u'video'

    if (converted_result['file_type'] == 'video' and success and
        fileutil.exists(screenshot_path)):
        converted_result['screenshot_path'] = screenshot_path
    else:
        converted_result['screenshot_path'] = None
    return converted_result

def _make_screenshot_path(source_path, image_directory):
    """Get a unique path to put a screenshot at

    This function creates a unique path to put a screenshot file at.

    :param source_path: path to the input video file
    :param image_directory: directory to put screenshots in
    """
    filename = os.path.basename(source_path) + ".png"
    path = os.path.join(image_directory, filename)
    # we have to use next_free_filename_no_create() here because we are
    # passing the file path to the movie data process, so keeping the file
    # open is not an option.  We'll just have to live with the race condition
    return download_utils.next_free_filename(path)

def process_file(source_path, image_directory):
    """Send a file to the movie data program.

    :param source_path: path to the file to process
    :param image_directory: directory to put screenshut files
    :returns: dictionary with metadata info
    """
    if not os.path.exists(image_directory):
        fileutil.makedirs(image_directory)
    screenshot_path, fp = _make_screenshot_path(source_path, image_directory)
    result = run_media_metadata_extractor(source_path, screenshot_path)
    # we can close the file now, since MDP has written to it
    fp.close()
    return convert_mdp_result(source_path, screenshot_path, result)
