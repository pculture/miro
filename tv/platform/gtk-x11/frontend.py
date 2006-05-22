import os
import config
import prefs
import gtk
from frontend_implementation.gtk_queue import gtkAsyncMethod

# Import MozillaBrowser ASAP.  On some systems the gtkmozembed module is
# linked against a different libxpcom than MozillaBrowser.  Importing it first
# ensures that MozillaBrowser's libxpcom gets linked to.
#
# NOTE: this could also lead to problems, since now gtkmozembed is being
# linked to a different libxpcom than it expects.  This way seems to be less
# bad though, so we'll use it for now.  See Bug #1560.
import MozillaBrowser

# Almost everything is split out into files under frontend-implementation.
from frontend_implementation.Application import Application
from frontend_implementation.MainFrame import MainFrame, NullDisplay
from frontend_implementation.UIBackendDelegate import UIBackendDelegate
from frontend_implementation.HTMLDisplay import HTMLDisplay, getDTVAPICookie, getDTVAPIURL
from frontend_implementation.VideoDisplay import VideoDisplay, PlaylistItem
from frontend_implementation.VideoDisplay import PlaybackController

# Create democracy directories in the user's home
support_dir = config.get(prefs.SUPPORT_DIRECTORY)
os.environ['APPDATA'] = support_dir # Needed to make bittorrent happy
if not os.path.exists(support_dir):
    os.makedirs(support_dir)

import mozsetup
mozsetup.setupMozillaEnvironment()

def exit(returnCode):
    return returnCode

@gtkAsyncMethod
def quit():
    gtk.main_quit()

###############################################################################
###############################################################################
