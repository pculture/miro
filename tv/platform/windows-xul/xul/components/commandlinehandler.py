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

"""Miro Command Line Handler."""

from xpcom import components

from miro.platform.xulhelper import makeService, proxify

class DemocracyCLH:
    _com_interfaces_ = [components.interfaces.nsICommandLineHandler]
    _reg_clsid_ = "{951DF9BD-EED3-4571-8A87-A16BA157A6CD}"
    _reg_contractid_ = "@participatoryculture.org/dtv/commandlinehandler;1"
    _reg_desc_ = "Democracy Command line Handler"

    def __init__(self):
        pass

    def handle(self, commandLine):
        commandLine = proxify(commandLine,components.interfaces.nsICommandLine)
        args = [commandLine.getArgument(i) for i in range(commandLine.length)]
        if "--register-xul-only" in args:
            return

        chromeURL = "chrome://dtv/content/main.xul"
        windowName = "DemocracyPlayer"
        wwatch = makeService("@mozilla.org/embedcomp/window-watcher;1",components.interfaces.nsIWindowWatcher, False)
        pybridge = makeService("@participatoryculture.org/dtv/pybridge;1",
                        components.interfaces.pcfIDTVPyBridge, False)

        startupError = pybridge.getStartupError()
        if startupError:
            startupErrorURL = "chrome://dtv/content/startuperror.xul"
            wwatch.openWindow(None, startupErrorURL, "DemocracyPlayerError", 
                    "chrome,dialog=yes,all", None)
            return

        pybridge.createProxyObjects()
        pybridge.handleCommandLine(commandLine)

        existingWindow = wwatch.getWindowByName(windowName, None)
        if existingWindow is None:
            try:
                pybridge.deleteVLCCache()
            except:
                print "WARNING: error in deleteVLCCache()"
            if pybridge.getStartupTasksDone():
                wwatch.openWindow(None, chromeURL, windowName,
                        "chrome,resizable,dialog=no,all", None)
            else:
                jsbridge = makeService("@participatoryculture.org/dtv/jsbridge;1",components.interfaces.pcfIDTVJSBridge, False)
                jsbridge.performStartupTasks()
                return
        else:
            # If Democracy is already running and minimize, make the
            # tray icon disappear
            minimizer = makeService("@participatoryculture.org/dtv/minimize;1",components.interfaces.pcfIDTVMinimize, False)
            if minimizer.isMinimized():
                minimizer.minimizeOrRestore()

catman = makeService("@mozilla.org/categorymanager;1",components.interfaces.nsICategoryManager, False)
catman.addCategoryEntry("command-line-handler", "z-default",
        "@participatoryculture.org/dtv/commandlinehandler;1", True, True)
