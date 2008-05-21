# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

from miro import app
from miro import config
from miro import prefs
import gobject
import gtk
import gtk.gdk
import gnomevfs
import sys
import logging
from gtk_queue import gtkAsyncMethod, gtkSyncMethod
from miro.frontends.html.displaybase import Display, VideoDisplayBase
from miro.frontends.html.playbackcontroller import PlaybackControllerBase
from miro.plat import options

from threading import Event

###############################################################################
#### The Playback Controller                                               ####
###############################################################################

class PlaybackController (PlaybackControllerBase):
    
    def playItemExternally(self, itemID):
        item = PlaybackControllerBase.playItemExternally(self, itemID)
        # now play this item externally

###############################################################################
#### Right-hand pane video display                                         ####
###############################################################################

class VideoDisplay (VideoDisplayBase):
    "Video player that can be shown in a MainFrame's right-hand pane."

    def __init__(self):
        VideoDisplayBase.__init__(self)
        self.videoUpdateTimeout = None
        self._gtkInit()
        self.renderersReady = Event()

    def addRenderer(self, modname):
        logging.info ("addRenderer: trying to add %s", modname)
        try:
            pkg = __import__('miro.plat.renderers.' + modname)
            module = getattr(pkg.plat.renderers, modname)
            renderer = module.Renderer()
            widget = gtk.DrawingArea()
            widget.set_double_buffered(False)
            widget.add_events(gtk.gdk.POINTER_MOTION_MASK)
            widget.show()
            renderer.setWidget(widget)
            app.renderers.append(renderer)
            logging.info ("addRenderer: success")
        except:
            logging.info ("initRenderers: couldn't load %s: %s", modname, sys.exc_info()[1])
            raise

    @gtkAsyncMethod
    def initRenderers(self):
        # renderer modules have to be xxxxrenderer and xxxx shows up in the
        # preferences.

        r = config.get(options.USE_RENDERER)
        try:
            self.addRenderer(r + "renderer")
        except:
            try:
                logging.error ("initRenderers: error detected...  trying to add gstreamerrenderer")
                # try to add the xine renderer if the preferences aren't right
                self.addRenderer("gstreamerrenderer")
            except:
                logging.error ("initRenderers: no valid renderer has been loaded")
                return

        self.widget.add (app.renderers[0].widget)
        self.renderersReady.set()

    @gtkAsyncMethod
    def fillMovieData (self, filename, movie_data, callback):
        def next_renderer (i, success):
            if success:
                callback()
                return
            i = i + 1
            if i < len(app.renderers):
                app.renderers[i].fillMovieData(filename, movie_data, lambda success: next_renderer(i, success))
            else:
                callback()
        next_renderer(-1, False)

    def setRendererAndCallback(self, anItem, internal, external):
        self.renderersReady.wait()
        for renderer in app.renderers:
            if renderer.canPlayFile(anItem.getVideoFilename()):
                self.setActiveRenderer(renderer)
                self.selectItem(anItem, renderer)
                internal()
                return
        external()

    @gtkAsyncMethod
    def _gtkInit(self):
        self.widget = gtk.Alignment(xscale = 1.0, yscale = 1.0)
        self.widget.show()

    def startVideoTimeUpdate(self):
        self.stopVideoTimeUpdate()
        self.videoUpdateTimeout = gobject.timeout_add(500,
                app.htmlapp.frame.updateVideoTime)
        app.htmlapp.frame.updateVideoTime()

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
        VideoDisplayBase.setActiveRenderer(self, renderer)
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
        app.htmlapp.frame.windowChanger.updatePlayPauseButton()

    def playPause(self):
        if self.isPlaying:
            self.pause()
        else:
            self.play(-1)

    def playFromTime(self, startTime):
        
        self.play (startTime)

    def goToBeginningOfMovie(self):
        self.play(0)

    @gtkAsyncMethod
    def pause(self):
        self.stopVideoTimeUpdate()
        VideoDisplayBase.pause(self)
        app.htmlapp.frame.windowChanger.updatePlayPauseButton()

    def getWidget(self, area = None):
        return self.widget

    def setVolume(self, volume):
        VideoDisplayBase.setVolume(self, volume)
        self.moveVolumeSlider(volume)

    @gtkAsyncMethod
    def moveVolumeSlider(self, volume):
        volumeScale = app.htmlapp.frame.widgetTree['volume-scale']
        volumeScale.set_value(self.volume)

    def onDeselected(self, frame):
        Display.onDeselected(self, frame)
        VideoDisplayBase.onDeselected(self, frame)

###############################################################################
###############################################################################
