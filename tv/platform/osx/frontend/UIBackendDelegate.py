import os
import time
import string
import signal
import threading

from objc import YES, NO, nil
from AppKit import *
from Foundation import *
from PyObjCTools import NibClassBuilder, Conversion

import app
import feed
import prefs
import config
import dialogs
import platformutils

from StartupPanel import StartupPanelController

###############################################################################

NibClassBuilder.extractClasses("PasswordWindow")
NibClassBuilder.extractClasses("TextEntryWindow")
NibClassBuilder.extractClasses("ExceptionReporterPanel")

dlTask = None

###############################################################################
#### Helper methods used to display alert dialog of various types          ####
###############################################################################

def showInformationalDialog(summary, message, buttons=None):
    return showDialog(summary, message, buttons, NSInformationalAlertStyle)

def showWarningDialog(summary, message, buttons=None):
    return showDialog(summary, message, buttons, NSWarningAlertStyle)

def showCriticalDialog(summary, message, buttons=None):
    return showDialog(summary, message, buttons, NSCriticalAlertStyle)

@platformutils.onMainThreadWithReturn
def showDialog(summary, message, buttons, style):
    alert = NSAlert.alloc().init()
    alert.setAlertStyle_(style)
    alert.setMessageText_(summary)
    alert.setInformativeText_(message)
    if buttons is not None:
        for title in buttons:
            alert.addButtonWithTitle_(title)
    result = platformutils.callOnMainThreadAndWaitReturnValue(alert.runModal)
    result -= NSAlertFirstButtonReturn
    del alert
    return result

###############################################################################

