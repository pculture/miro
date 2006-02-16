from frontend_implementation.HTMLDisplay import execChromeJS
from random import randint
from threading import Event
from urllib import unquote

###############################################################################
#### 'Delegate' objects for asynchronously asking the user questions       ####
###############################################################################

def dispatchResultByCookie(cookie, url):
    UIBackendDelegate.returnValues[cookie] = unquote(url)
    UIBackendDelegate.events[cookie].set()

#FIXME: is this sufficient?
def generateCookie():
    return str(randint(1000000000,9999999999))

class UIBackendDelegate:

    events = {}
    returnValues ={}

    def initializeReturnEvent(self):
        """Set up the data structures to listen for a return event
        from XUL"""

        cookie = generateCookie()
        UIBackendDelegate.events[cookie] = Event()
        return cookie

    def getReturnValue(self, cookie):
        """Block until the frontend gives us a return value, then
        return it"""

        UIBackendDelegate.events[cookie].wait()
        retval = UIBackendDelegate.returnValues[cookie]
        del UIBackendDelegate.events[cookie]
        del UIBackendDelegate.returnValues[cookie]
        return retval

    def getHTTPAuth(self, url, domain, prefillUser = None, prefillPassword = None):
        """Ask the user for HTTP login information for a location, identified
        to the user by its URL and the domain string provided by the
        server requesting the authorization. Default values can be
        provided for prefilling the form. If the user submits
        information, it's returned as a (user, password)
        tuple. Otherwise, if the user presses Cancel or similar, None
        is returned."""
        cookie = self.initializeReturnEvent()
        message = "%s requires a username and password for \"%s\"." % (url, domain)
        message = message.replace("\\","\\\\").replace("\"","\\\"").replace("'","\\'")
        execChromeJS("showPasswordDialog('%s','%s');" % (cookie, message))

        ret = self.getReturnValue(cookie)
        if (len(ret) == 0):
            return None

        # FIXME find a saner way of marshalling data
        # Currently, the pair of strings is separated by "|", escaped by "\\"
        ret = ret.split("|",1)
        while ((len(ret[0])>0) and (ret[0][-1] == "\\") and 
               (len(ret[0]) == 1 or ret[0][-2] != "\\")):
            temp = ret.pop(0)
            ret[0] = temp + '|' + ret[0]
        while ((len(ret[1])>0) and (ret[1][-1] == "\\") and 
               (len(ret[1]) == 1 or ret[1][-2] != "\\")):
            temp = ret.pop(1)
            ret[1] = temp + '|' + ret[1]
        user = ret[0].replace("\\|","|").replace("\\\\","\\")
        password = ret[1].replace("\\|","|").replace("\\\\","\\")
        #print "Username is (%s)" % user
        #print "Password is (%s)" % password
        return (user, password)

    def isScrapeAllowed(self, url):
        """Tell the user that URL wasn't a valid feed and ask if it should be
        scraped for links instead. Returns True if the user gives
        permission, or False if not."""
        cookie = self.initializeReturnEvent()
        url = url.replace("\\","\\\\").replace("\"","\\\"").replace("'","\\'")
        execChromeJS(("showIsScrapeAllowedDialog('%s','%s');" % (cookie,url)))
        return (str(self.getReturnValue(cookie)) != "0")

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

    def notifyUnkownErrorOccurence(self, when):
        summary = u'Unknown Runtime Error'
        message = u'An unknown error has occured %s.' % when
        # NEEDS inform user
        return True
