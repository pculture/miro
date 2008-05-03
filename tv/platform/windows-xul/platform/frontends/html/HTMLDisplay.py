# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

import threading
import socket
import re
from miro import xhtmltools
import time
import errno
import os

from miro import app
from miro import config
from miro import download_utils
import tempfile
import os
from miro.plat.utils import makeURLSafe, getLongPathName, osFilenameToFilenameType
from miro import prefs
from miro.frontends.html.displaybase import Display
from miro.plat.frontends.html import urlcallbacks

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

def makeFileUrl(path):
    path = osFilenameToFilenameType(path.replace("\\", "/"))
    return "file:///" + makeURLSafe(path)

def compareFileUrls(url1, url2):
    if not url1.startswith("file://") or not url2.startswith("file://"):
        return False
    def normalize(url):
        path = download_utils.getFileURLPath(url)
        return os.path.normpath(getLongPathName(path))
    return normalize(url1) == normalize(url2)

class HTMLDisplay (Display):
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
            handle.write(self.initialHTML.encode('utf-8'))
        finally:
            handle.close()
        self.location = os.path.abspath(location)
        self.url = makeFileUrl(self.location)
        urlcallbacks.installCallback(self.url, self.onURLLoad)
        app.jsBridge.xulNavigateDisplay(self.area, self.url)

    def pageFinishCallback(self, url):
        # make sure that the page that finished was our page, if we install
        # enough HTMLDisplays in a short time, then the last HTMLDisplay can
        # get callbacks for the earlier loads.
        if url.startswith("file://") and compareFileUrls(url, self.url):
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
    def execJS(self, javascript):
        fullUrl = "javascript:%s" % javascript
        app.jsBridge.xulNavigateDisplay(self.area, fullUrl)

    @deferUntilLoad
    def navigateToFragment(self, fragment):
        fullUrl = "%s#%s" % (self.url, fragment)
        app.jsBridge.xulNavigateDisplay(self.area, fullUrl)

    @deferUntilLoad
    def addItemAtEnd(self, xml, id):
        app.jsBridge.xulAddElementAtEnd(self.area, xml, id)

    @deferUntilLoad
    def addItemBefore(self, xml, id):
        app.jsBridge.xulAddElementBefore(self.area, xml, id)
    
    @deferUntilLoad
    def removeItem(self, id):
        app.jsBridge.xulRemoveElement(self.area, id)
    
    @deferUntilLoad
    def removeItems(self, ids):
        for id in ids:
            app.jsBridge.xulRemoveElement(self.area, id)
    
    @deferUntilLoad
    def changeItem(self, *args):
        self._doChangeItem(*args)

    @deferUntilLoad
    def changeItems(self, listOfArgs):
        for args in listOfArgs:
            self._doChangeItem(*args)

    def _doChangeItem(self, id, xml, changeHint):
        if changeHint is None or changeHint.changedInnerHTML is not None:
            app.jsBridge.xulChangeElement(self.area, id, xml)
        else:
            for name, value in changeHint.changedAttributes.items():
                if value is not None:
                    app.jsBridge.xulChangeAttribute(self.area, id, name,
                            value)
                else:
                    app.jsBridge.xulRemoveAttribute(self.area, id, name)

    @deferUntilLoad
    def hideItem(self, id):
        app.jsBridge.xulHideElement(self.area, id)
        
    @deferUntilLoad
    def showItem(self, id):
        app.jsBridge.xulShowElement(self.area, id)

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
