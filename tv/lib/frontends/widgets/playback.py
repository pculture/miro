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

import logging
import os

from miro import app
from miro import prefs
from miro import config
from miro import signals
from miro import messages
from miro import filetypes

from miro.gtcache import gettext as _
from miro.plat.frontends.widgets import timer
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets.displays import VideoDisplay
from miro.frontends.widgets import menus
from miro.frontends.widgets import dialogs

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
        self.open_successful = False
        self.playlist = None
        self.position = 0
        self.mark_as_watched_timeout = None
        self.update_timeout = None
        self.presentation_mode = 'fit-to-bounds'
        self.create_signal('selecting-file')
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
        app.info_updater.item_changed_callbacks.add('manual', 'playback-list',
                self._on_items_changed)

    def _on_items_changed(self, message):
        if self.playlist is None:
            return
        deleted = message.removed[:]
        for info in message.changed:
            if info.id not in self.id_to_position:
                # item was removed from our playlist already
                continue
            if not info.downloaded:
                deleted.append(info.id)
            else:
                self.playlist[self.id_to_position[info.id]] = info
        if len(deleted) > 0:
            self._handle_items_deleted(deleted)

    def _handle_items_deleted(self, id_list):
        if self.playlist is None:
            return
        to_delete = []
        deleting_current = False
        # Figure out what which items are in our playlist.
        for id in id_list:
            try:
                pos = self.id_to_position[id]
            except KeyError:
                continue
            to_delete.append(pos)
            if pos == self.position:
                deleting_current = True
        if len(to_delete) == 0:
            return
        # Delete those items (we need to do it last to first)
        to_delete.sort(reverse=True)
        for pos in to_delete:
            del self.playlist[pos]
            if pos < self.position:
                self.position -= 1
        if self.position >= len(self.playlist):
            # we deleted the current movie and all the ones after it
            self.stop(save_resume_time=False)
        elif deleting_current:
            self.play_from_position(self.position, save_resume_time=False)
        if self.playlist is not None:
            # Recalculate id_to_position, since the playlist has changed
            self._calc_id_to_position()

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
    
    def play_pause(self):
        if not self.is_playing or self.is_paused:
            self.play()
        else:
            self.pause()
    
    def start_with_items(self, item_infos, presentation_mode='fit-to-bounds'):
        if self.is_playing:
            # If we get here and we are already playing something it most
            # certainly means that the currently playing item is an audio one
            # which leaves the UI free to start another item, so stop first.
            self.stop()
        self.playlist = []
        for info in item_infos:
            self._append_item(info)
        self.position = 0
        self._calc_id_to_position()
        self.presentation_mode = presentation_mode
        self._start_tracking_items()
        self._play_current()
        if self.presentation_mode != 'fit-to-bounds':
            self.fullscreen()

    def append_item(self, item_info):
        if self.playlist is None:
            raise ValueError("Can't append items when not playing")
        self._append_item(item_info)

    def _append_item(self, item_info):
        if not item_info.is_container_item:
            self.playlist.append(item_info)
        else:
            playlables = [i for i in item_info.children if i.is_playable]
            self.playlist.extend(playlables)

    def _start_tracking_items(self):
        id_list = [info.id for info in self.playlist]
        m = messages.TrackItemsManually('playback-list', id_list)
        m.send_to_backend()

    def _stop_tracking_items(self):
        m = messages.StopTrackingItems('manual', 'playback-list')
        m.send_to_backend()

    def _calc_id_to_position(self):
        self.id_to_position = dict((info.id, i) for i, info in
                enumerate(self.playlist))
    
    def prepare_attached_playback(self):
        self.emit('will-play-attached')
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
        self.emit('will-play-detached')
        detached_window_frame = config.get(prefs.DETACHED_WINDOW_FRAME)
        if detached_window_frame is None:
            detached_window_frame = widgetset.Rect(0, 0, 800, 600)
        else:
            detached_window_frame = widgetset.Rect.from_string(detached_window_frame)
        title = self.playlist[self.position].name
        self.detached_window = DetachedWindow(title, detached_window_frame)
        self.align = widgetset.DetachedWindowHolder()
        self.align.add(self.video_display.widget)
        self.detached_window.set_content_widget(self.align)
        self.detached_window.show()
    
    def finish_detached_playback(self):
        # this prevents negative x and y values from getting saved
        coords = str(self.detached_window.get_frame())
        coords = ",".join([str(max(0, int(c))) for c in coords.split(",")])
        config.set(prefs.DETACHED_WINDOW_FRAME, coords)
        config.save()
        self.align.remove()
        self.align = None
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
        if self.player is not None:
            elapsed = self.player.get_elapsed_playback_time()
            total = self.player.get_total_playback_time()
            self.emit('playback-did-progress', elapsed, total)

    def on_display_removed(self, display):
        if not self.removing_video_display:
            self.stop()

    def play(self, start_at=0):
        if not self.player:
            return
        duration = self.player.get_total_playback_time()
        self.emit('will-play', duration)
        resume_time = self.playlist[self.position].resume_time
        if start_at > 0:
            self.player.play_from_time(start_at)
        elif (config.get(prefs.RESUME_VIDEOS_MODE)
               and not self.is_paused):
            self.player.play_from_time(resume_time)
        else:
            self.player.play()
        self.notify_update()
        self.schedule_update()
        self.is_paused = False
        self.is_suspended = False
        app.menu_manager.update_menus()

    def pause(self):
        if self.is_playing:
            self.emit('will-pause')
            self.player.pause()
            self.is_paused = True
            app.menu_manager.update_menus()

    def fullscreen(self):
        if not self.is_playing:
            return
        self.emit('will-fullscreen')
        self.toggle_fullscreen()

    def stop(self, save_resume_time=True):
        if not self.is_playing:
            return
        self._stop_tracking_items()
        if save_resume_time:
            self.update_current_resume_time()
        self.cancel_update_timer()
        self.cancel_mark_as_watched()
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
        self.position = 0
        self.playlist = None
        self.emit('did-stop')

    def remove_video_display(self):
        self.removing_video_display = True
        if self.detached_window is not None:
            self.video_display.cleanup()
            self.finish_detached_playback()
        else:
            self.finish_attached_playback()
        self.removing_video_display = False

    def update_current_resume_time(self, resume_time=-1):
        if not self.open_successful or self.player is None:
            return
        item_info = self.playlist[self.position]
        if config.get(prefs.RESUME_VIDEOS_MODE):
            if resume_time == -1:
                resume_time = self.player.get_elapsed_playback_time()
                # if we are 95% of the way into the movie and less than 30
                # seconds before the end, don't save resume time (#11956)
                if resume_time > min(item_info.duration * 0.95,
                        item_info.duration - 30):
                    resume_time = 0
            if resume_time < 3:
                # if we're in the first three seconds, don't save the
                # resume time.
                # Note: this should match mark_as_watched time.
                resume_time = 0
        else:
            resume_time = 0
        m = messages.SetItemResumeTime(item_info.id, resume_time)
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
        total = self.player.get_total_playback_time()
        if total is not None:
            self.emit('playback-did-progress', progress * total, total)

    def on_movie_finished(self):
        self.update_current_resume_time(0)
        self.play_next_item(False)

    def schedule_mark_as_watched(self, id_):
        # Note: mark_as_watched time should match the minimum resume
        # time in update_current_resume_time.
        self.mark_as_watched_timeout = timer.add(3, self.mark_as_watched, id_)

    def cancel_mark_as_watched(self):
        if self.mark_as_watched_timeout is not None:
            timer.cancel(self.mark_as_watched_timeout)
            self.mark_as_watched_timeout = None

    def mark_as_watched(self, id_):
        self.mark_as_watched_timeout = None
        # if we're in a state we don't think we should be in, then we don't
        # want to mark the item as watched.
        if not self.playlist or self.playlist[self.position].id != id_:
            logging.warning("mark_as_watched: not marking the item as watched because we're in a weird state")
            return
        messages.MarkItemWatched(id_).send_to_backend()

    def get_playing_item(self):
        if self.playlist:
            return self.playlist[self.position]
        return None

    def _setup_player(self, item_info, volume):
        def _handle_successful_sniff(item_type):
            self._finish_setup_player(item_info, item_type, volume)
        def _handle_unsuccessful_sniff():
            self._finish_setup_player(item_info, "unplayable", volume)
        if item_info.media_type_checked:
            type = item_info.file_type
            if type == 'other':
                # the backend and frontend use different names for this
                type = 'unplayable'
            self._finish_setup_player(item_info, type, volume)
        else:
            widgetset.get_item_type(item_info, _handle_successful_sniff, _handle_unsuccessful_sniff)
    
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
            self.video_display.setup(item_info, volume)
            if self.detached_window is not None:
                self.detached_window.set_title(item_info.name)
        self.emit('did-start-playing')
        app.menu_manager.update_menus()

    def _build_video_player(self, item_info, volume):
        self.player = widgetset.VideoPlayer()
        self.video_display = VideoDisplay(self.player)
        self.video_display.connect('removed', self.on_display_removed)
        self.video_display.connect('cant-play', self._on_cant_play)
        self.video_display.connect('ready-to-play', self._on_ready_to_play)
        if config.get(prefs.PLAY_DETACHED):
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

    def _select_current(self):
        item_info = self.playlist[self.position]
        if not config.get(prefs.PLAY_IN_MIRO):
            if self.is_playing:
                self.player.stop()
                self.player = None
                if self.video_display is not None:
                    self.remove_video_display()
                    self.video_display = None
            # FIXME - do this to avoid "currently playing green thing.
            # should be a better way.
            self.playlist = None
            app.widgetapp.open_file(item_info.video_path)
            messages.MarkItemWatched(item_info.id).send_to_backend()
            return

        volume = config.get(prefs.VOLUME_LEVEL)
        self.emit('selecting-file', item_info)
        self.open_successful = False
        self._setup_player(item_info, volume)

    def _play_current(self, new_position=None, save_resume_time=True):
        """If you pass in new_position, then this will attempt to play
        that and will update self.position ONLY if the new_position
        doesn't exceed the bounds of the playlist.
        """
        if new_position == None:
            new_position = self.position

        self.cancel_update_timer()
        self.cancel_mark_as_watched()
        if self.playlist is not None and (0 <= new_position < len(self.playlist)):
            self.position = new_position
            if self.is_playing:
                self.player.stop(True)
            self._select_current()
        else:
            self.stop(save_resume_time)

    def _on_ready_to_play(self, obj):
        self.open_successful = True
        self.schedule_mark_as_watched(self.playlist[self.position].id)
        if isinstance(self.player, widgetset.VideoPlayer):
            self.player.select_subtitle_encoding(self.initial_subtitle_encoding)
        self.play()

    def _on_cant_play(self, obj):
        self.emit('cant-play-file')
        if isinstance(obj, widgetset.AudioPlayer):
            self.play_next_item(False)

    def play_next_item(self, save_resume_time=True):
        self.play_from_position(self.position + 1, save_resume_time)

    def play_prev_item(self, save_resume_time=True, from_user=False):
        """
        :param save_resume_time: whether or not to save the resume
                                 time of the currently playing item
                                 before switching to the previous
                                 item.
        :param from_user: whether or not play_prev_item is being
                          called as a resume of the user pressing a
                          'prev' button or menu item.
        """
        # if the user pressed a prev button or menu item and the
        # current elapsed time is 3 seconds or greater, then we seek
        # to the beginning of the item.
        #
        # otherwise, we move to the previous item in the play list.
        if from_user:
            current_time = self.player.get_elapsed_playback_time()
            if current_time > 3:
                self.seek_to(0)
                return

        self.play_from_position(self.position - 1, save_resume_time)

    def play_from_position(self, new_position, save_resume_time=True):
        self.cancel_update_timer()
        self.cancel_mark_as_watched()
        if config.get(prefs.SINGLE_VIDEO_PLAYBACK_MODE):
            self.stop(save_resume_time)
        else:
            if save_resume_time:
                self.update_current_resume_time()
            self._play_current(new_position, save_resume_time)

    def skip_forward(self):
        self.player.skip_forward()

    def skip_backward(self):
        self.player.skip_backward()

    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        self.is_fullscreen = True
        self.video_display.enter_fullscreen()
    
    def exit_fullscreen(self):
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
        app.menu_manager.update_menus()
            
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
            item_info = self.playlist[self.position]
            self.player.select_subtitle_encoding(encoding)
            messages.SetItemSubtitleEncoding(item_info.id,
                    encoding).send_to_backend()

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
        if set([menus.MOD, menus.SHIFT]) == mods:
            if key in ('>', '.'): # OS X sends '.', GTK sends '>'
                app.widgetapp.on_forward_clicked()
                return True
            elif key in ('<', ','): # OS X sends ',', GTK sends '<'
                app.widgetapp.on_previous_clicked()
                return True

        if set([menus.SHIFT]) == mods:
            if key == menus.RIGHT_ARROW:
                app.widgetapp.on_skip_forward()
                return True
            elif key == menus.LEFT_ARROW:
                app.widgetapp.on_skip_backward()
                return True

        if set([menus.CTRL]) == mods and key == menus.SPACE:
            app.playback_manager.play_pause()
            return True
        return False

    if key == menus.ESCAPE:
        if app.playback_manager.is_fullscreen:
            app.widgetapp.on_fullscreen_clicked()
            return True
        else:
            app.widgetapp.on_stop_clicked()
            return True

    # anything after this point doesn't work when we're playing
    # audio
    if app.playback_manager.is_playing_audio:
        return False

    if key == menus.RIGHT_ARROW:
        app.widgetapp.on_skip_forward()
        return True

    if key == menus.LEFT_ARROW:
        app.widgetapp.on_skip_backward()
        return True

    if key == menus.UP_ARROW:
        app.widgetapp.up_volume()
        return True

    if key == menus.DOWN_ARROW:
        app.widgetapp.down_volume()
        return True

    if key == menus.SPACE:
        app.playback_manager.play_pause()
        return True
