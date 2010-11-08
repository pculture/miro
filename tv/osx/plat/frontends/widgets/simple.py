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

import math

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

from miro.plat.utils import filename_to_unicode
from miro.frontends.widgets import widgetconst
from miro.plat.frontends.widgets.base import Widget, SimpleBin, FlippedView

"""A collection of various simple widgets."""

class Image(object):
    """See https://develop.participatoryculture.org/index.php/WidgetAPI for a description of the API for this class."""
    def __init__(self, path):
        self.nsimage = NSImage.alloc().initByReferencingFile_(filename_to_unicode(path))
        self.width = self.nsimage.size().width
        self.height = self.nsimage.size().height

    def resize(self, width, height):
        return ResizedImage(self, width, height)

class ResizedImage(Image):
    def __init__(self, image, width, height):
        self.nsimage = image.nsimage.copy()
        self.nsimage.setCacheMode_(NSImageCacheNever)
        self.nsimage.setScalesWhenResized_(YES)
        self.nsimage.setSize_(NSSize(width, height))
        self.width = width
        self.height = height

class NSImageDisplay (NSView):
    def initWithImage_(self, image):
        self = super(NSImageDisplay, self).init()
        self.image = image
        return self
    def drawRect_(self, rect):
        NSGraphicsContext.currentContext().setShouldAntialias_(YES)
        NSGraphicsContext.currentContext().setImageInterpolation_(NSImageInterpolationHigh)
        self.image.nsimage.drawInRect_fromRect_operation_fraction_(rect, NSZeroRect, NSCompositeSourceOver, 1.0)

class ImageDisplay(Widget):
    """See https://develop.participatoryculture.org/index.php/WidgetAPI for a description of the API for this class."""
    def __init__(self, image):
        Widget.__init__(self)
        self.image = image
        self.image.nsimage.setCacheMode_(NSImageCacheNever)
        self.view = NSImageDisplay.alloc().initWithImage_(self.image)

    def calc_size_request(self):
        return self.image.width, self.image.height

class AnimatedImageDisplay(Widget):
    def __init__(self, path):
        Widget.__init__(self)
        self.nsimage = NSImage.alloc().initByReferencingFile_(filename_to_unicode(path))
        self.view = NSImageView.alloc().init()
        self.view.setImage_(self.nsimage)

    def calc_size_request(self):
        return self.nsimage.size().width, self.nsimage.size().height

class Label(Widget):
    """See https://develop.participatoryculture.org/index.php/WidgetAPI for a description of the API for this class."""
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
        self.__color = self.view.textColor()

    def set_bold(self, bold):
        self.bold = bold
        self.set_font()

    def set_size(self, size):
        if size > 0:
            self.size = NSFont.systemFontSize() * size
        elif size == widgetconst.SIZE_SMALL:
            self.size = NSFont.smallSystemFontSize()
        elif size == widgetconst.SIZE_NORMAL:
            self.size = NSFont.systemFontSize()
        else:
            raise ValueError("Unknown size constant: %s" % size)

        self.set_font()

    def set_color(self, color):
        self.__color = self.make_color(color)

        if self.view.isEnabled():
            self.view.setTextColor_(self.__color)
        else:
            self.view.setTextColor_(self.__color.colorWithAlphaComponent_(0.5))

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
        return math.ceil(size.width), math.ceil(size.height)

    def baseline(self):
        return -self.view.font().descender()

    def set_text(self, text):
        self.view.setStringValue_(text)
        self.sizer_cell.setStringValue_(text)
        self.invalidate_size_request()

    def get_text(self):
        self.view.stringValue()

    def set_wrap(self, wrap):
        self.wrap = True
        self.invalidate_size_request()

    def enable(self):
        Widget.enable(self)
        self.view.setTextColor_(self.__color)
        self.view.setEnabled_(True)

    def disable(self):
        Widget.disable(self)
        self.view.setTextColor_(self.__color.colorWithAlphaComponent_(0.5))
        self.view.setEnabled_(False)

class SolidBackground(SimpleBin):
    def __init__(self,  color=None):
        SimpleBin.__init__(self)
        self.view = FlippedView.alloc().init()
        if color is not None:
            self.set_background_color(color)

    def set_background_color(self, color):
        self.view.setBackgroundColor_(self.make_color(color))

class ProgressBar(Widget):
    def __init__(self):
        Widget.__init__(self)
        self.view = NSProgressIndicator.alloc().init()
        self.view.setMaxValue_(1.0)
        self.view.setIndeterminate_(False)

    def calc_size_request(self):
        return 20, 20

    def set_progress(self, fraction):
        self.view.setIndeterminate_(False)
        self.view.setDoubleValue_(fraction)

    def start_pulsing(self):
        self.view.setIndeterminate_(True)
        self.view.startAnimation_(nil)

    def stop_pulsing(self):
        self.view.stopAnimation_(nil)
