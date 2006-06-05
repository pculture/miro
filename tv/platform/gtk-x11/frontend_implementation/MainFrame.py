import app
import pygtk
pygtk.require('2.0')
import gtk
import gobject
import gtk.glade
import sets
import gconf

import resource
from frontend import *
from frontend_implementation.gtk_queue import gtkAsyncMethod, gtkSyncMethod
from frontend_implementation.VideoDisplay import VideoDisplay
from frontend_implementation.HTMLDisplay import HTMLDisplay
from frontend_implementation.callbackhandler import CallbackHandler
from frontend_implementation.mainwindowchanger import MainWindowChanger
from platformcfg import gconf_lock
import config
import prefs

def getInt(key):
    gconf_lock.acquire()
    try:
        client = gconf.client_get_default()
        fullkey = '/apps/democracy/player/window/' + key
        value = client.get (fullkey)
        if (value != None):
            return value.get_int()
        else:
            return None
    finally:
        gconf_lock.release()

def setInt(key, value):
    gconf_lock.acquire()
    try:
        client = gconf.client_get_default()
        fullkey = '/apps/democracy/player/window/' + key
        value = client.set_int (fullkey, value)
    finally:
        gconf_lock.release()

def getBool(key):
    gconf_lock.acquire()
    try:
        client = gconf.client_get_default()
        fullkey = '/apps/democracy/player/window/' + key
        value = client.get (fullkey)
        if (value != None):
            return value.get_bool()
        else:
            return None
    finally:
        gconf_lock.release()

def setBool(key, value):
    gconf_lock.acquire()
    try:
        client = gconf.client_get_default()
        fullkey = '/apps/democracy/player/window/' + key
        value = client.set_bool (fullkey, value)
    finally:
        gconf_lock.release()

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
        self.aboutWidget = None

    @gtkAsyncMethod
    def _gtkInit(self):
        # Create the widget tree, and remember important widgets
        self.widgetTree = WidgetTree(resource.path('democracy.glade'), 'main-window', 'democracyplayer')
        self.displayBoxes = {
            self.mainDisplay : self.widgetTree['main-box'],
            self.channelsDisplay : self.widgetTree['channels-box'],
            self.videoInfoDisplay : self.widgetTree['video-info-box'],
        }

        self.widgetTree['main-window'].set_icon_from_file (resource.sharePath('pixmaps/democracyplayer-128x128.png'))

        # create the buttonsDown attribute to the video time scale.  It will
        # track which mouse buttons are currently pressed.  This is usefull
        # because we don't want to update widget when the user is in the
        # middle of draging it.
        self.widgetTree['video-time-scale'].buttonsDown = sets.Set()
        # connect all signals
        self.widgetTree.signal_autoconnect(self.callbackHandler)
        # disable menu item's that aren't implemented yet
