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

import logging
import os
import time
import thread
from threading import Event

import pygst
pygst.require('0.10')
import gst
import gst.interfaces
import gtk

from miro import app
from miro import config
from miro import prefs
from miro.download_utils import nextFreeFilename
from miro.plat import options

from miro.frontends.widgets.gtk.threads import call_on_ui_thread

def to_seconds(t):
    return t / gst.SECOND

def from_seconds(s):
    return s * gst.SECOND

class Tester:
    def __init__(self, filename):
        self.done = Event()
        self.success = False
        self.actual_init(filename)

    def actual_init(self, filename):
        self.playbin = gst.element_factory_make('playbin')
        self.videosink = gst.element_factory_make("fakesink", "videosink")
        self.playbin.set_property("video-sink", self.videosink)
        self.audiosink = gst.element_factory_make("fakesink", "audiosink")
        self.playbin.set_property("audio-sink", self.audiosink)

        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.watch_id = self.bus.connect("message", self.on_bus_message)

        self.playbin.set_property("uri", "file://%s" % filename)
        self.playbin.set_state(gst.STATE_PAUSED)

    def result(self, yes_callback, no_callback):
        def _result():
            self.done.wait(1)
            self.disconnect()
            if self.success:
                call_on_ui_thread(yes_callback)
            else:
                call_on_ui_thread(no_callback)
        thread.start_new_thread(_result, ())

    def on_bus_message(self, bus, message):
        if message.src == self.playbin:
            if message.type == gst.MESSAGE_STATE_CHANGED:
                prev, new, pending = message.parse_state_changed()
                if new == gst.STATE_PAUSED:
                    # Success
                    self.success = True
                    self.done.set()

            elif message.type == gst.MESSAGE_ERROR:
                self.success = False
                self.done.set()

    def disconnect(self):
        self.bus.disconnect(self.watch_id)
        self.playbin.set_state(gst.STATE_NULL)
        del self.bus
        del self.playbin
        del self.audiosink
        del self.videosink


