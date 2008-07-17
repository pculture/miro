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

"""miro.plat.frontend.widgets.drawing -- Draw on Views."""

import math

from Foundation import *
from AppKit import *
from Quartz import *
from objc import YES, NO, nil

from miro.plat import utils
from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets.base import Widget, SimpleBin, FlippedView
from miro.plat.frontends.widgets.layoutmanager import LayoutManager
from miro.plat.frontends.widgets.rect import NSRectWrapper

class ImageSurface:
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, image):
        """Create a new ImageSurface."""
        self.image = image.nsimage.copy()
        self.image.setFlipped_(YES)
        self.width = image.width
        self.height = image.height

    def draw(self, context, x, y, width, height):
        endy = y + height
        while y < endy:
            current_height = min(self.height, endy - y)
            self._draw_line(x, y, width, current_height)
            y += height
        context.path.removeAllPoints()

    def get_size(self):
        return self.width, self.height

    def _draw_line(self, x, y, width, height):
        endx = x + width
        while x < endx:
            at = NSPoint(x+0.5, y+0.5)
            current_width = min(self.width, endx - x)
            dest_rect = NSRect(at, NSSize(current_width, height))
            source_rect = NSMakeRect(0, 0, current_width, height)
            self.image.drawInRect_fromRect_operation_fraction_(dest_rect,
                source_rect, NSCompositeSourceOver, 1.0)
            x += current_width

class DrawingStyle(object):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, bg_color=None, text_color=None):
        self.use_custom_style = True
        self.use_custom_titlebar_background = True
        if text_color is None:
            text_color = NSColor.textColor()
        if bg_color is None:
            bg_color = NSColor.textBackgroundColor()
        self.text_color = self.convert_cocoa_color(text_color)
        self.bg_color = self.convert_cocoa_color(bg_color)

    def convert_cocoa_color(self, color):
        rgb = color.colorUsingColorSpaceName_(NSDeviceRGBColorSpace)
        return (rgb.redComponent(), rgb.greenComponent(), rgb.blueComponent())

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
        self.path.moveToPoint_(NSPoint(x+0.5, y+0.5))

    def rel_move_to(self, dx, dy):
        self.path.relativeMoveToPoint_(NSPoint(dx, dy))

    def line_to(self, x, y):
        self.path.lineToPoint_(NSPoint(x+0.5, y+0.5))

    def rel_line_to(self, dx, dy):
        self.path.relativeLineToPoint_(NSPoint(dx, dy))

    def curve_to(self, x1, y1, x2, y2, x3, y3):
        self.path.curveToPoint_controlPoint1_controlPoint2_(
                NSPoint(x3+0.5, y3+0.5), NSPoint(x1+0.5, y1+0.5), NSPoint(x2+0.5, y2+0.5))

    def rel_curve_to(self, dx1, dy1, dx2, dy2, dx3, dy3):
        self.path.relativeCurveToPoint_controlPoint1_controlPoint2_(
                NSPoint(dx3, dy3), NSPoint(dx1, dy1), NSPoint(dx2, dy2))

    def arc(self, x, y, radius, angle1, angle2):
        angle1 = (angle1 * 360) / (2 * math.pi)
        angle2 = (angle2 * 360) / (2 * math.pi)
        center = NSPoint(x+0.5, y+0.5)
        self.path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(center, radius, angle1, angle2)

    def arc_negative(self, x, y, radius, angle1, angle2):
        angle1 = (angle1 * 360) / (2 * math.pi)
        angle2 = (angle2 * 360) / (2 * math.pi)
        center = NSPoint(x+0.5, y+0.5)
        self.path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(center, radius, angle1, angle2, YES)

    def rectangle(self, x, y, width, height):
        rect = NSMakeRect(x+0.5, y+0.5, width, height)
        self.path.appendBezierPathWithRect_(rect)

    def set_color(self, (red, green, blue), alpha=1.0):
        self.color = NSColor.colorWithDeviceRed_green_blue_alpha_(red, green,
                blue, alpha)
        self.color.set()

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
        gradient.set_input_points(self)
        NSGraphicsContext.currentContext().saveGraphicsState()
        path_rect = self.path.bounds()
        self.path.addClip()
        context = NSGraphicsContext.currentContext().CIContext()
        context.drawImage_atPoint_fromRect_(gradient.get_image(),
                path_rect.origin, 
                gradient.rect_for_flipped_rect(path_rect))
        NSGraphicsContext.currentContext().restoreGraphicsState()


