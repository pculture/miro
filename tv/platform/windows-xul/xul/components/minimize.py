from xpcom import components
import ctypes

class Minimize:
    _com_interfaces_ = [components.interfaces.pcfIDTVMinimize]
    _reg_clsid_ = "{C8F996EC-599E-4749-9A70-EE9B7662981F}"
    _reg_contractid_ = "@participatoryculture.org/dtv/minimize;1"
    _reg_desc_ = "Minimizize and restorizor windizows"

    def __init__(self):
        self.gethref = components.classes["@participatoryculture.org/dtv/gethref;1"].getService(components.interfaces.pcfIDTVGetHREF)
        #self.getHREF = gethref.getit

    def minimizeAll(self):
        mediator = components.classes["@mozilla.org/appshell/window-mediator;1"].getService(components.interfaces.nsIWindowMediator)
        winList = mediator.getEnumerator(None)
        while (winList.hasMoreElements()):
            win = winList.getNext()
            win = win.queryInterface(components.interfaces.nsIInterfaceRequestor)
            win = win.getInterface(components.interfaces.nsIWebNavigation)
            win = win.queryInterface(components.interfaces.nsIDocShellTreeItem)
            win = win.treeOwner
            win = win.queryInterface(components.interfaces.nsIInterfaceRequestor)
            win = win.getInterface(components.interfaces.nsIXULWindow)
            win = win.docShell
            win = win.queryInterface(components.interfaces.nsIDocShell)
            win = win.queryInterface(components.interfaces.nsIBaseWindow)
#             ctypes.windll.user32.ShowWindow(
#                 ctypes.c_int(self.gethref.getit(win)),
#                 ctypes.c_int(0)) # SW_HIDE
#             ctypes.windll.user32.ShowWindow(
#                 ctypes.c_int(self.gethref.getit(win)),
#                 ctypes.c_int(5)) # SW_SHOW

    def restoreAll(self):
        pass
