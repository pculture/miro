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

from miro import app
from miro import config
from miro import messages
from miro import prefs
from miro import signals
from miro.plat.frontends.widgets import timer
from miro.frontends.widgets.displays import VideoDisplay
#from miro.frontends.widgets.displays import AudioDisplay
#from miro.frontends.widgets.displays import ExternalVideoDisplay

class PlaybackManager (signals.SignalEmitter):
    
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.previous_left_width = 0
        self.video_display = None
        self.is_fullscreen = False
        self.is_playing = False
        self.is_paused = False
        self.is_suspended = False
        self.playlist = None
        self.position = None
        self.mark_as_watched_timeout = None
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
        self.video_display = VideoDisplay()
        self.video_display.connect('removed', self.on_display_removed)
        splitter = app.widgetapp.window.splitter
        self.previous_left_width = splitter.get_left_width()
        self.previous_left_widget = splitter.left
        splitter.remove_left()
        splitter.set_left_width(0)
        app.display_manager.push_display(self.video_display)
        app.menu_manager.handle_playing_selection()
        self.playlist = item_infos
        self.position = 0
        self._select_current()
        self.play()
    
    def schedule_update(self):
        def notify_and_reschedule():
            if self.is_playing and not self.is_paused:
                if not self.is_suspended:
                    self.notify_update()
                self.schedule_update()
        timer.add(0.5, notify_and_reschedule)

    def notify_update(self):
        if self.video_display is not None:
            elapsed = self.video_display.get_elapsed_playback_time()
            total = self.video_display.get_total_playback_time()
            self.emit('playback-did-progress', elapsed, total)

    def on_display_removed(self, display):
        self.stop()
    
    def play(self):
        duration = self.video_display.get_total_playback_time()
        self.emit('will-play', duration)
        resume_time = self.playlist[self.position].resume_time
        if config.get(prefs.RESUME_VIDEOS_MODE) and resume_time > 10:
            self.video_display.play_from_time(resume_time)
        else:
            self.video_display.play()
        self.notify_update()
        self.schedule_update()
        self.is_playing = True
        self.is_paused = False
        self.is_suspended = False

    def pause(self):
        if self.is_playing:
            self.emit('will-pause')
            self.video_display.pause()
            self.is_paused = True

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
        self.cancel_mark_as_watched()
        self.is_playing = False
        self.is_paused = False
        self.emit('will-stop')
        self.video_display.stop()
        app.display_manager.pop_display()
        app.widgetapp.window.splitter.set_left_width(self.previous_left_width)
        app.widgetapp.window.splitter.set_left(self.previous_left_widget)
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

    def _select_current(self):
        self.cancel_mark_as_watched()
        if self.is_playing:
            self.video_display.stop()
        if 0 <= self.position < len(self.playlist):
            item_info = self.playlist[self.position]
            volume = config.get(prefs.VOLUME_LEVEL)
            self.video_display.setup(item_info, volume)
            self.schedule_mark_as_watched()
        else:
            self.stop()

    def _play_current(self):
        self._select_current()
        if self.is_playing:
            self.video_display.play()

    def play_next_movie(self, save_current_resume_time=True):
        self.cancel_mark_as_watched()
        if config.get(prefs.SINGLE_VIDEO_PLAYBACK_MODE) or (self.position == len(self.playlist) - 1):
            self.stop(save_current_resume_time)
        else:
            self.position += 1
            self._play_current()

    def play_prev_movie(self):
        self.cancel_mark_as_watched()
        if config.get(prefs.SINGLE_VIDEO_PLAYBACK_MODE):
            self.stop()
        else:
            self.position -= 1
            self._play_current()

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
