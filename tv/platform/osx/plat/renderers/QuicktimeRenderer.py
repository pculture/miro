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

import os
import sys
import glob
import logging

from objc import YES, NO, nil
from QTKit import *
from AppKit import *
from Foundation import *

from miro import util
from miro import prefs
from miro import config
from miro.plat import qtcomp
from miro.plat import bundle
from miro.plat.utils import getMajorOSVersion, filenameTypeToOSFilename, getResizedJPEGData
from miro import download_utils
from miro.plat.frontends.html import threads

from miro.gtcache import gettext as _

###############################################################################

SUPPORTED_VIDEO_MEDIA_TYPES = (QTMediaTypeVideo, QTMediaTypeMPEG, QTMediaTypeMovie, QTMediaTypeFlash)
SUPPORTED_AUDIO_MEDIA_TYPES = (QTMediaTypeSound, QTMediaTypeMusic)
ALL_SUPPORTED_MEDIA_TYPES   = SUPPORTED_VIDEO_MEDIA_TYPES + SUPPORTED_AUDIO_MEDIA_TYPES

###############################################################################

class QuicktimeRenderer:

    def __init__(self, delegate):
        self.view = nil
        self.movie = nil
        self.delegate = delegate
        self.cachedMovie = nil
        self.interactivelySeeking = False
        self.registerComponents()

    def registerComponents(self):
        bundlePath = bundle.getBundlePath()
        componentsDirectoryPath = os.path.join(bundlePath, 'Contents', 'Components')
        components = glob.glob(os.path.join(componentsDirectoryPath, '*.component'))
        for component in components:
            cmpName = os.path.basename(component)
            if self.checkComponentCompatibility(cmpName):
                ok = qtcomp.register(component.encode('utf-8'))
                if ok:
                    logging.info('Successfully registered embedded component: %s' % cmpName)
                else:
                    logging.warn('Error while registering embedded component: %s' % cmpName)

    def checkComponentCompatibility(self, name):
        if "Perian" in name or "AC3" in name or "A52" in name:
            if getMajorOSVersion() <= 7:
                return False
        return True

    def registerMovieObserver(self, movie):
        threads.warnIfNotOnMainThread('QuicktimeRenderer.registerMovieObserver')
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self.delegate, 'handleMovieNotification:', QTMovieDidEndNotification, movie)

    def unregisterMovieObserver(self, movie):
        threads.warnIfNotOnMainThread('QuicktimeRenderer.unregisterMovieObserver')
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_name_object_(self.delegate, QTMovieDidEndNotification, movie)

    @threads.onMainThread
    def reset(self):
        if self.view is not nil:
            self.view.setMovie_(nil)
        self.unregisterMovieObserver(self.movie)
        self.view = nil
        self.movie = nil
        self.cachedMovie = nil

    @threads.onMainThreadWithReturn
    def canPlayFile(self, filename):
        canPlay = False
        qtmovie = self.getMovieFromFile(filename)

        # Purely referential movies have a no duration, no track and need to be 
        # streamed first. Since we don't support this yet, we delegate the 
        # streaming to the standalone QT player to avoid any problem (like the 
        # crash in #944) by simply declaring that we can't play the corresponding item.
        # Note that once the movie is fully streamed and cached by QT, DTV will
        # be able to play it internally just fine -- luc
        
        # [UPDATE - 26 Feb, 2006]
        # Actually, streaming movies *can* have tracks as shown in #1124. We
        # therefore need to drill down and find out if we have a zero length
        # video track/media.
        
        if qtmovie is not nil and qtmovie.duration().timeValue > 0:
            allTracks = qtmovie.tracks()
            if len(qtmovie.tracks()) > 0:
                # First make sure we have at least one video track with a non zero length
                allMedia = [track.media() for track in allTracks]
                for media in allMedia:
                    mediaType = media.attributeForKey_(QTMediaTypeAttribute)
                    mediaDuration = media.attributeForKey_(QTMediaDurationAttribute).QTTimeValue().timeValue
                    if mediaType in ALL_SUPPORTED_MEDIA_TYPES and mediaDuration > 0:
                        canPlay = True
                        break
        else:
            self.cachedMovie = nil

        return canPlay

    @threads.onMainThreadWaitingUntilDone
    def selectFile(self, filename):
        qtmovie = self.getMovieFromFile(filename)
        self.reset()
        if qtmovie is not nil:
            self.movie = qtmovie
            self.view = PlaybackView.alloc().init()
            self.view.setMovie_(self.movie)
            self.view.setNeedsDisplay_(YES)
            self.registerMovieObserver(qtmovie)

    def getMovieFromFile(self, filename):
        osfilename = filenameTypeToOSFilename(filename)
        url = NSURL.fileURLWithPath_(osfilename)
        if self.cachedMovie is not nil and self.cachedMovie.attributeForKey_(QTMovieURLAttribute) == url:
            qtmovie = self.cachedMovie
        else:
            (qtmovie, error) = QTMovie.alloc().initWithURL_error_(url)
            self.cachedMovie = qtmovie
        return qtmovie

    @threads.onMainThreadWithReturn
    def fillMovieData(self, filename, movie_data):
        logging.info("Processing movie %s" % filename)
        osfilename = filenameTypeToOSFilename(filename)
        (qtmovie, error) = QTMovie.movieWithFile_error_(osfilename)
        if qtmovie is not None:
            movie_data["duration"] = int(movieDuration(qtmovie) * 1000)
            if getMajorOSVersion() > 7:
                movie_data["screenshot"] = extractIcon(qtmovie, filename)
            del qtmovie
            return True
        return False

    @threads.onMainThread
    def play(self):
        self.view.play_(self)
        self.view.setNeedsDisplay_(YES)

    @threads.onMainThread
    def pause(self):
        self.view.pause_(nil)

    @threads.onMainThread
    def stop(self):
        self.view.pause_(nil)

    @threads.onMainThread
    def goToBeginningOfMovie(self):
        if self.movie is not nil:
            self.movie.gotoBeginning()

    def getDisplayTime(self, callback = None):
        if callback is None:
            logging.warn("using deprecated VideoRenderer.getDisplayTime(). Please, update your code")
            return ""
        else:
            self.getCurrentTime(lambda secs : callback(util.formatTimeForUser(secs)))

    def getDisplayDuration(self, callback = None):
        if callback is None:
            logging.warn("using deprecated VideoRenderer.getDisplayDuration(). Please, update your code")
            return ""
        else:
            self.getDuration(lambda secs : callback(util.formatTimeForUser(secs)))

    def getDisplayRemainingTime(self, callback = None):
        def startCallbackChain():
            self.getDuration(durationCallback)
        def durationCallback(duration):
            self.getCurrentTime(lambda ct: currentTimeCallback(ct, duration))
        def currentTimeCallback(currentTime, duration):
            callback(util.formatTimeForUser(abs(currentTime-duration), -1))
        if callback is None:
            logging.warn("using deprecated VideoRenderer.getDisplayRemainingTime(). Please, update your code")
            return ""
        else:
            startCallbackChain()

    def getProgress(self, callback = None):
        def startCallbackChain():
            self.getDuration(durationCallback)
        def durationCallback(duration):
            self.getCurrentTime(lambda ct: currentTimeCallback(ct, duration))
        def currentTimeCallback(currentTime, duration):
            if currentTime == 0 or duration == 0:
                callback(0.0)
            else:
                callback(currentTime / duration)
        if callback is None:
            logging.warn("using deprecated VideoRenderer.getProgress(). Please, update your code")
            return 0.0
        else:
            startCallbackChain()

    def getDuration(self, callback):
        callback(movieDuration(self.movie))

    def getCurrentTime(self, callback):
        if self.movie is nil:
            callback(0)
        else:
            qttime = self.movie.currentTime()
            callback(_qttime2secs(qttime))

    @threads.onMainThread
    def setCurrentTime(self, time):
        threads.warnIfNotOnMainThread('QuicktimeRenderer.setCurrentTime')
        if self.movie is not nil:
            qttime = self.movie.currentTime()
            qttime.timeValue = time * float(qttime.timeScale)
            self.movie.setCurrentTime_(qttime)

    def setProgress(self, progress):
        if progress > 1.0:
            progress = 1.0
        if progress < 0.0:
            progress = 0.0
        self.getDuration(lambda x: self.setCurrentTime(x*progress))

    def selectItem(self, anItem):
        self.selectFile (anItem.getVideoFilename())

    def getRate(self, callback):
        if self.movie is nil:
            callback(0.0)
        else:
            callback(self.movie.rate())

    def setRate(self, rate):
        threads.warnIfNotOnMainThread('QuicktimeRenderer.setRate')
        if self.movie is not nil:
            self.movie.setRate_(rate)

    def playFromTime(self, position):
        self.play()
        self.setCurrentTime(position)
        
    @threads.onMainThread
    def setVolume(self, level):
        if self.movie is not nil:
            self.movie.setVolume_(level)

    def movieDataProgramInfo(self, moviePath, thumbnailPath):
        py_exe_path = os.path.join(os.path.dirname(NSBundle.mainBundle().executablePath()), 'python')
        rsrc_path = NSBundle.mainBundle().resourcePath()
        script_path = os.path.join(rsrc_path, 'qt_extractor.py')
        options = NSBundle.mainBundle().infoDictionary().get('PyOptions')
        env = None
        if options['alias'] == 1:
            env = {'PYTHONPATH': ':'.join(sys.path)}
        else:
            env = {'PYTHONHOME': rsrc_path}
        return ((py_exe_path, script_path, moviePath, thumbnailPath), env)