class Renderer:
    def __init__(self):
        logging.info("GStreamer version: %s", gst.version_string())
        self.playbin = gst.element_factory_make("playbin", "player")
        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.bus.enable_sync_message_emission()

        self.bus.connect("message::eos", self.on_bus_message)
        self.bus.connect("message::error", self.on_bus_message)
        self.bus.connect('sync-message::element', self.on_sync_message)

        videosink = config.get(options.GSTREAMER_IMAGESINK)
        try:
            self.sink = gst.element_factory_make(videosink, "sink")

        except gst.ElementNotFoundError:
            logging.info("gstreamerrenderer: ElementNotFoundError '%s'" % videosink)
            videosink = "ximagesink"
            self.sink = gst.element_factory_make(videosink, "sink")

        except Exception, e:
            logging.info("gstreamerrenderer: Exception thrown '%s'" % e)
            logging.exception("sink exception")
            videosink = "ximagesink"
            self.sink = gst.element_factory_make(videosink, "sink")

        logging.info("GStreamer sink:    %s", videosink)
        self.playbin.set_property("video-sink", self.sink)
        self.set_visualization()

        self.rate = 1.0

    def set_visualization(self):
        value = config.get(options.VIZ_PLUGIN)

        if value == "goom":
            vis = gst.element_factory_make("goom", "goom")
        else:
            vis = None

        self.playbin.set_property("vis-plugin", vis)

    def change_visualization(self, value):
        # FIXME - this should switch between none and goom, but it doesn't work.
        pass

    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == 'prepare-xwindow-id':
            imagesink = message.src
            imagesink.set_property('force-aspect-ratio', True)
            imagesink.set_xwindow_id(self.widget.window.xid)

    def on_bus_message(self, bus, message):
        """recieves message posted on the GstBus"""
        if message.type == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            logging.error("on_bus_message: gstreamer error: %s", err)

        elif message.type == gst.MESSAGE_EOS:
            app.playback_manager.on_movie_finished()

    def set_widget(self, widget):
        widget.connect_after("realize", self.on_realize)
        widget.connect("unrealize", self.on_unrealize)
        widget.connect("expose-event", self.on_expose)
        self.widget = widget

    def on_realize(self, widget):
        self.gc = widget.window.new_gc()
        self.gc.foreground = gtk.gdk.color_parse("black")

    def on_unrealize(self, widget):
        self.playbin.set_state(gst.STATE_NULL)
        self.sink = None

    def on_expose(self, widget, event):
        if self.sink and hasattr(self.sink, "expose"):
            self.sink.expose()
        else:
            # if we had an image to show, we could do so here...  that image
            # would show for audio-only items.
            widget.window.draw_rectangle(self.gc,
                                         True,
                                         0, 0,
                                         widget.allocation.width,
                                         widget.allocation.height)
        return True

    def can_play_file(self, filename, yes_callback, no_callback):
        """whether or not this renderer can play this data"""
        return Tester(filename).result(yes_callback, no_callback)

    def fill_movie_data(self, filename, movie_data, callback):
        d = os.path.join(config.get(prefs.ICON_CACHE_DIRECTORY), "extracted")
        try:
            os.makedirs(d)
        except:
            pass
        screenshot = os.path.join(d, os.path.basename(filename) + ".png")
        movie_data["screenshot"] = nextFreeFilename(screenshot)

    def go_fullscreen(self):
        """Handle when the video window goes fullscreen."""
        logging.debug("haven't implemented go_fullscreen method yet!")

    def exit_fullscreen(self):
        """Handle when the video window exits fullscreen mode."""
        logging.debug("haven't implemented exit_fullscreen method yet!")

    def select_item(self, an_item):
        self.set_visualization()
        self.select_file(an_item.get_filename())

    def select_file(self, filename):
        """starts playing the specified file"""
        self.stop()
        self.set_visualization()
        self.playbin.set_property("uri", "file://%s" % filename)
        self.playbin.set_state(gst.STATE_PAUSED)

    def get_progress(self):
        logging.info("get_progress: what does this do?")

    def get_current_time(self):
        try:
            position, format = self.playbin.query_position(gst.FORMAT_TIME)
            return to_seconds(position)
        except Exception, e:
            logging.warn("get_current_time: caught exception: %s" % e)
            return None

    def __seek(self, seconds):
        # FIXME - switch to self.playbin.seek_simple ?
        #              self.player.seek_simple(self.time_format, gst.SEEK_FLAG_FLUSH, seek_ns)
        event = gst.event_new_seek(1.0,
                                   gst.FORMAT_TIME,
                                   gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
                                   gst.SEEK_TYPE_SET, from_seconds(seconds),
                                   gst.SEEK_TYPE_NONE, 0)
        result = self.playbin.send_event(event)
        if not result:
            logging.error("seek failed")

    def __on_state_changed(self, bus, message, seconds):
        if self.playbin.get_state(0)[1] in (gst.STATE_PAUSED, gst.STATE_PLAYING):
            self.__seek(seconds)
            self.bus.disconnect(self.__on_state_changed_id)

    def set_current_time(self, seconds):
        # only want to kick these off when PAUSED or PLAYING
        if self.playbin.get_state(0)[1] not in (gst.STATE_PAUSED, gst.STATE_PLAYING):
            self.__on_state_changed_id = self.bus.connect("message::state-changed", self.__on_state_changed, seconds)
            return

        self.__seek(seconds)

    def get_duration(self):
        try:
            duration, format = self.playbin.query_duration(gst.FORMAT_TIME)
            return to_seconds(duration)
        except Exception, e:
            logging.warn("get_duration: caught exception: %s" % e)
            return None

    def reset(self):
        self.playbin.set_state(gst.STATE_NULL)

    def set_volume(self, level):
        self.playbin.set_property("volume", level * 4.0)

    def play(self):
        self.playbin.set_state(gst.STATE_PLAYING)

    def pause(self):
        self.playbin.set_state(gst.STATE_PAUSED)

    def stop(self):
        self.playbin.set_state(gst.STATE_NULL)

    def get_rate(self):
        return 256

    def set_rate(self, rate):
        if self.rate == rate:
            return
        self.rate = rate
        position = self.playbin.query_position(gst.FORMAT_TIME, None)[0]
        if rate >= 0:
            self.playbin.seek(rate, 
                gst.FORMAT_TIME, 
                gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_KEY_UNIT,
                gst.SEEK_TYPE_SET,
                position + (rate * gst.SECOND),
                gst.SEEK_TYPE_SET, 
                -1)
        else:
            self.playbin.seek(rate,
                gst.FORMAT_TIME, 
                gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_KEY_UNIT,
                gst.SEEK_TYPE_SET, 
                0,
                gst.SEEK_TYPE_SET,
                position + (rate * gst.SECOND))
 
    def movie_data_program_info(self, movie_path, thumbnail_path):
        return (("python", 'plat/renderers/gst_extractor.py', movie_path, thumbnail_path), None)
