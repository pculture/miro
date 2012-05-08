# Miro - an RSS based video player application
# Copyright (C) 2012
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
Hide/show the mouse for fullscreen video
"""

import gtk.gdk

_hidden_cursor = None

def ensure_hidden_cursor():
    global _hidden_cursor

    if _hidden_cursor is None:
        pixmap = gtk.gdk.Pixmap(None, 1, 1, 1)
        color = gtk.gdk.Color()
        _hidden_cursor = gtk.gdk.Cursor(pixmap, pixmap, color, color, 0, 0)

def hide(window):
    """Hide the mouse.

    :param window: gtk.gdk.Window that's fullscreened
    """
    ensure_hidden_cursor()
    window.set_cursor(_hidden_cursor)

def unhide(window):
    """Unhide the mouse.

    :param window: gtk.gdk.Window that's fullscreened
    """
    window.set_cursor(None)

