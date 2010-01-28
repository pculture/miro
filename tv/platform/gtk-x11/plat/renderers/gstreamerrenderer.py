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

import sys
import logging
import os
import thread
import shutil
from threading import Event

import pygst
pygst.require('0.10')
import gst
import gst.interfaces
import gtk

# not sure why this isn't in the gst module, but it's easy to define
GST_PLAY_FLAG_TEXT          = (1 << 2)

from miro import app
from miro import config
from miro import prefs
from miro.util import gather_subtitle_files
from miro.gtcache import gettext as _
from miro.plat import options
from miro import iso_639

from miro.frontends.widgets.gtk.threads import call_on_ui_thread

def to_seconds(t):
    return t / gst.SECOND

def from_seconds(s):
    return s * gst.SECOND

class Sniffer:
    """Determines whether a file is "audio", "video", or "unplayable".
    """
    def __init__(self, filename):
        self.done = Event()
        self.success = False

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

    def result(self, success_callback, error_callback):
        def _result():
            self.done.wait(1)
            if self.success:
                # -1 if None, 0 if yes
                current_video = self.playbin.get_property("current-video")
                current_audio = self.playbin.get_property("current-audio")

                if current_video == 0:
                    call_on_ui_thread(success_callback, "video")
                elif current_audio == 0:
                    call_on_ui_thread(success_callback, "audio")
                else:
                    call_on_ui_thread(success_callback, "unplayable")
            else:
                call_on_ui_thread(error_callback)
            self.disconnect()
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

        self.rate = 1.0
        self.select_callbacks = None

        audiosink = config.get(options.GSTREAMER_AUDIOSINK)
        try:
            self.audiosink = gst.element_factory_make(audiosink, "audiosink")

        except gst.ElementNotFoundError:
            logging.info("gstreamerrenderer: ElementNotFoundError '%s'",
                         audiosink)
            audiosink = "autoaudiosink"
            self.audiosink = gst.element_factory_make(audiosink, "audiosink")

        except Exception, e:
            logging.info("gstreamerrenderer: Exception thrown '%s'" % e)
            logging.exception("sink exception")
            audiosink = "alsasink"
            self.audiosink = gst.element_factory_make(audiosink, "audiosink")

        logging.info("GStreamer audiosink: %s", audiosink)

        self.playbin = None
        self.bus = None
        self.watch_ids = []

    def build_playbin(self):
        self.playbin = gst.element_factory_make("playbin2", "player")
        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.bus.enable_sync_message_emission()

        self.watch_ids.append(self.bus.connect("message", self.on_bus_message))
        self.playbin.set_property("audio-sink", self.audiosink)

    def destroy_playbin(self):
        if self.playbin is None:
            return
        for watch_id in self.watch_ids:
            self.bus.disconnect(watch_id)
        self.watch_ids = []
        self.bus = None
        self.playbin = None

    def on_bus_message(self, bus, message):
        """receives message posted on the GstBus"""
        if message.src is not self.playbin:
            return

        if message.type == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            if self.select_callbacks is not None:
                self.select_callbacks[1]()
                self.select_callbacks = None
                logging.error("on_bus_message: gstreamer error: %s", err)
            else:
                err, debug = message.parse_error()
                logging.error("on_bus_message: gstreamer error: %s", err)
        elif message.type == gst.MESSAGE_STATE_CHANGED:
            prev, new, pending = message.parse_state_changed()
            if ((new == gst.STATE_PAUSED
                 and self.select_callbacks is not None)):
                self.select_callbacks[0]()
                self.select_callbacks = None
                self.finish_select_file()
        elif message.type == gst.MESSAGE_EOS:
            app.playback_manager.on_movie_finished()

    def select_file(self, iteminfo, callback, errback, sub_filename=""):
        """starts playing the specified file"""
        self.stop()
        self.destroy_playbin()
        self.build_playbin()
        self.enabled_track = None

        self.iteminfo = iteminfo

        self.select_callbacks = (callback, errback)
        self.playbin.set_property("uri", "file://%s" % iteminfo.video_path)
        if sub_filename:
            self.playbin.set_property("suburi", "file://%s" % sub_filename)
        else:
            self.playbin.set_property("suburi", None)
        self.playbin.set_state(gst.STATE_PAUSED)

    def finish_select_file(self):
        pass

    def get_current_time(self, attempt=0):
        # query_position fails periodically, so this attempts it 5 times
        # and if after that it fails, then we return 0.
        if attempt == 5:
            return 0
        try:
            position, fmt = self.playbin.query_position(gst.FORMAT_TIME)
            return to_seconds(position)
        except gst.QueryError, qe:
            logging.warn("get_current_time: caught exception: %s" % qe)
            return self.get_current_time(attempt + 1)

    def _seek(self, seconds):
        event = gst.event_new_seek(1.0,
                                   gst.FORMAT_TIME,
                                   gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
                                   gst.SEEK_TYPE_SET, from_seconds(seconds),
                                   gst.SEEK_TYPE_NONE, 0)
        result = self.playbin.send_event(event)
        if not result:
            logging.error("seek failed")

    def _set_current_time_actual(self, bus, message, seconds):
        if self.playbin.get_state(0)[1] in (gst.STATE_PAUSED,
                                            gst.STATE_PLAYING):
            self._seek(seconds)
            self.bus.disconnect(self._set_current_time_actual_id)

    def set_current_time(self, seconds):
        # only want to kick these off when PAUSED or PLAYING
        if self.playbin.get_state(0)[1] not in (gst.STATE_PAUSED,
                                                gst.STATE_PLAYING):
            self._set_current_time_actual_id = self.bus.connect(
                "message::state-changed",
                self._set_current_time_actual,
                seconds)
            return

        self._seek(seconds)

    def get_duration(self):
        try:
            duration, fmt = self.playbin.query_duration(gst.FORMAT_TIME)
            return to_seconds(duration)
        except gst.QueryError, qe:
            logging.warn("get_duration: caught exception: %s" % qe)
            return None

    def reset(self):
        if self.playbin:
            self.playbin.set_state(gst.STATE_NULL)
            self.destroy_playbin()

    def set_volume(self, level):
        self.playbin.set_property("volume", level)

    def play(self):
        self.playbin.set_state(gst.STATE_PLAYING)

    def pause(self):
        self.playbin.set_state(gst.STATE_PAUSED)

    def stop(self):
        if self.playbin:
            self.playbin.set_state(gst.STATE_NULL)
            self.destroy_playbin()

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

