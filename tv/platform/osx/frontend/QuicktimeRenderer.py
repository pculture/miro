import os
import glob
import logging

from objc import YES, NO, nil
from QTKit import *
from AppKit import *
from Foundation import *

import app
import prefs
import config
import qtcomp
import platformcfg
import platformutils
import download_utils

from gtcache import gettext as _

###############################################################################

SUPPORTED_VIDEO_MEDIA_TYPES = (QTMediaTypeVideo, QTMediaTypeMPEG, QTMediaTypeMovie, QTMediaTypeFlash)
SUPPORTED_AUDIO_MEDIA_TYPES = (QTMediaTypeSound, QTMediaTypeMusic)
ALL_SUPPORTED_MEDIA_TYPES   = SUPPORTED_VIDEO_MEDIA_TYPES + SUPPORTED_AUDIO_MEDIA_TYPES

###############################################################################

class QuicktimeRenderer (app.VideoRenderer):

    def __init__(self, delegate):
        app.VideoRenderer.__init__(self)
        self.view = nil
        self.movie = nil
        self.delegate = delegate
        self.cachedMovie = nil
        self.registerComponents()

    def registerComponents(self):
        bundlePath = platformcfg.getBundlePath()
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
            if platformutils.getMajorOSVersion <= 7:
                return False
        return True

    def registerMovieObserver(self, movie):
        platformutils.warnIfNotOnMainThread('QuicktimeRenderer.registerMovieObserver')
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self.delegate, 'handleMovieNotification:', QTMovieDidEndNotification, movie)

    def unregisterMovieObserver(self, movie):
        platformutils.warnIfNotOnMainThread('QuicktimeRenderer.unregisterMovieObserver')
        nc = NSNotificationCenter.defaultCenter()
        nc.removeObserver_name_object_(self.delegate, QTMovieDidEndNotification, movie)

    @platformutils.onMainThread
    def reset(self):
        if self.view is not nil:
            self.view.setMovie_(nil)
        self.unregisterMovieObserver(self.movie)
        self.view = nil
        self.movie = nil
        self.cachedMovie = nil

    @platformutils.onMainThreadWithReturn
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

    @platformutils.onMainThreadWaitingUntilDone
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
        osfilename = platformutils.filenameTypeToOSFilename(filename)
        url = NSURL.fileURLWithPath_(osfilename)
        if self.cachedMovie is not nil and self.cachedMovie.attributeForKey_(QTMovieURLAttribute) == url:
            qtmovie = self.cachedMovie
        else:
            (qtmovie, error) = QTMovie.alloc().initWithURL_error_(url)
            self.cachedMovie = qtmovie
        return qtmovie

    @platformutils.onMainThreadWithReturn
    def fillMovieData(self, filename, movie_data):
        osfilename = platformutils.filenameTypeToOSFilename(filename)
        (qtmovie, error) = QTMovie.movieWithFile_error_(osfilename)
        if qtmovie is not None:
            movie_data["duration"] = int(movieDuration(qtmovie) * 1000)
            if platformutils.getMajorOSVersion > 7:
                movie_data["screenshot"] = extractIcon(qtmovie, filename)
            del qtmovie
            return True
        return False

    @platformutils.onMainThread
    def play(self):
        self.view.play_(self)
        self.view.setNeedsDisplay_(YES)

    @platformutils.onMainThread
    def pause(self):
        self.view.pause_(nil)

    @platformutils.onMainThread
    def stop(self):
        self.view.pause_(nil)

    @platformutils.onMainThread
    def goToBeginningOfMovie(self):
        if self.movie is not nil:
            self.movie.gotoBeginning()

    def getDuration(self):
        return movieDuration(self.movie)

    def getCurrentTime(self):
        if self.movie is nil:
            return 0
        qttime = self.movie.currentTime()
        return _qttime2secs(qttime)

    @platformutils.onMainThread
    def setCurrentTime(self, time):
        platformutils.warnIfNotOnMainThread('QuicktimeRenderer.setCurrentTime')
        if self.movie is not nil:
            qttime = self.movie.currentTime()
            qttime.timeValue = time * float(qttime.timeScale)
            self.movie.setCurrentTime_(qttime)

    def getRate(self):
        if self.movie is nil:
            return 0.0
        return self.movie.rate()

    def setRate(self, rate):
        platformutils.warnIfNotOnMainThread('QuicktimeRenderer.setRate')
        if self.movie is not nil:
            self.movie.setRate_(rate)
        
    @platformutils.onMainThread
    def setVolume(self, level):
        if self.movie is not nil:
            self.movie.setVolume_(level)

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
    jpegData = platformutils.getResizedJPEGData(frame, 226.0, 170.0)

    try:
        target = os.path.join (config.get(prefs.ICON_CACHE_DIRECTORY), "extracted")
        iconFilename = os.path.basename(filename) + '.jpg'
        iconFilename = download_utils.saveData(target, iconFilename, jpegData)
    except:
        return ""

    return iconFilename

###############################################################################
