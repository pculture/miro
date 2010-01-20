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

"""miro.frontends.widgets.gtk.controls -- Control Widgets."""

import weakref

import gtk
import gobject
import pango

from miro import searchengines
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets.gtk.base import Widget
from miro.frontends.widgets.gtk.simple import Label

class BinBaselineCalculator(object):
    """Mixin class that defines the baseline method for gtk.Bin subclasses,
    where the child is the label that we are trying to get the baseline for.
    """

    def baseline(self):
        my_size = self._widget.size_request()
        child_size = self._widget.child.size_request()
        ypad = (my_size[1] - child_size[1]) / 2

        pango_context = self._widget.get_pango_context()
        metrics = pango_context.get_metrics(self._widget.style.font_desc)
        return pango.PIXELS(metrics.get_descent()) + ypad

class TextEntry(Widget):
    entry_class = gtk.Entry
    def __init__(self, initial_text=None):
        Widget.__init__(self)
        self.create_signal('activate')
        self.create_signal('changed')
        self.create_signal('validate')
        self.set_widget(self.entry_class())
        self.forward_signal('activate')
        self.forward_signal('changed')
        if initial_text is not None:
            self.set_text(initial_text)

    def focus(self):
        self._widget.grab_focus()

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

    def baseline(self):
        layout_height = pango.PIXELS(self._widget.get_layout().get_size()[1])
        ypad = (self._widget.size_request()[1] - layout_height) / 2
        pango_context = self._widget.get_pango_context()
        metrics = pango_context.get_metrics(self._widget.style.font_desc)
        return pango.PIXELS(metrics.get_descent()) + ypad

class SecureTextEntry(TextEntry):
    def __init__(self, initial_text=None):
        TextEntry.__init__(self, initial_text)
        self.set_invisible(True)

class MultilineTextEntry(Widget):
    entry_class = gtk.TextView
    def __init__(self, initial_text=None):
        Widget.__init__(self)
        self.set_widget(self.entry_class())
        if initial_text is not None:
            self.set_text(initial_text)
        self._widget.set_wrap_mode(gtk.WRAP_WORD)

    def focus(self):
        self._widget.grab_focus()

    def set_text(self, text):
        self._widget.get_buffer().set_text(text)

    def get_text(self):
        buffer_ = self._widget.get_buffer()
        return buffer_.get_text(*(buffer_.get_bounds())).decode('utf-8')

    def baseline(self):
        # FIXME
        layout_height = pango.PIXELS(self._widget.get_layout().get_size()[1])
        ypad = (self._widget.size_request()[1] - layout_height) / 2
        pango_context = self._widget.get_pango_context()
        metrics = pango_context.get_metrics(self._widget.style.font_desc)
        return pango.PIXELS(metrics.get_descent()) + ypad

class Checkbox(Widget, BinBaselineCalculator):
    """Widget that the user can toggle on or off."""

    def __init__(self, label):
        Widget.__init__(self)
        self.set_widget(gtk.CheckButton(label))
        self.create_signal('toggled')
        self.forward_signal('toggled')

    def get_checked(self):
        return self._widget.get_active()

    def set_checked(self, value):
        self._widget.set_active(value)

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

class RadioButton(Widget, BinBaselineCalculator):
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

    def set_selected(self):
        radio_button_to_group_mapping[id(self)].set_selected(self)

class Button(Widget, BinBaselineCalculator):
    def __init__(self, text, style='normal'):
        Widget.__init__(self)
        # We just ignore style here, GTK users expect their own buttons.
        self.set_widget(gtk.Button())
        self.create_signal('clicked')
        self.forward_signal('clicked')
        self.label = Label(text)
        self._widget.add(self.label._widget)
        self.label._widget.show()

    def set_text(self, title):
        self.label.set_text(title)

    def set_bold(self, bold):
        self.label.set_bold(bold)

    def set_size(self, scale_factor):
        self.label.set_size(scale_factor)

    def set_color(self, color):
        self.label.set_color(color)

class OptionMenu(Widget):
    def __init__(self, options):
        Widget.__init__(self)
        self.create_signal('changed')

        self.set_widget(gtk.ComboBox(gtk.ListStore(str, str)))
        self.cell = gtk.CellRendererText()
        self._widget.pack_start(self.cell, True)
        self._widget.add_attribute(self.cell, 'text', 0)
        if options:
            for option in options:
                self._widget.get_model().append((option, 'booya'))
            self._widget.set_active(0)
        self.options = options
        self.wrapped_widget_connect('changed', self.on_changed)

    def baseline(self):
        my_size = self._widget.size_request()
        child_size = self._widget.child.size_request()
        ypad = self.cell.props.ypad + (my_size[1] - child_size[1]) / 2

        pango_context = self._widget.get_pango_context()
        metrics = pango_context.get_metrics(self._widget.style.font_desc)
        return pango.PIXELS(metrics.get_descent()) + ypad 

    def set_bold(self, bold):
        if bold:
            self.cell.props.weight = pango.WEIGHT_BOLD
        else:
            self.cell.props.weight = pango.WEIGHT_NORMAL

    def set_size(self, size):
        if size == widgetconst.SIZE_NORMAL:
            self.cell.props.scale = 1
        else:
            self.cell.props.scale = 0.85

    def set_color(self, color):
        self.cell.props.foreground_gdk = self.make_color(color)

    def set_selected(self, index):
        self._widget.set_active(index)

    def get_selected(self):
        return self._widget.get_active()

    def on_changed(self, widget):
        index = widget.get_active()
        self.emit('changed', index)
