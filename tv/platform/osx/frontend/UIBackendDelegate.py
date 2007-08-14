import os
import time
import string
import signal
import logging
import threading

from objc import YES, NO, nil, signature
from AppKit import *
from Foundation import *
from PyObjCTools import NibClassBuilder, Conversion, AppHelper

import app
import feed
import prefs
import config
import dialogs
import eventloop
import platformcfg
import platformutils

from StartupPanel import StartupPanelController
import GrowlNotifier
import SparkleUpdater

###############################################################################

NibClassBuilder.extractClasses(u"PasswordWindow")
NibClassBuilder.extractClasses(u"TextEntryWindow")
NibClassBuilder.extractClasses(u'SearchChannelWindow')
NibClassBuilder.extractClasses(u"ExceptionReporterPanel")

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
    alert.setMessageText_(unicode(summary))
    alert.setInformativeText_(unicode(message))
    if buttons is not None:
        for title in buttons:
            alert.addButtonWithTitle_(unicode(title))
    result = platformutils.callOnMainThreadAndWaitReturnValue(alert.runModal)
    result -= NSAlertFirstButtonReturn
    del alert
    return result

###############################################################################

class UIBackendDelegate:

    # This lock is used by the HTTPAuthDialog to serialize HTTP authentication 
    # requests and prevent multiple authentication dialogs to pop up at once.
    httpAuthLock = threading.Lock()

    def __init__(self):
        self.contextItemHandler = ContextItemHandler.alloc().init()
        self.openPanelHandler = OpenPanelHandler.alloc().init()
        self.savePanelHandler = SavePanelHandler.alloc().init()

    def performStartupTasks(self, terminationCallback):
        NSApplication.sharedApplication().delegate().checkQuicktimeVersion(True)
        startupController = StartupPanelController.alloc().init()
        startupController.run(terminationCallback)

    @platformutils.onMainThread
    def askForSavePathname(self, callback, defaultFilename=None):
        self.savePanelHandler.run(callback, defaultFilename)

    @platformutils.onMainThread
    def askForOpenPathname(self, callback, defaultDirectory=None, types=None):
        self.openPanelHandler.run(callback, defaultDirectory, types)

    @platformutils.onMainThread
    def runDialog(self, dialog):
        if isinstance(dialog, dialogs.TextEntryDialog):
            dlog = TextEntryController.alloc().initWithDialog_(dialog)
            dlog.run()
            call = lambda:dialog.runCallback(dlog.result, dlog.value)
            name = "TextEntryDialog"
        elif isinstance(dialog, dialogs.HTTPAuthDialog):
            self.httpAuthLock.acquire()
            try:
                authDlog = PasswordController.alloc().initWithDialog_(dialog)
                result = authDlog.getAnswer()
                name = "HTTPAuthDialog"
                if result is not None:
                    call = lambda:dialog.runCallback(dialogs.BUTTON_OK, *result)
                else:
                    call = lambda:dialog.runCallback(None)
            finally:
                self.httpAuthLock.release()
        elif isinstance(dialog, dialogs.SearchChannelDialog):
            dlog = SearchChannelController.alloc().initWithDialog_(dialog)
            dlog.run()
            call = lambda:dialog.runCallback(dlog.result)
            name = "SearchChannelDialog"
        else:
            buttons = map(lambda x:x.text, dialog.buttons)
            result = showWarningDialog(dialog.title, dialog.description, buttons)
            call = lambda:dialog.runCallback(dialog.buttons[result])
            name = "Dialog"
        eventloop.addUrgentCall(call, "Calling back from %s" % name)

    def openExternalURL(self, url):
        # We could use Python's webbrowser.open() here, but
        # unfortunately, it doesn't have the same semantics under UNIX
        # as under other OSes. Sometimes it blocks, sometimes it doesn't.
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))

    def revealFile(self, filename):
        filename = platformutils.filenameTypeToOSFilename(filename)
        NSWorkspace.sharedWorkspace().selectFile_inFileViewerRootedAtPath_(filename, nil)

    def updateAvailableItemsCountFeedback(self, count):
        try:
            appIcon = NSImage.imageNamed_(u'NSApplicationIcon')
            badgedIcon = NSImage.alloc().initWithSize_(appIcon.size())
            badgedIcon.lockFocus()
        except:
            pass
        else:
            try:
                appIcon.compositeToPoint_operation_((0,0), NSCompositeSourceOver)
                if count > 0:
                    digits = len(str(count))
                    badge = nil
                    if digits <= 2:
                        badge = NSImage.imageNamed_(u'dock_badge_1_2.png')
                    elif digits <= 5:
                        badge = NSImage.imageNamed_(u'dock_badge_%d.png' % digits)
                    else:
                        logging.warn("Wow, that's a whole lot of new items!")
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
    
    def notifyDownloadCompleted(self, item):
        GrowlNotifier.notifyDownloadComplete(item.getTitle())

    def notifyDownloadFailed(self, item):
        GrowlNotifier.notifyDownloadFailed(item.getTitle())
    
    @platformutils.onMainThread
    def notifyUnkownErrorOccurence(self, when, log = ''):
        if config.get(prefs.SHOW_ERROR_DIALOG):
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
            logging.info('Waiting for the downloader daemon to terminate...')
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
                logging.info("Timeout expired - Killing downloader daemon!")
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
        dlTask.setArguments_([u'download_daemon'])
        dlTask.setEnvironment_(env)
        
        controller = NSApplication.sharedApplication().delegate()
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(controller, 'downloaderDaemonDidTerminate:', NSTaskDidTerminateNotification, dlTask)

        logging.info('Launching Download Daemon')
        dlTask.launch()
        
    def makeAppRunAtStartup(self, run):
        defaults = NSUserDefaults.standardUserDefaults()
        lwdomain = defaults.persistentDomainForName_('loginwindow')
        lwdomain = Conversion.pythonCollectionFromPropertyList(lwdomain)
        if lwdomain is None:
            lwdomain = dict()
        if 'AutoLaunchedApplicationDictionary' not in lwdomain:
            lwdomain['AutoLaunchedApplicationDictionary'] = list()
        launchedApps = lwdomain['AutoLaunchedApplicationDictionary']
        ourPath = platformcfg.getBundlePath()
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
        if url is None or not feed.validateFeedURL(unicode(url)):
            url = ""
        return url
    
    @platformutils.onMainThread
    def showContextMenu(self, items):
        nsmenu = NSMenu.alloc().init()
        nsmenu.setAutoenablesItems_(NO)
        for item in items:
            if item.label == '':
                nsitem = NSMenuItem.separatorItem()
            else:
                nsitem = NSMenuItem.alloc()
                nsitem.initWithTitle_action_keyEquivalent_(item.label, 'processContextItem:', '')
                nsitem.setEnabled_(item.callback is not None)
                nsitem.setRepresentedObject_(item)
                nsitem.setTarget_(self.contextItemHandler)
            nsmenu.addItem_(nsitem)
        window = NSApplication.sharedApplication().mainWindow()
        view = window.contentView()
        event = NSEvent.mouseEventWithType_location_modifierFlags_timestamp_windowNumber_context_eventNumber_clickCount_pressure_(
                        NSRightMouseDown,
                        window.mouseLocationOutsideOfEventStream(),
                        0,
                        1,
                        window.windowNumber(),
                        NSGraphicsContext.currentContext(),
                        1,
                        1,
                        0.0)
        NSMenu.popUpContextMenu_withEvent_forView_(nsmenu, event, view)

    def handleNewUpdate(self, latest):
        SparkleUpdater.handleNewUpdate(latest)

