# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

"""Main module for the HTML frontend.  Responsible for startup, shutdown,
error reporting, etc.
"""

import logging

from gtcache import gettext as _
from gtcache import ngettext
from frontends.html import dialogs
from frontends.html.templatedisplay import TemplateDisplay
import frontend
import app
import autoupdate
import config
import eventloop
import frontendutil
import opml
import prefs
import selection
import startup
import singleclick
import signals
import tabs
import util
import views

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

    def startup(self):
        signals.system.connect('error', self.handleError)
        signals.system.connect('download-complete', self.handleDownloadComplete)
        signals.system.connect('startup-success', self.handleStartupSuccess)
        signals.system.connect('startup-failure', self.handleStartupFailure)
        signals.system.connect('loaded-custom-channels',
                self.handleCustomChannelLoad)
        signals.system.connect('shutdown', self.onBackendShutdown)
        startup.initialize()

    def handleStartupFailure(self, obj, summary, description):
        dialog = dialogs.MessageBoxDialog(summary, description)
        dialog.run(lambda d: self.cancelStartup())

    def onBackendShutdown(self, obj):
        logging.info ("Shutting down frontend")
        self.quitUI()

    def quitUI(self):
        """Stop the UI event loop.
        Platforms must implement this method.
        """
        raise NotImplementedError("HTMLApplication.quit() not implemented")

    def cancelStartup(self):
        self.quitUI()
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
        self.playbackController = frontend.PlaybackController()

        # HACK
        app.controller.playbackController = self.playbackController

        util.print_mem_usage("Pre-UI memory check")

        # Put up the main frame
        logging.info ("Displaying main frame...")
        self.frame = frontend.MainFrame(self)
        # HACK
        app.controller.frame = self.frame

        logging.info ("Creating video display...")
        # Set up the video display
        self.videoDisplay = frontend.VideoDisplay()
        self.videoDisplay.initRenderers()
        self.videoDisplay.playbackController = self.playbackController
        self.videoDisplay.setVolume(config.get(prefs.VOLUME_LEVEL))
        util.print_mem_usage("Post-UI memory check")

        # HACK
        app.controller.videoDisplay = self.videoDisplay

        # create our selection handler
        
        self.selection = selection.SelectionHandler()

        # HACK
        app.controller.selection = self.selection

        self.selection.selectFirstTab()

        if self.loadedCustomChannels:
            dialog = dialogs.MessageBoxDialog(_("Custom Channels"), Template(_("You are running a version of $longAppName with a custom set of channels.")).substitute(longAppName=config.get(prefs.LONG_APP_NAME)))
            dialog.run()
            views.feedTabs.resetCursor()
            tab = views.feedTabs.getNext()
            if tab is not None:
                self.selection.selectTabByObject(tab.obj)

        util.print_mem_usage("Post-selection memory check")

        channelTabOrder = util.getSingletonDDBObject(views.channelTabOrder)
        playlistTabOrder = util.getSingletonDDBObject(views.playlistTabOrder)
        self.tabDisplay = TemplateDisplay('tablist', 'default',
                playlistTabOrder=playlistTabOrder,
                channelTabOrder=channelTabOrder)
        # HACK
        app.controller.tabDisplay = self.tabDisplay
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
            frontendutil.sendBugReport(report, description, send_dabatase)
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
            
        if (downloadsCount > 0 and config.get(prefs.WARN_IF_DOWNLOADING_ON_QUIT)) or (frontendutil.sendingCrashReport > 0):
            title = _("Are you sure you want to quit?")
            if frontendutil.sendingCrashReport > 0:
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
