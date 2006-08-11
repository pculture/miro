import sys
import frontend
import time
import gettext
import locale
import resource
import config
import prefs
import _winreg

from frontend_implementation import HTMLDisplay

###############################################################################
#### Application object                                                    ####
###############################################################################
langs = {
0x401: "ar",
0x416: "pt_BR",
0x804: "Chinese (Simplified)",
0x404: "Chinese (Traditional)",
0x405: "cs",
0x406: "da",
0x413: "nl",
0x409: "en",
0x40b: "fi",
0x40c: "fr",
0x407: "de",
0x408: "el",
0x40d: "he",
0x40e: "hu",
0x410: "it",
0x411: "jp",
0x412: "ko",
0x414: "nb",
0x415: "pl",
0x816: "pt",
0x419: "ru",
0xc0a: "es",
0x41D: "sv",
0x41f: "tr",
}

def getLocale():
    try:
    	keyName = "Software\Policies\Microsoft\Control Panel\Desktop"
        key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, keyName)
    	subkey = "MultiUILanguageID"
    	(val, t) = _winreg.QueryValueEx(key, subkey)
    	if t == _winreg.REG_DWORD:
            return langs[val]
    except:
        pass
    return ''
    
class Application:

    def __init__(self):
        print "Application init"

    def Run(self):
        HTMLDisplay.initTempDir()

        lang = getLocale()
        if lang:
            os.environ["LANGUAGE"] = lang
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
