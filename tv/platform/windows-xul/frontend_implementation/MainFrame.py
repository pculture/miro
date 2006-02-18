import frontend
from xpcom import components
import threading
from util import quoteJS

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

        frontend.execChromeJS("navigateDisplay('%s', '%s');" % \
                              (quoteJS(area), quoteJS(newURL)))

    def selectURL(self, url, area):
	# Generate a deselection message for the previously selected
	# display in this area, if any
        if area in self.selectedDisplays:
            oldDisplay = self.selectedDisplays[area]
            if oldDisplay:
                oldDisplay.onDeselected_private(self)
                oldDisplay.onDeselected(self)
            self.selectedDisplays[area] = None

        # Now just make Mozilla load the new URL over there
        frontend.execChromeJS("navigateDisplay('%s', '%s');" % \
                              (quoteJS(area), quoteJS(url)))

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
