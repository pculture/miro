import app
import pygtk
pygtk.require('2.0')
import gtk
import gobject

from frontend import *
from frontend_implementation.gtk_queue import gtkMethod

###############################################################################
#### Initialization code: window classes, invisible toplevel parent        ####
###############################################################################


###############################################################################
#### Main window                                                           ####
###############################################################################

# Strategy: for now, a hash from names to hwnds. We put one child in each
# to completely fill it. selectdisplay changes this child.
#
# For later, embedding a browser in a browser, and sending control
# commands to it. Yeah, that's the story. Either that or just overlay the
# subordinate browser windows on top and have explicit resize logic for
# them.
#
# May want to use binary element behaviors to grab, eg, current bounding
# box of a div, and use that to site the window.

# NEEDS: save/restore window position and size
class MainFrame:
    def __init__(self, appl):
        """The initially active display will be an instance of NullDisplay."""

        # Symbols by other parts of the program as as arguments
        # to selectDisplay
        self.mainDisplay = "mainDisplay"
        self.channelsDisplay = "channelsDisplay"
        self.collectionDisplay = "collectionDisplay"

        # Child display state
        self.selectedDisplays = {}
        self.windowCreated = False
        gobject.idle_add(self.ensureWindowCreated)

    def createWindow(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title("DTV")
        window.connect("destroy", lambda w: gtk.main_quit())
        window.set_border_width(10)
        window.set_size_request(750, 550)

        # create a vpaned widget and add it to our toplevel window
        self.hpaned = gtk.HPaned()
        self.hpaned.set_position(200)
        window.add(self.hpaned)
        self.hpaned.show()

        window.show()

    def ensureWindowCreated(self):
        if not self.windowCreated:
            self.createWindow()
            self.windowCreated = True

    @gtkMethod
    def selectDisplay(self, newDisplay, area):
        """Install the provided 'newDisplay' in the requested area"""
        print "selectDisplay %s  in %s" % (newDisplay, area)

        oldDisplay = None # protect from GC at least until new window's in
        print "selecting display"
        if self.selectedDisplays.has_key(area):
            oldDisplay = self.selectedDisplays[area]
            if oldDisplay:
                oldDisplay.onDeselected_private(self)
                oldDisplay.onDeselected(self)
            self.hpaned.remove(oldDisplay.getWidget())

        if area == self.mainDisplay:
            self.hpaned.add2(newDisplay.getWidget())

        elif area == self.channelsDisplay:
            self.hpaned.add1(newDisplay.getWidget())

        self.selectedDisplays[area] = newDisplay
        newDisplay.onSelected_private(self)
        newDisplay.onSelected(self)

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
