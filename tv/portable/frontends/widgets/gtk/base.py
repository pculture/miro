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

"""miro.frontends.widgets.gtk.base -- Base classes for GTK Widgets."""

import gtk

from miro import signals
from miro.frontends.widgets.gtk import window
from miro.frontends.widgets.gtk import wrappermap
from miro.frontends.widgets.gtk.weakconnect import weak_connect
from miro.frontends.widgets.gtk import keymap

def make_gdk_color(miro_color):
    def convert_value(value):
        return int(round(value * 65535))

    values = tuple(convert_value(c) for c in miro_color)
    return gtk.gdk.Color(*values)

class Widget(signals.SignalEmitter):
    """Base class for GTK widgets.  

    The actual GTK Widget is stored in '_widget'.

    signals:

        'size-allocated' (widget, width, height): The widget had it's size
            allocated.
    """
    def __init__(self, *signal_names):
        signals.SignalEmitter.__init__(self, *signal_names)
        self.create_signal('size-allocated')
        self.create_signal('key-press')
        self.style_mods = {}
        self.use_custom_style = False
        self._disabled = False

    def wrapped_widget_connect(self, signal, method, *user_args):
        """Connect to a signal of the widget we're wrapping.

        We use a weak reference to ensures that we don't have circular
        references between the wrapped widget and the wrapper widget.
        """
        return weak_connect(self._widget, signal, method, *user_args)

    def set_widget(self, widget):
        self._widget = widget
        wrappermap.add(self._widget, self)
        self.wrapped_widget_connect('hierarchy_changed',
                self.on_hierarchy_changed)
        self.wrapped_widget_connect('size-allocate', self.on_size_allocate)
        self.wrapped_widget_connect('key-press-event', self.on_key_press)
        self.use_custom_style_callback = None

    def on_hierarchy_changed(self, widget, previous_toplevel):
        toplevel = widget.get_toplevel()
        if not (toplevel.flags() & gtk.TOPLEVEL):
            toplevel = None
        if previous_toplevel != toplevel:
            if self.use_custom_style_callback:
                old_window = wrappermap.wrapper(previous_toplevel)
                old_window.disconnect(self.use_custom_style_callback)
            if toplevel is not None:
                window = wrappermap.wrapper(toplevel)
                callback_id = window.connect('use-custom-style-changed',
                        self.on_use_custom_style_changed)
                self.use_custom_style_callback = callback_id
            else:
                self.use_custom_style_callback = None
            if previous_toplevel is None:
                # Setup our initial state
                self.on_use_custom_style_changed(window)

    def on_size_allocate(self, widget, allocation):
        self.emit('size-allocated', allocation.width, allocation.height)

    def on_key_press(self, widget, event):
        key, modifiers = keymap.translate_gtk_event(event)
        return self.emit('key-press', key, modifiers)

    def on_use_custom_style_changed(self, window):
        self.use_custom_style = window.use_custom_style
        if not self.style_mods:
            return # no need to do any work here
        if self.use_custom_style:
            for (what, state), color in self.style_mods.items():
                self.do_modify_style(what, state, color)
        else:
            # This should reset the style changes we've made
            self._widget.modify_style(gtk.RcStyle())
        self.handle_custom_style_change()

    def handle_custom_style_change(self):
        """Called when the user changes a from a theme where we don't want to
        use our custom style to one where we do, or vice-versa.  The Widget
        class handles changes that used modify_style(), but subclasses might
        want to do additional work.
        """
        pass

    def modify_style(self, what, state, color):
        """Change the style of our widget.  This method checks to see if we
        think the user's theme is compatible with our stylings, and doesn't
        change things if not.  what is either 'base', 'text', 'bg' or 'fg'
        depending on which color is to be changed.
        """
        if self.use_custom_style:
            self.do_modify_style(what, state, color)
        self.style_mods[(what, state)] = color

    def unmodify_style(self, what, state):
        if (what, state) in self.style_mods:
            del self.style_mods[(what, state)]
            default_color = getattr(self.style, what)[state]
            self.do_modify_style(what, state, default_color)

    def do_modify_style(self, what, state, color):
        if what == 'base':
            self._widget.modify_base(state, color)
        elif what == 'text':
            self._widget.modify_text(state, color)
        elif what == 'bg':
            self._widget.modify_bg(state, color)
        elif what == 'fg':
            self._widget.modify_fg(state, color)
        else:
            raise ValueError("Unknown what in do_modify_style: %s" % what)

    def get_window(self):
        gtk_window = self._widget.get_toplevel()
        return wrappermap.wrapper(gtk_window)

    def get_size_request(self):
        return self._widget.size_request()

    def invalidate_size_request(self):
        # FIXME - do we need to do anything here?
        pass

    def set_size_request(self, width, height):
        self._widget.set_size_request(width, height)

    def relative_position(self, other_widget):
        return other_widget._widget.translate_coordinates(self._widget, 0, 0)

    def convert_gtk_color(self, color):
        return (color.red / 65535.0, color.green / 65535.0, 
                color.blue / 65535.0)

    def get_width(self):
        try:
            return self._widget.allocation.width
        except AttributeError:
            return -1
    width = property(get_width)

    def get_height(self):
        try:
            return self._widget.allocation.height
        except AttributeError:
            return -1
    height = property(get_height)

    def queue_redraw(self):
        if self._widget:
            self._widget.queue_draw()

    def forward_signal(self, signal_name, forwarded_signal_name=None):
        """Add a callback so that when the GTK widget emits a signal, we emit
        signal from the wrapper widget.
        """
        if forwarded_signal_name is None:
            forwarded_signal_name = signal_name
        self.wrapped_widget_connect(signal_name, self.do_forward_signal,
                forwarded_signal_name)

    def do_forward_signal(self, widget, *args):
        forwarded_signal_name = args[-1]
        args = args[:-1]
        self.emit(forwarded_signal_name, *args)

    def make_color(self, miro_color):
        color = make_gdk_color(miro_color)
        self._widget.get_colormap().alloc_color(color)
        return color

    def enable(self):
        self._disabled = False
        self._widget.set_sensitive(True)

    def disable(self):
        self._disabled = True
        self._widget.set_sensitive(False)

    def set_disabled(self, disabled):
        if disabled:
            self.disable()
        else:
            self.enable()

    def get_disabled(self):
        return self._disabled


class Bin(Widget):
    def __init__(self):
        Widget.__init__(self)
        self.child = None

    def add(self, child):
        if self.child is not None:
            raise ValueError("Already have a child: %s" % self.child)
        if child._widget.parent is not None:
            raise ValueError("%s already has a parent" % child)
        self.child = child
        self.add_child_to_widget()
        child._widget.show()

    def add_child_to_widget(self):
        self._widget.add(self.child._widget)

    def remove_child_from_widget(self):
        self._widget.get_child().hide() # otherwise gtkmozembed gets confused
        self._widget.remove(self._widget.get_child())

    def remove(self):
        if self.child is not None:
            self.child = None
            self.remove_child_from_widget()

    def set_child(self, new_child):
        self.remove()
        self.add(new_child)

    def enable(self):
        self.child.enable()

    def disable(self):
        self.child.disable()
