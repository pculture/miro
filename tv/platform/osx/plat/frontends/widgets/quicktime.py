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
from miro import prefs
from miro import config
from miro import player
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
    timeScale = qttimescale(qttime)
    if timeScale == 0:
        return 0.0
    timeValue = qttimevalue(qttime)
    return timeValue / float(timeScale)

def qttimescale(qttime):
    if isinstance(qttime, tuple):
        return qttime[1]
    else:
        return qttime.timeScale

def qttimevalue(qttime):
    if isinstance(qttime, tuple):
        return qttime[0]
    else:
        return qttime.timeValue

###############################################################################
# The QTMediaTypeSubtitle and QTMediaTypeClosedCaption media types are only
# available in OS X 10.6 so we emulate them if they aren't defined.

try:
    dummy = QTMediaTypeSubtitle
except:
    QTMediaTypeSubtitle = u'sbtl'

try:
    dummy = QTMediaTypeClosedCaption
except:
    QTMediaTypeClosedCaption = u'clcp'

###############################################################################

class Player(player.Player):

    def __init__(self, supported_media_types):
        player.Player.__init__(self)
        self.supported_media_types = supported_media_types
        self.movie_notifications = None
        self.movie = None

    def reset(self):
        threads.warn_if_not_on_main_thread('quicktime.Player.reset')
        if self.movie_notifications is not None:
            self.movie_notifications.disconnect()
        self.movie_notifications = None
        self.movie = None

    def set_item(self, item_info, callback, errback):
        threads.warn_if_not_on_main_thread('quicktime.Player.set_item')
        qtmovie = self.get_movie_from_file(item_info.video_path)
        self.reset()
        if qtmovie is not None:
            self.movie = qtmovie
            self.movie_notifications = NotificationForwarder.create(self.movie)
            self.movie_notifications.connect(self.handle_movie_notification, QTMovieDidEndNotification)
            self.setup_subtitles()
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
        duration = qttimevalue(qtmovie.duration())
        
        if qtmovie is not None and duration > 0:
            allTracks = qtmovie.tracks()
            if len(qtmovie.tracks()) > 0:
                # Make sure we have at least one track with a non zero length
                allMedia = [track.media() for track in allTracks]
                for media in allMedia:
                    mediaType = media.attributeForKey_(QTMediaTypeAttribute)
                    mediaDuration = qttimevalue(media.attributeForKey_(QTMediaDurationAttribute).QTTimeValue())
                    if mediaType in self.supported_media_types and mediaDuration > 0:
                        can_open = True
                        break

        return can_open
    
    def setup_subtitles(self):
        if config.get(prefs.ENABLE_SUBTITLES):
            default_track = self.get_enabled_subtitle_track()
            if default_track is None:
                tracks = self.get_subtitle_tracks()
                if len(tracks) > 0:
                    self.enable_subtitle_track(tracks[0])
        else:
            self.disable_subtitles()

    def get_subtitle_tracks(self):
        tracks = list()
        if self.movie is not None:
            for track in self.movie.tracks():
                if self.is_subtitle_track(track):
                    name = track.attributeForKey_(QTTrackDisplayNameAttribute)
                    is_enabled = track.attributeForKey_(QTTrackEnabledAttribute) == 1
                    tracks.append((name, is_enabled))
        return tracks

    def get_enabled_subtitle_track(self):
        if self.movie is not None:
            for track in self.movie.tracks():
                if self.is_subtitle_track(track):
                    if track.attributeForKey_(QTTrackEnabledAttribute) == 1:
                        return track
        return None

    def get_subtitle_track_by_name(self, name):
        if self.movie is not None:
            for track in self.movie.tracks():
                if self.is_subtitle_track(track):
                    if track.attributeForKey_(QTTrackDisplayNameAttribute) == track_name:
                        return track
        return None

    def is_subtitle_track(self, track):
        layer = track.attributeForKey_(QTTrackLayerAttribute)
        media_type = track.attributeForKey_(QTTrackMediaTypeAttribute)
        return (layer == -1 and media_type == QTMediaTypeVideo) or media_type in [QTMediaTypeSubtitle, QTMediaTypeClosedCaption]

    def enable_subtitle_track(self, track_name):
        current = self.get_enabled_subtitle_track()
        if current is not None:
            current.setAttribute_forKey_(0, QTTrackEnabledAttribute)
        to_enable = self.get_subtitle_track_by_name(track_name)
        if to_enable is not None:
            to_enable.setAttribute_forKey_(1, QTTrackEnabledAttribute)

    def disable_subtitles(self):
        track = self.get_enabled_subtitle_track()
        if track is not None:
            track.setAttribute_forKey_(0, QTTrackEnabledAttribute)

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
        if isinstance(qttime, tuple):
            qttime = (qttime[0] * position, qttime[1], qttime[2])
        else:
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
