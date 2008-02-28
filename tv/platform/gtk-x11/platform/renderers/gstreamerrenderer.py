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

from threading import Event
import logging
import os
import traceback

import pygst
pygst.require('0.10')
import gobject
import gst
import gst.interfaces
import gtk
import pygtk

from miro import app
from miro import config
from miro import eventloop
from miro import prefs
from miro.download_utils import nextFreeFilename
from miro.platform.frontends.html import gtk_queue
from miro.platform.utils import confirmMainThread

class Tester:
    def __init__(self, filename):
        self.done = Event()
        self.success = False
        self.actualInit(filename)

    @gtk_queue.gtkSyncMethod
    def actualInit(self, filename):
        confirmMainThread()
        self.playbin = gst.element_factory_make('playbin')
        self.videosink = gst.element_factory_make("fakesink", "videosink")
        self.playbin.set_property("video-sink", self.videosink)
        self.audiosink = gst.element_factory_make("fakesink", "audiosink")
        self.playbin.set_property("audio-sink", self.audiosink)

        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.watch_id = self.bus.connect("message", self.onBusMessage)

        self.playbin.set_property("uri", "file://%s" % filename)
        self.playbin.set_state(gst.STATE_PAUSED)

    def result (self):
        self.done.wait(5)
        self.disconnect()
        return self.success

    def onBusMessage(self, bus, message):
        confirmMainThread()
        if message.src == self.playbin:
            if message.type == gst.MESSAGE_STATE_CHANGED:
                prev, new, pending = message.parse_state_changed()
                if new == gst.STATE_PAUSED:
                    self.success = True
                    self.done.set()
                    # Success
            if message.type == gst.MESSAGE_ERROR:
                self.success = False
                self.done.set()

    @gtk_queue.gtkAsyncMethod
    def disconnect (self):
        confirmMainThread()
        self.bus.disconnect (self.watch_id)
        self.playbin.set_state(gst.STATE_NULL)
        del self.bus
        del self.playbin
        del self.audiosink
        del self.videosink

class Renderer:
    def __init__(self):
        confirmMainThread()
        self.playbin = gst.element_factory_make("playbin", "player")
        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.bus.enable_sync_message_emission()        
        self.watch_id = self.bus.connect("message", self.onBusMessage)
        self.bus.connect('sync-message::element', self.onSyncMessage)
        self.sink = gst.element_factory_make("ximagesink", "sink")
        self.playbin.set_property("video-sink", self.sink)

    def onSyncMessage(self, bus, message):
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == 'prepare-xwindow-id':
            imagesink = message.src
            imagesink.set_property('force-aspect-ratio', True)
            imagesink.set_xwindow_id(self.widget.window.xid)        
        
    def onBusMessage(self, bus, message):
        confirmMainThread()
        "recieves message posted on the GstBus"
        if message.type == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "onBusMessage: gstreamer error: %s" % err
        elif message.type == gst.MESSAGE_EOS:
#            print "onBusMessage: end of stream"
            eventloop.addIdle(app.htmlapp.playbackController.onMovieFinished,
                              "onBusMessage: skipping to next track")
        return None
            
    def setWidget(self, widget):
        confirmMainThread()
        widget.connect_after("realize", self.onRealize)
        widget.connect("unrealize", self.onUnrealize)
        widget.connect("expose-event", self.onExpose)
        self.widget = widget

    def onRealize(self, widget):
        confirmMainThread()
        self.gc = widget.window.new_gc()
        self.gc.foreground = gtk.gdk.color_parse("black")
        
    def onUnrealize(self, widget):
        confirmMainThread()
