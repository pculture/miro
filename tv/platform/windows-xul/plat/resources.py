# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

import os
import re
import sys
import urllib
import platform

from miro.plat import specialfolders

def appRoot():
    """Determine the directory the .exe file is located in.  Taken from the
    WhereAmI recipe on the py2exe website.
    """
    exe_path = unicode(sys.executable, sys.getfilesystemencoding())
    return os.path.dirname(exe_path)

def root():
    return os.path.join(appRoot(), 'resources')

def share_path(path):
    return os.path.join(root(), path)

# Note: some of these functions are probably not absolutely correct in
# the face of funny characters in the input paths. In particular,
# url() doesn't DTRT when the path contains spaces. But they should be
# sufficient for resolving resources, since we have control over the
# filenames.

# Find the full path to a resource data file. 'relative_path' is
# expected to be supplied in Unix format, with forward-slashes as
# separators. The output, though, uses the native platform separator.
def path(relative_path):
    abspath = os.path.abspath(os.path.join(root(), relative_path))
    return abspath.replace("/", "\\")

def url(relative_path):
    return absoluteUrl(path(relative_path))

def absoluteUrl(absolute_path):
    """Like url, but without adding the resource directory.
    """
    absolute_path = absolute_path.encode('utf_8')
    return u"file:///" + urllib.quote(absolute_path, safe=":~\\")

def _getThemeDirectory():
    # We don't get the publisher and long app name from the config so
    # changing the app name doesn't change the support directory
    path = os.path.join(specialfolders.commonAppDataDirectory,
                        u'Participatory Culture Foundation',
                        u'Miro',
                        u'Themes')
    try:
        os.makedirs(path)
    except:
        pass
    return path

def theme_path(theme, relative_path):
    return os.path.join(_getThemeDirectory(), theme, relative_path)

def get_osname():
    osname = '%s %s %s' % (platform.system(), platform.release(),
            platform.machine())
    return osname

def get_default_search_dir():
    return specialfolders.get_special_folder("My Videos")
