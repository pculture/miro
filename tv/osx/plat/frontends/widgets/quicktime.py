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

import os
import glob
import logging

from objc import pathForFramework, loadBundleFunctions
from Foundation import *
from QTKit import *

from miro import app
from miro import prefs
from miro import player
from miro import iso639
from miro.gtcache import gettext as _
from miro.plat import utils
from miro.plat import qttimeutils
from miro.plat import bundle
from miro.plat import qtcomp
from miro.plat import script_codes
from miro.plat.frontends.widgets import threads
from miro.plat.frontends.widgets.helpers import NotificationForwarder
from miro.util import copy_subtitle_file

def register_components():
    bundlePath = bundle.getBundlePath()
    componentsDirectoryPath = os.path.join(bundlePath, 'Contents', 'Components')
    components = glob.glob(os.path.join(componentsDirectoryPath, '*.component'))
    for component in components:
        cmpName = os.path.basename(component)
        stdloc1 = os.path.join(os.path.sep, "Library", "Quicktime", cmpName)
        stdloc2 = os.path.join(os.path.sep, "Library", "Audio", "Plug-Ins",
                               "Components", cmpName)
        if not os.path.exists(stdloc1) and not os.path.exists(stdloc2):
            ok = qtcomp.register(component.encode('utf-8'))
            if ok:
                logging.debug('Successfully registered embedded component: %s',
                              cmpName)
            else:
                logging.warn('Error while registering embedded component: %s',
                             cmpName)
        else:
            logging.debug('Skipping embedded %s registration, '
                          'already installed.', cmpName)

###############################################################################

class WarmupProgressHandler(NSObject):
    def init(self):
        self = super(WarmupProgressHandler, self).init()
        self.complete = False
        return self
    def loadStateChanged_(self, notification):
        self.handleLoadStateForMovie_(notification.object())
    def handleInitialLoadStateForMovie_(self, movie):
        load_state = movie.attributeForKey_(QTMovieLoadStateAttribute).longValue()
        if load_state < QTMovieLoadStateComplete:
            NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
                warmup_handler, 
                'loadStateChanged:', 
                QTMovieLoadStateDidChangeNotification, 
                warmup_movie)
        else:
            self.handleLoadStateForMovie_(movie)
    def handleLoadStateForMovie_(self, movie):
        load_state = movie.attributeForKey_(QTMovieLoadStateAttribute).longValue()
        if load_state == QTMovieLoadStateComplete:
            logging.debug("QuickTime warm up complete")
            NSNotificationCenter.defaultCenter().removeObserver_(self)
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                10, self, 'releaseWarmupMovie:', None, False)
            self.complete = True
    def releaseWarmupMovie_(self, timer):
        logging.debug("Releasing warmup movie.")
        global warmup_movie
        del warmup_movie

warmup_handler = WarmupProgressHandler.alloc().init()
warmup_movie = None

