import frontend
import app

from frontend_implementation.MainFrame import blankWindowClassAtom
from frontend_implementation.MainFrame import invisibleDisplayParentHwnd

import win32gui, win32api
from win32con import *
from ctypes import *
from ctypes.com import *
from ctypes.com.automation import IDispatch
from ctypes.com.automation import VARIANT
from ctypes.com.connectionpoints import dispinterface_EventReceiver
import ctypes.com.client
from ctypes.wintypes import *
import frontend_implementation.shdocvw_gen as shdocvw_gen
import frontend_implementation.mshtml_gen as mshtml_gen
atl = windll.atl

# Declare an extra function we need
atl.AtlAxCreateControlEx.argtypes = [ c_wchar_p, c_int, POINTER(IUnknown), POINTER(POINTER(IUnknown)), POINTER(POINTER(IUnknown)), POINTER(GUID), POINTER(IUnknown) ]
atl.AtlAxCreateControlEx.restypes = HRESULT

###############################################################################
#### HTML display                                                          ####
###############################################################################

class EventListener(dispinterface_EventReceiver):
    _com_interfaces_ = [shdocvw_gen.DWebBrowserEvents2]

    def __init__(self, parent):
        dispinterface_EventReceiver.__init__(self) # very important!
        self.parent = parent

    def BeforeNavigate2(self, this, pDisp, URL, Flags, TargetFrameName,
        PostData, Headers, Cancel):
        print "BeforeNavigate2: %s" % URL
        if self.parent.onURLLoad(URL):
            print "--> continue"
            return
        else:
            print "--> cancel"
            Cancel.value = True
            return

    def DocumentComplete(self, this, pDisp, URL):
        # Potentially problematic -- fires for each frame if more than one.
        print "DocumentComplete: %s" % URL

class HTMLDisplay (app.Display, dispinterface_EventReceiver):
    "Selectable Display that shows a HTML document."
    _com_interfaces_ = [shdocvw_gen.DWebBrowserEvents2]

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

        # Instantiate IE as an ActiveX control; tell ATL to take over
        # management of the window just created and use it to host the IE
        # control
        containerUnknown = POINTER(IUnknown)()
        controlUnknown = POINTER(IUnknown)()
        # Using 'about:' instead of the usual 'mshtml:' causes us to get a
        # browser object (WebBrowser) instead of just a document object
        # (MSHTML). This gives us the machinery to follow links, etc.
#        hr = atl.AtlAxCreateControlEx("about:" + html, self.hwnd, None,
        hr = atl.AtlAxCreateControlEx("about:blank", self.hwnd, None,
            byref(containerUnknown), byref(controlUnknown), byref(GUID()),
            None)

        # Get the dispatch interface for the control we just created.
        controlDispatch = POINTER(IDispatch)()
        controlUnknown.QueryInterface(byref(IDispatch._iid_),
            byref(controlDispatch))
        # When I can't win, I cheat.
        wrappedDispatch = ctypes.com.client._Dispatch(controlDispatch)
        self.browser = wrappedDispatch
        self.browserRaw = controlDispatch

        # Set ourself up to receive events
        # We need to pass in the actual POINTER(IDispatch), not the
        # wrapped version we made for automatic Python bridging.
        self.eventListener = EventListener(self)
        self.eventRegistrationHandle = self.eventListener.connect(self.browserRaw)

        # NEEDS: set user agent: "DTV/pre-release (http://participatoryculture.org/)"
        self.browser.Document.clear()
        try:
            self.browser.Document.write(html)
        except:
            "initial load failed"
            import traceback
            traceback.print_exc()
        print "continuing"
        self.browser.Document.close()

    def getHwnd(self):
        return self.hwnd

    def execJS(self, js):
        # NEEDS: threading??? queueing???
        # Go ahead and queue on main thread, through message. You'll be glad.
        print "Punted JS" #NEEDS
        #self.browser.document.parentWindow.execScript(js, "javascript")

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
        self.disconnect(self.eventHandle)
        self.eventListener = None
        self.eventRegistrationHandle = None
        self.browser = None
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
