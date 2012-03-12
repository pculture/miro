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

"""miro.frontends.widgets.gtk.controls -- Contains the ControlBox and
CustomControl classes.  These handle the custom buttons/sliders used during
playback.
"""

from __future__ import division
import math

import gtk
import gobject

from miro.frontends.widgets.gtk import wrappermap
from miro.frontends.widgets.gtk.base import Widget
from miro.frontends.widgets.gtk.simple import Label, Image
from miro.frontends.widgets.gtk.drawing import (CustomDrawingMixin, Drawable,
    ImageSurface)
from miro.plat.frontends.widgets import timer
from miro.frontends.widgets import widgetconst

class CustomControlMixin(CustomDrawingMixin):
    def do_expose_event(self, event):
        CustomDrawingMixin.do_expose_event(self, event)
        if self.is_focus():
            style = self.get_style()
            style.paint_focus(self.window, self.state,
                    event.area, self, None, self.allocation.x,
                    self.allocation.y, self.allocation.width,
                    self.allocation.height)

class CustomButtonWidget(CustomControlMixin, gtk.Button):
    def draw(self, wrapper, context):
        if self.is_active():
            wrapper.state = 'pressed'
        elif self.state == gtk.STATE_PRELIGHT:
            wrapper.state = 'hover'
        else:
            wrapper.state = 'normal'
        wrapper.draw(context, wrapper.layout_manager)
        self.set_focus_on_click(False)

    def is_active(self):
        return self.state == gtk.STATE_ACTIVE

class ContinuousCustomButtonWidget(CustomButtonWidget):
    def is_active(self):
        return (self.state == gtk.STATE_ACTIVE or
                wrappermap.wrapper(self).button_down)

class DragableCustomButtonWidget(CustomButtonWidget):
    def __init__(self):
        CustomButtonWidget.__init__(self)
        self.button_press_x = None
        self.set_events(self.get_events() | gtk.gdk.POINTER_MOTION_MASK)

    def do_button_press_event(self, event):
        self.button_press_x = event.x
        self.last_drag_event = None
        gtk.Button.do_button_press_event(self, event)

    def do_button_release_event(self, event):
        self.button_press_x = None
        gtk.Button.do_button_release_event(self, event)

    def do_motion_notify_event(self, event):
        DRAG_THRESHOLD = 15
        if self.button_press_x is None:
            # button not down
            return
        if (self.last_drag_event != 'right' and
                event.x > self.button_press_x + DRAG_THRESHOLD):
            wrappermap.wrapper(self).emit('dragged-right')
            self.last_drag_event = 'right'
        elif (self.last_drag_event != 'left' and
                event.x < self.button_press_x - DRAG_THRESHOLD):
            wrappermap.wrapper(self).emit('dragged-left')
            self.last_drag_event = 'left'

    def do_clicked(self):
        # only emit clicked if we didn't emit dragged-left or dragged-right
        if self.last_drag_event is None:
            wrappermap.wrapper(self).emit('clicked')

class _DragInfo(object):
    """Info about the start of a drag.

    Attributes:

    - button: button that started the drag
    - start_pos: position of the slider
    - click_pos: position of the click

    Note that start_pos and click_pos will be different if the user clicks
    inside the slider.
    """

    def __init__(self, button, start_pos, click_pos):
        self.button = button
        self.start_pos = start_pos
        self.click_pos = click_pos

