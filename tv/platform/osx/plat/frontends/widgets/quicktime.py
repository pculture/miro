# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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
import glob
import logging

from Foundation import *
from QTKit import *

from miro import app
from miro.plat import utils
from miro.plat import bundle
from miro.plat import qtcomp
from miro.plat.frontends.widgets import threads
from miro.plat.frontends.widgets.helpers import NotificationForwarder

###############################################################################

def register_components():
    bundlePath = bundle.getBundlePath()
    componentsDirectoryPath = os.path.join(bundlePath, 'Contents', 'Components')
    components = glob.glob(os.path.join(componentsDirectoryPath, '*.component'))
    for component in components:
        cmpName = os.path.basename(component)
        ok = qtcomp.register(component.encode('utf-8'))
        if ok:
            logging.info('Successfully registered embedded component: %s' % cmpName)
        else:
            logging.warn('Error while registering embedded component: %s' % cmpName)

###############################################################################

def qttime2secs(qttime):
    if qttime.timeScale == 0:
        return 0.0
    return qttime.timeValue / float(qttime.timeScale)

###############################################################################

class Player(object):

    def __init__(self, supported_media_types):
        self.supported_media_types = supported_media_types
        self.movie_notifications = None
        self.movie = None

    def reset(self):
        threads.warn_if_not_on_main_thread('quicktime.Player.reset')
        if self.movie_notifications is not None:
            self.movie_notifications.disconnect()
        self.movie_notifications = None
        self.movie = None

    def set_movie_item(self, item_info, callback, errback):
        threads.warn_if_not_on_main_thread('quicktime.Player.set_movie_item')
        qtmovie = self.get_movie_from_file(item_info.video_path)
        self.reset()
        if qtmovie is not None:
            self.movie = qtmovie
            self.movie_notifications = NotificationForwarder.create(self.movie)
            self.movie_notifications.connect(self.handle_movie_notification, QTMovieDidEndNotification)
            callback()
        else:
            errback()

    def get_movie_from_file(self, path):
        osfilename = utils.filenameTypeToOSFilename(path)
        url = NSURL.fileURLWithPath_(osfilename)
        if utils.get_pyobjc_major_version() == 2:
            qtmovie, error = QTMovie.movieWithURL_error_(url, None)
        else:
            qtmovie, error = QTMovie.movieWithURL_error_(url)
        if not self.can_open_file(qtmovie):
            return None
        return qtmovie

    def can_open_file(self, qtmovie):
        threads.warn_if_not_on_main_thread('quicktime.Player.can_open_file')
        can_open = False

        if qtmovie is not None and qtmovie.duration().timeValue > 0:
            allTracks = qtmovie.tracks()
            if len(qtmovie.tracks()) > 0:
                # Make sure we have at least one track with a non zero length
                allMedia = [track.media() for track in allTracks]
                for media in allMedia:
                    mediaType = media.attributeForKey_(QTMediaTypeAttribute)
                    mediaDuration = media.attributeForKey_(QTMediaDurationAttribute).QTTimeValue().timeValue
                    if mediaType in self.supported_media_types and mediaDuration > 0:
                        can_open = True
                        break

        return can_open

    def set_volume(self, volume):
        if self.movie:
            self.movie.setVolume_(volume)

    def get_elapsed_playback_time(self):
        qttime = self.movie.currentTime()
        return qttime2secs(qttime)

    def get_total_playback_time(self):
        if self.movie is None:
            return 0
        qttime = self.movie.duration()
        return qttime2secs(qttime)

    def skip_forward(self):
        current = self.get_elapsed_playback_time()
        duration = self.get_total_playback_time()
        pos = min(duration, current + 30.0)
        self.seek_to(pos / duration)

    def skip_backward(self):
        current = self.get_elapsed_playback_time()
        duration = self.get_total_playback_time()
        pos = max(0, current - 15.0)
        self.seek_to(pos / duration)

    def seek_to(self, position):
        qttime = self.movie.duration()
        qttime.timeValue = qttime.timeValue * position
        self.movie.setCurrentTime_(qttime)

    def play_from_time(self, resume_time=0):
        self.seek_to(resume_time / self.get_total_playback_time())
        self.play()

    def set_playback_rate(self, rate):
        self.movie.setRate_(rate)

    def handle_movie_notification(self, notification):
        if notification.name() == QTMovieDidEndNotification and not app.playback_manager.is_suspended:
            app.playback_manager.on_movie_finished()

###############################################################################
