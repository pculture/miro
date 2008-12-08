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

import os
import urllib

resource_root = os.environ.get('MIRO_RESOURCE_ROOT', '/usr/share/miro/resources/')
resource_root = os.path.abspath(resource_root)

share_root = os.environ.get('MIRO_SHARE_ROOT', '/usr/share/')
share_root = os.path.abspath(share_root)

# Note: some of these functions are probably not absolutely correct in
# the face of funny characters in the input paths. In particular,
# url() doesn't DTRT when the path contains spaces. But they should be
# sufficient for resolving resources, since we have control over the
# filenames.

def root():
    return resource_root

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

def theme_path(theme, relative_path):
    return os.path.join('/usr/share/miro/themes', theme, relative_path)

def check_kde():
    return os.environ.get("KDE_FULL_SESSION", None) != None

def get_autostart_dir():
    if check_kde():
        if os.environ.get("KDE_SESSION_VERSION") == "4":
            autostart_dir = "~/.kde/share/autostart"
        else:
            autostart_dir = "~/.kde/Autostart"
    else:
        config_home = os.environ.get('XDG_CONFIG_HOME', '~/.config')
        autostart_dir = os.path.join(config_home, "autostart")

    autostart_dir = os.path.expanduser(autostart_dir)
    return autostart_dir
