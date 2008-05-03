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
import time
import string
import signal
import logging
import threading

from objc import YES, NO, nil, signature, IBOutlet
from AppKit import *
from Foundation import *
from PyObjCTools import Conversion, AppHelper

from miro import app
from miro import feed
from miro import prefs
from miro import config
from miro import dialogs
from miro import eventloop
from miro.plat import bundle
from miro.plat.utils import filenameTypeToOSFilename
from miro.plat.frontends.html import threads

from miro.plat.frontends.html.StartupPanel import StartupPanelController
from miro.plat.frontends.html import GrowlNotifier
from miro.plat.frontends.html import SparkleUpdater

###############################################################################

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

@threads.onMainThreadWithReturn
def showDialog(summary, message, buttons, style):
    alert = NSAlert.alloc().init()
    alert.setAlertStyle_(style)
    alert.setMessageText_(unicode(summary))
    alert.setInformativeText_(unicode(message))
    if buttons is not None:
        for title in buttons:
            alert.addButtonWithTitle_(unicode(title))
    result = threads.callOnMainThreadAndWaitReturnValue(alert.runModal)
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
        self.maximizeMainFrameWhenAvailable = False

    def maximizeWindow(self):
        window = NSApplication.sharedApplication().mainWindow()
        if window is not None:
            self.doMaximizeWindow(window)
        else:
            self.maximizeMainFrameWhenAvailable = True

    def doMaximizeWindow(self, window):
        screen = window.screen()
        fullFrame = screen.visibleFrame()
        window.setFrame_display_(fullFrame, YES)
        self.maximizeMainFrameWhenAvailable = False

    def performStartupTasks(self, terminationCallback):
        NSApplication.sharedApplication().delegate().checkQuicktimeVersion(True)
        startupController = StartupPanelController.alloc().init()
        startupController.run(terminationCallback)

    @threads.onMainThread
    def askForSavePathname(self, title, callback, defaultDirectory=None, defaultFilename=None):
        self.savePanelHandler.run(callback, defaultFilename)

    @threads.onMainThread
    def askForOpenPathname(self, title, callback, defaultDirectory=None,
            typeString=None, types=None):
        self.openPanelHandler.run(callback, defaultDirectory, types)

    @threads.onMainThread
    def runDialog(self, dialog):
        if isinstance(dialog, dialogs.TextEntryDialog):
            dlog = TextEntryController.alloc().initWithDialog_(dialog)
            dlog.run()
            call = lambda:dialog.runCallback(dlog.result, dlog.value)
            name = "TextEntryDialog"
        elif isinstance(dialog, dialogs.CheckboxTextboxDialog):
            dlog = CheckboxTextboxDialogController.alloc().initWithDialog_(dialog)
            dlog.run()
            call = lambda:dialog.runCallback(dlog.result, dlog.value, dlog.text)
            name = "CheckboxTextboxDialog"
        elif isinstance(dialog, dialogs.CheckboxDialog):
            dlog = CheckboxDialogController.alloc().initWithDialog_(dialog)
            dlog.run()
            call = lambda:dialog.runCallback(dlog.result, dlog.value)
            name = "CheckboxDialog"
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
        filename = filenameTypeToOSFilename(filename)
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
            threads.callOnMainThreadAndWaitUntilDone(appl.setApplicationIconImage_, badgedIcon)
    
    def notifyDownloadCompleted(self, item):
        GrowlNotifier.notifyDownloadComplete(item.getTitle())

    def notifyDownloadFailed(self, item):
        GrowlNotifier.notifyDownloadFailed(item.getTitle())
    
    @threads.onMainThread
    def notifyUnkownErrorOccurence(self, when, log = ''):
        if config.get(prefs.SHOW_ERROR_DIALOG):
            controller = ExceptionReporterController.alloc().initWithMoment_log_(when, log)
            controller.showPanel()
        return True

    def copyTextToClipboard(self, text):
        pb = NSPasteboard.generalPasteboard()
        pb.declareTypes_owner_([NSStringPboardType], self)
        pb.setString_forType_(text, NSStringPboardType)

    def makeAppRunAtStartup(self, run):
        defaults = NSUserDefaults.standardUserDefaults()
        lwdomain = defaults.persistentDomainForName_('loginwindow')
        lwdomain = Conversion.pythonCollectionFromPropertyList(lwdomain)
        if lwdomain is None:
            lwdomain = dict()
        if 'AutoLaunchedApplicationDictionary' not in lwdomain:
            lwdomain['AutoLaunchedApplicationDictionary'] = list()
        launchedApps = lwdomain['AutoLaunchedApplicationDictionary']
        ourPath = bundle.getBundlePath()
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
    
    @threads.onMainThread
    def showContextMenu(self, items):
        nsmenu = NSMenu.alloc().init()
        nsmenu.setAutoenablesItems_(NO)
        for item in items:
            if item.label == '':
                nsitem = NSMenuItem.separatorItem()
            else:
                nsitem = NSMenuItem.alloc()
                nsitem.initWithTitle_action_keyEquivalent_(item.label.decode('utf8'), 'processContextItem:', '')
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

