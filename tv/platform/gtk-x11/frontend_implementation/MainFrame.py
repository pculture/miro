import app
import pygtk
pygtk.require('2.0')
import gtk
import gobject
import gtk.glade

from frontend import *
from frontend_implementation.gtk_queue import gtkMethod
from frontend_implementation.VideoDisplay import VideoDisplay
from frontend_implementation.callbackhandler import CallbackHandler
from frontend_implementation.fullscreenhandler import FullscreenHandler
from frontend_implementation.mainwindowchanger import MainWindowChanger

class WidgetTree(gtk.glade.XML):
    """Small helper class.  It's exactly like the gtk.glade.XML interface,
    except that it supports a mapping interface to get widgets.  If wt is a
    WidgetTree object, wt[name] is equivelent to wt.get_widget(name), but
    without all the typing.
    """

    def __getitem__(self, key):
        rv = self.get_widget(key)
        if rv is None:
            raise KeyError("No widget named %s" % key)
        else:
            return rv

###############################################################################
#### Initialization code: window classes, invisible toplevel parent        ####
###############################################################################


###############################################################################
#### Main window                                                           ####
###############################################################################

# Strategy: We create an EventBox for each display change the children on
# selectDisplay().  Each Display class has a getWidget() call that returns a
# widget to place inside the EventBoxes.  The choice of EventBox as the widget
# is pretty much arbitrary -- any container would do.  
#
class MainFrame:
    def __init__(self, appl):
        """The initially active display will be an instance of NullDisplay."""

        # Symbols by other parts of the program as as arguments
        # to selectDisplay
        self.mainDisplay = "mainDisplay"
        self.channelsDisplay = "channelsDisplay"
        self.collectionDisplay = "collectionDisplay"
        self.videoInfoDisplay = "videoInfoDisplay"
        self.selectedDisplays = {}
        self.videoLength = None
        self.callbackHandler = CallbackHandler(self)
        self.isFullscreen = False
        self._gtkInit()

    @gtkMethod
    def _gtkInit(self):
        # Create the widget tree, and remember important widgets
        self.widgetTree = WidgetTree('glade/dtv.glade')
        self.widgetTree['main-window'].show_all()
        self.displayBoxes = {
            self.mainDisplay : self.widgetTree['main-box'],
            self.channelsDisplay : self.widgetTree['channels-box'],
            self.videoInfoDisplay : self.widgetTree['video-info-box'],
        }
        self.windowChanger = MainWindowChanger(self.widgetTree,
                MainWindowChanger.BROWSING)
        self.fullscreenHandler = FullscreenHandler(self.widgetTree,
                self.windowChanger)
        # connect all signals
        self.widgetTree.signal_autoconnect(self.callbackHandler)
        gobject.timeout_add(500, self.updateVideoTime)
        # disable menu item's that aren't implemented yet
        self.widgetTree.get_widget('update-channel').set_sensitive(False)
        self.widgetTree.get_widget('update-all-channels').set_sensitive(False)
        self.widgetTree.get_widget('tell-a-friend').set_sensitive(False)
        self.widgetTree.get_widget('channel-rename').set_sensitive(False)
        self.widgetTree.get_widget('channel-copy-url').set_sensitive(False)
        self.widgetTree.get_widget('channel-add').set_sensitive(False)
        self.widgetTree.get_widget('channel-remove').set_sensitive(False)
        self.widgetTree.get_widget('delete-video').set_sensitive(False)

    @gtkMethod
    def selectDisplay(self, newDisplay, area):
        """Install the provided 'newDisplay' in the requested area"""

        if area == self.collectionDisplay:
            print "TODO: Collection Display not implemented on gtk/x11"
            return

        displayBox = self.displayBoxes[area]
        oldDisplay = self.selectedDisplays.get(area)
        if oldDisplay:
            oldDisplay.onDeselected_private(self)
            oldDisplay.onDeselected(self)
            displayBox.remove(oldDisplay.getWidget())
        # Leave a reference to oldDisplay around.  This protect it from
        # getting garbage collected at least until new displays's in
        displayBox.add(newDisplay.getWidget())
        newDisplay.onSelected_private(self)
        newDisplay.onSelected(self)
        self.selectedDisplays[area] = newDisplay
        # show the video info display when we are showing a movie.
        if area == self.mainDisplay:
            watchable = newDisplay.getWatchable()
            if watchable:
                self.windowChanger.changeState(self.windowChanger.PLAYLIST)
                app.Controller.instance.playbackController.configure(watchable)
            elif isinstance(newDisplay, VideoDisplay):
                self.windowChanger.changeState(self.windowChanger.VIDEO)
            else:
                self.windowChanger.changeState(self.windowChanger.BROWSING)

    def updateVideoTime(self):
        renderer = app.Controller.instance.videoDisplay.activeRenderer
        if renderer:
            videoTimeScale = self.widgetTree['video-time-scale']
            try:
                self.videoLength = renderer.getDuration()
            except:
                self.videoLength = None
                videoTimeScale.set_value(0)
            else:
                videoTimeScale.set_range(0, self.videoLength)
                videoTimeScale.set_value(renderer.getCurrentTime())
        return True

    def setFullscreen(self, fullscreen):
        activeRenderer = app.Controller.instance.videoDisplay.activeRenderer
        if fullscreen:
            self.windowChanger.changeState(self.windowChanger.VIDEO_FULLSCREEN)
            self.widgetTree['main-window'].fullscreen()
            self.fullscreenHandler.enable()
            activeRenderer.goFullscreen()
        else:
            self.windowChanger.changeState(self.windowChanger.VIDEO)
            self.widgetTree['main-window'].unfullscreen()
            self.fullscreenHandler.disable()
            activeRenderer.exitFullscreen()
        self.isFullscreen = fullscreen

    # Internal use: return an estimate of the size of a given display area
    # as a (width, height) pair, or None if no information's available.
    def getDisplaySizeHint(self, area):
        display = self.selectedDisplays.get(area)
        if display is None:
            return None
        allocation = display.getWidget().get_allocation()
        return allocation.width, allocation.height

    def unlink(self):
        pass
    
    def __del__(self):
        self.unlink()

###############################################################################
#### The no-op display (here's as good a place as any)                     ####
###############################################################################

class NullDisplay (app.Display):
    "A blank placeholder Display."

    def __init__(self):
        app.Display.__init__(self)

        view = gtk.TextView()
        buffer = view.get_buffer()
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add(view)
        iter = buffer.get_iter_at_offset(0)
        buffer.insert(iter,
                      "From: pathfinder@nasa.gov\n"
                      "To: mom@nasa.gov\n"
                      "Subject: Made it!\n"
                      "\n"
                      "We just got in this morning. The weather has been\n"
                      "great - clear but cold, and there are lots of fun sights.\n"
                      "Sojourner says hi. See you soon.\n"
                      " -Path\n")
        scrolled_window.show_all()
        self.widget = scrolled_window

    def getWidget(self):
        return self.widget

    def unlink(self):
        pass

    def __del__(self):
        self.unlink()

###############################################################################
###############################################################################