class Gradient(object):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, x1, y1, x2, y2):
        self.filter = CIFilter.filterWithName_('CILinearGradient')
        # Make y negative because we want  things to work in flipped
        # coordinates
        if utils.getMajorOSVersion() < 9:
            self.filter.setValue_forKey_(self.ci_point(x1, -y1), 'inputPoint0')
            self.filter.setValue_forKey_(self.ci_point(x2, -y2), 'inputPoint1')
        else:
            self.filter.setValue_forKey_(self.ci_point(x1, -y1), 'inputPoint1')
            self.filter.setValue_forKey_(self.ci_point(x2, -y2), 'inputPoint0')

    def rect_for_flipped_rect(self, rect):
        origin = NSPoint(rect.origin.x, -rect.origin.y-rect.size.height)
        return NSRect(origin, rect.size)

    def set_input_points(self, drawing_context):
        return
        # Adjust for the fact the coordinate systems are flipped
        y1 = drawing_context.height - self.y1
        y2 = drawing_context.height - self.y2
        if utils.getMajorOSVersion() < 9:
            self.filter.setValue_forKey_(self.ci_point(self.x1, y1), 'inputPoint0')
            self.filter.setValue_forKey_(self.ci_point(self.x2, y2), 'inputPoint1')
        else:
            self.filter.setValue_forKey_(self.ci_point(self.x1, y1), 'inputPoint1')
            self.filter.setValue_forKey_(self.ci_point(self.x2, y2), 'inputPoint0')

    def set_start_color(self, (red, green, blue)):
        self.filter.setValue_forKey_(self.ci_color(red, green, blue), 
                'inputColor0')

    def set_end_color(self, (red, green, blue)):
        self.filter.setValue_forKey_(self.ci_color(red, green, blue),
                'inputColor1')

    def ci_point(self, x, y):
        return CIVector.vectorWithX_Y_(x, y)

    def ci_color(self, red, green, blue):
        return CIColor.colorWithRed_green_blue_(red, green, blue)

    def get_image(self):
        return self.filter.valueForKey_('outputImage')

class DrawingView(FlippedView):
    def init(self):
        FlippedView.init(self)
        self.layout_manager = LayoutManager()
        return self

    def isOpaque(self):
        return wrappermap.wrapper(self).is_opaque()

    def drawRect_(self, rect):
        context = DrawingContext(self, self.bounds(), rect)
        context.style = DrawingStyle()
        wrappermap.wrapper(self).draw(context, self.layout_manager)

class DrawingMixin(object):
    def calc_size_request(self):
        return self.size_request(self.view.layout_manager)

    # Default implementations for methods that subclasses override.

    def is_opaque(self):
        return False

    def size_request(self, layout_manager):
        return 0, 0

    def draw(self, context, layout_manager):
        pass

class DrawingArea(DrawingMixin, Widget):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        Widget.__init__(self)
        self.view = DrawingView.alloc().init()

class Background(DrawingMixin, SimpleBin):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        SimpleBin.__init__(self)
        self.view = DrawingView.alloc().init()

    def calc_size_request(self):
        drawing_size = DrawingMixin.calc_size_request(self)
        container_size = SimpleBin.calc_size_request(self)
        return (max(container_size[0], drawing_size[0]), 
                max(container_size[1], drawing_size[1]))
