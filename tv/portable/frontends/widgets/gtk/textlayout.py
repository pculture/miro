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

"""textlayout.py -- Handles creating TextLayout objects to layout text.
"""

import gtk
import pango
import pangocairo

font_map = pangocairo.cairo_font_map_get_default()

class TextLayout(object):
    def __init__(self, widget):
        self.context = font_map.create_context()
        self.layout = pango.Layout(self.context)
        self.update_style(widget.style)
        self.update_direction(widget.get_direction())
        self.width = self.font_metrics = None

    def reset(self):
        self.font_desc = self.style_font_desc.copy()
        self.layout = pango.Layout(self.context)
        self.width = self.font_metrics = None

    def update_style(self, style):
        self.style_font_desc = style.font_desc
        self.font_desc = style.font_desc.copy()

    def update_direction(self, direction):
        if direction == gtk.TEXT_DIR_RTL:
            self.context.set_base_dir(pango.DIRECTION_RTL)
        else:
            self.context.set_base_dir(pango.DIRECTION_LTR)

    def update_cairo_context(self, cairo_context):
        cairo_context.update_context(self.context)

    def set_font(self, scale_factor, bold=False):
        size = int(scale_factor * self.style_font_desc.get_size())
        self.font_desc.set_size(size)
        if bold:
            self.font_desc.set_weight(pango.WEIGHT_BOLD)
        else:
            self.font_desc.set_weight(pango.WEIGHT_NORMAL)
        self.layout.set_font_description(self.font_desc)
        self.font_metrics = None

    def get_font_metrics(self):
        if self.font_metrics is None:
            self.font_metrics = self.context.get_metrics(self.font_desc)
        return self.font_metrics

    def font_ascent(self):
        return pango.PIXELS(self.get_font_metrics().get_ascent())

    def font_descent(self):
        return pango.PIXELS(self.get_font_metrics().get_descent())

    def line_height(self):
        metrics = self.get_font_metrics()
        return pango.PIXELS(metrics.get_ascent() + metrics.get_descent())

    def set_width(self, width):
        if width is not None:
            self.layout.set_width(width * pango.SCALE)
        else:
            self.layout.set_width(-1)
        self.width = width

    def set_wrap_style(self, wrap):
        if wrap == 'word':
            self.layout.set_wrap(pango.WRAP_WORD_CHAR)
        elif wrap == 'char':
            self.layout.set_wrap(pango.WRAP_CHAR)
        else:
            raise ValueError("Unknown wrap value: %s" % wrap)

    def set_text(self, text):
        self.layout.set_text(text)

    def set_alignment(self, align):
        if align == 'left':
            self.layout.set_alignment(pango.ALIGN_LEFT)
        elif align == 'right':
            self.layout.set_alignment(pango.ALIGN_RIGHT)
        elif align == 'center':
            self.layout.set_alignment(pango.ALIGN_CENTER)
        else:
            raise ValueError("Unknown align value: %s" % align)

    def line_count(self):
        return self.layout.get_line_count()

    def get_size(self):
        return self.layout.get_pixel_size()
