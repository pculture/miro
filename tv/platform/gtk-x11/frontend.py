import config

# Almost everything is split out into files under frontend-implementation.
from frontend_implementation.Application import Application
from frontend_implementation.MainFrame import MainFrame, NullDisplay
from frontend_implementation.UIBackendDelegate import UIBackendDelegate
from frontend_implementation.HTMLDisplay import HTMLDisplay, getDTVAPICookie, getDTVAPIURL
from frontend_implementation.VideoDisplay import VideoDisplay, PlaylistItem
from frontend_implementation.VideoDisplay import PlaybackController

import mozsetup
mozsetup.setupMozillaEnvironment()

def exit(returnCode):
    return returnCode

###############################################################################
###############################################################################
