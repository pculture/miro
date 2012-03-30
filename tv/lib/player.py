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

from miro import signals
from miro import messages

class Player(signals.SignalEmitter):
    def __init__(self):
        signals.SignalEmitter.__init__(self, 'cant-play', 'ready-to-play')
        self.item_info = None

    def setup(self, item_info, volume):
        self.item_info = item_info
        self.set_item(item_info, self._open_success, self._open_error)
        self.set_volume(volume)

    def _open_success(self):
        self.emit('ready-to-play')

    def _open_error(self):
        messages.MarkItemWatched(self.item_info).send_to_backend()
        self.emit('cant-play')

    def _seek(self, seek_to_func, args):
        if args is None:
            return False
        pos, duration = seek_to_func(*args)
        if duration <= 0:
            logging.warning('_seek: duration = %s', duration)
            return None
        self.seek_to(pos / duration)
        return True

    def _skip_args(self):
        current = self.get_elapsed_playback_time()
        duration = self.get_total_playback_time()
        if current is None or duration is None:
            logging.warning('cannot skip: current = %s duration = %s',
                            current, duration)
            return None
        return (current, duration)

    def _resume_at_args(self, resume):
        duration = self.get_total_playback_time()
        if duration is not None:
            logging.warn('_resume_at_args: duration is None')
            return None
        return (resume, duration)

    def _skip_forward_func(self, current, duration):
        return (min(duration, current + 30.0), duration)

    def _skip_backward_func(self, current, duration):
        return (max(0, current - 15.0), duration)

    def _resume_at_func(self, resume_time, duration):
        return (resume_time, duration)

    def skip_forward(self):
        args = self._skip_args()
        self._seek(self._skip_forward_func, args)

    def skip_backward(self):
        args = self._skip_args()
        self._seek(self._skip_backward_func, args)

    def play_from_time(self, resume_time=0):
        args = self._resume_at_args(resume)
        if self._seek(self._resume_at_func, args):
            self.play()

    def set_item(self, item_info, success_callback, error_callback):
        raise NotImplementedError()

    def set_volume(self, volume):
        raise NotImplementedError()

    def get_total_playback_time(self):
        raise NotImplementedError()

    def get_elapsed_playback_time(self):
        raise NotImplementedError()

    def seek_to(self, position):
        raise NotImplementedError()

    def play(self):
        raise NotImplementedError()
