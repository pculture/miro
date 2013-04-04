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

import logging
import random

from miro import app
from miro import prefs
from miro import signals
from miro import messages
from miro import filetypes

from miro.gtcache import gettext as _
from miro.plat.frontends.widgets import timer
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets.displays import VideoDisplay
from miro.frontends.widgets import keyboard
from miro.frontends.widgets import dialogs
from miro.frontends.widgets.widgetstatestore import WidgetStateStore

class PlaybackManager (signals.SignalEmitter):
    
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.player = None
        self.video_display = None
        self.removing_video_display = False
        self.detached_window = None
        self.previous_left_width = 0
        self.previous_left_widget = None
        self.is_fullscreen = False
        self.is_playing = False
        self.is_playing_audio = False
        self.is_paused = False
        self.is_suspended = False
        self.shuffle = False
        self.repeat = WidgetStateStore.get_repeat_off() 
        self.open_finished = False
        self.open_successful = False
        self.playlist = None
        self.mark_as_watched_timeout = None
        self.update_timeout = None
        self.manual_item_list = None
        self.selected_tab_list = self.selected_tabs = None
        self.presentation_mode = 'fit-to-bounds'
        self.create_signal('will-start')
        self.create_signal('selecting-file')
        self.create_signal('playing-info-changed')
        self.create_signal('cant-play-file')
        self.create_signal('will-play')
        self.create_signal('did-start-playing')
        self.create_signal('will-play-attached')
        self.create_signal('will-play-detached')
        self.create_signal('will-pause')
        self.create_signal('will-stop')
        self.create_signal('did-stop')
        self.create_signal('will-fullscreen')
        self.create_signal('playback-did-progress')
        self.create_signal('update-shuffle')
        self.create_signal('update-repeat')

    def player_ready(self):
        return self.player is not None and self.open_finished

    def player_playing(self):
        return self.player is not None and self.open_successful

    def get_is_playing_video(self):
        return self.is_playing and not self.is_playing_audio
    is_playing_video = property(get_is_playing_video)

    def set_volume(self, volume):
        self.volume = volume
        if self.player is not None:
            self.player.set_volume(volume)
    
    def set_presentation_mode(self, mode):
        self.presentation_mode = mode
        if self.is_playing:
            if not self.is_fullscreen:
                self.fullscreen()
            self.video_display.renderer.update_for_presentation_mode(mode)
    
    def toggle_paused(self):
        """Pause a playing item, play a paused item, and soft_fail otherwise."""
        if not self.is_playing:
            app.widgetapp.handle_soft_failure('toggle_paused',
                "item not playing or paused in toggle_paused",
                with_exception=False)
            return # in release mode, recover by doing nothing
        if self.is_paused:
            self.play()
        else:
            self.pause()

    def start_with_items(self, item_infos):
        """Start playback, playing a static list of ItemInfos."""
        # call stop before anything so that we release our existing
        # manual_item_list (#19932)
        self.stop()
        id_list = [i.id for i in item_infos]
        item_list = app.item_list_pool.get(u'manual', id_list)
        self.manual_item_list = item_list
        self.start(None, item_list)

    def goto_currently_playing(self):
        """Jump to the currently playing item in the display."""
        playing_item = self.get_playing_item()
        if not self.selected_tab_list or not playing_item:
            return
        if (self.is_playing and not
          (self.is_playing_audio or self.detached_window)):
            # playing a video in the app, so don't bother
            return
        try:
            tab_iter = self.selected_tab_list.iter_map[self.selected_tabs[0].id]
        except KeyError:
            #17495 - item may be from a tab that no longer exists
            self.selected_tab_list = self.selected_tabs = None
            return
        app.tabs._select_from_tab_list(self.selected_tab_list.type, tab_iter)
        display = app.display_manager.current_display
        if display and hasattr(display, 'controller'):
            controller = display.controller
            controller.scroll_to_item(playing_item, manual=True, recenter=True)
        else:
            #17488 - GuideDisplay doesn't have a controller
            logging.debug("current display doesn't have a controller - "
                    "can't switch to")

    def start(self, start_id, item_list,
            presentation_mode='fit-to-bounds', force_resume=False):
        """Start playback, playing the items from an ItemTracker"""
        if self.is_playing:
            self.stop()
        self.emit('will-start')

        # Remember where we are, so we can switch to it later
        list_type, selected = app.tabs.selection
        self.selected_tab_list = app.tabs[list_type]
        self.selected_tabs = selected

        play_in_miro = app.config.get(prefs.PLAY_IN_MIRO)
        # Only setup a playlist if we are playing in Miro - otherwise we
        # farm off to an external player for an individual item and the
        # concept of a playlist doesn't really make sense.
        start_item = None
        if play_in_miro:
            self.playlist = PlaybackPlaylist(item_list, start_id,
                                             self.shuffle, self.repeat)
            self.playlist.connect("position-changed",
                self._on_position_changed)
            self.playlist.connect("playing-info-changed",
                self._on_playing_changed)
        else:
            if start_id:
                start_item = item_list.get_item(start_id)
            else:
                start_item = item_list.get_first_item()
        self.should_mark_watched = []
        self.presentation_mode = presentation_mode
        self.force_resume = force_resume
        self._play_current(item=start_item)
        if self.presentation_mode != 'fit-to-bounds':
            self.fullscreen()

    def _on_position_changed(self, playlist):
        self._skipped_by_user = False
        self._play_current()

    def _on_playing_changed(self, playlist):
        new_info = self.get_playing_item()
        if new_info is None or not new_info.is_playable:
            self.stop()
            return
        if self.detached_window:
            if self.detached_window.get_title() != new_info.title:
                self.detached_window.set_title(new_info.title)
        if app.config.get(prefs.PLAY_IN_MIRO):
            self.emit('playing-info-changed', new_info)

    def prepare_attached_playback(self):
        self.emit('will-play-attached')
        splitter = app.widgetapp.window.splitter
        self.previous_left_width = splitter.get_left_width()
        self.previous_left_widget = splitter.left
        splitter.remove_left()
        splitter.set_left_width(0)
        app.display_manager.push_display(self.video_display)            
    
    def finish_attached_playback(self, unselect=True):
        if (self.video_display is not None and
                app.display_manager.current_display is self.video_display):
            app.display_manager.pop_display(unselect)
        app.widgetapp.window.splitter.set_left_width(self.previous_left_width)
        app.widgetapp.window.splitter.set_left(self.previous_left_widget)
    
    def prepare_detached_playback(self):
        self.emit('will-play-detached')
        detached_window_frame = app.config.get(prefs.DETACHED_WINDOW_FRAME)
        if detached_window_frame is None:
            detached_window_frame = widgetset.Rect(0, 0, 800, 600)
        else:
            detached_window_frame = widgetset.Rect.from_string(detached_window_frame)
        title = self.playlist.currently_playing.title
        self.detached_window = DetachedWindow(title, detached_window_frame)
        self.align = widgetset.DetachedWindowHolder()
        self.align.add(self.video_display.widget)
        self.detached_window.set_content_widget(self.align)
        self.detached_window.show()
    
    def finish_detached_playback(self):
        # this prevents negative x and y values from getting saved
        coords = str(self.detached_window.get_frame())
        coords = ",".join([str(max(0, int(c))) for c in coords.split(",")])
        app.config.set(prefs.DETACHED_WINDOW_FRAME, coords)
        app.config.save()
        self.align.remove()
        self.align = None
        self.detached_window.close(False)
        self.detached_window.destroy()
        self.detached_window = None
    
    def schedule_update(self):
        def notify_and_reschedule():
            if self.update_timeout is not None:
                self.update_timeout = None
                if self.is_playing:
                    if not self.is_suspended:
                        self.notify_update()
                    self.schedule_update()
        if self.update_timeout:
            self.cancel_update_timer()
        self.update_timeout = timer.add(0.5, notify_and_reschedule)

    def cancel_update_timer(self):
        if self.update_timeout is not None:
            timer.cancel(self.update_timeout)
            self.update_timeout = None

    def notify_update(self):
        if self.player_playing():
            elapsed = self.player.get_elapsed_playback_time()
            total = self.player.get_total_playback_time()
            if elapsed is not None and total is not None:
                self.emit('playback-did-progress', elapsed, total)
            else:
                logging.warning('notify_update: elapsed = %s total = %s',
                                elapsed, total)

    def on_display_removed(self, display):
        if not self.removing_video_display:
            self._skipped_by_user = False
            self.stop()

    def play(self, start_at=0):
        if not self.player:
            logging.warn("no self.player in play(). race condition?")
            return
        duration = self.player.get_total_playback_time()
        if duration is None or duration <= 0:
            logging.warning('duration is %s', duration)
        self.emit('will-play', duration)
        resume_time = self.playlist.currently_playing.resume_time
        if start_at > 0:
            self.player.play_from_time(start_at)
        elif self.should_resume() and not self.is_paused:
            self.player.play_from_time(resume_time)
        else:
            self.player.play()
        self.notify_update()
        self.schedule_update()
        self.is_paused = False
        self.is_suspended = False
        app.menu_manager.update_menus('playback-changed')

    def should_resume(self):
        if self.force_resume:
            return True

        if(self.shuffle == True or 
           self.repeat != WidgetStateStore.get_repeat_off()):
           return False

        currently_playing = self.playlist.currently_playing
        return self.item_resume_policy(currently_playing)

    def pause(self):
        if self.is_playing:
            self.emit('will-pause')
            self.player.pause()
            self.is_paused = True
            app.menu_manager.update_menus('playback-changed')

    def fullscreen(self):
        if not self.is_playing or not self.video_display:
            return
        self.emit('will-fullscreen')
        self.toggle_fullscreen()

    def stop(self):
        if not self.is_playing:
            return
        if self.get_playing_item() is not None:
            self.update_current_resume_time()
        if self.manual_item_list is not None:
            app.item_list_pool.release(self.manual_item_list)
            self.manual_item_list = None
        self.playlist.finished()
        self.playlist = None
        self.cancel_update_timer()
        self.cancel_mark_as_watched()
        self.send_mark_items_watched()
        self.is_playing = False
        self.is_playing_audio = False
        self.is_paused = False
        self.emit('will-stop')
        if self.player is not None:
            self.player.stop()
            self.player = None
        if self.video_display is not None:
            self.remove_video_display()
            self.video_display = None
        self.is_fullscreen = False
        self.previous_left_widget = None
        self.emit('did-stop')
        app.menu_manager.update_menus('playback-changed')

    def get_audio_tracks(self):
        """Get a list of available audio tracks

        :returns: list of (label, track_id) tuples
        """
        if self.player is not None:
            return self.player.get_audio_tracks()
        else:
            return []

    def get_enabled_audio_track(self):
        """Get the currently enabled audio track

        :returns: current track_id or None if we are not playing
        """
        if self.player is not None:
            return self.player.get_enabled_audio_track()
        else:
            return None

    def set_audio_track(self, track_id):
        """Change the currently enabled audio track

        :param track_id: track_id from get_audio_tracks()
        """
        if self.player is not None:
            self.player.set_audio_track(track_id)
        else:
            raise ValueError("Not playing")

    def get_subtitle_tracks(self):
        """Get a list of available subtitle tracks

        :returns: list of (label, track_id) tuples
        """
        if self.player is not None and not self.is_playing_audio:
            return self.player.get_subtitle_tracks()
        else:
            return []

    def get_enabled_subtitle_track(self):
        """Get the currently enabled subtitle track

        :returns: current track_id or None if we are not playing video
        """
        if self.player is not None and not self.is_playing_audio:
            return self.player.get_enabled_subtitle_track()
        else:
            return None

    def set_subtitle_track(self, track_id):
        """Change the currently enabled subtitle track

        :param track_id: track_id from get_subtitle_tracks()
        """
        if self.player is None:
            raise ValueError("Not playing")
        if self.is_playing_audio:
            raise ValueError("Playing Audio")
        self.player.set_subtitle_track(track_id)

    def toggle_shuffle(self):
        self.set_shuffle(not self.shuffle)

    def set_shuffle(self, shuffle):
        if self.shuffle != shuffle:
            self.shuffle = shuffle
            if self.playlist:
                self.playlist.set_shuffle(self.shuffle)
            self.emit('update-shuffle')

    def toggle_repeat(self):
        if self.repeat == WidgetStateStore.get_repeat_playlist():
            self.set_repeat(WidgetStateStore.get_repeat_track())
        elif self.repeat == WidgetStateStore.get_repeat_track():
            self.set_repeat(WidgetStateStore.get_repeat_off())
        elif self.repeat == WidgetStateStore.get_repeat_off():
            self.set_repeat(WidgetStateStore.get_repeat_playlist())
        #handle unknown values
        else:
            self.set_repeat(WidgetStateStore.get_repeat_off())

    def set_repeat(self, repeat):
        if self.repeat != repeat:
            self.repeat = repeat
            if self.playlist:
                self.playlist.set_repeat(self.repeat)
            self.emit('update-repeat')

    def remove_video_display(self):
        self.removing_video_display = True
        if self.detached_window is not None:
            self.video_display.cleanup()
            self.finish_detached_playback()
        else:
            self.finish_attached_playback()
        self.removing_video_display = False

    def update_current_resume_time(self, resume_time=-1):
        if not self._skipped_by_user:
            return
        if not self.player_playing() and resume_time == -1:
            # we want to see what the current time is, but the player hasn't
            # started playing yet.  Just return
            return
        item_info = self.playlist.currently_playing
        if resume_time == -1:
            resume_time = self.player.get_elapsed_playback_time()
            duration = self.player.get_total_playback_time()
            if duration is None:
                logging.warning('update_current_resume_time: duration is None')
                return
            # if we are 95% of the way into the movie and less than 30
            # seconds before the end, don't save resume time (#11956)
            if resume_time > min(duration * 0.95, duration - 30):
                resume_time = 0
        if resume_time < 3:
            # if we're in the first three seconds, don't save the
            # resume time.
            # Note: this should match mark_as_watched time.
            resume_time = 0
        m = messages.SetItemResumeTime(item_info, resume_time)
        m.send_to_backend()

    def fast_forward(self):
        self.player.play()
        self.set_playback_rate(3.0)
        self.notify_update()
        
    def fast_backward(self):
        self.player.play()
        self.set_playback_rate(-3.0)
        self.notify_update()

    def stop_fast_playback(self):
        if self.is_playing:
            self.set_playback_rate(1.0)
            if self.is_paused:
                self.player.pause()
            self.notify_update()

    def set_playback_rate(self, rate):
        if self.is_playing:
            self.player.set_playback_rate(rate)

    def suspend(self):
        if self.is_playing and not self.is_paused:
            self.player.pause()
        self.is_suspended = True
    
    def resume(self):
        if self.is_playing and not self.is_paused:
            self.player.play()
        self.is_suspended = False

    def seek_to(self, progress):
        self.player.seek_to(progress)
        # Sigh.  We could seek past the end and require a stop, which
        # calls stop and destroys the player.  After we come back,
        # the player is no longer valid and we crash.  There's probably
        # a better way to fix this.
        try:
            total = self.player.get_total_playback_time()
            if total is not None:
                self.emit('playback-did-progress', progress * total, total)
        except StandardError:
            pass

    def on_movie_finished(self):
        self._skipped_by_user = False
        if self.playlist.currently_playing is not None:
            m = messages.MarkItemCompleted(self.playlist.currently_playing)
            m.send_to_backend()
            self.update_current_resume_time(0)
            self.play_next_item()
        else:
            self.stop()

    def schedule_mark_as_watched(self, info):
        # Note: mark_as_watched time should match the minimum resume
        # time in update_current_resume_time.
        self.mark_as_watched_timeout = timer.add(3, self.mark_as_watched, info)

    def cancel_mark_as_watched(self):
        if self.mark_as_watched_timeout is not None:
            timer.cancel(self.mark_as_watched_timeout)
            self.mark_as_watched_timeout = None

    def mark_as_watched(self, info):
        self.mark_as_watched_timeout = None
        # if we're in a state we don't think we should be in, then we don't
        # want to mark the item as watched.
        if not self.playlist or self.get_playing_item().id != info.id:
            logging.warning("mark_as_watched: not marking the item as "
                    "watched because we're in a weird state")
            return
        self.should_mark_watched.append(info)

    def send_mark_items_watched(self):
        messages.SetItemsWatched(self.should_mark_watched, True).send_to_backend()
        self.should_mark_watched = []

    def get_playing_item(self):
        if self.playlist is None:
            return None
        return self.playlist.currently_playing

    def is_playing_id(self, id_):
        return self.playlist and self.playlist.is_playing_id(id_)

    def is_playing_item(self, item_info):
        return self.is_playing_id(item_info.id)

    def _setup_player(self, item_info, volume):
        def _handle_successful_sniff(item_type):
            logging.debug("sniffer got '%s' for %s", item_type,
                          item_info.filename)
            self._finish_setup_player(item_info, item_type, volume)
        def _handle_unsuccessful_sniff():
            logging.debug("sniffer got 'unplayable' for %s",
                          item_info.filename)
            self._finish_setup_player(item_info, "unplayable", volume)
        typ = item_info.file_type
        if typ == 'other':
            # the backend and frontend use different names for this
            typ = 'unplayable'
        self._finish_setup_player(item_info, typ, volume)
    
    def _finish_setup_player(self, item_info, item_type, volume):
        if item_type == 'audio':
            if self.is_playing and self.video_display is not None:
                # if we were previously playing a video get rid of the video
                # display first
                self.player.stop()
                self.player = None
                self.remove_video_display()
                self.video_display = None
            if self.player is None or not self.is_playing:
                self._build_audio_player(item_info, volume)
            self.is_playing = True
            self.player.setup(item_info, volume)
        elif item_type in ('video', 'unplayable'):
            # We send items with type 'other' to the video display to be able 
            # to open them using the 'play externally' display - luc.
            if self.is_playing and self.video_display is None:
                # if we were previously playing an audio file, stop.
                self.stop()
                return
            if self.video_display is None or not self.is_playing:
                self._build_video_player(item_info, volume)
            self.is_playing = True
            self.video_display.setup(item_info, item_type, volume)
            if self.detached_window is not None:
                self.detached_window.set_title(item_info.title)
        self.emit('did-start-playing')
        app.menu_manager.update_menus('playback-changed')

    def _build_video_player(self, item_info, volume):
        self.player = widgetset.VideoPlayer()
        self.video_display = VideoDisplay(self.player)
        self.video_display.connect('removed', self.on_display_removed)
        self.video_display.connect('cant-play', self._on_cant_play)
        self.video_display.connect('ready-to-play', self._on_ready_to_play)
        if app.config.get(prefs.PLAY_DETACHED):
            self.prepare_detached_playback()
        else:
            self.prepare_attached_playback()
        self.is_playing_audio = False
        app.menu_manager.select_subtitle_encoding(item_info.subtitle_encoding)
        self.initial_subtitle_encoding = item_info.subtitle_encoding

    def _build_audio_player(self, item_info, volume):
        self.player = widgetset.AudioPlayer()
        self.player.connect('cant-play', self._on_cant_play)
        self.player.connect('ready-to-play', self._on_ready_to_play)
        self.is_playing_audio = True

    def _play_current(self, item=None):
        # XXX item is a hint in the case of external playback - where a
        # playlist does not make sense and don't want to rely on it being
        # there.
        self.cancel_update_timer()
        self.cancel_mark_as_watched()
        self._skipped_by_user = True

        info_to_play = item if item else self.get_playing_item()
        if info_to_play is None: # end of the playlist
            self.stop()
            return

        play_in_miro = app.config.get(prefs.PLAY_IN_MIRO)
        if self.is_playing:
            self.player.stop(will_play_another=play_in_miro)

        if not play_in_miro:
            app.widgetapp.open_file(info_to_play.filename)
            messages.MarkItemWatched(info_to_play).send_to_backend()
            return

        volume = app.config.get(prefs.VOLUME_LEVEL)
        self.emit('selecting-file', info_to_play)
        self.open_successful = self.open_finished = False
        self._setup_player(info_to_play, volume)

    def _on_ready_to_play(self, obj):
        playing_item = self.get_playing_item()
        if playing_item is None:
            return
        self.open_successful = self.open_finished = True
        if not playing_item.video_watched:
            self.schedule_mark_as_watched(playing_item)
        if isinstance(self.player, widgetset.VideoPlayer):
            self.player.select_subtitle_encoding(self.initial_subtitle_encoding)
        self.play()

    def _on_cant_play(self, obj):
        playing_item = self.get_playing_item()
        if playing_item is None:
            return
        self.open_finished = True
        self._skipped_by_user = False
        self.emit('cant-play-file')
        if isinstance(obj, widgetset.AudioPlayer):
            self.play_next_item()

    def _handle_skip(self):
        playing = self.get_playing_item()
        if self._skipped_by_user and playing is not None:
            self.update_current_resume_time()
            messages.MarkItemSkipped(playing).send_to_backend()

    def play_next_item(self):
        if not self.player_ready():
            return
        self._handle_skip()
        if ((not self.item_continuous_playback_mode(
                            self.playlist.currently_playing) and
             not self._skipped_by_user)):
            if self.repeat:
                self._play_current()
            else: # not repeating, or shuffle
                self.stop()
        else:
            self.playlist.select_next_item(self._skipped_by_user)
            self._play_current()

    def play_prev_item(self, from_user=False):
        """
        :param from_user: whether or not play_prev_item is being
                          called as a resume of the user pressing a
                          'prev' button or menu item.
        """
        # if the user pressed a prev button or menu item and the
        # current elapsed time is 3 seconds or greater, then we seek
        # to the beginning of the item.
        #
        # otherwise, we move to the previous item in the play list.
        if not self.player_ready():
            return
        if from_user:
            current_time = self.player.get_elapsed_playback_time()
            if current_time > 3:
                self.seek_to(0)
                return
        self._handle_skip()
        self.playlist.select_previous_item()
        self._play_current()

    def skip_forward(self):
        if not self.player_ready():
            return
        self.player.skip_forward()

    def skip_backward(self):
        if not self.player_ready():
            return
        self.player.skip_backward()

    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        if not self.is_fullscreen:
            self.is_fullscreen = True
            self.video_display.enter_fullscreen()
    
    def exit_fullscreen(self):
        if self.is_fullscreen:
            self.is_fullscreen = False
            self.presentation_mode = 'fit-to-bounds'
            self.video_display.exit_fullscreen()

    def toggle_detached_mode(self):
        if self.is_fullscreen:
            return
        if self.detached_window is None:
            self.switch_to_detached_playback()
        else:
            self.switch_to_attached_playback()
        app.menu_manager.update_menus('playback-changed')
            
    def switch_to_attached_playback(self):
        self.cancel_update_timer()
        self.video_display.prepare_switch_to_attached_playback()
        self.finish_detached_playback()
        self.prepare_attached_playback()
        self.schedule_update()
    
    def switch_to_detached_playback(self):
        self.cancel_update_timer()
        self.video_display.prepare_switch_to_detached_playback()
        self.finish_attached_playback(False)
        self.prepare_detached_playback()
        self.schedule_update()

    def open_subtitle_file(self):
        if not self.is_playing:
            return

        pos = self.player.get_elapsed_playback_time()
        def after_successful_select():
            self.play(start_at=pos)

        self.pause()

        title = _('Open Subtitles File...')
        filters = [(_('Subtitle files'), [ext[1:] for ext in filetypes.SUBTITLES_EXTENSIONS])]
        filename = dialogs.ask_for_open_pathname(title, filters=filters, select_multiple=False)
        if filename is None:
            self.play()
            return

        self.player.select_subtitle_file(filename, after_successful_select)

    def select_subtitle_encoding(self, encoding):
        if self.is_playing:
            self.player.select_subtitle_encoding(encoding)
            messages.SetItemSubtitleEncoding(self.get_playing_item(),
                    encoding).send_to_backend()

    def item_resume_policy(self, item_info):
        """
        There are two kinds of resume results we need. 
        ItemRenderer.should_resume_item() calculates whether an item should 
        display a resume button and PlaybackManager.should_resume() calculates
        whether an item should resume when clicked. This method calculates 
        the general resume policy for an item which these other methods then
        use to calculate their final result.
        """
        # FIXME: we should have a better way of deciding
        # which tab something is listed in.  In addition, assume all items
        # from a remote share is either audio or video (no podcast).
        # Figure out if its from a library or feed. Also, if feed_url
        # is None don't consider it a podcast.
        if (item_info.remote or 
           not item_info.feed_id or
          (item_info.feed_url and
          (item_info.feed_url.startswith('dtv:manualFeed') or
           item_info.feed_url.startswith('dtv:directoryfeed') or
           item_info.feed_url.startswith('dtv:search') or
           item_info.feed_url.startswith('dtv:searchDownloads')))):
            if(item_info.file_type == u'video'):
                resume = app.config.get(prefs.RESUME_VIDEOS_MODE)
            else:
                resume = app.config.get(prefs.RESUME_MUSIC_MODE)
        else:
            resume =  app.config.get(prefs.RESUME_PODCASTS_MODE)
        
        result = (item_info.is_playable
               and item_info.resume_time > 0
               and resume
               and app.config.get(prefs.PLAY_IN_MIRO))
        return result

    def item_continuous_playback_mode(self, item_info):
        if (item_info.remote or
           not item_info.feed_id or
          (item_info.feed_url and
          (item_info.feed_url.startswith('dtv:manualFeed') or
           item_info.feed_url.startswith('dtv:directoryfeed') or
           item_info.feed_url.startswith('dtv:search') or
           item_info.feed_url.startswith('dtv:searchDownloads')))):
            if(item_info.file_type == u'video'):
                continuous_playback = app.config.get(
                                          prefs.CONTINUOUS_VIDEO_PLAYBACK_MODE)
            else:
                continuous_playback = app.config.get(
                                          prefs.CONTINUOUS_MUSIC_PLAYBACK_MODE)
        else:
            continuous_playback = app.config.get(
                                      prefs.CONTINUOUS_PODCAST_PLAYBACK_MODE)

        result = continuous_playback and app.config.get(prefs.PLAY_IN_MIRO)
        return result

