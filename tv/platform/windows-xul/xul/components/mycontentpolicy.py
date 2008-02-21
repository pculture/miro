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
import traceback
import sys

from miro import config
from miro import prefs
from miro.platform.frontends.html import urlcallbacks
from miro.platform.xulhelper import makeService

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

catman = makeService("@mozilla.org/categorymanager;1",components.interfaces.nsICategoryManager, False)
catman.addCategoryEntry("content-policy", "@participatoryculture.org/dtv/mycontentpolicy;1", "@participatoryculture.org/dtv/mycontentpolicy;1", True, True)
