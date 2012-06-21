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

"""gst.renderer -- Video and Audio renderer using gstremer
"""

import logging
import os

import gst
import gst.interfaces
import gtk

# not sure why this isn't in the gst module, but it's easy to define
GST_PLAY_FLAG_TEXT = (1 << 2)

from miro import app
from miro import prefs
from miro import util
from miro.gtcache import gettext as _
from miro.plat import options
from miro import iso639

from miro.frontends.widgets import menus
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets.gst import gstutil

class SinkFactory(object):
    """SinkFactory -- Create audio/video sinks for our renderer.

    SinkFactory an the interface that platforms must implement to use
    VideoRenderer and AudioRenderer.  It simple contains the logic to create
    the audiosink and videosink elements to give to gstreamer.

    When creating elements, SinkFactory can return anything that will work
    with playbin2.  Normally this means creating an element with
    gst.element_factory_make().  Howvever, if platforms need more complexity,
    they can chain elements together and return a gst.Bin that contains them.
    """

    def make_audiosink(self):
        """Create a gstreamer element to use as an audiosink.  """
        raise NotImplementedError()

    def make_videosink(self):
        """Create a gstreamer element to use as an audiosink.  """
        raise NotImplementedError()


class Renderer(object):
    def __init__(self, sink_factory):
        logging.info("GStreamer version: %s", gst.version_string())

        self.rate = 1.0
        self.select_callbacks = None
        self.sink_factory = sink_factory
        self.supports_subtitles = True
        self.playbin = None
        self.bus = None
        self.watch_ids = []
        self.enabled_track = None

    def build_playbin(self):
        self.playbin = gst.element_factory_make("playbin2", "player")
        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.bus.enable_sync_message_emission()

        self.watch_ids.append(self.bus.connect("message", self.on_bus_message))
        self.playbin.set_property("audio-sink",
                self.sink_factory.make_audiosink())

    def destroy_playbin(self):
        if self.playbin is None:
            return
        for watch_id in self.watch_ids:
            self.bus.disconnect(watch_id)
        self.watch_ids = []
        self.bus = None
        self.playbin = None

    def invoke_select_callback(self, success=False):
        if success:
            callback = self.select_callbacks[0]
        else:
            callback = self.select_callbacks[1]
        self.select_callbacks = None
        try:
            callback()
        except StandardError:
            logging.exception("Error calling renderer callback")

    def on_bus_message(self, bus, message):
        """receives message posted on the GstBus"""
        if message.src is not self.playbin:
            return

        if message.type == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            if self.select_callbacks is not None:
                self.invoke_select_callback(success=False)
                logging.error("on_bus_message: gstreamer error: %s", err)
            else:
                err, debug = message.parse_error()
                logging.error("on_bus_message (after callbacks): "
                              "gstreamer error: %s", err)
        elif message.type == gst.MESSAGE_STATE_CHANGED:
            prev, new, pending = message.parse_state_changed()
            if ((new == gst.STATE_PAUSED
                 and self.select_callbacks is not None)):
                self.invoke_select_callback(success=True)
                self.finish_select_file()
        elif message.type == gst.MESSAGE_EOS:
            app.playback_manager.on_movie_finished()

    def select_file(self, iteminfo, callback, errback):
        """starts playing the specified file"""
        self._setup_item(iteminfo)
        self.select_callbacks = (callback, errback)
        self.playbin.set_state(gst.STATE_PAUSED)

    def _setup_item(self, iteminfo):
        self.stop()
        self.destroy_playbin()
        self.build_playbin()
        self.enabled_track = None

        self.iteminfo = iteminfo
        self.playbin.set_property("uri",
                                  gstutil._get_file_url(iteminfo.filename))

    def finish_select_file(self):
        pass

    def get_current_time(self, attempt=0):
        # query_position fails periodically, so this attempts it 5 times
        # and if after that it fails, then we return 0.
        if not self.playbin or attempt == 5:
            return 0
        try:
            position, fmt = self.playbin.query_position(gst.FORMAT_TIME)
            return gstutil.to_seconds(position)
        except gst.QueryError, qe:
            logging.warn("get_current_time: caught exception: %s" % qe)
            return self.get_current_time(attempt + 1)

    def _seek(self, seconds):
        if not self.playbin:
            return
        event = gst.event_new_seek(
            1.0,
            gst.FORMAT_TIME,
            gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
            gst.SEEK_TYPE_SET, gstutil.from_seconds(seconds),
            gst.SEEK_TYPE_NONE, 0)
        result = self.playbin.send_event(event)
        if not result:
            logging.error("seek failed")

    def _set_current_time_actual(self, bus, message, seconds):
        if not self.playbin:
            return
        if self.playbin.get_state(0)[1] in (gst.STATE_PAUSED,
                                            gst.STATE_PLAYING):
            self._seek(seconds)
            self.bus.disconnect(self._set_current_time_actual_id)

    def set_current_time(self, seconds):
        if not self.playbin:
            return
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
        if not self.playbin:
            return None
        try:
            duration, fmt = self.playbin.query_duration(gst.FORMAT_TIME)
            return gstutil.to_seconds(duration)
        except gst.QueryError, qe:
            logging.warn("get_duration: caught exception: %s" % qe)
            return None

    def reset(self):
        if self.playbin:
            self.playbin.set_state(gst.STATE_NULL)
            self.destroy_playbin()

    def set_volume(self, level):
        if not self.playbin:
            return
        self.playbin.set_property("volume", level / widgetconst.MAX_VOLUME)

    def play(self):
        if not self.playbin:
            return
        self.playbin.set_state(gst.STATE_PLAYING)

    def pause(self):
        if not self.playbin:
            return
        self.playbin.set_state(gst.STATE_PAUSED)

    def stop(self):
        if self.playbin:
            self.reset()

    def get_rate(self):
        return 256

    def set_rate(self, rate):
        if not self.playbin or self.rate == rate:
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

    def get_audio_tracks(self):
        if not self.playbin:
            return 0
        return self.playbin.get_property('n-audio')

    def set_audio_track(self, track_index):
        if not self.playbin:
            return
        self.playbin.set_property('current-audio', track_index)

    def get_enabled_audio_track(self):
        if not self.playbin:
            return None
        return self.playbin.get_property('current-audio')

