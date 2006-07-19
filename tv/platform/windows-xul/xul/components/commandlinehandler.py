"""Democracy Command Line Handler."""

from xpcom import components

class DemocracyCLH:
    _com_interfaces_ = [components.interfaces.nsICommandLineHandler]
    _reg_clsid_ = "{951DF9BD-EED3-4571-8A87-A16BA157A6CD}"
    _reg_contractid_ = "@participatoryculture.org/dtv/commandlinehandler;1"
    _reg_desc_ = "Democracy Command line Handler"

    def __init__(self):
        pass

    def handle(self, commandLine):
        chromeURL = "chrome://dtv/content/main.xul"
        windowName = "DemocracyPlayer"
        wwatch = components.classes["@mozilla.org/embedcomp/window-watcher;1"]\
                .getService(components.interfaces.nsIWindowWatcher)
        pybridgeCID = "@participatoryculture.org/dtv/pybridge;1"
        pybridge = components.classes[pybridgeCID].getService()
        startupError = pybridge.getStartupError()
        if startupError:
            startupErrorURL = "chrome://dtv/content/startuperror.xul"
            wwatch.openWindow(None, startupErrorURL, "DemocracyPlayerError", 
                    "chrome,dialog=yes,all", None)
            return
        existingWindow = wwatch.getWindowByName(windowName, None)
        if existingWindow is None:
            try:
                pybridge.deleteVLCCache()
            except:
                print "WARNING: error in deleteVLCCache()"
            pybridge.handleCommandLine(commandLine)
            wwatch.openWindow(None, chromeURL, windowName,
                    "chrome,dialog=no,all", None)
        else:
            pybridge.handleCommandLine(commandLine)

catman = components.classes["@mozilla.org/categorymanager;1"].getService()
catman.queryInterface(components.interfaces.nsICategoryManager)
catman.addCategoryEntry("command-line-handler", "z-default",
        "@participatoryculture.org/dtv/commandlinehandler;1", True, True)