class AudioRenderer(Renderer):
    pass

class VideoRenderer(Renderer):
    def __init__(self):
        Renderer.__init__(self)

        videosink = config.get(options.GSTREAMER_IMAGESINK)
        try:
            self.videosink = gst.element_factory_make(videosink, "videosink")

        except gst.ElementNotFoundError:
            logging.info("gstreamerrenderer: ElementNotFoundError '%s'",
                         videosink)
            videosink = "xvimagesink"
            self.videosink = gst.element_factory_make(videosink, "videosink")

        except Exception, e:
            logging.info("gstreamerrenderer: Exception thrown '%s'" % e)
            logging.exception("sink exception")
            videosink = "ximagesink"
            self.videosink = gst.element_factory_make(videosink, "videosink")

        logging.info("GStreamer videosink: %s", videosink)
        self.textsink = gst.element_factory_make("textoverlay", "textsink")

    def build_playbin(self):
        Renderer.build_playbin(self)
        self.watch_ids.append(self.bus.connect('sync-message::element', self.on_sync_message))
        self.playbin.set_property("video-sink", self.videosink)
        self.playbin.set_property("text-sink", self.textsink)

    def select_file(self, filename, callback, errback, sub_filename=""):
        Renderer.select_file(self, filename, callback, errback, sub_filename)
        if sub_filename != "":
            self.pick_subtitle_track = 0

    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == 'prepare-xwindow-id':
            imagesink = message.src
            imagesink.set_property('force-aspect-ratio', True)
            imagesink.set_xwindow_id(self.widget.persistent_window.xid)

    def set_widget(self, widget):
        widget.connect("destroy", self.on_destroy)
        widget.connect("expose-event", self.on_expose)
        self.widget = widget
        self.gc = widget.persistent_window.new_gc()
        self.gc.foreground = gtk.gdk.color_parse("black")

    def on_destroy(self, widget):
        if self.playbin:
            self.playbin.set_state(gst.STATE_NULL)

    def on_expose(self, widget, event):
        if self.videosink and hasattr(self.videosink, "expose"):
            self.videosink.expose()
        else:
            # if we had an image to show, we could do so here...  that image
            # would show for audio-only items.
            widget.window.draw_rectangle(self.gc,
                                         True,
                                         0, 0,
                                         widget.allocation.width,
                                         widget.allocation.height)
        return True

    def go_fullscreen(self):
        """Handle when the video window goes fullscreen."""
        logging.debug("haven't implemented go_fullscreen method yet!")

    def exit_fullscreen(self):
        """Handle when the video window exits fullscreen mode."""
        logging.debug("haven't implemented exit_fullscreen method yet!")

    def finish_select_file(self):
        Renderer.finish_select_file(self)
        if hasattr(self, "pick_subtitle_track"):
            flags = self.playbin.get_property('flags')
            self.playbin.set_properties(flags=flags | GST_PLAY_FLAG_TEXT,
                                        current_text=0)
            del self.__dict__["pick_subtitle_track"]
            return

        if config.get(prefs.ENABLE_SUBTITLES):
            default_track = self.get_enabled_subtitle_track()
            if default_track is None:
                tracks = self.get_subtitle_tracks()
                if len(tracks) > 0:
                    self.enable_subtitle_track(0)

    def _get_subtitle_track_name(self, index):
        """Returns the language for the track at the specified index.
        """
        tag_list = self.playbin.emit("get-text-tags", index)
        lang = None
        if tag_list is not None and gst.TAG_LANGUAGE_CODE in tag_list:
            code = tag_list[gst.TAG_LANGUAGE_CODE]
            lang = iso_639.find(code, iso_639.THREE_LETTERS_CODE)
        if lang is None:
            return _("Unknown Language")
        else:
            return lang['name']

    def _get_subtitle_file_name(self, filename):
        """Returns the language for the file at the specified
        filename.
        """
        basename, ext = os.path.splitext(filename)
        movie_file, code = os.path.splitext(basename)

        # if the filename is like "foo.srt" and "srt", then there
        # is no language code, so we return None
        if not code:
            return None

        # remove . in the code so we end up with what's probably
        # a two or three letter language code
        if "." in code:
            code = code.replace(".", "")

        lang = iso_639.find(code, iso_639.THREE_LETTERS_CODE)
        if lang == None:
            lang = iso_639.find(code, iso_639.TWO_LETTERS_CODE)

        if lang is None:
            return _("Unknown Language")
        else:
            return lang['name']

    def get_subtitles(self):
        """Returns a dict of index -> (language, filename) for available
        tracks.
        """
        if not self.playbin:
            return {}

        tracks = {}

        for track_index in range(self.playbin.get_property("n-text")):
            tracks[track_index] = (self._get_subtitle_track_name(track_index),
                                   None)

        files = gather_subtitle_files(self.iteminfo.video_path)

        external_track_id = 100
        for i, mem in enumerate(files):
            tracks[external_track_id + i] = (self._get_subtitle_file_name(mem),
                                             mem)
        return tracks

    def get_subtitle_tracks(self):
        """Returns a 2-tuple of (index, language) for available
        tracks.
        """
        tracks = [(index, filename)
                  for index, (filename, language) in self.get_subtitles().items()]
        return tracks

    def get_enabled_subtitle_track(self):
        if self.enabled_track is not None:
            return self.enabled_track
        return self.playbin.get_property("current-text")

    def enable_subtitle_track(self, track_index):
        tracks = self.get_subtitles()
        if tracks.get(track_index) is None:
            return

        language, filename = tracks[track_index]

        if filename is not None:
            # file-based subtitle tracks have to get selected as files
            # first, then enable_subtitle_track gets called again with
            # the new track_index
            self.select_subtitle_file(self.iteminfo, filename)
            self.enabled_track = track_index
            return
        flags = self.playbin.get_property('flags')
        self.playbin.set_properties(flags=flags | GST_PLAY_FLAG_TEXT,
                                    current_text=track_index)

    def disable_subtitles(self):
        flags = self.playbin.get_property('flags')
        self.playbin.set_property('flags', flags & ~GST_PLAY_FLAG_TEXT)

    def select_subtitle_file(self, iteminfo, sub_path):
        current_time = self.get_current_time()
        total_time = self.get_duration()

        filenames = [filename for lang, filename in self.get_subtitles().values()]
        if sub_path not in filenames:
            dstname = os.path.splitext(iteminfo.video_path)[0]
            ext = os.path.splitext(sub_path)[1]
            dstpath = dstname + ".ex" + ext
            shutil.copyfile(sub_path, dstpath)
            sub_path = dstpath

        def handle_ok():
            app.playback_manager.emit('will-play', total_time)
            self.set_current_time(current_time)
            self.play()
            app.playback_manager.emit('did-start-playing')
        def handle_err():
            app.playback_manager.stop()
        app.playback_manager.emit('will-pause')
        self.select_file(iteminfo, handle_ok, handle_err, sub_path)

def movie_data_program_info(movie_path, thumbnail_path):
    extractor_path = os.path.join(os.path.split(__file__)[0],
                                  "gst_extractor.py")
    return ((sys.executable, extractor_path, movie_path, thumbnail_path), None)

def get_item_type(item_info, success_callback, error_callback):
    s = Sniffer(item_info.video_path)
    s.result(success_callback, error_callback)
