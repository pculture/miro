import frontend
from xpcom import components
from util import quoteJS
from frontend_implementation.VideoDisplay import VideoDisplay

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

	# Generate a selection message for the new display, if any
        self.selectedDisplays[area] = newDisplay
	if newDisplay:
	    newDisplay.onSelected_private(self)
	    newDisplay.onSelected(self)
            newDisplay.setArea(area)
        return
        # NEEDS: case out instances for HTMLDisplay and VideoDisplay
        self.selectHTML(newDisplay, area)
        if area == self.mainDisplay:
            if isinstance(newDisplay, VideoDisplay):
                frontend.execChromeJS("setVideoInfoDisplayHidden('false')")
            else:
                frontend.execChromeJS("setVideoInfoDisplayHidden('true')")

    def getDisplay(self, area):
        return self.selectedDisplays[area]

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