class PlaybackPlaylist(signals.SignalEmitter):
    def __init__(self, item_list, start_id, shuffle, repeat):
        """Create a playlist of items we are playing

        :param item_list: ItemList that we're playing from
        :param start_id: id of the first item to play, or None to play a
        random item.
        :param shuffle: should we start in shuffle mode?
        :param repeat: repeate mode to start in.
        """
        signals.SignalEmitter.__init__(self, 'position-changed',
                'playing-info-changed')
        self.item_list = item_list
        app.item_list_pool.add_ref(item_list)
        self._item_list_callbacks = [
                item_list.connect('items-changed', self._on_items_changed),
                item_list.connect('list-changed', self._on_list_changed),
        ]
        self.shuffle = shuffle
        self.repeat = repeat
        if len(self.item_list) == 0:
            # special case for empty item lists (#19890)
            self.currently_playing = None
            return
        # If we get be passed a torrent folder item, we can't play it
        # directly.  We use _find_playable to find its first playable child in
        # that case.
        if start_id is None:
            start_id = self.item_list.get_first_item().id
        start_id = self._find_playable(start_id)
        if start_id is not None:
            self.currently_playing = self.item_list.get_item(start_id)
            self._create_navigation_strategy()
        else:
            self.currently_playing = None

    def is_playing_id(self, id_):
        return self.currently_playing and self.currently_playing.id == id_

    def is_playing_item(self, info):
        return self.is_playing_id(info.id)

    def set_shuffle(self, value):
        self.shuffle = value
        self._create_navigation_strategy()

    def set_repeat(self, value):
        self.repeat = value
        self._create_navigation_strategy()

    def _create_navigation_strategy(self):
        if self.item_list.item_in_list(self.currently_playing.id):
            initial_item = self.currently_playing
        else:
            initial_item = None
        repeat = (self.repeat == WidgetStateStore.get_repeat_playlist())
        if self.shuffle:
            self.navigation_strategy = ShuffleNavigationStrategy(
                initial_item, self.item_list, repeat)
        else:
            self.navigation_strategy = LinearNavigationStrategy(
                initial_item, self.item_list, repeat)

    def select_previous_item(self):
        prev_item = self.navigation_strategy.previous_item()
        self._change_currently_playing(prev_item)

    def select_next_item(self, skipped_by_user=False):
        if (self.repeat == WidgetStateStore.get_repeat_track() and
            not skipped_by_user):
            next_item = self.currently_playing
        else:
            next_item = self.navigation_strategy.next_item()
        self._change_currently_playing(next_item)

    def finished(self):
        """Call this when we're finished with the playlist."""
        self._change_currently_playing(None)
        for handle in self._item_list_callbacks:
            self.item_list.disconnect(handle)
        app.item_list_pool.release(self.item_list)
        self.navigation_strategy = self.item_list = None
        self._item_list_callbacks = []
        self.disconnect_all()

    def _find_playable(self, item_id):
        """Find the first playable item in our item list starting with
        item_info and moving down.
        """
        try:
            item_info = self.item_list.get_item(item_id)
        except KeyError:
            return None
        if item_info.is_playable:
            return item_info.id
        current_row = self.item_list.get_index(item_info.id)
        for i in xrange(current_row + 1, len(self.item_list)):
            item_info = self.item_list.get_row(i)
            if item_info.is_playable:
                return item_info.id
        # no playable items
        return None

    def _on_items_changed(self, item_list, changed_ids):
        self.handle_changes()

    def _on_list_changed(self, item_list):
        self.handle_changes()

    def handle_changes(self):
        if self.currently_playing is not None:
            if self.item_list.item_in_list(self.currently_playing.id):
                new_item = self.item_list.get_item(self.currently_playing.id)
                if new_item != self.currently_playing:
                    if new_item.is_playable:
                        self.currently_playing = new_item
                    else:
                        self.currently_playing = None
                    self.emit("playing-info-changed")

    def _change_currently_playing(self, new_info):
        self.currently_playing = new_info
        # FIXME: should notify the item list code and so that it can redraw
        # the item.

