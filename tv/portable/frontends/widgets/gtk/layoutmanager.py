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

"""drawing.py -- Contains the LayoutManager class.  LayoutManager is
handles laying out complex objects for the custom drawing code like text
blocks and buttons.
"""

import itertools
import math

import cairo
import gtk
import pango
import pangocairo

from miro.plat.frontends.widgets import use_native_buttons

font_map = pangocairo.cairo_font_map_get_default()

class LayoutManager(object):
    def __init__(self, widget):
        self.pango_context = font_map.create_context()
        self.update_style(widget.style)
        self.update_direction(widget.get_direction())
        widget.connect('style-set', self.on_style_set)
        widget.connect('direction-changed', self.on_direction_changed)
        self.widget = widget
        self.reset()

    def reset(self):
        self.current_font = self.font(1.0)
        self.text_color = (0, 0, 0)

    def on_style_set(self, widget, previous_style):
        self.update_style(widget.style)

    def on_direction_changed(self, widget, previous_direction):
        self.update_direction(widget.get_direction())

    def update_style(self, style):
        self.style_font_desc = style.font_desc
        self.style = style

    def update_direction(self, direction):
        if direction == gtk.TEXT_DIR_RTL:
            self.pango_context.set_base_dir(pango.DIRECTION_RTL)
        else:
            self.pango_context.set_base_dir(pango.DIRECTION_LTR)

    def font(self, scale_factor, bold=False, italic=False, family=None):
        return Font(self.pango_context, self.style_font_desc, scale_factor,
                bold, italic)

    def set_font(self, scale_factor, bold=False, italic=False, family=None):
        self.current_font = self.font(scale_factor, bold, italic)

    def set_text_color(self, color):
        self.text_color = color

    def set_text_shadow(self, shadow):
        self.shadow = shadow

    def textbox(self, text, underline=False):
        textbox = TextBox(self.pango_context, self.current_font,
                self.text_color)
        textbox.set_text(text, underline=underline)
        return textbox

    def button(self, text, pressed=False):
        if use_native_buttons:
            return NativeButton(text, self.pango_context, self.current_font, 
                    pressed, self.style, self.widget)
        else:
            return StyledButton(text, self.pango_context, self.current_font, 
                    pressed)

    def update_cairo_context(self, cairo_context):
        cairo_context.update_context(self.pango_context)

class Font(object):
    def __init__(self, context, style_font_desc, scale, bold, italic):
        self.context = context
        self.description = style_font_desc.copy()
        self.description.set_size(int(scale * style_font_desc.get_size()))
        if bold:
            self.description.set_weight(pango.WEIGHT_BOLD)
        if italic:
            self.description.set_style(pango.STYLE_ITALIC)
        self.font_metrics = None

    def get_font_metrics(self):
        if self.font_metrics is None:
            self.font_metrics = self.context.get_metrics(self.description)
        return self.font_metrics

    def ascent(self):
        return pango.PIXELS(self.get_font_metrics().get_ascent())

    def descent(self):
        return pango.PIXELS(self.get_font_metrics().get_descent())

    def line_height(self):
        metrics = self.get_font_metrics()
        return pango.PIXELS(metrics.get_ascent() + metrics.get_descent())

