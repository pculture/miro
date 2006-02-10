from database import DDBObject
from downloader import grabURL
from scheduler import ScheduleEvent
from xhtmltools import urlencode
from copy import copy
import re
import config
import threading
import urllib

HTMLPattern = re.compile("^.*(<head.*?>.*</body\s*>)", re.S)

firstTimeIntroBody = """
<body>
  <script type=\"text/javascript\">
    eventURL('template:first-time-intro');
  </script>
</body>
"""

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
        self.cond = threading.Condition()
        DDBObject.__init__(self)
        # Start loading the channel guide.
        print "Guide created. Scheduling first update."
        ScheduleEvent(0, self.update, False)
        # Start hourly reloads.
        ScheduleEvent(3600, self.update, True)

    ##
    # Called by pickle during serialization
    def __getstate__(self):
        temp = copy(self.__dict__)
        del temp['cond']
        del temp['loadedThisSession']
        return (1,temp)

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
        (version, data) = state

        if version == 0:
            self.sawIntro = data['viewed']
            self.cachedGuideBody = None
            self.loadedThisSession = False
            self.cond = threading.Condition()
        else:
            assert(version == 1)
            self.__dict__ = data
            self.cond = threading.Condition()
            self.loadedThisSession = False

        # Try to get a fresh version.
        # NEEDS: There's a race between self.update finishing and
        # getHTML() being called. If the latter happens first, we might get
        # the version of the channel guide from the last time DTV was run even
        # if we have a perfectly good net connection.
        ScheduleEvent(0, self.update, False)
        # Start hourly reloads.
        ScheduleEvent(3600, self.update, True)

    def getHTML(self):
        self.cond.acquire()
        try:
            print "guide in getHTML"
            if not self.sawIntro:
                print "guide: not viewed. toggling flag."
                self.sawIntro = True
                print "guide: setting viewed. now %s" % self.sawIntro
                return firstTimeIntroBody 
            else:
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
                    print "guide scheduling a load and returning apology"
                    ScheduleEvent(0, self.update, False)
                    return guideNotAvailableBody
                else:
                    if not self.loadedThisSession:
                        print "*** WARNING *** loading a stale copy of the chanel guide from cache"
                    return self.cachedGuideBody
        finally:
            self.cond.release()

    def update(self):
        # We grab the URL and convert the HTML to JavaScript so it can
        # be loaded from a plain old template. It's less elegant than
        # making another kind of feed object, but it makes it easier
        # for non-programmers to work with
        print "guide update running"
        url = config.get(config.CHANNEL_GUIDE_URL)

        import frontend
        apiurl = frontend.getDTVAPIURL()
        if apiurl:
            apiurl = urllib.quote_plus(apiurl)
            apicookie = urllib.quote_plus(frontend.getDTVAPICookie())
            url = "%s?dtvapiURL=%s&dtvapiCookie=%s" % (url, apiurl, apicookie)

        print "guide update grabbing %s" % url
        info = grabURL(url)
        print "guide update got: %s" % info
        if info is not None:
            html = info['file-handle'].read()
            info['file-handle'].close()

            # Put the HTML into the cache
            self.cond.acquire()
            try:
                self.cachedGuideBody = HTMLPattern.match(html).group(1)
                self.loadedThisSession = True
                self.cond.notify()
            finally:
                self.cond.release()
