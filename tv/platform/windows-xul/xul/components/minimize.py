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

from xpcom import components
from miro.plat.xulhelper import makeService
import ctypes
import logging
from ctypes.wintypes import DWORD, HWND, HANDLE, LPCWSTR, WPARAM, LPARAM, RECT, POINT
UINT = ctypes.c_uint
WCHAR = ctypes.c_wchar
INT = ctypes.c_int

WH_MOUSE_LL = 14
WH_MOUSE    = 7

WM_NULL = 0x0000
WM_USER = 0x0400
WM_TRAYICON = WM_USER+0x1EEF
WM_GETICON = 0x007F
WM_SETICON = 0x0080
WM_STYLECHANGED = 0x007D
WM_SIZE = 0x0005
WM_GETMINMAXINFO = 0x0024
WM_ACTIVATEAPP = 0x001C
WM_ACTIVATE = 0x0006
WM_INITMENUPOPUP = 0x0117
WM_MOUSEMOVE = 0x0200
WS_EX_APPWINDOW = 0x00040000L
WS_MAXIMIZE = 0x01000000L
SIZE_MAXIMIZED = 2
ICON_SMALL = 0
ICON_BIG   = 1

IMAGE_ICON = 1

LR_LOADFROMFILE = 0x0010

NIF_MESSAGE = 0x00000001
NIF_ICON    = 0x00000002
NIF_TIP     = 0x00000004

WM_LBUTTONDOWN                 = 0x0201
WM_LBUTTONUP                   = 0x0202
WM_LBUTTONDBLCLK               = 0x0203
WM_RBUTTONDOWN                 = 0x0204
WM_RBUTTONUP                   = 0x0205
WM_RBUTTONDBLCLK               = 0x0206
WM_MBUTTONDOWN                 = 0x0207
WM_MBUTTONUP                   = 0x0208
WM_MBUTTONDBLCLK               = 0x0209
WM_XBUTTONDOWN                 = 0x020B
WM_XBUTTONUP                   = 0x020C
WM_XBUTTONDBLCLK               = 0x020D

NIM_ADD     = 0
NIM_DELETE  = 2

IDI_APPLICATION = 32512
IDI_WINLOGO = 32517

ABM_GETTASKBARPOS = 5
ABM_GETSTATE      = 4

ABS_AUTOHIDE   = 1
ABE_LEFT       = 0
ABE_TOP        = 1
ABE_RIGHT      = 2
ABE_BOTTOM     = 3

IDANI_OPEN         = 1
IDANI_CAPTION      = 3

SW_HIDE = 0
SW_SHOWMINIMIZED = 2
SW_SHOW = 5
SW_RESTORE = 9

GWL_WNDPROC = -4

MONITOR_DEFAULTTONEAREST = 0x00000002

def LOWORD(dword): return dword & 0x0000ffff
def HIWORD(dword): return dword >> 16

WNDPROCTYPE = ctypes.WINFUNCTYPE(ctypes.c_int, HWND, UINT, WPARAM, LPARAM)
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_int, HWND, LPARAM)

from miro import config
from miro import prefs
from miro.plat import resources

class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_int32),
                ("Data2", ctypes.c_int16),
                ("Data3", ctypes.c_int16),
                ("Data4", ctypes.c_byte * 8),
                ]

class TIMEOUT(ctypes.Union):
    _fields_ = [("uTimeout", UINT),
                ("uVersion", UINT),
                ]

class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [("cbSize", DWORD),
                ("hWnd", HWND),
                ("uID", UINT),
                ("uFlags", UINT),
                ("uCallbackMessage", UINT),
                ("hIcon", HANDLE),
                ("szTip", WCHAR * 64),
                ("dwState", DWORD),
                ("dwStateMask", DWORD),
                ("szInfo", WCHAR * 256),
                ("timeout", TIMEOUT),
                ("szInfoTitle", WCHAR * 64),
                ("dwInfoFlags", DWORD),
                ("guidItem", GUID),
                ("hBalloonIcon", HANDLE),
                ]

