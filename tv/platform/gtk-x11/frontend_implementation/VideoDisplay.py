import app
import frontend
import gobject
import gtk
import gtk.gdk
import gnomevfs
import gconf
import sys
import logging
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
            widget = gtk.DrawingArea()
            widget.set_double_buffered(False)
            widget.add_events(gtk.gdk.POINTER_MOTION_MASK)
            widget.show()
            renderer.setWidget(widget)
            self.renderers.append(renderer)
            logging.info ("loaded renderer '%s'", modname)
        except:
            logging.info ("initRenderers: couldn't load %s: %s", modname, sys.exc_info()[1])

    @gtkAsyncMethod
    def initRenderers(self):
        self.renderers = []
        gconf_lock.acquire()
        values = gconf.client_get_default().get("/apps/democracy/player/renderers")
        if values == None:
            # Using both renderers causes segfaults --NN
            # self.add_renderer("gstrenderer")
            self.add_renderer("xinerenderer")
        else:
            for value in values.get_list():
                self.add_renderer(value.get_string())
        self.widget.add (self.renderers[0].widget)
        gconf_lock.release()
        self.renderersReady.set()

    @gtkAsyncMethod
    def fillMovieData (self, filename, movie_data, callback):
        app.VideoDisplayBase.fillMovieData (self, filename, movie_data, callback)
            
    def getRendererForItem(self, anItem):
        self.renderersReady.wait()
        return app.VideoDisplayBase.getRendererForItem(self, anItem)

    @gtkAsyncMethod
    def _gtkInit(self):
        self.widget = gtk.Alignment(xscale = 1.0, yscale = 1.0)
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
    def setChildWidget (self, widget):
        if self.widget.child != widget:
            if self.widget.child:
                self.widget.remove (self.widget.child)
            self.widget.add (widget)
            
    def setActiveRenderer (self, renderer):
        app.VideoDisplayBase.setActiveRenderer(self, renderer)
        self.setChildWidget (renderer.widget)

    @gtkAsyncMethod
    def play(self, startTime=0):
        if not self.activeRenderer:
            return
        if startTime == -1:
            self.activeRenderer.play()
        else:
            self.activeRenderer.playFromTime(startTime)
        self.startVideoTimeUpdate()
        self.isPlaying = True
        app.controller.frame.windowChanger.updatePlayPauseButton()

    def playFromTime(self, startTime):
        self.play (startTime)

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
