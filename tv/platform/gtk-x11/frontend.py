import os
import config

# Almost everything is split out into files under frontend-implementation.
from frontend_implementation.Application import Application
from frontend_implementation.MainFrame import MainFrame, NullDisplay
from frontend_implementation.UIBackendDelegate import UIBackendDelegate
from frontend_implementation.HTMLDisplay import HTMLDisplay, getDTVAPICookie, getDTVAPIURL
from frontend_implementation.VideoDisplay import VideoDisplay, PlaylistItem
from frontend_implementation.VideoDisplay import PlaybackController

# Create democracy directories in the user's home
support_dir = config.get(config.SUPPORT_DIRECTORY)
os.environ['APPDATA'] = support_dir # Needed to make bittorrent happy
if not os.path.exists(support_dir):
    os.makedirs(support_dir)
movie_dir = config.get(config.MOVIES_DIRECTORY)
if not os.path.exists(support_dir):
    os.makedirs(os.path.join(movie_dir,'Incomplete Downloads'))

#import mozsetup
#mozsetup.setupMozillaEnvironment()

def exit(returnCode):
    return returnCode

###############################################################################
###############################################################################
