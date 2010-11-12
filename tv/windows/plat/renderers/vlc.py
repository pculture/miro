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

import ctypes
import logging
import os
import traceback
import urllib
import logging

import gtk
import gobject

from miro.gtcache import gettext as _
from miro.plat import resources
from miro import app
from miro import config
from miro import prefs
from miro.frontends.widgets import menus
from miro.frontends.widgets.widgetconst import MAX_VOLUME
from miro.util import copy_subtitle_file

# load the DLL
libvlc = ctypes.cdll.libvlc
libvlccore = ctypes.cdll.libvlccore

# Pick out functions that start with "__".  It's very awkward to use them
# inside classes.
vlc_object_release = libvlccore.__vlc_object_release

config_GetInt = libvlccore.__config_GetInt
config_PutInt = libvlccore.__config_PutInt
config_GetFloat = libvlccore.__config_GetFloat
config_PutFloat = libvlccore.__config_PutFloat
config_GetPsz = libvlccore.__config_GetPsz
config_PutPsz = libvlccore.__config_PutPsz


# set up the function signatures
libvlc_MediaStateChanged = 5

(libvlc_NothingSpecial,
 libvlc_Opening,
 libvlc_Buffering,
 libvlc_Playing,
 libvlc_Paused,
 libvlc_Stopped,
 libvlc_Ended,
 libvlc_Error) = range(8)

# Win32 Function
EnableWindow = ctypes.windll.user32.EnableWindow

class VLCError(Exception):
    pass

class VLCException(ctypes.Structure):
    _fields_ = [
            ('raised', ctypes.c_int),
            ('code', ctypes.c_int),
            ('message', ctypes.c_char_p)
    ]

    def __init__(self):
        ctypes.Structure.__init__(self)
        libvlc.libvlc_exception_init(self.ref())

    def ref(self):
        return ctypes.byref(self)

    def check(self):
        if self.raised:
            msg = self.message
            libvlc.libvlc_exception_clear(self.ref())
            raise VLCError(repr(self.code) + " " + repr(msg))

class VLCEvent(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_int),
        ('p_obj', ctypes.c_void_p),
        ('arg1', ctypes.c_int),
        ('arg2', ctypes.c_int),
    ]

class VLCTrackDescription(ctypes.Structure):
    # The libvlc_track_description_t structure type is
    # self-referencing so we have to specify the fields after the
    # class is defined.
    pass

VLCTrackDescription._fields_ = [
    ('id', ctypes.c_int),
    ('name', ctypes.c_char_p),
    ('next', ctypes.POINTER(VLCTrackDescription))
    ]

libvlc.libvlc_video_get_spu_description.restype = ctypes.POINTER(
    VLCTrackDescription)
libvlc.libvlc_video_get_track_description.restype = ctypes.POINTER(
    VLCTrackDescription)

VLC_EVENT_CALLBACK = ctypes.CFUNCTYPE(
    None, ctypes.POINTER(VLCEvent), ctypes.c_void_p)

def make_string_list(args):
    ArgsArray = ctypes.c_char_p * len(args)
    return ArgsArray(*args)

STOPPED, PAUSED, PLAYING = range(3)

