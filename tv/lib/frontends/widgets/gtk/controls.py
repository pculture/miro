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

"""miro.frontends.widgets.gtk.controls -- Control Widgets."""

import gtk
import pango

from miro.frontends.widgets import widgetconst
from miro.frontends.widgets.gtk import layout
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

    def start_editing(self, text):
        self.set_text(text)
        self.focus()
        self._widget.emit('move-cursor', gtk.MOVEMENT_BUFFER_ENDS, 1, False)

    def set_text(self, text):
        self._widget.set_text(text)

    def get_text(self):
        return self._widget.get_text().decode('utf-8')

    def set_max_length(self, chars):
        self._widget.set_max_length(chars)

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

class NumberEntry(TextEntry):
    def __init__(self, initial_text=None):
        TextEntry.__init__(self, initial_text)
        self._widget.connect('changed', self.validate)
        self.previous_text = initial_text or ""

    def validate(self, entry):
        text = self.get_text()
        if text.isdigit() or not text:
            self.previous_text = text
        else:
            self._widget.set_text(self.previous_text)

class SecureTextEntry(TextEntry):
    def __init__(self, initial_text=None):
        TextEntry.__init__(self, initial_text)
        self.set_invisible(True)

class MultilineTextEntry(Widget):
    entry_class = gtk.TextView
    def __init__(self, initial_text=None, border=False):
        Widget.__init__(self)
        self.set_widget(self.entry_class())
        if initial_text is not None:
            self.set_text(initial_text)
        self._widget.set_wrap_mode(gtk.WRAP_WORD)
        self._widget.set_accepts_tab(False)
        self.border = border

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

    def set_editable(self, editable):
        self._widget.set_editable(editable)

class Checkbox(Widget, BinBaselineCalculator):
    """Widget that the user can toggle on or off."""

    def __init__(self, text=None, bold=False):
        Widget.__init__(self)
        BinBaselineCalculator.__init__(self)
        if text is None:
            text = ''
        self.set_widget(gtk.CheckButton())
        self.label = Label(text)
        self._widget.add(self.label._widget)
        self.label._widget.show()
        self.create_signal('toggled')
        self.forward_signal('toggled')
        if bold:
            self.label.set_bold(True)

    def get_checked(self):
        return self._widget.get_active()

    def set_checked(self, value):
        self._widget.set_active(value)

    def set_size(self, scale_factor):
        self.label.set_size(scale_factor)

    def get_text_padding(self):
        """
        Returns the amount of space the checkbox takes up before the label.
        """
        indicator_size = self._widget.style_get_property('indicator-size')
        indicator_spacing = self._widget.style_get_property(
            'indicator-spacing')
        focus_width = self._widget.style_get_property('focus-line-width')
        focus_padding = self._widget.style_get_property('focus-padding')
        return (indicator_size + 3 * indicator_spacing + 2 * (focus_width +
                focus_padding))

class RadioButtonGroup(Widget, BinBaselineCalculator):
    """RadioButtonGroup.

    Create the group, then create a bunch of RadioButtons passing in the group.

    NB: GTK has built-in radio button grouping functionality, and we should
    be using that but we need this widget for portable code.  We create
    a dummy GTK radio button and make this the "root" button which gets
    inherited by all buttons in this radio button group.
    """
    def __init__(self):
        Widget.__init__(self)
        BinBaselineCalculator.__init__(self)
        self.set_widget(gtk.RadioButton(label=""))
        self._widget.set_active(False)
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

class RadioButton(Widget, BinBaselineCalculator):
    """RadioButton."""
    def __init__(self, label, group=None):
        Widget.__init__(self)
        BinBaselineCalculator.__init__(self)
        if group:
            self.group = group
        else:
            self.group = RadioButtonGroup()

        self.set_widget(gtk.RadioButton(group=self.group._widget, label=label))
        self.create_signal('clicked')
        self.forward_signal('clicked')

        group.add_button(self)

    def get_group(self):
        return self.group

    def get_selected(self):
        return self._widget.get_active()

    def set_selected(self):
        self.group.set_selected(self)

class Button(Widget, BinBaselineCalculator):
    def __init__(self, text, style='normal', width=None):
        Widget.__init__(self)
        BinBaselineCalculator.__init__(self)
        # We just ignore style here, GTK users expect their own buttons.
        self.set_widget(gtk.Button())
        self.create_signal('clicked')
        self.forward_signal('clicked')
        self.label = Label(text)
        # only honor width if its bigger than the width we need to display the
        # label (#18994)
        if width and width > self.label.get_width():
            alignment = layout.Alignment(0.5, 0.5, 0, 0)
            alignment.set_size_request(width, -1)
            alignment.add(self.label)
            self._widget.add(alignment._widget)
        else:
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

    def set_width(self, width):
        self._widget.set_property('width-request', width)
