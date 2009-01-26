# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

import pygtk
import gtk
import gobject

import pygst
pygst.require('0.10')
import gst
import gst.interfaces

import sys

class Extractor:
    def __init__(self, filename, thumbnail_filename, callback):
#        print "__init__(%s, %s, %s)" % (filename, thumbnail_filename, callback)
        self.thumbnail_filename = thumbnail_filename
        self.filename = filename
        self.callback = callback

        self.grabit = False
        self.first_pause = True
        self.success = False
        self.duration = -1
        self.buffer_probes = {}
        self.audio_only = False

        self.pipeline = gst.parse_launch('filesrc location="%s" ! decodebin ! ffmpegcolorspace ! video/x-raw-rgb,depth=24,bpp=24 ! fakesink signal-handoffs=True' % (filename,))

        for sink in self.pipeline.sinks():
            name = sink.get_name()
            factoryname = sink.get_factory().get_name()
            if factoryname == "fakesink":
                pad = sink.get_pad("sink")
                self.buffer_probes[name] = pad.add_buffer_probe(self.buffer_probe_handler, name)

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.watch_id = self.bus.connect("message", self.on_bus_message)

        self.pipeline.set_state(gst.STATE_PAUSED)

    def start_audio_only(self):
        self.audio_only = True

        self.pipeline = gst.parse_launch('filesrc location="%s" ! decodebin ! fakesink' % (self.filename,))

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.watch_id = self.bus.connect("message", self.on_bus_message)

        self.pipeline.set_state(gst.STATE_PAUSED)
            
    def done (self):
#        print "done()"
        self.callback(self.duration, self.success)

    def paused_reached(self):
#        print "paused_reached()"
        if self.audio_only:
            self.duration = self.pipeline.query_duration(gst.FORMAT_TIME)[0]
            self.success = True
            self.disconnect()
            self.done()
        if self.first_pause:
            self.duration = self.pipeline.query_duration(gst.FORMAT_TIME)[0]
            self.grabit = True
            seek_result = self.pipeline.seek(1.0,
                    gst.FORMAT_TIME,
                    gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
                    gst.SEEK_TYPE_SET,
                    self.duration / 2,
                    gst.SEEK_TYPE_NONE, 0)
            if not seek_result:
                self.disconnect()
                self.done()
        self.first_pause = False
        return False

    def error_occurred(self):
        self.disconnect()
        if self.audio_only:
            self.done()
        else:
            self.start_audio_only()
        return False

    def on_bus_message(self, bus, message):
        if message.src == self.pipeline:
            if message.type == gst.MESSAGE_STATE_CHANGED:
                prev, new, pending = message.parse_state_changed()
                if new == gst.STATE_PAUSED:
                    gobject.idle_add(self.paused_reached)
        if message.type == gst.MESSAGE_ERROR:
            gobject.idle_add(self.error_occurred)

    def buffer_probe_handler_real(self, pad, buff, name):
        """Capture buffers as gdk_pixbufs when told to."""
        if self.grabit:
            caps = buff.caps
            if caps is not None:
                filters = caps[0]
                self.width = filters["width"]
                self.height = filters["height"]
            timecode = self.pipeline.query_position(gst.FORMAT_TIME)[0]
            pixbuf = gtk.gdk.pixbuf_new_from_data(buff.data, gtk.gdk.COLORSPACE_RGB, False, 8, self.width, self.height, self.width * 3)
            pixbuf.save(self.thumbnail_filename, "png")
            del pixbuf
            self.success = True
            self.disconnect()
            self.done()
        return False

    def buffer_probe_handler(self, pad, buff, name):
        gobject.idle_add(lambda: self.buffer_probe_handler_real(pad, buff, name))
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

def handle_result(duration, success):
    if duration != -1:
        print "Miro-Movie-Data-Length: %s" % (duration / 1000000)
    else:
        print "Miro-Movie-Data-Length: -1"
    if success:
        print "Miro-Movie-Data-Thumbnail: Success"
    else:
        print "Miro-Movie-Data-Thumbnail: Failure"
    sys.exit(0)

extractor = Extractor(sys.argv[1], sys.argv[2], handle_result)
gtk.gdk.threads_init()
gtk.main()