class PlaylistNavigationStrategy(object):
    """Handles moving back/forward for PlaybackPlaylist."""
    def __init__(self, initial_item, item_list, repeat):
        """Create a PlaylistNavigationStrategy

        :param initial_item: the first item in the playlist, or None
        :param item_list: ItemList we're playing from
        :param repeat: repeat mode
        """

    def next_item(self):
        """Pick the next item to play.

        :returns: ItemInfo to play
        """
        raise NotImplementedError()

    def previous_item(self):
        """Pick the previous item to play.

        :returns: ItemInfo to play
        """
        raise NotImplementedError()

class LinearNavigationStrategy(PlaylistNavigationStrategy):
    """Play items in the same order as the item list."""

    def __init__(self, initial_item, item_list, repeat):
        self.repeat = repeat
        self.current_item = initial_item
        self.item_list = item_list

    def next_item(self):
        return self._pick_item(+1)

    def previous_item(self):
        return self._pick_item(-1)

    def _pick_item(self, delta):
        if (self.current_item is None or
            not self.item_list.item_in_list(self.current_item.id)):
            # item no longer in item list.  Return None to stop playback
            self.current_item = None
            return None
        current_item = self.current_item
        while True:
            canditate = self._next_candidate_item(current_item, delta)
            if canditate is None:
                # no more items to choose from, select None to stop playback
                self.current_item = None
                return None
            if canditate.is_playable:
                # found an item, select it
                self.current_item = canditate
                return self.current_item
            if canditate is self.current_item:
                # we've wrapped around the list without finding an item,
                # return None
                self.current_item = None
                return None
            # candidate item isn't playable, continue searching
            current_item = canditate

    def _next_candidate_item(self, current_item, delta):
        row = self.item_list.get_index(current_item.id)
        new_row = row + delta
        if 0 <= new_row < len(self.item_list):
            # normal case, play the next item
            return self.item_list.get_row(new_row)
        elif self.repeat and len(self.item_list) > 0:
            # if we are in repeat mode, wrap around
            return self.item_list.get_row(new_row % len(self.item_list))
        else:
            # no items left to pick, return None to stop playback
            return None

