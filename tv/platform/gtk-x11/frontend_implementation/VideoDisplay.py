import app
import frontend
import gobject
import gtk
import gtk.gdk
import gnomevfs
from gtk_queue import gtkAsyncMethod, gtkSyncMethod

from xinerenderer import XineRenderer
from threading import Event

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
        self.renderersReady = Event()

    @gtkAsyncMethod
    def initRenderers(self):
        self.renderers = [
            XineRenderer(),
            # add additional video renderers here
        ]
        for renderer in self.renderers:
            renderer.setWidget(self.widget)
        self.renderersReady.set()

    def getRendererForItem(self, anItem):
        self.renderersReady.wait()
        return app.VideoDisplayBase.getRendererForItem(self, anItem)

    @gtkAsyncMethod
    def _gtkInit(self):
        self.widget = gtk.DrawingArea()
        self.widget.set_double_buffered(False)
        self.widget.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.widget.show()

    def startVideoTimeUpdate(self):
        self.stopVideoTimeUpdate()
        self.videoUpdateTimeout = gobject.timeout_add(500,
                app.controller.frame.updateVideoTime)

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
        app.controller.frame.windowChanger.updatePlayPauseButton()

    def goToBeginningOfMovie(self):
        self.play(0)

    @gtkAsyncMethod
    def pause(self):
        self.stopVideoTimeUpdate()
        app.VideoDisplayBase.pause(self)
        app.controller.frame.windowChanger.updatePlayPauseButton()

    def getWidget(self, area = None):
        return self.widget

    @gtkSyncMethod
    def getLength(self):
        """Get the length, in seconds, of the current video."""
        if self.activeRenderer:
            return self.activeRenderer.getLength()
        else:
            return 0

###############################################################################
###############################################################################
