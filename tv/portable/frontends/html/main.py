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

"""Main module for the HTML frontend.  Responsible for startup, shutdown,
error reporting, etc.
"""

import logging

from miro.gtcache import gettext as _
from miro.gtcache import ngettext
from miro import dialogs
from miro.frontends.html import template
from miro.frontends.html import templatedisplay
from miro.platform.frontends.html.MainFrame import MainFrame
from miro.platform.frontends.html.UIBackendDelegate import UIBackendDelegate
from miro.platform.frontends.html import VideoDisplay
from miro import app
from miro import autoupdate
from miro import config
from miro import eventloop
from miro import iheartmiro
from miro import menubar
from miro import opml
from miro import prefs
from miro import startup
from miro import singleclick
from miro import signals
from miro import tabs
from miro import util
from miro import views

class HTMLApplication:
    """HTMLApplication handles the frontend when Miro is using the HTML-based
    templates for the display (i.e. the Miro frontend for version 1.0)
    """

    AUTOUPDATE_SUPPORTED = True

    def __init__(self):
        self.ignoreErrors = False
        self.inQuit = False
        self.loadedCustomChannels = False
        app.htmlapp = self
        app.delegate = UIBackendDelegate()
        self.frame = None
        self.lastDisplay = None

    def startup(self):
        signals.system.connect('error', self.handleError)
        signals.system.connect('download-complete', self.handleDownloadComplete)
        signals.system.connect('startup-success', self.handleStartupSuccess)
        signals.system.connect('startup-failure', self.handleStartupFailure)
        signals.system.connect('loaded-custom-channels', self.handleCustomChannelLoad)
        signals.system.connect('new-dialog', self.handleDialog)
        signals.system.connect('theme-first-run', self.handleThemeFirstRun)
        signals.system.connect('shutdown', self.onBackendShutdown)
        signals.system.connect('videos-added', self.onVideosAdded)
        self.installMenubarImplementations()
        startup.startup()

    def handleThemeFirstRun(self, obj, theme):
        if config.get(prefs.MAXIMIZE_ON_FIRST_RUN).lower() not in ['false','no','0']:
            app.delegate.maximizeWindow()

    def handleDialog(self, obj, dialog):
        app.delegate.runDialog(dialog)

    def handleStartupFailure(self, obj, summary, description):
        dialog = dialogs.MessageBoxDialog(summary, description)
        dialog.run(lambda d: self.cancelStartup())

    def installMenubarImplementations(self):
        menubar.menubar.addImpl("NewDownload", self.newDownload)
        menubar.menubar.addImpl("ImportChannels", self.importChannels)
        menubar.menubar.addImpl("ExportChannels", self.exportChannels)

    def onBackendShutdown(self, obj):
        logging.info ("Shutting down frontend")
        self.quitUI()

    def quitUI(self):
        """Stop the UI event loop.
        Platforms must implement this method.
        """
        raise NotImplementedError("HTMLApplication.quitUI() not implemented")

    def cancelStartup(self):
        app.controller.shutdown()

    def handleStartupSuccess(self, obj):
        if self.AUTOUPDATE_SUPPORTED:
            eventloop.addTimeout (3, autoupdate.checkForUpdates, 
                    "Check for updates")
            signals.system.connect('update-available', self.handleNewUpdate)

        if not config.get(prefs.STARTUP_TASKS_DONE):
            logging.info ("Showing startup dialog...")
            app.delegate.performStartupTasks(self.finishStartup)
            config.set(prefs.STARTUP_TASKS_DONE, True)
            config.save()
        else:
            self.finishStartup()

    def handleMoviesGone():
        title = _("Video Directory Missing")
        description = _("""
    Miro can't find your primary video directory.  This may be because it's \
    located on an external drive that is currently disconnected.

    If you continue, the video directory will be reset to a location on this \
    drive (this will cause you to lose some details about the videos on the \
    external drive).  You can also quit, connect the drive, and relaunch Miro.""")
        dialog = dialogs.ChoiceDialog(title, description, dialogs.BUTTON_QUIT,
                dialogs.BUTTON_LAUNCH_MIRO)
        def callback(dialog):
            if dialog.choice == dialogs.BUTTON_LAUNCH_MIRO:
                startup.finalizeStartup()
            else:
                self.cancelStartup()
        dialog.run(callback)

    @eventloop.asUrgent
    def finishStartup(self, gatheredVideos=None):
        # Keep a ref of the 'new' and 'download' tabs, we'll need'em later
        self.newTab = None
        self.downloadTab = None
        for tab in views.allTabs:
            if tab.tabTemplateBase == 'newtab':
                self.newTab = tab
            elif tab.tabTemplateBase == 'downloadtab':
                self.downloadTab = tab

        views.unwatchedItems.addAddCallback(self.onUnwatchedItemsCountChange)
        views.unwatchedItems.addRemoveCallback(self.onUnwatchedItemsCountChange)
        views.downloadingItems.addAddCallback(self.onDownloadingItemsCountChange)
        views.downloadingItems.addRemoveCallback(self.onDownloadingItemsCountChange)
        self.onUnwatchedItemsCountChange(None, None)
        self.onDownloadingItemsCountChange(None, None)

        # Set up the playback controller
        self.playbackController = VideoDisplay.PlaybackController()

        util.print_mem_usage("Pre-UI memory check")

        # Put up the main frame
        logging.info ("Displaying main frame...")
        self.frame = MainFrame(self)

        logging.info ("Creating video display...")
        # Set up the video display
        self.videoDisplay = VideoDisplay.VideoDisplay()
        self.videoDisplay.initRenderers()
        self.videoDisplay.playbackController = self.playbackController
        self.videoDisplay.setVolume(config.get(prefs.VOLUME_LEVEL))
        util.print_mem_usage("Post-UI memory check")

        # create our selection handler
        
        app.selection.connect('tab-selected', self.onTabSelected)
        app.selection.connect('item-selected', self.updateMenus)
        app.selection.selectFirstTab()

        if self.loadedCustomChannels:
            dialog = dialogs.MessageBoxDialog(_("Custom Channels"), Template(_("You are running a version of $longAppName with a custom set of channels.")).substitute(longAppName=config.get(prefs.LONG_APP_NAME)))
            dialog.run()
            views.feedTabs.resetCursor()
            tab = views.feedTabs.getNext()
            if tab is not None:
                app.selection.selectTabByObject(tab.obj)

        util.print_mem_usage("Post-selection memory check")

        channelTabOrder = util.getSingletonDDBObject(views.channelTabOrder)
        playlistTabOrder = util.getSingletonDDBObject(views.playlistTabOrder)
        channelTabOrder.connect('tab-added', self.makeLastTabVisible)
        playlistTabOrder.connect('tab-added', self.makeLastTabVisible)
        self.tabDisplay = templatedisplay.TemplateDisplay('tablist',
                'default', playlistTabOrder=playlistTabOrder,
                channelTabOrder=channelTabOrder)
        self.frame.selectDisplay(self.tabDisplay, self.frame.channelsDisplay)

        # If we have newly available items, provide feedback
        self.updateAvailableItemsCountFeedback()

        # Now adding the video files we possibly gathered from the startup
        # dialog
        if gatheredVideos is not None and len(gatheredVideos) > 0:
            singleclick.resetCommandLineView()
            for v in gatheredVideos:
                try:
                    singleclick.addVideo(v)
                except Exception, e:
                    logging.info ("error while adding file %s", v)
                    logging.info (e)

        util.print_mem_usage("Pre single-click memory check")

        # Use an idle for parseCommandLineArgs because the frontend may
        # have put in idle calls to do set up video playback or similar
        # things.
        eventloop.addIdle(singleclick.parseCommandLineArgs, 
                'parse command line')

        util.print_mem_usage("Post single-click memory check")

        app.controller.finishedStartup = True

        eventloop.addIdle(iheartmiro.checkIHeartMiroInstall, "Install iHeartMiro")

        logging.info ("Finished startup sequence")
        self.finishStartupSequence()

    def finishStartupSequence(self):
        """Called after startup is completed.  Platforms can override this
        method if they need take action at this point.
        """
        pass

    def handleCustomChannelLoad(self, obj):
        self.loadedCustomChannels = True

    def handleDownloadComplete(self, obj, item):
        app.delegate.notifyDownloadCompleted(item)

    def handleError(self, obj, report):
        if self.ignoreErrors:
            return

        def callback(dialog):
            if dialog.choice == dialogs.BUTTON_IGNORE:
                self.ignoreErrors = True
                return
            try:
                send_dabatase = dialogs.checkbox_value
            except AttributeError:
                send_dabatase = False
            try:
                description = dialog.textbox_value
            except AttributeError:
                description = u"Description text not implemented"
            app.controller.sendBugReport(report, description, send_dabatase)
        chkboxdialog = dialogs.CheckboxTextboxDialog(_("Internal Error"),_("Miro has encountered an internal error. You can help us track down this problem and fix it by submitting an error report."), _("Include entire program database including all video and channel metadata with crash report"), False, _("Describe what you were doing that caused this error"), dialogs.BUTTON_SUBMIT_REPORT, dialogs.BUTTON_IGNORE)
        chkboxdialog.run(callback)

    def handleNewUpdate(self, obj, item):
        """Handle new updates.  The default version opens the download page in
        a user's browser.
        """
        if hasattr(app.delegate, 'handleNewUpdate'):
            app.delegate.handleNewUpdate(item)
            return

        url = item['enclosures'][0]['href']
        def callback(dialog):
            if dialog.choice == dialogs.BUTTON_DOWNLOAD:
                app.delegate.openExternalURL(url)
        summary = _("%s Version Alert") % (config.get(prefs.SHORT_APP_NAME), )
        message = _("A new version of %s is available. Would you like to download it now?") % (config.get(prefs.LONG_APP_NAME), )
        dlog = dialogs.ChoiceDialog(summary, message, dialogs.BUTTON_DOWNLOAD, dialogs.BUTTON_CANCEL)
        dlog.run(callback)

    def handleUpToDate(self):
        title = _('%s Version Check') % (config.get(prefs.SHORT_APP_NAME), )
        message = _('%s is up to date.') % (config.get(prefs.LONG_APP_NAME), )
        dialogs.MessageBoxDialog(title, message).run()

    # methods to handle user interaction

    @eventloop.asUrgent
    def checkForUpdates(self):
        """Call when the user manually asks for updates."""
        autoupdate.checkForUpdates(self.handleUpToDate)


    @eventloop.asUrgent
    def quit(self):
        if self.inQuit:
            return
        downloadsCount = views.downloadingItems.len()
            
        if (downloadsCount > 0 and config.get(prefs.WARN_IF_DOWNLOADING_ON_QUIT)) or (app.controller.sendingCrashReport > 0):
            title = _("Are you sure you want to quit?")
            if app.controller.sendingCrashReport > 0:
                message = _("Miro is still uploading your crash report. If you quit now the upload will be canceled.  Quit Anyway?")
                dialog = dialogs.ChoiceDialog(title, message,
                                              dialogs.BUTTON_QUIT,
                                              dialogs.BUTTON_CANCEL)
            else:
                message = ngettext ("You have %d download still in progress.  Quit Anyway?", 
                                    "You have %d downloads still in progress.  Quit Anyway?", 
                                    downloadsCount) % (downloadsCount,)
                warning = _ ("Warn me when I attempt to quit with downloads in progress")
                dialog = dialogs.CheckboxDialog(title, message, warning, True,
                        dialogs.BUTTON_QUIT, dialogs.BUTTON_CANCEL)

            def callback(dialog):
                if dialog.choice == dialogs.BUTTON_QUIT:
                    if isinstance(dialog, dialogs.CheckboxDialog):
                        config.set(prefs.WARN_IF_DOWNLOADING_ON_QUIT,
                                   dialog.checkbox_value)
                    app.controller.shutdown()
                else:
                    self.inQuit = False
            dialog.run(callback)
            self.inQuit = True
        else:
            app.controller.shutdown()


    @eventloop.asUrgent
    def importChannels(self):
        callback = lambda p: opml.Importer().importSubscriptionsFrom(p)
        title = _("Import OPML File")
        app.delegate.askForOpenPathname(title, callback, None, 
                _("OPML Files"), ['opml'])

    @eventloop.asUrgent
    def exportChannels(self):
        callback = lambda p: opml.Exporter().exportSubscriptionsTo(p)
        title = _("Export OPML File")
        app.delegate.askForSavePathname(title, callback, None, u"miro_subscriptions.opml")

    ### Keep track of currently available+downloading items and refresh the
    ### corresponding tabs accordingly.

    def onUnwatchedItemsCountChange(self, obj, id):
        self.newTab.redraw()
        self.updateAvailableItemsCountFeedback()

    def onDownloadingItemsCountChange(self, obj, id):
        self.downloadTab.redraw()

    def updateAvailableItemsCountFeedback(self):
        count = views.unwatchedItems.len()
        app.delegate.updateAvailableItemsCountFeedback(count)

    ### Handling events received from the OS (via our base class) ###

    # Called by Frontend via Application base class in response to OS request.
    def addAndSelectFeed(self, url = None, showTemplate = None):
        return templatedisplay.GUIActionHandler().addFeed(url, showTemplate)

    def addAndSelectGuide(self, url = None):
        return templatedisplay.GUIActionHandler().addGuide(url)

    def addSearchFeed(self, term=None, style=dialogs.SearchChannelDialog.CHANNEL, location = None):
        return templatedisplay.GUIActionHandler().addSearchFeed(term, style, location)

    ### Handling 'DTVAPI' events from the channel guide ###

    def addFeed(self, url = None):
        return templatedisplay.GUIActionHandler().addFeed(url, selected = None)

    def selectFeed(self, url):
        return templatedisplay.GUIActionHandler().selectFeed(url)

    def newDownload(self, url = None):
        return templatedisplay.GUIActionHandler().addDownload(url)

    ### Chrome search:
    ### Switch to the search tab and perform a search using the specified engine.
    def performSearch(self, engine, query):
        util.checkU(engine)
        util.checkU(query)
        handler = templatedisplay.TemplateActionHandler(None, None)
        handler.updateLastSearchEngine(engine)
        handler.updateLastSearchQuery(query)
        handler.performSearch(engine, query)
        app.selection.selectTabByTemplateBase('searchtab')

    def copyCurrentFeedURL(self):
        tabs = app.selection.getSelectedTabs()
        if len(tabs) == 1 and tabs[0].isFeed():
            app.delegate.copyTextToClipboard(tabs[0].obj.getURL())

    def recommendCurrentFeed(self):
        tabs = app.selection.getSelectedTabs()
        if len(tabs) == 1 and tabs[0].isFeed():
            # See also dynamic.js if changing this URL
            feed = tabs[0].obj
            query = urllib.urlencode({'url': feed.getURL(), 'title': feed.getTitle()})
            app.delegate.openExternalURL('http://www.videobomb.com/democracy_channel/email_friend?%s' % (query, ))

    def copyCurrentItemURL(self):
        tabs = app.selection.getSelectedItems()
        if len(tabs) == 1 and isinstance(tabs[0], item.Item):
            url = tabs[0].getURL()
            if url:
                app.delegate.copyTextToClipboard(url)

    def onTabSelected(self, selection):
        self.displayCurrentTabContent()

    def displayCurrentTabContent(self):
        mainDisplay = self.frame.getDisplay(self.frame.mainDisplay)

        # Hack to avoid re-displaying channel template
        if (mainDisplay and hasattr(mainDisplay, 'templateName') and mainDisplay.templateName == 'channel'):
            if len(app.selection.tabListSelection.currentSelection) == 1:
                for id in app.selection.tabListSelection.currentSelection:
                    tabView = app.selection.tabListSelection.currentView
                    tab = tabView.getObjectByID(id)
                    if tab.contentsTemplate == 'channel':
                        newId = int(tab.obj.getID())
                        #print "swapping templates %d %d" % (mainDisplay.kargs['id'], newId)
                                                        
                        app.selection.itemListSelection.clearSelection()
                        self.updateMenus(app.selection)
                        if mainDisplay.kargs['id'] != newId:
                            mainDisplay.reInit(id = newId)
                        return
        newDisplay = self._chooseDisplayForCurrentTab(app.selection)

        # Don't redisplay the current tab if it's being displayed.  It messes
        # up our database callbacks.  The one exception is the guide tab,
        # where redisplaying it will reopen the home page.
        if (self.lastDisplay and newDisplay == self.lastDisplay and
                self.lastDisplay is mainDisplay and
                newDisplay.templateName != 'guide'):
            newDisplay.unlink()
            return

        app.selection.itemListSelection.clearSelection()
        self.updateMenus(app.selection)
        # do a queueSelectDisplay to make sure that the selectDisplay gets
        # executed after our changes to the tablist template.  This makes tab
        # selection feel faster because the selection changes quickly.
        template.queueSelectDisplay(self.frame, newDisplay, self.frame.mainDisplay)
        self.lastDisplay = newDisplay

    def _chooseDisplayForCurrentTab(self, selection):
        tls = selection.tabListSelection

        if len(tls.currentSelection) == 0:
            raise AssertionError("No tabs selected")
        elif len(tls.currentSelection) == 1:
            for id in tls.currentSelection:
                tab = tls.currentView.getObjectByID(id)
                return templatedisplay.TemplateDisplay(tab.contentsTemplate,
                        tab.templateState, frameHint=self.frame,
                        areaHint=self.frame.mainDisplay, id=tab.obj.getID())
        else:
            foldersSelected = False
            type = tls.getType()
            if type == 'playlisttab':
                templateName = 'multi-playlist'
            elif type == 'channeltab':
                templateName = 'multi-channel'
            selectedChildren = 0
            selectedFolders = 0
            containedChildren = 0
            for tab in selection.getSelectedTabs():
                if isinstance(tab.obj, folder.FolderBase):
                    selectedFolders += 1
                    view = tab.obj.getChildrenView()
                    containedChildren += view.len()
                    for child in view:
                        if child.getID() in tls.currentSelection:
                            selectedChildren -= 1
                else:
                    selectedChildren += 1
            return templatedisplay.TemplateDisplay(templateName, 'default',
                    frameHint=self.frame, areaHint=self.frame.mainDisplay,
                    selectedFolders=selectedFolders,
                    selectedChildren=selectedChildren,
                    containedChildren=containedChildren)

    def updateMenus(self, selection):
        tabTypes = selection.tabListSelection.getTypesDetailed()
        if tabTypes.issubset(set(['guidetab', 'addedguidetab'])):
            guideURL = selection.getSelectedTabs()[0].obj.getURL()
        else:
            guideURL = None
        multiple = len(selection.tabListSelection.currentSelection) > 1

        actionGroups = {}
        states = {"plural":[],
                  "folders":[],
                  "folder":[]}

        is_playlistlike = tabTypes.issubset (set(['playlisttab', 'playlistfoldertab']))
        is_channellike = tabTypes.issubset (set(['channeltab', 'channelfoldertab', 'addedguidetab']))
        is_channel = tabTypes.issubset (set(['channeltab', 'channelfoldertab']))
        if len (tabTypes) == 1:
            if multiple:
                if 'playlisttab' in tabTypes:
                    states["plural"].append("RemovePlaylists")
                elif 'playlistfoldertab' in tabTypes:
                    states["folders"].append("RemovePlaylists")
                elif 'channeltab' in tabTypes:
                    states["plural"].append("RemoveChannels")
                elif 'channelfoldertab' in tabTypes:
                    states["folders"].append("RemoveChannels")
                elif 'addedguidetab' in tabTypes:
                    states["plural"].append("ChannelGuides")
            else:
                if 'playlisttab' in tabTypes:
                    pass
                elif 'playlistfoldertab' in tabTypes:
                    states["folder"].append("RemovePlaylists")
                elif 'channeltab' in tabTypes:
                    pass
                elif 'channelfoldertab' in tabTypes:
                    states["folder"].append("RemoveChannels")
                elif 'addedguidetab' in tabTypes:
                    pass

        if multiple and is_channel:
            states["plural"].append("UpdateChannels")

        actionGroups["ChannelLikeSelected"] = is_channellike and not multiple
        actionGroups["ChannelLikesSelected"] = is_channellike
        actionGroups["PlaylistLikeSelected"] = is_playlistlike and not multiple
        actionGroups["PlaylistLikesSelected"] = is_playlistlike
        actionGroups["ChannelSelected"] = tabTypes.issubset (set(['channeltab'])) and not multiple
        actionGroups["ChannelsSelected"] = tabTypes.issubset (set(['channeltab', 'channelfoldertab']))
        actionGroups["ChannelFolderSelected"] = tabTypes.issubset(set(['channelfoldertab'])) and not multiple

        # Handle video item area.
        actionGroups["VideoSelected"] = False
        actionGroups["VideosSelected"] = False
        actionGroups["VideoPlayable"] = False
        videoFileName = None
        if 'downloadeditem' in selection.itemListSelection.getTypesDetailed():
            actionGroups["VideosSelected"] = True
            actionGroups["VideoPlayable"] = True
            if len(selection.itemListSelection.currentSelection) == 1:
                actionGroups["VideoSelected"] = True
                item = selection.itemListSelection.getObjects()[0]
                videoFileName = item.getVideoFilename()
            else:
                states["plural"].append("RemoveVideos")
#        if len(self.itemListSelection.currentSelection) == 0:
#            if playable_videos:
#                actionGroups["VideoPlayable"] = True

        self.frame.onSelectedTabChange(states, actionGroups, guideURL,
                videoFileName)

    def makeLastTabVisible(self, tabOrder, tab):
        try:
            tabDisplay = self.tabDisplay
        except AttributeError:
            # haven't created the tab display yet, just ignore the signal
            return
        # try to go back a little to make the view prettier
        tabOrder.getView().moveCursorToID(tab.objID())
        for i in range(3):
            last = tabOrder.getView().getPrev()
            if last is None:
                break
            tab = last
        tabDisplay.navigateToFragment('tab-%d' % tab.objID())


    def onVideosAdded(self, obj, commandLineView):
        self.playView(commandLineView)

    def playView(self, view, firstItemId=None, justPlayOne=False):
        self.playbackController.configure(view, firstItemId, justPlayOne)
        self.playbackController.enterPlayback()
