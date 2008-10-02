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

"""video.py -- Video code. """

import time

import gobject
import gtk
import logging

from miro import app
from miro.plat import screensaver
from miro.frontends.widgets.gtk.widgetset import Widget
from miro.frontends.widgets.gtk import wrappermap

class NullRenderer(object):
    def can_play_file(self, path):
        return False

    def reset(self):
        pass

def make_hidden_cursor():
    pixmap = gtk.gdk.Pixmap(None, 1, 1, 1)
    color = gtk.gdk.Color()
    return gtk.gdk.Cursor(pixmap, pixmap, color, color, 0, 0)

# Couple of utility functions to grab GTK widgets out of the widget tree for
# fullscreen code
def _videobox_widget():
    return app.widgetapp.window.videobox._widget

def _window():
    return app.widgetapp.window._window

def can_play_file(path):
    if app.renderer is not None:
        return app.renderer.can_play_file(path)
    logging.warn("can_play_file: app.renderer is None")
    return False

class VideoRenderer(Widget):
    """Video renderer widget.

    Note: app.renderer must be initialized before instantiating this class.
    If no renderers can be found, set app.renderer to None.
    """

    HIDE_CONTROLS_TIMEOUT = 2000

    def __init__(self):
        Widget.__init__(self)
        if app.renderer is not None:
            self.renderer = app.renderer
        else:
            self.renderer = NullRenderer()
        self.set_widget(gtk.DrawingArea())
        self._widget.set_double_buffered(False)
        self._widget.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.renderer.set_widget(self._widget)
        self.hide_controls_timeout = None
        self.motion_handler = None
        self.videobox_motion_handler = None
        self.hidden_cursor = make_hidden_cursor()

    def teardown(self):
        self.renderer.reset()
    
    def set_movie_item(self, item_info):
        self.renderer.select_file(item_info.video_path)

    def get_elapsed_playback_time(self):
        return self.renderer.get_current_time()

    def get_total_playback_time(self):
        return self.renderer.get_duration()

    def set_volume(self, volume):
        self.renderer.set_volume(volume)

    def play(self):
        self.renderer.play()

    def play_from_time(self, resume_time=0):
        self.seek_to_time(resume_time)
        self.play()

    def pause(self):
        self.renderer.pause()

    def stop(self):
        self.renderer.stop()

    def set_playback_rate(self, rate):
        print "set_playback_rate: implement me!"

    def seek_to(self, position):
        time = self.get_total_playback_time() * position
        self.seek_to_time(time)

    def seek_to_time(self, time_pos):
        self.renderer.set_current_time(time_pos)

    def enter_fullscreen(self):
        self.screensaver_manager = screensaver.create_manager()
        if self.screensaver_manager is not None:
            self.screensaver_manager.disable()
        self.motion_handler = self.wrapped_widget_connect(
                'motion-notify-event', self.on_mouse_motion)
        self.videobox_motion_handler = _videobox_widget().connect(
                'motion-notify-event', self.on_mouse_motion)
        app.widgetapp.window.menubar.hide()
        self.schedule_hide_controls(self.HIDE_CONTROLS_TIMEOUT)
        _window().fullscreen()

    def on_mouse_motion(self, widget, event):
        if not _videobox_widget().props.visible:
            self.show_controls()
            self.schedule_hide_controls(self.HIDE_CONTROLS_TIMEOUT)
        else:
            self.last_motion_time = time.time()

    def show_controls(self):
        _videobox_widget().show()
        _window().window.set_cursor(None)

    def on_hide_controls_timeout(self):
        # Check if the mouse moved before the timeout
        time_since_motion = int((time.time() - self.last_motion_time) * 1000)
        timeout_left = self.HIDE_CONTROLS_TIMEOUT - time_since_motion
        if timeout_left <= 0:
            _window().window.set_cursor(self.hidden_cursor)
            _videobox_widget().hide()
            self.hide_controls_timeout = None
        else:
            self.schedule_hide_controls(timeout_left)

    def cancel_hide_controls(self):
        if self.hide_controls_timeout is not None:
            gobject.source_remove(self.hide_controls_timeout)

    def schedule_hide_controls(self, time):
        self.hide_controls_timeout = gobject.timeout_add(time,
                self.on_hide_controls_timeout)
        self.last_motion_time = 0

    def exit_fullscreen(self):
        if self.screensaver_manager is not None:
            self.screensaver_manager.enable()
            self.screensaver_manager = None
        app.widgetapp.window.menubar.show()
        _videobox_widget().show()
        _window().unfullscreen()
        self._widget.disconnect(self.motion_handler)
        _videobox_widget().disconnect(self.videobox_motion_handler)
        self.cancel_hide_controls()
        _window().window.set_cursor(None)
