import app
import frontend
import os
from xpcom import components
from util import quoteJS
from frontend_implementation.VideoDisplay import VideoDisplay
from frontend_implementation import urlcallbacks

###############################################################################
#### Main window                                                           ####
###############################################################################

class MainFrame:
    def __init__(self, appl):
        # Symbols by other parts of the program as arguments
        # to selectDisplay
        self.mainDisplay = "mainDisplay"
        self.channelsDisplay = "channelsDisplay"
        self.videoInfoDisplay = "videoInfoDisplay"

        # Displays selected in each area, for generating deselection
        # messages.
        self.selectedDisplays = {}
        urlcallbacks.installChannelGuideCallback(self.channelGuideCallback)

    def onSelectedTabChange(self, strings, actionGroups, guideURL,
            videoFilename):
        app.controller.setGuideURL(guideURL)
        if videoFilename is not None:
            frontend.jsBridge.updateVideoFilename(os.path.basename(videoFilename))
        else:
            frontend.jsBridge.updateVideoFilename('')
        frontend.currentVideoPath = videoFilename
        for group, enabled in actionGroups.items():
            frontend.jsBridge.setActionGroupEnabled(group, enabled)
        for name, label in strings.items():
            id = 'menuitem-%s' % name.replace('_', '-')
            frontend.jsBridge.updateLabel(id, label)

    def selectDisplay(self, newDisplay, area):
        """Install the provided 'newDisplay' in the requested area"""

        # Generate a deselection message for the previously selected
        # display in this area, if any
        if area in self.selectedDisplays:
            oldDisplay = self.selectedDisplays[area]
            if oldDisplay:
                oldDisplay.onDeselected_private(self)
                oldDisplay.onDeselected(self)
                oldDisplay.removedFromArea()

        # Generate a selection message for the new display, if any
        self.selectedDisplays[area] = newDisplay
        if newDisplay:
            newDisplay.onSelected_private(self)
            newDisplay.onSelected(self)
            newDisplay.setArea(area)
        if area == self.mainDisplay:
            if isinstance(newDisplay, VideoDisplay):
                frontend.jsBridge.showVideoDisplay()
            else:
                frontend.jsBridge.hideVideoDisplay()
                frontend.jsBridge.leaveFullscreen()

    def channelGuideCallback(self, url):
        try:
            # assume all channel guide URLS come from the mainDisplay
            return self.selectedDisplays[self.mainDisplay].onURLLoad(url)
        except KeyError:
            return True

    def getDisplay(self, area):
        return self.selectedDisplays.get(area)

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
