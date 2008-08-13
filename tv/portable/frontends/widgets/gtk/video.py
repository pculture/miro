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

"""video.py -- Video code. """

import gtk

from miro import app
from miro.frontends.widgets.gtk.widgetset import Widget

class NullRenderer(object):
    def can_play_file(self, path):
        return False

    def reset(self):
        pass

class VideoRenderer (Widget):
    """Video renderer widget.  NOTE app.renderer must be initialized before
    instantiating this class.  If no renderers can be found, set app.renderer
    to None.
    """

    def __init__(self):
        Widget.__init__(self)
        if app.renderer is not None:
            self.renderer = app.renderer
        else:
            self.renderer = NullRenderer()
        self.set_widget(gtk.DrawingArea())
        self._widget.set_double_buffered(False)
        self._widget.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.renderer.set_widget(self._widget)

    def teardown(self):
        self.renderer.reset()
    
    def can_play_movie_file(self, path):
        return self.renderer.can_play_file(path)
    
    def set_movie_file(self, path):
        self.renderer.select_file(path)

    def get_elapsed_playback_time(self):
        # FIXME, why use a callback here?
        return self.renderer.get_current_time()

    def get_total_playback_time(self):
        return self.renderer.get_duration()

    def set_volume(self, volume):
        pass

    def play(self):
        self.renderer.play()

    def pause(self):
        self.renderer.pause()

    def stop(self):
        self.renderer.stop()

    def seek_to(self, position):
        time = self.get_total_playback_time() * position
        self.renderer.set_current_time(time)

    def enter_fullscreen(self):
        pass

    def exit_fullscreen(self):
        pass
