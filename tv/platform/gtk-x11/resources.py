# Democracy Player - an RSS based video player application
# Copyright (C) 2005-2006 Participatory Culture Foundation
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

import os
import re
import sys
import urllib
import config
import prefs

resource_root = os.environ.get('MIRO_RESOURCE_ROOT',
        '/usr/share/democracy/resources/')
resource_root = os.path.abspath(resource_root)

share_root = os.environ.get('MIRO_SHARE_ROOT',
                            '/usr/share/')
share_root = os.path.abspath(share_root)

# Note: some of these functions are probably not absolutely correct in
# the face of funny characters in the input paths. In particular,
# url() doesn't DTRT when the path contains spaces. But they should be
# sufficient for resolving resources, since we have control over the
# filenames.

# Find the full path to a resource data file. 'relative_path' is
# expected to be supplied in Unix format, with forward-slashes as
# separators. 
def path(relative_path):
    return os.path.join(resource_root, relative_path)

def sharePath(relative_path):
    return os.path.join(share_root, relative_path)

# As path(), but return a file: URL instead.
def url(relative_path):
    return u'file://%s' % urllib.quote(path(relative_path))

def absoluteUrl(absolute_path):
    """Like url, but without adding the resource directory.
    """
    return u"file://%s" % urllib.quote(absolute_path)
