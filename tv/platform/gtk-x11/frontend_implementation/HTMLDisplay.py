import frontend
import app
import gobject
import gtk
import gtkmozembed
import tempfile
from xml.sax.saxutils import escape
from MozillaBrowser import MozillaBrowser
from frontend_implementation.gtk_queue import gtkMethod

import os
import re
import threading
import time

def quoteJS(x):
    x = re.compile("\\\\").sub("\\\\", x)  #       \ -> \\
    x = re.compile("\"").  sub("\\\"", x)  #       " -> \"
    x = re.compile("'").   sub("\\'", x)   #       ' -> \'
    x = re.compile("\n").  sub("\\\\n", x) # newline -> \n
    x = re.compile("\r").  sub("\\\\r", x) #      CR -> \r
    return x
        
###############################################################################
#### HTML display                                                          ####
###############################################################################

# Decorator to make using execAfterLoad easier
def deferUntilAfterLoad(func):
    def schedFunc(self, *args, **kwargs):
        self.execAfterLoad(lambda: func(self, *args, **kwargs))
    return schedFunc

class HTMLDisplay(app.Display):
    "Selectable Display that shows a HTML document."

    def __init__(self, html, existingView=None, frameHint=None, areaHint=None):
        """'html' is the initial contents of the display, as a string. If
        frameHint is provided, it is used to guess the initial size the HTML
        display will be rendered at, which might reduce flicker when the
        display is installed."""
        app.Display.__init__(self)

        self.initialLoadFinished = False
        self.execQueue = []

        (handle, location) = tempfile.mkstemp('.html')
        handle = os.fdopen(handle,"w")
        handle.write(html)
        handle.close()

        # Translate path into URL.
        parts = re.split(r'/', location)
        self.urlToLoad = "file:///" + '/'.join(parts)

        userAgent = "DTV/pre-release (http://participatoryculture.org/)"

        self.widgetDestroyed = False
        self.widget = None
        self._gtkInit()

    @gtkMethod
    def _gtkInit(self):
        self.mb = MozillaBrowser()
        self.widget = self.mb.getWidget()
        self.widget.connect("net-stop", self.loadFinished)
        self.widget.connect("destroy", self.onBrowserDestroy)
        self.mb.setURICallBack(self.onURLLoad)
        self.widget.load_url(self.urlToLoad)
        self.widget.show()

    def getEventCookie(self):
        return ''

    def getDTVPlatformName(self):
        return 'gtk-x11-MozillaBrowser'

    def getWidget(self):
        return self.widget

    def loadFinished(self, widget):
        if (not self.initialLoadFinished):
            # Execute any function calls we queued because the page load
            # hadn't completed
            for func in self.execQueue:
                func()
            self.execQueue = []
            self.initialLoadFinished = True

            try:
                self.onInitialLoadFinished()
            except:
                pass

    # Call func() once the document has finished loading. If the
    # document has already finished loading, call it right away. But
    # in either case, the call is executed on the main thread, by
    # queueing an event, since WebViews are not documented to be
    # thread-safe, and we have seen crashes.
    def execAfterLoad(self, func):
        if not self.initialLoadFinished:
            self.execQueue.append(func)
        else:
            func()

    def onSelected(self, *args):
        # Give focus whenever the display is installed. Probably the best
        # of several not especially attractive options.
        app.Display.onSelected(self, *args)

    def execJS(self, js):
        self.widget.load_url('javascript:%s' % js)
    execJS = deferUntilAfterLoad(execJS)

    # DOM hooks used by the dynamic template code
    @gtkMethod
    @deferUntilAfterLoad
    def addItemAtEnd(self, xml, id):
        if not self.widgetDestroyed:
            self.mb.addItemAtEnd(xml, id)

    @gtkMethod
    @deferUntilAfterLoad
    def addItemBefore(self, xml, id):
        if not self.widgetDestroyed:
            self.mb.addItemBefore(xml, id)
    
    @gtkMethod
    @deferUntilAfterLoad
    def removeItem(self, id):
        if not self.widgetDestroyed:
            self.mb.removeItem(id)
    
    @gtkMethod
    @deferUntilAfterLoad
    def changeItem(self, id, xml):
        if not self.widgetDestroyed:
            self.mb.changeItem(id, xml)

    @gtkMethod
    @deferUntilAfterLoad
    def hideItem(self, id):
        if not self.widgetDestroyed:
            self.mb.hideItem(id)
        
    @gtkMethod
    @deferUntilAfterLoad
    def showItem(self, id):
        if not self.widgetDestroyed:
            self.mb.showItem(id)

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

    def onBrowserDestroy(self, widget):
        self.widgetDestroyed = True

    def onDocumentLoadFinished(self):
        pass
        
    def unlink(self):
        pass

    def __del__(self):
        self.unlink()

    # NEEDS: right-click menu.
    # Protocol: if type(getContextClickMenu) == "function", call it and
    # pass the DOM node that was clicked on. That returns "URL|description"
    # with blank lines for separators. On a click, force navigation of that
    # frame to that URL, maybe by setting document.location.href.

###############################################################################
###############################################################################
