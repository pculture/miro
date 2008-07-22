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

"""miro.plat.frontends.widgets.customcontrol -- CustomControl handlers.  """

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets.base import Widget, SimpleBin, FlippedView
from miro.plat.frontends.widgets import drawing
from miro.plat.frontends.widgets.layoutmanager import LayoutManager
from miro.plat.frontends.widgets.rect import NSRectWrapper

class DrawableButtonCell(NSButtonCell):
    def startTrackingAt_inView_(self, point, view):
        view.setState_(NSOnState)
        return YES

    def continueTracking_at_inView_(self, lastPoint, at, view):
        view.setState_(NSOnState)
        return YES

    def stopTracking_at_inView_mouseIsUp_(self, lastPoint, at, view, mouseIsUp):
        if not mouseIsUp:
            view.setState_(NSOffState)

class DrawableButton(NSButton):
    def init(self):
        NSButton.init(self)
        self.layout_manager = LayoutManager()
        return self

    def isOpaque(self):
        return wrappermap.wrapper(self).is_opaque()

    def drawRect_(self, rect):
        context = drawing.DrawingContext(self, self.bounds(), rect)
        context.style = drawing.DrawingStyle()
        if self.state() == NSOnState:
            wrappermap.wrapper(self).draw_pressed(context, self.layout_manager)
        else:
            wrappermap.wrapper(self).draw(context, self.layout_manager)
        self.layout_manager.reset()

    def sendAction_to_(self, action, to):
        # We override the Cocoa machinery here and just send it to our wrapper
        # widget.
        wrappermap.wrapper(self).emit('clicked')
        return YES
DrawableButton.setCellClass_(DrawableButtonCell)

class ContinousButtonCell(DrawableButtonCell):
    def stopTracking_at_inView_mouseIsUp_(self, lastPoint, at, view, mouseIsUp):
        view.onStopTracking(at)
        NSButtonCell.stopTracking_at_inView_mouseIsUp_(self, lastPoint, at,
                view, mouseIsUp)

class ContinuousDrawableButton(DrawableButton):
    def init(self):
        DrawableButton.init(self)
        self.setContinuous_(YES)
        return self

    def mouseDown_(self, event):
        self.releaseInbounds = self.stopTracking = self.firedOnce = False
        self.cell().trackMouse_inRect_ofView_untilMouseUp_(event,
                self.bounds(), self, YES)
        if not self.firedOnce and self.releaseInbounds:
            wrappermap.wrapper(self).emit('clicked')

    def sendAction_to_(self, action, to):
        if self.stopTracking:
            return NO
        self.firedOnce = True
        wrappermap.wrapper(self).emit('held-down')
        return YES

    def onStopTracking(self, mouseLocation):
        self.releaseInbounds = NSPointInRect(mouseLocation, self.bounds())
        self.stopTracking = True
ContinuousDrawableButton.setCellClass_(ContinousButtonCell)

class CustomSliderCell(NSSliderCell):
    def calc_slider_amount(self, view, pos, size):
        slider_size = wrappermap.wrapper(view).slider_size()
        pos -= slider_size / 2
        size -= slider_size
        return max(0, min(1, float(pos) / size))

    def startTrackingAt_inView_(self, at, view):
        wrappermap.wrapper(view).emit('clicked')
        return YES

    def continueTracking_at_inView_(self, lastPoint, at, view):
        if view.isVertical():
            pos = at.y
            size = view.bounds().size.height
        else:
            pos = at.x
            size = view.bounds().size.width
        slider_amount = self.calc_slider_amount(view, pos, size)
        value = (self.maxValue() - self.minValue()) * slider_amount
        self.setFloatValue_(value)
        wrappermap.wrapper(view).emit('moved', value)
        if self.isContinuous():
            wrappermap.wrapper(view).emit('changed', value)
        return YES
    
    def stopTracking_at_inView_mouseIsUp_(self, lastPoint, at, view, mouseUp):
        wrappermap.wrapper(view).emit('released')

class CustomSliderView(NSSlider):
    def init(self):
        NSSlider.init(self)
        self.layout_manager = LayoutManager()
        return self

    def isOpaque(self):
        return wrappermap.wrapper(self).is_opaque()

    def knobThickness(self):
        return wrappermap.wrapper(self).slider_size()

    def isVertical(self):
        return not wrappermap.wrapper(self).is_horizontal()

    def drawRect_(self, rect):
        context = drawing.DrawingContext(self, self.bounds(), rect)
        context.style = drawing.DrawingStyle()
        wrappermap.wrapper(self).draw(context, self.layout_manager)
        self.layout_manager.reset()

    def sendAction_to_(self, action, to):
        # We override the Cocoa machinery here and just send it to our wrapper
        # widget.
        wrappermap.wrapper(self).emit('changed', self.floatValue())
        return YES
CustomSliderView.setCellClass_(CustomSliderCell)

class CustomButton(drawing.DrawingMixin, Widget):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        Widget.__init__(self)
        self.create_signal('clicked')
        self.view = DrawableButton.alloc().init()
        self.view.setRefusesFirstResponder_(NO)

class ContinuousCustomButton(CustomButton):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        CustomButton.__init__(self)
        self.create_signal('held-down')
        self.view = ContinuousDrawableButton.alloc().init()
        self.view.setRefusesFirstResponder_(NO)

    def set_delays(self, initial, repeat):
        self.view.cell().setPeriodicDelay_interval_(initial, repeat)

class CustomSlider(drawing.DrawingMixin, Widget):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        Widget.__init__(self)
        self.create_signal('clicked')
        self.create_signal('released')
        self.create_signal('changed')
        self.create_signal('moved')
        self.view = CustomSliderView.alloc().init()
        self.view.setRefusesFirstResponder_(NO)
        if self.is_continuous():
            self.view.setContinuous_(YES)
        else:
            self.view.setContinuous_(NO)

    def viewport_created(self):
        self.view.cell().setKnobThickness_(self.slider_size())

    def get_value(self):
        return self.view.floatValue()

    def set_value(self, value):
        self.view.setFloatValue_(value)

    def get_range(self):
        return self.view.minValue(), self.view.maxValue()

    def set_range(self, min_value, max_value):
        self.view.setMinValue_(min_value)
        self.view.setMaxValue_(max_value)

    def set_increments(self, increment, big_increment):
        pass
