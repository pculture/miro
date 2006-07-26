import sys
import frontend
import time
import gettext
import locale
import config
import prefs

from frontend_implementation import HTMLDisplay

###############################################################################
#### Application object                                                    ####
###############################################################################

class Application:

    def __init__(self):
        print "Application init"

    def Run(self):
        HTMLDisplay.initTempDir()

        locale.setlocale(locale.LC_ALL, '')
        gettext.bindtextdomain("democracyplayer", resource.path("locale"))
        gettext.textdomain("democracyplayer")
        gettext.bind_textdomain_codeset("democracyplayer","UTF-8")
        import psyco
        #psyco.log('\\dtv.psyco')
        psyco.profile(.03)

        # Start the core.
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
