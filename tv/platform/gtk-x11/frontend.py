# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

import os
import config
import prefs
import sys

shouldSyncX = '--sync' in sys.argv

# These should be set by miro.real, but these are sane defaults
useXineHack = True
defaultXineDriver = "xv"

# Switch to a dummy frontend in the case we're running tests and
# DISPLAY isn't set
try:
    import gtk
    hasGTK = True
except ImportError:
    print "DTV: Warning: could not import GTK (is DISPLAY set?)"
    hasGTK = False
else:
    from frontend_implementation.gtk_queue import gtkAsyncMethod

if hasGTK:
    # Import MozillaBrowser ASAP.  On some systems the gtkmozembed
    # module is linked against a different libxpcom than
    # MozillaBrowser.  Importing it first ensures that
    # MozillaBrowser's libxpcom gets linked to.
    #
    # NOTE: this could also lead to problems, since now gtkmozembed is
    # being linked to a different libxpcom than it expects.  This way
    # seems to be less bad though, so we'll use it for now.  See Bug
    # #1560.
    import MozillaBrowser

    # Almost everything is split out into files under
    # frontend-implementation.
    from frontend_implementation.Application import Application
    from frontend_implementation.MainFrame import MainFrame, NullDisplay
    from frontend_implementation.UIBackendDelegate import UIBackendDelegate
    from frontend_implementation.HTMLDisplay import HTMLDisplay, getDTVAPICookie, getDTVAPIURL
    from frontend_implementation.VideoDisplay import VideoDisplay
    from frontend_implementation.VideoDisplay import PlaybackController
else:
    class Application:
        pass
    class MainFrame:
        pass
    class NullDisplay:
        pass
    class UIBackendDelegate:
        pass
    class HTMLDisplay:
        pass
    class VideoDisplay:
        pass
    class PlaybackController:
        pass

# Create miro directories in the user's home
support_dir = config.get(prefs.SUPPORT_DIRECTORY)
os.environ['APPDATA'] = support_dir # Needed to make bittorrent happy
if not os.path.exists(support_dir):
    os.makedirs(support_dir)

if hasGTK:
    import mozsetup
    mozsetup.setupMozillaEnvironment()

def exit(returnCode):
    return returnCode

if hasGTK:
    @gtkAsyncMethod
    def quit(emergencyExit=False):
        gtk.main_quit()

    @gtkAsyncMethod
    def inMainThread(function, args=None, kwargs=None):
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        function(*args, **kwargs)

###############################################################################
###############################################################################