class CustomScaleMixin(CustomControlMixin):
    def __init__(self):
        CustomControlMixin.__init__(self)
        self.drag_info = None
        self.min = self.max = 0.0

    def get_range(self):
        return self.min, self.max

    def set_range(self, min, max):
        self.min = float(min)
        self.max = float(max)
        gtk.Range.set_range(self, min, max)

    def is_continuous(self):
        return wrappermap.wrapper(self).is_continuous()

    def is_horizontal(self):
        # this comes from a mixin
        pass

    def gtk_scale_class(self):
        if self.is_horizontal():
            return gtk.HScale
        else:
            return gtk.VScale

    def get_slider_pos(self, value=None):
        if value is None:
            value = self.get_value()
        if self.is_horizontal():
            size = self.allocation.width
        else:
            size = self.allocation.height
        ratio = (float(value) - self.min) / (self.max - self.min)
        start_pos = self.slider_size() / 2.0
        return start_pos + ratio * (size - self.slider_size())

    def slider_size(self):
        return wrappermap.wrapper(self).slider_size()

    def _event_pos(self, event):
        """Get the position of an event.

        If we are horizontal, this will be the x coordinate.  If we are
        vertical, the y.
        """
        if self.is_horizontal():
            return event.x
        else:
            return event.y

    def do_button_press_event(self, event):
        if self.drag_info is not None:
            return
        current_pos = self.get_slider_pos()
        event_pos = self._event_pos(event)
        pos_difference = abs(current_pos - event_pos)
        # only move the slider if the click was outside its boundaries
        # (#18840)
        if pos_difference > self.slider_size() / 2.0:
            self.move_slider(event_pos)
        self.drag_info = _DragInfo(event.button,
                                   self.get_slider_pos(),
                                   event_pos)
        self.grab_focus()
        wrappermap.wrapper(self).emit('pressed')

    def do_motion_notify_event(self, event):
        if self.drag_info is not None:
            event_pos = self._event_pos(event)
            delta = event_pos - self.drag_info.click_pos
            self.move_slider(self.drag_info.start_pos + delta)

    def move_slider(self, new_pos):
        """Move the slider so that it's centered on new_pos."""
        if self.is_horizontal():
            size = self.allocation.width
        else:
            size = self.allocation.height

        slider_size = self.slider_size()
        new_pos -= slider_size / 2
        size -= slider_size
        ratio = max(0, min(1, float(new_pos) / size))
        self.set_value(ratio * (self.max - self.min))

        wrappermap.wrapper(self).emit('moved', self.get_value())
        if self.is_continuous():
            wrappermap.wrapper(self).emit('changed', self.get_value())

    def handle_drag_out_of_bounds(self):
        if not self.is_continuous():
            self.set_value(self.start_value)

    def do_button_release_event(self, event):
        if event.button != self.drag_info.button:
            return
        self.drag_info = None
        if (self.is_continuous and
                (0 <= event.x < self.allocation.width) and
                (0 <= event.y < self.allocation.height)):
            wrappermap.wrapper(self).emit('changed', self.get_value())
        wrappermap.wrapper(self).emit('released')

    def do_scroll_event(self, event):
        wrapper = wrappermap.wrapper(self)
        if self.is_horizontal():
            if event.direction == gtk.gdk.SCROLL_UP:
                event.direction = gtk.gdk.SCROLL_DOWN
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                event.direction = gtk.gdk.SCROLL_UP
        if (wrapper._scroll_step is not None and
            event.direction in (gtk.gdk.SCROLL_UP, gtk.gdk.SCROLL_DOWN)):
            # handle the scroll ourself
            if event.direction == gtk.gdk.SCROLL_DOWN:
                delta = wrapper._scroll_step
            else:
                delta = -wrapper._scroll_step
            self.set_value(self.get_value() + delta)
        else:
            # let GTK handle the scroll
            self.gtk_scale_class().do_scroll_event(self, event)
        # Treat mouse scrolls as if the user clicked on the new position
        wrapper.emit('pressed')
        wrapper.emit('changed', self.get_value())
        wrapper.emit('released')

    def do_move_slider(self, scroll):
        if self.is_horizontal():
            if scroll == gtk.SCROLL_STEP_UP:
                scroll = gtk.SCROLL_STEP_DOWN
            elif scroll == gtk.SCROLL_STEP_DOWN:
                scroll = gtk.SCROLL_STEP_UP
            elif scroll == gtk.SCROLL_PAGE_UP:
                scroll = gtk.SCROLL_PAGE_DOWN
            elif scroll == gtk.SCROLL_PAGE_DOWN:
                scroll = gtk.SCROLL_PAGE_UP
            elif scroll == gtk.SCROLL_START:
                scroll = gtk.SCROLL_END
            elif scroll == gtk.SCROLL_END:
                scroll = gtk.SCROLL_START
        return self.gtk_scale_class().do_move_slider(self, scroll)

class CustomHScaleWidget(CustomScaleMixin, gtk.HScale):
    def __init__(self):
        CustomScaleMixin.__init__(self)
        gtk.HScale.__init__(self)

    def is_horizontal(self):
        return True

class CustomVScaleWidget(CustomScaleMixin, gtk.VScale):
    def __init__(self):
        CustomScaleMixin.__init__(self)
        gtk.VScale.__init__(self)

    def is_horizontal(self):
        return False

