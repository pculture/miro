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

from objc import YES, NO, nil, signature, IBOutlet

from AppKit import *
from Foundation import *

from miro import app
from miro import util
from miro import prefs
from miro import config
from miro import eventloop
from miro.plat.utils import osFilenameToFilenameType
from miro.plat.frontends.html import threads

from miro.gtcache import gettext as _

###############################################################################

class StartupPanelController (NSWindowController):
    
    backButton      = IBOutlet('backButton')
    validateButton  = IBOutlet('validateButton')
    tabView         = IBOutlet('tabView')
    
    def init(self):
        self = super(StartupPanelController, self).initWithWindowNibName_(u"StartupPanel")
        self.shouldFinish = False
        self.parsed = 0
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
            }
        }
        return self
    
    def awakeFromNib(self):
        self.findProgressLabelFormat = self.findProgressLabel.stringValue()
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

    def setShouldFinish(self, shouldFinish):
        self.shouldFinish = shouldFinish
        self.validateButton.setTitle_(_(u'Finish'))

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
        NSApplication.sharedApplication().stopModal()
        self.terminationCallback(self.gathered)
        self.window().close()

    # -------------------------------------------------------------------------

    runAtStartupMatrix = IBOutlet('runAtStartupMatrix')

    def prepareRunAtStartupPanel(self):
        self.backButton.setEnabled_(NO)
        self.validateButton.setEnabled_(YES)
        self.validateButton.setTitle_(_(u'Next'))
        tag = int(config.get(prefs.RUN_DTV_AT_STARTUP))
        self.runAtStartupMatrix.selectCellWithTag_(tag)

    def performRunAtStartupTask(self):
        run = (self.runAtStartupMatrix.selectedCell().tag() == 1)
        app.delegate.makeAppRunAtStartup(run)
        config.set(prefs.RUN_DTV_AT_STARTUP, run)
        return True

    # -------------------------------------------------------------------------

    findVideosMatrix        = IBOutlet('findVideosMatrix')
    findRestrictionsMatrix  = IBOutlet('findRestrictionsMatrix')
    findLabel               = IBOutlet('findLabel')
    findProgressLabel       = IBOutlet('findProgressLabel')
    findProgressIndicator   = IBOutlet('findProgressIndicator')
    findCancelButton        = IBOutlet('findCancelButton')
    browseButton            = IBOutlet('browseButton')
    customLocationField     = IBOutlet('customLocationField')

    def prepareFindVideosPanel(self):
        self.parsed = 0
        self.gathered = None
        self.initFindVideosPanelState()
        
    def initFindVideosPanelState(self):
        self.backButton.setEnabled_(YES)
        self.validateButton.setEnabled_(YES)
        self.findVideosMatrix.setEnabled_(YES)
        self.findLabel.setHidden_(YES)
        self.findProgressIndicator.setHidden_(YES)
        self.findProgressLabel.setHidden_(YES)
        self.findCancelButton.setHidden_(YES)
        self.setFind_(self.findVideosMatrix)
        self.setFindRestriction_(self.findRestrictionsMatrix)
        
    def setFind_(self, sender):
        find = (sender.selectedCell().tag() == 1)
        self.findRestrictionsMatrix.setEnabled_(find)
        if find:
            self.setShouldFinish(False)
            self.validateButton.setTitle_(_(u'Search!'))
        else:
            self.findProgressLabel.setHidden_(YES)
            self.setShouldFinish(True)

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
        if find and not self.shouldFinish:
            if self.findRestrictionsMatrix.selectedCell().tag() == 2 and not os.path.exists(self.customLocationField.stringValue()):
                NSBeep()
            else:
                self.backButton.setEnabled_(NO)
                self.validateButton.setEnabled_(NO)
                self.findVideosMatrix.setEnabled_(NO)
                self.findRestrictionsMatrix.setEnabled_(NO)
                self.browseButton.setEnabled_(NO)
                self.customLocationField.setEnabled_(NO)
                self.findLabel.setHidden_(NO)
                self.findProgressIndicator.setHidden_(NO)
                self.findProgressLabel.setHidden_(NO)
                self.findCancelButton.setHidden_(NO)
                self.findProgressIndicator.startAnimation_(nil)
                self.findProgressLabel.setStringValue_("")
                NSThread.detachNewThreadSelector_toTarget_withObject_('performFind', self, nil)
        else:
            self.terminate()
        return not find
    
    def performFind(self):
        pool = NSAutoreleasePool.alloc().init()
        try:
            restrictionTag = self.findRestrictionsMatrix.selectedCell().tag()
            if restrictionTag == 0:
                path = os.path.expanduser(u'~/Movies')
            elif restrictionTag == 1:
                path = os.path.expanduser(u'~/')
            else:
                path = self.customLocationField.stringValue()
            path = osFilenameToFilenameType(path)
            self.keepFinding = True
            self.gathered = util.gatherVideos(path, self.onProgressFindingVideos)
            self.finishFindVideoTask(True)
        finally:
            del pool
    
    def onProgressFindingVideos(self, parsed, found):
        self.parsed = parsed
        progress = self.findProgressLabelFormat % (parsed, found)
        threads.callOnMainThread(self.findProgressLabel.setStringValue_, progress)
        return self.keepFinding
            
    def cancelFind_(self, sender):
        self.keepFinding = False
    
    @threads.onMainThread
    def finishFindVideoTask(self, goNext=False):
        self.initFindVideosPanelState()
        finalState = self.findProgressLabelFormat % (self.parsed, len(self.gathered))
        self.findProgressLabel.setStringValue_(finalState)
        self.findProgressLabel.setHidden_(NO)
        if goNext:
            self.setShouldFinish(True)

###############################################################################
