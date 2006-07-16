from database import DDBObject
from httpclient import grabURL
from xhtmltools import urlencode
from copy import copy
import re
import app
import config
import prefs
import threading
import urllib
import eventloop

HTMLPattern = re.compile("^.*(<head.*?>.*</body\s*>)", re.S)

# NEEDS: Make this something more attractive
guideNotAvailableBody = """
<body>
  <script type=\"text/javascript\">
    function tryAgain() {
      eventURL('template:guide-loading');
    }
  </script>

  <p>
    The channel guide could not be loaded. Perhaps you're not connected to the
    Internet?
  </p>
  <p>
    <a href="#" onclick="tryAgain();">Try again</a>
  </p>
</body>
"""

#""" Fix emacs misparse for coloration.

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
    def __init__(self):
        # Delayed callback for eventloop.
        self.dc = None
        # True if user has seen the tutorial
        self.sawIntro = False 
        # If None, we have never successfully loaded the guide. Otherwise,
        # the <body> part of the front channel guide page from the last time
        # we loaded it, whenever that was (perhaps in a previous session.)
        self.cachedGuideBody = None
        # True if we have successfully loaded the channel guide in this
        # session.
        self.loadedThisSession = False
        # Condition variable protecting access to above; signalled when
        # loadedThisSession changes.
        DDBObject.__init__(self)
        # Start loading the channel guide.
        self.startLoadsIfNecessary()

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
        if self.dc:
            self.dc.cancel()
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
            url = config.get(prefs.CHANNEL_GUIDE_URL)
            apiurl = urllib.quote_plus(apiurl)
            apicookie = urllib.quote_plus(frontend.getDTVAPICookie())
            url = "%s?dtvapiURL=%s&dtvapiCookie=%s" % (url, apiurl, apicookie)
            return ('url', url)

        # We're on a platform that uses template inclusions and URL
        # interception.
        if self.cachedGuideBody is not None:
            return ('template', 'guide')
        else:
            return ('template', 'guide-loading')

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
        if not self.cachedGuideBody:
            # Start a new attempt, so that clicking on the guide
            # tab again has at least a chance of working
            print "DTV: No guide available! Sending apology instead."
            self.startUpdates()
            return guideNotAvailableBody
        else:
            if not self.loadedThisSession:
                print "DTV: *** WARNING *** loading a stale copy of the channel guide from cache"
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

            currentTab = app.controller.currentSelectedTab
            if currentTab.tabTemplateBase == 'guidetab' and wasLoading:
                app.controller.selectTab(currentTab.id)

            self.loadedThisSession = True
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
        url = config.get(prefs.CHANNEL_GUIDE_URL)
        self.dc = grabURL(url, self.processUpdate, self.processUpdateErrback)
