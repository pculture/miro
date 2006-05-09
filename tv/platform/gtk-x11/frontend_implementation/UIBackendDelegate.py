import errno
import os
import signal
import sys
import time
import gtk
import threading
import traceback
import app

from frontend import *
from frontend_implementation.gtk_queue import gtkSyncMethod

###############################################################################
#### 'Delegate' objects for asynchronously asking the user questions       ####
###############################################################################

def EscapeMessagePart(message_part):
    if '&' in message_part or '<' in message_part:
        message_part = message_part.replace ("&", "&amp;")
        message_part = message_part.replace ("<", "&lt;")
    return message_part

@gtkSyncMethod
def ShowDialog (title, message, buttons, default = gtk.RESPONSE_CANCEL):
    dialog = gtk.Dialog(title, None, (), buttons)
    label = gtk.Label()
    alignment = gtk.Alignment()
    label.set_markup(message)
    label.set_padding (6, 6)
    dialog.vbox.add(label)
    label.show()
    dialog.set_default_response (default)
    response = dialog.run()
    dialog.destroy()
    return response

def pidIsRunning(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError, err:
        return err.errno == errno.EPERM

class UIBackendDelegate:

    @gtkSyncMethod
    def getHTTPAuth(self, url, domain, prefillUser = None, prefillPassword = None):
        """Ask the user for HTTP login information for a location, identified
        to the user by its URL and the domain string provided by the
        server requesting the authorization. Default values can be
        provided for prefilling the form. If the user submits
        information, it's returned as a (user, password)
        tuple. Otherwise, if the user presses Cancel or similar, None
        is returned."""
        summary = "Channel requires authentication"
        message = "%s requires a username and password for \"%s\"." % (EscapeMessagePart(url), EscapeMessagePart(domain))
        dialog = gtk.Dialog(summary, None, (), (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
        table = gtk.Table()
        dialog.vbox.add(table)
        
        label = gtk.Label()
        label.set_markup(message)
        label.set_padding (6, 6)
        table.attach (label, 0, 2, 0, 1, gtk.FILL, gtk.FILL)

        label = gtk.Label()
        label.set_markup("Username:")
        label.set_padding (6, 6)
        label.set_alignment (1.0, 0.5)
        table.attach (label, 0, 1, 1, 2, gtk.FILL, gtk.FILL)

        user = gtk.Entry()
        if (prefillUser != None):
            user.set_text(prefillUser)
        table.attach (user, 1, 2, 1, 2, gtk.FILL | gtk.EXPAND, gtk.FILL, 6, 6)

        label = gtk.Label()
        label.set_markup("Password:")
        label.set_padding (6, 6)
        label.set_alignment (1.0, 0.5)
        table.attach (label, 0, 1, 2, 3, gtk.FILL, gtk.FILL)

        password = gtk.Entry()
        if (prefillPassword != None):
            password.set_text(prefillPassword)
        table.attach (password, 1, 2, 2, 3, gtk.FILL | gtk.EXPAND, gtk.FILL, 6, 6)

        table.show_all()
        dialog.set_default_response (gtk.RESPONSE_OK)
        response = dialog.run()
        retval = None
        if (response == gtk.RESPONSE_OK):
            retval = (user.get_text(), password.get_text())
        dialog.destroy()
        return retval

    # Called from another thread.
    def isScrapeAllowed(self, url):
        """Tell the user that URL wasn't a valid feed and ask if it should be
        scraped for links instead. Returns True if the user gives
        permission, or False if not."""
        summary = "Not a DTV-style channel"
        message = "But we'll try our best to grab the files.\n- It may take time to list the videos\n- Descriptions may look funny\n\nPlease contact the publishers of %s and ask if they have a DTV-style channel." % EscapeMessagePart(url)
        buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, "Continue", gtk.RESPONSE_OK)
        response = ShowDialog (summary, message, buttons)
        if (response == gtk.RESPONSE_OK):
            return True
        else:
            return False

    def updateAvailable(self, url):
        """Tell the user that an update is available and ask them if they'd
        like to download it now"""
        title = "DTV Version Alert"
        message = "A new version of DTV is available.\n\nWould you like to download it now?"
        # NEEDS
        # right now, if user says yes, self.openExternalURL(url)
        print "WARNING: ignoring new version available at URL: %s" % url
#        raise NotImplementedError

    def dtvIsUpToDate(self):
        summary = u'DTV Version Check'
        message = u'This version of DTV is up to date.'
        # NEEDS inform user
        print "DTV: is up to date"

    def saveFailed(self, reason):
        summary = u'%s database save failed' % \
            (config.get(config.SHORT_APP_NAME), )
        message = u"%s was unable to save its database.\nRecent changes may be lost\n\n%s" % (EscapeMessagePart(config.get(config.LONG_APP_NAME)), EscapeMessagePart(reason))
        buttons = (gtk.STOCK_CLOSE, gtk.RESPONSE_OK)
        ShowDialog (summary, message, buttons)

    def validateFeedRemoval(self, feedTitle):
        summary = u'Remove Channel'
        message = u'Are you sure you want to <b>remove</b> the channel\n   \'<b>%s</b>\'?\n<b>This operation cannot be undone.</b>' % EscapeMessagePart(feedTitle)
        buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_REMOVE, gtk.RESPONSE_OK)
        response = ShowDialog (summary, message, buttons)
        if (response == gtk.RESPONSE_OK):
            return True
        else:
            return False

    @gtkSyncMethod
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
        summary = u'Are you sure you want to quit?'
        message = u'You have %d download%s still in progress.' % (downloadsCount, downloadsCount > 1 and 's' or '')
        buttons = (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_QUIT, gtk.RESPONSE_OK)
        response = ShowDialog (summary, message, buttons)
        if (response == gtk.RESPONSE_OK):
            return True
        else:
            return False

    def notifyUnkownErrorOccurence(self, when, log = ''):
        summary = u'Unknown Runtime Error'
        message = u'An unknown error has occured %s.' % EscapeMessagePart(when)
        buttons = (gtk.STOCK_CLOSE, gtk.RESPONSE_OK)
        ShowDialog (summary, message, buttons)
        return True

    @gtkSyncMethod
    def copyTextToClipboard(self, text):
        gtk.Clipboard(selection="CLIPBOARD").set_text(text)
        gtk.Clipboard(selection="PRIMARY").set_text(text)

    def killDownloadDaemon(self, oldpid):
        if pidIsRunning(oldpid):
            try:
                os.kill(oldpid, signal.SIGTERM)
                time.sleep(1)
                if pidIsRunning(oldpid):
                    os.kill(oldpid, signal.SIGKILL)
            except:
                print "error killing download daemon"
                traceback.print_exc()

    def launchDownloadDaemon(self, oldpid, env):
        # Use UNIX style kill
        if oldpid is not None and pidIsRunning(oldpid):
            self.killDownloadDaemon(oldpid)
        pid = os.fork()
        if pid == 0:
            # child process
            # insert the dl_daemon.private directory, then the democracy
            # directory at the top of PYTOHNPATH
            import democracy
            democracyPath = os.path.dirname(democracy.__file__)
            dlDaemonPath = os.path.join(democracyPath, 'dl_daemon')
            privatePath = os.path.join(dlDaemonPath, 'private')
            pythonPath = os.environ.get('PYTHONPATH', '').split(':')
            pythonPath[0:0] = [privatePath, democracyPath]
            os.environ['PYTHONPATH'] = ':'.join(pythonPath)
            for key, value in env.items():
                os.environ[key] = value
            # run the Democracy_Downloader script
            script = os.path.join(dlDaemonPath,  'Democracy_Downloader.py')
            os.execlp("python2.4", "python2.4", script)
        else:
            # parent processes, nothing to do here
#            print "spawned download daemon (PID %d)" % pid
            pass
