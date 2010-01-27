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

from miro import app
from miro import player
from miro import signals
from miro import messages

class NullRenderer:
    def __init__(self):
        pass

    def reset(self):
        pass

    def select_file(self, iteminfo, success_callback, error_callback):
        error_callback()

    def stop(self):
        pass

    def set_volume(self, v):
        pass

class AudioPlayer(player.Player):
    """Audio renderer widget.

    Note: ``app.audio_renderer`` must be inititalized before instantiating this
    class.  If no renderers can be found, set ``app.audio_renderer`` to ``None``.
    """
    def __init__(self):
        player.Player.__init__(self)
        if app.audio_renderer is not None:
            self.renderer = app.audio_renderer
        else:
            self.renderer = NullRenderer()

    def teardown(self):
        self.renderer.reset()

    def set_item(self, item_info, success_callback, error_callback):
        self.renderer.select_file(item_info, success_callback, error_callback)

    def play(self):
        self.renderer.play()

    def play_from_time(self, resume_time=0):
        self.seek_to_time(resume_time)
        self.play()

    def pause(self):
        self.renderer.pause()

    def stop(self, will_play_another=False):
        self.renderer.stop()

    def set_volume(self, volume):
        self.renderer.set_volume(volume)

    def get_elapsed_playback_time(self):
        return self.renderer.get_current_time()

    def get_total_playback_time(self):
        return self.renderer.get_duration()

    def seek_to(self, position):
        time = self.get_total_playback_time() * position
        self.seek_to_time(time)

    def seek_to_time(self, position):
        self.renderer.set_current_time(position)

    def set_playback_rate(self, rate):
        self.renderer.set_rate(rate)
