import app
import frontend
import gobject
import gtk
from gtk_queue import gtkMethod

from xinerenderer import XineRenderer

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
        self._gtkInit()

    def initRenderers(self):
        self.renderers = [
            XineRenderer(),
            # add additional video renderers here
        ]

    @gtkMethod
    def _gtkInit(self):
        self.widget = gtk.DrawingArea()
        self.widget.set_double_buffered(False)
        self.widget.show()
        for renderer in self.renderers:
            renderer.setWidget(self.widget)

    def getWidget(self):
        return self.widget

    def goFullScreen(self):
        print "NOT IMPLEMENTED: goFullScreen()"

    def exitFullScreen(self):
        print "NOT IMPLEMENTED: exitFullScreen()"

    def getLength(self):
        """Get the length, in seconds, of the current video."""
        if self.activeRenderer:
            return self.activeRenderer.getLength()
        else:
            return 0

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
