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

"""miro.plat.frontends.widgets.customcontrol -- CustomControl handlers.  """

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

from miro.frontends.widgets import widgetconst
from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets.base import Widget
from miro.plat.frontends.widgets import drawing
from miro.plat.frontends.widgets.layoutmanager import LayoutManager

class DrawableButtonCell(NSButtonCell):
    def startTrackingAt_inView_(self, point, view):
        view.setState_(NSOnState)
        return YES

    def continueTracking_at_inView_(self, lastPoint, at, view):
        view.setState_(NSOnState)
        return YES

    def stopTracking_at_inView_mouseIsUp_(self, lastPoint, at, view, mouseIsUp):
        if not mouseIsUp:
            view.mouse_inside = False
            view.setState_(NSOffState)

class DrawableButton(NSButton):
    def init(self):
        self = super(DrawableButton, self).init()
        self.layout_manager = LayoutManager()
        self.tracking_area = None
        self.mouse_inside = False
        self.custom_cursor = None
        return self

    def resetCursorRects(self):
        if self.custom_cursor is not None:
            self.addCursorRect_cursor_(self.visibleRect(), self.custom_cursor)
            self.custom_cursor.setOnMouseEntered_(YES)

    def updateTrackingAreas(self):
        # remove existing tracking area if needed
        if self.tracking_area:
            self.removeTrackingArea_(self.tracking_area)

        # create a new tracking area for the entire view.  This allows us to
        # get mouseMoved events whenever the mouse is inside our view.
        self.tracking_area = NSTrackingArea.alloc()
        self.tracking_area.initWithRect_options_owner_userInfo_(
                self.visibleRect(),
                NSTrackingMouseEnteredAndExited | NSTrackingMouseMoved |
                NSTrackingActiveInKeyWindow,
                self,
                nil)
        self.addTrackingArea_(self.tracking_area)

    def mouseEntered_(self, event):
        window = self.window()
        if window is not nil and window.isMainWindow():
            self.mouse_inside = True
            self.setNeedsDisplay_(YES)

    def mouseExited_(self, event):
        window = self.window()
        if window is not nil and window.isMainWindow():
            self.mouse_inside = False
            self.setNeedsDisplay_(YES)

    def isOpaque(self):
        return wrappermap.wrapper(self).is_opaque()

    def drawRect_(self, rect):
        context = drawing.DrawingContext(self, self.bounds(), rect)
        context.style = drawing.DrawingStyle()
        wrapper = wrappermap.wrapper(self)
        wrapper.state = 'normal'
        disabled = wrapper.get_disabled()
        if not disabled:
            if self.state() == NSOnState:
                wrapper.state = 'pressed'
            elif self.mouse_inside:
                wrapper.state = 'hover'
            else:
                wrapper.state = 'normal'

        wrapper.draw(context, self.layout_manager)
        self.layout_manager.reset()

    def sendAction_to_(self, action, to):
        # We override the Cocoa machinery here and just send it to our wrapper
        # widget.
        wrapper = wrappermap.wrapper(self)
        disabled = wrapper.get_disabled()
        if not disabled:
            wrapper.emit('clicked')
        # Tell Cocoa we handled it anyway, just not emit the actual clicked
        # event.
        return YES
DrawableButton.setCellClass_(DrawableButtonCell)

class ContinousButtonCell(DrawableButtonCell):
    def stopTracking_at_inView_mouseIsUp_(self, lastPoint, at, view, mouseIsUp):
        view.onStopTracking(at)
        NSButtonCell.stopTracking_at_inView_mouseIsUp_(self, lastPoint, at,
                view, mouseIsUp)

class ContinuousDrawableButton(DrawableButton):
    def init(self):
        self = super(ContinuousDrawableButton, self).init()
        self.setContinuous_(YES)
        return self

    def mouseDown_(self, event):
        self.releaseInbounds = self.stopTracking = self.firedOnce = False
        self.cell().trackMouse_inRect_ofView_untilMouseUp_(event,
                self.bounds(), self, YES)
        wrapper = wrappermap.wrapper(self)
        if not wrapper.get_disabled():
            if self.firedOnce:
                wrapper.emit('released')
            elif self.releaseInBounds:
                wrapper.emit('clicked')

    def sendAction_to_(self, action, to):
        if self.stopTracking:
            return NO
        self.firedOnce = True
        wrapper = wrappermap.wrapper(self)
        if not wrapper.get_disabled():
            wrapper.emit('held-down')
        return YES

    def onStopTracking(self, mouseLocation):
        self.releaseInbounds = NSPointInRect(mouseLocation, self.bounds())
        self.stopTracking = True
ContinuousDrawableButton.setCellClass_(ContinousButtonCell)

