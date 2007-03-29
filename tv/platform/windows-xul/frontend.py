# Almost everything is split out into files under frontend-implementation.
# Note: these can't be in just any order; there is some subtlety in the
# initialization order, so take care.
from frontend_implementation.HTMLDisplay import HTMLDisplay, getDTVAPIURL, getDTVAPICookie
from frontend_implementation.Application import Application
from frontend_implementation.UIBackendDelegate import UIBackendDelegate
from frontend_implementation.MainFrame import MainFrame
from frontend_implementation.VideoDisplay import VideoDisplay, PlaybackController
import frontend_implementation.startup as startup

# these get set in components.pybridge.onStartup
jsBridge = None
vlcRenderer = None

currentVideoPath = None # gets changed in MainFrame.onSelectedTabChange()

def quit():
    jsBridge.closeWindow()

# Python's sys.exit isn't sufficient in a Windows application. It's not
# clear why.
# NEEDS: this is probably *not* what we want to do under XUL.
from ctypes.wintypes import windll
def exit(returnCode):
    windll.kernel32.ExitProcess(returnCode)

def inMainThread(function, args=None, kwargs=None):
    # TODO: IMPLEMENT THIS CORRECTLY (Currently calling on the same thread)
    if args is None:
        args = ()
    if kwargs is None:
        kwargs = {}
    return function(*args, **kwargs)
    
# NEEDS: preferences
#        config.set(prefs.RUN_DTV_AT_STARTUP, <bool>)
#        config.set(prefs.CHECK_CHANNELS_EVERY_X_MN, minutes)
#        config.set(prefs.LIMIT_UPSTREAM, <bool>)
#        config.set(prefs.UPSTREAM_LIMIT_IN_KBS, <real>)
#        config.set(prefs.PRESERVE_X_GB_FREE, <real>)
