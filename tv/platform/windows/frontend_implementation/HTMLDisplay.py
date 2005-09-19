import frontend
import app
import WebBrowser

from frontend_implementation.MainFrame import blankWindowClassAtom
from frontend_implementation.MainFrame import invisibleDisplayParentHwnd

import win32gui, win32api
from win32con import *
from ctypes import *
from ctypes.wintypes import *

###############################################################################
#### HTML display                                                          ####
###############################################################################

class HTMLDisplay (app.Display):
    "Selectable Display that shows a HTML document."

    def __init__(self, html, existingView=None, frameHint=None, areaHint=None):
        """'html' is the initial contents of the display, as a string. If
        frameHint is provided, it is used to guess the initial size the HTML
        display will be rendered at, which might reduce flicker when the
        display is installed."""
        app.Display.__init__(self)

        # Create a dummy child window
        self.hwnd = win32gui.CreateWindowEx(0, blankWindowClassAtom,
            "", WS_CHILDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT,
            CW_USEDEFAULT, invisibleDisplayParentHwnd, 0,
            win32api.GetModuleHandle(None), None)

        # If we have size information available, use it. It will be the
        # tuple (width, height).
        displaySizeHint = frameHint and areaHint and frameHint.getDisplaySizeHint(areaHint) or None
        if displaySizeHint:
            win32gui.MoveWindow(self.hwnd, 0, 0, 
                displaySizeHint[0], displaySizeHint[1], False)

        # NEEDS: debugging; save HTML to disk
        import tempfile
        import os
        (handle, location) = tempfile.mkstemp('.html')
        handle = os.fdopen(handle,"w")
        handle.write(html)
        handle.close()
        print "Logged HTML to %s" % location
	
	# Use C++ extension to instantiate IE as an ActiveX control and
	# host it in the window just created
	# NEEDS: move user agent string to central location
        userAgent = "DTV/pre-release (http://participatoryculture.org/)"
#	html = "Hello from Python!" # NEEDS
	self.wb = WebBrowser.WebBrowser(hwnd = self.hwnd,
                                        initialHTML = html,
                                        onLoadCallback = self.rawOnLoad,
                                        userAgent = userAgent)

    def getHwnd(self):
        return self.hwnd

    def execJS(self, js):
        # NEEDS: threading??? queueing???
        # Go ahead and queue on main thread, through message. You'll be glad.
        #print "Punted JS" #NEEDS
        #self.browser.document.parentWindow.execScript(js, "javascript")
	self.wb.execJS(js)

    # DOM hooks used by the dynamic template code
    # NEEDS (go back to OS X code, for starters)
    def addItemAtEnd(self, xml, id):
        pass
    def addItemBefore(self, xml, id):
        pass
    def removeItem(self, id):
        pass
    def changeItem(self, id, xml):
        pass
    def hideItem(self, id):
        pass
    def showItem(self, id):
        pass

    def rawOnLoad(self, *args):
        print "Got load event in Python, args: %s" % (args, )
        # NEEDS: decode args, call onURLLoad, return False to cancel load
	# (just return value of self.onURLLoad)

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
        self.wb = None
        if self.hwnd:
            print "HTMLDisplay unlink %s" % self.hwnd
            win32gui.DestroyWindow(self.hwnd)
        self.hwnd = None

    def __del__(self):
        self.unlink()

    # NEEDS: right-click menu.
    # Protocol: if type(getContextClickMenu) == "function", call it and
    # pass the DOM node that was clicked on. That returns "URL|description"
    # with blank lines for separators. On a click, force navigation of that
    # frame to that URL, maybe by setting document.location.href.

###############################################################################
###############################################################################
