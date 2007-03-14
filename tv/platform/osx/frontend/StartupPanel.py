import os

from objc import YES, NO, nil, signature
from PyObjCTools import NibClassBuilder

from AppKit import *
from Foundation import *

import app
import util
import prefs
import config
import eventloop
import platformutils

from gtcache import gettext as _

NibClassBuilder.extractClasses(u"StartupPanel")

###############################################################################

class StartupPanelController (NibClassBuilder.AutoBaseClass):
    
    def init(self):
        self = super(StartupPanelController, self).initWithWindowNibName_(u"StartupPanel")
        self.gathered = None
        self.panels = {
            'run-at-startup':
            {
                'prepare':  self.prepareRunAtStartupPanel,
                'perform':  self.performRunAtStartupTask
            },
            'find-videos':
            {
                'prepare':  self.prepareFindVideosPanel,
                'perform':  self.performFindVideoTask
            },
            'done':
            {
                'prepare':  self.prepareLastPanel,
                'perform':  self.terminate
            }
        }
        return self
    
    def awakeFromNib(self):
        self.findProgressLabelFormat = self.findProgressLabel.stringValue()
        self.doneMessage.setBackgroundColor_(darkRuledLinesColor())
        self.tabView.selectFirstTabViewItem_(nil)
        self.preparePanel()
        
    def run(self, callback):
        self.terminationCallback = callback
        NSApplication.sharedApplication().runModalForWindow_(self.window())

    def goBack_(self, sender):
        self.tabView.selectPreviousTabViewItem_(nil)
        self.preparePanel()

    def goNext_(self, sender):
        switch = self.performPanelTask()
        if switch:
            self.doGoNext()

    def doGoNext(self):
        self.tabView.selectNextTabViewItem_(nil)
        self.preparePanel()

    def preparePanel(self):
        currentPanelID = self.tabView.selectedTabViewItem().identifier()
        prepare = self.panels[currentPanelID]['prepare']
        prepare()

    def performPanelTask(self):
        currentPanelID = self.tabView.selectedTabViewItem().identifier()
        perform = self.panels[currentPanelID]['perform']
        return perform()
                
    def terminate(self):
        self.progressIndicator.startAnimation_(nil)
        NSApplication.sharedApplication().stopModal()
        self.terminationCallback(self.gathered)
        self.window().close()

    # -------------------------------------------------------------------------

    def prepareRunAtStartupPanel(self):
        self.backButton.setEnabled_(NO)
        self.validateButton.setEnabled_(YES)
        self.validateButton.setTitle_(_(u'Next'))
        tag = int(config.get(prefs.RUN_DTV_AT_STARTUP))
        self.runAtStartupMatrix.selectCellWithTag_(tag)

    def performRunAtStartupTask(self):
        run = (self.runAtStartupMatrix.selectedCell().tag() == 1)
        app.delegate.makeDemocracyRunAtStartup(run)
        config.set(prefs.RUN_DTV_AT_STARTUP, run)
        return True

    # -------------------------------------------------------------------------

    def prepareFindVideosPanel(self):
        self.gathered = None
        self.backButton.setEnabled_(YES)
        self.validateButton.setEnabled_(YES)
        self.findVideosMatrix.setEnabled_(YES)
        self.setFind_(self.findVideosMatrix)
        self.setFindRestriction_(self.findRestrictionsMatrix)
        
    def setFind_(self, sender):
        find = (sender.selectedCell().tag() == 1)
        self.findRestrictionsMatrix.setEnabled_(find)
        if find:
            self.validateButton.setTitle_(_(u'Search!'))
        else:
            self.validateButton.setTitle_(_(u'Next'))

    def setFindRestriction_(self, sender):
        tag = sender.selectedCell().tag()
        self.browseButton.setEnabled_(tag == 2)
        self.customLocationField.setEnabled_(tag == 2)

    def browse_(self, sender):
        panel = NSOpenPanel.openPanel()
        panel.setAllowsMultipleSelection_(NO)
        panel.setCanChooseFiles_(NO)
        panel.setCanChooseDirectories_(YES)
        panel.beginSheetForDirectory_file_types_modalForWindow_modalDelegate_didEndSelector_contextInfo_(
            nil, nil, nil, self.window(), self, 'openPanelDidEnd:returnCode:contextInfo:', 0)

    @signature("v@:@ii")
    def openPanelDidEnd_returnCode_contextInfo_(self, panel, code, info):
        if code == NSOKButton:
            filenames = panel.filenames()
            self.customLocationField.setStringValue_(filenames[0])

    def performFindVideoTask(self):
        find = (self.findVideosMatrix.selectedCell().tag() == 1)
        if find:
            if self.findRestrictionsMatrix.selectedCell().tag() == 2 and not os.path.exists(self.customLocationField.stringValue()):
                NSBeep()
            else:
                self.backButton.setEnabled_(NO)
                self.validateButton.setEnabled_(NO)
                self.findVideosMatrix.setEnabled_(NO)
                self.findRestrictionsMatrix.setEnabled_(NO)
                self.browseButton.setEnabled_(NO)
                self.customLocationField.setEnabled_(NO)
                self.findProgressView.setHidden_(NO)
                self.findProgressIndicator.startAnimation_(nil)
                self.findProgressLabel.setStringValue_("")
                NSThread.detachNewThreadSelector_toTarget_withObject_('performFind', self, nil)
        return not find
    
    def performFind(self):
        pool = NSAutoreleasePool.alloc().init()
        try:
            restrictionTag = self.findRestrictionsMatrix.selectedCell().tag()
            if restrictionTag == 0:
                path = os.path.expanduser('~/Movies')
            elif restrictionTag == 1:
                path = os.path.expanduser('~/')
            else:
                path = unicode(self.customLocationField.stringValue())
            self.keepFinding = True
            self.gathered = util.gatherVideos(path, self.onProgressFindingVideos)
            self.finishFindVideoTask(True)
        finally:
            del pool
    
    def onProgressFindingVideos(self, parsed, found):
        progress = self.findProgressLabelFormat % (parsed, found)
        platformutils.callOnMainThread(self.findProgressLabel.setStringValue_, progress)
        return self.keepFinding
            
    def cancelFind_(self, sender):
        self.keepFinding = False
    
    def finishFindVideoTask(self, goNext=False):
        self.findProgressIndicator.stopAnimation_(nil)
        self.findProgressView.setHidden_(YES)
        if goNext:
            self.doGoNext()
        else:
            self.prepareFindVideosPanel()

    # -------------------------------------------------------------------------

    def prepareLastPanel(self):
        self.backButton.setEnabled_(YES)
        self.validateButton.setEnabled_(YES)
        self.validateButton.setTitle_(u'Finish')

###############################################################################

def darkRuledLinesColor():
    # NSColor does not have a call to get the color of the darkened ruled lines 
    # pattern like the one of NSBox and NSTabView, so we have to build it manually.
    pattern = NSImage.alloc().initWithSize_((1.0, 4.0))
    pattern.lockFocus()
    NSColor.colorWithCalibratedWhite_alpha_(228.0/255.0, 1.0).set()
    NSBezierPath.fillRect_(((0.0, 0.0), (1.0, 2.0)))
    NSColor.colorWithCalibratedWhite_alpha_(232.0/255.0, 1.0).set()
    NSBezierPath.fillRect_(((0.0, 2.0), (1.0, 2.0)))
    pattern.unlockFocus()
    return NSColor.colorWithPatternImage_(pattern)

###############################################################################
