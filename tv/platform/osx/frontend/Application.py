import os
import re
import time
import struct
import gettext
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
import resource
import eventloop
import autoupdate
import singleclick

from Preferences import PreferencesWindowController

NibClassBuilder.extractClasses("MainMenu")

###############################################################################

class Application:

    def __init__(self):
        appl = NSApplication.sharedApplication()
        NSBundle.loadNibNamed_owner_("MainMenu", appl)
        controller = appl.delegate()

    def Run(self):
        languages = list(NSUserDefaults.standardUserDefaults()["AppleLanguages"])
        for i in xrange (len(languages)):
            if languages[i] == "en":
                languages[i] = "C"

        os.environ["LANGUAGE"] = ':'.join(languages)
        gettext_path = os.path.abspath(resource.path("../locale"))
        gettext.bindtextdomain("democracyplayer", gettext_path)
        gettext.textdomain("democracyplayer")
        gettext.bind_textdomain_codeset("democracyplayer", "UTF-8")

        eventloop.setDelegate(self)
        AppHelper.runEventLoop()

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
        nc.addObserver_selector_name_object_(self, 'videoWillPlay:', 'videoWillPlay',  nil)
        nc.addObserver_selector_name_object_(self, 'videoWillStop:', 'videoWillPause', nil)
        nc.addObserver_selector_name_object_(self, 'videoWillStop:', 'videoWillStop',  nil)
        
        ws = NSWorkspace.sharedWorkspace()
        wsnc = ws.notificationCenter()
        wsnc.addObserver_selector_name_object_(self, 'workspaceWillSleep:', NSWorkspaceWillSleepNotification, nil)
        wsnc.addObserver_selector_name_object_(self, 'workspaceDidWake:',   NSWorkspaceDidWakeNotification,   nil)
        
        self.pausedDownloaders = list()
        self.internalShutdown = False
        
    def applicationDidFinishLaunching_(self, notification):
        # The [NSURLRequest setAllowsAnyHTTPSCertificate:forHost:] selector is
        # not documented anywhere, so I assume it is not public. It is however 
        # a very clean and easy way to allow us to load our channel guide from
        # https, so let's use it here anyway :)
        components = urlparse.urlparse(config.get(prefs.CHANNEL_GUIDE_URL))
        channelGuideHost = components[1]
        NSURLRequest.setAllowsAnyHTTPSCertificate_forHost_(YES, channelGuideHost)

        # Startup
        app.controller.onStartup()
    
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
            result = NSTerminateCancel
        return result
    
    def applicationWillTerminate_(self, notification):
        # Reset the application icon to its default state
        defaultAppIcon = NSImage.imageNamed_('NSApplicationIcon')
        NSApplication.sharedApplication().setApplicationIconImage_(defaultAppIcon)
        # Ensure that the download daemon is not running anymore at this point
        app.delegate.waitUntilDownloadDaemonExit()
            
        # Call shutdown on backend
        app.controller.onShutdown()

    def downloaderDaemonDidTerminate_(self, notification):
        task = notification.object()
        status = task.terminationStatus()
        print "DTV: Downloader daemon has been terminated (status: %d)" % status

    def application_openFiles_(self, app, filenames):
        eventloop.addUrgentCall(lambda:self.openFiles(filenames), "Open local file(s)")
        app.replyToOpenOrPrint_(NSApplicationDelegateReplySuccess)

    def addTorrent(self, path):
        try:
            infoHash = singleclick.getTorrentInfoHash(path)
        except:
            print "WARNING: %s doesn't seem to be a torrent file" % path
        else:
            singleclick.addTorrent(path, infoHash)
            app.controller.selection.selectTabByTemplateBase('downloadtab')
        
    def addVideo(self, path):
        singleclick.addVideo(path)
        app.controller.selection.selectTabByTemplateBase('librarytab')

    def workspaceWillSleep_(self, notification):
        def pauseRunningDownloaders(self=self):
            views.remoteDownloads.confirmDBThread()
            self.pausedDownloaders = list()
            for dl in views.remoteDownloads:
                if dl.getState() == 'downloading':
                    self.pausedDownloaders.append(dl)
            dlCount = len(self.pausedDownloaders)
            if dlCount > 0:
                print "DTV: System is going to sleep, suspending %d download(s)." % dlCount
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
                print "DTV: System is awake from sleep, resuming %s download(s)." % dlCount
                try:
                    for dl in self.pausedDownloaders:
                        dl.start()
                finally:
                    self.pausedDownloaders = list()
        eventloop.addUrgentCall(lambda:restartPausedDownloaders(), "Resuming downloaders after sleep")

    def videoWillPlay_(self, notification):
        self.playPauseMenuItem.setTitle_('Pause Video')

    def videoWillStop_(self, notification):
        self.playPauseMenuItem.setTitle_('Play Video')

    def checkQuicktimeVersion(self, showError):
        supported = gestalt('qtim') >= 0x07000000
        
        if not supported and showError:
            summary = u'Unsupported version of Quicktime'
            message = u'To run %s you need the most recent version of Quicktime, which is a free update.' % (config.get(prefs.LONG_APP_NAME), )
            def callback(dialog):
                if dialog.choice == dialogs.BUTTON_DOWNLOAD:
                    url = NSURL.URLWithString_('http://www.apple.com/quicktime/download')
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
            app.controller.addAndSelectFeed(url)
        elif url.startswith('democracy:'):
            eventloop.addUrgentCall(lambda:singleclick.addDemocracyURL(url), 
                        "Open Democracy URL")

    def checkForUpdates_(self, sender):
        eventloop.addUrgentCall(lambda:autoupdate.checkForUpdates(True), "Checking for new version")

    def showPreferencesWindow_(self, sender):
        prefController = PreferencesWindowController.alloc().init()
        prefController.retain()
        prefController.showWindow_(nil)

    def addGuide_(self, sender):
        eventloop.addIdle(lambda:app.controller.addAndSelectGuide(), "Add Guide")

    def removeGuide_(self, sender):
        eventloop.addIdle(app.controller.removeCurrentGuide, "Remove Guide")

    def openFile_(self, sender):
        openPanel = NSOpenPanel.openPanel()
        openPanel.setAllowsMultipleSelection_(YES)
        openPanel.setCanChooseDirectories_(NO)
        result = openPanel.runModalForDirectory_file_types_(NSHomeDirectory(), nil, nil)
        if result == NSOKButton:
            filenames = openPanel.filenames()
            eventloop.addUrgentCall(lambda:self.openFiles(filenames), "Open local file(s)")
                
    def openFiles(self, filenames):
        singleclick.resetCommandLineView()
        for filename in filenames:
            root, ext = os.path.splitext(filename.lower())
            if ext == ".democracy":
                singleclick.addSubscriptions(filename)
            elif ext == ".torrent":
                self.addTorrent(filename)
            elif ext in (".rss", ".rdf", ".atom"):
                singleclick.addFeed(filename)
            else:
                self.addVideo(filename)
        singleclick.playCommandLineView()

    def donate_(self, sender):
        print "NOT IMPLEMENTED"

    def shutdown_(self, sender):
        self.internalShutdown = True
        app.controller.quit()

    itemsAlwaysAvailable = ('checkForUpdates:', 'showPreferencesWindow:', 'addGuide:', 'openFile:', 'shutdown:')
    def validateMenuItem_(self, item):
        mainFrame = app.controller.frame
        if item.action() == 'removeGuide:':
            return mainFrame.selectedTabType == 'addedguidetab'
        else:
            return item.action() in self.itemsAlwaysAvailable

###############################################################################