def warm_up():
    logging.debug('Warming up QuickTime')
    rsrcPath = bundle.getBundleResourcePath()

    attributes = NSMutableDictionary.dictionary()
    attributes['QTMovieFileNameAttribute'] = os.path.join(rsrcPath,
                                                          'warmup.mov')
    attributes['QTMovieOpenAsyncRequiredAttribute'] = True
    attributes['QTMovieDelegateAttribute'] = None

    global warmup_movie
    warmup_movie, error = QTMovie.movieWithAttributes_error_(attributes, None)
    
    if error is not None:
        logging.warn("QuickTime Warm Up failed: %s" % error)
    else:
        warmup_handler.handleInitialLoadStateForMovie_(warmup_movie)

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
        self.callback = self.errback = None
        self.force_subtitles = False
        self.item_info = None

    def reset(self):
        threads.warn_if_not_on_main_thread('quicktime.Player.reset')
        if self.movie_notifications is not None:
            self.movie_notifications.disconnect()
        self.movie_notifications = None
        self.movie = None
        self.callback = self.errback = None
        self.force_subtitles = False

    def set_item(self, item_info, callback, errback, force_subtitles=False):
        threads.warn_if_not_on_main_thread('quicktime.Player.set_item')
        self.reset()
        qtmovie = self.get_movie_from_file(item_info.filename)
        self.callback = callback
        self.errback = errback
        self.force_subtitles = force_subtitles
        if qtmovie is not None:
            self.item_info = item_info
            self.movie = qtmovie
            self.movie_notifications = NotificationForwarder.create(self.movie)
            self.movie_notifications.connect(self.handle_movie_notification,
                QTMovieDidEndNotification)
            load_state = qtmovie.attributeForKey_(
                QTMovieLoadStateAttribute).longValue()
            # Only setup a deferred notification if we are unsure of status
            # anything else in movie_load_state_changed().
            if load_state in (QTMovieLoadStateLoading,
                                QTMovieLoadStateLoaded):
                self.movie_notifications.connect(
                    self.handle_movie_notification,
                    QTMovieLoadStateDidChangeNotification)
            else:
                # Playable right away or error - just call and don't disconnect
                # notification because it wasn't connected in the first place.
                self.movie_load_state_changed(disconnect=False)
        else:
            threads.call_on_ui_thread(errback)

    def get_movie_from_file(self, path):
        osfilename = utils.filename_type_to_os_filename(path)
        try:
            url = NSURL.URLWithString_(path.urlize())
        except AttributeError:
            url = NSURL.fileURLWithPath_(osfilename)
        attributes = NSMutableDictionary.dictionary()
        no = NSNumber.alloc().initWithBool_(NO)
        yes = NSNumber.alloc().initWithBool_(YES)
        attributes['QTMovieURLAttribute'] = url
        attributes['QTMovieOpenAsyncOKAttribute'] = yes
        # FIXME: Can't use yet qtmovie.tracks() not accessible.
        #attributes['QTMovieOpenForPlaybackAttribute'] = yes
        qtmovie, error = QTMovie.movieWithAttributes_error_(attributes, None)
        if error is not None:
            logging.debug(unicode(error).encode('utf-8'))
        if qtmovie is None or error is not None:
            return None
        return qtmovie

    def get_audio_tracks(self):
        tracks = list()
        if not self.movie:
            return tracks
        for i, track in enumerate(
          self.movie.tracksOfMediaType_(QTMediaTypeSound)):
            track_id = track.attributeForKey_(QTTrackIDAttribute)
            # To avoid crappy names encoded into files, use "Track %d (xxx)
            display_name = track.attributeForKey_(QTTrackDisplayNameAttribute)
            name = _("Track %(track)d (%(name)s)",
                {"track": i + 1, 
                 "name": display_name
                })
            tracks.append((track_id, name))
        return tracks

    def get_enabled_audio_track(self):
        if not self.movie:
            return None
        for track in self.movie.tracksOfMediaType_(QTMediaTypeSound):
            if track.attributeForKey_(QTTrackEnabledAttribute) == 1:
                return track.attributeForKey_(QTTrackIDAttribute)

    def set_audio_track(self, new_track_id):
        if not self.movie:
            return
        for track in self.movie.tracksOfMediaType_(QTMediaTypeSound):
            track_id = track.attributeForKey_(QTTrackIDAttribute)
            # In theory, you could have multiple enabled audio tracks, playing
            # at the same time but that'd be a bit silly?
            track.setEnabled_(new_track_id == track_id)

    def setup_subtitles(self, force_subtitles):
        if app.config.get(prefs.ENABLE_SUBTITLES) or force_subtitles:
            enabled_tracks = self.get_all_enabled_subtitle_tracks()
            if len(enabled_tracks) == 0:
                tracks = self.get_subtitle_tracks()
                if len(tracks) > 0:
                    self.set_subtitle_track(tracks[0][1])
            elif len(enabled_tracks) > 1:
                track_id = enabled_tracks[-1].attributeForKey_(QTTrackIDAttribute)
                self.disable_subtitles()
                self.set_subtitle_track(track_id)
        else:
            self.disable_subtitles()

    def get_subtitle_tracks(self):
        tracks = list()
        if self.movie is not None:
            for track in self.movie.tracks():
                if self.is_subtitle_track(track):
                    media = track.media().quickTimeMedia()
                    name = track.attributeForKey_(QTTrackDisplayNameAttribute)
                    track_id = track.attributeForKey_(QTTrackIDAttribute)
                    tracks.append((track_id, name))
        return tracks

    def get_enabled_subtitle_track(self):
        if self.movie is None:
            return None
        for track in self.movie.tracks():
            if (self.is_subtitle_track(track) and
                track.attributeForKey_(QTTrackEnabledAttribute) == 1):
                return track.attributeForKey_(QTTrackIDAttribute)
        return None

    def _find_track(self, key, value):
        if self.movie is not None:
            for track in self.movie.tracks():
                if self.is_subtitle_track(track):
                    if track.attributeForKey_(key) == value:
                        return track
        return None

    def _find_all_tracks(self, key, value):
        tracks = list()
        if self.movie is not None:
            for track in self.movie.tracks():
                if self.is_subtitle_track(track):
                    if track.attributeForKey_(key) == value:
                        tracks.append(track)
        return tracks

    def unset_subtitle_track(self):
        track = self._find_track(QTTrackEnabledAttribute, 1)
        if track is not None:
            track.setAttribute_forKey_(0, QTTrackEnabledAttribute)

    def get_all_enabled_subtitle_tracks(self):
        return self._find_all_tracks(QTTrackEnabledAttribute, 1)

    def get_subtitle_track_by_name(self, name):
        return self._find_track(QTTrackDisplayNameAttribute, name)

    def get_subtitle_track_by_id(self, track_id):
        return self._find_track(QTTrackIDAttribute, track_id)

    def is_subtitle_track(self, track):
        layer = track.attributeForKey_(QTTrackLayerAttribute)
        media_type = track.attributeForKey_(QTTrackMediaTypeAttribute)
        return (layer == -1 and media_type == QTMediaTypeVideo) or media_type in [QTMediaTypeSubtitle, QTMediaTypeClosedCaption]

    def set_subtitle_track(self, track_id):
        self.unset_subtitle_track()
        if track_id is None:
            return
        to_enable = self.get_subtitle_track_by_id(track_id)
        if to_enable is not None:
            to_enable.setAttribute_forKey_(1, QTTrackEnabledAttribute)
        app.menu_manager.update_menus('playback-changed')

    def disable_subtitles(self):
        tracks = self.get_all_enabled_subtitle_tracks()
        if len(tracks) > 0:
            for track in tracks:
                track.setAttribute_forKey_(0, QTTrackEnabledAttribute)

    def select_subtitle_file(self, sub_path, handle_successful_select):
        def handle_ok():
            handle_successful_select()
        def handle_err():
            app.playback_manager.stop()
        copy_subtitle_file(sub_path, self.item_info.filename)
        self.set_item(self.item_info, handle_ok, handle_err, True)

    def select_subtitle_encoding(self, encoding):
        # FIXME - set the subtitle encoding in quicktime
        pass

    def set_volume(self, volume):
        if self.movie:
            self.movie.setVolume_(volume)

    def get_elapsed_playback_time(self):
        if self.movie:
            qttime = self.movie.currentTime()
            return qttimeutils.qttime2secs(qttime)
        else:
            return 0

    def get_total_playback_time(self):
        if self.movie is None:
            return 0
        qttime = self.movie.duration()
        return qttimeutils.qttime2secs(qttime)

    def seek_to(self, position):
        if not self.movie:
            return
        qttime = self.movie.duration()
        if isinstance(qttime, tuple):
            qttime = (qttime[0] * position, qttime[1], qttime[2])
        else:
            qttime.timeValue = qttime.timeValue * position
        self.movie.setCurrentTime_(qttime)

    def set_playback_rate(self, rate):
        if self.movie:
            self.movie.setRate_(rate)

    def movie_load_state_changed(self, disconnect=True):
        callback = self.callback
        errback = self.errback
        force_subtitles = self.force_subtitles
        if not self.movie:
            logging.error('self.movie is not set')
            # We can only get here via the callback notification so no need
            # to check disconnect.
            self.movie_notifications.disconnect(
                QTMovieLoadStateDidChangeNotification)
            return
        load_state = self.movie.attributeForKey_(
            QTMovieLoadStateAttribute).longValue()
        if load_state == QTMovieLoadStateError:
            threads.call_on_ui_thread(errback)
        elif load_state == QTMovieLoadStateLoading:
            # Huh?  Shouldn't we start of as loading?  If so then what's
            # changed?
            pass
        elif load_state == QTMovieLoadStateLoaded:
            # We really want to be able to play it not just query properties.
            pass
        elif load_state in (QTMovieLoadStatePlayable,
                            QTMovieLoadStatePlaythroughOK,
                            QTMovieLoadStateComplete):
            # call the callback in an idle call, the rest of the Player code
            # expects it
            if disconnect:
                self.movie_notifications.disconnect(
                    QTMovieLoadStateDidChangeNotification)
            self.setup_subtitles(force_subtitles)
            tracks = self.movie.tracks()
            threads.call_on_ui_thread(callback)
        else:
            raise ValueError('Unknown QTMovieLoadStateAttribute value')

    def handle_movie_notification(self, notification):
        if notification.name() == QTMovieDidEndNotification and not app.playback_manager.is_suspended:
            app.playback_manager.on_movie_finished()
        if notification.name() == QTMovieLoadStateDidChangeNotification:
            if notification.object() != self.movie:
                logging.error('Stale notification received for '
                              'QTMovieLoadStateDidChangeNotification')
            self.movie_load_state_changed()

###############################################################################
