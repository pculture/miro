import app
import frontend

###############################################################################
#### Right-hand pane video display                                         ####
###############################################################################

class VideoDisplay (app.VideoDisplayBase):
    "Video player that can be shown in a MainFrame's right-hand pane."

    def __init__(self):
        app.VideoDisplayBase.__init__(self)
        pass
    
    def selectItem(self, item):
        app.VideoDisplayBase.selectItem(self, item)

    def resetMovie(self):
        pass

    def play(self):
        app.VideoDisplayBase.play(self)

    def pause(self):
        app.VideoDisplayBase.pause(self)

    def stop(self):
        app.VideoDisplayBase.stop(self)

    def goFullScreen(self):
        app.VideoDisplayBase.goFullScreen(self)

    def getCurrentTime(self):
        return 0.0

    def onSelected(self, frame):
        app.VideoDisplayBase.onSelected(self, frame)

    def onDeselected(self, frame):
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
