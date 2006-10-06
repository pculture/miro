import app
import frontend
import gobject
import gtk
import gtk.gdk
import gnomevfs
import gconf
from gtk_queue import gtkAsyncMethod, gtkSyncMethod
from platformcfg import gconf_lock

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

    def add_renderer(self, modname):
        try:
            pkg = __import__('frontend_implementation.' + modname)
            module = getattr(pkg, modname)
            renderer = module.Renderer()
            renderer.setWidget(self.widget)
            self.renderers.append(renderer)
            print "loaded renderer '%s'" % modname
        except ImportError, error:
            print "initRenderers: couldn't load %s: %s" % (modname, error)

    @gtkAsyncMethod
    def initRenderers(self):
        self.renderers = []
        gconf_lock.acquire()
        values = gconf.client_get_default().get("/apps/democracy/player/renderers")
        if values == None:
            self.add_renderer("xinerenderer")
            self.add_renderer("gstrenderer")
        else:
            for value in values.get_list():
                self.add_renderer(value.get_string())
        gconf_lock.release()
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
