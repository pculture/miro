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

import os
import re
import time
import struct
import logging
import urlparse

from objc import YES, NO, nil, signature, IBOutlet
from AppKit import *
from Foundation import *
from PyObjCTools import AppHelper
from ExceptionHandling import NSExceptionHandler, NSLogAndHandleEveryExceptionMask

from gestalt import gestalt

from miro import app
from miro import views
from miro import prefs
from miro import config
from miro import dialogs
from miro.frontends.html.main import HTMLApplication
from miro import filetypes
from miro import eventloop
from miro import autoupdate
from miro import singleclick
from miro.plat.utils import ensureDownloadDaemonIsTerminated, osFilenamesToFilenameTypes

from miro.gtcache import gettext as _

from miro.plat.frontends.html import Preferences
from miro.plat.frontends.html import GrowlNotifier
from miro.plat.frontends.html import SparkleUpdater

###############################################################################

class Application(HTMLApplication):

    def __init__(self):
        appl = NSApplication.sharedApplication()
        NSBundle.loadNibNamed_owner_(u"MainMenu", appl)
        HTMLApplication.__init__(self)

    def quitUI(self):
        ensureDownloadDaemonIsTerminated()
        NSApplication.sharedApplication().terminate_(nil)

    def run(self):
        if self.checkOtherAppInstances():
            eventloop.connect('begin-loop', self.beginLoop)
            eventloop.connect('end-loop', self.endLoop)
            AppHelper.runEventLoop()
        else:
            logging.warning('Another instance of %s is already running! Quitting now.' % config.get(prefs.SHORT_APP_NAME))

    def checkOtherAppInstances(self):
        ourBundleIdentifier = NSBundle.mainBundle().bundleIdentifier()
        applications = NSWorkspace.sharedWorkspace().launchedApplications()
        democracies = [appl for appl in applications if appl.get('NSApplicationBundleIdentifier') == ourBundleIdentifier]
        alone = len(democracies) == 1

        if not alone:
            ourBundlePath = NSBundle.mainBundle().bundlePath()
            otherInstance = [dem['NSApplicationPath'] for dem in democracies if dem['NSApplicationPath'] != ourBundlePath]
            if len(otherInstance) == 1:
                NSWorkspace.sharedWorkspace().launchApplication_(otherInstance[0])

        return alone

    def finishStartupSequence(self):
        NSApplication.sharedApplication().delegate().finishStartupSequence()

    ### eventloop (our own one, not the Cocoa one) delegate methods

    def beginLoop(self, loop):
        loop.pool = NSAutoreleasePool.alloc().init()

    def endLoop(self, loop):
        del loop.pool

###############################################################################

