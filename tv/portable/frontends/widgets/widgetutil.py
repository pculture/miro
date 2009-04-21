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

"""Utility functions."""

import math

from miro import app
from miro.frontends.widgets import imagepool
from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

BLACK = (0, 0, 0)
WHITE = (1, 1, 1)

PI = math.pi

def round_rect(context, x, y, width, height, edge_radius):
    edge_radius = min(edge_radius, min(width, height)/2.0)
    inner_width = width - edge_radius*2
    inner_height = height - edge_radius*2
    x_inner1 = x + edge_radius
    x_inner2 = x + width - edge_radius
    y_inner1 = y + edge_radius
    y_inner2 = y + height - edge_radius

    context.move_to(x+edge_radius, y)
    context.rel_line_to(inner_width, 0)

    context.arc(x_inner2, y_inner1, edge_radius, -PI/2, 0)
    context.rel_line_to(0, inner_height)
    context.arc(x_inner2, y_inner2, edge_radius, 0, PI/2)
    context.rel_line_to(-inner_width, 0)
    context.arc(x_inner1, y_inner2, edge_radius, PI/2, PI)
    context.rel_line_to(0, -inner_height)
    context.arc(x_inner1, y_inner1, edge_radius, PI, PI*3/2)

def round_rect_reverse(context, x, y, width, height, edge_radius):
    edge_radius = min(edge_radius, min(width, height)/2.0)
    inner_width = width - edge_radius*2
    inner_height = height - edge_radius*2
    x_inner1 = x + edge_radius
    x_inner2 = x + width - edge_radius
    y_inner1 = y + edge_radius
    y_inner2 = y + height - edge_radius

    context.move_to(x+edge_radius, y)
    context.arc_negative(x_inner1, y_inner1, edge_radius, PI*3/2, PI)
    context.rel_line_to(0, inner_height)
    context.arc_negative(x_inner1, y_inner2, edge_radius, PI, PI/2)
    context.rel_line_to(inner_width, 0)
    context.arc_negative(x_inner2, y_inner2, edge_radius, PI/2, 0)
    context.rel_line_to(0, -inner_height)
    context.arc_negative(x_inner2, y_inner1, edge_radius, 0, -PI/2)
    context.rel_line_to(-inner_width, 0)

def circular_rect(context, x, y, width, height):
    """Make a path for a rectangle with the left/right side being circles."""

    radius = height / 2.0
    inner_width = width - height
    inner_y = y + radius
    inner_x1 = x + radius
    inner_x2 = inner_x1 + inner_width

    context.move_to(inner_x1, y)
    context.rel_line_to(inner_width, 0)
    context.arc(inner_x2, inner_y, radius, -PI/2, PI/2)
    context.rel_line_to(-inner_width, 0)
    context.arc(inner_x1, inner_y, radius, PI/2, -PI/2)

def circular_rect_negative(context, x, y, width, height):
    """The same path as circular_rect(), but going counter clockwise.  """

    radius = height / 2.0
    inner_width = width - height
    inner_y = y + radius
    inner_x1 = x + radius
    inner_x2 = inner_x1 + inner_width

    context.move_to(inner_x1, y)
    context.arc_negative(inner_x1, inner_y, radius, -PI/2, PI/2)
    context.rel_line_to(inner_width, 0)
    context.arc_negative(inner_x2, inner_y, radius, PI/2, -PI/2)
    context.rel_line_to(-inner_width, 0)

def draw_rounded_icon(context, icon, x, y, width, height, inset=0):
    """Draw an icon with the corners rounded.
    
    x, y, width, height define where the box is.

    inset creates a margin between where the images is drawn and (x, y, width,
    height)
    """
    context.save()
    round_rect(context, x + inset, y + inset, width - inset*2, 
            height - inset*2, 3)
    context.clip()
    if icon.width != width or icon.height != height:
        context.set_color((0, 0, 0))
        round_rect(context, x, y, width, height, 3)
        context.fill()
        icon_x = int((width - icon.width) / 2)
        icon_y = int((height - icon.height) / 2)
    else:
        icon_x = icon_y = 0
    icon.draw(context, x + icon_x, y + icon_y, icon.width, icon.height)
    context.restore()