class WNDCLASSEX(ctypes.Structure):
    _fields_ = [("cbSize", UINT),
                ("style", UINT),
                ("lpfnWndProc", WNDPROCTYPE),
                ("cbClsExtra", INT),
                ("cbWndExtra", INT),
                ("hInstance", HANDLE),
                ("hIcon", HANDLE),
                ("hCursor", HANDLE),
                ("hBrush", HANDLE),
                ("lpszMenuName", LPCWSTR),
                ("lpszClassName", LPCWSTR),
                ("hIconSm", HANDLE),
                ]
class APPBARDATA(ctypes.Structure):
    _fields_ = [("cbSize", DWORD),
                ("hWnd", HANDLE),
                ("uCallbackMessage", UINT),
                ("uEdge", UINT),
                ("rc", RECT),
                ("lParam", LPARAM)]

class STYLESTRUCT(ctypes.Structure):
    _fields_ = [("styleOld", DWORD),
                ("styleNew", DWORD)]

class MINMAXINFO(ctypes.Structure):
    _fields_ = [("ptReserved", POINT),
                ("ptMaxSize", POINT),
                ("ptMaxPosition", POINT),
                ("ptMinTrackSize", POINT),
                ("ptMaxTrackSize",POINT)]

class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
                ("length", UINT),
                ("flags", UINT),
                ("showCmd", UINT),
                ("ptMinPosition", POINT),
                ("ptMaxPosition", POINT),
                ("rcNormalPosition", RECT),
    ]

def getTaskbarEdge():
    appBarData = APPBARDATA(0,0,0,0,RECT(0,0,0,0),0)
    if (ctypes.windll.shell32.SHAppBarMessage(ABM_GETTASKBARPOS,ctypes.byref(appBarData)) != 0):
        return appBarData.uEdge
    else:
        return -1

def getTaskbarHeight():
    appBarData = APPBARDATA(0,0,0,0,RECT(0,0,0,0),0)
    if ((ctypes.windll.shell32.SHAppBarMessage(ABM_GETSTATE,ctypes.byref(appBarData)) & ABS_AUTOHIDE) != 0):
        return 1
    if (ctypes.windll.shell32.SHAppBarMessage(ABM_GETTASKBARPOS,ctypes.byref(appBarData)) != 0):
        if appBarData.uEdge in [ABE_LEFT, ABE_RIGHT]:
            return (appBarData.rc.right - appBarData.rc.left)
        else:
            return (appBarData.rc.bottom - appBarData.rc.top)
    else:
        return -1

# Returns true iff the Windows task bar is on the current monitor
def taskbarOnCurrentMonitor():
    if len(Minimize.oldWindowProcs) > 0:
        appBarData = APPBARDATA(0,0,0,0,RECT(0,0,0,0),0)
        if (ctypes.windll.shell32.SHAppBarMessage(ABM_GETTASKBARPOS,ctypes.byref(appBarData)) != 0):
            taskbarMonitor = ctypes.windll.user32.MonitorFromRect(ctypes.pointer(appBarData.rc), MONITOR_DEFAULTTONEAREST)
            appMonitor = ctypes.windll.user32.MonitorFromWindow (Minimize.oldWindowProcs.keys()[0], MONITOR_DEFAULTTONEAREST)
            return appMonitor == taskbarMonitor

    # Assume that if there's trouble, the task bar is on the current monitor
    return True

def PyWindProc(hWnd, uMsg, wParam, lParam):
    mousePos = ctypes.windll.user32.GetMessagePos()
    mouseX = LOWORD(mousePos)
    mouseY = HIWORD(mousePos)
    if uMsg == WM_TRAYICON:
        if lParam in [WM_LBUTTONUP, WM_MBUTTONUP]:
            Minimize.minimizers[hWnd].minimizeOrRestore()
        elif lParam == WM_RBUTTONUP:
            Minimize.minimizers[hWnd].showPopup(mouseX, mouseY)

    #components.classes['@mozilla.org/consoleservice;1'].getService(components.interfaces.nsIConsoleService).logStringMessage("PYWINPROC %d %d %d %d" % (hWnd, uMsg, wParam, lParam))
    return ctypes.windll.user32.CallWindowProcW(ctypes.windll.user32.DefWindowProcW,hWnd, uMsg, wParam, lParam)

