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

"""Utility functions."""

import math

from miro import app
from miro.frontends.widgets import imagepool
from miro.plat import resources
from miro.plat.frontends.widgets import widgetset

BLACK = (0, 0, 0)
WHITE = (1, 1, 1)

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
    pi = math.pi
    # Our basic strategy for the corners is to make a curve with the
    # control points at the corner where a non-round rectangle would be
    context.arc(x_inner2, y_inner1, edge_radius, -pi/2, 0)
    context.rel_line_to(0, inner_height)
    context.arc(x_inner2, y_inner2, edge_radius, 0, pi/2)
    context.rel_line_to(-inner_width, 0)
    context.arc(x_inner1, y_inner2, edge_radius, pi/2, pi)
    context.rel_line_to(0, -inner_height)
    context.arc(x_inner1, y_inner1, edge_radius, pi, pi*3/2)

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

def make_surface(image_name):
    path = resources.path("wimages/%s.png" % image_name)
    return imagepool.get_surface(path)

class ThreeImageSurface(object):
    """Takes a left, center and right image and draws them to an arbitrary
    width.  If the width is greater than the combined width of the 3 images,
    then the center image will be tiled to compensate.
    """

    def __init__(self, basename):
        self.left = make_surface(basename + '_left')
        self.center = make_surface(basename + '_center')
        self.right = make_surface(basename + '_right')
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
        center_width = width - right_width

        self.center.draw(context, x, y, center_width, self.height, fraction)
        self.right.draw(context, x + center_width, y, right_width, self.height, fraction)

class HideableWidget(widgetset.VBox):
    """Widget that can be hidden and shown."""

    def __init__(self, child):
        widgetset.VBox.__init__(self)
        self._child = child
        self.shown = False

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

#def middle_baseline(font, height):
#    """Calculate a baseline that will position a line of text in the middle
#    of a box height pixels tall.
#    """
#    extra = max(0, height - font.line_height())
#    return font.ascent() + (extra / 2.0)

def get_feed_info(feed_id):
    return app.tab_list_manager.feed_list.get_info(feed_id)
