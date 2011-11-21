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

from __future__ import division
import logging
import math

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

from miro.plat.utils import filename_to_unicode
from miro.frontends.widgets import widgetconst
from miro.plat.frontends.widgets.base import Widget, SimpleBin, FlippedView
from miro.plat.frontends.widgets import drawing
from miro.plat.frontends.widgets import wrappermap

"""A collection of various simple widgets."""

class Image(object):
    """See https://develop.participatoryculture.org/index.php/WidgetAPI for a description of the API for this class."""
    def __init__(self, path):
        self._set_image(NSImage.alloc().initByReferencingFile_(
            filename_to_unicode(path)))

    def _set_image(self, nsimage):
        self.nsimage = nsimage
        self.width = self.nsimage.size().width
        self.height = self.nsimage.size().height
        if self.width * self.height == 0:
            raise ValueError('Image has invalid size: (%d, %d)' % (
                    self.width, self.height))
        self.nsimage.setFlipped_(YES)

    def resize(self, width, height):
        return ResizedImage(self, width, height)

    def crop_and_scale(self, src_x, src_y, src_width, src_height, dest_width,
            dest_height):
        if dest_width <= 0 or dest_height <= 0:
            logging.stacktrace("invalid dest sizes: %s %s" % (dest_width,
                    dest_height))
            return TransformedImage(self.nsimage)

        source_rect = NSMakeRect(src_x, src_y, src_width, src_height)
        dest_rect = NSMakeRect(0, 0, dest_width, dest_height)

        dest = NSImage.alloc().initWithSize_(NSSize(dest_width, dest_height))
        dest.lockFocus()
        try:
            NSGraphicsContext.currentContext().setImageInterpolation_(
                    NSImageInterpolationHigh)
            self.nsimage.drawInRect_fromRect_operation_fraction_(dest_rect,
                    source_rect, NSCompositeCopy, 1.0)
        finally:
            dest.unlockFocus()
        return TransformedImage(dest)
    
    def resize_for_space(self, width, height):
        """Returns an image scaled to fit into the specified space at the
        correct height/width ratio.
        """
        # this prevents division by 0.
        if self.width == 0 and self.height == 0:
            return self
        elif self.width == 0:
            ratio = height / self.height
            return self.resize(self.width, ratio * self.height)
        elif self.height == 0:
            ratio = width / self.width
            return self.resize(ratio * self.width, self.height)

        ratio = min(width / self.width, height / self.height)
        return self.resize(ratio * self.width, ratio * self.height)

class ResizedImage(Image):
    def __init__(self, image, width, height):
        nsimage = image.nsimage.copy()
        nsimage.setCacheMode_(NSImageCacheNever)
        nsimage.setScalesWhenResized_(YES)
        nsimage.setSize_(NSSize(width, height))
        self._set_image(nsimage)

class TransformedImage(Image):
    def __init__(self, nsimage):
        self._set_image(nsimage)

class NSImageDisplay(NSView):
    def init(self):
        self = super(NSImageDisplay, self).init()
        self.border = False
        self.image = None
        return self

    def isFlipped(self):
        return YES

    def set_border(self, border):
        self.border = border

    def set_image(self, image):
        self.image = image

    def drawRect_(self, dest_rect):
        if self.image is not None:
            source_rect = self.calculateSourceRectFromDestRect_(dest_rect)
            NSGraphicsContext.currentContext().setShouldAntialias_(YES)
            NSGraphicsContext.currentContext().setImageInterpolation_(
                NSImageInterpolationHigh)
            self.image.nsimage.drawInRect_fromRect_operation_fraction_(
                dest_rect, source_rect, NSCompositeSourceOver, 1.0)
        if self.border:
            context = drawing.DrawingContext(self, self.bounds(), dest_rect)
            context.style = drawing.DrawingStyle()
            context.set_line_width(1)
            context.set_color((0, 0, 0))    # black
            context.rectangle(0, 0, context.width, context.height)
            context.stroke()

    def calculateSourceRectFromDestRect_(self, dest_rect):
        """Calulate where dest_rect maps to on our image.

        This is tricky because our image might be scaled up, in which case
        the rect from our image will be smaller than dest_rect.
        """
        view_size = self.frame().size
        x_scale = float(self.image.width) / view_size.width
        y_scale = float(self.image.height) / view_size.height

        return NSMakeRect(dest_rect.origin.x * x_scale,
                dest_rect.origin.y * y_scale,
                dest_rect.size.width * x_scale,
                dest_rect.size.height * y_scale)

    # XXX FIXME: should track mouse movement - mouseDown is not the correct
    # event.
    def mouseDown_(self, event):
        wrappermap.wrapper(self).emit('clicked')

class ImageDisplay(Widget):
    """See https://develop.participatoryculture.org/index.php/WidgetAPI for a description of the API for this class."""
    def __init__(self, image=None):
        Widget.__init__(self)
        self.create_signal('clicked')
        self.view = NSImageDisplay.alloc().init()
        self.set_image(image)

    def set_image(self, image):
        self.image = image
        if image:
            image.nsimage.setCacheMode_(NSImageCacheNever)
        self.view.set_image(image)
        self.invalidate_size_request()

    def set_border(self, border):
        self.view.set_border(border)

    def calc_size_request(self):
        if self.image is not None:
            return self.image.width, self.image.height
        else:
            return 0, 0

class ClickableImageButton(ImageDisplay):
    def __init__(self, image_path, max_width=None, max_height=None):
        ImageDisplay.__init__(self)
        self.set_border(True)
        self.max_width = max_width
        self.max_height = max_height
        self.image = None
        self._width, self._height = None, None
        if image_path:
            self.set_path(image_path)

    def set_path(self, path):
        image = Image(path)
        if self.max_width:
            image = image.resize_for_space(self.max_width, self.max_height)
        super(ClickableImageButton, self).set_image(image)

    def calc_size_request(self):
        if self.max_width:
            return self.max_width, self.max_height
        else:
            return ImageDisplay.calc_size_request(self)

class MiroImageView(NSImageView):
    def viewWillMoveToWindow_(self, aWindow):
        self.setAnimates_(not aWindow == nil)

class AnimatedImageDisplay(Widget):
    def __init__(self, path):
        Widget.__init__(self)
        self.nsimage = NSImage.alloc().initByReferencingFile_(
          filename_to_unicode(path))
        self.view = MiroImageView.alloc().init()
        self.view.setImage_(self.nsimage)
        # enabled when viewWillMoveToWindow:aWindow invoked
        self.view.setAnimates_(NO)

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

    def get_width(self):
        return self.calc_size_request()[0]

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
        val = self.view.stringValue()
        if not val:
            val = u''
        return val

    def set_selectable(self, val):
        self.view.setSelectable_(val)

    def set_alignment(self, alignment):
        self.view.setAlignment_(alignment)
      
    def get_alignment(self, alignment):
        return self.view.alignment()

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

class HLine(Widget):
    def __init__(self):
        Widget.__init__(self)
        self.view = NSBox.alloc().init()
        self.view.setBoxType_(NSBoxSeparator)

    def calc_size_request(self):
        return self.view.frame().size.width, self.view.frame().size.height
