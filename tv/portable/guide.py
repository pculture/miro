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

import resources
from database import DDBObject
from template import fillStaticTemplate
from httpclient import grabURL
from urlparse import urlparse
from xhtmltools import urlencode
from copy import copy
from util import returnsUnicode, unicodify, checkU
import re
import app
import config
import indexes
import menu
import prefs
import threading
import urllib
import eventloop
import views
import logging
from gtcache import gettext as _

HTMLPattern = re.compile("^.*(<head.*?>.*</body\s*>)", re.S)

def isPartOfGuide(url, guideURL):
    """Return if url is part of a channel guide where guideURL is the base URL
    for that guide.
    """
    guideHost = urlparse(guideURL)[1]
    urlHost = urlparse(url)[1]
    return urlHost.endswith(guideHost)

class ChannelGuide(DDBObject):
    def __init__(self, url=None):
        checkU(url)
        self.url = url
        self.title = None
        self.lastVisitedURL = None
        DDBObject.__init__(self)

    def onRestore(self):
        self.lastVisitedURL = None

    def __str__(self):
        return "Miro Guide <%s>" % (self.url,)

    def makeContextMenu(self, templateName, view):
        menuItems = [
            (lambda: app.delegate.copyTextToClipboard(self.getURL()),
                _('Copy URL to clipboard')),
        ]
        if not self.getDefault():
            i = (lambda: app.controller.removeGuide(self), _('Remove'))
            menuItems.append(i)
        return menu.makeMenu(menuItems)

    def remove(self):
        DDBObject.remove(self)

    def isPartOfGuide(self, url):
        return isPartOfGuide(url, self.getURL())

    def getURL(self):
        if self.url is not None:
            return self.url
        else:
            return config.get(prefs.CHANNEL_GUIDE_URL)

    def getLastVisitedURL(self):
        if self.lastVisitedURL is not None:
            return self.lastVisitedURL
        else:
            return self.getURL()

    def getDefault(self):
        return self.url is None

    # For the tabs
    @returnsUnicode
    def getTitle(self):
        if self.getDefault():
            return _('Miro Guide')
        elif self.title:
            return title
        else:
            return self.getURL()

    @returnsUnicode
    def getIconURL(self):
        return resources.url("images/channelguide-icon-tablist.png")

def getGuideByURL(url):
    return views.guides.getItemWithIndex(indexes.guidesByURL, url)
