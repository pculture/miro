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
import os
import urllib

import pygtk
import gtk
import gobject

import pygst
pygst.require('0.10')
import gst
import gst.interfaces

class Extractor:
    def __init__(self, filename, thumbnail_filename, callback):
        self.thumbnail_filename = thumbnail_filename
        self.filename = filename
        self.callback = callback

        self.grabit = False
        self.first_pause = True
        self.success = False
        self.duration = -1
        self.buffer_probes = {}
        self.audio_only = False
        self.saw_video_tag = self.saw_audio_tag = False

        self.pipeline = gst.element_factory_make('playbin')
        self.videosink = gst.element_factory_make("fakesink", "videosink")
        self.pipeline.set_property("video-sink", self.videosink)
        self.audiosink = gst.element_factory_make("fakesink", "audiosink")
        self.pipeline.set_property("audio-sink", self.audiosink)

        self.thumbnail_pipeline = None

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.watch_id = self.bus.connect("message", self.on_bus_message)

        self.pipeline.set_property("uri", "file://%s" % urllib.quote(filename))
        self.pipeline.set_state(gst.STATE_PAUSED)

    def on_bus_message(self, bus, message):
        if message.src == self.pipeline:
            if message.type == gst.MESSAGE_STATE_CHANGED:
                prev, new_, pending = message.parse_state_changed()
                if new_ == gst.STATE_PAUSED:
                    gobject.idle_add(self.paused_reached)

            elif message.type == gst.MESSAGE_ERROR:
                gobject.idle_add(self.error_occurred)

        elif message.src == self.thumbnail_pipeline:
            if message.type == gst.MESSAGE_STATE_CHANGED:
                prev, new_, pending = message.parse_state_changed()
                if new_ == gst.STATE_PAUSED:
                    for sink in self.thumbnail_pipeline.sinks():
                        name = sink.get_name()
                        factoryname = sink.get_factory().get_name()
                        if factoryname == "fakesink":
                            pad = sink.get_pad("sink")
                            self.buffer_probes[name] = pad.add_buffer_probe(
                                self.buffer_probe_handler, name)

                    seek_result = self.thumbnail_pipeline.seek(
                        1.0, gst.FORMAT_TIME,
                        gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
                        gst.SEEK_TYPE_SET, min(self.duration / 2, 20 * gst.SECOND),
                        gst.SEEK_TYPE_NONE, 0)

                    if not seek_result:
                        self.disconnect()
                        self.done()

            elif message.type == gst.MESSAGE_ERROR:
                gobject.idle_add(self.error_occurred)

    def done(self):
        if self.saw_video_tag:
            media_type = 'video'
        elif self.saw_audio_tag:
            media_type = 'audio'
        else:
            media_type = 'other'
        self.callback(self.duration, self.success, media_type)

    def get_duration(self, pipeline, attempts=0):
        if attempts == 5:
            return 0
        try:
            return pipeline.query_duration(gst.FORMAT_TIME)[0]
        except gst.QueryError:
            return self.get_duration(pipeline, attempts + 1)

    def paused_reached(self):
        self.saw_video_tag = False
        self.saw_audio_tag = False

        if not self.first_pause:
            return False

        self.first_pause = True
        current_video = self.pipeline.get_property("current-video")
        current_audio = self.pipeline.get_property("current-audio")

        if current_video == 0:
            self.saw_video_tag = True
        if current_audio == 0:
            self.saw_audio_tag = True

        if not self.saw_video_tag and self.saw_audio_tag:
            # audio only
            self.audio_only = True
            self.duration = self.get_duration(self.pipeline)
            self.success = True
            self.disconnect()
            self.done()
            return False

        if not self.saw_video_tag and not self.saw_audio_tag:
            # no audio and no video
            self.audio_only = False
            self.disconnect()
            self.done()
            return False

        self.duration = self.get_duration(self.pipeline)
        self.grabit = True
        self.buffer_probes = {}

        self.thumbnail_pipeline = gst.parse_launch(
            'filesrc location="%s" ! decodebin ! '
            'ffmpegcolorspace ! video/x-raw-rgb,depth=24,bpp=24 ! '
            'fakesink signal-handoffs=True' % self.filename)

        self.thumbnail_bus = self.thumbnail_pipeline.get_bus()
        self.thumbnail_bus.add_signal_watch()
        self.thumbnail_watch_id = self.thumbnail_bus.connect(
            "message", self.on_bus_message)

        self.thumbnail_pipeline.set_state(gst.STATE_PAUSED)
        return False

    def error_occurred(self):
        self.disconnect()
        self.done()
        return False

    def buffer_probe_handler_real(self, pad, buff, name):
        """Capture buffers as gdk_pixbufs when told to.
        """
        try:
            caps = buff.caps
            if caps is None:
                self.success = False
                self.disconnect()
                self.done()
                return False

            filters = caps[0]
            width = filters["width"]
            height = filters["height"]
            timecode = self.thumbnail_pipeline.query_position(gst.FORMAT_TIME)[0]
            pixbuf = gtk.gdk.pixbuf_new_from_data(
                buff.data, gtk.gdk.COLORSPACE_RGB, False, 8,
                width, height, width * 3)
            pixbuf.save(self.thumbnail_filename, "png")
            del pixbuf
            self.success = True
            self.disconnect()
            self.done()
        except gst.QueryError:
            pass
        return False

    def buffer_probe_handler(self, pad, buff, name):
        gobject.idle_add(
            lambda: self.buffer_probe_handler_real(pad, buff, name))
        return True

    def disconnect(self):
        if self.pipeline is not None:
            self.pipeline.set_state(gst.STATE_NULL)
            if not self.audio_only:
                for sink in self.pipeline.sinks():
                    name = sink.get_name()
                    factoryname = sink.get_factory().get_name()
                    if factoryname == "fakesink" :
                        pad = sink.get_pad("sink")
                        pad.remove_buffer_probe(self.buffer_probes[name])
                        del self.buffer_probes[name]
            self.pipeline = None

        if self.bus is not None:
            self.bus.disconnect(self.watch_id)
            self.bus = None

def make_verbose():
    import logging
    logging.basicConfig(level=logging.INFO)
    def wrap_func(func):
        def _wrap_func(*args, **kwargs):
            logging.info("calling %s (%s) (%s)",
                         func.__name__, repr(args), repr(kwargs))
            return func(*args, **kwargs)
        return _wrap_func

    for mem in dir(Extractor):
        fun = Extractor.__dict__[mem]
        if callable(fun):
            Extractor.__dict__[mem] = wrap_func(fun)

def handle_result(duration, success, media_type):
    if duration != -1:
        print "Miro-Movie-Data-Length: %s" % (duration / 1000000)
    else:
        print "Miro-Movie-Data-Length: -1"
    if success:
        print "Miro-Movie-Data-Thumbnail: Success"
    else:
        print "Miro-Movie-Data-Thumbnail: Failure"
    print "Miro-Movie-Data-Type: %s" % media_type
    sys.exit(0)

def main(argv):
    if "--verbose" in argv:
        make_verbose()
        argv.remove("--verbose")

    if len(argv) < 2:
        print "Syntax: gst_extractor.py <media-file> <path-to-thumbnail>"
        sys.exit(1)

    if len(argv) < 3:
        argv.append(os.path.join(os.path.dirname(__file__), "thumbnail.png"))

    extractor = Extractor(argv[1], argv[2], handle_result)
    gtk.gdk.threads_init()
    gtk.main()

if __name__ == "__main__":
    main(sys.argv)
