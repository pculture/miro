from MainFrame import MainFrame, NullDisplay
from Application import Application
from HTMLDisplay import HTMLDisplay, getDTVAPICookie, getDTVAPIURL
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

def quit():
    if app.controller.databaseIsSetup:
        app.delegate.ensureDownloadDaemonIsTerminated()
    else:
        NSApplication.sharedApplication().delegate().internalShutdown = True
    NSApplication.sharedApplication().terminate_(nil)

###############################################################################

def inMainThread(function, args=None, kwargs=None):
    if args is None:
        args = ()
    if kwargs is None:
        kwargs = {}
    platformutils.callOnMainThread(function, *args, **kwargs)
