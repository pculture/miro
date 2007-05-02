import threading
import socket
import re
import xhtmltools
import time
import errno
import os

import app
import config
import tempfile
import os
import prefs
import frontend
from frontend_implementation import urlcallbacks

tempdir = os.path.join(tempfile.gettempdir(), config.get(prefs.SHORT_APP_NAME))

def getDTVAPICookie():
    return None
def getDTVAPIURL():
    return None

pageFinishCallbacks = {}
def runPageFinishCallback(area, url):
    try:
        callback = pageFinishCallbacks[area]
    except KeyError:
        return
    else:
        callback(url)

def deferUntilLoad(function):
    def wrapper(self, *args):
        if self.pageLoadFinised:
            function(self, *args)
        else:
            self.deferedCalls.append((function, args))
    return wrapper

def initTempDir():
    if os.path.exists(tempdir):
        # get rid of stale temp files
        for child in os.listdir(tempdir):
            try:
                os.unlink(os.path.join(tempdir, child))
            except:
                pass
    else:
        os.mkdir(tempdir)

class HTMLDisplay (app.Display):
    "Selectable Display that shows a HTML document."

    def __init__(self, html, existingView=None, frameHint=None, areaHint=None,
                 baseURL=None):
        self.initialHTML = html
        self.area = None
        self.pageLoadFinised = False
        self.deferedCalls = []
        self.location = None
        if baseURL == config.get(prefs.CHANNEL_GUIDE_URL):
            self.removeTempFile = False
        else:
            self.removeTempFile = True


    def setInitialHTML(self):
        if not os.path.exists(tempdir):
            os.mkdir(tempdir)
        handle, location = tempfile.mkstemp('.html', dir=tempdir)
        handle = os.fdopen(handle, "wt")
        try:
            handle.write(self.initialHTML)
        finally:
            handle.close()
        self.location = os.path.abspath(location)
        self.url = "file:///%s" % self.location.replace("\\", "/")
        urlcallbacks.installCallback(self.url, self.onURLLoad)
        frontend.jsBridge.xulNavigateDisplay(self.area, self.url)

    def pageFinishCallback(self, url):
        # make sure that the page that finished was our page, if we install
        # enough HTMLDisplays in a short time, then the last HTMLDisplay can
        # get callbacks for the earlier loads.
        if url == self.url:
            self.pageLoadFinised = True
            for function, args in self.deferedCalls:
                function(self, *args)
            if self.removeTempFile:
                try:
                    os.unlink(self.location)
                except:
                    pass

    def setArea(self, area):
        self.area = area
        self.pageLoadFinised = False
        pageFinishCallbacks[self.area] = self.pageFinishCallback
        self.setInitialHTML()

    def removedFromArea(self):
        try:
            del pageFinishCallbacks[self.area]
        except KeyError:
            pass
        self.area = None

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
    def removeItems(self, ids):
        for id in ids:
            frontend.jsBridge.xulRemoveElement(self.area, id)
    
    @deferUntilLoad
    def changeItem(self, *args):
        self._doChangeItem(*args)

    @deferUntilLoad
    def changeItems(self, listOfArgs):
        for args in listOfArgs:
            self._doChangeItem(*args)

    def _doChangeItem(self, id, xml, changeHint):
        if changeHint is None or changeHint.changedInnerHTML is not None:
            frontend.jsBridge.xulChangeElement(self.area, id, xml)
        else:
            for name, value in changeHint.changedAttributes.items():
                if value is not None:
                    frontend.jsBridge.xulChangeAttribute(self.area, id, name,
                            value)
                else:
                    frontend.jsBridge.xulRemoveAttribute(self.area, id, name)

    @deferUntilLoad
    def hideItem(self, id):
        frontend.jsBridge.xulHideElement(self.area, id)
        
    @deferUntilLoad
    def showItem(self, id):
        frontend.jsBridge.xulShowElement(self.area, id)

    def onDeselected(self, frame):
        pass

    def getEventCookie(self):
        return ''

    def getDTVPlatformName(self):
        return 'xul'

    def getBodyTagExtra(self):
        return ''

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