class TextBox(object):
    def __init__(self, context, font, color):
        self.layout = pango.Layout(context)
        self.font = font
        self.color = color
        self.layout.set_font_description(font.description.copy())
        self.width = None

    def set_text(self, text, font=None, color=None, underline=False):
        self.text_chunks = []
        self.attr_list = pango.AttrList()
        self.text_length = 0
        self.underlines = []
        self.append_text(text, font, color, underline)

    def append_text(self, text, font=None, color=None, underline=False):
        if text == None:
            text = u""
        startpos = self.text_length
        self.text_chunks.append(text)
        endpos = self.text_length = self.text_length + len(text)
        if font is not None:
            attr = pango.AttrFontDesc(font.description, startpos, endpos)
            self.attr_list.insert(attr)
        if underline:
            self.underlines.append((startpos, endpos))
        if color:
            def convert(value):
                return int(round(value * 65535))
            attr = pango.AttrForeground(convert(color[0]), convert(color[1]),
                    convert(color[2]), startpos, endpos)
            self.attr_list.insert(attr)
        self.text_set = False

    def set_width(self, width):
        if width is not None:
            self.layout.set_width(int(width * pango.SCALE))
        else:
            self.layout.set_width(-1)
        self.width = width

    def set_wrap_style(self, wrap):
        if wrap == 'word':
            self.layout.set_wrap(pango.WRAP_WORD_CHAR)
        elif wrap == 'char' or wrap == 'truncated-char':
            self.layout.set_wrap(pango.WRAP_CHAR)
        else:
            raise ValueError("Unknown wrap value: %s" % wrap)

    def set_alignment(self, align):
        if align == 'left':
            self.layout.set_alignment(pango.ALIGN_LEFT)
        elif align == 'right':
            self.layout.set_alignment(pango.ALIGN_RIGHT)
        elif align == 'center':
            self.layout.set_alignment(pango.ALIGN_CENTER)
        else:
            raise ValueError("Unknown align value: %s" % align)

    def ensure_layout(self):
        if not self.text_set:
            self.layout.set_text(''.join(self.text_chunks))
            self.layout.set_attributes(self.attr_list.copy())
            self.text_set = True

    def line_count(self):
        self.ensure_layout()
        return self.layout.get_line_count()

    def get_size(self):
        self.ensure_layout()
        return self.layout.get_pixel_size()

    def char_at(self, x, y):
        self.ensure_layout()
        x *= pango.SCALE
        y *= pango.SCALE
        width, height = self.layout.get_size()
        if 0 <= x < width and 0 <= y < height:
            index, leading = self.layout.xy_to_index(x, y)
            return index
        else:
            return None

    def draw(self, context, x, y, width, height):
        self.set_width(width)
        self.ensure_layout()
        cairo_context = context.context
        cairo_context.save()
        cairo_context.set_source_rgb(*self.color)
        underline_drawer = UnderlineDrawer(self.underlines)
        line_height = 0
        for i in xrange(self.layout.get_line_count()):
            line = self.layout.get_line(i)
            extents = line.get_pixel_extents()[1]
            next_line_height = line_height + extents[3]
            if next_line_height > height:
                break
            baseline = y + line_height + pango.ASCENT(extents)
            context.move_to(x, baseline)
            cairo_context.show_layout_line(line)
            underline_drawer.draw(context, x, baseline, line)
            line_height = next_line_height
        cairo_context.restore()
        cairo_context.new_path()

class UnderlineDrawer(object):
    """Class to draw our own underlines because cairo's don't look that great
    at small fonts.  We make sure that the underline is always drawn at a
    pixel boundary and that there always is space between the text and the
    baseline.

    This class makes a couple assumptions that might not be that great.  It
    assumes that the correct underline size is 1 pixel and that the text color
    doesn't change in the middle of an underline.
    """
    def __init__(self, underlines):
        self.underline_iter = iter(underlines)
        self.finished = False
        self.next_underline()

    def next_underline(self):
        try:
            self.startpos, self.endpos = self.underline_iter.next()
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            self.finished = True
        else:
            self.endpos -= 1 # endpos is the char to stop underlining at

    def draw(self, context, x, baseline, line):
        baseline = round(baseline) + 0.5
        context.set_line_width(1)
        while not self.finished and line.start_index <= self.startpos:
            startpos = max(line.start_index, self.startpos)
            endpos = min(self.endpos, line.start_index + line.length)
            x1 = x + pango.PIXELS(line.index_to_x(startpos, 0))
            x2 = x + pango.PIXELS(line.index_to_x(endpos, 1))
            context.move_to(x1, baseline + 1)
            context.line_to(x2, baseline + 1)
            context.stroke()
            if endpos < self.endpos:
                break
            else:
                self.next_underline()

