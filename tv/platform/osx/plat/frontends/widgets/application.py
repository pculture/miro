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

import traceback

from objc import YES, NO, nil
from AppKit import *
from Foundation import *
from PyObjCTools import AppHelper

from miro import app
from miro import eventloop
from miro.frontends.widgets.application import Application
from miro.plat import migrateappname
from miro.plat.utils import ensureDownloadDaemonIsTerminated

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
        Application.handleStartupSuccess(self, obj)

    ### eventloop (our own one, not the Cocoa one) delegate methods
    def beginLoop(self, loop):
        loop.pool = NSAutoreleasePool.alloc().init()

    def endLoop(self, loop):
        del loop.pool

    def run(self):
        AppHelper.runEventLoop(main=self.main)

    def quitUI(self):
        self.gotQuit = True
        NSApplication.sharedApplication().terminate_(nil)

    def main(self, args):
        try:
            # initialize the global Application object
            NSApplication.sharedApplication()
            self.startup()
            self.installAppController()
        except:
            print "error starting up"
            traceback.print_exc()
            NSApplication.sharedApplication().terminate_(nil)
        NSApplicationMain(args)

    def installAppController(self):
        self.app_controller = AppController.alloc().initWithApp_(self)
        # Keeping a reference to AppController is very important!
        # setDelegate_ creates a weak reference, so we need to make sure that
        # we keep the object around.
        NSApplication.sharedApplication().setDelegate_(self.app_controller)

    def open_url(self, url):
        # We could use Python's webbrowser.open() here, but
        # unfortunately, it doesn't have the same semantics under UNIX
        # as under other OSes. Sometimes it blocks, sometimes it doesn't.
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))

class AppController(NSObject):
    def initWithApp_(self, application):
        self.init()
        self.application = application
        return self

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

    def applicationWillTerminate_(self, notification):
        ensureDownloadDaemonIsTerminated()    
        app.controller.onShutdown()
