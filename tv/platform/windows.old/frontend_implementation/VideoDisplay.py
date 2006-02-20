import app
import frontend
import vlc

###############################################################################
#### The Playback Controller                                               ####
###############################################################################

class PlaybackController (app.PlaybackControllerBase):
    
    def playItemExternally(self, itemID):
        item = app.PlaybackControllerBase.playItemExternally(self, itemID)
        # now play this item externally


###############################################################################
#### Right-hand pane video display                                         ####
###############################################################################

class VideoDisplay (app.VideoDisplayBase):
    "Video player that can be shown in a MainFrame's right-hand pane."

    def __init__(self):
        app.VideoDisplayBase.__init__(self)
        self.vlc = vlc.SimpleVLC()
        self.vlc.setWindow(self.getHwnd())
    
    def canPlayItem(self, item):
        return False

    def selectItem(self, item):
        app.VideoDisplayBase.selectItem(self, item)

    def goToBeginningOfMovie(self):
        pass

    def play(self):
        filename = self.cur().getPath()
        if filename is None:
            filename= self.getNext().getPath()
        self.vlc.play(filename)
        app.VideoDisplayBase.play(self)

    def pause(self):
        self.vlc.pause(0)
        app.VideoDisplayBase.pause(self)

    def stop(self):
        self.vlc.stop()
        app.VideoDisplayBase.stop(self)

    def goFullScreen(self):
        app.VideoDisplayBase.goFullScreen(self)

    def exitFullScreen(self):
        app.VideoDisplayBase.exitFullScreen(self)

    def getCurrentTime(self):
        return self.vlc.getPosition()

    def setVolume(self, level):
        self.vlc.setVolume(level )
        app.VideoDisplayBase.setVolume(self, level)

    def getVolume(self):
        return self.vlc.getVolume()

    def muteVolume(self):
        app.VideoDisplayBase.muteVolume(self)

    def restoreVolume(self):
        app.VideoDisplayBase.restoreVolume(self)

    def onSelected(self, frame):
        app.VideoDisplayBase.onSelected(self, frame)

    def onDeselected(self, frame):
        app.VideoDisplayBase.onDeselected(self, frame)

    def onWMClose(self, hwnd, msg, wparam, lparam):
        self.unlink()
        win32gui.PostQuitMessage(0)

    def onWMSize(self, hwnd, msg, wparam, lparam):
        pass

    def onWMActivate(self, hwnd, msg, wparam, lparam):
        pass


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