gobject.type_register(CustomButtonWidget)
gobject.type_register(ContinuousCustomButtonWidget)
gobject.type_register(DragableCustomButtonWidget)
gobject.type_register(CustomHScaleWidget)
gobject.type_register(CustomVScaleWidget)

class CustomControlBase(Drawable, Widget):
    def __init__(self):
        Widget.__init__(self)
        Drawable.__init__(self)
        self._gtk_cursor = None
        self._entry_handlers = None

    def _connect_enter_notify_handlers(self):
        if self._entry_handlers is None:
            self._entry_handlers = [
                    self.wrapped_widget_connect('enter-notify-event',
                        self.on_enter_notify),
                    self.wrapped_widget_connect('leave-notify-event',
                        self.on_leave_notify),
                    self.wrapped_widget_connect('button-release-event',
                        self.on_click)
            ]

    def _disconnect_enter_notify_handlers(self):
        if self._entry_handlers is not None:
            for handle in self._entry_handlers:
                self._widget.disconnect(handle)
            self._entry_handlers = None

    def set_cursor(self, cursor):
        if cursor == widgetconst.CURSOR_NORMAL:
            self._gtk_cursor = None
            self._disconnect_enter_notify_handlers()
        elif cursor == widgetconst.CURSOR_POINTING_HAND:
            self._gtk_cursor = gtk.gdk.Cursor(gtk.gdk.HAND2)
            self._connect_enter_notify_handlers()
        else:
            raise ValueError("Unknown cursor: %s" % cursor)

    def on_enter_notify(self, widget, event):
        self._widget.window.set_cursor(self._gtk_cursor)

    def on_leave_notify(self, widget, event):
        if self._widget.window:
            self._widget.window.set_cursor(None)

    def on_click(self, widget, event):
        self.emit('clicked')
        return True

class CustomButton(CustomControlBase):
    def __init__(self):
        """Create a new CustomButton.  active_image will be displayed while
        the button is pressed.  The image must have the same size.
        """
        CustomControlBase.__init__(self)
        self.set_widget(CustomButtonWidget())
        self.create_signal('clicked')
        self.forward_signal('clicked')

class ContinuousCustomButton(CustomControlBase):
    def __init__(self):
        CustomControlBase.__init__(self)
        self.set_widget(ContinuousCustomButtonWidget())
        self.button_down = False
        self.button_held = False
        self.timeout = None
        self.create_signal('clicked')
        self.create_signal('held-down')
        self.create_signal('released')
        self.wrapped_widget_connect('pressed', self.on_pressed)
        self.wrapped_widget_connect('released', self.on_released)
        self.wrapped_widget_connect('clicked', self.on_clicked)
        self.initial_delay = 0.6
        self.repeat_delay = 0.3

    def set_delays(self, initial_delay, repeat_delay):
        self.initial_delay = initial_delay
        self.repeat_delay = repeat_delay

    def on_pressed(self, widget):
        if self.timeout:
            timer.cancel(self.timeout)
        self.button_down = True
        self.button_held = False
        self.timeout = timer.add(self.initial_delay, self.on_button_hold)

    def on_button_hold(self):
        self.button_held = True
        self.emit('held-down')
        self.timeout = timer.add(self.repeat_delay, self.on_button_hold)

    def on_released(self, widget):
        if self.timeout:
            timer.cancel(self.timeout)
        self.timeout = None
        self.button_down = self.button_held = False
        self.queue_redraw()
        self.emit('released')

    def on_clicked(self, widget):
        if self.timeout:
            timer.cancel(self.timeout)
        if not self.button_held:
            self.emit('clicked')

class DragableCustomButton(CustomControlBase):
    def __init__(self):
        CustomControlBase.__init__(self)
        self.set_widget(DragableCustomButtonWidget())
        self.create_signal('clicked')
        self.create_signal('dragged-left')
        self.create_signal('dragged-right')

