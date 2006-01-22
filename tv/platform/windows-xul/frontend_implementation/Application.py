import sys
import frontend
import asyncore
import time
import threading

###############################################################################
#### Application object                                                    ####
###############################################################################

class Application:

    def __init__(self):
	print "Application init"

    def runNonblocking(self):
        # Start the asynchronous I/O thread (mostly for the webserver
        # used to send events to the browsers.)
        ioThread = threading.Thread(name = "Asynchronous IO",
                                    target = ioThreadFunc)
        ioThread.setDaemon(True)
        ioThread.start()

        # Start the core.
	self.onStartup()

    # NEDS: arrange for onShutdown to be called

    def getBackendDelegate(self):
        return frontend.UIBackendDelegate()

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

def ioThreadFunc():
    # loop() shouldn't exit, because we keep some listening sockets
    # open; if it does, just try again
    while True:
        asyncore.loop()
        time.sleep(.1)

###############################################################################
###############################################################################
