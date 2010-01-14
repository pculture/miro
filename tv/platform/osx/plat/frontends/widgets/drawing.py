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

"""miro.plat.frontend.widgets.drawing -- Draw on Views."""

import math

from Foundation import *
from AppKit import *
from Quartz import *
from objc import YES, NO, nil

from miro.plat import utils
from miro.plat import shading

class ImageSurface:
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, image):
        """Create a new ImageSurface."""
        self.image = image.nsimage.copy()
        self.image.setFlipped_(YES)
        self.image.setCacheMode_(NSImageCacheNever)
        self.width = image.width
        self.height = image.height

    def get_size(self):
        return self.width, self.height

    def draw(self, context, x, y, width, height, fraction=1.0):
        if self.width == 0 or self.height == 0:
            return
        NSGraphicsContext.currentContext().setShouldAntialias_(YES)
        NSGraphicsContext.currentContext().setImageInterpolation_(NSImageInterpolationHigh)
        dest_rect = NSRect((x, y), (width, height))
        if self.width <= width and self.height <= height:
            self.image.drawInRect_fromRect_operation_fraction_(dest_rect, NSZeroRect, NSCompositeSourceOver, fraction)
        else:
            NSColor.colorWithPatternImage_(self.image).set()
            NSRectFill(dest_rect)
        context.path.removeAllPoints()

def convert_cocoa_color(color):
    rgb = color.colorUsingColorSpaceName_(NSDeviceRGBColorSpace)
    return (rgb.redComponent(), rgb.greenComponent(), rgb.blueComponent())

class DrawingStyle(object):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, bg_color=None, text_color=None):
        self.use_custom_style = True
        self.use_custom_titlebar_background = True
        if text_color is None:
            self.text_color = self.default_text_color
        else:
            self.text_color = convert_cocoa_color(text_color)
        if bg_color is None:
            self.bg_color = self.default_bg_color
        else:
            self.bg_color = convert_cocoa_color(bg_color)

    default_text_color = convert_cocoa_color(NSColor.textColor())
    default_bg_color = convert_cocoa_color(NSColor.textBackgroundColor())

class DrawingContext:
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, view, drawing_area, rect):
        self.view = view
        self.path = NSBezierPath.bezierPath()
        self.color = NSColor.blackColor()
        self.width = drawing_area.size.width
        self.height = drawing_area.size.height
        if drawing_area.origin != NSZeroPoint:
            xform = NSAffineTransform.transform()
            xform.translateXBy_yBy_(drawing_area.origin.x, 
                    drawing_area.origin.y)
            xform.concat()

    def move_to(self, x, y):
        self.path.moveToPoint_(NSPoint(x, y))

    def rel_move_to(self, dx, dy):
        self.path.relativeMoveToPoint_(NSPoint(dx, dy))

    def line_to(self, x, y):
        self.path.lineToPoint_(NSPoint(x, y))

    def rel_line_to(self, dx, dy):
        self.path.relativeLineToPoint_(NSPoint(dx, dy))

    def curve_to(self, x1, y1, x2, y2, x3, y3):
        self.path.curveToPoint_controlPoint1_controlPoint2_(
                NSPoint(x3, y3), NSPoint(x1, y1), NSPoint(x2, y2))

    def rel_curve_to(self, dx1, dy1, dx2, dy2, dx3, dy3):
        self.path.relativeCurveToPoint_controlPoint1_controlPoint2_(
                NSPoint(dx3, dy3), NSPoint(dx1, dy1), NSPoint(dx2, dy2))

    def arc(self, x, y, radius, angle1, angle2):
        angle1 = (angle1 * 360) / (2 * math.pi)
        angle2 = (angle2 * 360) / (2 * math.pi)
        center = NSPoint(x, y)
        self.path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(center, radius, angle1, angle2)

    def arc_negative(self, x, y, radius, angle1, angle2):
        angle1 = (angle1 * 360) / (2 * math.pi)
        angle2 = (angle2 * 360) / (2 * math.pi)
        center = NSPoint(x, y)
        self.path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(center, radius, angle1, angle2, YES)

    def rectangle(self, x, y, width, height):
        rect = NSMakeRect(x, y, width, height)
        self.path.appendBezierPathWithRect_(rect)

    def set_color(self, (red, green, blue), alpha=1.0):
        self.color = NSColor.colorWithDeviceRed_green_blue_alpha_(red, green,
                blue, alpha)
        self.color.set()
        
    def set_shadow(self, color, opacity, offset, blur_radius):
        shadow = NSShadow.alloc().init()
        shadow.setShadowOffset_(offset)
        shadow.setShadowBlurRadius_(blur_radius)
        shadow.setShadowColor_(NSColor.colorWithDeviceRed_green_blue_alpha_(color[0], color[1], color[2], opacity))
        shadow.set()

    def set_line_width(self, width):
        self.path.setLineWidth_(width)

    def stroke(self):
        self.path.stroke()
        self.path.removeAllPoints()

    def stroke_preserve(self):
        self.path.stroke()

    def fill(self):
        self.path.fill()
        self.path.removeAllPoints()

    def fill_preserve(self):
        self.path.fill()

    def clip(self):
        self.path.addClip()
        self.path.removeAllPoints()

    def save(self):
        NSGraphicsContext.currentContext().saveGraphicsState()

    def restore(self):
        NSGraphicsContext.currentContext().restoreGraphicsState()

    def gradient_fill(self, gradient):
        self.gradient_fill_preserve(gradient)
        self.path.removeAllPoints()

    def gradient_fill_preserve(self, gradient):
        context = NSGraphicsContext.currentContext()
        context.saveGraphicsState()
        self.path.addClip()
        shading.draw_axial(gradient)
        context.restoreGraphicsState()

class Gradient(object):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, x1, y1, x2, y2):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.start_color = None
        self.end_color = None

    def set_start_color(self, (red, green, blue)):
        self.start_color = (red, green, blue)

    def set_end_color(self, (red, green, blue)):
        self.end_color = (red, green, blue)

class DrawingMixin(object):
    def calc_size_request(self):
        return self.size_request(self.view.layout_manager)

    # squish width / squish height only make sense on GTK
    def set_squish_width(self, setting):
        pass

    def set_squish_height(self, setting):
        pass

    # Default implementations for methods that subclasses override.

    def is_opaque(self):
        return False

    def size_request(self, layout_manager):
        return 0, 0

    def draw(self, context, layout_manager):
        pass