###############################################################################

class ContextItemHandler (NSObject):
    
    @signature("v@:@")
    def processContextItem_(self, item):
        item.representedObject().activate()

###############################################################################

class OpenPanelHandler (NSObject):

    def run(self, callback, defaultDirectory, types):
        self.callback = callback
        if defaultDirectory is None:
            defaultDirectory = NSHomeDirectory()
        panel = NSOpenPanel.openPanel()
        panel.beginSheetForDirectory_file_types_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
            defaultDirectory,
            nil,
            types,
            NSApplication.sharedApplication().mainWindow(),
            self,
            'openPanelDidEnd:returnCode:contextInfo:',
            0)
    
    @AppHelper.endSheetMethod
    def openPanelDidEnd_returnCode_contextInfo_(self, panel, result, contextID):
        if result == NSOKButton:
            filenames = panel.filenames()
            self.callback(filenames[0])

###############################################################################

class SavePanelHandler (NSObject):
    
    def run(self, callback, defaultFilename):
        self.callback = callback
        panel = NSSavePanel.savePanel()
        panel.beginSheetForDirectory_file_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
            NSHomeDirectory(),
            defaultFilename,
            NSApplication.sharedApplication().mainWindow(),
            self,
            'savePanelDidEnd:returnCode:contextInfo:',
            0)
    
    @AppHelper.endSheetMethod
    def savePanelDidEnd_returnCode_contextInfo_(self, panel, result, contextID):
        if result == NSOKButton:
            self.callback(panel.filename())

###############################################################################

