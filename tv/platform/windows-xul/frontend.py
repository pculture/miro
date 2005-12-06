#import feed
#import config
#import resource
#import template
#import database

#import re
#import os
#import tempfile
#import sys
#import time
#import threading

# Almost everything is split out into files under frontend-implementation.
from frontend_implementation.Application import Application
from frontend_implementation.MainFrame import MainFrame, NullDisplay
from frontend_implementation.UIBackendDelegate import UIBackendDelegate
from frontend_implementation.HTMLDisplay import HTMLDisplay
from frontend_implementation.VideoDisplay import VideoDisplay, PlaylistItem, PlaybackController

# Python's sys.exit isn't sufficient in a Windows application. It's not
# clear why.
from ctypes.wintypes import windll
def exit(returnCode):
    windll.kernel32.ExitProcess(returnCode)

# NEEDS: preferences
#        config.set(config.RUN_DTV_AT_STARTUP, <bool>)
#        config.set(config.CHECK_CHANNELS_EVERY_X_MN, minutes)
#        config.set(config.LIMIT_UPSTREAM, <bool>)
#        config.set(config.UPSTREAM_LIMIT_IN_KBS, <real>)
#        config.set(config.PRESERVE_X_GB_FREE, <real>)


###############################################################################
###############################################################################