class AudioRenderer(Renderer):
    pass

class VideoRenderer(Renderer):
    def __init__(self, sink_factory):
        Renderer.__init__(self, sink_factory)

        self.textsink_name = "textoverlay"
        self.imagesink = None
        self.window_id = None
        self.config_cb_handle = None

    def build_playbin(self):
        Renderer.build_playbin(self)
        # imagesink gets set when we get the prepare-xwindow-id message
        self.imagesink = None
        self.watch_ids.append(self.bus.connect(
                'sync-message::element', self.on_sync_message))
        self.playbin.set_property("video-sink",
                self.sink_factory.make_videosink())
        try:
            textsink = gst.element_factory_make(
                self.textsink_name, "textsink")
            self.playbin.set_property("text-sink", textsink)
        except TypeError:
            logging.warning("this platform has an old version of "
                            "playbin2--no subtitle support.")
            self.supports_subtitles = False
        # setup subtitle fonts
        self.set_subtitle_font(app.config.get(prefs.SUBTITLE_FONT))
        self.connect_to_config_changed()

    def destroy_playbin(self):
        Renderer.destroy_playbin(self)
        self.imagesink = None
        self.disconnect_from_config_changed()

    def connect_to_config_changed(self):
        if self.config_cb_handle is None:
            self.config_cb_handle = app.frontend_config_watcher.connect(
                    'changed', self.on_config_changed)

    def disconnect_from_config_changed(self):
        if self.config_cb_handle is not None:
            app.frontend_config_watcher.disconnect(self.config_cb_handle)
            self.config_cb_handle = None

    def on_config_changed(self, obj, key, value):
        if key == prefs.SUBTITLE_FONT.key:
            self.set_subtitle_font(value)

    def set_subtitle_font(self, name):
        if not self.playbin:
            return
        self.playbin.set_property("subtitle-font-desc", name)

    def select_file(self, iteminfo, callback, errback, sub_filename=""):
        self._setup_item(iteminfo)
        self._setup_initial_subtitles(sub_filename)
        self.select_callbacks = (callback, errback)
        self.playbin.set_state(gst.STATE_PAUSED)

    def _setup_initial_subtitles(self, sub_filename):
        sub_index = -1
        if (app.config.get(prefs.ENABLE_SUBTITLES) and self.supports_subtitles
                and not sub_filename):
            tracks = self.get_subtitles()
            if 100 in tracks:  # Select default sidecar file
                sub_filename = tracks[100][1]
                sub_index = 0
                self.enabled_track = 100
            elif 0 in tracks:  # Select default embedded subtitle track
                sub_index = 0
                self.enabled_track = 0

        if sub_filename and self.playbin:
            self.playbin.set_property("suburi",
                    gstutil._get_file_url(sub_filename))
        if sub_index > -1:
            flags = self.playbin.get_property('flags')
            self.playbin.set_properties(flags=flags | GST_PLAY_FLAG_TEXT,
                                        current_text=sub_index)

    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == 'prepare-xwindow-id':
            self.imagesink = message.src
            self.imagesink.set_property('force-aspect-ratio', True)
            if self.window_id is not None:
                self.imagesink.set_xwindow_id(self.window_id)
            else:
                logging.warn("Got prepare-xwindow-id before "
                        "set_xwindow_id() called")

    def set_window_id(self, window_id):
        """Set the window id to render to

        window_id a value to pass into gstreamer's set_xwindow_id() method.
        On linux, it's an x window id, on windows it's an HWND
        """
        self.window_id = window_id

    def ready_for_expose(self):
        """Are we ready to handle an expose event?"""
        return self.imagesink and hasattr(self.imagesink, "expose")

    def expose(self):
        if self.ready_for_expose():
            self.imagesink.expose()

    def go_fullscreen(self):
        """Handle when the video window goes fullscreen."""
        logging.debug("haven't implemented go_fullscreen method yet!")

    def exit_fullscreen(self):
        """Handle when the video window exits fullscreen mode."""
        logging.debug("haven't implemented exit_fullscreen method yet!")

    def _get_subtitle_track_name(self, index):
        """Returns the language for the track at the specified index.
        """
        if not self.supports_subtitles or not self.playbin:
            return None
        tag_list = self.playbin.emit("get-text-tags", index)
        lang = None
        if tag_list is not None and gst.TAG_LANGUAGE_CODE in tag_list:
            code = tag_list[gst.TAG_LANGUAGE_CODE]
            lang = iso639.find(code)
        if lang is None:
            return None
        else:
            return lang['name']

    def _get_subtitle_file_name(self, filename):
        """Returns the language for the file at the specified
        filename.
        """
        if not self.supports_subtitles:
            return None
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

        lang = iso639.find(code)
        if lang is None:
            return None
        else:
            return lang['name']

    def get_subtitles(self):
        """Returns a dict of index -> (language, filename) for available
        tracks.
        """
        if not self.playbin or not self.supports_subtitles:
            return {}

        tracks = {}

        if self.playbin.get_property("suburi") is None:
            # Don't list subtitle tracks that we're getting from an SRT file
            for track_index in range(self.playbin.get_property("n-text")):
                track_name = self._get_subtitle_track_name(track_index)
                if track_name is None:
                    track_name = _("Track %(tracknumber)d",
                                   {"tracknumber": track_index})
                tracks[track_index] = (track_name, None)

        files = util.gather_subtitle_files(self.iteminfo.filename)

        external_track_id = 100
        for i, mem in enumerate(files):
            track_name = self._get_subtitle_file_name(mem)
            if track_name is None:
                track_name = _("Subtitle file %(tracknumber)d",
                               {"tracknumber": i})
            tracks[external_track_id + i] = (track_name, mem)

        return tracks

    def get_subtitle_tracks(self):
        """Returns a list of 2-tuple of (index, language) for
        available tracks.
        """
        if not self.supports_subtitles:
            return []
        tracks = [(index, filename)
                  for index, (filename, language)
                  in self.get_subtitles().items()]
        return tracks

    def get_enabled_subtitle_track(self):
        if not self.playbin:
            return None
        if not self.supports_subtitles:
            return None
        if self.enabled_track is not None:
            return self.enabled_track
        return self.playbin.get_property("current-text")

    def set_subtitle_track(self, track_index):
        if not self.supports_subtitles:
            return
        tracks = self.get_subtitles()
        if tracks.get(track_index) is None:
            return

        language, filename = tracks[track_index]

        if filename is not None:
            self.switch_subtitle_file(filename)
            self.enabled_track = track_index
            return
        flags = self.playbin.get_property('flags')
        self.playbin.set_properties(flags=flags | GST_PLAY_FLAG_TEXT,
                                    current_text=track_index)

    def switch_subtitle_file(self, filename):
        """Set our playbin to use a file to get subtitles from.

        :param filename: path to file or None to disable subtitle files
        """
        # file-based subtitle tracks have to get selected as files
        # first, then enable_subtitle_track gets called again with
        # the new track_index
        pos = self.get_current_time()

        # note: select_success needs to mirror what playback
        # manager does
        def select_success():
            self.set_current_time(pos)
            self.play()

        self.select_subtitle_file(self.iteminfo, filename, select_success)

    def disable_subtitles(self):
        if not self.supports_subtitles:
            return
        if self.playbin.get_property("suburi") is None:
            # playing embedded subtitles, we can just switch off the
            # PLAY_FLAG_TEXT property
            flags = self.playbin.get_property('flags')
            self.playbin.set_property('flags', flags & ~GST_PLAY_FLAG_TEXT)
        else:
            # playing subtitles from an external file, we have to jump through
            # some hoops to disable them.
            self.switch_subtitle_file(None)
        self.enabled_track = None

    def select_subtitle_file(self, iteminfo, sub_path,
                             handle_successful_select):
        if not self.supports_subtitles:
            return
        subtitle_encoding = self.playbin.get_property("subtitle-encoding")

        def handle_ok():
            self.playbin.set_property("subtitle-encoding", subtitle_encoding)
            handle_successful_select()

        def handle_err():
            app.playback_manager.stop()
        filenames = [filename
                     for lang, filename in self.get_subtitles().values()]
        if sub_path is not None and sub_path not in filenames:
            sub_path = util.copy_subtitle_file(sub_path, iteminfo.filename)
        self.select_file(iteminfo, handle_ok, handle_err, sub_path)

    def setup_subtitle_encoding_menu(self):
        app.menu_manager.add_subtitle_encoding_menu(_('Eastern European'),
                ("ISO-8859-4", _("Baltic")),
                ("ISO-8859-13", _("Baltic")),
                ("WINDOWS-1257", _("Baltic")),
                ("MAC_CROATIAN", _("Croatian")),
                ("ISO-8859-5", _("Cyrillic")),
                ("IBM855", _("Cyrillic")),
                ("ISO-IR-111", _("Cyrillic")),
                ("KOI8-R", _("Cyrillic")),
                ("MAC-CYRILLIC", _("Cyrillic")),
                ("WINDOWS-1251", _("Cyrillic")),
                ("CP866", _("Cyrillic/Russian")),
                ("MAC_UKRAINIAN", _("Cyrillic/Ukrainian")),
                ("KOI8-U", _("Cyrillic/Ukrainian")),
                ("ISO-8859-2", ("Central European")),
                ("IBM852", _("Central European")),
                ("MAC_CE", _("Central European")),
                ("WINDOWS-1250", _("Central European")),
                ("ISO-8859-16", _("Romanian")),
                ("MAC_ROMANIAN", _("Romanian")),
        )
        app.menu_manager.add_subtitle_encoding_menu(_('Western European'),
                ("ISO-8859-14", _("Celtic")),
                ("ISO-8859-7", _("Greek")),
                ("MAC_GREEK", _("Greek")),
                ("WINDOWS-1253", _("Greek")),
                ("MAC_ICELANDIC", _("Icelandic")),
                ("ISO-8859-10", _("Nordic")),
                ("ISO-8859-3", _("South European")),
                ("ISO-8859-1", _("Western")),
                ("ISO-8859-15", _("Western")),
                ("IBM850", _("Western")),
                ("MAC_ROMAN", _("Western")),
                ("WINDOWS-1252", _("Western")),
        )
        app.menu_manager.add_subtitle_encoding_menu(_('East Asian'),
                ("GB18030", _("Chinese Simplified")),
                ("GB2312", _("Chinese Simplified")),
                ("GBK", _("Chinese Simplified")),
                ("HZ", _("Chinese Simplified")),
                ("BIG5", _("Chinese Traditional")),
                ("BIG5-HKSCS", _("Chinese Traditional")),
                ("EUC-TW", _("Chinese Traditional")),
                ("EUC-JP", _("Japanese")),
                ("ISO2022JP", _("Japanese")),
                ("SHIFT-JIS", _("Japanese")),
                ("EUC-KR", _("Korean")),
                ("ISO2022KR", _("Korean")),
                ("JOHAB", _("Korean")),
                ("UHC", _("Korean")),
        )
        app.menu_manager.add_subtitle_encoding_menu(_('SE and SW Asian'),
                ("ARMSCII-8", _("Armenian")),
                ("GEORGIAN-PS", _("Georgian")),
                ("MAC_GUJARATI", _("Gujarati")),
                ("MAC_GURMUKHI", _("Gurmukhi")),
                ("MAC_DEVANAGARI", _("Hindi")),
                ("TIS-620", _("Thai")),
                ("ISO-8859-9", _("Turkish")),
                ("IBM857", _("Turkish")),
                ("MAC_TURKISH", _("Turkish")),
                ("WINDOWS-1254", _("Turkish")),
                ("TCVN", _("Vietnamese")),
                ("VISCII", _("Vietnamese")),
                ("WINDOWS-1258", _("Vietnamese")),
        )
        app.menu_manager.add_subtitle_encoding_menu(_('Middle Eastern'),
                ("ISO-8859-6", _("Arabic")),
                ("IBM864", _("Arabic")),
                ("MAC_ARABIC", _("Arabic")),
                ("WINDOWS-1256", _("Arabic")),
                ("ISO-8859-8-I", _("Hebrew")),
                ("IBM862", _("Hebrew")),
                ("MAC_HEBREW", _("Hebrew")),
                ("WINDOWS-1255", _("Hebrew")),
                ("ISO-8859-8", _("Hebrew Visual")),
                ("MAC_FARSI", _("Persian")),
        )
        app.menu_manager.add_subtitle_encoding_menu(_('Unicode'),
                ("UTF-7", _("Unicode")),
                ("UTF-8", _("Unicode")),
                ("UTF-16", _("Unicode")),
                ("UCS-2", _("Unicode")),
                ("UCS-4", _("Unicode")),
        )

    def select_subtitle_encoding(self, encoding):
        self.playbin.set_property("subtitle-encoding", encoding)
