from objc import YES, NO, nil
from AppKit import *
from Foundation import *
from PyObjCTools import NibClassBuilder

import app
import prefs
import config
import dialogs
import eventloop

NibClassBuilder.extractClasses("PreferencesWindow")

###############################################################################

class PreferenceItem (NSToolbarItem):

    def setView_(self, view):
        self.view = view

###############################################################################

class PreferencesWindowController (NibClassBuilder.AutoBaseClass):

    def init(self):
        super(PreferencesWindowController, self).initWithWindowNibName_("PreferencesWindow")
        return self

    def awakeFromNib(self):
        self.items = dict()
        self.allIdentifiers = list()
        
        generalItem = self.makePreferenceItem("GeneralItem", "General", "general_pref", self.generalView)
        channelsItem = self.makePreferenceItem("ChannelsItem", "Channels", "channels_pref", self.channelsView)
        downloadsItem = self.makePreferenceItem("DownloadsItem", "Downloads", "downloads_pref", self.downloadsView)
        diskSpaceItem = self.makePreferenceItem("DiskSpaceItem", "Disk Space", "disk_space_pref", self.diskSpaceView)
        playbackItem = self.makePreferenceItem("PlaybackItem", "Playback", "playback_pref", self.playbackView)

        initialItem = generalItem

        toolbar = NSToolbar.alloc().initWithIdentifier_("Preferences")
        toolbar.setDelegate_(self)
        toolbar.setAllowsUserCustomization_(NO)
        toolbar.setSelectedItemIdentifier_(initialItem.itemIdentifier())

        self.window().setToolbar_(toolbar)
        if hasattr(self.window(), 'setShowsToolbarButton_'): # 10.4 only
            self.window().setShowsToolbarButton_(NO)
        self.switchPreferenceView_(initialItem)

    def makePreferenceItem(self, identifier, label, imageName, view):
        item = PreferenceItem.alloc().initWithItemIdentifier_(identifier)
        item.setLabel_(label)
        item.setImage_(NSImage.imageNamed_(imageName))
        item.setTarget_(self)
        item.setAction_("switchPreferenceView:")
        item.setView_(view)
        
        identifier = item.itemIdentifier()
        self.items[identifier] = item
        self.allIdentifiers.append(identifier)
        
        return item

    def windowWillClose_(self, notification):
        self.window().endEditingFor_(nil)
        config.save()

    def toolbarAllowedItemIdentifiers_(self, toolbar):
        return self.allIdentifiers

    def toolbarDefaultItemIdentifiers_(self, toolbar):
        return self.allIdentifiers

    def toolbarSelectableItemIdentifiers_(self, toolbar):
        return self.allIdentifiers

    def toolbar_itemForItemIdentifier_willBeInsertedIntoToolbar_(self, toolbar, itemIdentifier, flag ):
        return self.items[ itemIdentifier ]

    def validateToolbarItem_(self, item):
        return YES

    def switchPreferenceView_(self, sender):
        if self.window().contentView() == sender.view:
            return

        window = self.window()
        wframe = window.frame()
        vframe = sender.view.frame()
        toolbarHeight = wframe.size.height - window.contentView().frame().size.height
        wframe.origin.y += wframe.size.height - vframe.size.height - toolbarHeight
        wframe.size = vframe.size
        wframe.size.height += toolbarHeight

        self.window().setContentView_(sender.view)
        self.window().setFrame_display_animate_(wframe, YES, YES)

###############################################################################

class GeneralPrefsController (NibClassBuilder.AutoBaseClass):
    
    def awakeFromNib(self):
        run = config.get(prefs.RUN_DTV_AT_STARTUP)
        self.runAtStartupCheckBox.setState_(run and NSOnState or NSOffState)
    
    def runAtStartup_(self, sender):
        run = (sender.state() == NSOnState)
        app.delegate.makeDemocracyRunAtStartup(run)
        config.set(prefs.RUN_DTV_AT_STARTUP, run)
                    
###############################################################################

class ChannelsPrefsController (NibClassBuilder.AutoBaseClass):

    def awakeFromNib(self):
        minutes = config.get(prefs.CHECK_CHANNELS_EVERY_X_MN)
        itemIndex = self.periodicityPopup.indexOfItemWithTag_(minutes)
        self.periodicityPopup.selectItemAtIndex_(itemIndex)

    def checkEvery_(self, sender):
        minutes = sender.selectedItem().tag()
        eventloop.addUrgentCall(lambda:config.set(prefs.CHECK_CHANNELS_EVERY_X_MN, minutes), "Setting update frequency pref.")

###############################################################################

