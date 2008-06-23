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

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

from miro.plat.frontends.widgets.base import Widget, SimpleBin, FlippedView

"""A collection of various simple widgets."""

class Image(object):
    def __init__(self, path):
        self.path = path
        self.nsimage = NSImage.alloc().initByReferencingFile_(path)
        self.width = self.nsimage.size().width
        self.height = self.nsimage.size().height

class ImageDisplay(Widget):
    def __init__(self, image):
        Widget.__init__(self)
        self.image = image
        self.view = NSImageView.alloc().init()
        self.view.setImage_(self.image.nsimage)

    def calc_size_request(self):
        return self.image.width, self.image.height

class Label(Widget):
    def __init__(self, text="", wrap=False):
        Widget.__init__(self)
        self.view = NSTextField.alloc().init()
        self.view.setEditable_(NO)
        self.view.setBezeled_(NO)
        self.view.setBordered_(NO)
        self.view.setDrawsBackground_(NO)
        self.wrap = wrap
        self.bold = False
        self.size = NSFont.systemFontSize()
        self.sizer_cell = self.view.cell().copy()
        self.set_font()
        self.set_text(text)

    def set_bold(self, bold):
        self.bold = bold
        self.set_font()

    def set_size(self, ratio):
        self.size = NSFont.systemFontSize() * ratio
        self.set_font()

    def set_color(self, color):
        self.view.setTextColor_(self.make_color(color))

    def set_background_color(self, color):
        self.view.setBackgroundColor_(self.make_color(color))
        self.view.setDrawsBackground_(YES)

    def set_font(self):
        if self.bold:
            font = NSFont.boldSystemFontOfSize_(self.size)
        else:
            font= NSFont.systemFontOfSize_(self.size)
        self.view.setFont_(font)
        self.sizer_cell.setFont_(font)
        self.invalidate_size_request()

    def calc_size_request(self):
        if (self.wrap and self.manual_size_request is not None and 
                self.manual_size_request[0] > 0):
            wrap_width = self.manual_size_request[0]
            size = self.sizer_cell.cellSizeForBounds_(NSMakeRect(0, 0,
                wrap_width, 10000))
        else:
            size = self.sizer_cell.cellSize()
        return size.width, size.height

    def set_text(self, text):
        self.view.setStringValue_(text)
        self.sizer_cell.setStringValue_(text)

    def get_text(self):
        self.view.stringValue()

    def set_wrap(self, wrap):
        self.wrap = True
        self.invalidate_size_request()

class SolidBackground(SimpleBin):
    def __init__(self,  color=None):
        SimpleBin.__init__(self)
        self.view = FlippedView.alloc().init()
        if color is not None:
            self.set_background_color(color)

    def set_background_color(self, color):
        self.view.setBackgroundColor_(self.make_color(color))

class SeparatorView(FlippedView):
    def initWithHorizontal_(self, horizontal):
        self = FlippedView.init(self)
        self.horizontal = horizontal
        self.color1 = NSColor.colorWithDeviceRed_green_blue_alpha_(0.85, 0.85,
                0.85, 1.0)
        self.color2 = NSColor.colorWithDeviceRed_green_blue_alpha_(0.95, 0.95,
                0.95, 1.0)
        return self

    def isOpaque(self):
        return True

    def drawRect_(self, rect):
        size = self.bounds().size
        path = NSBezierPath.bezierPath()
        path.setLineWidth_(1)
        if self.horizontal:
            path.moveToPoint_(NSPoint(0, 0.5))
            path.lineToPoint_(NSPoint(size.width, 0.5))
        else:
            path.moveToPoint_(NSPoint(0.5, 0))
            path.lineToPoint_(NSPoint(0.5, size.height))
        self.color1.set()
        path.stroke()
        path.removeAllPoints()
        if self.horizontal:
            path.moveToPoint_(NSPoint(0, 1.5))
            path.lineToPoint_(NSPoint(size.width, 1.5))
        else:
            path.moveToPoint_(NSPoint(1.5, 0))
            path.lineToPoint_(NSPoint(1.5, size.height))
        self.color2.set()
        path.stroke()

class HSeparator(Widget):
    def __init__(self):
        Widget.__init__(self)
        self.view = SeparatorView.alloc().initWithHorizontal_(True)

    def calc_size_request(self):
        return (0, 2)

class VSeparator(Widget):
    #CREATES_VIEW = False
    def __init__(self):
        Widget.__init__(self)
        self.view = SeparatorView.alloc().initWithHorizontal_(False)

    def calc_size_request(self):
        return (2, 0)
