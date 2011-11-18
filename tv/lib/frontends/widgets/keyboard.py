# Miro - an RSS based video player application
# Copyright (C) 2011
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

"""Define keyboard input in a platform-independant way."""

(CTRL, ALT, SHIFT, CMD, MOD, RIGHT_ARROW, LEFT_ARROW, UP_ARROW,
 DOWN_ARROW, SPACE, ENTER, DELETE, BKSPACE, ESCAPE,
 F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12) = range(26)

class Shortcut:
    """Defines a shortcut key combination used to trigger this
    menu item.

    The first argument is the shortcut key.  Other arguments are
    modifiers.

    Examples:

    >>> Shortcut("x", MOD)
    >>> Shortcut(BKSPACE, MOD)

    This is wrong:

    >>> Shortcut(MOD, "x")
    """
    def __init__(self, shortcut, *modifiers):
        self.shortcut = shortcut
        self.modifiers = modifiers

    def _get_key_symbol(self, value):
        """Translate key values to their symbolic names."""
        if isinstance(self.shortcut, int):
            shortcut_string = '<Unknown>'
            for name, value in globals().iteritems():
                if value == self.shortcut:
                    return name
        return repr(value)

    def __str__(self):
        shortcut_string = self._get_key_symbol(self.shortcut)
        mod_string = repr(set(self._get_key_symbol(k) for k in
                              self.modifiers))
        return "Shortcut(%s, %s)" % (shortcut_string, mod_string)
