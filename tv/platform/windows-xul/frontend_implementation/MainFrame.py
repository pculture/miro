# Miro - an RSS based video player application
# Copyright (C) 2005-2007 Participatory Culture Foundation
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

import app
import frontend
import os
from xpcom import components
from util import quoteJS
from frontend_implementation.VideoDisplay import VideoDisplay
from frontend_implementation import urlcallbacks

###############################################################################
#### Main window                                                           ####
###############################################################################

class MainFrame:
    def __init__(self, appl):
        # Symbols by other parts of the program as arguments
        # to selectDisplay
        self.mainDisplay = "mainDisplay"
        self.channelsDisplay = "channelsDisplay"
        self.videoInfoDisplay = "videoInfoDisplay"

        # Displays selected in each area, for generating deselection
        # messages.
        self.selectedDisplays = {}
        urlcallbacks.installMainDisplayCallback(self.mainDisplayCallback)

    def onSelectedTabChange(self, states, actionGroups, guideURL,
            videoFilename):
        app.controller.setGuideURL(guideURL)
        if videoFilename is not None:
            frontend.jsBridge.updateVideoFilename(os.path.basename(videoFilename))
        else:
            frontend.jsBridge.updateVideoFilename('')
        frontend.currentVideoPath = videoFilename
        for group, enabled in actionGroups.items():
            frontend.jsBridge.setActionGroupEnabled(group, enabled)

        # Convert this into something JavaScript can see
        array_cls = components.classes["@mozilla.org/supports-array;1"]
        variant_cls = components.classes["@mozilla.org/variant;1"]
        stateLists = array_cls.createInstance()
        stateLists = stateLists.queryInterface(components.interfaces.nsICollection)
        for key, actions in states.items():
            newactions = array_cls.createInstance()
            newactions = newactions.queryInterface(components.interfaces.nsICollection)
            for action in actions:
                newaction = variant_cls.createInstance()
                newaction = newaction.queryInterface(components.interfaces.nsIWritableVariant)
                newaction.setAsAString(action)
                newactions.AppendElement(newaction)
            newlist = array_cls.createInstance()
            newlist = newlist.queryInterface(components.interfaces.nsICollection)
            newkey = variant_cls.createInstance()
            newkey = newkey.queryInterface(components.interfaces.nsIWritableVariant)
            newkey.setAsAString(key)
            newlist.AppendElement(newkey)
            newactions = newactions.queryInterface(components.interfaces.nsISupportsArray)
            newlist.AppendElement(newactions)
            stateLists.AppendElement(newlist)

        stateLists.queryInterface(components.interfaces.nsISupportsArray)
        frontend.jsBridge.updateMenus(stateLists)
        
    def selectDisplay(self, newDisplay, area):
        """Install the provided 'newDisplay' in the requested area"""

        # Generate a deselection message for the previously selected
        # display in this area, if any
        if area in self.selectedDisplays:
            oldDisplay = self.selectedDisplays[area]
            if oldDisplay:
                oldDisplay.onDeselected_private(self)
                oldDisplay.onDeselected(self)
                oldDisplay.removedFromArea()

        # Generate a selection message for the new display, if any
        self.selectedDisplays[area] = newDisplay
        if newDisplay:
            newDisplay.onSelected_private(self)
            newDisplay.onSelected(self)
            newDisplay.setArea(area)
        if area == self.mainDisplay:
            if isinstance(newDisplay, VideoDisplay):
                frontend.jsBridge.showVideoDisplay()
            else:
                frontend.jsBridge.hideVideoDisplay()
                frontend.jsBridge.leaveFullscreen()

    def mainDisplayCallback(self, url):
        try:
            display = self.selectedDisplays[self.mainDisplay]
            if hasattr (display, "onURLLoad"):
                return self.selectedDisplays[self.mainDisplay].onURLLoad(url)
            else:
                return True
        except KeyError:
            return True

    def getDisplay(self, area):
        return self.selectedDisplays.get(area)

    # Internal use: return an estimate of the size of a given display area
    # as a (width, height) pair, or None if no information's available.
    def getDisplaySizeHint(self, area):
        return None

    def unlink(self):
        pass

    def __del__(self):
        self.unlink()

###############################################################################
###############################################################################
