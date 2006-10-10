import sys
import frontend
import time
import resource
import config
import prefs
import os
from platformutils import _getLocale as getLocale

from frontend_implementation import HTMLDisplay

###############################################################################
#### Application object                                                    ####
###############################################################################
class Application:

    def __init__(self):
        print "Application init"

    def Run(self):
        HTMLDisplay.initTempDir()

        lang = getLocale()
        if lang:
            if not os.path.exists(resource.path(r"..\chrome\locale\%s" % (lang,))):
                lang = "en-US"
        else:
            lang = "en-US"

        from xpcom import components
        ps_cls = components.classes["@mozilla.org/preferences-service;1"]
        ps = ps_cls.getService(components.interfaces.nsIPrefService)
        branch = ps.getBranch("general.useragent.")
        branch.setCharPref("locale", lang)

        import psyco
        #psyco.log('\\dtv.psyco')
        psyco.profile(.03)

        # Start the core.
        if frontend.startup.search:
            self.onStartup(frontend.startup.search.getFiles())
        else:
            self.onStartup()
        frontend.jsBridge.positionVolumeSlider(config.get(prefs.VOLUME_LEVEL))

    def onStartup(self):
        # For overriding
        pass

    def onShutdown(self):
        # For overriding
        pass

    # This is called on OS X when we are handling a click on an RSS feed
    # button for Safari. NEEDS: add code here to register as a RSS feed
    # reader on Windows too. Just call this function when we're launched
    # to handle a click on a feed.
    def addAndSelectFeed(self, url):
        # For overriding
        pass

###############################################################################
###############################################################################