#        self.widgetTree.get_widget('update-channel').set_sensitive(False)
#        self.widgetTree.get_widget('update-all-channels').set_sensitive(False)
#        self.widgetTree.get_widget('tell-a-friend').set_sensitive(False)
#        self.widgetTree.get_widget('channel-rename').set_sensitive(False)
#        self.widgetTree.get_widget('channel-copy-url').set_sensitive(False)
#        self.widgetTree.get_widget('channel-add').set_sensitive(False)
#        self.widgetTree.get_widget('channel-remove').set_sensitive(False)
#        self.widgetTree.get_widget('delete-video').set_sensitive(False)

        self.uiManager = gtk.UIManager()

        self.actionGroups = self.callbackHandler.actionGroups ()
        i = 0
        for actionGroup in self.actionGroups.values():
            self.uiManager.insert_action_group (actionGroup, i)
            i = i + 1

        self.uiManager.add_ui_from_file(resource.path('Democracy.xml'))

        self.widgetTree['menubar-box'].add (self.uiManager.get_widget('/menubar'))
        self.widgetTree['main-window'].add_accel_group(self.uiManager.get_accel_group())

        self.widgetTree['volume-scale'].set_value (config.get(prefs.VOLUME_LEVEL))

        self.windowChanger = MainWindowChanger(self.widgetTree, self,
                MainWindowChanger.BROWSING)

        width = getInt ("width")
        height = getInt ("height")
        x = getInt ("x")
        y = getInt ("y")
        if (x != None and y != None):
            self.widgetTree['main-window'].move (x, y);
        if (width != None and height != None):
            self.widgetTree['main-window'].resize (width, height);

        maximized = getBool ("maximized")
        if maximized != None:
            if maximized:
                self.widgetTree['main-window'].maximize()
            else:
                self.widgetTree['main-window'].unmaximize()

        self.widgetTree['main-window'].connect ("configure-event", self.configureEvent)
        self.widgetTree['main-window'].connect ("window-state-event", self.stateEvent)

        self.widgetTree['main-window'].show_all()

    def configureEvent(self, widget, event):
        (x, y) = self.widgetTree['main-window'].get_position ()
        (width, height) = self.widgetTree['main-window'].get_size()
        setInt ("width", width)
        setInt ("height", height)
        setInt ("x", x)
        setInt ("y", y)
        return False

    def stateEvent (self, widget, event):
        maximized = (event.new_window_state & gtk.gdk.WINDOW_STATE_MAXIMIZED) != 0
        setBool ("maximized", maximized)
        

    @gtkAsyncMethod
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
            if oldDisplay.getWidget(area) != newDisplay.getWidget(area):
                displayBox.remove(oldDisplay.getWidget(area))
                # Leave a reference to oldDisplay around.  This protect it from
                # getting garbage collected at least until new displays's in
                displayBox.add(newDisplay.getWidget(area))
            newDisplay.onSelected_private(self)
            newDisplay.onSelected(self)
        else:
            displayBox.add(newDisplay.getWidget(area))
            newDisplay.onSelected_private(self)
            newDisplay.onSelected(self)

        self.selectedDisplays[area] = newDisplay
        # show the video info display when we are showing a movie.
        if area == self.mainDisplay:
            watchable = newDisplay.getWatchable()
            if watchable:
                app.controller.playbackController.configure(watchable)

            if isinstance(newDisplay, VideoDisplay):
                self.windowChanger.changeState(self.windowChanger.VIDEO)
            else:
                self.windowChanger.changeState(self.windowChanger.BROWSING)
            if isinstance(newDisplay, HTMLDisplay):
                newDisplay.getWidget(area).child.grab_focus()

    @gtkSyncMethod
    def getDisplay(self, area):
        return self.selectedDisplays[area]

    @gtkAsyncMethod
    def about(self):
        if (self.aboutWidget is None):
            self.aboutWidget = gtk.AboutDialog()
            self.aboutWidget.set_name("Democracy Player")
            self.aboutWidget.set_version(config.get(prefs.APP_VERSION))
            self.aboutWidget.set_website("http://www.getdemocracy.com/")
            def delete_event_cb(widget, event):
                widget.hide()
                return True
            self.aboutWidget.connect ("delete_event", delete_event_cb)
            self.aboutWidget.set_transient_for (self.widgetTree['main-window'])
        self.aboutWidget.present()

    @gtkSyncMethod
    def updateVideoTime(self):
        renderer = app.controller.videoDisplay.activeRenderer
        videoTimeScale = self.widgetTree['video-time-scale']
        if renderer and not videoTimeScale.buttonsDown:
            try:
                self.videoLength = renderer.getDuration()
            except:
                self.videoLength = 1
            try:
                currentTime = renderer.getCurrentTime()
            except:
                currentTime = 0
            if self.videoLength < 1:
                self.videoLength = 1
            if currentTime < 0:
                currentTime = 0
            if currentTime > self.videoLength:
                currentTime = self.videoLength
            videoTimeScale.set_range(0, self.videoLength)
            videoTimeScale.set_value(renderer.getCurrentTime())
        return True

    @gtkAsyncMethod
    def setFullscreen(self, fullscreen):
        self.windowChanger.changeFullScreen (fullscreen)
        self.isFullscreen = fullscreen

    # Internal use: return an estimate of the size of a given display area
    # as a (width, height) pair, or None if no information's available.
    @gtkSyncMethod
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

    @gtkSyncMethod
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

    def getWidget(self, *args):
        return self.widget

    def unlink(self):
        pass

    def __del__(self):
        self.unlink()

###############################################################################
###############################################################################