class AppController (NSObject):

    playPauseMenuItem = IBOutlet('playPauseMenuItem')

    def applicationWillFinishLaunching_(self, notification):
        NSExceptionHandler.defaultExceptionHandler().setExceptionHandlingMask_(NSLogAndHandleEveryExceptionMask)
        NSExceptionHandler.defaultExceptionHandler().setDelegate_(self)
        
        SparkleUpdater.setup()
        
        man = NSAppleEventManager.sharedAppleEventManager()
        man.setEventHandler_andSelector_forEventClass_andEventID_(
            self,
            "openURL:withReplyEvent:",
            struct.unpack(">i", "GURL")[0],
            struct.unpack(">i", "GURL")[0])

        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self, 'videoWillPlay:', u'videoWillPlay',  nil)
        nc.addObserver_selector_name_object_(self, 'videoWillStop:', u'videoWillPause', nil)
        nc.addObserver_selector_name_object_(self, 'videoWillStop:', u'videoWillStop',  nil)
        
        ws = NSWorkspace.sharedWorkspace()
        wsnc = ws.notificationCenter()
        wsnc.addObserver_selector_name_object_(self, 'workspaceWillSleep:', NSWorkspaceWillSleepNotification, nil)
        wsnc.addObserver_selector_name_object_(self, 'workspaceDidWake:',   NSWorkspaceDidWakeNotification,   nil)
        
        self.openQueue = list()
        self.pausedDownloaders = list()
        self.emergencyShutdown = False
        
    def applicationDidFinishLaunching_(self, notification):
        # Startup
        app.htmlapp.startup()

        # The database should be ready at this point, check Miro migration.
        from miro.plat import migrateappname
        migrateappname.migrateVideos('Democracy', 'Miro')

        # Initialize the Growl notifier
        GrowlNotifier.register()
    
    def finishStartupSequence(self):
        for command in self.openQueue:
            eventloop.addUrgentCall(*command)
    
    def applicationDidBecomeActive_(self, notification):
        if app.htmlapp.frame is not None:
            # This should hopefully avoid weird things like #1722
            app.htmlapp.frame.controller.window().contentView().setNeedsDisplay_(YES)

    def applicationShouldTerminate_(self, sender):
        # External termination requests (through Dock menu or AppleScript) call
        # [NSApplication terminate:] directly, which breaks our shutdown sequence.
        # To fix this we simply check an internal flag which is only True when 
        # the correct shutdown call is made. Otherwise we cancel the current
        # shutdown process and schedule the correct one.
        result = NSTerminateNow
        if not eventloop.finished():
            eventloop.addUrgentCall(lambda:self.shutdown_(nil), "Shutdowning")
            result = NSTerminateLater
        return result
    
    def applicationWillTerminate_(self, notification):
        # Reset the application icon to its default state
        defaultAppIcon = NSImage.imageNamed_(u'NSApplicationIcon')
        NSApplication.sharedApplication().setApplicationIconImage_(defaultAppIcon)
        
        if not self.emergencyShutdown:
            # Ensure that the download daemon is not running anymore at this point
            ensureDownloadDaemonIsTerminated()    
            # Call shutdown on backend
            app.controller.onShutdown()

    def applicationShouldHandleReopen_hasVisibleWindows_(self, appl, flag):
        if not flag:
            self.showMainWindow_(appl)
        if app.controller is not None and app.htmlapp.frame is not None:
            mainWindow = app.htmlapp.frame.controller.window()
            if mainWindow.isMiniaturized():
                mainWindow.deminiaturize_(appl)            
        return NO

    def downloaderDaemonDidTerminate_(self, notification):
        task = notification.object()
        status = task.terminationStatus()
        logging.info("Downloader daemon has been terminated (status: %d)" % status)

    def application_openFiles_(self, nsapp, filenames):
        filenames = osFilenamesToFilenameTypes(filenames)
        eventloop.addUrgentCall(lambda:singleclick.handleCommandLineArgs(filenames), "Open local file(s)")
        nsapp.replyToOpenOrPrint_(NSApplicationDelegateReplySuccess)

    def exceptionHandler_shouldLogException_mask_(self, handler, exception, mask):
        logging.warn("Unhandled exception: %s", exception.name())
        import traceback
        traceback.print_stack()
        return NO
        
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

    def videoWillPlay_(self, notification):
        self.playPauseMenuItem.setTitle_(_(u'Pause Video'))

    def videoWillStop_(self, notification):
        self.playPauseMenuItem.setTitle_(_(u'Play Video'))

    def checkQuicktimeVersion(self, showError):
        supported = gestalt('qtim') >= 0x07000000
        
        if not supported and showError:
            summary = _(u'Unsupported version of Quicktime')
            message = _(u'To run %s you need the most recent version of Quicktime, which is a free update.') % (config.get(prefs.LONG_APP_NAME), )
            def callback(dialog):
                if dialog.choice == dialogs.BUTTON_DOWNLOAD:
                    url = NSURL.URLWithString_(u'http://www.apple.com/quicktime/download')
                    NSWorkspace.sharedWorkspace().openURL_(url)
                else:
                    self.shutdown_(nil)              
            dlog = dialogs.ChoiceDialog(summary, message, dialogs.BUTTON_DOWNLOAD, dialogs.BUTTON_QUIT)
            dlog.run(callback)
        
        return supported

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

        if app.controller.finishedStartup:
            eventloop.addIdle(*command)
        else:
            self.openQueue.append(command)

    def donate_(self, sender):
        donateURL = NSURL.URLWithString_(config.get(prefs.DONATE_URL))
        NSWorkspace.sharedWorkspace().openURL_(donateURL)

    def checkForUpdates_(self, sender):
        app.htmlapp.checkForUpdates()

    def showMainWindow_(self, sender):
        if app.controller is not None and app.htmlapp.frame is not None:
            app.htmlapp.frame.controller.window().makeKeyAndOrderFront_(sender)

    def showPreferencesWindow_(self, sender):
        Preferences.showWindow()

    def openFile_(self, sender):
        openPanel = NSOpenPanel.openPanel()
        openPanel.setAllowsMultipleSelection_(YES)
        openPanel.setCanChooseDirectories_(NO)
        result = openPanel.runModalForDirectory_file_types_(NSHomeDirectory(), nil, nil)
        if result == NSOKButton:
            filenames = osFilenamesToFilenameTypes(openPanel.filenames())
            eventloop.addUrgentCall(lambda:singleclick.parseCommandLineArgs(filenames), "Open local file(s)")
    
    def downloadVideo_(self, sender):
        app.htmlapp.newDownload()
    
    def importChannels_(self, sender):
        app.htmlapp.importChannels()
    
    def exportChannels_(self, sender):
        app.htmlapp.exportChannels()
    
    def shutdown_(self, sender):
        app.htmlapp.quit()

    def validateMenuItem_(self, item):
        return item.action() in ('donate:', 'checkForUpdates:', 'showMainWindow:',
                                 'showPreferencesWindow:', 'addGuide:', 
                                 'openFile:', 'downloadVideo:', 'importChannels:', 
                                 'exportChannels:', 'shutdown:')

###############################################################################
