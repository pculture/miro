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

"""miro.frontends.widgets.gtk.controls -- Contains the ControlBox and
CustomControl classes.  These handle the custom buttons/sliders used during
playback.
"""

import math

import gtk
import gobject

from miro.frontends.widgets.gtk import wrappermap
from miro.frontends.widgets.gtk.base import Widget, Bin
from miro.frontends.widgets.gtk.simple import Label
from miro.frontends.widgets.gtk.drawing import CustomDrawingMixin, Drawable
from miro.plat.frontends.widgets import timer

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

class CustomScaleMixin(CustomControlMixin):
    def __init__(self):
        self.in_drag = False
        self.drag_inbounds = False
        self.drag_button = None
        self.min = self.max = 0.0

    def get_range(self):
        return self.min, self.max

    def set_range(self, min, max):
        self.min = float(min)
        self.max = float(max)
        gtk.Range.set_range(self, min, max)

    def is_continuous(self):
        return wrappermap.wrapper(self).is_continuous()

    def do_button_press_event(self, event):
        if self.in_drag:
            return
        self.start_value = self.get_value()
        self.in_drag = True
        self.drag_button = event.button
        self.drag_inbounds = True
        self.move_slider_to_mouse(event.x, event.y)
        self.grab_focus()
        wrappermap.wrapper(self).emit('pressed')

    def do_motion_notify_event(self, event):
        if self.in_drag:
            self.move_slider_to_mouse(event.x, event.y)

    def calc_percent(self, pos, size):
        slider_size = wrappermap.wrapper(self).slider_size()
        pos -= slider_size / 2
        size -= slider_size
        return max(0, min(1, float(pos) / size))

    def is_horizontal(self):
        # this comes from a mixin
        pass

    def gtk_scale_class(self):
        if self.is_horizontal():
            return gtk.HScale
        else:
            return gtk.VScale

    def move_slider_to_mouse(self, x, y):
        if ((not 0 <= x < self.allocation.width) or
                (not 0 <= y < self.allocation.height)):
            self.handle_drag_out_of_bounds()
            return
        if self.is_horizontal():
            pos = x
            size = self.allocation.width
        else:
            pos = y
            size = self.height
        value = (self.max - self.min) * self.calc_percent(pos, size)
        self.set_value(value)
        wrappermap.wrapper(self).emit('moved', self.get_value())
        if self.is_continuous():
            wrappermap.wrapper(self).emit('changed', self.get_value())

    def handle_drag_out_of_bounds(self):
        self.drag_inbounds = False
        if not self.is_continuous():
            self.set_value(self.start_value)

    def do_button_release_event(self, event):
        if event.button != self.drag_button:
            return
        self.in_drag = False
        if (self.is_continuous and
                (0 <= event.x < self.allocation.width) and
                (0 <= event.y < self.allocation.height)):
            wrappermap.wrapper(self).emit('changed', self.get_value())
        wrappermap.wrapper(self).emit('released')

    def do_scroll_event(self, event):
        if self.is_horizontal():
            if event.direction == gtk.gdk.SCROLL_UP:
                event.direction = gtk.gdk.SCROLL_DOWN
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                event.direction = gtk.gdk.SCROLL_UP
        self.gtk_scale_class().do_scroll_event(self, event)
        # Treat mouse scrolls as if the user clicked on the new position
        wrappermap.wrapper(self).emit('pressed')
        wrappermap.wrapper(self).emit('changed', self.get_value())
        wrappermap.wrapper(self).emit('released')

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
gobject.type_register(CustomHScaleWidget)
gobject.type_register(CustomVScaleWidget)

class CustomButton(Drawable, Widget):
    def __init__(self):
        """Create a new CustomButton.  active_image will be displayed while
        the button is pressed.  The image must have the same size.
        """
        Widget.__init__(self)
        Drawable.__init__(self)
        self.set_widget(CustomButtonWidget())
        self.create_signal('clicked')
        self.forward_signal('clicked')

class ContinuousCustomButton(Drawable, Widget):
    def __init__(self):
        Widget.__init__(self)
        Drawable.__init__(self)
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

class CustomSlider(Drawable, Widget):
    def __init__(self):
        Widget.__init__(self)
        Drawable.__init__(self)
        self.create_signal('pressed')
        self.create_signal('released')
        self.create_signal('changed')
        self.create_signal('moved')
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

    def set_range(self, min_value, max_value):
        self._widget.set_range(min_value, max_value)
        # Try to pick a reasonable default for the digits
        range = max_value - min_value
        self._widget.set_digits(int(round(math.log10(100.0 / range))))

    def set_increments(self, increment, big_increment):
        self._widget.set_increments(increment, big_increment)

def to_miro_volume(value):
    """Convert from 0 to 1.0 to 0.0 to MAX_VOLUME.
    """
    if value == 0:
        return 0.0
    return value * 3.0

def to_gtk_volume(value):
    """Convert from 0.0 to MAX_VOLUME to 0 to 1.0.
    """
    if value > 0.0:
        value = (value / 3.0)
    return value

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
        self.wrapped_widget_connect('popdown', self.on_value_set)
        self.create_signal('changed')
        self.create_signal('released')

    def on_value_changed(self, *args):
        value = self.get_value()
        self.emit('changed', value)

    def on_value_set(self, *args):
        self.emit('released')

    def get_value(self):
        value = self._widget.get_property('value')
        return to_miro_volume(value)

    def set_value(self, value):
        value = to_gtk_volume(value)
        self._widget.set_property('value', value)