class UIBackendDelegate:

    # This lock is used by the HTTPAuthDialog to serialize HTTP authentication 
    # requests and prevent multiple authentication dialogs to pop up at once.
    httpAuthLock = threading.Lock()

    def performStartupTasks(self, terminationCallback):
        NSApplication.sharedApplication().delegate().checkQuicktimeVersion(True)
        startupController = StartupPanelController.alloc().init()
        startupController.run(terminationCallback)

    def runDialog(self, dialog):
        if isinstance(dialog, dialogs.TextEntryDialog):
            dlog = TextEntryController.alloc().initWithDialog_(dialog)
            dlog.run()
            dialog.runCallback(dlog.result, dlog.value)
        elif isinstance(dialog, dialogs.HTTPAuthDialog):
            self.httpAuthLock.acquire()
            try:
                authDlog = PasswordController.alloc().initWithDialog_(dialog)
                result = authDlog.getAnswer()
                if result is not None:
                    dialog.runCallback(dialogs.BUTTON_OK, *result)
                else:
                    dialog.runCallback(None)
            finally:
                self.httpAuthLock.release()
        else:
            buttons = map(lambda x:x.text, dialog.buttons)
            result = showWarningDialog(dialog.title, dialog.description, buttons)
            dialog.runCallback(dialog.buttons[result])

    def openExternalURL(self, url):
        # We could use Python's webbrowser.open() here, but
        # unfortunately, it doesn't have the same semantics under UNIX
        # as under other OSes. Sometimes it blocks, sometimes it doesn't.
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))

    def revealFile(self, filename):
        NSWorkspace.sharedWorkspace().selectFile_inFileViewerRootedAtPath_(filename, nil)

    def updateAvailableItemsCountFeedback(self, count):
        appIcon = NSImage.imageNamed_('NSApplicationIcon')
        badgedIcon = NSImage.alloc().initWithSize_(appIcon.size())
        badgedIcon.lockFocus()
        try:
            appIcon.compositeToPoint_operation_((0,0), NSCompositeSourceOver)
            if count > 0:
                digits = len(str(count))
                badge = nil
                if digits <= 2:
                    badge = NSImage.imageNamed_('dock_badge_1_2.png')
                elif digits <= 5:
                    badge = NSImage.imageNamed_('dock_badge_%d.png' % digits)
                else:
                    print "DTV: Wow, that's a whole lot of new items!"
                if badge is not nil:
                    appIconSize = appIcon.size()
                    badgeSize = badge.size()
                    badgeLoc = (appIconSize.width - badgeSize.width, appIconSize.height - badgeSize.height)
                    badge.compositeToPoint_operation_(badgeLoc, NSCompositeSourceOver)
                    badgeLabel = NSString.stringWithString_(u'%d' % count)
                    badgeLabelFont = NSFont.boldSystemFontOfSize_(24)
                    badgeLabelColor = NSColor.whiteColor()
                    badgeParagraphStyle = NSMutableParagraphStyle.alloc().init()
                    badgeParagraphStyle.setAlignment_(NSCenterTextAlignment)
                    badgeLabelAttributes = {NSFontAttributeName: badgeLabelFont, 
                                            NSForegroundColorAttributeName: badgeLabelColor,
                                            NSParagraphStyleAttributeName: badgeParagraphStyle}
                    badgeLabelLoc = (badgeLoc[0], badgeLoc[1]-10)
                    badgeLabel.drawInRect_withAttributes_((badgeLabelLoc, badgeSize), badgeLabelAttributes)
        finally:
            badgedIcon.unlockFocus()
        appl = NSApplication.sharedApplication()
        platformutils.callOnMainThreadAndWaitUntilDone(appl.setApplicationIconImage_, badgedIcon)
        
    @platformutils.onMainThread
    def notifyUnkownErrorOccurence(self, when, log = ''):
        controller = ExceptionReporterController.alloc().initWithMoment_log_(when, log)
        controller.showPanel()
        return True

    def copyTextToClipboard(self, text):
        pb = NSPasteboard.generalPasteboard()
        pb.declareTypes_owner_([NSStringPboardType], self)
        pb.setString_forType_(text, NSStringPboardType)

    def ensureDownloadDaemonIsTerminated(self):
        # Calling dlTask.waitUntilExit() here could cause problems since we 
        # cannot specify a timeout, so if the daemon fails to shutdown we could
        # wait here indefinitely. We therefore manually poll for a specific 
        # amount of time beyond which we force quit the daemon.
        global dlTask
        if dlTask is not None and dlTask.isRunning():
            print "DTV: Waiting for the downloader daemon to terminate..."
            timeout = 5.0
            sleepTime = 0.2
            loopCount = int(timeout / sleepTime)
            for i in range(loopCount):
                if dlTask.isRunning():
                    time.sleep(sleepTime)
                else:
                    break
            else:
                # If the daemon is still alive at this point, it's likely to be
                # in a bad state, so nuke it.
                print "DTV: Timeout expired - Killing downloader daemon!"
                dlTask.terminate()
        dlTask.waitUntilExit()
        dlTask = None

    def waitUntilDownloadDaemonExit(self):
        global dlTask
        if dlTask is not None:
            dlTask.waitUntilExit()
            dlTask = None      

    def killDownloadDaemon(self, oldpid=None):
        if oldpid is not None:
            try:
                os.kill(oldpid, signal.SIGTERM)
                sleep(1)
                os.kill(oldpid, signal.SIGKILL)
            except:
                pass

    def launchDownloadDaemon(self, oldpid, env):
        self.killDownloadDaemon(oldpid)

        env['DEMOCRACY_DOWNLOADER_LOG'] = config.get(prefs.DOWNLOADER_LOG_PATHNAME)
        env.update(os.environ)
                
        bundle = NSBundle.mainBundle()
        bundleExe = bundle.executablePath()
        exe = "%s/Downloader" % os.path.dirname(bundleExe)
        
        global dlTask
        dlTask = NSTask.alloc().init()
        dlTask.setLaunchPath_(exe)
        dlTask.setArguments_(['download_daemon'])
        dlTask.setEnvironment_(env)
        
        controller = NSApplication.sharedApplication().delegate()
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(controller, 'downloaderDaemonDidTerminate:', NSTaskDidTerminateNotification, dlTask)

        print "DTV: Launching Download Daemon"
        dlTask.launch()
        
    def makeDemocracyRunAtStartup(self, run):
        defaults = NSUserDefaults.standardUserDefaults()
        lwdomain = defaults.persistentDomainForName_('loginwindow')
        lwdomain = Conversion.pythonCollectionFromPropertyList(lwdomain)
        if 'AutoLaunchedApplicationDictionary' not in lwdomain:
            lwdomain['AutoLaunchedApplicationDictionary'] = list()
        launchedApps = lwdomain['AutoLaunchedApplicationDictionary']
        ourPath = NSBundle.mainBundle().bundlePath()
        ourEntry = None
        for entry in launchedApps:
            if entry.get('Path') == ourPath:
                ourEntry = entry
                break

        if run and ourEntry is None:
            launchInfo = dict(Path=ourPath, Hide=NO)
            launchedApps.append(launchInfo)
        elif ourEntry is not None:
            launchedApps.remove(entry)

        lwdomain = Conversion.propertyListFromPythonCollection(lwdomain)
        defaults.setPersistentDomain_forName_(lwdomain, 'loginwindow')
        defaults.synchronize()
        
    def getURLFromClipboard(self):
        url = NSPasteboard.generalPasteboard().stringForType_(NSStringPboardType)
        if url is None or not feed.validateFeedURL(url):
            url = ""
        return url

