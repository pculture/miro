import os
import signal
import sys
import time

from frontend import *

###############################################################################
#### 'Delegate' objects for asynchronously asking the user questions       ####
###############################################################################

class UIBackendDelegate:

    def getHTTPAuth(self, url, domain, prefillUser = None, prefillPassword = None):
        """Ask the user for HTTP login information for a location, identified
        to the user by its URL and the domain string provided by the
        server requesting the authorization. Default values can be
        provided for prefilling the form. If the user submits
        information, it's returned as a (user, password)
        tuple. Otherwise, if the user presses Cancel or similar, None
        is returned."""
        message = "%s requires a username and password for \"%s\"." % (url, domain)
        # NEEDS
        raise NotImplementedError

    def isScrapeAllowed(self, url):
        """Tell the user that URL wasn't a valid feed and ask if it should be
        scraped for links instead. Returns True if the user gives
        permission, or False if not."""
        summary = "Not a DTV-style channel"
        message = "But we'll try our best to grab the files.\n- It may take time to list the videos\n- Descriptions may look funny\n\nPlease contact the publishers of %s and ask if they have a DTV-style channel." % url
        defaultButtonTitle = 'Continue'
        # NEEDS
        raise NotImplementedError

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

    def validateFeedRemoval(self, feedTitle):
        summary = u'Remove Channel'
        message = u'Are you sure you want to remove the channel \'%s\'? This operation cannot be undone.' % feedTitle
        buttons = (u'Remove', u'Cancel')
        # NEEDS inform user
        print "WARNING: defaulting feed validation removal to True"
        return True

    def openExternalURL(self, url):
        # We could use Python's webbrowser.open() here, but
        # unfortunately, it doesn't have the same semantics under UNIX
        # as under other OSes. Sometimes it blocks, sometimes it doesn't.
        print "WARNING: ignoring external URL: %s" % url
#        raise NotImplementedError

    def updateAvailableItemsCountFeedback(self, count):
        # Inform the user in a way or another that newly available items are
        # available
        pass

    def interruptDownloadsAtShutdown(self, downloadsCount):
        summary = u'Are you sure you want to quit?'
        message = u'You have %d download%s still in progress.' % (downloadsCount, downloadsCount > 1 and 's' or '')
        buttons = (u'Quit', u'Cancel')
        # NEEDS inform user
        return True

    def notifyUnkownErrorOccurence(self, when, log = ''):
        summary = u'Unknown Runtime Error'
        message = u'An unknown error has occured %s.' % when
        # NEEDS inform user
        return True

    def copyTextToClipboard(self, text):
        print "WARNING: copyTextToClipboard not implemented"
        # NEEDS do it!

    def launchDownloadDaemon(self, oldpid, port):
        print "*** LAUNCHING**** "
        # Use UNIX style kill
        if oldpid is not None:
            print "KILLING old download daemon with pid: %r" % oldpid
            try:
                os.kill(oldpid, signal.SIGTERM)
                time.sleep(1)
                os.kill(oldpid, signal.SIGKILL)
            except:
                import traceback
                print "ERROR killing old daemon"
                traceback.print_exc()
                pass
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
            os.environ['DEMOCRACY_DOWNLOADER_PORT'] = str(port)
            # run the Democracy_Downloader script
            script = os.path.join(dlDaemonPath,  'Democracy_Downloader.py')
            os.execlp("python2.4", "python2.4", script)
        else:
            # parent processes, nothing to do here
            print "spawned download daemon (PID %d)" % pid
            pass
