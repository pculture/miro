# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

import sys
import logging
import traceback

from objc import YES, NO, nil
from AppKit import *
from Foundation import *
from PyObjCTools import AppHelper

from miro import app
from miro import eventloop
from miro import prefs
from miro import config
from miro.frontends.widgets.application import Application
from miro.plat import migrateappname
from miro.plat.utils import ensureDownloadDaemonIsTerminated, filenameTypeToOSFilename
from miro.plat.frontends.widgets import osxmenus
from miro.plat.frontends.widgets.rect import Rect

class OSXApplication(Application):

    def __init__(self):
        Application.__init__(self)
        self.gotQuit = False

    def connect_to_signals(self):
        Application.connect_to_signals(self)
        eventloop.connect('begin-loop', self.beginLoop)
        eventloop.connect('end-loop', self.endLoop)

    def handleStartupSuccess(self, obj):
        migrateappname.migrateVideos('Democracy', 'Miro')
        osxmenus.populate_menu()
        Application.handleStartupSuccess(self, obj)

    ### eventloop (our own one, not the Cocoa one) delegate methods
    def beginLoop(self, loop):
        loop.pool = NSAutoreleasePool.alloc().init()

    def endLoop(self, loop):
        del loop.pool

    def run(self):
        self.app_controller = AppController.alloc().initWithApp_(self)
        NSApplication.sharedApplication().setDelegate_(self.app_controller)
        NSApplicationMain(sys.argv)        
    
    def do_quit(self):
        windowFrame = self.window.nswindow.frame()
        windowFrame.size.height -= 22
        config.set(prefs.MAIN_WINDOW_FRAME, NSStringFromRect(windowFrame))
        config.save()
        Application.do_quit(self)
            
    def quit_ui(self):
        self.gotQuit = True
        NSApplication.sharedApplication().terminate_(nil)

    def get_clipboard_text(self):
        return NSPasteboard.generalPasteboard().stringForType_(NSStringPboardType)

    def copy_text_to_clipboard(self, text):
        pb = NSPasteboard.generalPasteboard()
        pb.declareTypes_owner_([NSStringPboardType], self)
        pb.setString_forType_(text, NSStringPboardType)

    def open_url(self, url):
        # We could use Python's webbrowser.open() here, but
        # unfortunately, it doesn't have the same semantics under UNIX
        # as under other OSes. Sometimes it blocks, sometimes it doesn't.
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))

    def open_file(self, fn):
        filename = filenameTypeToOSFilename(fn)
        NSWorkspace.sharedWorkspace().selectFile_inFileViewerRootedAtPath_(filename, nil)
    
    def get_main_window_dimensions(self):
        windowFrame = config.get(prefs.MAIN_WINDOW_FRAME)
        if windowFrame is None:
            windowFrame = (0,0,800,600)
        else:
            rect = NSRectFromString(windowFrame)
            windowFrame = (rect.origin.x, rect.origin.y, rect.size.width, rect.size.height)
        return Rect(*windowFrame)

class AppController(NSObject):

    def initWithApp_(self, application):
        self.init()
        self.application = application
        return self

    def applicationDidFinishLaunching_(self, notification):
        try:
            self.application.startup()
        except:
            traceback.print_exc()
            NSApplication.sharedApplication().terminate_(nil)

    def applicationShouldTerminate_(self, sender):
        # External termination requests (through Dock menu or AppleScript) call
        # [NSApplication terminate:] directly, which breaks our shutdown sequence.
        # To fix this we simply check an internal flag which is only True when 
        # the correct shutdown call is made. Otherwise we cancel the current
        # shutdown process and schedule the correct one.
        result = NSTerminateNow
        if not self.application.gotQuit:
            self.application.quit()
            result = NSTerminateLater
        return result

    def downloaderDaemonDidTerminate_(self, notification):
        task = notification.object()
        status = task.terminationStatus()
        logging.info("Downloader daemon has been terminated (status: %d)" % status)

    def applicationWillTerminate_(self, notification):
        # Reset the application icon to its default state
        defaultAppIcon = NSImage.imageNamed_(u'NSApplicationIcon')
        NSApplication.sharedApplication().setApplicationIconImage_(defaultAppIcon)

        ensureDownloadDaemonIsTerminated()    
        app.controller.onShutdown()
