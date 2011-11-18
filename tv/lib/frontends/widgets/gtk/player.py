# Miro - an RSS based video player application
# Copyright (C) 2011
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

from miro import player

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

class GTKPlayer(player.Player):
    """Audio/Video player base class."""

    def __init__(self, renderer):
        player.Player.__init__(self)
        if renderer is not None:
            self.renderer = renderer
        else:
            self.renderer = NullRenderer()

    def get_audio_tracks(self):
        track_count = self.renderer.get_audio_tracks()
        tracks = []
        for i in xrange(track_count):
            name = 'Track %s' % i
            tracks.append((i, name))
        return tracks

    def get_enabled_audio_track(self):
        return self.renderer.get_enabled_audio_track()

    def set_audio_track(self, track_index):
        self.renderer.set_audio_track(track_index)
