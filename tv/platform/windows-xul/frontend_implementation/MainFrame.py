import frontend
from xpcom import components
import threading

###############################################################################
#### Main window                                                           ####
###############################################################################

class MainFrame:
    def __init__(self, appl):
        # Symbols by other parts of the program as as arguments
        # to selectDisplay
        self.mainDisplay = "mainDisplay"
        self.channelsDisplay = "channelsDisplay"
        self.videoInfoDisplay = "videoInfoDisplay"

        # Displays selected in each area, for generating deselection
        # messages.
        self.selectedDisplays = {}

        ## BEGIN SYNCHRONOUS MOZILLA CALLS ##

	# Find the XUL document corresponding to the window.
	#klass = components.classes["@participatoryculture.org/dtv/pybridge;1"]
	#pybridge = klass.getService(components.interfaces.pcfIDTVPyBridge)
	#self.document = pybridge.mainWindowDocument

        # Grab the Javascript bridge so we can call our Javascript helpers.
	#klass = components.classes["@participatoryculture.org/dtv/jsbridge;1"]
	#self.jsbridge = klass.getService(components.interfaces.pcfIDTVJSBridge)

        ## END SYNCHRONOUS MOZILLA CALLS ##

    def selectDisplay(self, newDisplay, area):
        """Install the provided 'newDisplay' in the requested area"""

	# Generate a deselection message for the previously selected
	# display in this area, if any
        if area in self.selectedDisplays:
            oldDisplay = self.selectedDisplays[area]
            if oldDisplay:
                oldDisplay.onDeselected_private(self)
                oldDisplay.onDeselected(self)

        # NEEDS: case out instances for HTMLDisplay and VideoDisplay
        self.selectHTML(newDisplay, area)

	# Generate a selection message for the new display, if any
        self.selectedDisplays[area] = newDisplay
	if newDisplay:
	    newDisplay.onSelected_private(self)
	    newDisplay.onSelected(self)

    def selectHTML(self, display, area):
        newURL = display.getURL()
        # make the display load newURL. that's it!

        ## BEGIN SYNCHRONOUS MOZILLA CALLS ##

        print "Telling %s to load %s" % (area, newURL)
        #self.jsbridge.xulNavigateDisplay(self.document, area, newURL)
        frontend.execChromeJS("navigateDisplay('%s', '%s');" % (area, newURL))
        print "Came back from that"

        ## END SYNCHRONOUS MOZILLA CALLS ##

    # Internal use: return an estimate of the size of a given display area
    # as a (width, height) pair, or None if no information's available.
    def getDisplaySizeHint(self, area):
	return None

    def unlink(self):
        pass

    def __del__(self):
        self.unlink()

###############################################################################
###############################################################################