def align(widget, xalign=0, yalign=0, xscale=0, yscale=0, 
        top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
    """Create an alignment, then add widget to it and return the alignment."""
    alignment = widgetset.Alignment(xalign, yalign, xscale, yscale)
    alignment.set_padding(top_pad, bottom_pad, left_pad, right_pad)
    alignment.add(widget)
    return alignment

def align_center(widget, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
    """Wrap a widget in an Alignment that will center it horizontally."""
    return align(widget, 0.5, 0, 0, 1,
            top_pad, bottom_pad, left_pad, right_pad)

def align_right(widget, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
    """Wrap a widget in an Alignment that will align it left."""
    return align(widget, 1, 0, 0, 1, top_pad, bottom_pad, left_pad, right_pad)

def align_left(widget, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
    """Wrap a widget in an Alignment that will align it right."""
    return align(widget, 0, 0, 0, 1, top_pad, bottom_pad, left_pad, right_pad)

def align_middle(widget, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
    """Wrap a widget in an Alignment that will center it vertically."""
    return align(widget, 0, 0.5, 1, 0,
            top_pad, bottom_pad, left_pad, right_pad)

def align_top(widget, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
    """Wrap a widget in an Alignment that will align to the top."""
    return align(widget, 0, 0, 1, 0, top_pad, bottom_pad, left_pad, right_pad)

def align_bottom(widget, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
    """Wrap a widget in an Alignment that will align to the bottom."""
    return align(widget, 0, 1, 1, 0, top_pad, bottom_pad, left_pad, right_pad)

def pad(widget, top=0, bottom=0, left=0, right=0):
    """Wrap a widget in an Alignment that will pad it."""
    alignment = widgetset.Alignment(xscale=1, yscale=1)
    alignment.set_padding(top, bottom, left, right)
    alignment.add(widget)
    return alignment

def build_hbox(items, padding=5):
    """Builds an HBox and packs with the list of widgets.  Padding defaults to
    5 pixels.
    """
    h = widgetset.HBox()
    [h.pack_start(item, padding=padding) for item in items]
    return h

def build_control_line(items, padding=5):
    max_baseline = -1
    for item in items:
        max_baseline = max(max_baseline, item.baseline())
    padded_items = []
    for item in items:
        if item.baseline() == max_baseline:
            padded_items.append(item)
        else:
            pad = int(round(max_baseline - item.baseline()))
            padded_items.append(align_bottom(item, bottom_pad=pad))
    return build_hbox(padded_items, padding)

def make_surface(image_name):
    path = resources.path("images/%s.png" % image_name)
    return imagepool.get_surface(path)

class ThreeImageSurface(object):
    """Takes a left, center and right image and draws them to an arbitrary
    width.  If the width is greater than the combined width of the 3 images,
    then the center image will be tiled to compensate.
    """

    def __init__(self, basename=None):
        self.left = self.center = self.right = None
        self.height = 0
        if basename is not None:
            left = make_surface(basename + '_left')
            center = make_surface(basename + '_center')
            right = make_surface(basename + '_right')
            self.set_images(left, center, right)

    def set_images(self, left, center, right):
        self.left = left
        self.center = center
        self.right = right
        if not (self.left.height == self.center.height == self.right.height):
            raise ValueError("Images aren't the same height")
        self.height = self.left.height

    def draw(self, context, x, y, width, fraction=1.0):
        left_width = min(self.left.width, width)
        self.left.draw(context, x, y, left_width, self.height, fraction)
        self.draw_right(context, x + left_width, y, width - left_width, fraction)

    def draw_right(self, context, x, y, width, fraction=1.0):
        """Draw only the right 2 images."""

        right_width = min(self.right.width, width)
        center_width = int(width - right_width)

        self.center.draw(context, x, y, center_width, self.height, fraction)
        self.right.draw(context, x + center_width, y, right_width, self.height, fraction)

class HideableWidget(widgetset.VBox):
    """Widget that can be hidden and shown."""

    def __init__(self, child):
        widgetset.VBox.__init__(self)
        self._child = child
        self.shown = False

    def child(self):
        return self._child

    def show(self):
        if not self.shown:
            self.pack_start(self._child)
            self.shown = True

    def hide(self):
        if self.shown:
            self.remove(self._child)
            self.shown = False

class Shadow(object):
    """Encapsulates all parameters required to draw shadows"""
    def __init__(self, color, opacity, offset, blur_radius):
        self.color = color
        self.opacity = opacity
        self.offset = offset
        self.blur_radius = blur_radius

def get_feed_info(feed_id):
    tablist = app.tab_list_manager.which_tablist_has_id(feed_id)
    return tablist.get_info(feed_id)

def feed_exists(feed_id):
    try:
        get_feed_info(feed_id)
        return True
    except (ValueError, KeyError):
        pass
    return False
