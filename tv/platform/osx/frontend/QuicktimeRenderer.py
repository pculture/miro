import os
import glob

from objc import YES, NO, nil
from QTKit import *
from Foundation import *

import app
import platformutils

###############################################################################

class QuicktimeRenderer (app.VideoRenderer):

    CORRECT_QTMEDIA_TYPES = (QTMediaTypeVideo, QTMediaTypeMPEG, QTMediaTypeMovie, QTMediaTypeFlash)

    def __init__(self, delegate):
        app.VideoRenderer.__init__(self)
        self.view = nil
        self.movie = nil
        self.delegate = delegate
        self.cachedMovie = nil

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
                    if mediaType in self.CORRECT_QTMEDIA_TYPES and mediaDuration > 0:
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
            self.view = QTMovieView.alloc().initWithFrame_(((0,0),(100,100)))
            self.view.setFillColor_(NSColor.blackColor())
            self.view.setControllerVisible_(NO)
            self.view.setEditable_(NO)
            self.view.setPreservesAspectRatio_(YES)
            self.view.setMovie_(self.movie)
            self.view.setNeedsDisplay_(YES)
            self.registerMovieObserver(qtmovie)

    def getMovieFromFile(self, filename):
        url = NSURL.fileURLWithPath_(filename)
        if self.cachedMovie is not nil and self.cachedMovie.attributeForKey_(QTMovieURLAttribute) == url:
            qtmovie = self.cachedMovie
        else:
            (qtmovie, error) = QTMovie.alloc().initWithURL_error_(url)
            self.cachedMovie = qtmovie
        return qtmovie

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
        if self.movie is nil:
            return 0
        qttime = self.movie.duration()
        return qttime.timeValue / float(qttime.timeScale)

    def getCurrentTime(self):
        if self.movie is nil:
            return 0
        qttime = self.movie.currentTime()
        return qttime.timeValue / float(qttime.timeScale)

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
