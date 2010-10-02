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

"""
Holds functions that return import directories and other platform-oriented
functions.

.. Note::

   Some of these functions are probably not absolutely correct in the
   face of funny characters in the input paths. In particular,
   :fun:`url` doesn't DTRT when the path contains spaces. But they
   should be sufficient for resolving resources, since we have control
   over the filenames.
"""

import os
import urllib
import platform

RESOURCE_ROOT = os.path.abspath(
    os.environ.get('MIRO_RESOURCE_ROOT', '/usr/share/miro/resources/'))
SHARE_ROOT = os.path.abspath(
    os.environ.get('MIRO_SHARE_ROOT', '/usr/share/'))

def root():
    return RESOURCE_ROOT

def extension_roots():
    return []

def path(relative_path):
    """Find the full path to a resource data file. 'relative_path' is
    expected to be supplied in Unix format, with forward-slashes as
    separators.
    """
    return os.path.join(RESOURCE_ROOT, relative_path)

def share_path(relative_path):
    return os.path.join(SHARE_ROOT, relative_path)

def url(relative_path):
    """As path(), but return a file: URL instead.
    """
    return u'file://%s' % urllib.quote(path(relative_path))

def theme_path(theme, relative_path):
    return os.path.join('/usr/share/miro/themes', theme, relative_path)

def check_kde():
    return os.environ.get("KDE_FULL_SESSION", None) != None

def open_url(url):
    # We could use Python's webbrowser.open() here, but unfortunately,
    # it doesn't have the same semantics under UNIX as under other
    # OSes. Sometimes it blocks, sometimes it doesn't.
    if check_kde():
        os.spawnlp(os.P_NOWAIT, "kfmclient", "kfmclient", "exec", url)
    else:
        os.spawnlp(os.P_NOWAIT, "gnome-open", "gnome-open", url)

def open_file(filename):
    if check_kde():
        os.spawnlp(os.P_NOWAIT, "kfmclient", "kfmclient",
                   "exec", "file://" + filename)
    else:
        os.spawnlp(os.P_NOWAIT, "gnome-open", "gnome-open", filename)

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

def _clean_piece(piece):
    return piece.replace(";", " ")

def get_osname():
    """Composes and returns the osname section of the user agent.

    The osname currently looks something like this::

        Linux i686; Ubuntu 9.04
          1     2        3

    **1** - comes from ``platform.uname()[0]``

    **2** - comes from ``platform.machine()``

    **3** - comes from the first two parts of ``platform.dist``

    This function also removes any stray ``;``.
    """
    osname = ["%s %s" % (platform.uname()[0], platform.machine())]
    osname.append(" ".join(platform.dist("Unknown", "Unknown", "Unknown")[0:2]))
    osname = "; ".join([_clean_piece(s) for s in osname])
    return osname

def get_default_search_dir():
    return os.path.expanduser("~/")