class NativeButton(object):
    def __init__(self, text, context, font, pressed, style, widget):
        self.layout = pango.Layout(context)
        self.font = font
        self.pressed = pressed
        self.layout.set_font_description(font.description.copy())
        self.layout.set_text(text)
        self.pad_x = style.xthickness + 1
        self.pad_y = style.ythickness + 1
        self.style = style
        self.widget = widget
        # The above code assumes an "inner-border" style property of 1. PyGTK
        # doesn't seem to support Border objects very well, so can't get it
        # from the widget style.
        self.min_width = 0

    def set_min_width(self, width):
        self.min_width = width

    def get_size(self):
        text_size = self.layout.get_pixel_size()
        width = text_size[0] + self.pad_x * 2
        height = text_size[1] + self.pad_y * 2
        return max(self.min_width, width), height

    def text_area(self):
        width, height = self.layout.get_pixel_size()
        y = self.pad_y
        extra_x = max(0, int((self.min_width - width - self.pad_x * 2) / 2))
        x = self.pad_x + extra_x
        return gtk.gdk.Rectangle(x, y, width, height)

    def draw(self, context, x, y, width, height):
        x, y = context.context.user_to_device(x, y)
        # Hmm, maybe we should somehow support floating point numbers here,
        # but I don't know how to.
        x, y, width, height = (int(f) for f in (x, y, width, height))
        context.context.get_target().flush()
        self.draw_box(context.window, x, y, width, height)
        self.draw_text(context.window, x, y)

    def draw_box(self, window, x, y, width, height):
        if self.pressed:
            shadow = gtk.SHADOW_IN
            state = gtk.STATE_ACTIVE
        else:
            shadow = gtk.SHADOW_OUT
            state = gtk.STATE_NORMAL
        if 'QtCurveStyle' in str(self.style):
            # This is a horrible hack for the libqtcurve library.  See
            # http://bugzilla.pculture.org/show_bug.cgi?id=10380
            # for details
            widget = window.get_user_data()
        else:
            widget = self.widget

        self.style.paint_box(window, state, shadow, None, widget, "button", 
                int(x), int(y), int(width), int(height))

    def draw_text(self, window, x, y):
        offset_x, offset_y, _, _ = self.text_area()
        if self.pressed:
            state = gtk.STATE_ACTIVE
        else:
            state = gtk.STATE_NORMAL
        self.style.paint_layout(window, state, True, None, None, None, 
                x + offset_x, y + offset_y, self.layout)

class StyledButton(object):
    PAD_HORIZONTAL = 4
    PAD_VERTICAL = 2
    TOP_COLOR = (1, 1, 1)
    BOTTOM_COLOR = (0.86, 0.86, 0.86)
    LINE_COLOR = (0.69, 0.69, 0.69)
    TEXT_COLOR = (0, 0, 0)

    def __init__(self, text, context, font, pressed):
        self.layout = pango.Layout(context)
        self.font = font
        self.layout.set_font_description(font.description.copy())
        self.layout.set_text(text)
        self.min_width = 0
        self.pressed = pressed

    def set_min_width(self, width):
        self.min_width = width

    def get_size(self):
        width, height = self.layout.get_pixel_size()
        height += self.PAD_VERTICAL * 2
        if height % 2 == 1:
            # make height even so that the radius of our circle is whole
            height += 1 
        width += self.PAD_HORIZONTAL * 2 + height
        return max(self.min_width, width), height

    def text_area(self):
        width, height = self.layout.get_pixel_size()
        y = self.pad_y
        extra_x = max(0, int((self.min_width - width - self.pad_x * 2) / 2))
        x = self.pad_x + extra_x
        return gtk.gdk.Rectangle(x, y, width, height)


    def draw_path(self, context, x, y, width, height, radius):
        inner_width = width - radius * 2
        context.move_to(x + radius, y)
        context.rel_line_to(inner_width, 0)
        context.arc(x + width - radius, y+radius, radius, -math.pi/2, math.pi/2)
        context.rel_line_to(-inner_width, 0)
        context.arc(x + radius, y+radius, radius, math.pi/2, -math.pi/2)

    def draw_button(self, context, x, y, width, height, radius):
        context.context.save()
        self.draw_path(context, x, y, width, height, radius)
        if self.pressed:
            end_color = self.TOP_COLOR
            start_color = self.BOTTOM_COLOR
        else:
            context.set_line_width(1)
            start_color = self.TOP_COLOR
            end_color = self.BOTTOM_COLOR
        gradient = cairo.LinearGradient(x, y, x, y + height)
        gradient.add_color_stop_rgb(0, *start_color)
        gradient.add_color_stop_rgb(1, *end_color)
        context.context.set_source(gradient)
        context.fill()
        context.set_line_width(1)
        self.draw_path(context, x+0.5, y+0.5, width, height, radius)
        context.set_source_rgb(*self.LINE_COLOR)
        context.stroke()
        context.context.restore()

    def draw(self, context, x, y, width, height):
        radius = height / 2
        self.draw_button(context, x, y, width, height, radius)
        self.draw_text(context, x, y, width, height, radius)

    def draw_text(self, context, x, y, width, height, radius):
        context.set_color(self.TEXT_COLOR)
        text_width, text_height = self.layout.get_pixel_size()
        # draw the text in the center of the button
        x += (width - text_width) / 2
        y += (height - text_height) / 2
        context.move_to(x, y)
        context.context.show_layout(self.layout)