class DownloadsPrefsController (NibClassBuilder.AutoBaseClass):
    
    def awakeFromNib(self):
        moviesDirPath = config.get(prefs.MOVIES_DIRECTORY)
        self.moviesDirectoryField.setStringValue_(moviesDirPath)
        limit = config.get(prefs.LIMIT_UPSTREAM)
        self.limitUpstreamCheckBox.setState_(limit and NSOnState or NSOffState)
        self.limitValueField.setEnabled_(limit)
        self.limitValueField.setIntValue_(config.get(prefs.UPSTREAM_LIMIT_IN_KBS))
        self.maxDownloadsField.setIntValue_(config.get(prefs.MAX_MANUAL_DOWNLOADS))
        btMinPort = config.get(prefs.BT_MIN_PORT)
        self.btMinPortField.setIntValue_(btMinPort)
        btMaxPort = config.get(prefs.BT_MAX_PORT)
        self.btMaxPortField.setIntValue_(btMaxPort)
    
    def limitUpstream_(self, sender):
        limit = (sender.state() == NSOnState)
        self.limitValueField.setEnabled_(limit)
        config.set(prefs.LIMIT_UPSTREAM, limit)
        self.setUpstreamLimit_(self.limitValueField)
    
    def setUpstreamLimit_(self, sender):
        limit = sender.intValue()
        config.set(prefs.UPSTREAM_LIMIT_IN_KBS, limit)
        
    def changeMoviesDirectory_(self):
        panel = NSOpenPanel.openPanel()
        panel.setCanChooseFiles_(NO)
        panel.setCanChooseDirectories_(YES)
        panel.setCanCreateDirectories_(YES)
        panel.setAllowsMultipleSelection_(NO)
        panel.setTitle_('Movies Directory')
        panel.setMessage_('Select a Directory to store Democracy downloads in.')
        panel.setPrompt_('Select')
        
        oldMoviesDirectory = self.moviesDirectoryField.stringValue()
        result = panel.runModalForDirectory_file_(oldMoviesDirectory, nil)
        
        if result == NSOKButton:
            newMoviesDirectory = panel.directory()
            if newMoviesDirectory != oldMoviesDirectory:
                self.moviesDirectoryField.setStringValue_(newMoviesDirectory)
                summary = u'Migrate existing movies?'
                message = u'You\'ve selected a new folder to download movies to.  Should Democracy migrate your existing downloads there?  (Currently dowloading movies will not be moved until they finish).'
                def migrationCallback(dialog):
                    migrate = (dialog.choice == dialogs.BUTTON_YES)
                    app.changeMoviesDirectory(newMoviesDirectory, migrate)
                dlog = dialogs.ChoiceDialog(summary, message, dialogs.BUTTON_YES, dialogs.BUTTON_NO)
                dlog.run(migrationCallback)
    
    def setMaxDownloads_(self, sender):
        maxDownloads = self.maxDownloadsField.intValue()
        config.set(prefs.MAX_MANUAL_DOWNLOADS, maxDownloads)

    def setBTMinPort_(self, sender):
        self.validateBTPortValues()
    
    def setBTMaxPort_(self, sender):
        self.validateBTPortValues()

    def validateBTPortValues(self):
        btMinPort = self.btMinPortField.intValue()
        btMaxPort = self.btMaxPortField.intValue()
        if btMinPort > btMaxPort:
            btMaxPort = btMinPort
            self.btMaxPortField.setIntValue_(btMaxPort)
        config.set(prefs.BT_MIN_PORT, btMinPort)
        config.set(prefs.BT_MAX_PORT, btMaxPort)
                
###############################################################################

class DiskSpacePrefsController (NibClassBuilder.AutoBaseClass):
    
    def awakeFromNib(self):
        preserve = config.get(prefs.PRESERVE_DISK_SPACE)
        self.preserveSpaceCheckBox.setState_(preserve and NSOnState or NSOffState)
        self.minimumSpaceField.setEnabled_(preserve)
        self.minimumSpaceField.setFloatValue_(config.get(prefs.PRESERVE_X_GB_FREE))
        itemTag = int(config.get(prefs.EXPIRE_AFTER_X_DAYS) * 24)
        itemIndex = self.expirationDelayPopupButton.indexOfItemWithTag_(itemTag)
        self.expirationDelayPopupButton.selectItemAtIndex_(itemIndex)
    
    def preserveDiskSpace_(self, sender):
        preserve = (sender.state() == NSOnState)
        self.minimumSpaceField.setEnabled_(preserve)
        config.set(prefs.PRESERVE_DISK_SPACE, preserve)
        self.setMinimumSpace_(self.minimumSpaceField)
    
    def setMinimumSpace_(self, sender):
        space = sender.floatValue()
        config.set(prefs.PRESERVE_X_GB_FREE, space)
        
    def setExpirationDelay_(self, sender):
        delay = sender.selectedItem().tag()
        config.set(prefs.EXPIRE_AFTER_X_DAYS, delay / 24.0)

###############################################################################

class PlaybackPrefsController (NibClassBuilder.AutoBaseClass):

    def awakeFromNib(self):
        singleMode = config.get(prefs.SINGLE_VIDEO_PLAYBACK_MODE)
        self.modesMatrix.selectCellWithTag_(int(singleMode))

    def setPlaybackMode_(self, sender):
        singleMode = bool(sender.selectedCell().tag())
        config.set(prefs.SINGLE_VIDEO_PLAYBACK_MODE, singleMode)

###############################################################################
