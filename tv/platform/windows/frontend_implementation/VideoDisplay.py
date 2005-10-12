import app
import frontend
import vlc

###############################################################################
#### Right-hand pane video display                                         ####
###############################################################################

class VideoDisplay (frontend.NullDisplay, app.VideoDisplayDB):
    "Video player that can be shown in a MainFrame's right-hand pane."

    def __init__(self):
        app.VideoDisplayDB.__init__(self)
        frontend.NullDisplay.__init__(self)
        self.vlc = vlc.SimpleVLC()
        self.vlc.setWindow(self.getHwnd())

    # FIXME: This strange API was inherited from OS X
    @classmethod
    def getInstance(self):
        return VideoDisplay()

    def configure(self, view, firstItemId, previousDisplay):
        self.setPlaylist(view, firstItemId)
        self.previousDisplay = previousDisplay


    def onWMClose(self, hwnd, msg, wparam, lparam):
	self.unlink()
	win32gui.PostQuitMessage(0)

    def onWMSize(self, hwnd, msg, wparam, lparam):
        pass

    def onWMActivate(self, hwnd, msg, wparam, lparam):
        pass

    def playPause(self):
        filename = self.cur().getPath()
        if filename is None:
            filename= self.getNext().getPath()
        self.vlc.play(filename)

    def stop(self):
        self.vlc.stop()
    
    def onSelected(self, frame):
        # Enable controls
        pass

    def onDeselected(self, frame):
        # Disable controls
        self.vlc.stop()

    # NEEDS: See OS X for details on how to use VideoDisplayDB to find
    # items to play.

#    def getHwnd(self):
#        in parent for now

    def unlink(self):
        frontend.NullDisplay.unlink(self)

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
