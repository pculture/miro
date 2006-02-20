import resource
import MozillaBrowser
import sys

import win32gui, win32api
from win32con import *
from ctypes import *
from ctypes.wintypes import *
user32 = windll.user32

###############################################################################
## Callbacks                                                                 ##
###############################################################################

theControl = None
theHwnd = None

def onClose(hwnd, msg, wparam, lparam):
    win32gui.PostQuitMessage(0)

def onSize(hwnd, msg, wparam, lparam):
    theControl and theControl.recomputeSize()

def onActivate(hwnd, msg, wparam, lparam):
    if theControl:
        if wparam == WA_ACTIVE or wparam == WA_CLICKACTIVE:
           theControl.activate()
        if wparam == WA_INACTIVE:
           theControl.deactivate()

messageMap = { WM_CLOSE: onClose,
               WM_SIZE: onSize,
               WM_ERASEBKGND: lambda *args: 1, # flicker reduction
               WM_ACTIVATE: onActivate,
}

def onActionCallback(url):
    print "Python got action: %s" % url

def onDocumentLoadFinishedCallback():
    print "Python notes that the document load has finished."

def getNewElementMarkup():
    return "<p>new element</p>"

def onLoadCallback(url):
    print "onLoad for %s (control is %s)" % (url, theControl)
    if not theControl:
	return True

    if url == "test:remove":
	theControl.removeElement('victim') 
    if url == "test:before_victim":
	theControl.addElementBefore(getNewElementMarkup(), 'victim') 
    if url == "test:before_bottom":
	theControl.addElementBefore(getNewElementMarkup(), 'bottom') 
    if url == "test:after":
	theControl.addElementAtEnd(getNewElementMarkup(), 'arena') 
    if url == "test:change":
	newMarkup = "<div id=\"victim\"><p>I am the mticiv!</p></div>"
	theControl.changeElement('victim', newMarkup)
    if url == "test:hide":
	theControl.hideElement('victim') 
    if url == "test:show":
	theControl.showElement('victim') 
    return False

###############################################################################
## Control creation                                                          ##
###############################################################################

def createBrowser():
    hInstance = win32api.GetModuleHandle(None)

    wc = win32gui.WNDCLASS()
    wc.style = CS_HREDRAW | CS_VREDRAW
    wc.lpfnWndProc = messageMap
    wc.cbWndExtra = 0
    wc.hInstance = hInstance
    wc.hIcon = win32gui.LoadIcon(0, IDI_APPLICATION)
    wc.hCursor = win32gui.LoadCursor(0, IDC_ARROW)
    wc.hbrBackground = win32gui.GetStockObject(WHITE_BRUSH)
    #wc.lpszMenuName = None
    wc.lpszClassName = "Test frame"
    mainWindowClassAtom = win32gui.RegisterClass(wc)

    globals()['theHwnd'] = \
	win32gui.CreateWindowEx(0, mainWindowClassAtom,
				"DOM test", WS_OVERLAPPEDWINDOW,
				CW_USEDEFAULT, CW_USEDEFAULT,
				CW_USEDEFAULT, CW_USEDEFAULT,
				0, 0, hInstance, None)
    user32.ShowWindow(theHwnd, SW_SHOWDEFAULT)
    user32.UpdateWindow(theHwnd)

    globals()['theControl'] = MozillaBrowser. \
    MozillaBrowser(theHwnd,
		   initialURL = resource.url('templates/test/domtest.html'),
		   onLoadCallback = onLoadCallback,
		   onActionCallback = onActionCallback,
		   onDocumentLoadFinishedCallback = onDocumentLoadFinishedCallback,
		   )
    theControl.activate()

    return (theControl, theHwnd)

###############################################################################
## Main loop                                                                 ##
###############################################################################

def main():
    (browserRef, hwnd) = createBrowser()

    msg = MSG()
    returnCode = 0
    while True:
	returnCode = user32.GetMessageA(byref(msg), None, 0, 0)
	if not returnCode:
	    break
	user32.TranslateMessage(byref(msg))
	user32.DispatchMessageA(byref(msg))

    sys.exit(returnCode)

###############################################################################
###############################################################################
