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

from MainFrame import MainFrame
from Application import Application
from VideoDisplay import VideoDisplay, PlaybackController
from UIBackendDelegate import UIBackendDelegate
import UIStrings

from objc import nil
from AppKit import NSApplication

import app
import platformutils

###############################################################################

def exit(returnCode):
    NSApplication.sharedApplication().stop_(nil)

def quit(emergencyExit=False):
    if emergencyExit:
        NSApplication.sharedApplication().delegate().internalShutdown = True
    else:
        platformutils.ensureDownloadDaemonIsTerminated()
    NSApplication.sharedApplication().terminate_(nil)

###############################################################################

def inMainThread(function, args=None, kwargs=None):
    if args is None:
        args = ()
    if kwargs is None:
        kwargs = {}
    platformutils.callOnMainThread(function, *args, **kwargs)
