import app
from frontend import *

from ctypes import *
from ctypes.wintypes import *
import win32gui, win32api
from win32con import *
user32 = windll.user32

###############################################################################
#### Initialization code: window classes, invisible toplevel parent        ####
###############################################################################

# blankWindowClassAtom: no-op window class 
wc = win32gui.WNDCLASS()
wc.style = 0 
wc.lpfnWndProc = { }
wc.cbWndExtra = 0
wc.hInstance = win32api.GetModuleHandle(None)
wc.hIcon = win32gui.LoadIcon(0, IDI_APPLICATION)
wc.hCursor = win32gui.LoadCursor(0, IDC_ARROW)
wc.hbrBackground = win32gui.GetStockObject(WHITE_BRUSH)
#wc.lpszMenuName = None
wc.lpszClassName = "DTV Blank Window"
blankWindowClassAtom = win32gui.RegisterClass(wc)
del wc            

# invisibleDisplayParentHwnd: top-level window that is used as the parent
# of Displays that aren't selected in a visible window right now
invisibleDisplayParentHwnd = win32gui.CreateWindowEx(0, blankWindowClassAtom,
    "DTV Invisible Display Container", WS_OVERLAPPEDWINDOW, CW_USEDEFAULT,
    CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, 0, 0,
    win32api.GetModuleHandle(None), None)

import MozillaBrowser #NEEDS: test
import HTMLDisplay #NEEDS: test

###############################################################################
#### Main window                                                           ####
###############################################################################

# Strategy: for now, a hash from names to hwnds. We put one child in each
# to completely fill it. selectdisplay changes this child.
#
# For later, embedding a browser in a browser, and sending control
# commands to it. Yeah, that's the story. Either that or just overlay the
# subordinate browser windows on top and have explicit resize logic for
# them.
#
# May want to use binary element behaviors to grab, eg, current bounding
# box of a div, and use that to site the window.

