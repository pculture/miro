import app
import frontend

###############################################################################
#### Right-hand pane video display                                         ####
###############################################################################

class VideoDisplay (frontend.NullDisplay, app.VideoDisplayDB):
    "Video player that can be shown in a MainFrame's right-hand pane."

    def __init__(self, firstItemId, view, previousDisplay):
        app.VideoDisplayDB.__init__(self, firstItemId, view)
        frontend.NullDisplay.__init__(self)
        self.previousDisplay = previousDisplay

    def onSelected(self, frame):
        # Enable controls
        pass

    def onDeselected(self, frame):
        # Disable controls
        pass

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
