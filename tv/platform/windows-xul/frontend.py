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

# Almost everything is split out into files under frontend-implementation.
# Note: these can't be in just any order; there is some subtlety in the
# initialization order, so take care.

from frontend_implementation.HTMLDisplay import HTMLDisplay, getDTVAPIURL, getDTVAPICookie
from frontend_implementation.Application import Application
from frontend_implementation.UIBackendDelegate import UIBackendDelegate
from frontend_implementation.MainFrame import MainFrame
from frontend_implementation.VideoDisplay import VideoDisplay, PlaybackController
import frontend_implementation.startup as startup

# FIXME: I threw this here so distutils would find it --NN
import migrateappname

# these get set in components.pybridge.onStartup
jsBridge = None
vlcRenderer = None

currentVideoPath = None # gets changed in MainFrame.onSelectedTabChange()

def quit(emergencyExit=False):
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
