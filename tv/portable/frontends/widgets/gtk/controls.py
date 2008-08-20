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

"""miro.frontends.widgets.gtk.controls -- Control Widgets."""

import gtk
import weakref

from miro.frontends.widgets.gtk.base import Widget

class TextEntry(Widget):
    def __init__(self, initial_text=None, hidden=False):
        Widget.__init__(self)
        self.create_signal('activate')
        self.create_signal('changed')
        self.set_widget(gtk.Entry())
        self.forward_signal('activate')
        self.forward_signal('changed')
        if initial_text is not None:
            self._widget.set_text(initial_text)
        if hidden:
            self.set_invisible(hidden)

    def set_text(self, text):
        self._widget.set_text(text)

    def get_text(self):
        return self._widget.get_text().decode('utf-8')

    def set_width(self, chars):
        self._widget.set_width_chars(chars)

    def set_invisible(self, setting):
        self._widget.props.visibility = not setting

    def set_activates_default(self, setting):
        self._widget.set_activates_default(setting)

    def enable_widget(self):
        self._widget.set_sensitive(True)

    def disable_widget(self):
        self._widget.set_sensitive(False)

class Checkbox(Widget):
    """Widget that the user can toggle on or off."""

    def __init__(self, label):
        Widget.__init__(self)
        self.set_widget(gtk.CheckButton(label))

    def get_checked(self):
        return self._widget.get_active()

    def set_checked(self, value):
        self._widget.set_active(value)

    def enable_widget(self):
        self._widget.set_sensitive(True)

    def disable_widget(self):
        self._widget.set_sensitive(False)

class RadioButtonGroup:
    """RadioButtonGroup.

    Create the group, then create a bunch of RadioButtons passing in the group.
    """
    def __init__(self):
        self._buttons = []

    def add_button(self, button):
        self._buttons.append(button)

    def get_buttons(self):
        return self._buttons

    def get_selected(self):
        for mem in self._buttons:
            if mem.get_selected():
                return mem

    def set_selected(self, button):
        for mem in self._buttons:
            if mem is button:
                mem._widget.set_active(True)
            else:
                mem._widget.set_active(False)


# use a weakref so that we're not creating circular references between
# RadioButtons and RadioButtonGroups
radio_button_to_group_mapping = weakref.WeakValueDictionary()

class RadioButton(Widget):
    """RadioButton."""
    def __init__(self, label, group=None):
        Widget.__init__(self)
        self.set_widget(gtk.RadioButton(label=label))
        self.create_signal('clicked')
        self.forward_signal('clicked')

        if group:
            buttons = group.get_buttons()
            if buttons:
                self._widget.set_group(buttons[0]._widget)
        else:
            group = RadioButtonGroup()

        group.add_button(self)
        oid = id(self)
        radio_button_to_group_mapping[oid] = group

    def get_group(self):
        return radio_button_to_group_mapping[id(self)]

    def get_selected(self):
        return self._widget.get_active()

    def enable_widget(self):
        self._widget.set_sensitive(True)

    def disable_widget(self):
        self._widget.set_sensitive(False)
