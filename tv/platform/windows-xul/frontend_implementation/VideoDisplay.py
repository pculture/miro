import app
import frontend
import os
import util

from xpcom import components
from threading import Lock
import frontend
import time

selectItemLock = Lock()

###############################################################################
#### The Playback Controller                                               ####
###############################################################################

class PlaybackController (app.PlaybackControllerBase):
    
    def playItemExternally(self, itemID):
        item = app.PlaybackControllerBase.playItemExternally(self, itemID)
        # now play this item externally
        moviePath = ""
        try:
            moviePath = os.path.normpath(item.getVideoFilename())
            os.startfile(moviePath)
        except:
            print "DTV: movie %s could not be externally opened" % moviePath

###############################################################################
#### Right-hand pane video display                                         ####
###############################################################################

class VideoDisplay (app.VideoDisplayBase):
    "Video player shown in a MainFrame's right-hand pane."

    def initRenderers(self):
        self.renderers.append(VLCRenderer())

    def setArea(self, area):
        # we hardcode the videodisplay's area to be mainDisplayVideo
        pass
    def removedFromArea(self):
        # don't care about this either
        pass

    def goFullScreen(self):
        return frontend.vlcRenderer.goFullscreen(url)

    def exitFullScreen(self):
        return frontend.vlcRenderer.exitFullScreen(url)

    def setVolume(self, volume): 
        self.volume = volume
        frontend.vlcRenderer.setVolume(volume)

# This is a major hack to avoid VLC crashes by giving it time to
# process each stop or play command. --NN
def lockAndPlay(func):
    def locked(*args, **kwargs):
        global selectItemLock
        selectItemLock.acquire()
        try:
            ret = func(*args, **kwargs)
            time.sleep(1)
            return ret
        finally:
            selectItemLock.release()
    return locked

class VLCRenderer (app.VideoRenderer):
    """The VLC renderer is very thin wrapper around the xine-renderer xpcom
    component. 
    """

    def canPlayFile(self, filename):
        url = util.absolutePathToFileURL(filename)
        return frontend.vlcRenderer.canPlayURL(url)

    @lockAndPlay
    def selectFile(self, filename):
        url = util.absolutePathToFileURL(filename)
        return frontend.vlcRenderer.selectURL(url)
    def setVolume(self, volume): 
        return frontend.vlcRenderer.setVolume(volume)
    @lockAndPlay
    def reset(self): 
        return frontend.vlcRenderer.reset()
    @lockAndPlay
    def play(self): 
        return frontend.vlcRenderer.play()
    def pause(self): 
        return frontend.vlcRenderer.pause()
    @lockAndPlay
    def stop(self): 
        return frontend.vlcRenderer.stop()
    def goToBeginningOfMovie(self): 
        return frontend.vlcRenderer.goToBeginningOfMovie()
    def getDuration(self): 
        return frontend.vlcRenderer.getDuration()
    def getCurrentTime(self): 
        try:
            return frontend.vlcRenderer.getCurrentTime()
        except:
            return None
    def setCurrentTime(self, time): 
        return frontend.vlcRenderer.setCurrentTime(time)
    def getRate(self): 
        return frontend.vlcRenderer.getRate()
    def setRate(self, rate): 
        return frontend.vlcRenderer.setRate(rate)

###############################################################################
###############################################################################