#        print "onUnrealize"
        self.playbin.set_state(gst.STATE_NULL)
        self.sink = None
        
    def onExpose(self, widget, event):
        confirmMainThread()
        if self.sink:
            self.sink.expose()
        else:
            widget.window.draw_rectangle(self.gc,
                                         True,
                                         0, 0,
                                         widget.allocation.width,
                                         widget.allocation.height)
        return True

    def canPlayFile(self, filename):
        """whether or not this renderer can play this data"""
        return Tester(filename).result()

    def fillMovieData(self, filename, movie_data, callback):
        confirmMainThread()
        dir = os.path.join (config.get(prefs.ICON_CACHE_DIRECTORY), "extracted")
        try:
            os.makedirs(dir)
        except:
            pass
        screenshot = os.path.join (dir, os.path.basename(filename) + ".png")
        movie_data["screenshot"] = nextFreeFilename(screenshot)


	extracter = Extracter(filename, movie_data["screenshot"], handle_result)

    def goFullscreen(self):
        confirmMainThread()
        """Handle when the video window goes fullscreen."""
        print "haven't implemented goFullscreen method yet!"
        
    def exitFullscreen(self):
        confirmMainThread()
        """Handle when the video window exits fullscreen mode."""
        print "haven't implemented exitFullscreen method yet!"

    def selectItem(self, anItem):
        self.selectFile(anItem.getFilename())

    @gtk_queue.gtkAsyncMethod
    def selectFile(self, filename):
        confirmMainThread()
        """starts playing the specified file"""
        self.stop()
        self.playbin.set_property("uri", "file://%s" % filename)
#        print "selectFile: playing file %s" % filename

    def getProgress(self):
        confirmMainThread()
        print "getProgress: what does this do?"

    @gtk_queue.gtkAsyncMethod
    def getCurrentTime(self, callback):
        confirmMainThread()
        try:
            position, format = self.playbin.query_position(gst.FORMAT_TIME)
            position = position / 1000000000
        except Exception, e:
            print "getCurrentTime: caught exception: %s" % e
            position = 0
        callback(position)

    def seek(self, seconds):
        confirmMainThread()
        event = gst.event_new_seek(1.0,
                                   gst.FORMAT_TIME,
                                   gst.SEEK_FLAG_FLUSH|gst.SEEK_FLAG_ACCURATE,
                                   gst.SEEK_TYPE_SET,
                                   seconds * 1000000000,
                                   gst.SEEK_TYPE_NONE, 0)
        result = self.playbin.send_event(event)
        if not result:
            print "seek failed"
        
    def playFromTime(self, seconds):
        confirmMainThread()
        #self.playbin.set_state(gst.STATE_NULL)
	self.seek(seconds)
        self.play()
#        print "playFromTime: starting playback from %s sec" % seconds

    def getDuration(self, callback=None):
        confirmMainThread()
        try:
            duration, format = self.playbin.query_duration(gst.FORMAT_TIME)
            duration = duration / 1000000000
        except Exception, e:
            print "getDuration: caught exception: %s" % e
            duration = 1
        if callback:
            callback(duration)
            return
        return duration

    @gtk_queue.gtkAsyncMethod
    def reset(self):
        confirmMainThread()
        self.playbin.set_state(gst.STATE_NULL)
#        print "** RESET **"

    @gtk_queue.gtkAsyncMethod
    def setVolume(self, level):
        confirmMainThread()
#        print "setVolume: set volume to %s" % level
        self.playbin.set_property("volume", level * 4.0)

    @gtk_queue.gtkAsyncMethod
    def play(self):
        confirmMainThread()
        self.playbin.set_state(gst.STATE_PLAYING)
#        print "** PLAY **"

    @gtk_queue.gtkAsyncMethod
    def pause(self):
        confirmMainThread()
        self.playbin.set_state(gst.STATE_PAUSED)
#        print "** PAUSE **"

    @gtk_queue.gtkAsyncMethod
    def stop(self):
        confirmMainThread()
        self.playbin.set_state(gst.STATE_NULL)
#        print "** STOP **"
        
    def getRate(self):
        confirmMainThread()
        return 256
    
    def setRate(self, rate):
        confirmMainThread()
        print "setRate: set rate to %s" % rate

    def movieDataProgramInfo(self, moviePath, thumbnailPath):
        return (("python", 'platform/renderers/gst_extractor.py', moviePath, thumbnailPath), None)