class ShuffleNavigationStrategy(PlaylistNavigationStrategy):
    """Play items in shuffle mode."""
    def __init__(self, initial_item, item_list, repeat):
        self.repeat = repeat
        self.item_list = item_list
        # history of items that we've already played
        self.history = []
        # history of items that we've already played, then skipped back to
        self.forward_history = []
        self.current_item = initial_item

    def next_item(self):
        if self.current_item is not None:
            self.history.append(self.current_item)
        self.current_item = self._next_from_history_list(self.forward_history)
        if self.current_item is None:
            self.current_item = self._random_item()
        return self.current_item

    def previous_item(self):
        if self.current_item is not None:
            self.forward_history.append(self.current_item)
        self.current_item = self._next_from_history_list(self.history)
        if self.current_item is None:
            self.current_item = self._random_item()
        return self.current_item

    def _random_item(self):
        choices = self.item_list.get_playable_ids()
        if not self.repeat:
            history_ids = set((i.id for i in self.history))
            history_ids.update(i.id for i in self.forward_history)
            choices = list(set(choices) - history_ids)
        if choices:
            return self.item_list.get_item(random.choice(choices))
        else:
            return None

    def _next_from_history_list(self, history_list):
        while history_list:
            item = history_list.pop()
            if self.item_list.item_in_list(item.id):
                return item