# NEEDS: save/restore window position and size
class MainFrame:
    def __init__(self, appl):
        """The initially active display will be an instance of NullDisplay."""

        self.hInstance = win32api.GetModuleHandle(None)

        # Main window message routing table
        messageMap = {
	    WM_SIZE: self.onWMSize,
            WM_CLOSE: self.onWMClose,
        }

        # Create the main window window class
        # Needs to be here and not global because messageMap closes over self
        # NEEDS: make Unicode (?)
        wc = win32gui.WNDCLASS()
        wc.style = CS_HREDRAW | CS_VREDRAW
        wc.lpfnWndProc = messageMap
        wc.cbWndExtra = 0
        wc.hInstance = self.hInstance
        wc.hIcon = win32gui.LoadIcon(0, IDI_APPLICATION)
        wc.hCursor = win32gui.LoadCursor(0, IDC_ARROW)
        wc.hbrBackground = win32gui.GetStockObject(WHITE_BRUSH)
        #wc.lpszMenuName = None
        wc.lpszClassName = "DTV MainFrame %s" % id(self)
        self.mainWindowClassAtom = win32gui.RegisterClass(wc)

        # Symbols by other parts of the program as as arguments
        # to selectDisplay
        self.mainDisplay = "mainDisplay"
        self.channelsDisplay = "channelsDisplay"
        self.collectionDisplay = "collectionDisplay"
        #(videoInfoDisplay?)

        # Child display state
        self.selectedDisplays = {}
        self.areaHwnds = {}

        # Create top-level window
        windowTitle = "DTV"
        self.hwnd = win32gui.CreateWindowEx(0, self.mainWindowClassAtom,
            windowTitle, WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT,
            CW_USEDEFAULT, CW_USEDEFAULT, 0, 0, self.hInstance, None)

	# Create display areas
        self.areaHwnds[self.channelsDisplay] = win32gui.CreateWindowEx(0,
            blankWindowClassAtom, "", WS_CHILDWINDOW,
	    CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, 
            self.hwnd, 0, self.hInstance, None)
        self.areaHwnds[self.mainDisplay] = win32gui.CreateWindowEx(0,
            blankWindowClassAtom, "", WS_CHILDWINDOW,
	    CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, 
            self.hwnd, 0, self.hInstance, None)
        for hwnd in self.areaHwnds.values():
	    self.onWMSize(hwnd, None, 0, 0)
            win32gui.ShowWindow(hwnd, SW_SHOW)

        # Push the window to the screen
        user32.ShowWindow(self.hwnd, SW_SHOWDEFAULT)
        user32.UpdateWindow(self.hwnd)

    def onWMSize(self, hwnd, msg, wparam, lparam):
        # Size display areas based on a fixed, programmatic concept of
	# MainFrame layout. There is a 20 pixel border around the
	# window and between the display areas. The left area is 400
	# pixels wide. Both areas are as tall as the remaining space.
	outerBorder = 20
	innerBorder = 20
        (left, top, right, bottom) = win32gui.GetWindowRect(hwnd)
        (width, height) = (right-left, bottom-top)
	availableWidth = width - outerBorder*2 - innerBorder
	contentHeight = height - outerBorder*2
	channelsWidth = 250
	mainWidth = availableWidth - channelsWidth
	if mainWidth < 0:
	    mainWidth = 0

	channelsHwnd = self.channelsDisplay in self.areaHwnds and self.areaHwnds[self.channelsDisplay] or None
	mainHwnd = self.mainDisplay in self.areaHwnds and self.areaHwnds[self.mainDisplay] or None

	if channelsHwnd:
	    win32gui.MoveWindow(channelsHwnd, outerBorder, outerBorder,
				channelsWidth, contentHeight, False)
	if self.channelsDisplay in self.selectedDisplays:
	    d = self.selectedDisplays[self.channelsDisplay]
	    if d:
		win32gui.MoveWindow(d.getHwnd(), 0, 0,
				    channelsWidth, contentHeight, False)

	if mainHwnd:
	    win32gui.MoveWindow(mainHwnd,
				outerBorder + channelsWidth + innerBorder,
				outerBorder, mainWidth, contentHeight, False)
	if self.mainDisplay in self.selectedDisplays:
	    d = self.selectedDisplays[self.mainDisplay]
	    if d:
		win32gui.MoveWindow(d.getHwnd(), 0, 0,
				    mainWidth, contentHeight, False)

        user32.UpdateWindow(self.hwnd)

    def onWMClose(self, hwnd, msg, wparam, lparam):
        self.unlink()
        win32gui.PostQuitMessage(0)

    def selectDisplay(self, newDisplay, area):
        """Install the provided 'newDisplay' in the requested area"""
        print "selectDisplay %s (%s) in %s" % (newDisplay, newDisplay.getHwnd(), area)
        if not self.hwnd:
            print "Warning: selectDisplay ignored on destroyed MainFrame."
	    return

        oldDisplay = None # protect from GC at least until new window's in
        oldHwnd = None
        if self.selectedDisplays.has_key(area):
            oldDisplay = self.selectedDisplays[area]
            if oldDisplay:
                oldDisplay.onDeselected_private(self)
                oldDisplay.onDeselected(self)
                oldHwnd = oldDisplay.getHwnd()
        newHwnd = newDisplay.getHwnd()

        if newHwnd and self.areaHwnds.has_key(area):
            # If no such area, move it offscreen. Still treat it as
            # selected for the purpose of sending deselection messages --
            # just don't display it anywhere.
            areaHwnd = self.areaHwnds[area] or invisibleDisplayParentHwnd
            win32gui.ShowWindow(newHwnd, SW_HIDE)
            win32gui.SetParent(newHwnd, areaHwnd)
            (left, top, right, bottom) = win32gui.GetWindowRect(areaHwnd)
            # 'False' suppresses the paint message until we're ready.
            win32gui.MoveWindow(newHwnd, 0, 0, right-left, bottom-top, False)
            win32gui.BringWindowToTop(newHwnd)
            win32gui.ShowWindow(newHwnd, SW_SHOW)

        if oldHwnd and oldHwnd != newHwnd:
            win32gui.SetParent(oldHwnd, invisibleDisplayParentHwnd)

        self.selectedDisplays[area] = newDisplay
        newDisplay.onSelected_private(self)
        newDisplay.onSelected(self)

        # Get a redraw.
        user32.UpdateWindow(newHwnd)

    # Internal use: return an estimate of the size of a given display area
    # as a (width, height) pair, or None if no information's available.
    def getDisplaySizeHint(self, area):
        if not self.areaHwnds.has_key(area):
            return None
        hwnd = self.areaHwnds[area]
        (left, top, right, bottom) = win32gui.GetWindowRect(hwnd)
        return (right-left, bottom-top)

    def unlink(self):
        for area in self.areaHwnds:
            # Don't call selectDisplay for this. We don't want to
            # call the deselection hooks; they could lead to subsequent
            # calls to selectDisplay which could complicate things greatly.
            # This confuses Displays a little but the alternative is worse.
            # Effectively what we do here is simulate selectDisplay without
            # calling onDeselected.
            if self.selectedDisplays.has_key(area):
                display = self.selectedDisplays[area]
                if display:
                    hwnd = display.getHwnd()
                    if hwnd:
                        # Move the windows of the Displays that are in this
                        # MainFrame out of the way so that they are not
                        # destroyed with the MainFrame. That would confuse
                        # the Displays even more.
                        win32gui.SetParent(hwnd, invisibleDisplayParentHwnd)
            self.selectedDisplays[area] = None

        # Don't bother to destroy self.areaHwnds. They'll go down with the
        # window. But do clear them out out of the array so there's no
        # chance we're holding stale hwnd's (so, for example,
        # getDisplaySizeHint doesn't get confused.)
        self.areaHwnds = {}

        # Kill the window.
        if self.hwnd:
            win32gui.DestroyWindow(self.hwnd)
            self.hwnd = None

        # Leak window classes for now.

    def __del__(self):
        self.unlink()

###############################################################################
#### The no-op display (here's as good a place as any)                     ####
###############################################################################

class NullDisplay (app.Display):
    "A blank placeholder Display."

    def __init__(self):
        app.Display.__init__(self)
        self.hwnd = win32gui.CreateWindowEx(0, blankWindowClassAtom,
            "", WS_CHILDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT,
            CW_USEDEFAULT, invisibleDisplayParentHwnd, 0,
            win32api.GetModuleHandle(None), None)

    def getHwnd(self):
        return self.hwnd

    def unlink(self):
        if self.hwnd:
            print "NullDisplay unlink %s" % self.hwnd
            win32gui.DestroyWindow(self.hwnd)
        self.hwnd = None

    def __del__(self):
        self.unlink()

###############################################################################
###############################################################################
