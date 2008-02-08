# Miro - an RSS based video player application
# Copyright (C) 2008 Participatory Culture Foundation
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

from xpcom import components
from miro.platform import pyxpcomcalls

class PyCallback:
    _com_interfaces_ = [components.interfaces.pcfIDTVPyCallback]
    _reg_clsid_ = "{A9F5D7BE-DE38-4D4C-BD5D-30023CE5AD45}"
    _reg_contractid_ = "@participatoryculture.org/dtv/pycallback;1"
    _reg_desc_ = "callback"

    def setCallbackId(callbackID):
        self.callbackID = callbackID
    def makeCallbackFloat(val):
        pyxpcomcalls.makeCallback(self.callbackID, val)
    def makeCallbackInt(val):
        pyxpcomcalls.makeCallback(self.callbackID, val)
    def makeCallbackString(val):
        pyxpcomcalls.makeCallback(self.callbackID, val)
