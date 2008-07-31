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

import ctypes
import logging
import os

import gtk

from miro.plat import resources

# load the DLL
libvlc = ctypes.cdll.libvlc
# set up the function signatures
libvlc.libvlc_new.restype = ctypes.c_void_p
libvlc.libvlc_playlist_get_input.restype = ctypes.c_void_p
libvlc.libvlc_input_get_position.restype = ctypes.c_float
libvlc.libvlc_input_get_length.restype = ctypes.c_longlong

class VLCError(Exception):
    pass

class VLCException(ctypes.Structure):
    _fields_ = [
            ('code', ctypes.c_int),
            ('message', ctypes.c_char_p)
    ]

    def __init__(self):
        ctypes.Structure.__init__(self)
        libvlc.libvlc_exception_init(self.ref())

    def ref(self):
        return ctypes.byref(self)

    def check(self):
        if self.code:
            msg = self.message
            libvlc.libvlc_exception_clear(self.ref())
            raise VLCError(msg)

def make_string_list(args):
    ArgsArray = ctypes.c_char_p * len(args)
    return ArgsArray(*args)

class VLCRenderer:
    def __init__(self):
        logging.info("Initializing VLC")
        plugin_dir = os.path.join(resources.appRoot(), 'vlc-plugins')
        self.exc = VLCException()

        vlc_args = [
            "vlc", '--quiet', '--nostats', '--intf', 'dummy', 
            '--plugin-path', plugin_dir
        ]
        self.vlc = libvlc.libvlc_new(len(vlc_args),
                make_string_list(vlc_args), self.exc.ref())
        self.exc.check()

    def set_widget(self, widget):
        widget.connect("realize", self.on_realize)
        widget.connect("unrealize", self.on_unrealize)
        self.widget = widget
        if widget.flags() & gtk.REALIZED:
            # Check if the widget is already realized
            self.on_unrealize(widget)

    def on_realize(self, widget):
        hwnd = widget.window.handle
        libvlc.libvlc_video_set_parent(self.vlc, hwnd, self.exc.ref())
        self.exc.check()

    def on_unrealize(self, widget):
        libvlc.libvlc_video_set_parent(self.vlc, 0, self.exc.ref())
        self.exc.check()

    def can_play_file(self, filename):
        """whether or not this renderer can play this data"""
        return True

    def go_fullscreen(self):
        """Handle when the video window goes fullscreen."""
        logging.debug("haven't implemented go_fullscreen method yet!")

    def exit_fullscreen(self):
        """Handle when the video window exits fullscreen mode."""
        logging.debug("haven't implemented exit_fullscreen method yet!")

    def select_file(self, filename):
        """starts playing the specified file"""
        mrl = 'file://%s' % filename
        libvlc.libvlc_playlist_clear(self.vlc, self.exc.ref())
        self.exc.check()
        libvlc.libvlc_playlist_add(self.vlc, ctypes.c_char_p(mrl), self.exc.ref())
        self.exc.check()

    def play(self):
        libvlc.libvlc_playlist_play(self.vlc, 0, None, self.exc.ref())
        self.exc.check()

    def pause(self):
        libvlc.libvlc_playlist_pause(self.vlc, self.exc.ref())
        self.exc.check()

    def stop(self):
        libvlc.libvlc_playlist_stop(self.vlc, self.exc.ref())
        self.exc.check()

    def reset(self):
        libvlc.libvlc_playlist_stop(self.vlc, self.exc.ref())
        self.exc.check()
        libvlc.libvlc_playlist_clear(self.vlc, self.exc.ref())
        self.exc.check()

    def _get_input(self):
        input = libvlc.libvlc_playlist_get_input(self.vlc, self.exc.ref())
        self.exc.check()
        return input

    def get_current_time(self, callback):
        try:
            input = self._get_input()
            try:
                time = libvlc.libvlc_input_get_time(input, self.exc.ref())
                self.exc.check()
            finally:
                libvlc.libvlc_input_free(input)
        except VLCError, e:
            logging.warn("exception getting time: %s" % e)
            time = 0
        time = time / 1000.0

        if callback:
            callback(time)
        return time

    def set_current_time(self, seconds):
        self.seek(seconds)

    def seek(self, seconds):
        time = int(seconds * 1000)
        try:
            input = self._get_input()
            try:
                libvlc.libvlc_input_set_time(input, ctypes.c_longlong(time),
                        self.exc.ref())
                self.exc.check()
            finally:
                libvlc.libvlc_input_free(input)
        except VLCError, e:
            logging.warn("exception seeking: %s" % e)

    def get_duration(self, callback=None):
        try:
            input = self._get_input()
            try:
                duration = libvlc.libvlc_input_get_length(input, self.exc.ref())
                self.exc.check()
            finally:
                libvlc.libvlc_input_free(input)
        except VLCError, e:
            logging.warn("exception getting duration: %s" % e)
            duration = 0
        duration = duration / 1000.0

        if callback:
            callback(duration)
        return duration
