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

import os
import platform
import urllib
from miro.plat import bundle

def root():
    # XXX sigh.
    # Unicode kludge.  This wouldn't be a problem once we switch to Python 3.
    path = os.path.join(bundle.getBundleResourcePath(), u'resources')
    return path.encode('utf-8')

def extension_roots():
    syspath = os.path.join(bundle.getBundleResourcePath(), u'extensions')
    syspath = syspath.encode('utf-8')
    return [syspath, "%(supportdir)s/extensions"]

# Find the full path to a resource data file. 'relative_path' is
# expected to be supplied in Unix format, with forward-slashes as
# separators. The output, though, uses the native platform separator.
def path(relative_path):
    # XXX sigh.
    # Unicode kludge.  This wouldn't be a problem once we switch to Python 3.
    if isinstance(relative_path, unicode):
        relative_path = relative_path.encode('utf-8')
    rsrcpath = os.path.join(root(), relative_path)
    return os.path.abspath(rsrcpath)

# As path(), but return a file: URL instead.
def url(relative_path):
    return u"file://" + urllib.quote(path(relative_path))

def theme_path(theme, relative_path):
    # XXX sigh.
    # Unicode kludge.  This wouldn't be a problem once we switch to Python 3.
    bundlePath = bundle.getBundlePath().encode('utf-8')
    if isinstance(theme, unicode):
        theme = theme.encode('utf-8')
    if isinstance(relative_path, unicode):
        relative_path = relative_path.encode('utf-8')
    path = os.path.join(bundlePath, "Contents", "Theme", theme,
            relative_path)
    return path

def get_osname():
    osname = '%s %s %s' % (platform.system(), platform.release(),
            platform.machine())
    return osname

def get_default_search_dir():
    return os.path.expanduser("~/")