class CustomSlider(CustomControlBase):
    def __init__(self):
        CustomControlBase.__init__(self)
        self.create_signal('pressed')
        self.create_signal('released')
        self.create_signal('changed')
        self.create_signal('moved')
        self._scroll_step = None
        if self.is_horizontal():
            self.set_widget(CustomHScaleWidget())
        else:
            self.set_widget(CustomVScaleWidget())
        self.wrapped_widget_connect('move-slider', self.on_slider_move)

    def on_slider_move(self, widget, scrolltype):
        self.emit('changed', widget.get_value())
        self.emit('moved', widget.get_value())

    def get_value(self):
        return self._widget.get_value()

    def set_value(self, value):
        self._widget.set_value(value)

    def get_range(self):
        return self._widget.get_range()

    def get_slider_pos(self, value=None):
        """Get the position for the slider for our current value.

        This will return position that the slider should be centered on to
        display the value.  It will be the x coordinate if is_horizontal() is
        True and the y coordinate otherwise.

        This method takes into acount the size of the slider when calculating
        the position.  The slider position will start at (slider_size / 2) and
        will end (slider_size / 2) px before the end of the widget.

        :param value: value to get the position for.  Defaults to the current
        value
        """
        return self._widget.get_slider_pos(value)

    def set_range(self, min_value, max_value):
        self._widget.set_range(min_value, max_value)
        # set_digits controls the precision of the scale by limiting changes
        # to a certain number of digits.  If the range is [0, 1], this code
        # will give us 4 digits of precision, which seems reasonable.
        range = max_value - min_value
        self._widget.set_digits(int(round(math.log10(10000.0 / range))))

    def set_increments(self, small_step, big_step, scroll_step=None):
        """Set the increments to scroll.

        :param small_step: scroll amount for up/down
        :param big_step: scroll amount for page up/page down.
        :param scroll_step: scroll amount for mouse wheel, or None to make
                            this 2 times the small step
        """
        self._widget.set_increments(small_step, big_step)
        self._scroll_step = scroll_step

def to_miro_volume(value):
    """Convert from 0 to 1.0 to 0.0 to MAX_VOLUME.
    """
    if value == 0:
        return 0.0
    return value * widgetconst.MAX_VOLUME

def to_gtk_volume(value):
    """Convert from 0.0 to MAX_VOLUME to 0 to 1.0.
    """
    if value > 0.0:
        value = (value / widgetconst.MAX_VOLUME)
    return value

if hasattr(gtk.VolumeButton, "get_popup"):
    # FIXME - Miro on Windows has an old version of gtk (2.16) and
    # doesn't have the get_popup method.  Once we upgrade and
    # fix that, we can take out the hasattr check.

    class VolumeMuter(Label):
        """Empty space that has a clicked signal so it can be dropped
        in place of the VolumeMuter.
        """
        def __init__(self):
            Label.__init__(self)
            self.create_signal("clicked")

    class VolumeSlider(Widget):
        """VolumeSlider that uses the gtk.VolumeButton().
        """
        def __init__(self):
            Widget.__init__(self)
            self.set_widget(gtk.VolumeButton())
            self.wrapped_widget_connect('value-changed', self.on_value_changed)
            self._widget.get_popup().connect("hide", self.on_hide)
            self.create_signal('changed')
            self.create_signal('released')

        def on_value_changed(self, *args):
            value = self.get_value()
            self.emit('changed', value)

        def on_hide(self, *args):
            self.emit('released')

        def get_value(self):
            value = self._widget.get_property('value')
            return to_miro_volume(value)

        def set_value(self, value):
            value = to_gtk_volume(value)
            self._widget.set_property('value', value)

class ClickableImageButton(CustomButton):
    """Image that can send clicked events. If max_width and/or max_height are
    specified, resizes the image proportionally such that all constraints are
    met.
    """
    def __init__(self, image_path, max_width=None, max_height=None):
        CustomButton.__init__(self)
        self.max_width = max_width
        self.max_height = max_height
        self.image = None
        self._width, self._height = None, None
        if image_path:
            self.set_path(image_path)
        self.set_cursor(widgetconst.CURSOR_POINTING_HAND)

    def set_path(self, path):
        image = Image(path)
        if self.max_width:
            image = image.resize_for_space(self.max_width, self.max_height)
        self.image = ImageSurface(image)
        self._width, self._height = image.width, image.height

    def size_request(self, layout):
        w = self._width
        h = self._height
        if not w:
            w = self.max_width
        if not h:
            h = self.max_height
        return w, h

    def draw(self, context, layout):
        if self.image:
            self.image.draw(context, 0, 0, self._width, self._height)
        w = self._width
        h = self._height
        if not w:
            w = self.max_width
        if not h:
            h = self.max_height
        w = min(context.width, w)
        h = min(context.height, h)
        context.rectangle(0, 0, w, h)
        context.set_color((0, 0, 0))    # black
        context.set_line_width(1)
        context.stroke()