class DragableButtonCell(NSButtonCell):
    def startTrackingAt_inView_(self, point, view):
        self.start_x = point.x
        return YES

    def continueTracking_at_inView_(self, lastPoint, at, view):
        DRAG_THRESHOLD = 15
        wrapper = wrappermap.wrapper(view)
        if not wrapper.get_disabled():
            if (view.last_drag_event != 'right' and
                    at.x > self.start_x + DRAG_THRESHOLD):
                wrapper.emit("dragged-right")
                view.last_drag_event = 'right'
            elif (view.last_drag_event != 'left' and
                    at.x < self.start_x - DRAG_THRESHOLD):
                view.last_drag_event = 'left'
                wrapper.emit("dragged-left")
        return YES

class DragableDrawableButton(DrawableButton):
    def mouseDown_(self, event):
        self.last_drag_event = None
        self.cell().trackMouse_inRect_ofView_untilMouseUp_(event,
                self.bounds(), self, YES)

    def sendAction_to_(self, action, to):
        # only send the click event if we didn't send a
        # dragged-left/dragged-right event
        wrapper = wrappermap.wrapper(self)
        if self.last_drag_event is None and not wrapper.get_disabled():
            wrapper.emit('clicked')
        return YES
DragableDrawableButton.setCellClass_(DragableButtonCell)

class CustomSliderCell(NSSliderCell):
    def calc_slider_amount(self, view, pos, size):
        slider_size = wrappermap.wrapper(view).slider_size()
        pos -= slider_size / 2
        size -= slider_size
        return max(0, min(1, float(pos) / size))

    def startTrackingAt_inView_(self, at, view):
        wrapper = wrappermap.wrapper(view)
        if not wrapper.get_disabled():
            wrapper.emit('pressed')
        return self.continueTracking_at_inView_(at, at, view)

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
        wrapper = wrappermap.wrapper(view)
        if not wrapper.get_disabled():
            wrapper.emit('moved', value)
            if self.isContinuous():
                wrapper.emit('changed', value)
        return YES
    
    def stopTracking_at_inView_mouseIsUp_(self, lastPoint, at, view, mouseUp):
        wrapper = wrappermap.wrapper(view)
        if not wrapper.get_disabled():
            wrapper.emit('released')

class CustomSliderView(NSSlider):
    def init(self):
        self = super(CustomSliderView, self).init()
        self.layout_manager = LayoutManager()
        self.custom_cursor = None
        return self

    def resetCursorRects(self):
        if self.custom_cursor is not None:
            self.addCursorRect_cursor_(self.visibleRect(), self.custom_cursor)
            self.custom_cursor.setOnMouseEntered_(YES)

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
        wrapper = wrappermap.wrapper(self)
        disabled = wrapper.get_disabled()
        if not disabled:
            wrapper.emit('changed', self.floatValue())
        # Total Cocoa we handled it anyway to prevent the event passed to
        # upper layer.
        return YES
CustomSliderView.setCellClass_(CustomSliderCell)

class CustomControlBase(drawing.DrawingMixin, Widget):
    def set_cursor(self, cursor):
        if cursor == widgetconst.CURSOR_NORMAL:
            self.view.custom_cursor = None
        elif cursor == widgetconst.CURSOR_POINTING_HAND:
            self.view.custom_cursor = NSCursor.pointingHandCursor()
        else:
            raise ValueError("Unknown cursor: %s" % cursor)
        if self.view.window():
            self.view.window().invalidateCursorRectsForView_(self.view)

class CustomButton(CustomControlBase):
    """See https://develop.participatoryculture.org/index.php/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        CustomControlBase.__init__(self)
        self.create_signal('clicked')
        self.view = DrawableButton.alloc().init()
        self.view.setRefusesFirstResponder_(NO)
        self.view.setEnabled_(True)
    
    def enable(self):
        Widget.enable(self)
        self.view.setNeedsDisplay_(YES)

    def disable(self):
        Widget.disable(self)
        self.view.setNeedsDisplay_(YES)

class ContinuousCustomButton(CustomButton):
    """See https://develop.participatoryculture.org/index.php/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        CustomButton.__init__(self)
        self.create_signal('held-down')
        self.create_signal('released')
        self.view = ContinuousDrawableButton.alloc().init()
        self.view.setRefusesFirstResponder_(NO)

    def set_delays(self, initial, repeat):
        self.view.cell().setPeriodicDelay_interval_(initial, repeat)

class DragableCustomButton(CustomButton):
    """See https://develop.participatoryculture.org/index.php/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        CustomButton.__init__(self)
        self.create_signal('dragged-left')
        self.create_signal('dragged-right')
        self.view = DragableDrawableButton.alloc().init()

class CustomSlider(CustomControlBase):
    """See https://develop.participatoryculture.org/index.php/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        CustomControlBase.__init__(self)
        self.create_signal('pressed')
        self.create_signal('released')
        self.create_signal('changed')
        self.create_signal('moved')
        self.view = CustomSliderView.alloc().init()
        self.view.setRefusesFirstResponder_(NO)
        if self.is_continuous():
            self.view.setContinuous_(YES)
        else:
            self.view.setContinuous_(NO)
        self.view.setEnabled_(True)

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

    def enable(self):
        Widget.enable(self)
        self.view.setNeedsDisplay_(YES)

    def disable(self):
        Widget.disable(self)
        self.view.setNeedsDisplay_(YES)
