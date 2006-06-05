import errno
import os
import signal
import sys
import time
import gtk
import threading
import traceback
import app
import dialogs
from gettext import gettext as _
from gettext import ngettext

import config
import prefs
from frontend import *
from frontend_implementation.gtk_queue import gtkSyncMethod, gtkAsyncMethod

###############################################################################
#### 'Delegate' objects for asynchronously asking the user questions       ####
###############################################################################

def EscapeMessagePart(message_part):
    if '&' in message_part or '<' in message_part:
        message_part = message_part.replace ("&", "&amp;")
        message_part = message_part.replace ("<", "&lt;")
    return message_part

def BuildDialog (title, message, buttons, default):
    dialog = gtk.Dialog(title, None, (), buttons)
    dialog.set_default_size(425, -1)
    label = gtk.Label()
    label.set_line_wrap(True)
    label.set_selectable(True)
    label.set_markup(message)
    label.set_padding (6, 6)
    dialog.vbox.add(label)
    label.show()
    dialog.set_default_response (default)
    return dialog

def BuildHTTPAuth(summary, message, prefillUser = None, prefillPassword = None):
    """Ask the user for HTTP login information for a location, identified
    to the user by its URL and the domain string provided by the
    server requesting the authorization. Default values can be
    provided for prefilling the form. If the user submits
    information, it's returned as a (user, password)
    tuple. Otherwise, if the user presses Cancel or similar, None
    is returned."""
    dialog = gtk.Dialog(summary, None, (), (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
    dialog.set_default_size(425, -1)
    table = gtk.Table()
    dialog.vbox.add(table)
    
    label = gtk.Label()
    label.set_line_wrap(True)
    label.set_selectable(True)
    label.set_markup(message)
    label.set_padding (6, 6)
    table.attach (label, 0, 2, 0, 1, gtk.FILL, gtk.FILL)

    label = gtk.Label()
    label.set_markup(_("Username:"))
    label.set_padding (6, 6)
    label.set_alignment (1.0, 0.5)
    table.attach (label, 0, 1, 1, 2, gtk.FILL, gtk.FILL)

    dialog.user = gtk.Entry()
    if (prefillUser != None):
        dialog.user.set_text(prefillUser)
    table.attach (dialog.user, 1, 2, 1, 2, gtk.FILL | gtk.EXPAND, gtk.FILL, 6, 6)

    label = gtk.Label()
    label.set_markup(_("Password:"))
    label.set_padding (6, 6)
    label.set_alignment (1.0, 0.5)
    table.attach (label, 0, 1, 2, 3, gtk.FILL, gtk.FILL)

    dialog.password = gtk.Entry()
    dialog.password.set_activates_default(True)
    if (prefillPassword != None):
        dialog.password.set_text(prefillPassword)
    table.attach (dialog.password, 1, 2, 2, 3, gtk.FILL | gtk.EXPAND, gtk.FILL, 6, 6)

    table.show_all()
    dialog.set_default_response (gtk.RESPONSE_OK)
    return dialog


@gtkSyncMethod
def ShowDialog (title, message, buttons, default = gtk.RESPONSE_CANCEL):
    dialog = BuildDialog (title, message, buttons, default)
    response = dialog.run()
    dialog.destroy()
    return response

once_dialogs = {}


@gtkAsyncMethod
def ShowDialogAsync (title, message, buttons, default = gtk.RESPONSE_CANCEL, once=None, callback=None):

    def AsyncDialogResponse(dialog, response):
        if callback:
            callback (response)
        dialog.destroy()

    def AsyncDialogDestroy (dialog):
        try:
            del once_dialogs[once]
        except:
            pass

    if once is not None and once_dialogs.has_key (once):
        return
    dialog = BuildDialog (title, message, buttons, default)
    dialog.connect("response", AsyncDialogResponse)
    dialog.connect("destroy", AsyncDialogDestroy)
    dialog.show()
    if once is not None:
        once_dialogs[once] = dialog

_stock = { dialogs.BUTTON_OK.text : gtk.STOCK_OK,
           dialogs.BUTTON_CANCEL.text : gtk.STOCK_CANCEL,
           dialogs.BUTTON_YES.text : gtk.STOCK_YES,
           dialogs.BUTTON_NO.text : gtk.STOCK_NO,
           dialogs.BUTTON_QUIT.text : gtk.STOCK_QUIT}


def pidIsRunning(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError, err:
        return err.errno == errno.EPERM

clipboard = None
primary = None

class UIBackendDelegate:

    def getHTTPAuth(self, url, domain, prefillUser = None, prefillPassword = None):
        dialog = BuildHTTPAuth (_("Channel requires authentication"), _("%s requires a username and password for \"%s\".") % (EscapeMessagePart(url), EscapeMessagePart(domain)), prefillUser, prefillPassword)
        response = dialog.run()
        retval = None
        if (response == gtk.RESPONSE_OK):
            retval = (dialog.user.get_text(), dialog.password.get_text())
        dialog.destroy()
        return retval

    # Called from another thread.
    def isScrapeAllowed(self, url):
        """Tell the user that URL wasn't a valid feed and ask if it should be
        scraped for links instead. Returns True if the user gives
        permission, or False if not."""
        summary = _("Not a DTV-style channel")
        message = _("But we'll try our best to grab the files.\n- It may take time to list the videos\n- Descriptions may look funny\n\nPlease contact the publishers of %s and ask if they have a DTV-style channel.") % EscapeMessagePart(url)
        buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, _("Continue"), gtk.RESPONSE_OK)
        response = ShowDialog (summary, message, buttons)
        if (response == gtk.RESPONSE_OK):
            return True
        else:
            return False

    def updateAvailable(self, url):
        """Tell the user that an update is available and ask them if they'd
        like to download it now"""
        title = _("DTV Version Alert")
        message = _("A new version of DTV is available.\n\nWould you like to download it now?")
        # NEEDS
        # right now, if user says yes, self.openExternalURL(url)
        print "WARNING: ignoring new version available at URL: %s" % url
#        raise NotImplementedError

    def dtvIsUpToDate(self):
        summary = _("DTV Version Check")
        message = _("This version of DTV is up to date.")
        # NEEDS inform user
        print "DTV: is up to date"

    def saveFailed(self, reason):
        summary = _("%s database save failed") % \
            (config.get(prefs.SHORT_APP_NAME), )
        message = _("%s was unable to save its database: %s.\nRecent changes may be lost.") % (EscapeMessagePart(config.get(prefs.LONG_APP_NAME)), EscapeMessagePart(reason))
        buttons = (gtk.STOCK_CLOSE, gtk.RESPONSE_OK)
        ShowDialogAsync (summary, message, buttons, once="saveFailed")

    def validateFeedRemoval(self, feedTitle):
        summary = _("Remove Channel")
        message = _("Are you sure you want to <b>remove</b> the channel\n   \'<b>%s</b>\'?\n<b>This operation cannot be undone.</b>") % EscapeMessagePart(feedTitle)
        buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_REMOVE, gtk.RESPONSE_OK)
        response = ShowDialog (summary, message, buttons)
        if (response == gtk.RESPONSE_OK):
            return True
        else:
            return False

    @gtkAsyncMethod
    def openExternalURL(self, url):
        inKDE = False
        # We could use Python's webbrowser.open() here, but
        # unfortunately, it doesn't have the same semantics under UNIX
        # as under other OSes. Sometimes it blocks, sometimes it doesn't.
        try:
            if (os.environ["KDE_FULL_SESSION"]):
                inKDE = True
        except:
            pass
        if (inKDE):
            os.spawnlp (os.P_NOWAIT, "kfmclient", "kfmclient", "exec", url)
        else:
            os.spawnlp (os.P_NOWAIT, "gnome-open", "gnome-open", url)

    def updateAvailableItemsCountFeedback(self, count):
        # Inform the user in a way or another that newly available items are
        # available
        pass

    def interruptDownloadsAtShutdown(self, downloadsCount):
        summary = _("Are you sure you want to quit?")
        message = ngettext ("You have %d download still in progress.", "You have %d downloads still in progress.", downloadsCount) % (downloadsCount,)
        buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_QUIT, gtk.RESPONSE_OK)
        response = ShowDialog (summary, message, buttons)
        if (response == gtk.RESPONSE_OK):
            return True
        else:
            return False

    def notifyUnkownErrorOccurence(self, when, log = ''):
        summary = _("Unknown Runtime Error")
        message = _("An unknown error has occurred %s.") % (EscapeMessagePart(when),)
        buttons = (gtk.STOCK_CLOSE, gtk.RESPONSE_OK)
        ShowDialogAsync (summary, message, buttons, once="UnknownError")
        return True

    def runDialog (self, dialog):
        if isinstance(dialog, dialogs.ChoiceDialog):
            buttons = []
            i = 0
            for button in dialog.buttons:
                if _stock.has_key(button.text):
                    buttons [0:0] = (_stock[button.text], i)
                else:
                    buttons [0:0] = (button.text, i)
                i = i + 1
    
            def Callback (response):
                if response == gtk.RESPONSE_DELETE_EVENT:
                    dialog.runCallback (None)
                elif response >= 0 and response < i:
                    dialog.runCallback (dialog.buttons [response])
                else:
                    dialog.runCallback (None)
    
            ShowDialogAsync (EscapeMessagePart(dialog.title), EscapeMessagePart(dialog.description), tuple(buttons), default=0, callback = Callback)
        elif isinstance(dialog, dialogs.HTTPAuthDialog):

            def AsyncDialogResponse(gtkDialog, response):
                retval = None
                if (response == gtk.RESPONSE_OK):
                    dialog.runCallback(dialogs.BUTTON_OK, gtkDialog.user.get_text(), gtkDialog.password.get_text())
                else:
                    dialog.runCallback(None)
                gtkDialog.destroy()

            gtkDialog = BuildHTTPAuth (EscapeMessagePart(dialog.title), EscapeMessagePart(dialog.description), dialog.prefillUser, dialog.prefillPassword)
            gtkDialog.connect("response", AsyncDialogResponse)
            gtkDialog.show()
        else:
            dialog.runCallback (None)

    @gtkAsyncMethod
    def copyTextToClipboard(self, text):
        global clipboard
        global primary
        if clipboard is None:
            clipboard = gtk.Clipboard(selection="CLIPBOARD")
        if primary is None:
            primary = gtk.Clipboard(selection="PRIMARY")
        clipboard.set_text(text)
        primary.set_text(text)

    def killDownloadDaemon(self, oldpid):
        if pidIsRunning(oldpid):
            try:
                os.kill(oldpid, signal.SIGTERM)
                for i in xrange(100):
                    time.sleep(.01)
                    if not pidIsRunning(oldpid):
                        return
                os.kill(oldpid, signal.SIGKILL)
            except:
                print "error killing download daemon"
                traceback.print_exc()

    def launchDownloadDaemon(self, oldpid, env):
        # Use UNIX style kill
        if oldpid is not None and pidIsRunning(oldpid):
            self.killDownloadDaemon(oldpid)

        environ = os.environ.copy()
        import democracy
        democracyPath = os.path.dirname(democracy.__file__)
        dlDaemonPath = os.path.join(democracyPath, 'dl_daemon')
        privatePath = os.path.join(dlDaemonPath, 'private')

        pythonPath = environ.get('PYTHONPATH', '').split(':')
        pythonPath[0:0] = [privatePath, democracyPath]
        environ['PYTHONPATH'] = ':'.join(pythonPath)

        environ.update(env)

        # run the Democracy_Downloader script
        script = os.path.join(dlDaemonPath,  'Democracy_Downloader.py')

        os.spawnlpe(os.P_NOWAIT, "python2.4", "python2.4", script, environ)
