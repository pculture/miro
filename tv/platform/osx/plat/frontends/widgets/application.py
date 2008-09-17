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
import struct
import logging
import traceback

from objc import YES, NO, nil, signature
from AppKit import *
from Foundation import *
from PyObjCTools import AppHelper
from ExceptionHandling import NSExceptionHandler, NSLogAndHandleEveryExceptionMask

from miro import app
from miro import prefs
from miro import views
from miro import config
from miro import messages
from miro import filetypes
from miro import eventloop
from miro import singleclick
from miro.frontends.widgets.application import Application
from miro.plat import migrateappname
from miro.plat.utils import ensureDownloadDaemonIsTerminated, filenameTypeToOSFilename, osFilenamesToFilenameTypes
from miro.plat.frontends.widgets import video, osxmenus
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
        video.register_quicktime_components()

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
            NSExceptionHandler.defaultExceptionHandler().setExceptionHandlingMask_(NSLogAndHandleEveryExceptionMask)
            NSExceptionHandler.defaultExceptionHandler().setDelegate_(self)

            man = NSAppleEventManager.sharedAppleEventManager()
            man.setEventHandler_andSelector_forEventClass_andEventID_(
                self,
                "openURL:withReplyEvent:",
                struct.unpack(">i", "GURL")[0],
                struct.unpack(">i", "GURL")[0])

            ws = NSWorkspace.sharedWorkspace()
            wsnc = ws.notificationCenter()
            wsnc.addObserver_selector_name_object_(self, 'workspaceWillSleep:', NSWorkspaceWillSleepNotification, nil)
            wsnc.addObserver_selector_name_object_(self, 'workspaceDidWake:',   NSWorkspaceDidWakeNotification,   nil)

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

    def exceptionHandler_shouldLogException_mask_(self, handler, exception, mask):
        logging.warn("Unhandled exception: %s", exception.name())
        import traceback
        traceback.print_stack()
        return NO

    def applicationShouldHandleReopen_hasVisibleWindows_(self, appl, flag):
        if not flag:
            app.widgetapp.window.nswindow.makeKeyAndOrderFront_(nil)
        if app.widgetapp is not None and app.widgetapp.window is not None:
            mainWindow = app.widgetapp.window.nswindow
            if mainWindow.isMiniaturized():
                mainWindow.deminiaturize_(appl)            
        return NO

    def application_openFiles_(self, nsapp, filenames):
        filenames = osFilenamesToFilenameTypes(filenames)
        messages.OpenIndividualFiles(filenames).send_to_backend()
        nsapp.replyToOpenOrPrint_(NSApplicationDelegateReplySuccess)

    def workspaceWillSleep_(self, notification):
        def pauseRunningDownloaders(self=self):
            if views.initialized:
                views.remoteDownloads.confirmDBThread()
                self.pausedDownloaders = list()
                for dl in views.remoteDownloads:
                    if dl.getState() == 'downloading':
                        self.pausedDownloaders.append(dl)
                dlCount = len(self.pausedDownloaders)
                if dlCount > 0:
                    logging.info("System is going to sleep, suspending %d download(s)." % dlCount)
                    for dl in self.pausedDownloaders:
                        dl.pause(block=True)
        dc = eventloop.addUrgentCall(lambda:pauseRunningDownloaders(), "Suspending downloaders for sleep")
        # Until we can get proper delayed call completion notification, we're
        # just going to wait a few seconds here :)
        time.sleep(3)
        #dc.waitCompletion()

    def workspaceDidWake_(self, notification):
        def restartPausedDownloaders(self=self):
            dlCount = len(self.pausedDownloaders)
            if dlCount > 0:
                logging.info("System is awake from sleep, resuming %s download(s)." % dlCount)
                try:
                    for dl in self.pausedDownloaders:
                        dl.start()
                finally:
                    self.pausedDownloaders = list()
        eventloop.addUrgentCall(lambda:restartPausedDownloaders(), "Resuming downloaders after sleep")

    @signature('v@:@@')
    def openURL_withReplyEvent_(self, event, replyEvent):
        keyDirectObject = struct.unpack(">i", "----")[0]
        url = event.paramDescriptorForKeyword_(keyDirectObject).stringValue().decode('utf8')

        urlPattern = re.compile(r"^(.*?)://(.*)$")
        match = urlPattern.match(url)
        if match and match.group(1) == 'feed':
            url = match.group(2)
            match = urlPattern.match(url)
            if not match:
                url = u'http://%s' % url

        if url.startswith('http'):
            components = urlparse.urlparse(url)
            path = components[2]
            if filetypes.isVideoFilename(path):
                command = [lambda:app.htmlapp.newDownload(url), "Open HTTP Movie"]
            else:
                command = [lambda:app.htmlapp.addAndSelectFeed(url), "Open HTTP URL"]
        elif url.startswith('miro:'):
            command = [lambda:singleclick.addSubscriptionURL('miro:', 'application/x-miro', url), "Open Miro URL"]
        elif url.startswith('democracy:'):
            command = [lambda:singleclick.addSubscriptionURL('democracy:', 'application/x-democracy', url), "Open Democracy URL"]

        eventloop.addIdle(*command)
