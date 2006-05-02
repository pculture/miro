import app
import frontend
import gobject
import gtk
import gtk.gdk
import gnomevfs
from gtk_queue import gtkAsyncMethod, gtkSyncMethod

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
        self.videoUpdateTimeout = None
        self._gtkInit()

    @gtkAsyncMethod
    def initRenderers(self):
        self.renderers = [
            XineRenderer(),
            # add additional video renderers here
        ]

    @gtkAsyncMethod
    def _gtkInit(self):
        self.widget = gtk.DrawingArea()
        self.widget.set_double_buffered(False)
        self.widget.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.widget.show()
        for renderer in self.renderers:
            renderer.setWidget(self.widget)

    def startVideoTimeUpdate(self):
        self.stopVideoTimeUpdate()
        self.videoUpdateTimeout = gobject.timeout_add(500,
                app.Controller.instance.frame.updateVideoTime)

    def stopVideoTimeUpdate(self):
        if self.videoUpdateTimeout is not None:
            gobject.source_remove(self.videoUpdateTimeout)
            self.videoUpdateTimeout = None

    @gtkAsyncMethod
    def play(self, startTime=0):
        if not self.activeRenderer:
            return
        self.activeRenderer.playFromTime(startTime)
        self.startVideoTimeUpdate()
        self.isPlaying = True
        app.Controller.instance.frame.windowChanger.updatePlayPauseButton()

    def goToBeginningOfMovie(self):
        self.play(0)

    @gtkAsyncMethod
    def pause(self):
        self.stopVideoTimeUpdate()
        app.VideoDisplayBase.pause(self)
        app.Controller.instance.frame.windowChanger.updatePlayPauseButton()

    def getWidget(self):
        return self.widget

    @gtkSyncMethod
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
