import resource
from database import DDBObject
from template import fillStaticTemplate
from httpclient import grabURL
from xhtmltools import urlencode
from copy import copy
import re
import app
import config
import indexes
import menu
import prefs
import threading
import urllib
import eventloop
import views
from gtcache import gettext as _

HTMLPattern = re.compile("^.*(<head.*?>.*</body\s*>)", re.S)

# Desired semantics:
#  * The first time getHTML() is called (ever, across sessions), the user
#    gets 'firstTimeIntroBody' above. Subsequent times, she gets the <body>
#    part of the document returned from CHANNEL_GUIDE_URL (the 'network guide
#    body'.)
#  * The network guide body is retrieved at program startup, and once an
#    hour after that, so that getHTML() can return immediately. If retrieval
#    fails, we just skip that hourly update. The last-retrieved copy is
#    kept in memory, and it is saved to disk across executions of the program.
#  * When getHTML() is called, we just return that cached copy. That might
#    be from the previous run of the program if we haven't succeeded in a
#    retrieval during this session.
#  * If we have *never* succeeded in retrieving the channel guide, we put up
#    an error page and immediately schedule a reload. We provide a "try again"
#    link that simply reloads the guide. Hopefully by the time the user
#    manages to click it, the scheduled update attempt will have completed.
#
# NEEDS: Right now, there's a race between execution (and completion)
# of the first update and the first call to getHTML(). On Windows, the
# latter has a tendency to happen first, meaning that on our first
# view of the channel guide in a session we see a stale copy of the
# guide from the last run. This usually isn't a problem on the first
# run, because the load will finish while the user is messing around
# with the tutorial.
#
# Fixing this is tricky -- do we want to block waiting for the update
# to complete during that first load? Then we need to redesign some of
# the frontend semantics somewhere, because this causes nasty
# lockup-like behavior on Windows. (It might be sufficient to call
# onStartup from a new thread rather than from a JS window creation
# event handler calling into Python.)

class ChannelGuide(DDBObject):
    def __init__(self, url=None):
        # Delayed callback for eventloop.
        self.dc = None
        # True if user has seen the tutorial, or this is a non default guide.
        self.sawIntro = url != None
        # If None, we have never successfully loaded the guide. Otherwise,
        # the <body> part of the front channel guide page from the last time
        # we loaded it, whenever that was (perhaps in a previous session.)
        self.cachedGuideBody = None
        # True if we have successfully loaded the channel guide in this
        # session.
        self.loadedThisSession = False

        # None means this is the default channel guide.
        self.url = url

        self.redirectedURL = None

        DDBObject.__init__(self)
        # Start loading the channel guide.
        self.startLoadsIfNecessary()

    def __str__(self):
        return "Channel Guide <%s>" % (self.url,)

    ##
    # Called by pickle during deserialization
    def onRestore(self):
        self.loadedThisSession = False
        self.dc = None

        # Try to get a fresh version.
        # NEEDS: There's a race between self.update finishing and
        # getHTML() being called. If the latter happens first, we might get
        # the version of the channel guide from the last time DTV was run even
        # if we have a perfectly good net connection.
        self.startLoadsIfNecessary()

    def startLoadsIfNecessary(self):
        import frontend
        if frontend.getDTVAPIURL():
            # Uses direct browsing. No precaching needed here.
            pass
        else:
            # Uses precaching. Set up an initial update, plus hourly reloads..
            self.startUpdates()

    def setSawIntro(self):
        self.sawIntro = True
        self.signalChange()

    def startUpdates(self):
        if not self.dc:
            self.dc = eventloop.addIdle (self.update, "Channel Guide Update")

    # How should we load the guide? Returns (scheme, value). If scheme is
    # 'url', value is a URL that should be loaded directly in the frame.
    # If scheme is 'template', value is the template that should be loaded in
    # the frame.
    def getLocation(self):
        if not self.sawIntro:
            return ('template', 'first-time-intro')

        import frontend
        apiurl = frontend.getDTVAPIURL()
        if apiurl:
            # We're on a platform that uses direct loads and DTVAPI.
            apiurl = urllib.quote_plus(apiurl)
            apicookie = urllib.quote_plus(frontend.getDTVAPICookie())
            url = "%s?dtvapiURL=%s&dtvapiCookie=%s" % (self.getURL(), apiurl, apicookie)
            return ('url', url)

        # We're on a platform that uses template inclusions and URL
        # interception.
        return ('template', 'guide')

    def makeContextMenu(self, templateName):
        menuItems = [
            (lambda: app.delegate.copyTextToClipboard(self.getURL()),
                _('Copy URL to clipboard')),
        ]
        if not self.getDefault():
            i = (lambda: app.controller.removeGuide(self), _('Remove'))
            menuItems.append(i)
        return menu.makeMenu(menuItems)

    def getHTML(self):
        # In the future, may want to use
        # self.loadedThisSession to tell if this is a fresh
        # copy of the channel guide, and/or block a bit to
        # give the initial load a chance to succeed or fail
        # (but this would require changing the frontend code
        # to expect the template code to block, and in general
        # seems like a bad idea.)
        #
        # A better solution would be to put up a "loading" page and
        # somehow shove an event to the page when the channel guide
        # load finishes that causes the browser to reload the page.
        if (not self.cachedGuideBody) or (not self.loadedThisSession):
            # Start a new attempt, so that clicking on the guide
            # tab again has at least a chance of working

            #print "DTV: No guide available! Sending apology instead."
            self.startUpdates()
            return fillStaticTemplate("go-to-guide", platform="", eventCookie="", id=self.getID())
        else:
            return self.cachedGuideBody

    def processUpdate(self, info):
        try:
            html = info["body"]

            # Put the HTML into the cache
            match = HTMLPattern.match(html)
            wasLoading = self.cachedGuideBody is None

            if match:
                self.cachedGuideBody = match.group(1)
            else:
                self.cachedGuideBody = html
            self.redirectedURL = info['redirected-url']

            selection = app.controller.selection
            if wasLoading:
                myTab = None
                for tab in views.guideTabs:
                    if tab.obj is self:
                        myTab = tab
                        break
                if myTab and selection.isTabSelected(myTab):
                    selection.displayCurrentTabContent()

            self.loadedThisSession = True
            self.signalChange()
        finally:
            self.dc = eventloop.addTimeout(3600, self.update, "Channel Guide Update")

    def processUpdateErrback(self, error):
        print "WARNING: HTTP error while downloading the channel guide (%s)" \
                % error
        self.dc = eventloop.addTimeout(3600, self.update, 
                "Channel Guide Update")

    def update(self):
        # We grab the URL and convert the HTML to JavaScript so it can
        # be loaded from a plain old template. It's less elegant than
        # making another kind of feed object, but it makes it easier
        # for non-programmers to work with
        print "DTV: updating the Guide"
        self.dc = grabURL(self.getURL(), self.processUpdate, self.processUpdateErrback)

    def remove(self):
        self.dc.cancel()
        DDBObject.remove(self)

    def getURL(self):
        if self.url is not None:
            return self.url
        else:
            return config.get(prefs.CHANNEL_GUIDE_URL)

    def getRedirectedURL(self):
        return self.redirectedURL

    def getDefault(self):
        return self.url is None

    # For the tabs
    def getTitle(self):
        if self.getDefault():
            return _('Channel Guide')
        else:
            return self.getURL()

    def getIconURL(self):
        return resource.url("images/channelguide-icon-tablist.png")

def getGuideByURL(url):
    return views.guides.getItemWithIndex(indexes.guidesByURL, url)
