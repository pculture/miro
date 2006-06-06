import app
import frontend
import os
import util

from xpcom import components
import frontend

###############################################################################
#### The Playback Controller                                               ####
###############################################################################

class PlaybackController (app.PlaybackControllerBase):
    
    def playItemExternally(self, itemID):
        item = app.PlaybackControllerBase.playItemExternally(self, itemID)
        # now play this item externally
        moviePath = ""
        try:
            moviePath = os.path.normpath(item.getPath())
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

class VLCRenderer:
    """The VLC renderer is very thin wrapper around the xine-renderer xpcom
    component. 
    """

    def canPlayItem(self, item):
        path = item.getFilename()
        url = util.absolutePathToFileURL(path)
        return frontend.vlcRenderer.canPlayURL(url)

    def selectItem(self, item):
        path = item.getFilename()
        url = util.absolutePathToFileURL(path)
        return frontend.vlcRenderer.selectURL(url)

    def setVolume(self, volume): 
        return frontend.vlcRenderer.setVolume(volume)
    def reset(self): 
        return frontend.vlcRenderer.reset()
    def play(self): 
        return frontend.vlcRenderer.play()
    def pause(self): 
        return frontend.vlcRenderer.pause()
    def stop(self): 
        return frontend.vlcRenderer.stop()
    def goToBeginningOfMovie(self): 
        return frontend.vlcRenderer.goToBeginningOfMovie()
    def getDuration(self): 
        return frontend.vlcRenderer.getDuration()
    def getCurrentTime(self): 
        return frontend.vlcRenderer.getCurrentTime()
    def setCurrentTime(self, time): 
        return frontend.vlcRenderer.setCurrentTime(time)
    def getRate(self): 
        return frontend.vlcRenderer.getRate()
    def setRate(self, rate): 
        return frontend.vlcRenderer.setRate(rate)

###############################################################################
#### Playlist item base class                                              ####
###############################################################################

class PlaylistItem:
    "The record that makes up VideoDisplay playlists."

    def getTitle(self):
        """Return the title of this item as a string, for visual presentation
        to the user."""
        raise NotImplementedError

    def getPath(self):
        """Return the full path in the local filesystem to the video file
        to play."""
        raise NotImplementedError

    def getLength(self):
        """Return the length of this item in seconds as a real number. This
        is used only cosmetically, for telling the user the total length
        of the current playlist and so on."""
        raise NotImplementedError

    def onViewed(self):
        """Called by the frontend when a clip is at least partially watched
        by the user. To handle this event, for example by marking the
        item viewed in the database, override this method in a subclass."""
        raise NotImplementedError

###############################################################################
###############################################################################
