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

"""gst.sniffer -- Examine media files, without playing them
"""

import thread
from threading import Event

import gst
import gst.interfaces

from miro.frontends.widgets.gst import gstutil
from miro.plat.frontends.widgets.threads import call_on_ui_thread

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

        self.playbin.set_property("uri", gstutil._get_file_url(filename))
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

def get_item_type(item_info, success_callback, error_callback):
    s = Sniffer(item_info.filename)
    s.result(success_callback, error_callback)
