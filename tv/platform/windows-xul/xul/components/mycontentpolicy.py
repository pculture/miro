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

from xpcom import components
from xulhelper import makeService
import traceback
import sys
import config
import prefs

from frontend_implementation import urlcallbacks

nsIContentPolicy = components.interfaces.nsIContentPolicy

class MyContentPolicy:
    _com_interfaces_ = [nsIContentPolicy]
    _reg_clsid_ = "{CFECB6A2-24AE-48f4-9A7A-87E62B972795}"
    _reg_contractid_ = "@participatoryculture.org/dtv/mycontentpolicy;1"
    _reg_desc_ = "Democracy content policy"

    def __init__(self):
        pass

    def shouldLoad(self, contentType, contentLocation, requestOrigin, context, mimeTypeGuess,  extra):
        rv = nsIContentPolicy.ACCEPT
        if (requestOrigin is not None and 
                contentType in (nsIContentPolicy.TYPE_DOCUMENT,
                    nsIContentPolicy.TYPE_SUBDOCUMENT)):
            url = contentLocation.spec
            referrer = requestOrigin.spec
            if not urlcallbacks.runCallback(referrer, url):
                rv = nsIContentPolicy.REJECT_REQUEST
        return rv

    def shouldProcess(self, contentType, contentLocation, requestOrigin, context, mimeType,  extra):
        return nsIContentPolicy.ACCEPT

catman = makeService("@mozilla.org/categorymanager;1",components.interfaces.nsICategoryManager)
catman.addCategoryEntry("content-policy", "@participatoryculture.org/dtv/mycontentpolicy;1", "@participatoryculture.org/dtv/mycontentpolicy;1", True, True)
