import sys
from xpcom import components, nsError, ServerException
import traceback
import sys
import os
import time

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

def getArgumentList(commandLine):
    """Convert a nsICommandLine component to a list of arguments to pass
    to the singleclick module."""

    args = [commandLine.getArgument(i) for i in range(commandLine.length)]
    # filter out the application.ini that gets included
    if args[0].lower().endswith('application.ini'):
        args = args[1:]
    return args

def makeComp(clsid, iid):
    """Helper function to create an XPCOM component"""
    return components.classes[clsid].createInstance(iid)

def makeService(clsid, iid):
    """Helper function to get an XPCOM service"""
    return components.classes[clsid].getService(iid)

def makeJSBridgeProxy(mainWindowDocument):
    """Creates our JSBridge component, then wraps it in a Proxy object.  This
    ensures that all its methods run in the main xul event loop.
    """

    jsBridge = makeComp("@participatoryculture.org/dtv/jsbridge;1",
            pcfIDTVJSBridge)
    jsBridge.init(mainWindowDocument)
    proxyManager = makeService("@mozilla.org/xpcomproxy;1",
            nsIProxyObjectManager)
    eventQueueService = makeService("@mozilla.org/event-queue-service;1",
            nsIEventQueueService)
    xulEventQueue = eventQueueService.getSpecialEventQueue(
            nsIEventQueueService.UI_THREAD_EVENT_QUEUE)
    return proxyManager.getProxyForObject(xulEventQueue, pcfIDTVJSBridge,
            jsBridge, nsIProxyObjectManager.INVOKE_ASYNC |
            nsIProxyObjectManager.FORCE_PROXY_CREATION)

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

    def onStartup(self, mainWindowDocument):
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

        frontend.jsBridge = makeJSBridgeProxy(mainWindowDocument)
        app.main()

    def handleCommandLine(self, commandLine):
        singleclick.setCommandLineArgs(getArgumentList(commandLine))

    def handleSecondCommandLine(self, commandLine):
        singleclick.parseCommandLineArgs(getArgumentList(commandLine))

    def onShutdown(self):
        app.controller.onShutdown()

    def pageLoadFinished(self, area):
        eventloop.addIdle(HTMLDisplay.runPageFinishCallback, 
                "%s finish callback" % area, args=(area,))

    @eventloop.asIdle
    def setVolume(self, volume):
        app.controller.videoDisplay.setVolume(volume)

    @eventloop.asIdle
    def quit(self):
        app.controller.quit()

    @eventloop.asIdle
    def removeCurrentChannel(self):
        app.ModelActionHandler(UIBackendDelegate()).removeCurrentFeed()

    @eventloop.asIdle
    def updateCurrentChannel(self):
        print "UPDATE CURRENT"
        app.ModelActionHandler(UIBackendDelegate()).updateCurrentFeed()

    @eventloop.asIdle
    def updateChannels(self):
        print "UPDATE ALL"
        app.ModelActionHandler(UIBackendDelegate()).updateAllFeeds()

    @eventloop.asIdle
    def showHelp(self):
        print "SHOULD SHOW HELP"
        pass

    @eventloop.asIdle
    def copyChannelLink(self):
        app.ModelActionHandler(UIBackendDelegate()).copyCurrentFeedURL()