class ExceptionReporterController (NibClassBuilder.AutoBaseClass):
    
    def initWithMoment_log_(self, when, log):
        self = super(ExceptionReporterController, self).initWithWindowNibName_owner_(u"ExceptionReporterPanel", self)
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
        NSBundle.loadNibNamed_owner_(u"PasswordWindow", self)
        self.window.setTitle_(dialog.title)
        self.usernameField.setStringValue_(dialog.prefillUser or u"")
        self.passwordField.setStringValue_(dialog.prefillPassword or u"")
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
        username = unicode(self.usernameField.stringValue())
        password = unicode(self.passwordField.stringValue())
        self.closeWithResult((username, password))

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
        self = super(TextEntryController, self).initWithWindowNibName_owner_(u"TextEntryWindow", self)
        self.dialog = dialog
        self.window().setTitle_(unicode(dialog.title))
        self.messageField.setStringValue_(dialog.description)
        self.entryField.setStringValue_(u"")
        self.mainButton.setTitle_(unicode(dialog.buttons[0].text))
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
        entry = unicode(self.entryField.stringValue())
        self.closeWithResult(self.dialog.buttons[0], entry)

    def cancelEntry_(self, sender):
        self.closeWithResult(self.dialog.buttons[1], None)

    def closeWithResult(self, result, value):
        self.result = result
        self.value = value
        self.window().close()
        NSApplication.sharedApplication().stopModal()

###############################################################################

class SearchChannelController (NibClassBuilder.AutoBaseClass):
    
    def initWithDialog_(self, dialog):
        self = super(SearchChannelController, self).initWithWindowNibName_owner_(u'SearchChannelWindow', self)
        self.dialog = dialog
        self.result = None

        self.window().setTitle_(dialog.title)
        self.labelField.setStringValue_(dialog.description)
        self.searchTermField.setStringValue_(dialog.term or u'')
        self.targetMatrix.selectCellWithTag_(dialog.style)
        self.changeTarget_(self.targetMatrix)

        self.channelPopup.removeAllItems()
        for cid, title in dialog.channels:
            self.channelPopup.addItemWithTitle_(title)

        self.enginePopup.removeAllItems()
        for name, title in dialog.engines:
            self.enginePopup.addItemWithTitle_(title)

        if dialog.style == dialogs.SearchChannelDialog.CHANNEL:
            channel = self.getChannelTitleForID(dialog.location)
            self.channelPopup.selectItemWithTitle_(channel)
        elif dialog.style == dialogs.SearchChannelDialog.ENGINE:
            engine = self.getEngineTitleForName(dialog.location, dialog.defaultEngine)
            self.enginePopup.selectItemWithTitle_(engine)

        self.controlTextDidChange_(nil)

        return self
    
    def getChannelTitleForID(self, cid):
        for eid, etitle in self.dialog.channels:
            if eid == cid:
                return etitle
        return self.dialog.channels[0][1]
    
    def getChannelIDForTitle(self, ctitle):
        for eid, etitle in self.dialog.channels:
            if etitle == ctitle:
                return eid
        return self.dialog.channels[0][0]
    
    def getEngineTitleForName(self, name, default):
        for ename, etitle in self.dialog.engines:
            if ename == name:
                return etitle
        return default
    
    def getEngineNameForTitle(self, title):
        for ename, etitle in self.dialog.engines:
            if etitle == title:
                return ename
        return self.dialog.engines[0][0]
        
    def run(self):
        NSApplication.sharedApplication().runModalForWindow_(self.window())

    def controlTextDidChange_(self, notification):
        enable = (self.searchTermField.stringValue().strip() != '')
        if self.targetMatrix.selectedCell().tag() == dialogs.SearchChannelDialog.URL:
            enable = enable and (self.urlField.stringValue().strip() != '')
        self.createButton.setEnabled_(enable)

    def changeTarget_(self, sender):
        target = sender.selectedCell().tag()
        self.channelPopup.setEnabled_(target == dialogs.SearchChannelDialog.CHANNEL)
        self.enginePopup.setEnabled_(target == dialogs.SearchChannelDialog.ENGINE)
        self.urlField.setEnabled_(target == dialogs.SearchChannelDialog.URL)
        self.controlTextDidChange_(nil)
    
    def cancel_(self, sender):
        self.closeWithResult(self.dialog.buttons[1])

    def create_(self, sender):
        self.dialog.term = unicode(self.searchTermField.stringValue())
        self.dialog.style = self.targetMatrix.selectedCell().tag()
        if self.dialog.style == dialogs.SearchChannelDialog.CHANNEL:
            channel = self.channelPopup.titleOfSelectedItem()
            self.dialog.location = self.getChannelIDForTitle(channel)
        elif self.dialog.style == dialogs.SearchChannelDialog.ENGINE:
            engine = self.enginePopup.titleOfSelectedItem()
            self.dialog.location = self.getEngineNameForTitle(engine)
        elif self.dialog.style == dialogs.SearchChannelDialog.URL:
            self.dialog.location = unicode(self.urlField.stringValue())
        self.closeWithResult(self.dialog.buttons[0])

    def closeWithResult(self, result):
        self.result = result
        self.window().close()
        NSApplication.sharedApplication().stopModal()