###############################################################################

class ExceptionReporterController (NibClassBuilder.AutoBaseClass):
    
    def initWithMoment_log_(self, when, log):
        self = super(ExceptionReporterController, self).initWithWindowNibName_owner_("ExceptionReporterPanel", self)
        self.info = config.getAppConfig()
        self.info['when'] = when
        self.info['log'] = log
        return self
        
    def awakeFromNib(self):
        title = string.Template(self.window().title()).safe_substitute(self.info)
        msg1 = string.Template(self.msg1Field.stringValue()).safe_substitute(self.info)
        msg3 = string.Template(self.msg3View.string()).safe_substitute(self.info)
        nsmsg3 = NSString.stringWithString_(unicode(msg3))
        msg3Data = nsmsg3.dataUsingEncoding_(NSUTF8StringEncoding)
        (msg3, attrs) = NSAttributedString.alloc().initWithHTML_documentAttributes_(msg3Data)
        logmsg = string.Template(self.logView.string()).safe_substitute(self.info)

        self.window().setTitle_(title)
        self.msg1Field.setStringValue_(msg1)
        self.msg3View.setBackgroundColor_(NSColor.controlColor())
        self.msg3View.textContainer().setLineFragmentPadding_(0)
        self.msg3View.textStorage().setAttributedString_(msg3)
        self.logView.setString_(logmsg)
    
    def showPanel(self):
        platformutils.warnIfNotOnMainThread('ExceptionReporterController.showPanel')
        NSApplication.sharedApplication().runModalForWindow_(self.window())
    
    def dismissPanel_(self, sender):
        self.window().close()
        NSApplication.sharedApplication().stopModal()

###############################################################################

class PasswordController (NibClassBuilder.AutoBaseClass):

    def initWithDialog_(self, dialog):
        NSBundle.loadNibNamed_owner_("PasswordWindow", self)
        self.window.setTitle_(dialog.title)
        self.usernameField.setStringValue_(dialog.prefillUser or "")
        self.passwordField.setStringValue_(dialog.prefillPassword or "")
        self.textArea.setStringValue_(dialog.description)
        self.result = None
        return self

    def getAnswer(self):
        """Present the dialog and wait for user answer. Returns (username,
        password) if the user pressed OK, or None if the user pressed Cancel."""
        NSApplication.sharedApplication().runModalForWindow_(self.window)
        return self.result

    # bound to button in nib
    def acceptEntry_(self, sender):
        result = (self.usernameField.stringValue(), self.passwordField.stringValue())
        self.closeWithResult(result)

    # bound to button in nib
    def cancelEntry_(self, sender):
        self.closeWithResult(None)
        
    def closeWithResult(self, result):
        self.result = result
        self.window.close()
        NSApplication.sharedApplication().stopModal()

###############################################################################

class TextEntryController (NibClassBuilder.AutoBaseClass):
    
    def initWithDialog_(self, dialog):
        self = super(TextEntryController, self).initWithWindowNibName_owner_("TextEntryWindow", self)
        self.dialog = dialog
        self.window().setTitle_(dialog.title)
        self.messageField.setStringValue_(dialog.description)
        self.entryField.setStringValue_("")
        self.mainButton.setTitle_(dialog.buttons[0].text)
        self.secondaryButton.setTitle_(dialog.buttons[1].text)
        self.result = None
        self.value = None
        return self

    def run(self):
        if self.dialog.fillWithClipboardURL:
            self.entryField.setStringValue_(app.delegate.getURLFromClipboard())
        elif self.dialog.prefillCallback is not None:
            self.entryField.setStringValue_(self.dialog.prefillCallback() or "")
        NSApplication.sharedApplication().runModalForWindow_(self.window())

    def acceptEntry_(self, sender):
        self.closeWithResult(self.dialog.buttons[0], self.entryField.stringValue())

    def cancelEntry_(self, sender):
        self.closeWithResult(self.dialog.buttons[1], None)

    def closeWithResult(self, result, value):
        self.result = result
        self.value = value
        self.window().close()
        NSApplication.sharedApplication().stopModal()

###############################################################################
