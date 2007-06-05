import app
import traceback
import gobject
import eventloop
import config
import prefs
import os
from download_utils import nextFreeFilename
from gtk_queue import gtkAsyncMethod

from threading import Event

import pygtk
import gtk

import pygst
pygst.require('0.10')
import gst
import gst.interfaces

class Tester:
    def __init__(self, filename):
        self.playbin = gst.element_factory_make('playbin')
        self.videosink = gst.element_factory_make("fakesink", "videosink")
        self.playbin.set_property("video-sink", self.videosink)
        self.audiosink = gst.element_factory_make("fakesink", "audiosink")
        self.playbin.set_property("audio-sink", self.audiosink)

        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.watch_id = self.bus.connect("message", self.onBusMessage)
        self.done = Event()
        self.success = False

        self.playbin.set_property("uri", "file://%s" % filename)
        self.playbin.set_state(gst.STATE_PAUSED)

    def result (self):
        self.done.wait(5)
        self.disconnect()
        print self.success
        return self.success

    def onBusMessage(self, bus, message):
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

    def disconnect (self):
        self.bus.disconnect (self.watch_id)
        self.playbin.set_state(gst.STATE_NULL)
        del self.bus
        del self.playbin
        del self.audiosink
        del self.videosink

class Extracter:
    def __init__(self, filename, thumbnail_filename, callback):
        self.thumbnail_filename = thumbnail_filename
        self.grabit = False
        self.first_pause = True
        self.success = False
        self.duration = 0
	self.buffer_probes = {}
        self.callback = callback

	self.pipeline = gst.parse_launch('filesrc location="%s" ! decodebin ! ffmpegcolorspace ! video/x-raw-rgb,depth=24,bpp=24 ! fakesink signal-handoffs=True' % (filename,))

        for sink in self.pipeline.sinks():
            name = sink.get_name()
            factoryname = sink.get_factory().get_name()
            if factoryname == "fakesink":
                pad = sink.get_pad("sink")
                self.buffer_probes[name] = pad.add_buffer_probe(self.buffer_probe_handler, name)

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.watch_id = self.bus.connect("message", self.onBusMessage)

        self.pipeline.set_state(gst.STATE_PAUSED)

    def done (self):
        self.callback(self.success)

    def onBusMessage(self, bus, message):
        if message.src == self.pipeline:
            if message.type == gst.MESSAGE_STATE_CHANGED:
                prev, new, pending = message.parse_state_changed()
                if new == gst.STATE_PAUSED:
                    if self.first_pause:
                        self.duration = self.pipeline.query_duration(gst.FORMAT_TIME)[0]
                        self.grabit = True
                        seek_result = self.pipeline.seek(1.0,
                                gst.FORMAT_TIME,
                                gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
                                gst.SEEK_TYPE_SET,
                                self.duration / 2,
                                gst.SEEK_TYPE_NONE, 0)
                        if not seek_result:
                            self.success = False
                            self.disconnect()
                    self.first_pause = False
            if message.type == gst.MESSAGE_ERROR:
                self.success = False
                self.disconnect()

    def buffer_probe_handler(self, pad, buffer, name) :
        """Capture buffers as gdk_pixbufs when told to."""
        if self.grabit:
            caps = buffer.caps
            if caps is not None:
                filters = caps[0]
                self.width = filters["width"]
                self.height = filters["height"]
            timecode = self.pipeline.query_position(gst.FORMAT_TIME)[0]
            pixbuf = gtk.gdk.pixbuf_new_from_data(buffer.data, gtk.gdk.COLORSPACE_RGB, False, 8, self.width, self.height, self.width * 3)
            pixbuf.save(self.thumbnail_filename, "png")
            del pixbuf
            self.success = True
            self.disconnect()
        return True

    @gtkAsyncMethod
    def disconnect (self):
        if self.pipeline is not None:
            self.pipeline.set_state(gst.STATE_NULL)
            for sink in self.pipeline.sinks():
                name = sink.get_name()
                factoryname = sink.get_factory().get_name()
                if factoryname == "fakesink" :
                    pad = sink.get_pad("sink")
                    pad.remove_buffer_probe(self.buffer_probes[name])
                    del self.buffer_probes[name]
            self.pipeline = None
        if self.bus is not None:
            self.bus.disconnect (self.watch_id)
            self.bus = None
        self.done()