def PyMainWindProc(hWnd, uMsg, wParam, lParam):
    if uMsg == WM_GETMINMAXINFO and len(Minimize.minimizers) > 0 and taskbarOnCurrentMonitor():
        info = ctypes.cast(lParam, ctypes.POINTER(MINMAXINFO)).contents
        edge = getTaskbarEdge()
        height = getTaskbarHeight()
        pybridge = makeService("@participatoryculture.org/dtv/pybridge;1",components.interfaces.pcfIDTVPyBridge,False)
        window = Minimize.minimizers[Minimize.minimizers.keys()[0]].window
        if edge == 3: # Taskbar is on the bottom
            info.ptMaxSize.x = window.screen.width
            info.ptMaxSize.y = window.screen.height - height
            info.ptMaxPosition.x = 0
            info.ptMaxPosition.y = 0
        elif edge == 2: # Taskbar is on the right
            info.ptMaxSize.x = window.screen.width - height
            info.ptMaxSize.y = window.screen.height
            info.ptMaxPosition.x = 0
            info.ptMaxPosition.y = 0
        elif edge == 1: # Taskbar is on top
            info.ptMaxSize.x = window.screen.width
            info.ptMaxSize.y = window.screen.height - height
            info.ptMaxPosition.x = 0
            info.ptMaxPosition.y = height
        elif edge == 0: # Taskbar is on the left
            info.ptMaxSize.x = window.screen.width - height
            info.ptMaxSize.y = window.screen.height
            info.ptMaxPosition.x = height
            info.ptMaxPosition.y = 0
            
    return ctypes.windll.user32.CallWindowProcW(Minimize.oldWindowProcs[hWnd],hWnd, uMsg, wParam, lParam)

WindProc = WNDPROCTYPE(PyWindProc)
MainWindProc = WNDPROCTYPE(PyMainWindProc)