class VLCSniffer(object):
    def __init__(self):
        plugin_dir = os.path.join(resources.appRoot(), 'vlc-plugins')
        self.exc = VLCException()

        # Note: if you need vlc output to stdout, remove the --quiet
        # from the list of arguments.  Also, you can add -vvv.
        vlc_args = [
            "vlc", '--quiet',
            '--nostats', '--intf', 'dummy', '--volume=0',
            '--no-video-title-show', '--plugin-path', plugin_dir
        ]
        self.vlc = libvlc.libvlc_new(
            len(vlc_args), make_string_list(vlc_args), self.exc.ref())
        self.exc.check()
        self.media_player = libvlc.libvlc_media_player_new(
            self.vlc, self.exc.ref())
        self.exc.check()
        self._callback_ref = VLC_EVENT_CALLBACK(self.event_callback)
        self._filename = None
        self.media_playing = None
        self.callback_info = None

        self._hidden_window = gtk.gdk.Window(
            None, x=0, y=0, width=1, height=1,
            window_type=gtk.gdk.WINDOW_TOPLEVEL,
            wclass=gtk.gdk.INPUT_OUTPUT, event_mask=0)
        libvlc.libvlc_media_player_set_hwnd(
            self.media_player, self._hidden_window.handle, self.exc.ref())
        self.exc.check()

    def shutdown(self):
        logging.info("shutting down VLC Sniffer")
        libvlc.libvlc_media_player_release(self.media_player)
        libvlc.libvlc_release(self.vlc)

    def event_callback(self, p_event, p_user_data):
        event = p_event[0]
        # Copy the values from event, the memory might be freed by the
        # time handle_event gets called.
        obj = event.p_obj
        type_ = event.type
        arg1 = event.arg1
        arg2 = event.arg2
        gobject.idle_add(self.handle_event, obj, type_, arg1, arg2)

    def handle_event(self, obj, type_, state, arg2):
        if type_ != libvlc_MediaStateChanged:
            return 
        if obj != self.media_playing:
            return
        if self.callback_info is None:
            # We the video has already been opened (successfully or
            # not)
            if state == libvlc_Ended:
                app.playback_manager.on_movie_finished()

        else:
            # We are waiting to see if the video opens successfully
            if state in (libvlc_Error, libvlc_Ended):
                self._open_failure()
            elif state == libvlc_Playing:
                libvlc.libvlc_media_player_pause(
                    self.media_player, self.exc.ref())
                self.exc.check()
                self._open_success()

    def _open_success(self):
        # FIXME - sometimes _open_success is called, but callback_info
        # is None.  not sure why this happens.
        item_type = "failure"
        if self.callback_info:
            video_tracks = libvlc.libvlc_video_get_track_count(
                self.media_player, self.exc.ref())
            try:
                self.exc.check()
            except VLCError:
                video_tracks = 0
            audio_tracks = libvlc.libvlc_audio_get_track_count(
                self.media_player, self.exc.ref())
            try:
                self.exc.check()
            except VLCError:
                audio_tracks = 0

            if video_tracks > 0:
                item_type = "video"
            elif audio_tracks > 0:
                item_type = "audio"
            else:
                item_type = "unplayable"
        try:
            libvlc.libvlc_media_player_stop(self.media_player, self.exc.ref())
            self.exc.check()
        except VLCError, vlce:
            logging.warning("sniffer reset failed: %s", vlce)
        self.callback_info[0](item_type)
        self.callback_info = None
        self.media_playing = None

    def _open_failure(self):
        try:
            libvlc.libvlc_media_player_stop(self.media_player, self.exc.ref())
            self.exc.check()
        except VLCError, vlce:
            logging.warning("sniffer reset failed: %s", vlce)
        self.callback_info[1]()
        self.callback_info = None
        self.media_playing = None

    def select_file(self, iteminfo, success_callback, error_callback):
        """starts playing the specified file"""
        filename = iteminfo.video_path

        # filenames coming in are unicode objects, VLC expects utf-8
        # strings.
        filename = filename.encode('utf-8')
        self._filename = filename
        self.callback_info = (success_callback, error_callback)
        self.play_state = STOPPED

        media = libvlc.libvlc_media_new(self.vlc, ctypes.c_char_p(filename),
                self.exc.ref())
        self.exc.check()
        if media is None:
            raise AssertionError(
                "libvlc_media_new returned NULL for %s" % filename)
        event_manager = libvlc.libvlc_media_event_manager(media, 
                                                          self.exc.ref())
        self.exc.check()
        libvlc.libvlc_event_attach(event_manager, 
                                   libvlc_MediaStateChanged,
                                   self._callback_ref, 
                                   None, 
                                   self.exc.ref())
        self.exc.check()
        try:
            libvlc.libvlc_media_player_set_media(self.media_player, 
                                                 media,
                                                 self.exc.ref())
            self.exc.check()
        finally:
            libvlc.libvlc_media_release(media)
        self.media_playing = media
        # We want to load the media to test if we can play it.  The
        # best way that I can see to do that is to play it, then pause
        # once we see it's opened in the event_callack method.
        libvlc.libvlc_media_player_play(self.media_player, self.exc.ref())
        self.exc.check()

        libvlc.libvlc_media_player_pause(self.media_player, self.exc.ref())
        self.exc.check()

