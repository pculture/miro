from objc import YES, NO, nil
from AppKit import *
from Foundation import *
from PyObjCTools import NibClassBuilder, Conversion

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
        generalItem = self.makePreferenceItem("GeneralItem", "General", "general_pref", self.generalView)
        channelsItem = self.makePreferenceItem("ChannelsItem", "Channels", "channels_pref", self.channelsView)
        downloadsItem = self.makePreferenceItem("DownloadsItem", "Downloads", "downloads_pref", self.downloadsView)
        diskSpaceItem = self.makePreferenceItem("DiskSpaceItem", "Disk Space", "disk_space_pref", self.diskSpaceView)

        self.items = {generalItem.itemIdentifier(): generalItem,
                      channelsItem.itemIdentifier(): channelsItem,
                      downloadsItem.itemIdentifier(): downloadsItem,
                      diskSpaceItem.itemIdentifier(): diskSpaceItem}

        self.allItems = (generalItem.itemIdentifier(),
                         channelsItem.itemIdentifier(),
                         downloadsItem.itemIdentifier(),
                         diskSpaceItem.itemIdentifier())

        initialItem = generalItem

        toolbar = NSToolbar.alloc().initWithIdentifier_("Preferences")
        toolbar.setDelegate_(self)
        toolbar.setAllowsUserCustomization_(NO)
        toolbar.setSelectedItemIdentifier_(initialItem.itemIdentifier())

        self.window().setToolbar_(toolbar)
        if hasattr(self.window(), 'setShowsToolbarButton_'): # 10.4 only
            self.window().setShowsToolbarButton_(NO)
        self.switchPreferenceView_(initialItem)

    def windowWillClose_(self, notification):
        self.window().endEditingFor_(nil)
        config.save()

    def makePreferenceItem(self, identifier, label, imageName, view):
        item = PreferenceItem.alloc().initWithItemIdentifier_(identifier)
        item.setLabel_(label)
        item.setImage_(NSImage.imageNamed_(imageName))
        item.setTarget_(self)
        item.setAction_("switchPreferenceView:")
        item.setView_(view)
        return item

    def toolbarAllowedItemIdentifiers_(self, toolbar):
        return self.allItems

    def toolbarDefaultItemIdentifiers_(self, toolbar):
        return self.allItems

    def toolbarSelectableItemIdentifiers_(self, toolbar):
        return self.allItems

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
        config.set(prefs.RUN_DTV_AT_STARTUP, run)

        defaults = NSUserDefaults.standardUserDefaults()
        lwdomain = defaults.persistentDomainForName_('loginwindow')
        lwdomain = Conversion.pythonCollectionFromPropertyList(lwdomain)
        launchedApps = lwdomain['AutoLaunchedApplicationDictionary']
        ourPath = NSBundle.mainBundle().bundlePath()
        ourEntry = None
        for entry in launchedApps:
            if entry['Path'] == ourPath:
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
