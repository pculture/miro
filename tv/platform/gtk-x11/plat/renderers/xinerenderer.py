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

import os
import traceback
import logging

import gtk
import gobject

from miro import app
from miro import config
from miro import eventloop
from miro import prefs
from miro import xine
from miro.download_utils import nextFreeFilename
from miro.plat.frontends.html import gtk_queue
from miro.plat import options
from miro.plat import resources
from miro.plat.utils import confirmMainThread

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

class Renderer:
    def __init__(self):
        logging.info("Xine version:    %s", xine.getXineVersion())
        self.xine = xine.Xine()
        self.xine.setEosCallback(self.onEos)
        self.attachQueue = []
        self.attached = False
        self.driver = self.getDriver()
        logging.info("Xine driver:     %s", self.driver)

    def getDriver(self):
        xineDriver = config.get(options.DEFAULT_XINE_DRIVER)
        if xineDriver is None:
            xineDriver = "xv"
        return xineDriver
 
    def setWidget(self, widget):
        confirmMainThread()
        widget.connect_after("realize", self.onRealize)
        widget.connect("unrealize", self.onUnrealize)
        widget.connect("configure-event", self.onConfigureEvent)
        widget.connect("expose-event", self.onExposeEvent)
        self.widget = widget

    def onEos(self):
        eventloop.addIdle(app.htmlapp.playbackController.onMovieFinished, "onEos: Skip to next track")

    def onRealize(self, widget):
        confirmMainThread()
        # flush gdk output to ensure that our window is created
        gtk.gdk.flush()
        displayName = gtk.gdk.display_get_default().get_name()
        self.xine.attach(displayName, 
                         widget.window.xid, 
                         self.driver, 
                         int(options.shouldSyncX), 
                         int(config.get(options.USE_XINE_XV_HACK)))
        self.attached = True
        for func, args in self.attachQueue:
            try:
                func(self, *args)
            except Exception, e:
                print "Exception in attachQueue function"
                traceback.print_exc()
        self.attachQueue = []

    def onUnrealize(self, widget):
        confirmMainThread()
        self.xine.detach()
        self.attached = False

    def onConfigureEvent(self, widget, event):
        confirmMainThread()
        self.xine.setArea(event.x, event.y, event.width, event.height)

    def onExposeEvent(self, widget, event):
        confirmMainThread()
        self.xine.gotExposeEvent(event.area.x, event.area.y, event.area.width,
                event.area.height)

    @gtk_queue.gtkSyncMethod
    def canPlayFile(self, filename):
        confirmMainThread()
        return self.xine.canPlayFile(filename)

    def goFullscreen(self):
        """Handle when the video window goes fullscreen."""
        confirmMainThread()
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
        confirmMainThread()

    def selectItem(self, anItem):
        self.selectFile(anItem.getFilename())

    @gtk_queue.gtkAsyncMethod
    @waitForAttach
    def selectFile(self, filename):
        confirmMainThread()
        viz = config.get(options.XINE_VIZ);
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
        confirmMainThread()
        try:
            pos, length = self.xine.getPositionAndLength()
        except:
            pass

    @gtk_queue.gtkSyncMethod
    def getCurrentTime(self, callback):
        confirmMainThread()
        try:
            pos, length = self.xine.getPositionAndLength()
            callback(pos / 1000.0)
        except:
            callback(None)

    def setCurrentTime(self, seconds):
        confirmMainThread()
        self.seek(seconds)

    def playFromTime(self, seconds):
        confirmMainThread()
        self.seek (seconds)
        
    @waitForAttach
    def seek(self, seconds):
        confirmMainThread()
        self.xine.seek(int(seconds * 1000))

    def getDuration(self, callback=None):
        confirmMainThread()
        try:
            pos, length = self.xine.getPositionAndLength()
            ret = length / 1000
        except:
            ret = None

        if callback: 
            callback(ret)
            return

        return ret

    # @waitForAttach  -- Not necessary because stop does this
    def reset(self):
        # confirmMainThread() -- Not necessary because stop does this
        self.stop()

    @gtk_queue.gtkAsyncMethod
    @waitForAttach
    def setVolume(self, level):
        confirmMainThread()
        self.xine.setVolume(int(level * 100))

    @gtk_queue.gtkAsyncMethod
    @waitForAttach
    def play(self):
        confirmMainThread()
        self.xine.play()

    @gtk_queue.gtkAsyncMethod
    @waitForAttach
    def pause(self):
        confirmMainThread()
        self.xine.pause()

    #@waitForAttach -- Not necessary because pause does this
    def stop(self):
        # confirmMainThread() -- Not necessary since pause does this
        self.pause()

    @gtk_queue.gtkSyncMethod
    def getRate(self):
        confirmMainThread()
        return self.xine.getRate()

    @gtk_queue.gtkAsyncMethod
    @waitForAttach
    def setRate(self, rate):
        confirmMainThread()
        self.xine.setRate(rate)

    def movieDataProgramInfo(self, moviePath, thumbnailPath):
        return ((resources.path('../../../lib/miro/xine_extractor'), moviePath, thumbnailPath), None)