class Minimize:
    _com_interfaces_ = [components.interfaces.pcfIDTVMinimize]
    _reg_clsid_ = "{C8F996EC-599E-4749-9A70-EE9B7662981F}"
    _reg_contractid_ = "@participatoryculture.org/dtv/minimize;1"
    _reg_desc_ = "Minimizize and restorizor windizows"

    minimizers = {}
    oldWindowProcs = {}

    def __init__(self):
	pass

    def initialize(self):
        self.iconinfo = None
        self.wclassName = ctypes.c_wchar_p(u"PCF:DTV:Minimize:MessageWindowClass")
        self.wname = ctypes.c_wchar_p(u"PCF:DTV:Minimize:MessageWindow")
        self._gethrefcomp = makeService("@participatoryculture.org/dtv/gethref;1",components.interfaces.pcfIDTVGetHREF, False)
        self.hInst = ctypes.windll.kernel32.GetModuleHandleW(0)
        self.wndClass = WNDCLASSEX(ctypes.sizeof(WNDCLASSEX),
                                   ctypes.c_uint(0x4200), # CS_NOCLOSE | CS_GLOBALCLASS
                                   WindProc,
                                   0,
                                   0,
                                   self.hInst,
                                   0,
                                   0,
                                   0,
                                   0,
                                   self.wclassName,
                                   0)
        ctypes.windll.user32.RegisterClassExW(ctypes.byref(self.wndClass))
        self.trayIconWindow = ctypes.windll.user32.CreateWindowExW(
            WS_EX_APPWINDOW,
            self.wclassName,
            self.wname,
            0x20000000L, #WS_MINIMIZE
            0x80000000, #CW_USEDEFAULT
            0x80000000, #CW_USEDEFAULT
            0x80000000, #CW_USEDEFAULT
            0x80000000, #CW_USEDEFAULT
            ctypes.windll.user32.GetDesktopWindow(),
            0,
            self.hInst,
            0)
        Minimize.minimizers[self.trayIconWindow] = self

        # By default, everything uses the XULRunner icon
        # Use the Miro icon instead
        self.iconloc = ctypes.c_wchar_p(resources.path("..\\Miro.ico"))
        self.hIcon = ctypes.windll.user32.LoadImageW(0, self.iconloc, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)

        self.minimized = []


    def updateIcon(self):
        if config.get(prefs.MINIMIZE_TO_TRAY):
            self.addTrayIcon()
        else:
            self.delTrayIcon()

    def __del__(self):
        del Minimize.minimizers[self.trayIconWindow]
        self.delTrayIcon()

    def registerMainWindowProc(self, win):
        self.window = win
        href = self.getHREFFromDOMWindow(win)
        Minimize.oldWindowProcs[href.value] = ctypes.windll.user32.SetWindowLongW(href,GWL_WNDPROC, MainWindProc)

    def contextMenuHack(self):
        """Hack to make context menus work, must be called BEFORE the menu is
        shown.
        """
        # Need to make the XUL window the foreground window.  See 
        # http://support.microsoft.com/kb/135788
        # If the msdn URL doesn't work, try searhing for Q135788
        ctypes.windll.user32.SetForegroundWindow(self.trayIconWindow)

    def contextMenuHack2(self):
        """Hack to make context menus work, must be called AFTER the menu is
        shown.
        """
        ctypes.windll.user32.PostMessageA(self.trayIconWindow, WM_NULL, 0, 0)

    def getHREFFromBaseWindow(self, win):
        return ctypes.c_int(self._gethrefcomp.getit(win))

    def getHREFFromDOMWindow(self,win):
        win = win.queryInterface(components.interfaces.nsIInterfaceRequestor)
        win = win.getInterface(components.interfaces.nsIWebNavigation)
        win = win.queryInterface(components.interfaces.nsIDocShellTreeItem)
        win = win.treeOwner
        win = win.queryInterface(components.interfaces.nsIInterfaceRequestor)
        win = win.getInterface(components.interfaces.nsIXULWindow)
        win = win.docShell
        win = win.queryInterface(components.interfaces.nsIDocShell)
        win = win.queryInterface(components.interfaces.nsIBaseWindow)
        return self.getHREFFromBaseWindow(win)

    def minimizeAll(self):
        self.minimized = []
        mediator = makeService("@mozilla.org/appshell/window-mediator;1",components.interfaces.nsIWindowMediator, False)
        winList = mediator.getEnumerator(None)
        while (winList.hasMoreElements()):
            win = winList.getNext()
            href = self.getHREFFromDOMWindow(win)
            self.minimized.append(href)
            self.minimize(href)

    def addTrayIcon(self):
        self.iconinfo = NOTIFYICONDATA(ctypes.sizeof(NOTIFYICONDATA),
                                  self.trayIconWindow,
                                  1,
                                  NIF_ICON | NIF_MESSAGE | NIF_TIP,
                                  WM_TRAYICON,
                                  self.hIcon,
                                  config.get(prefs.LONG_APP_NAME),
                                  0,
                                  0,
                                  config.get(prefs.LONG_APP_NAME)+" is AWESOME",
                                  TIMEOUT(0,0),
                                  config.get(prefs.LONG_APP_NAME)+" is COOL",
                                  0,
                                  GUID(0,0,0,(ctypes.c_byte*8)(0,0,0,0,0,0,0,0)),
                                  0
                                  )
        ctypes.windll.shell32.Shell_NotifyIconW(NIM_ADD,ctypes.byref(self.iconinfo))

    def delTrayIcon(self):
        if self.iconinfo:
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_DELETE,ctypes.byref(self.iconinfo))

    def getTrayRect(self):
        trayRect = RECT(0,0,0,0)

        # I don't think this ever actually works with modern windows,
        # but gAIM does this, so I'll do it to like the sheep I am -NN
        trayWindow = ctypes.windll.user32.FindWindowExW(0,0,"Shell_TrayWnd",0)
        if trayWindow != 0:
            trayNotifyWindow = ctypes.windll.user32.FindWindowEx(trayWindow,0,"TrayNotifyWnd",0)
            if trayNotifyWindow != 0:
                ctypes.windll.user32.GetWindowRect(trayNotifyWindow, ctypes.byref(trayRect))
                return trayRect

        # That hack didn't work, let's find the tray notify window the
        # by finding the task bar
        appBarData = APPBARDATA(0,0,0,0,RECT(0,0,0,0),0)
        if (ctypes.windll.shell32.SHAppBarMessage(ABM_GETTASKBARPOS,ctypes.byref(appBarData)) != 0):
            if appBarData.uEdge in [ABE_LEFT, ABE_RIGHT]:
                trayRect.top=appBarData.rc.bottom-100
                trayRect.bottom=appBarData.rc.bottom-16
                trayRect.left=appBarData.rc.left
                trayRect.right=appBarData.rc.right
            else: # ABE_TOP, ABE_BOTTOM
                trayRect.top=appBarData.rc.top
                trayRect.bottom=appBarData.rc.bottom
                trayRect.left=appBarData.rc.right-100
                trayRect.right=appBarData.rc.right-16
            return trayRect
        # Give up
        return None
    
    def showPopup(self, x, y):
        jsbridge = makeService("@participatoryculture.org/dtv/jsbridge;1",components.interfaces.pcfIDTVJSBridge, False)
        jsbridge.showPopup(x, y)

    def minimize(self, href):
        fromer = RECT(0,0,0,0)
        ctypes.windll.user32.GetWindowRect(href,ctypes.byref(fromer))
        to = self.getTrayRect()
        if to:
            ctypes.windll.user32.DrawAnimatedRects(href,IDANI_CAPTION,ctypes.byref(fromer),ctypes.byref(to))
        ctypes.windll.user32.ShowWindow(href, ctypes.c_int(SW_HIDE))

    def restore(self, href):
        placement = WINDOWPLACEMENT()
        rv = ctypes.windll.user32.GetWindowPlacement(href, 
                ctypes.byref(placement))
        if rv and placement.showCmd == SW_SHOWMINIMIZED:
            show_flag = SW_RESTORE
        else:
            show_flag = SW_SHOW
        ctypes.windll.user32.ShowWindow(href, ctypes.c_int(show_flag))
        ctypes.windll.user32.SetForegroundWindow(href)

        fromer = RECT(0,0,0,0)
        ctypes.windll.user32.GetWindowRect(href,ctypes.byref(fromer))
        to = self.getTrayRect()
        if to:
            ctypes.windll.user32.DrawAnimatedRects(href,IDANI_CAPTION,ctypes.byref(to),ctypes.byref(fromer))


    def minimizeOrRestore(self):
        pybridge = makeService("@participatoryculture.org/dtv/pybridge;1",components.interfaces.pcfIDTVPyBridge, False)
        if len(self.minimized) > 0:
            for href in self.minimized:
                self.restore(href)
            self.minimized = []
        else:
            self.minimizeAll()
            pybridge.pause()
        pybridge.updateTrayMenus()

    def isMinimized(self):
        for mini in Minimize.minimizers.values():
            if len(mini.minimized) > 0:
                return True
        return False
        

def configDidChange(key, value):
    if key is prefs.MINIMIZE_TO_TRAY.key:
        for mini in Minimize.minimizers:
            if value:
                Minimize.minimizers[mini].addTrayIcon()
            else:
                Minimize.minimizers[mini].delTrayIcon()

config.addChangeCallback(configDidChange)
