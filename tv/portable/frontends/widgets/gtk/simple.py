# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

"""simple.py -- Collection of simple widgets."""

import gtk
import gobject
import pango

from miro.frontends.widgets import widgetconst
from miro.frontends.widgets.gtk.base import Widget, Bin

class Image(object):
    def __init__(self, path):
        self.pixbuf = gtk.gdk.pixbuf_new_from_file(path)
        self.width = self.pixbuf.get_width()
        self.height = self.pixbuf.get_height()

    def resize(self, width, height):
        return ResizedImage(self, width, height)

class ResizedImage(Image):
    def __init__(self, image, width, height):
        self.pixbuf = image.pixbuf.scale_simple(width, height,
                gtk.gdk.INTERP_BILINEAR)
        self.width = width
        self.height = height

class ImageDisplay(Widget):
    def __init__(self, image):
        Widget.__init__(self)
        self.image = image
        self.set_widget(gtk.Image())
        self._widget.set_from_pixbuf(image.pixbuf)

class AnimatedImageDisplay(Widget):
    def __init__(self, path):
        Widget.__init__(self)
        self.set_widget(gtk.Image())
        self._widget.set_from_animation(gtk.gdk.PixbufAnimation(path))

class Label(Widget):
    """Widget that displays simple text."""
    def __init__(self, text=""):
        Widget.__init__(self)
        self.set_widget(gtk.Label())
        self.wrapped_widget_connect('style-set', self.on_style_set)
        if text:
            self.set_text(text)
        self.attr_list = pango.AttrList()
        self.font_description = self._widget.style.font_desc.copy()
        self.scale_factor = 1.0

    def set_bold(self, bold):
        if bold:
            weight = pango.WEIGHT_BOLD
        else:
            weight = pango.WEIGHT_NORMAL
        self.font_description.set_weight(weight)
        self.set_attr(pango.AttrFontDesc(self.font_description))

    def set_size(self, size):
        if size == widgetconst.SIZE_NORMAL:
            self.scale_factor = 1
        elif size == widgetconst.SIZE_SMALL:
            self.scale_factor = 0.85
        else:
            self.scale_factor = size
        baseline = self._widget.style.font_desc.get_size()
        self.font_description.set_size(int(baseline * self.scale_factor))
        self.set_attr(pango.AttrFontDesc(self.font_description))

    def on_style_set(self, widget, old_style):
        self.set_size(self.scale_factor)

    def set_wrap(self, wrap):
        self._widget.set_line_wrap(wrap)

    def set_text(self, text):
        self._widget.set_text(text)

    def get_text(self):
        self._widget.get_text().decode('utf-8')

    def set_attr(self, attr):
        attr.end_index = 65535
        self.attr_list.change(attr)
        self._widget.set_attributes(self.attr_list)

    def set_color(self, color):
        # It seems like 'text' is the color we want to change, but fg is
        # actually the one that changes it for me.  Change them both just to
        # be sure.
        for state in xrange(5):
            self.modify_style('fg', state, self.make_color(color))
            self.modify_style('text', state, self.make_color(color))

    def baseline(self):
        pango_context = self._widget.get_pango_context()
        metrics = pango_context.get_metrics(self.font_description)
        return pango.PIXELS(metrics.get_descent())

    def hide(self):
        self._widget.hide()

    def show(self):
        self._widget.show()


class Scroller(Bin):
    def __init__(self, horizontal, vertical):
        Bin.__init__(self)
        self.set_widget(gtk.ScrolledWindow())
        if horizontal:
            h_policy = gtk.POLICY_AUTOMATIC
        else:
            h_policy = gtk.POLICY_NEVER
        if vertical:
            v_policy = gtk.POLICY_AUTOMATIC
        else:
            v_policy = gtk.POLICY_NEVER
        self._widget.set_policy(h_policy, v_policy)

    def set_has_borders(self, has_border):
        pass

    def add_child_to_widget(self):
        if (isinstance(self.child._widget, gtk.TreeView) or
                isinstance(self.child._widget, gtk.TextView)):
            # child has native scroller
            self._widget.add(self.child._widget)
        else:
            self._widget.add_with_viewport(self.child._widget)

class SolidBackground(Bin):
    def __init__(self, color=None):
        Bin.__init__(self)
        self.set_widget(gtk.EventBox())
        if color is not None:
            self.set_background_color(color)

    def set_background_color(self, color):
        self.modify_style('base', gtk.STATE_NORMAL, self.make_color(color))
        self.modify_style('bg', gtk.STATE_NORMAL, self.make_color(color))

class Expander(Bin):
    def __init__(self, child=None):
        Bin.__init__(self)
        self.set_widget(gtk.Expander())
        if child is not None:
            self.add(child)
        self.label = None
        # This is a complete hack.  GTK expanders have a transparent
        # background most of the time, except when they are prelighted.  So we
        # just set the background to white there because that's what should
        # happen in the item list.
        self.modify_style('bg', gtk.STATE_PRELIGHT,
                gtk.gdk.color_parse('white'))

    def set_spacing(self, spacing):
        self._widget.set_spacing(spacing)

    def set_label(self, widget):
        self.label = widget
        self._widget.set_label_widget(widget._widget)
        widget._widget.show()

    def set_expanded(self, expanded):
        self._widget.set_expanded(expanded)

class ProgressBar(Widget):
    def __init__(self):
        Widget.__init__(self)
        self.set_widget(gtk.ProgressBar())
        self._timer = None

    def set_progress(self, fraction):
        self._widget.set_fraction(fraction)

    def start_pulsing(self):
        if self._timer is None:
            self._timer = gobject.timeout_add(100, self._do_pulse)

    def stop_pulsing(self):
        if self._timer:
            gobject.source_remove(self._timer)
            self._timer = None

    def _do_pulse(self):
        self._widget.pulse()
        return True
