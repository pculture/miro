import config

# Almost everything is split out into files under frontend-implementation.
from frontend_implementation.Application import Application
from frontend_implementation.MainFrame import MainFrame, NullDisplay
from frontend_implementation.UIBackendDelegate import UIBackendDelegate
from HTMLDisplay import HTMLDisplay
from frontend_implementation.VideoDisplay import VideoDisplay, PlaylistItem
import frontend_implementation.HTMLDisplayHelper

import gtkmozembed

gtkmozembed.gtk_moz_embed_set_profile_path(config.get(config.SUPPORT_DIRECTORY),'mozilla')

def exit(returnCode):
    return returnCode

###############################################################################
###############################################################################
