import os
import re
import time
import struct
import logging
import urlparse

from objc import YES, NO, nil, signature
from AppKit import *
from Foundation import *
from PyObjCTools import NibClassBuilder, AppHelper

from gestalt import gestalt

import app
import views
import prefs
import config
import dialogs
import eventloop
import autoupdate
import singleclick

from platformutils import osFilenamesToFilenameTypes
from gtcache import gettext as _

from Preferences import PreferencesWindowController
import GrowlNotifier

NibClassBuilder.extractClasses(u"MainMenu")

###############################################################################

class Application:

    def __init__(self):
        appl = NSApplication.sharedApplication()
        NSBundle.loadNibNamed_owner_(u"MainMenu", appl)
        controller = appl.delegate()

    def Run(self):
        if self.checkOtherDemocracyInstances():
            eventloop.setDelegate(self)
            AppHelper.runEventLoop()
        else:
            logging.warning('Another instance of Democracy is already running! Quitting now.')

    def checkOtherDemocracyInstances(self):
        ourBundleIdentifier = NSBundle.mainBundle().bundleIdentifier()
        applications = NSWorkspace.sharedWorkspace().launchedApplications()
        democracies = [appl for appl in applications if appl['NSApplicationBundleIdentifier'] == ourBundleIdentifier]
        alone = len(democracies) == 1

        if not alone:
            ourBundlePath = NSBundle.mainBundle().bundlePath()
            otherDemocracy = [dem['NSApplicationPath'] for dem in democracies if dem['NSApplicationPath'] != ourBundlePath]
            if len(otherDemocracy) == 1:
                NSWorkspace.sharedWorkspace().launchApplication_(otherDemocracy[0])

        return alone

    def onStartup(self):
        # For overriding
        pass

    def onShutdown(self):
        # For overriding
        pass

    def addAndSelectFeed(self, url):
        # For overriding
        pass

    ### eventloop (the Democracy one, not the Cocoa one) delegate methods

    def beginLoop(self, loop):
        loop.pool = NSAutoreleasePool.alloc().init()

    def endLoop(self, loop):
        del loop.pool

###############################################################################

