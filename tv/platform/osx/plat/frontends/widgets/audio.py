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

from QTKit import *

from miro import signals
from miro import messages

from miro.plat.frontends.widgets import mediatypes
from miro.plat.frontends.widgets import threads
from miro.plat.frontends.widgets import quicktime

###############################################################################

SUPPORTED_MEDIA_TYPES = mediatypes.AUDIO_MEDIA_TYPES

###############################################################################

class AudioPlayer(quicktime.Player):

    def __init__(self):
        quicktime.Player.__init__(self, SUPPORTED_MEDIA_TYPES)

    def play(self):
        threads.warn_if_not_on_main_thread('AudioPlayer.play')
        if self.movie is not None:
            self.movie.play()

    def pause(self):
        threads.warn_if_not_on_main_thread('AudioPlayer.pause')
        if self.movie is not None:
            self.movie.stop()

    def stop(self, will_play_another=False):
        if self.movie is not None:
            self.movie.stop()
        self.reset()

###############################################################################
