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
        self._gtkInit()

    @gtkMethod
    def _gtkInit(self):
        # Create the widget tree, and remember important widgets
        widgetTree = gtk.glade.XML('glade/dtv.glade')
        self.displayBoxes = {
            self.mainDisplay : widgetTree.get_widget('main-box'),
            self.channelsDisplay : widgetTree.get_widget('channels-box'),
            self.videoInfoDisplay : widgetTree.get_widget('video-info-box'),
        }
        self.playPauseImage = widgetTree.get_widget('play-pause-image')
        self.videoTimeScale = widgetTree.get_widget('video-time-scale')
        self.mainWindow = widgetTree.get_widget('main')
        # show all widgets except the video controll box, which is only shown
        # when we have a video playlist
        self.mainWindow.show_all()
        self.videoControlBox = widgetTree.get_widget('video-control-box')
        self.videoControlBox.hide()
        # Keep track of menu items that need to be disabled when we aren't
        # watching a video
        self.videoOnlyMenuItems = [
            widgetTree.get_widget('save-video'),
            # delete-video should be one ,but it's not implemented yet so we
            # always disable it
            #widgetTree.get_widget('delete-video'),
            widgetTree.get_widget('play'),
            widgetTree.get_widget('stop'),
            widgetTree.get_widget('fullscreen'),
        ]
        self.disableVideoControls()
        # connect all signals
        widgetTree.signal_autoconnect(self.callbackHandler)
        gobject.timeout_add(500, self.updateVideoTime)
        # disable menu item's that aren't implemented yet
        widgetTree.get_widget('update-channel').set_sensitive(False)
        widgetTree.get_widget('update-all-channels').set_sensitive(False)
        widgetTree.get_widget('tell-a-friend').set_sensitive(False)
        widgetTree.get_widget('channel-rename').set_sensitive(False)
        widgetTree.get_widget('channel-copy-url').set_sensitive(False)
        widgetTree.get_widget('channel-add').set_sensitive(False)
        widgetTree.get_widget('channel-remove').set_sensitive(False)
        widgetTree.get_widget('delete-video').set_sensitive(False)
        widgetTree.get_widget('fullscreen').set_sensitive(False)

    @gtkMethod
    def disableVideoControls(self):
        self.videoControlBox.hide()
        for widget in self.videoOnlyMenuItems:
            widget.set_sensitive(False)

    @gtkMethod
    def enableVideoControls(self):
        self.videoControlBox.show()
        self.updatePlayPauseButton()
        for widget in self.videoOnlyMenuItems:
            widget.set_sensitive(True)

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
                self.enableVideoControls()
                self.displayBoxes[self.videoInfoDisplay].hide()
                app.Controller.instance.playbackController.configure(watchable)
            elif isinstance(newDisplay, VideoDisplay):
                self.enableVideoControls()
                self.displayBoxes[self.videoInfoDisplay].show()
            else:
                self.disableVideoControls()

    @gtkMethod
    def updatePlayPauseButton(self):
        if app.Controller.instance.videoDisplay.isPlaying:
            pixbuf = self.playPauseImage.render_icon(gtk.STOCK_MEDIA_PAUSE, 
                    gtk.ICON_SIZE_LARGE_TOOLBAR)
        else:
            pixbuf = self.playPauseImage.render_icon(gtk.STOCK_MEDIA_PLAY, 
                    gtk.ICON_SIZE_LARGE_TOOLBAR)
        self.playPauseImage.set_from_pixbuf(pixbuf)

    def updateVideoTime(self):
        renderer = app.Controller.instance.videoDisplay.activeRenderer
        if renderer:
            try:
                self.videoLength = renderer.getDuration()
            except:
                self.videoLength = None
                self.videoTimeScale.set_value(0)
            else:
                self.videoTimeScale.set_range(0, self.videoLength)
                self.videoTimeScale.set_value(renderer.getCurrentTime())
        return True

    # Internal use: return an estimate of the size of a given display area
    # as a (width, height) pair, or None if no information's available.
    def getDisplaySizeHint(self, area):
        return None

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
