import threading
import socket
import re
import xhtmltools
import time
import errno
import os

import app
import tempfile
import os

import frontend
from frontend_implementation import urlcallbacks

def getDTVAPICookie():
    return None
def getDTVAPIURL():
    return None

pageFinishCallbacks = {}
def runPageFinishCallback(area):
    try:
        callback = pageFinishCallbacks[area]
    except KeyError:
        return
    else:
        callback()

def deferUntilLoad(function):
    def wrapper(self, *args):
        if self.pageLoadFinised:
            function(self, *args)
        else:
            self.deferedCalls.append((function, args))
    return wrapper


class HTMLDisplay (app.Display):
    "Selectable Display that shows a HTML document."

    def __init__(self, html, existingView=None, frameHint=None, areaHint=None,
                 baseURL=None):
        self.initialHTML = html
        self.area = None
        self.pageLoadFinised = False
        self.deferedCalls = []
        self.location = None

    def setInitialHTML(self):
        handle, location = tempfile.mkstemp('.html')
        handle = os.fdopen(handle, "wt")
        try:
            handle.write(self.initialHTML)
        finally:
            handle.close()
        self.location = os.path.abspath(location)
        url = "file:///%s" % self.location.replace("\\", "/")
        urlcallbacks.installCallback(url, self.onURLLoad)
        frontend.jsBridge.xulNavigateDisplay(self.area, url)

    def pageFinishCallback(self):
        self.pageLoadFinised = True
        for function, args in self.deferedCalls:
            function(self, *args)

    def setArea(self, area):
        self.area = area
        self.pageLoadFinised = False
        pageFinishCallbacks[self.area] = self.pageFinishCallback
        self.setInitialHTML()

    @deferUntilLoad
    def addItemAtEnd(self, xml, id):
        frontend.jsBridge.xulAddElementAtEnd(self.area, xml, id)

    @deferUntilLoad
    def addItemBefore(self, xml, id):
        frontend.jsBridge.xulAddElementBefore(self.area, xml, id)
    
    @deferUntilLoad
    def removeItem(self, id):
        frontend.jsBridge.xulRemoveElement(self.area, id)
    
    @deferUntilLoad
    def changeItem(self, id, xml):
        frontend.jsBridge.xulChangeElement(self.area, id, xml)

    @deferUntilLoad
    def hideItem(self, id):
        frontend.jsBridge.xulHideElement(self.area, id)
        
    @deferUntilLoad
    def showItem(self, id):
        frontend.jsBridge.xulShowElement(self.area, id)

    def onDeselected(self, frame):
        self.area = None
        try:
            del pageFinishCallbacks[self.area]
        except KeyError:
            pass

    def getEventCookie(self):
        return ''

    def getDTVPlatformName(self):
        return 'xul'

    def onURLLoad(self, url):
        """Called when this HTML browser attempts to load a URL (either
        through user action or Javascript.) The URL is provided as a
        string. Return true to allow the URL to load, or false to cancel
        the load (for example, because it was a magic URL that marks
        an item to be downloaded.) Implementation in HTMLDisplay always
        returns true; override in a subclass to implement special
        behavior."""
        # For overriding
        return True

    def unlink(self):
        try:
            urlcallbacks.removeCallback(self.location)
        except KeyError:
            pass

    def __del__(self):
        self.unlink()
