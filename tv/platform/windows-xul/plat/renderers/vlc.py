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

# These next three return libvlc_instance_t, libvlc_media_player_t and
# libvlc_media_t pointers, but we can fake it with void pointers
libvlc.libvlc_new.restype = ctypes.c_void_p
libvlc.libvlc_media_player_new.restype = ctypes.c_void_p
libvlc.libvlc_media_new.restype = ctypes.c_void_p
libvlc.libvlc_media_player_get_time.restype = ctypes.c_longlong
libvlc.libvlc_media_player_get_length.restype = ctypes.c_longlong

libvlc.libvlc_audio_set_volume.restype = None
libvlc.libvlc_exception_init.restype = None
libvlc.libvlc_exception_clear.restype = None
libvlc.libvlc_media_player_set_drawable.restype = None
libvlc.libvlc_media_player_stop.restype = None
libvlc.libvlc_media_player_set_time.restype = None
libvlc.libvlc_media_player_pause.restype = None
libvlc.libvlc_media_player_play.restype = None
libvlc.libvlc_media_release.restype = None
libvlc.libvlc_media_player_set_media.restype = None

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
            '--no-video-title-show', '--plugin-path', plugin_dir
        ]
        self.vlc = libvlc.libvlc_new(len(vlc_args),
                make_string_list(vlc_args), self.exc.ref())
        self.exc.check()
        self.media_player = libvlc.libvlc_media_player_new(self.vlc,
                self.exc.ref())
        self.exc.check()
        self.play_from_time = None
        self.started_playing = False

    def set_widget(self, widget):
        widget.connect("realize", self.on_realize)
        widget.connect("unrealize", self.on_unrealize)
        self.widget = widget
        if widget.flags() & gtk.REALIZED:
            # Check if the widget is already realized
            self.on_unrealize(widget)

    def on_realize(self, widget):
        hwnd = widget.window.handle
        libvlc.libvlc_media_player_set_drawable(self.media_player, hwnd, 
                self.exc.ref())
        self.exc.check()

    def on_unrealize(self, widget):
        self.reset()
        libvlc.libvlc_media_player_set_drawable(self.media_player, 0,
                self.exc.ref())
        self.exc.check()

    def can_play_file(self, filename):
        """whether or not this renderer can play this data"""
        return True

    def select_file(self, filename):
        """starts playing the specified file"""

        self.play_from_time = None
        self.started_playing = False

        mrl = 'file://%s' % filename
        media = libvlc.libvlc_media_new(self.vlc, ctypes.c_char_p(mrl),
                self.exc.ref())
        self.exc.check()
        if media is None:
            raise AssertionError("libvlc_media_new returned NULL for %s"
                    % filename)
        try:
            libvlc.libvlc_media_player_set_media(self.media_player, media,
                    self.exc.ref())
            self.exc.check()
        finally:
            libvlc.libvlc_media_release(media)

    def play(self):
        libvlc.libvlc_media_player_play(self.media_player, self.exc.ref())
        self.exc.check()
        self.started_playing = True
        if self.play_from_time is not None:
            self.set_current_time(self.play_from_time)
            self.play_from_time = None

    def pause(self):
        libvlc.libvlc_media_player_pause(self.media_player, self.exc.ref())
        self.exc.check()

    def stop(self):
        libvlc.libvlc_media_player_stop(self.media_player, self.exc.ref())
        self.exc.check()

    def reset(self):
        self.stop()
        self.play_from_time = None
        self.started_playing = False

    def get_current_time(self):
        time = libvlc.libvlc_media_player_get_time(self.media_player, self.exc.ref())
        try:
            self.exc.check()
        except VLCError, e:
            logging.warn("exception getting time: %s" % e)
            return None
        else:
            return time / 1000.0

    def set_current_time(self, seconds):
        if not self.started_playing:
            self.play_from_time = seconds
            return
        time = int(seconds * 1000)
        logging.warn('set time: %s %s' % (seconds, time))
        libvlc.libvlc_media_player_set_time(self.media_player,
                ctypes.c_longlong(time), self.exc.ref())
        self.exc.check()

    def get_duration(self):
        length = libvlc.libvlc_media_player_get_length(self.media_player,
                self.exc.ref())
        try:
            self.exc.check()
        except VLCError, e:
            logging.warn("exception getting time: %s" % e)
            return None
        else:
            return length / 1000.0

    def set_volume(self, volume):
        volume = int(volume * 100)
        libvlc.libvlc_audio_set_volume(self.vlc, volume, self.exc.ref())
        self.exc.check()

    def get_volume(self, volume):
        rv = libvlc.libvlc_audio_get_volume(self.vlc, self.exc.ref())
        self.exc.check()
        return rv / 100.0