class VLCRenderer(object):
    def __init__(self):
        logging.info("Initializing VLC")
        plugin_dir = os.path.join(resources.appRoot(), 'vlc-plugins')
        self.exc = VLCException()

        # Note: if you need vlc output to stdout, remove the --quiet
        # from the list of arguments.
        vlc_args = [
            "vlc", '--quiet', '--nostats', '--intf', 'dummy',
            '--no-video-title-show', '--plugin-path', plugin_dir
        ]
        self.vlc = libvlc.libvlc_new(len(vlc_args),
                make_string_list(vlc_args), self.exc.ref())
        self.exc.check()
        self.vlc_instance = libvlc.libvlc_get_vlc_instance(self.vlc)
        self.media_player = libvlc.libvlc_media_player_new(self.vlc,
                self.exc.ref())
        self.exc.check()
        self._callback_ref = VLC_EVENT_CALLBACK(self.event_callback)
        self.play_from_time = None
        self.play_state = STOPPED
        self._duration = None
        self._filename = None
        self._rate = 1.0
        self.media_playing = None
        self.callback_info = None
        self._change_subtitle_timout = None
        self.subtitle_info = []
        self._hidden_window = gtk.gdk.Window(
            None, x=0, y=0, width=1, height=1,
            window_type=gtk.gdk.WINDOW_TOPLEVEL,
            wclass=gtk.gdk.INPUT_OUTPUT, event_mask=0)
        self.unset_widget()

    def shutdown(self):
        logging.info("shutting down VLC")
        self.reset()
        libvlc.libvlc_media_player_release(self.media_player)
        vlc_object_release(self.vlc_instance)
        libvlc.libvlc_release(self.vlc)
        _sniffer.shutdown()

    def event_callback(self, p_event, p_user_data):
        event = p_event[0]
        # Copy the values from event, the memory might be freed by the
        # time handle_event gets called.
        obj = event.p_obj
        type_ = event.type
        arg1 = event.arg1
        arg2 = event.arg2
        gobject.idle_add(self.handle_event, obj, type_, arg1, arg2)

    def handle_event(self, obj, type_, arg1, arg2):
        if type_ == libvlc_MediaStateChanged:
            self._handle_state_change(obj, arg1)
        else:
            logging.warn("Unknown VLC event type: %s", type_)

    def _handle_state_change(self, obj, state):
        if obj != self.media_playing:
            return
        if self.callback_info is None:
            # We the video has already been opened (successfully or
            # not)
            if state == libvlc_Ended:
                app.playback_manager.on_movie_finished()

        else:
            # We are waiting to see if the video opens successfully
            if state in (libvlc_Error, libvlc_Ended):
                self._open_failure()
            elif state == libvlc_Playing:
                libvlc.libvlc_media_player_pause(self.media_player,
                        self.exc.ref())
                self.exc.check()
                self._length_check()

    def _length_check(self, attempt=0):
        # sometimes garbage data will appear to open, but it VLC won't
        # actually play anything.  Use the length to double check that
        # we actually will play.  We try three attempts because
        # sometimes it takes a bit to figure out the length.
        if attempt > 3:
            self._open_failure()
            return
        if self._file_type != 'video':
            # for items the user has marked as audio, disable video
            # output #12692
            self._disable_video()

        length = libvlc.libvlc_media_player_get_length(
            self.media_player, self.exc.ref())
        self.exc.check()

        if length > 0:
            self._open_success()
        else:
            gobject.timeout_add(500, self._length_check, attempt+1)

    def _open_success(self):
        # FIXME - sometimes _open_success is called, but callback_info
        # is None.  not sure why this happens.
        self.setup_subtitles()
        if self.callback_info:
            self.callback_info[0]()
        self.callback_info = None

    def _open_failure(self):
        logging.info("_open_failure\n%s", "".join(traceback.format_stack()))
        self.callback_info[1]()
        self.callback_info = None
        self.media_playing = None

    def _disable_video(self):
        desc = libvlc.libvlc_video_get_track_description(
                self.media_player, self.exc.ref())
        self.exc.check()
        # the 1st description should be "Disable"
        if desc:
            track_id = desc.contents.id
            libvlc.libvlc_track_description_release(desc)
            libvlc.libvlc_video_set_track(self.media_player, track_id,
                    self.exc.ref())
            self.exc.check()

    def set_widget(self, widget):
        hwnd = widget.persistent_window.handle
        libvlc.libvlc_media_player_set_hwnd(self.media_player, hwnd,
                                                self.exc.ref())
        self.exc.check()

        widget.add_events(gtk.gdk.EXPOSURE_MASK)
        widget.connect('expose-event', self._on_expose)
        EnableWindow(hwnd, 0)

    def unset_widget(self):
        libvlc.libvlc_media_player_set_hwnd(
            self.media_player, self._hidden_window.handle, self.exc.ref())
        self.exc.check()

    def _on_expose(self, widget, event):
        gc = widget.style.black_gc
        widget.persistent_window.draw_rectangle(
            gc, True, event.area.x, event.area.y, 
            event.area.width, event.area.height)

    def select_file(self, iteminfo, callback, errback):
        """starts playing the specified file"""
        filename = iteminfo.video_path

        # filenames coming in are unicode objects, VLC expects utf-8
        # strings.
        filename = filename.encode('utf-8')
        self._filename = filename
        self._file_type = iteminfo.file_type
        self.subtitle_info = []
        self.callback_info = (callback, errback)
        self.play_from_time = None
        self.play_state = STOPPED

        media = libvlc.libvlc_media_new(self.vlc, ctypes.c_char_p(filename),
                                        self.exc.ref())
        self.exc.check()
        if media is None:
            raise AssertionError(
                "libvlc_media_new returned NULL for %s" % filename)
        event_manager = libvlc.libvlc_media_event_manager(media, 
                                                          self.exc.ref())
        self.exc.check()
        libvlc.libvlc_event_attach(event_manager, libvlc_MediaStateChanged,
                                   self._callback_ref, None, self.exc.ref())
        self.exc.check()
        try:
            libvlc.libvlc_media_player_set_media(self.media_player, media,
                                                 self.exc.ref())
            self.exc.check()
        finally:
            libvlc.libvlc_media_release(media)
        self.media_playing = media
        self.setup_subtitle_font()
        # We want to load the media to test if we can play it.  The
        # best way that I can see to do that is to play it, then pause
        # once we see it's opened in the event_callack method.
        libvlc.libvlc_media_player_play(self.media_player, self.exc.ref())
        self.exc.check()
        # For unknown reasons, sometimes we don't see the state
        # changed event if they happen quickly enough.  To work around
        # that, check the initial state of the media player.
        state = libvlc.libvlc_media_player_get_state(self.media_player,
                self.exc.ref())
        self.exc.check()
        self._handle_state_change(self.media_playing, state)

    def play(self):
        if self.play_state == PLAYING:
            return
        libvlc.libvlc_media_player_play(self.media_player, self.exc.ref())
        self.exc.check()
        self.play_state = PLAYING
        if self.play_from_time is not None:
            self.set_current_time(self.play_from_time)
            self.play_from_time = None

    def pause(self):
        if self.play_state == PAUSED:
            return
        libvlc.libvlc_media_player_pause(self.media_player, self.exc.ref())
        self.exc.check()
        self.play_state = PAUSED

    def stop(self):
        if self.play_state == STOPPED:
            return
        self.callback_info = None
        self.media_playing = None
        libvlc.libvlc_media_player_stop(self.media_player, self.exc.ref())
        self.exc.check()
        self.play_state = STOPPED
        self.subtitle_info = []

    def reset(self):
        self.stop()
        self.play_from_time = None
        self.play_state = STOPPED

    def get_current_time(self):
        t = libvlc.libvlc_media_player_get_time(
            self.media_player, self.exc.ref())
        try:
            self.exc.check()
        except VLCError, e:
            logging.warn("exception getting time: %s" % e)
            return None

        return t / 1000.0

    def set_current_time(self, seconds):
        if not self.play_state == PLAYING:
            self.play_from_time = seconds
            return
        t = int(seconds * 1000)
        if t == 0:
            # I have no clue why this this is, but setting time=1
            # (1/1000th of a second) fixes #15079
            t = 1
        libvlc.libvlc_media_player_set_time(
            self.media_player, ctypes.c_longlong(t), self.exc.ref())
        try:
            self.exc.check()
        except VLCError, e:
            logging.warn("exception setting current time %s" % e)

    def get_duration(self):
        # self._duration = (filename, duration)
        if self._duration and self._duration[0] == self._filename:
            return self._duration[1]

        length = libvlc.libvlc_media_player_get_length(
            self.media_player, self.exc.ref())
        try:
            self.exc.check()
        except VLCError, e:
            logging.warn("exception getting duration: %s" % e)
            return None

        self._duration = (self._filename, length / 1000.0)
        return self._duration[1]

    def set_volume(self, volume):
        volume = int(200 * volume / MAX_VOLUME)
        libvlc.libvlc_audio_set_volume(self.vlc, volume, self.exc.ref())
        self.exc.check()

    def get_volume(self, volume):
        rv = libvlc.libvlc_audio_get_volume(self.vlc, self.exc.ref())
        self.exc.check()
        return rv / 100.0

    def set_rate(self, rate):
        logging.info("set_rate: rate %s", rate)
        if self._rate == rate:
            return
        self._rate = rate
        libvlc.libvlc_media_player_set_rate(self.media_player, 
                ctypes.c_float(rate), self.exc.ref())
        try:
            self.exc.check()
        except VLCError, e:
            logging.warn("exception setting rate: %s" % e)
            return None

    def get_rate(self):
        pass

    def setup_subtitles(self):
        self.setup_subtitle_info()
        if config.get(prefs.ENABLE_SUBTITLES):
            track_index = self.get_enabled_subtitle_track()
            if track_index == 0:
                count = libvlc.libvlc_video_get_spu_count(
                    self.media_player, self.exc.ref())
                if count > 1:
                    self.enable_subtitle_track(1)
        else:
            self.disable_subtitles()

    def setup_subtitle_font(self):
        font_path = config.get(prefs.SUBTITLE_FONT)
        config_PutPsz(self.vlc_instance,
                ctypes.c_char_p('freetype-font'),
                ctypes.c_char_p(font_path))
        logging.info("Setting VLC subtitle font: %s", font_path)
        
    def get_subtitle_tracks(self):
        return self.subtitle_info

    def setup_subtitle_info(self):
        self.subtitle_info = list()
        try:
            desc = libvlc.libvlc_video_get_spu_description(
                self.media_player, self.exc.ref())
            self.exc.check()
            count = libvlc.libvlc_video_get_spu_count(
                self.media_player, self.exc.ref())
            self.exc.check()
            first_desc = desc
            for i in range(0, count):
                if i > 0: # track 0 is "disabled", don't include it
                    self.subtitle_info.append((i, desc.contents.name))
                desc = desc.contents.next
            libvlc.libvlc_track_description_release(first_desc)
        except VLCError, e:
            logging.warn("exception when getting list of subtitle tracks")

    def get_enabled_subtitle_track(self):
        track_index = libvlc.libvlc_video_get_spu(
            self.media_player, self.exc.ref())
        try:
            self.exc.check()
        except VLCError, e:
            logging.warn("exception when getting enabled subtitle track")
            return None
        return track_index

    def enable_subtitle_track(self, track_index):
        if self._change_subtitle_timout:
            gobject.source_remove(self._change_subtitle_timout)
            self._change_subtitle_timout = None
        self._set_active_subtitle_track(track_index)

    def disable_subtitles(self):
        self._set_active_subtitle_track(0)
        
    def _set_active_subtitle_track(self, track_index):
        count = libvlc.libvlc_video_get_spu_count(
            self.media_player, self.exc.ref())
        self.exc.check()

        # if we're disabling subtitles but there aren't any, we
        # just return
        if track_index == 0 and count == 0:
            return

        if track_index >= count:
            logging.warn("Subtitle track too high: %s (count: %s)",
                    track_index, count)

        libvlc.libvlc_video_set_spu(self.media_player, track_index, 
                                    self.exc.ref())
        try:
            self.exc.check()
        except VLCError, e:
            logging.warn("exception when setting subtitle track: %s", e)

    def select_subtitle_file(self, item, sub_path, handle_successful_select):
        try:
            sub_path = copy_subtitle_file(sub_path, item.video_path)
        except WindowsError:
            # FIXME - need a better way to deal with this.  when this
            # happens, then the subtitle file isn't in the right place
            # for VLC to pick it up on the next playback forcing the
            # user to select it again.
            # This is bug 12813.
            logging.exception("exception thrown when copying subtitle file")

        sub_path = sub_path.encode('utf-8')
        res = libvlc.libvlc_video_set_subtitle_file(
            self.media_player, ctypes.c_char_p(sub_path), self.exc.ref())
        try:
            self.exc.check()
        except VLCError, e:
            logging.warn("exception when setting subtitle track to file: %s", e)
        else:
            handle_successful_select()
            # 1 is the track of the external file, don't select it quite yet
            # because VLC might not be ready.  (#12858)
            self._change_subtitle_timout = gobject.timeout_add(100,
                    self.handle_change_subtitle_timout)

    def handle_change_subtitle_timout(self):
        self._change_subtitle_timout = None
        self.setup_subtitle_info()
        self.enable_subtitle_track(1)

    def select_subtitle_encoding(self, encoding):
        if self.media_playing is None:
            return
        if encoding is None:
            encoding = ''
        config_PutPsz(self.vlc_instance,
                ctypes.c_char_p('subsdec-encoding'),
                ctypes.c_char_p(encoding))
        logging.info("Setting VLC subtitle encoding: %s", encoding)

    def setup_subtitle_encoding_menu(self, menubar):
        menus.add_subtitle_encoding_menu(menubar, _('Eastern European'),
                ('Latin-7', _('Baltic')),
                ('Windows-1257', _('Baltic')),
                ('Latin-2', _('Eastern European')),
                ('Windows-1250', _('Eastern European')),
                ('KOI8-R', _('Russian')),
                ('Latin-10', _('South-Eastern European')),
                ('KOI8-U', _('Ukrainian')),
        )

        menus.add_subtitle_encoding_menu(menubar, _('Western European'),
                ('Latin-8', _('Celtic')),
                ('Windows-1252', _('Western European')),
                ('Latin-3', _('Esperanto')),
                ('ISO 8859-7', _('Greek')),
                ('Windows-1253', _('Greek')),
        )

        menus.add_subtitle_encoding_menu(menubar, _('East Asian'),
                ('GB18030', _('Universal Chinese')),
                ('ISO-2022-CN-EXT', _('Simplified Chinese')),
                ('EUC-CN', _('Simplified Chinese Unix')),
                ('7-bits JIS/ISO-2022-JP-2', _('Japanese')),
                ('EUC-JP', _('Japanese Unix')),
                ('Shift JIS', _('Japanese')),
                ('EUC-KR/CP949', _('Korean')),
                ('ISO-2022-KR', _('Korean')),
                ('Big5', _('Traditional Chinese')),
                ('EUC-TW', _('Traditional Chinese Unix')),
                ('HKSCS', _('Hong-Kong Supplementary')),
        )

        menus.add_subtitle_encoding_menu(menubar, _('SE and SW Asian'),
                ('ISO 8859-9', _('Turkish')),
                ('Windows-1254', _('Turkish')),
                ('Windows-874', _('Thai')),
                ('VISCII', _('Vietnamese')),
                ('Windows-1258', _('Vietnamese')),
        )

        menus.add_subtitle_encoding_menu(menubar, _('Middle Eastern'),
                ('ISO 8859-6', _('Arabic')),
                ('Windows-1256', _('Arabic')),
                ('ISO 8859-8', _('Hebrew')),
                ('Windows-1255', _('Hebrew')),
        )

        menus.add_subtitle_encoding_menu(menubar, _('Unicode'),
                ('UTF-8', _('Universal')),
                ('UTF-16', _('Universal')),
                ('UTF-16BE', _('Universal')),
                ('UTF-16LE', _('Universal')),
        )



_sniffer = VLCSniffer()

def get_item_type(item_info, success_callback, error_callback):
    _sniffer.select_file(item_info, success_callback, error_callback)