class Renderer(app.VideoRenderer):
    def __init__(self):
        self.playbin = gst.element_factory_make("playbin", "player")
        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.watch_id = self.bus.connect("message", self.onBusMessage)
        self.sink = gst.element_factory_make("ximagesink", "sink")
        self.playbin.set_property("video-sink", self.sink)
        
    def onBusMessage(self, bus, message):
        "recieves message posted on the GstBus"
        if message.type == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "onBusMessage: gstreamer error: %s" % err
        elif message.type == gst.MESSAGE_EOS:
#            print "onBusMessage: end of stream"
            eventloop.addIdle(app.controller.playbackController.onMovieFinished,
                              "onBusMessage: skipping to next track")
        else:
            if not message.structure == None:
                if message.structure.get_name() == 'prepare-xwindow-id':
                    sink = message.src
                    sink.set_xwindow_id(self.widget.window.xid)
                    sink.set_property("force-aspect-ratio", True)
        return True
            
    def setWidget(self, widget):
        widget.connect_after("realize", self.onRealize)
        widget.connect("unrealize", self.onUnrealize)
        widget.connect("expose-event", self.onExpose)
        self.widget = widget

    def onRealize(self, widget):
        self.gc = widget.window.new_gc()
        self.gc.foreground = gtk.gdk.color_parse("black")
        
    def onUnrealize(self, widget):
#        print "onUnrealize"
        self.sink = None
        
    def onExpose(self, widget, event):
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
        dir = os.path.join (config.get(prefs.ICON_CACHE_DIRECTORY), "extracted")
        try:
            os.makedirs(dir)
        except:
            pass
        screenshot = os.path.join (dir, os.path.basename(filename) + ".png")
        movie_data["screenshot"] = nextFreeFilename(screenshot)

        def handle_result (success):
            if success:
                movie_data["duration"] = extracter.duration
                if not os.path.exists(movie_data["screenshot"]):
                    movie_data["screenshot"] = ""
            else:
                movie_data["screenshot"] = None
            callback(success)

	extracter = Extracter(filename, movie_data["screenshot"], handle_result)

    def goFullscreen(self):
        """Handle when the video window goes fullscreen."""
        print "haven't implemented goFullscreen method yet!"
        
    def exitFullscreen(self):
        """Handle when the video window exits fullscreen mode."""
        print "haven't implemented exitFullscreen method yet!"

    def selectFile(self, filename):
        """starts playing the specified file"""
        self.stop()
        self.playbin.set_property("uri", "file://%s" % filename)
#        print "selectFile: playing file %s" % filename

    def getProgress(self):
        print "getProgress: what does this do?"

    def getCurrentTime(self):
        try:
            position, format = self.playbin.query_position(gst.FORMAT_TIME)
            position = position / 1000000000
        except Exception, e:
            print "getCurrentTime: caught exception: %s" % e
            position = 0
        return position

    def seek(self, seconds):
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
        #self.playbin.set_state(gst.STATE_NULL)
	self.seek(seconds)
        self.play()
#        print "playFromTime: starting playback from %s sec" % seconds

    def getDuration(self):
        try:
            duration, format = self.playbin.query_duration(gst.FORMAT_TIME)
            duration = duration / 1000000000
        except Exception, e:
            print "getDuration: caught exception: %s" % e
            duration = 1
        return duration
        
    def reset(self):
        self.playbin.set_state(gst.STATE_NULL)
#        print "** RESET **"

    def setVolume(self, level):
#        print "setVolume: set volume to %s" % level
        self.playbin.set_property("volume", level * 4.0)
        
    def play(self):
        self.playbin.set_state(gst.STATE_PLAYING)
#        print "** PLAY **"
        
    def pause(self):
        self.playbin.set_state(gst.STATE_PAUSED)
#        print "** PAUSE **"
        
    def stop(self):
        self.playbin.set_state(gst.STATE_NULL)
#        print "** STOP **"
        
    def getRate(self):
        return 256
    
    def setRate(self, rate):
        print "setRate: set rate to %s" % rate
