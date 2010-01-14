# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""keymap.py -- Map portable key values to GTK ones.
"""

import gtk

from miro.frontends.widgets import menus

menubar_mod_map = {
    menus.CTRL: '<Ctrl>',
    menus.ALT: '<Alt>',
    menus.SHIFT: '<Shift>',
}

menubar_key_map = {
    menus.RIGHT_ARROW: 'Right',
    menus.LEFT_ARROW: 'Left',
    menus.UP_ARROW: 'Up',
    menus.DOWN_ARROW: 'Down',
    menus.SPACE: 'space',
    menus.ENTER: 'Return',
    menus.DELETE: 'Delete',
    menus.BKSPACE: 'BackSpace',
    menus.ESCAPE: 'Escape',
    '>': 'greater',
    '<': 'less'
}

# These are reversed versions of menubar_key_map and menubar_mod_map
gtk_key_map = dict((i[1], i[0]) for i in menubar_key_map.items())

def translate_gtk_modifiers(event):
    """Convert a keypress event to a set of modifiers from the menus
    module.
    """
    modifiers = set()
    if event.state & gtk.gdk.CONTROL_MASK:
        modifiers.add(menus.CTRL)
    if event.state & gtk.gdk.MOD1_MASK:
        modifiers.add(menus.ALT)
    if event.state & gtk.gdk.SHIFT_MASK:
        modifiers.add(menus.SHIFT)
    return modifiers

def translate_gtk_event(event):
    """Convert a GTK key event into the tuple (key, modifiers) where
    key and modifiers are from the menus module.
    """
    gtk_keyval = gtk.gdk.keyval_name(event.keyval)
    if gtk_keyval == None:
        return None
    if len(gtk_keyval) == 1:
        key = gtk_keyval
    else:
        key = gtk_key_map.get(gtk_keyval)
    modifiers = translate_gtk_modifiers(event)
    return key, modifiers
