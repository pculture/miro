# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

from xpcom import components
import os, sys
import re
import urllib

import config
import prefs

# Strategy: ask the directory service for
# NS_XPCOM_CURRENT_PROCESS_DIR, the directory "associated with this
# process," which is read to mean the root of the Mozilla
# installation. Use a fixed offset from this path.

def appRoot():
    # This reports the path to xulrunner.exe -- admittedly a little
    # misleading. In general, this will be in a 'xulrunner'
    # subdirectory underneath the actual application root directory.
    klass = components.classes["@mozilla.org/file/directory_service;1"]
    service = klass.getService(components.interfaces.nsIProperties)
    file = service.get("resource:app", components.interfaces.nsIFile)
    return file.path

def resourceRoot():
    return os.path.join(appRoot(), 'resources')

# Note: some of these functions are probably not absolutely correct in
# the face of funny characters in the input paths. In particular,
# url() doesn't DTRT when the path contains spaces. But they should be
# sufficient for resolving resources, since we have control over the
# filenames.

# Find the full path to a resource data file. 'relative_path' is
# expected to be supplied in Unix format, with forward-slashes as
# separators. The output, though, uses the native platform separator.
def path(relative_path):
    abspath = os.path.abspath(os.path.join(resourceRoot(), relative_path))
    return abspath.replace("/", "\\")

def url(relative_path):
    return absoluteUrl(path(relative_path))

def absoluteUrl(absolute_path):
    """Like url, but without adding the resource directory.
    """
    absolute_path = absolute_path.encode('utf_8')
    return u"file:///" + urllib.quote(absolute_path, safe=":~\\")
