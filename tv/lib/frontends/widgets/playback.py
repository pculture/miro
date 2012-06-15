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
from random import randrange
from random import shuffle

from miro import app
from miro import prefs
from miro import signals
from miro import messages
from miro import filetypes

from miro.gtcache import gettext as _
from miro.plat.frontends.widgets import timer
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets.displays import VideoDisplay
from miro.frontends.widgets import itemtrack
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
        tracker = itemtrack.ManualItemListTracker.create(item_infos)
        self.start(None, tracker)

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

    def start(self, start_id, item_tracker,
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
            self.playlist = PlaybackPlaylist(item_tracker, start_id)
            self.playlist.connect("position-changed",
                self._on_position_changed)
            self.playlist.connect("playing-info-changed",
                self._on_playing_changed)
            self.playlist.set_shuffle(self.shuffle)
            self.playlist.set_repeat(self.repeat)
        else:
            model = item_tracker.item_list.model
            if start_id:
                start_item = model.get_info(start_id)
            else:
                start_item = model.get_first_info()
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
        if self.detached_window:
            if self.detached_window.get_title() != new_info.name:
                self.detached_window.set_title(new_info.name)
        if app.config.get(prefs.PLAY_IN_MIRO) and new_info:
            # if playlist is None, new_info will be none as well.
            # Since emitting playing-info-changed with a "None"
            # argument will cause a crash, we only emit it if
            # new_info has a value
            self.emit('playing-info-changed', new_info)
        else:
            logging.warning("trying to update playback info "
                            "even though playback has stopped")

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
        title = self.playlist.currently_playing.name
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
        m = messages.MarkItemCompleted(self.playlist.currently_playing)
        m.send_to_backend()
        self.update_current_resume_time(0)
        self._skipped_by_user = False
        self.play_next_item()

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
                          item_info.video_path)
            self._finish_setup_player(item_info, item_type, volume)
        def _handle_unsuccessful_sniff():
            logging.debug("sniffer got 'unplayable' for %s",
                          item_info.video_path)
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
                self.detached_window.set_title(item_info.name)
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
            app.widgetapp.open_file(info_to_play.video_path)
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
    def __init__(self, item_tracker, start_id):
        signals.SignalEmitter.__init__(self, 'position-changed',
                'playing-info-changed')
        self.item_tracker = item_tracker
        self.model = item_tracker.item_list.model
        self._tracker_callbacks = [
                item_tracker.connect('items-will-change',
                    self._on_items_will_change),
                item_tracker.connect('items-changed', self._on_items_changed),
                item_tracker.connect('items-removed-from-source',
                    self._on_items_removed_from_source)
        ]
        self.repeat = WidgetStateStore.get_repeat_off()
        self.shuffle = False
        self.shuffle_history = []
        self.currently_playing = None
        self.shuffle_upcoming = self.generate_upcoming_shuffle_items()
        self._pick_initial_item(start_id)

    def _pick_initial_item(self, start_id):
        if start_id:
            # The call to _find_playable here covers the corner case where
            # start_id belogns to a container item with playable children.  In
            # that case is_playing is True, but we still can't directly play
            # it
            start_item = self._find_playable(self.model.get_info(start_id))
        else:
            start_item = self._find_playable(self.model.get_first_info())
        self._change_currently_playing(start_item)

    def finished(self):
        self._change_currently_playing(None)
        for handle in self._tracker_callbacks:
            self.item_tracker.disconnect(handle)
        self.item_tracker = None
        self.model = None
        self.disconnect_all()

    def prev_shuffle_item(self):
        while len(self.shuffle_history) > 0:
            try:
                return self.model.get_info(self.shuffle_history[-1])
            except KeyError:
                # Item was removed from our InfoList by a ItemList filter
                # (#17500).  Try the previous item in the list.
                self.shuffle_history.pop()
                continue
        # no items in our history, return None
        return

    def next_shuffle_item(self):
        while len(self.shuffle_upcoming) > 0:
            next_id = self.shuffle_upcoming.pop()
            try:
                return self.model.get_info(next_id)
            except KeyError:
                # Item was removed from our InfoList by a ItemList filter
                # (#17500).  Try the next item in the list.
                continue
        # no items left in shuffle_upcoming
        return None

    def find_next_item(self, skipped_by_user=True):
        #if track repeat is on and the user doesn't skip, 
        #shuffle doesn't matter
        if ((self.repeat == WidgetStateStore.get_repeat_track()
             and not skipped_by_user)):
            return self.currently_playing
        elif ((not self.shuffle and
             self.repeat == WidgetStateStore.get_repeat_playlist()
             and self.is_playing_last_item())):
            return self._find_playable(self.model.get_first_info())
        elif (self.shuffle and self.repeat == WidgetStateStore.get_repeat_off()
             or self.shuffle and self.repeat == WidgetStateStore.get_repeat_track()):
            next_item = self.next_shuffle_item()
            if next_item is None:
                self.shuffle_upcoming = self.generate_upcoming_shuffle_items()
                self.shuffle_history = []
                return None #stop playback 
            else:
                # Remove currently playing item from history if it
                # was removed from the playlist.
                if not self.shuffle_history:
                    logging.info('find_next_item: shuffle history empty: '
                                 'case 1')
                else:
                    if self._is_playing_filtered_item():
                        self.shuffle_history.pop()
                self.shuffle_history.append(next_item.id)
                return next_item
        elif self.shuffle and WidgetStateStore.get_repeat_playlist():
            next_item = self.next_shuffle_item()
            if next_item is None:
                #populate with new items
                self.shuffle_upcoming = self.generate_upcoming_shuffle_items() 
                next_item = self.next_shuffle_item()
                if next_item is None:
                    #17492 - nothing playable in list
                    return None
            # Remove currently playing item from history if it
            # was removed from the playlist.
            if not self.shuffle_history:
                logging.info('find_next_item: shuffle history empty: case 2')
            else:
                if self._is_playing_filtered_item():
                    self.shuffle_history.pop()
            self.shuffle_history.append(next_item.id)
            return next_item
        else:
            if self._is_playing_filtered_item():
                return self.model.get_first_info()
            else:
                next_item = self.model.get_next_info(self.currently_playing.id)
                return self._find_playable(next_item)

    def find_previous_item(self):
        if self.shuffle:
            if not self.shuffle_history:
                return None
            current_item = self.shuffle_history.pop()
            # Only add the currently playing item to upcoming shuffle items
            # if it exists in the playlist
            if not self._is_playing_filtered_item():
                self.shuffle_upcoming.append(current_item)
            return self.prev_shuffle_item()
        elif (not self.shuffle 
              and self.repeat == WidgetStateStore.get_repeat_playlist()
              and self.is_playing_first_item()):
            last_item = self._find_playable(self.model.get_last_info(), True)
            return last_item
        else:
            if self._is_playing_filtered_item():
                return None
            else:
                prev_item = self.model.get_prev_info(self.currently_playing.id)
                return self._find_playable(prev_item, backwards=True)

    def generate_upcoming_shuffle_items(self):
        if not self.shuffle:
            return []
        elif (self.repeat == WidgetStateStore.get_repeat_off()
             or self.repeat == WidgetStateStore.get_repeat_track()):
            #random order
            items = self.get_all_playable_items()
            shuffle(items)
            #do not include currently playing item
            if self.currently_playing:
                try:
                    items.remove(self.currently_playing.id)
                except ValueError:
                    pass
            return items
        elif self.repeat == WidgetStateStore.get_repeat_playlist():
            #random items
            items = self.get_all_playable_items()
            if items:
                return self.random_sequence(items, self.currently_playing.id)
            else: 
                return []
        else:
            return []

    def random_sequence(self, pool, do_not_begin_with=None):
        """
        Returns a list of random elements taken from the pool 
        parameter (which is a list). This means that the 
        returned list might contain elements from the pool 
        several times while others might not appear at all.

        The returned list has the following contraints:

        An element will never appear twice in a row.

        If an element from the pool is passed as do_no_begin_with 
        the returned list will not begin with that element.
        """
        random_items = []
        previous_index = None

        if do_not_begin_with:
            try:
                previous_index = pool.index(do_not_begin_with)
            except ValueError:
                pass

        if len(pool) < 2:
            #17493: infinite loop when trying to shuffle 1 item
            return pool
        for i in range(len(pool)):
            random_index = randrange(0, len(pool))
            while random_index == previous_index:
                random_index = randrange(0, len(pool))
            random_items.append(pool[random_index])
            previous_index = random_index
        return random_items

    def select_previous_item(self):
        previous_item = self.find_previous_item()
        self._change_currently_playing(previous_item)

    def select_next_item(self, skipped_by_user=False):
        next_item = self.find_next_item(skipped_by_user)
        self._change_currently_playing(next_item)

    def _is_playing_filtered_item(self):
        """Are we playing an item that is filtered out of our InfoList?

        This method should only be called if currently_playing is not None
        """

        if self.currently_playing is None:
            app.widgetapp.handle_soft_failure('_is_playing_filtered_item',
                "currently_playing is None", with_exception=False)
            return True # I guess this is most likely to make things work
        try:
            self.model.get_info(self.currently_playing.id)
        except KeyError:
            return True
        else:
            return False

    def is_playing_last_item(self):
        if self._is_playing_filtered_item():
            return False
        next_item = self.model.get_next_info(self.currently_playing.id)
        return self._find_playable(next_item) == None

    def is_playing_first_item(self):
        if self._is_playing_filtered_item():
            return False
        previous_item = self.model.get_prev_info(self.currently_playing.id)
        return self._find_playable(previous_item, True) == None

    def get_all_playable_items(self):
        item_info = self.model.get_first_info()
        items = []
        while item_info is not None:
            if item_info.is_playable:
                items.append(item_info.id)
            item_info = self.model.get_next_info(item_info.id)
        return items

    def is_playing_id(self, id_):
        return self.currently_playing and self.currently_playing.id == id_

    def set_shuffle(self, value):
        self.shuffle = value
        self.shuffle_upcoming = self.generate_upcoming_shuffle_items()
        if self.currently_playing:
            self.shuffle_history = [self.currently_playing.id]
        else:
            self.shuffle_history = []

    def set_repeat(self, value):
        self.repeat = value

    def _on_items_will_change(self, tracker, added, changed, removed):
        if self.currently_playing:
            self._items_before_change = self.model.info_list()
            if self._is_playing_filtered_item():
                self._index_before_change = -1
            else:
                self._index_before_change = self.model.index_of_id(
                        self.currently_playing.id)
           
    def _on_items_removed_from_source(self, tracker, ids_removed):
        if self.currently_playing:
            old_currently_playing = self.currently_playing
            removed_set = set(ids_removed)
            if self.currently_playing.id in removed_set:
                self._change_currently_playing_after_removed(ids_removed)
            
        if (self.currently_playing is None
                or old_currently_playing.id is not self.currently_playing.id):
            self.emit("position-changed")

    def _update_currently_playing(self, new_info):
        """Update our currently-playing ItemInfo."""
        self.currently_playing = new_info

    def _change_currently_playing_after_removed(self, removed_set):
        def position_removed(old_index):
            old_info = self._items_before_change[old_index]
            try:
                return (old_info.id in removed_set
                        or not self.model.get_info(old_info.id).is_playable)
            except KeyError:
                # info was removed by the ItemList's internal filter
                return True

        new_position = self._index_before_change
        if new_position == -1:
            # we were playing an item that was filtered by the search and
            # it got removed.  Start with the top of the list
            new_position = 0
        while True:
            if new_position >= len(self._items_before_change):
                # moved past the end of our old item list, stop playback
                self._change_currently_playing(None)
                return
            if not position_removed(new_position):
                break
            new_position += 1
        item = self.model.get_info(self._items_before_change[new_position].id)
        self._change_currently_playing(item)

    def _on_items_changed(self, tracker, added, changed, removed):
        if self.shuffle:
            for id_ in removed:
                while True:
                    try:
                        self.shuffle_upcoming.remove(id_)
                    except ValueError:
                        break
                while True:
                    try:
                        self.shuffle_history.remove(id_)
                    except ValueError:
                        break
            for item in added:
                shuffle_upcoming_len = len(self.shuffle_upcoming)
                if shuffle_upcoming_len:
                    index = randrange(0, shuffle_upcoming_len)
                else:
                    index = 0
                self.shuffle_upcoming.insert(index, item.id)
        self._index_before_change = None
        self._items_before_change = None
        for info in changed:
            if (self.currently_playing is not None and
                    info.id == self.currently_playing.id):
                self._update_currently_playing(info)
                self.emit("playing-info-changed")
                break

    def _find_playable(self, item_info, backwards=False):
        if backwards:
            iter_func = self.model.get_prev_info
        else:
            iter_func = self.model.get_next_info

        while item_info is not None and not item_info.is_playable:
            item_info = iter_func(item_info.id)
        return item_info

    def _change_currently_playing(self, new_info):
        self.currently_playing = new_info
        # FIXME: should notify the item list code and so that it can redraw
        # the item.

    def is_playing_item(self, info):
        return (self.currently_playing is not None and 
                self.currently_playing.id == info.id)

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
