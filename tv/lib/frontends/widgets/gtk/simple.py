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

"""simple.py -- Collection of simple widgets."""

import gtk
import gobject
import pango

from miro.frontends.widgets import widgetconst
from miro.frontends.widgets.gtk.base import Widget, Bin

class Image(object):
    def __init__(self, path):
        try:
            self._set_pixbuf(gtk.gdk.pixbuf_new_from_file(path))
        except gobject.GError, ge:
            raise ValueError("%s" % ge)
        self.width = self.pixbuf.get_width()
        self.height = self.pixbuf.get_height()

    def _set_pixbuf(self, pixbuf):
        self.pixbuf = pixbuf
        self.width = self.pixbuf.get_width()
        self.height = self.pixbuf.get_height()

    def resize(self, width, height):
        width = int(round(width))
        height = int(round(height))
        resized_pixbuf = self.pixbuf.scale_simple(width, height,
                gtk.gdk.INTERP_BILINEAR)
        return TransformedImage(resized_pixbuf)

    def resize_for_space(self, width, height):
        """Returns an image scaled to fit into the specified space at the
        correct height/width ratio.
        """
        ratio = min(1.0 * width / self.width, 1.0 * height / self.height)
        return self.resize(ratio * self.width, ratio * self.height)

    def crop_and_scale(self, src_x, src_y, src_width, src_height, dest_width,
            dest_height):
        """Crop an image then scale it.

        The image will be cropped to the rectangle (src_x, src_y, src_width,
        src_height), that rectangle will be scaled to a new Image with tisez
        (dest_width, dest_height)
        """
        dest = gtk.gdk.Pixbuf(self.pixbuf.get_colorspace(),
                self.pixbuf.get_has_alpha(),
                self.pixbuf.get_bits_per_sample(), dest_width, dest_height)

        scale_x = dest_width / float(src_width)
        scale_y = dest_height / float(src_height)

        self.pixbuf.scale(dest, 0, 0, dest_width, dest_height,
                -src_x * scale_x, -src_y * scale_y, scale_x, scale_y,
                gtk.gdk.INTERP_BILINEAR)
        return TransformedImage(dest)

class TransformedImage(Image):
    def __init__(self, pixbuf):
        # XXX intentionally not calling direct super's __init__; we should do
        # this differently
        self._set_pixbuf(pixbuf)

class ImageDisplay(Widget):
    def __init__(self, image=None):
        Widget.__init__(self)
        self.set_widget(gtk.Image())
        self.set_image(image)

    def set_image(self, image):
        self.image = image
        if image is not None:
            self._widget.set_from_pixbuf(image.pixbuf)
        else:
            self._widget.clear()

class AnimatedImageDisplay(Widget):
    def __init__(self, path):
        Widget.__init__(self)
        self.set_widget(gtk.Image())
        self._animation = gtk.gdk.PixbufAnimation(path)
        # Set to animate before we are shown and stop animating after
        # we disappear.
        self._widget.connect('map', lambda w: self._set_animate(True))
        self._widget.connect('unmap-event',
                             lambda w, a: self._set_animate(False))

    def _set_animate(self, enabled):
        if enabled:
            self._widget.set_from_animation(self._animation)
        else:
            self._widget.clear()

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

    def get_preferred_width(self):
        return self._widget.size_request()[0]

    def on_style_set(self, widget, old_style):
        self.set_size(self.scale_factor)

    def set_wrap(self, wrap):
        self._widget.set_line_wrap(wrap)

    def set_alignment(self, alignment):
        # default to left.
        gtkalignment = gtk.JUSTIFY_LEFT
        if alignment == widgetconst.TEXT_JUSTIFY_LEFT:
            gtkalignment = gtk.JUSTIFY_LEFT
        elif alignment == widgetconst.TEXT_JUSTIFY_RIGHT:
            gtkalignment = gtk.JUSTIFY_RIGHT
        elif alignment == widgetconst.TEXT_JUSTIFY_CENTER:
            gtkalignment = gtk.JUSTIFY_CENTER
        self._widget.set_justify(gtkalignment)

    def get_alignment(self):
        return self._widget.get_justify()

    def get_width(self):
        return self._widget.get_layout().get_pixel_size()[0]

    def set_text(self, text):
        if isinstance(text, basestring):
            self._widget.set_text(text.encode('utf-8'))
        elif text is None:
            self._widget.set_text("Title Unknown")
        else:
            self._widget.set_text(text)

    def get_text(self):
        return self._widget.get_text().decode('utf-8')

    def set_selectable(self, val):
        self._widget.set_selectable(val)

    def set_attr(self, attr):
        attr.end_index = 65535
        self.attr_list.change(attr)
        self._widget.set_attributes(self.attr_list)

    def set_color(self, color):
        color_as_int = (int(c * 65535) for c in color)
        self.set_attr(pango.AttrForeground(*color_as_int))

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

    def set_background_color(self, color):
        pass

    def add_child_to_widget(self):
        if (isinstance(self.child._widget, gtk.TreeView) or
                isinstance(self.child._widget, gtk.TextView)):
            # child has native scroller
            self._widget.add(self.child._widget)
        else:
            self._widget.add_with_viewport(self.child._widget)
            self._widget.get_child().set_shadow_type(gtk.SHADOW_NONE)
        if isinstance(self.child._widget, gtk.TextView):
            self._widget.set_shadow_type(gtk.SHADOW_IN)
        else:
            self._widget.set_shadow_type(gtk.SHADOW_NONE)

    def prepare_for_dark_content(self):
        # this is just a hack for cocoa
        pass


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

class HLine(Widget):
    """A horizontal separator. Not to be confused with HSeparator, which is is
    a DrawingArea, not a Widget.
    """
    def __init__(self):
        Widget.__init__(self)
        self.set_widget(gtk.HSeparator())