class ExceptionReporterController (NSWindowController):
    
    logView     = IBOutlet('logView')
    msg1Field   = IBOutlet('msg1Field')
    msg3View    = IBOutlet('msg3View')
    
    def initWithMoment_log_(self, when, log):
        self = super(ExceptionReporterController, self).initWithWindowNibName_owner_(u"ExceptionReporterPanel", self)
        self.info = app.configfile.copy()
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
        threads.warnIfNotOnMainThread('ExceptionReporterController.showPanel')
        NSApplication.sharedApplication().runModalForWindow_(self.window())
    
    def dismissPanel_(self, sender):
        self.window().close()
        NSApplication.sharedApplication().stopModal()

###############################################################################

class PasswordController (NSObject):

    passwordField   = IBOutlet('passwordField')
    textArea        = IBOutlet('textArea')
    usernameField   = IBOutlet('usernameField')
    window          = IBOutlet('window')

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

class TextEntryController (NSWindowController):
    
    entryField      = IBOutlet('entryField')
    messageField    = IBOutlet('messageField')
    mainButton      = IBOutlet('mainButton')
    secondaryButton = IBOutlet('secondaryButton')
    
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

class CheckboxDialogController (NSWindowController):
    
    checkbox        = IBOutlet('checkbox')
    mainButton      = IBOutlet('mainButton')
    messageField    = IBOutlet('messageField')
    secondaryButton = IBOutlet('secondaryButton')
    
    def initWithDialog_(self, dialog):
        self = super(CheckboxDialogController, self).initWithWindowNibName_owner_(u"CheckboxDialogWindow", self)
        self.dialog = dialog
        self.window().setTitle_(unicode(dialog.title))
        self.messageField.setStringValue_(dialog.description)
        self.checkbox.setTitle_(unicode(dialog.checkbox_text))
        if dialog.checkbox_value:
            self.checkbox.setState_(NSOnState)
        else:
            self.checkbox.setState_(NSOffState)
        self.mainButton.setTitle_(unicode(dialog.buttons[0].text))
        self.secondaryButton.setTitle_(dialog.buttons[1].text)
        self.result = None
        self.value = None
        return self

    def run(self):
        NSApplication.sharedApplication().runModalForWindow_(self.window())

    def acceptEntry_(self, sender):
        value = (self.checkbox.state() == NSOnState)
        self.closeWithResult(self.dialog.buttons[0], value)

    def cancelEntry_(self, sender):
        value = (self.checkbox.state() == NSOnState)
        self.closeWithResult(self.dialog.buttons[1], value)

    def closeWithResult(self, result, value):
        self.result = result
        self.value = value
        self.window().close()
        NSApplication.sharedApplication().stopModal()

###############################################################################

class CheckboxTextboxDialogController (NSWindowController):

    checkbox        = IBOutlet('checkbox')
    checkboxLabel   = IBOutlet('checkboxLabel')
    entryField      = IBOutlet('entryField')
    mainButton      = IBOutlet('mainButton')
    messageField    = IBOutlet('messageField')
    secondaryButton = IBOutlet('secondaryButton')
    
    def initWithDialog_(self, dialog):
        self = super(CheckboxTextboxDialogController, self).initWithWindowNibName_owner_(u"CheckboxTextboxDialogWindow", self)
        self.dialog = dialog
        self.window().setTitle_(unicode(dialog.title))
        self.messageField.setStringValue_(dialog.description)
        self.entryField.setStringValue_(unicode(dialog.textbox_value))
        self.checkboxLabel.setStringValue_(unicode(dialog.checkbox_text))
        if dialog.checkbox_value:
            self.checkbox.setState_(NSOnState)
        else:
            self.checkbox.setState_(NSOffState)
        self.mainButton.setTitle_(unicode(dialog.buttons[0].text))
        self.secondaryButton.setTitle_(dialog.buttons[1].text)
        self.result = None
        self.value = None
        return self

    def run(self):
        NSApplication.sharedApplication().runModalForWindow_(self.window())

    def acceptEntry_(self, sender):
        value = (self.checkbox.state() == NSOnState)
        text = self.entryField.stringValue()
        self.closeWithResult(self.dialog.buttons[0], value, text)

    def cancelEntry_(self, sender):
        value = (self.checkbox.state() == NSOnState)
        text = self.entryField.stringValue()
        self.closeWithResult(self.dialog.buttons[1], value, text)

    def closeWithResult(self, result, value, text):
        self.result = result
        self.value = value
        self.text = text
        self.window().close()
        NSApplication.sharedApplication().stopModal()

###############################################################################

class SearchChannelController (NSWindowController):
    
    channelPopup    = IBOutlet('channelPopup')
    createButton    = IBOutlet('createButton')
    enginePopup     = IBOutlet('enginePopup')
    labelField      = IBOutlet('labelField')
    searchTermField = IBOutlet('searchTermField')
    targetMatrix    = IBOutlet('targetMatrix')
    urlField        = IBOutlet('urlField')
    
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