class AppController (NibClassBuilder.AutoBaseClass):

    def applicationWillFinishLaunching_(self, notification):
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
        
        self.pausedDownloaders = list()
        self.internalShutdown = False
        self.emergencyShutdown = False
        
    def applicationDidFinishLaunching_(self, notification):
        # The [NSURLRequest setAllowsAnyHTTPSCertificate:forHost:] selector is
        # not documented anywhere, so I assume it is not public. It is however 
        # a very clean and easy way to allow us to load our channel guide from
        # https, so let's use it here anyway :)
        components = urlparse.urlparse(config.get(prefs.CHANNEL_GUIDE_URL))
        channelGuideHost = components[1]
        NSURLRequest.setAllowsAnyHTTPSCertificate_forHost_(YES, unicode(channelGuideHost))

        # Startup
        app.controller.onStartup()

        # Initialize the Growl notifier
        GrowlNotifier.register()
            
    def applicationDidBecomeActive_(self, notification):
        if app.controller.frame is not None:
            # This should hopefully avoid weird things like #1722
            app.controller.frame.controller.window().contentView().setNeedsDisplay_(YES)

    def applicationShouldTerminate_(self, sender):
        # External termination requests (through Dock menu or AppleScript) call
        # [NSApplication terminate:] directly, which breaks our shutdown sequence.
        # To fix this we simply check an internal flag which is only True when 
        # the correct shutdown call is made. Otherwise we cancel the current
        # shutdown process and schedule the correct one.
        result = NSTerminateNow
        if not self.internalShutdown:
            eventloop.addUrgentCall(lambda:self.shutdown_(nil), "Shutdowning")
            result = NSTerminateLater
        return result
    
    def applicationWillTerminate_(self, notification):
        # Reset the application icon to its default state
        defaultAppIcon = NSImage.imageNamed_(u'NSApplicationIcon')
        NSApplication.sharedApplication().setApplicationIconImage_(defaultAppIcon)
        
        if not self.emergencyShutdown:
            # Ensure that the download daemon is not running anymore at this point
            app.delegate.waitUntilDownloadDaemonExit()    
            # Call shutdown on backend
            app.controller.onShutdown()

    def applicationShouldHandleReopen_hasVisibleWindows_(self, appl, flag):
        if not flag:
            self.showMainWindow_(appl)
        if app.controller is not None and app.controller.frame is not None:
            mainWindow = app.controller.frame.controller.window()
            if mainWindow.isMiniaturized():
                mainWindow.deminiaturize_(appl)            
        return NO

    def downloaderDaemonDidTerminate_(self, notification):
        task = notification.object()
        status = task.terminationStatus()
        logging.info("Downloader daemon has been terminated (status: %d)" % status)

    def application_openFiles_(self, nsapp, filenames):
        filenames = osFilenamesToFilenameTypes(filenames)
        if app.controller.finishedStartup:
            eventloop.addIdle(lambda:singleclick.parseCommandLineArgs(filenames), "Open local file(s)")
        else:
            singleclick.setCommandLineArgs(filenames)
        nsapp.replyToOpenOrPrint_(NSApplicationDelegateReplySuccess)

    def addTorrent(self, path):
        try:
            infoHash = singleclick.getTorrentInfoHash(path)
        except:
            print "WARNING: %s doesn't seem to be a torrent file" % path
        else:
            singleclick.addTorrent(path, infoHash)
            app.controller.selection.selectTabByTemplateBase('downloadtab')
        
    def workspaceWillSleep_(self, notification):
        def pauseRunningDownloaders(self=self):
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
        url = event.paramDescriptorForKeyword_(keyDirectObject).stringValue()

        urlPattern = re.compile(r"^(.*?)://(.*)$")
        match = urlPattern.match(url)
        if match and match.group(1) == 'feed':
            url = match.group(2)
            match = urlPattern.match(url)
            if not match:
                url = 'http://%s' % url

        if url.startswith('http'):
            eventloop.addIdle(lambda:app.controller.addAndSelectFeed(url), "Open HTTP URL")
        elif url.startswith('democracy:'):
            eventloop.addIdle(lambda:singleclick.addDemocracyURL(url), "Open Democracy URL")

    def donate_(self, sender):
        donateURL = NSURL.URLWithString_(config.get(prefs.DONATE_URL))
        NSWorkspace.sharedWorkspace().openURL_(donateURL)

    def checkForUpdates_(self, sender):
        eventloop.addUrgentCall(lambda:autoupdate.checkForUpdates(True), "Checking for new version")

    def showMainWindow_(self, sender):
        if app.controller is not None and app.controller.frame is not None:
            app.controller.frame.controller.window().makeKeyAndOrderFront_(sender)

    def showPreferencesWindow_(self, sender):
        prefController = PreferencesWindowController.alloc().init()
        prefController.retain()
        prefController.showWindow_(nil)

    def openFile_(self, sender):
        openPanel = NSOpenPanel.openPanel()
        openPanel.setAllowsMultipleSelection_(YES)
        openPanel.setCanChooseDirectories_(NO)
        result = openPanel.runModalForDirectory_file_types_(NSHomeDirectory(), nil, nil)
        if result == NSOKButton:
            filenames = osFilenamesToFilenameTypes(openPanel.filenames())
            eventloop.addUrgentCall(lambda:singleclick.parseCommandLineArgs(filenames), "Open local file(s)")
                
    def shutdown_(self, sender):
        self.internalShutdown = True
        app.controller.quit()

    def validateMenuItem_(self, item):
        return item.action() in ('donate:', 'checkForUpdates:', 'showMainWindow:',
                                 'showPreferencesWindow:', 'addGuide:', 
                                 'openFile:', 'shutdown:')

###############################################################################
