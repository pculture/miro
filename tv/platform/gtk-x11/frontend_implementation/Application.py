import gtk

import threading
from frontend_implementation.gtk_queue import queue
import gtcache
import config
import prefs
import gtk.glade
import platformutils

###############################################################################
#### Application object                                                    ####
###############################################################################

class Application:

    def __init__(self):
        #print "Application init"
        pass
    def Run(self):
        gtk.glade.bindtextdomain("democracyplayer", config.get(prefs.GETTEXT_PATHNAME))
        gtk.glade.textdomain("democracyplayer")

        queue.main_thread = threading.currentThread()
        platformutils.setMainThread()
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