class DetachedWindow(widgetset.Window):
    def __init__(self, title, rect):
        widgetset.Window.__init__(self, title, rect)
        self.closing = False
        self.stop_on_close = True
        self.connect_menu_keyboard_shortcuts()

    def close(self, stop_playback=True):
        if not self.closing:
            self.stop_on_close = stop_playback
            widgetset.Window.close(self)

    def do_will_close(self):
        if not self.closing:
            self.closing = True
            if self.stop_on_close:
                app.playback_manager.stop()

    def do_key_press(self, key, mods):
        if handle_key_press(key, mods):
            return True
        return False

def handle_key_press(key, mods):
    """Handle a playback key press events """

    if len(mods) != 0:
        if set([keyboard.MOD, keyboard.SHIFT]) == mods:
            if key in ('>', '.'): # OS X sends '.', GTK sends '>'
                app.widgetapp.on_forward_clicked()
                return True
            elif key in ('<', ','): # OS X sends ',', GTK sends '<'
                app.widgetapp.on_previous_clicked()
                return True

        if set([keyboard.SHIFT]) == mods:
            if key == keyboard.RIGHT_ARROW:
                app.widgetapp.on_skip_forward()
                return True
            elif key == keyboard.LEFT_ARROW:
                app.widgetapp.on_skip_backward()
                return True

        if set([keyboard.ALT]) == mods:
            if key == keyboard.ENTER:
                app.playback_manager.enter_fullscreen()
                return True

        if set([keyboard.CTRL]) == mods and key == keyboard.SPACE:
            app.playback_manager.toggle_paused()
            return True
        return False

    if key == keyboard.DELETE or key == keyboard.BKSPACE:
        playing = app.playback_manager.get_playing_item()
        if playing is not None:
            if app.playback_manager.is_playing_audio:
                # if we're playing an audio item, then we let
                # remove_items figure out what is being deleted.
                app.widgetapp.remove_items()
            else:
                app.playback_manager.on_movie_finished()
                app.widgetapp.remove_items([playing])
            return True

    if key == keyboard.ESCAPE:
        if app.playback_manager.is_fullscreen:
            app.playback_manager.exit_fullscreen()
            return True
        else:
            app.widgetapp.on_stop_clicked()
            return True

    if key == keyboard.RIGHT_ARROW:
        app.widgetapp.on_forward_clicked()
        return True

    if key == keyboard.LEFT_ARROW:
        app.widgetapp.on_previous_clicked()
        return True

    if key == keyboard.UP_ARROW:
        app.widgetapp.up_volume()
        return True

    if key == keyboard.DOWN_ARROW:
        app.widgetapp.down_volume()
        return True

    if key == keyboard.SPACE:
        app.playback_manager.toggle_paused()
        return True
