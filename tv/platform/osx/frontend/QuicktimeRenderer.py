import os
import glob
import logging

from objc import YES, NO, nil
from QTKit import *
from AppKit import *
from Foundation import *

import app
import qtcomp
import platformcfg
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
                    logging.info('Successfully registered embedded Quicktime component: %s' % cmpName)
                else:
                    logging.warn('Error while registering embedded Quicktime component: %s' % cmpName)

    def checkComponentCompatibility(self, name):
        if "Perian" in name:
            versionInfo = os.uname()
            versionInfo = versionInfo[2].split('.')
            majorBuildVersion = int(versionInfo[0])
            if majorBuildVersion <= 7:
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
        url = NSURL.fileURLWithPath_(unicode(filename))
        if self.cachedMovie is not nil and self.cachedMovie.attributeForKey_(QTMovieURLAttribute) == url:
            qtmovie = self.cachedMovie
        else:
            (qtmovie, error) = QTMovie.alloc().initWithURL_error_(url)
            self.cachedMovie = qtmovie
        return qtmovie

    @platformutils.onMainThreadWithReturn
    def fileDuration(self, filename):
        (qtmovie, error) = QTMovie.movieWithFile_error_(filename)
        if qtmovie is None:
            return -1
        duration = movieDuration(qtmovie) * 1000
        del qtmovie
        return int(duration)

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

def movieDuration(qtmovie):
    if qtmovie is nil:
        return 0
    qttime = qtmovie.duration()
    return qttime.timeValue / float(qttime.timeScale)

###############################################################################

@platformutils.onMainThreadWithReturn
def extractIconDataAtPosition(filename, position):
    url = NSURL.fileURLWithPath_(unicode(filename))
    (qtmovie, error) = QTMovie.alloc().initWithURL_error_(url)
    if qtmovie is None:
        return None

    qttime = qtmovie.duration()
    qttime.timeValue *= position
    frame = qtmovie.frameImageAtTime_(qttime)
    if frame is None:
        return None

    frameSize = frame.size()
    frameRatio = frameSize.width / frameSize.height
    iconSize = NSSize(226.0, 170.0)
    iconRatio = iconSize.width / iconSize.height

    if frameRatio > iconRatio:
        size = NSSize(iconSize.width, iconSize.width / frameRatio)
        pos = NSPoint(0, (iconSize.height - size.height) / 2.0)
    else:
        size = NSSize(iconSize.height * frameRatio, iconSize.height)
        pos = NSPoint((iconSize.width - size.width) / 2.0, 0)
    
    icon = NSImage.alloc().initWithSize_(iconSize)
    try:
        icon.lockFocus()
        NSColor.blackColor().set()
        NSRectFill(((0,0), iconSize))
        frame.drawInRect_fromRect_operation_fraction_((pos, size), ((0,0), frameSize), NSCompositeSourceOver, 1.0)
    finally:
        icon.unlockFocus()
    
    jpegData = None
    try:
        tiffData = icon.TIFFRepresentation()
        imageRep = NSBitmapImageRep.imageRepWithData_(tiffData)
        properties = {NSImageCompressionFactor: 0.8}
        jpegData = imageRep.representationUsingType_properties_(NSJPEGFileType, properties)
        jpegData = str(jpegData.bytes())
    except:
        pass

    return jpegData

###############################################################################

import iconcache
iconcache.registerIconExtractor(extractIconDataAtPosition)

###############################################################################
