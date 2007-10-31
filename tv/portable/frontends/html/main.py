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

from gtcache import gettext as _
from gtcache import ngettext
from frontends.html import dialogs
import frontends.html
import app
import autoupdate
import config
import eventloop
import frontendutil
import opml
import prefs
import signals
import views

class HTMLApplication:
    AUTOUPDATE_SUPPORTED = True

    def __init__(self):
        self.ignoreErrors = False
        self.inQuit = False
        self.delegate = app.delegate
        frontends.html.app = self

    def startup(self):
        signals.system.connect('error', self.handleError)
        signals.system.connect('download-complete', self.handleDownloadComplete)
        if self.AUTOUPDATE_SUPPORTED:
            eventloop.addTimeout (3, autoupdate.checkForUpdates, 
                    "Check for updates")
            signals.system.connect('update-available', self.handleNewUpdate)

    # signal handlers
    def handleDownloadComplete(self, obj, item):
        self.delegate.notifyDownloadCompleted(item)

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
        if hasattr(self.delegate, 'handleNewUpdate'):
            self.delegate.handleNewUpdate(latest)
            return

        url = item['enclosures'][0]['href']
        def callback(dialog):
            if dialog.choice == dialogs.BUTTON_DOWNLOAD:
                self.delegate.openExternalURL(url)
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
        self.delegate.askForOpenPathname(title, callback, None, 
                _("OPML Files"), ['opml'])

    @eventloop.asUrgent
    def exportChannels(self):
        callback = lambda p: opml.Exporter().exportSubscriptionsTo(p)
        title = _("Export OPML File")
        app.delegate.askForSavePathname(title, callback, None, u"miro_subscriptions.opml")
