from xpcom import components
import traceback
import sys

import app
import eventloop
import util
import config
import prefs
import singleclick
import frontend
from frontend_implementation import HTMLDisplay
from frontend_implementation.UIBackendDelegate import UIBackendDelegate

nsIEventQueueService = components.interfaces.nsIEventQueueService
nsIProperties = components.interfaces.nsIProperties
nsIFile = components.interfaces.nsIFile
nsIProxyObjectManager = components.interfaces.nsIProxyObjectManager
pcfIDTVPyBridge = components.interfaces.pcfIDTVPyBridge
pcfIDTVJSBridge = components.interfaces.pcfIDTVJSBridge
pcfIDTVVLCRenderer = components.interfaces.pcfIDTVVLCRenderer

def makeComp(clsid, iid):
    """Helper function to get an XPCOM component"""
    return components.classes[clsid].createInstance(iid)

def makeService(clsid, iid):
    """Helper function to get an XPCOM service"""
    return components.classes[clsid].getService(iid)

def initializeProxyObjects(window):
    """Creates the jsbridge and vlcrenderer xpcom components, then wraps them in
    a proxy object, then stores them in the frontend module.  By making them
    proxy objects, we ensure that the calls to them get made in the xul event
    loop.
    """

    proxyManager = makeComp("@mozilla.org/xpcomproxy;1",
            nsIProxyObjectManager)
    eventQueueService = makeService("@mozilla.org/event-queue-service;1",
            nsIEventQueueService)
    xulEventQueue = eventQueueService.getSpecialEventQueue(
            nsIEventQueueService.UI_THREAD_EVENT_QUEUE)

    jsBridge = makeComp("@participatoryculture.org/dtv/jsbridge;1",
            pcfIDTVJSBridge)
    jsBridge.init(window)
    frontend.jsBridge = proxyManager.getProxyForObject(xulEventQueue,
            pcfIDTVJSBridge, jsBridge, nsIProxyObjectManager.INVOKE_ASYNC |
            nsIProxyObjectManager.FORCE_PROXY_CREATION)

    vlcRenderer = makeService("@participatoryculture.org/dtv/vlc-renderer;1",
            pcfIDTVVLCRenderer)
    vlcRenderer.init(window)
    frontend.vlcRenderer = proxyManager.getProxyForObject(xulEventQueue,
            pcfIDTVVLCRenderer, vlcRenderer, 
            nsIProxyObjectManager.INVOKE_SYNC |
            nsIProxyObjectManager.FORCE_PROXY_CREATION)

def getArgumentList(commandLine):
    """Convert a nsICommandLine component to a list of arguments to pass
    to the singleclick module."""

    args = [commandLine.getArgument(i) for i in range(commandLine.length)]
    # filter out the application.ini that gets included
    if len(args) > 0 and args[0].lower().endswith('application.ini'):
        args = args[1:]
    return args

# Copied from resource.py; if you change this function here, change it
# there too.
def appRoot():
    klass = components.classes["@mozilla.org/file/directory_service;1"]
    service = klass.getService(nsIProperties)
    file = service.get("XCurProcD", nsIFile)
    return file.path

