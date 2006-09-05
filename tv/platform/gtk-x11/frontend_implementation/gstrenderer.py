import app
import traceback
import gobject
import eventloop

import pygtk
import gtk

import pygst
pygst.require('0.10')
import gst
import gst.interfaces

class Renderer(app.VideoRenderer):
    def __init__(self):
        self.playbin = gst.element_factory_make("playbin", "player")
        self.bus = self.playbin.get_bus()
        self.bus.add_signal_watch()
        self.watch_id = self.bus.connect("message", self.onBusMessage)
        self.sink = gst.element_factory_make("ximagesink", "sink")
        self.playbin.set_property("video-sink", self.sink)
        print "created new GstRenderer"
        
    def onBusMessage(self, bus, message):
        "recieves message posted on the GstBus"
        if message.type == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "onBusMessage: gstreamer error: %s" % err
        elif message.type == gst.MESSAGE_EOS:
            print "onBusMessage: end of stream"
            eventloop.addIdle(lambda:app.controller.playbackController.skip(1),
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
        print "onUnrealize"
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
        return True

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
        print "selectFile: playing file %s" % filename

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
        
    def playFromTime(self, seconds):
        #self.playbin.set_state(gst.STATE_NULL)
        event = gst.event_new_seek(1.0,
                                   gst.FORMAT_TIME,
                                   gst.SEEK_FLAG_FLUSH|gst.SEEK_FLAG_ACCURATE,
                                   gst.SEEK_TYPE_SET,
                                   seconds * 1000000000,
                                   gst.SEEK_TYPE_NONE, 0)
        result = self.playbin.send_event(event)
        if not result:
            print "playFromTime: seek failed"
        self.play()
        print "playFromTime: starting playback from %s sec" % seconds

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
        print "** RESET **"

    def setVolume(self, level):
        print "setVolume: set volume to %s" % level
        self.playbin.set_property("volume", level * 4.0)
        
    def play(self):
        self.playbin.set_state(gst.STATE_PLAYING)
        print "** PLAY **"
        
    def pause(self):
        self.playbin.set_state(gst.STATE_PAUSED)
        print "** PAUSE **"
        
    def stop(self):
        self.playbin.set_state(gst.STATE_NULL)
        print "** STOP **"
        
    def getRate(self):
        return 256
    
    def setRate(self, rate):
        print "setRate: set rate to %s" % rate
