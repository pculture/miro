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

"""``miro.importmedia`` -- functions for importing from other music jukeboxes.
"""

import os
import plistlib
import urllib

ITUNES_XML_FILE = "iTunes Music Library.xml"

def file_path_xlat(path):
    """Convert iTunes path to what we can handle."""
    try:
        file_url_bits = "file://localhost"
        if not path.startswith(file_url_bits):
            return None
        path = urllib.url2pathname(path[len(file_url_bits):])
        return path
    # bad path catchall
    except StandardError:
        return None

def import_itunes_path(path):
    """Look for a specified iTunes Music Library.xml file from the specified
       path.  Returns the path of the music library as specified in the
       iTunes settings or None if it cannot find the xml file, or does not
       contain the path for some reason."""
    try:
        data = plistlib.readPlist(os.path.join(path, ITUNES_XML_FILE))
        return file_path_xlat(data['Music Folder'])
    except (IOError, KeyError):
        pass
    

