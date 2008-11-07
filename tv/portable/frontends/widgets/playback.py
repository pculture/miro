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

import os

from miro import app
from miro import prefs
from miro import config
from miro import signals
from miro import messages

from miro.plat.frontends.widgets import timer
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets.displays import VideoDisplay
#from miro.frontends.widgets.displays import AudioDisplay
#from miro.frontends.widgets.displays import ExternalVideoDisplay

class PlaybackManager (signals.SignalEmitter):
    
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.video_display = None
        self.detached_window = None
        self.previous_left_width = 0
        self.previous_left_widget = None
        self.is_fullscreen = False
        self.is_playing = False
        self.is_paused = False
        self.is_suspended = False
        self.playlist = None
        self.position = None
        self.mark_as_watched_timeout = None
        self.update_timeout = None
        self.create_signal('will-play')
        self.create_signal('will-pause')
        self.create_signal('will-stop')
        self.create_signal('did-stop')
        self.create_signal('will-fullscreen')
        self.create_signal('playback-did-progress')
    
    def set_volume(self, volume):
        self.volume = volume
        if self.video_display is not None:
            self.video_display.set_volume(volume)
    
    def play_pause(self):
        if not self.is_playing or self.is_paused:
            self.play()
        else:
            self.pause()
    
    def start_with_items(self, item_infos):
        self.playlist = item_infos
        self.position = 0
        def if_yes():
            if not self.is_playing:
                self.video_display = VideoDisplay()
                self.video_display.connect('removed', self.on_display_removed)
                if config.get(prefs.PLAY_DETACHED):
                    self.prepare_detached_playback()
                else:
                    self.prepare_attached_playback()
                app.menu_manager.handle_playing_selection()
            self._select_current()
            self.play()

        def if_no():
            self.exit_playback()

        self._try_select_current(if_yes, if_no)
    
    def prepare_attached_playback(self):
        splitter = app.widgetapp.window.splitter
        self.previous_left_width = splitter.get_left_width()
        self.previous_left_widget = splitter.left
        splitter.remove_left()
        splitter.set_left_width(0)
        app.display_manager.push_display(self.video_display)            
    
    def finish_attached_playback(self, unselect=True):
        app.display_manager.pop_display(unselect)
        app.widgetapp.window.splitter.set_left_width(self.previous_left_width)
        app.widgetapp.window.splitter.set_left(self.previous_left_widget)
    
    def prepare_detached_playback(self):
        detached_window_frame = config.get(prefs.DETACHED_WINDOW_FRAME)
        if detached_window_frame is None:
            detached_window_frame = widgetset.Rect(0, 0, 800, 600)
        else:
            detached_window_frame = widgetset.Rect.from_string(detached_window_frame)
        self.detached_window = DetachedWindow("", detached_window_frame)
        align = widgetset.Alignment(bottom_pad=16, xscale=1.0, yscale=1.0)
        align.add(self.video_display.widget)
        self.detached_window.set_content_widget(align)
        self.detached_window.show()
    
    def finish_detached_playback(self):
        config.set(prefs.DETACHED_WINDOW_FRAME, str(self.detached_window.get_frame()))
        config.save()
        self.detached_window.close(False)
        self.detached_window.destroy()
        self.detached_window = None
    
    def schedule_update(self):
        def notify_and_reschedule():
            if self.update_timeout is not None:
                self.update_timeout = None
                if self.is_playing and not self.is_paused:
                    if not self.is_suspended:
                        self.notify_update()
                    self.schedule_update()
        self.update_timeout = timer.add(0.5, notify_and_reschedule)

    def cancel_update_timer(self):
        if self.update_timeout is not None:
            timer.cancel(self.update_timeout)
            self.update_timeout = None

    def notify_update(self):
        if self.video_display is not None:
            elapsed = self.video_display.get_elapsed_playback_time()
            total = self.video_display.get_total_playback_time()
            self.emit('playback-did-progress', elapsed, total)

    def on_detached_window_close(self, window):
        self.stop()

    def on_display_removed(self, display):
        self.stop()
    
    def play(self):
        duration = self.video_display.get_total_playback_time()
        self.emit('will-play', duration)
        resume_time = self.playlist[self.position].resume_time
        if (config.get(prefs.RESUME_VIDEOS_MODE)
               and resume_time > 10
               and not self.is_paused):
            self.video_display.play_from_time(resume_time)
        else:
            self.video_display.play()
        self.notify_update()
        self.schedule_update()
        self.is_playing = True
        self.is_paused = False
        self.is_suspended = False
        app.menu_manager.set_play_pause("pause")

    def pause(self):
        if self.is_playing:
            self.emit('will-pause')
            self.video_display.pause()
            self.is_paused = True
            app.menu_manager.set_play_pause("play")

    def fullscreen(self):
        if not self.is_playing:
            return
        self.emit('will-fullscreen')
        self.toggle_fullscreen()

    def stop(self, save_resume_time=True):
        if not self.is_playing:
            return
        if save_resume_time:
            self.update_current_resume_time()
        self.exit_playback()
    
    def exit_playback(self):
        self.cancel_update_timer()
        self.cancel_mark_as_watched()
        self.is_playing = False
        self.is_paused = False
        self.emit('will-stop')
        if self.video_display is not None:
            self.video_display.stop()
            if self.detached_window is not None:
                self.video_display.cleanup()
                self.finish_detached_playback()
            else:
                self.finish_attached_playback()
        self.is_fullscreen = False
        self.previous_left_widget = None
        self.video_display = None
        self.position = self.playlist = None
        self.emit('did-stop')

    def update_current_resume_time(self, resume_time=-1):
        if config.get(prefs.RESUME_VIDEOS_MODE):
            if resume_time == -1:
                resume_time = self.video_display.get_elapsed_playback_time()
        else:
            resume_time = 0
        id = self.playlist[self.position].id
        messages.SetItemResumeTime(id, resume_time).send_to_backend()

    def set_playback_rate(self, rate):
        if self.is_playing:
            self.video_display.set_playback_rate(rate)

    def suspend(self):
        if self.is_playing and not self.is_paused:
            self.video_display.pause()
        self.is_suspended = True
    
    def resume(self):
        if self.is_playing and not self.is_paused:
            self.video_display.play()
        self.is_suspended = False

    def seek_to(self, progress):
        self.video_display.seek_to(progress)
        total = self.video_display.get_total_playback_time()
        self.emit('playback-did-progress', progress * total, total)

    def on_movie_finished(self):
        self.update_current_resume_time(0)
        self.play_next_movie(False)

    def schedule_mark_as_watched(self):
        self.mark_as_watched_timeout = timer.add(3, self.mark_as_watched)

    def cancel_mark_as_watched(self):
        if self.mark_as_watched_timeout is not None:
            timer.cancel(self.mark_as_watched_timeout)
            self.mark_as_watched_timeout = None

    def mark_as_watched(self):
        id = self.playlist[self.position].id
        messages.MarkItemWatched(id).send_to_backend()
        self.mark_as_watched_timeout = None

    def _try_select_current(self, if_yes_callback, if_no_callback):
        self.cancel_update_timer()
        self.cancel_mark_as_watched()
        if 0 <= self.position < len(self.playlist):
            if self.is_playing:
                self.video_display.stop()
            item_info = self.playlist[self.position]

            def _if_no():
                self.position += 1
                self._try_select_current(if_yes_callback, if_no_callback)

            self._item_check_playable(item_info, if_yes_callback, _if_no)

        else:
            if self.is_playing:
                self.stop(save_resume_time=False)
            if_no_callback()

    def _item_check_playable(self, item_info, yes_callback, no_callback):
        path = item_info.video_path
        if not os.path.exists(path):
            no_callback()
            return

        widgetset.can_play_file(path, yes_callback, no_callback)

    def get_playing_item(self):
        if self.playlist:
            return self.playlist[self.position]
        return None

    def _select_current(self):
        volume = config.get(prefs.VOLUME_LEVEL)
        item_info = self.playlist[self.position]
        self.video_display.setup(item_info, volume)
        if self.detached_window is not None:
            self.detached_window.set_title(item_info.name)
        self.schedule_mark_as_watched()

    def _play_current(self):
        if self.is_playing:
            def if_yes():
                self._select_current()
                self.play()
            self._try_select_current(if_yes, lambda:1)

    def play_next_movie(self, save_current_resume_time=True):
        self.cancel_update_timer()
        self.cancel_mark_as_watched()
        if config.get(prefs.SINGLE_VIDEO_PLAYBACK_MODE) or (self.position == len(self.playlist) - 1):
            self.stop(save_current_resume_time)
        else:
            if save_current_resume_time:
                self.update_current_resume_time()
            self.position += 1
            self._play_current()

    def play_prev_movie(self, save_current_resume_time=True):
        self.cancel_update_timer()
        self.cancel_mark_as_watched()
        if config.get(prefs.SINGLE_VIDEO_PLAYBACK_MODE):
            self.stop()
        else:
            if save_current_resume_time:
                self.update_current_resume_time()
            self.position -= 1
            self._play_current()

    def skip_forward(self):
        self.video_display.skip_forward()

    def skip_backward(self):
        self.video_display.skip_backward()

    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        self.video_display.enter_fullscreen()
        self.is_fullscreen = True
    
    def exit_fullscreen(self):
        self.video_display.exit_fullscreen()
        self.is_fullscreen = False

    def toggle_detached_mode(self):
        if self.is_fullscreen:
            return
        if self.detached_window is None:
            self.switch_to_detached_playback()
        else:
            self.switch_to_attached_playback()
        app.menu_manager.handle_playing_selection()
            
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


class DetachedWindow (widgetset.Window):

    def __init__(self, title, rect):
        widgetset.Window.__init__(self, title, rect)
        self.closing = False

    def close(self, stop_playback=True):
        if not self.closing:
            self.closing = True
            if stop_playback:
                app.playback_manager.stop()
            widgetset.Window.close(self)