###############################################################################

class PlaybackView (QTMovieView):
    
    def init(self):
        self = super(PlaybackView, self).initWithFrame_(((0,0),(100,100)))
        self.setFillColor_(NSColor.blackColor())
        self.setControllerVisible_(NO)
        self.setEditable_(NO)
        self.setPreservesAspectRatio_(YES)
        self.headlineAttributes = {
            NSForegroundColorAttributeName: NSColor.whiteColor(),
            NSFontAttributeName: NSFont.fontWithName_size_(u'Lucida Grande', 18)
        }
        return self
        
    def drawRect_(self, rect):
        if self.isAudioOnly():
            self.drawForAudioPlayback(rect)
        else:
            super(PlaybackView, self).drawRect_(rect)
    
    def drawForAudioPlayback(self, rect):
        NSColor.blackColor().set()
        NSRectFill(rect)
        headline = NSString.stringWithString_(_(u'Audio'))
        headlineRect = headline.boundingRectWithSize_options_attributes_(rect.size, 0, self.headlineAttributes)
        x = (rect.size.width - headlineRect.size.width) / 2
        y = (rect.size.height - headlineRect.size.height) / 2
        headline.drawAtPoint_withAttributes_((x, y), self.headlineAttributes)

    def isAudioOnly(self):
        audioOnly = False
        movie = self.movie()
        if movie is not None:
            allTracks = movie.tracks()
            allMedia = [track.media() for track in allTracks]
            allTypes = [media.attributeForKey_(QTMediaTypeAttribute) for media in allMedia]
            hasAudioTrack = True in [mtype in SUPPORTED_AUDIO_MEDIA_TYPES for mtype in allTypes]
            hasVideoTrack = True in [mtype in SUPPORTED_VIDEO_MEDIA_TYPES for mtype in allTypes]
            audioOnly = hasAudioTrack and not hasVideoTrack
        return audioOnly
            
###############################################################################

def _qttime2secs(qttime):
    if qttime.timeScale == 0:
        return 0.0
    return qttime.timeValue / float(qttime.timeScale)

def movieDuration(qtmovie):
    if qtmovie is nil:
        return 0
    qttime = qtmovie.duration()
    return _qttime2secs(qttime)

###############################################################################

def extractIcon(qtmovie, filename):
    if qtmovie is None:
        return ""

    qttime = qtmovie.duration()
    qttime.timeValue *= .5
    frame = qtmovie.frameImageAtTime_(qttime)
    if frame is None:
        return ""

    frameSize = frame.size()
    if frameSize.width == 0 or frameSize.height == 0:
        return ""

    frameRatio = frameSize.width / frameSize.height
    jpegData = getResizedJPEGData(frame, 226.0, 170.0)

    if jpegData is not None:
        try:
            target = os.path.join (config.get(prefs.ICON_CACHE_DIRECTORY), "extracted")
            iconFilename = os.path.basename(filename) + '.jpg'
            iconFilename = download_utils.saveData(target, iconFilename, jpegData)
        except:
            return ""
    else:
        return ""

    return iconFilename

###############################################################################