class PyBridge:
    _com_interfaces_ = [pcfIDTVPyBridge]
    _reg_clsid_ = "{F87D30FF-C117-401e-9194-DF3877C926D4}"
    _reg_contractid_ = "@participatoryculture.org/dtv/pybridge;1"
    _reg_desc_ = "Bridge into DTV Python core"

    def __init__(self):
        self.started = False
        self.delegate = UIBackendDelegate()

    def onStartup(self, window):
        if self.started:
            util.failed("Loading window", details="onStartup called twice")
            return
        else:
            self.started = True
        try:
            logFile = config.get(prefs.LOG_PATHNAME)
            if logFile is not None:
                h = open(logFile, "wt")
                sys.stdout = sys.stderr = util.AutoflushingStream(h)
        except:
            pass

        initializeProxyObjects(window)
        app.main()

    def onShutdown(self):
        frontend.vlcRenderer.stop()
        app.controller.onShutdown()

    # Preference setters/getters.
    #
    # NOTE: these are not in the mail event loop, so we have to be careful in
    # accessing data.  config.get and config.set are threadsafe though.
    #
    def getRunAtStartup(self):
        return config.get(prefs.RUN_AT_STARTUP)
    def setRunAtStartup(self, value):
        config.set(prefs.RUN_AT_STARTUP, value)
    def getCheckEvery(self):
        return config.get(prefs.CHECK_CHANNELS_EVERY_X_MN)
    def setCheckEvery(self, value):
        return config.set(prefs.CHECK_CHANNELS_EVERY_X_MN, value)
    def getMoviesDirectory(self):
        return config.get(prefs.MOVIES_DIRECTORY)
    def changeMoviesDirectory(self, path, migrate):
        app.changeMoviesDirectory(path, migrate)
    def getLimitUpstream(self):
        return config.get(prefs.LIMIT_UPSTREAM)
    def setLimitUpstream(self, value):
        config.set(prefs.LIMIT_UPSTREAM, value)
    def getLimitUpstreamAmount(self):
        return config.get(prefs.UPSTREAM_LIMIT_IN_KBS)
    def setLimitUpstreamAmount(self, value):
        return config.set(prefs.UPSTREAM_LIMIT_IN_KBS, value)
    def getPreserveDiskSpace(self):
        return config.get(prefs.PRESERVE_DISK_SPACE)
    def setPreserveDiskSpace(self, value):
        config.set(prefs.PRESERVE_DISK_SPACE, value)
    def getPreserveDiskSpaceAmount(self):
        return config.get(prefs.PRESERVE_X_GB_FREE)
    def setPreserveDiskSpaceAmount(self, value):
        print "Setting disk space amt to %s" % value
        return config.set(prefs.PRESERVE_X_GB_FREE, value)
    def getExpireAfter(self):
        return config.get(prefs.EXPIRE_AFTER_X_DAYS)
    def setExpireAfter(self, value):
        return config.set(prefs.EXPIRE_AFTER_X_DAYS, value)

    @eventloop.asUrgent
    def handleCommandLine(self, commandLine):
        singleclick.setCommandLineArgs(getArgumentList(commandLine))

    @eventloop.asUrgent
    def handleSecondCommandLine(self, commandLine):
        singleclick.parseCommandLineArgs(getArgumentList(commandLine))

    def pageLoadFinished(self, area, url):
        eventloop.addUrgentCall(HTMLDisplay.runPageFinishCallback, 
                "%s finish callback" % area, args=(area, url))

    @eventloop.asUrgent
    def openFile(self, path):
        singleclick.openFile(path)

    @eventloop.asUrgent
    def setVolume(self, volume):
        app.controller.videoDisplay.setVolume(volume)

    @eventloop.asUrgent
    def quit(self):
        app.controller.quit()

    @eventloop.asUrgent
    def removeCurrentChannel(self):
        app.ModelActionHandler(self.delegate).removeCurrentFeed()

    @eventloop.asUrgent
    def updateCurrentChannel(self):
        app.ModelActionHandler(self.delegate).updateCurrentFeed()

    @eventloop.asUrgent
    def updateChannels(self):
        app.ModelActionHandler(self.delegate).updateAllFeeds()

    @eventloop.asUrgent
    def showHelp(self):
        self.delegate.openExternalURL('http://www.getdemocracy.com/help')

    @eventloop.asUrgent
    def copyChannelLink(self):
        app.ModelActionHandler(self.delegate).copyCurrentFeedURL()

    @eventloop.asUrgent
    def handleSimpleDialog(self, id, buttonIndex):
        self.delegate.handleDialog(id, buttonIndex)

    @eventloop.asUrgent
    def handleHTTPAuthDialog(self, id, buttonIndex, username, password):
        self.delegate.handleDialog(id, buttonIndex, username=username,
                password=password)

    @eventloop.asUrgent
    def addChannel(self, url):
        app.controller.addAndSelectFeed(url)

    @eventloop.asUrgent
    def openURL(self, url):
        self.delegate.openExternalURL(url)

    @eventloop.asUrgent
    def playPause(self):
        app.controller.playbackController.playPause()

    @eventloop.asUrgent
    def stop(self):
        app.controller.playbackController.stop()

    @eventloop.asUrgent
    def skip(self, step):
        app.controller.playbackController.skip(step)

    @eventloop.asUrgent
    def loadURLInBrowser(self, browserId, url):
        try:
            display = app.controller.frame.selectedDisplays[browserId]
        except KeyError:
            print "No HTMLDisplay for %s in loadURLInBrowser: "% browserId
        else:
            display.onURLLoad(url)
