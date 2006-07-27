import gtk

import threading
from frontend_implementation.gtk_queue import queue
import xlibhelper
import gettext
import locale
import gtk.glade
import resource
import platformutils

###############################################################################
#### Application object                                                    ####
###############################################################################

class Application:

    def __init__(self):
        #print "Application init"
        pass
    def Run(self):
        locale.setlocale(locale.LC_ALL, '')
        gettext.bindtextdomain("democracyplayer", resource.path("../../locale"))
        gettext.textdomain("democracyplayer")
        gettext.bind_textdomain_codeset("democracyplayer","UTF-8")
        gtk.glade.bindtextdomain("democracyplayer", resource.path("../../locale"))
        gtk.glade.textdomain("democracyplayer")

        queue.main_thread = threading.currentThread()
        platformutils.setMainThread()
        if xlibhelper.XInitThreads() == 0:
            print "WARNING: XInitThreads() failed!"
        gtk.threads_init()
        self.onStartup()
        gtk.main()
        self.onShutdown()

    def onStartup(self):
        # For overriding
        pass

    def onShutdown(self):
        # For overriding
        pass

    # This is called on OS X when we are handling a click on an RSS feed
    # button for Safari. NEEDS: add code here to register as a RSS feed
    # reader on Windows too. Just call this function when we're launched
    # to handle a click on a feed.
    def addAndSelectFeed(self, url):
        # For overriding
        pass

###############################################################################
###############################################################################
