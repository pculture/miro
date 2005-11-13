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
        # This message could use some serious work.
        title = "Non-Standard Channel"
        message = "%s is not a DTV-style channel. DTV can try to subscribe, but videos may lack proper descriptions and thumbnails.\n\nPlease notify the publisher if you want this channel to be fully supported" % url
        defaultButtonTitle = "Subscribe"
        altButtonTitle = "Cancel"
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
