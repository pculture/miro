import sys
import frontend

from ctypes import *
from ctypes.wintypes import *
atl = windll.atl

###############################################################################
#### Application object                                                    ####
###############################################################################

class Application:

    def __init__(self):
	print "Application init"

    def Run(self):
	self.onStartup()

	# Standard Windows message pump
	# Alternative: ret = win32gui.PumpMessages()
	user32 = windll.user32
	msg = MSG()
        returnCode = 0
	while True:
            returnCode = user32.GetMessageA(byref(msg), None, 0, 0)
            if not returnCode:
                break
	    user32.TranslateMessage(byref(msg))
            user32.DispatchMessageA(byref(msg))

	self.onShutdown()
        frontend.exit(returnCode)

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

###############################################################################
###############################################################################
