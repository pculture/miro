# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

import app
import xine
import gtk
import traceback
import gobject
import eventloop
import config
import prefs
import os
import frontend
from download_utils import nextFreeFilename

def waitForAttach(func):
    """Many xine calls can't be made until we attach the object to a X window.
    This decorator delays method calls until then.
    """
    def waitForAttachWrapper(self, *args):
        if self.attached:
            func(self, *args)
        else:
            self.attachQueue.append((func, args))
    return waitForAttachWrapper

class Renderer(app.VideoRenderer):
    def __init__(self):
        self.xine = xine.Xine()
        self.xine.setEosCallback(self.onEos)
        self.attachQueue = []
        self.attached = False

    def setWidget(self, widget):
        widget.connect_after("realize", self.onRealize)
        widget.connect("unrealize", self.onUnrealize)
        widget.connect("configure-event", self.onConfigureEvent)
        widget.connect("expose-event", self.onExposeEvent)
        self.widget = widget

    def onEos(self):
        eventloop.addIdle(app.controller.playbackController.onMovieFinished, "onEos: Skip to next track")

    def onRealize(self, widget):
        # flush gdk output to ensure that our window is created
        gtk.gdk.flush()
        displayName = gtk.gdk.display_get_default().get_name()
        self.xine.attach(displayName, widget.window.xid, int(frontend.shouldSyncX))
        self.attached = True
        for func, args in self.attachQueue:
            try:
                func(self, *args)
            except Exception, e:
                print "Exception in attachQueue function"
                traceback.print_exc()
        self.attachQueue = []

    def onUnrealize(self, widget):
        self.xine.detach()
        self.attached = False

    def onConfigureEvent(self, widget, event):
        self.xine.setArea(event.x, event.y, event.width, event.height)

    def onExposeEvent(self, widget, event):
        self.xine.gotExposeEvent(event.area.x, event.area.y, event.area.width,
                event.area.height)

    def canPlayFile(self, filename):
        return self.xine.canPlayFile(filename)

    def fillMovieData(self, filename, movie_data, callback):
        dir = os.path.join (config.get(prefs.ICON_CACHE_DIRECTORY), "extracted")
        try:
            os.makedirs(dir)
        except:
            pass
        screenshot = os.path.join (dir, os.path.basename(filename) + ".png")
        movie_data["screenshot"] = nextFreeFilename(screenshot)

        success = self.xine.fillMovieData(filename, movie_data["screenshot"], movie_data)
        
        if success:
            if not os.path.exists(movie_data["screenshot"]):
                movie_data["screenshot"] = ""
        else:
            movie_data["screenshot"] = None
        callback (success)

    def goFullscreen(self):
        """Handle when the video window goes fullscreen."""
        # Sometimes xine doesn't seem to handle the expose events properly and
        # only thinks part of the window is exposed.  To work around this we
        # send it a couple of fake expose events for the entire window, after
        # a short time delay.

        def fullscreenExposeWorkaround():
            try:
                _, _, width, height, _ = self.widget.window.get_geometry()
                self.xine.gotExposeEvent(0, 0, width, height)
            except:
                return True
            return False

        gobject.timeout_add(500, fullscreenExposeWorkaround)
        gobject.timeout_add(1000, fullscreenExposeWorkaround)

    def exitFullscreen(self):
        """Handle when the video window exits fullscreen mode."""
        # nothing to do here
        pass

    @waitForAttach
    def selectFile(self, filename):
        viz = config.get(prefs.XINE_VIZ);
        self.xine.setViz(viz);
        self.xine.selectFile(filename)
        def exposeWorkaround():
            try:
                _, _, width, height, _ = self.widget.window.get_geometry()
                self.xine.gotExposeEvent(0, 0, width, height)
            except:
                return True
            return False

        gobject.timeout_add(500, exposeWorkaround)

    def getProgress(self):
        try:
            pos, length = self.xine.getPositionAndLength()
        except:
            pass

    def getCurrentTime(self):
        try:
            pos, length = self.xine.getPositionAndLength()
            return pos / 1000.0
        except:
            return None

    def setCurrentTime(self, seconds):
        self.seek(seconds)

    def playFromTime(self, seconds):
        self.seek (seconds)

    @waitForAttach
    def seek(self, seconds):
        self.xine.seek(int(seconds * 1000))

    def getDuration(self):
        try:
            pos, length = self.xine.getPositionAndLength()
            return length / 1000
        except:
            return None

    @waitForAttach
    def reset(self):
        self.stop()

    @waitForAttach
    def setVolume(self, level):
        self.xine.setVolume(int(level * 100))

    @waitForAttach
    def play(self):
        self.xine.play()

    @waitForAttach
    def pause(self):
        self.xine.pause()

    @waitForAttach
    def stop(self):
        self.pause()

    def getRate(self):
        return self.xine.getRate()

    @waitForAttach
    def setRate(self, rate):
        self.xine.setRate(rate)
