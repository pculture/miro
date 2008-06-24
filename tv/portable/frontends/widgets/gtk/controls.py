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

from miro.frontends.widgets.gtk.base import Widget

class TextEntry(Widget):
    def __init__(self, text=None):
        Widget.__init__(self)
        self.set_widget(gtk.Entry())
        if text is not None:
            self._widget.set_text(text)

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

class Checkbox(Widget):
    """Widget that the user can toggle on or off."""

    def __init__(self, label):
        Widget.__init__(self)
        self.set_widget(gtk.CheckButton(label))

    def get_checked(self):
        return self._widget.get_active()

    def set_checked(self, value):
        self._widget.set_active(value)
