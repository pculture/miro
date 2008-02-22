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

from miro.platform import resources
from miro.database import DDBObject
from miro.httpclient import grabURL
from urlparse import urlparse, urljoin
from miro.xhtmltools import urlencode
from copy import copy
from miro.util import returnsUnicode, unicodify, checkU
import re
from miro import app
from miro import config
from miro import indexes
from miro import prefs
import threading
import urllib
from miro import eventloop
from miro import views
import logging
from miro import httpclient
from miro.gtcache import gettext as _
from HTMLParser import HTMLParser,HTMLParseError
from miro import iconcache

HTMLPattern = re.compile("^.*(<head.*?>.*</body\s*>)", re.S)

def isPartOfGuide(url, guideURL, allowedURLs = None):
    """Return if url is part of a channel guide where guideURL is the base URL
    for that guide.
    """
    if guideURL == "*":
        return True
    elif guideURL.startswith('file://'):
        return False
    elif allowedURLs is None:
        guideHost = urlparse(guideURL)[1]
        urlHost = urlparse(url)[1]
        return urlHost.endswith(guideHost)
    else:
        if isPartOfGuide(url, guideURL):
            return True
        for altURL in allowedURLs:
            if isPartOfGuide(url, altURL):
                return True
        return False
class ChannelGuide(DDBObject):
    ICON_CACHE_SIZES = [
#        (20, 20),
    ]
    def __init__(self, url, allowedURLs = None):
        checkU(url)
        if allowedURLs is None:
            self.allowedURLs = []
        else:
            self.allowedURLs = allowedURLs
        self.url = url
        self.updated_url = url
        self.title = None
        self.lastVisitedURL = None
        self.iconCache = iconcache.IconCache(self, is_vital = True)
        self.favicon = None
        self.firstTime = True
        if url:
            self.historyLocation = 0
            self.history = [self.url]
        else:
            self.historyLocation = None
            self.history = []

        DDBObject.__init__(self)
        self.downloadGuide()

    def onRestore(self):
        self.lastVisitedURL = None
        self.historyLocation = None
        self.history = []
        if (self.iconCache == None):
            self.iconCache = iconcache.IconCache (self, is_vital = True)
        else:
            self.iconCache.dbItem = self
            self.iconCache.requestUpdate(True)
        if self.getDefault():
            self.allowedURLs = config.get(prefs.CHANNEL_GUIDE_ALLOWED_URLS).split()
            self.allowedURLs.append(config.get(prefs.CHANNEL_GUIDE_FIRST_TIME_URL))
        else:
            self.allowedURLs = []
        self.downloadGuide()


    def __str__(self):
        return "Miro Guide <%s>" % (self.url,)

    def remove(self):
        if self.iconCache is not None:
            self.iconCache.remove()
            self.iconCache = None
        DDBObject.remove(self)

    def isPartOfGuide(self, url):
        return isPartOfGuide(url, self.getURL(), self.allowedURLs)

    def getURL(self):
        return self.url

    def getFirstURL(self):
        if self.getDefault():
            return config.get(prefs.CHANNEL_GUIDE_FIRST_TIME_URL)
        else:
            return self.url

    def getLastVisitedURL(self):
        if self.lastVisitedURL is not None:
            logging.info("First URL is %s"%self.lastVisitedURL)
            return self.lastVisitedURL
        else:
            if self.firstTime:
                self.firstTime = False
                logging.info("First URL is %s"%self.getFirstURL())
                return self.getFirstURL()
            else:
                logging.info("First URL is %s"%self.getURL())
                return self.getURL()

    def getDefault(self):
        return self.url == config.get(prefs.CHANNEL_GUIDE_URL)

    # For the tabs
    @returnsUnicode
    def getTitle(self):
        if self.title:
            return self.title
        else:
            return self.getURL()

    def guideDownloaded(self, info):
        self.updated_url = unicode(info["updated-url"])
        try:
            parser = GuideHTMLParser(self.updated_url)
            parser.feed(info["body"])
            parser.close()
        except:
            pass
        else:
            self.title = unicode(parser.title)
            if parser.favicon is not None:
                self.favicon = unicode(parser.favicon)
            else:
                self.favicon = None
            self.extendHistory(self.updated_url)
            self.iconCache.requestUpdate(True)
            self.signalChange()

    def guideError (self, error):
        pass

    def downloadGuide(self):
        httpclient.grabURL(self.getURL(), self.guideDownloaded, self.guideError)

    @returnsUnicode
    def getIconURL(self):
        if self.iconCache.isValid():
            path = self.iconCache.getResizedFilename(20, 20)
            return resources.absoluteUrl(path)
        else:
            return resources.url("images/channelguide-icon-tablist.png")

    def getThumbnailURL(self):
        if self.favicon:
            return self.favicon
        else:
            if self.updated_url:
                parsed = urlparse(self.updated_url)
            else:
                parsed = urlparse(self.getURL())
            return parsed[0] + u"://" + parsed[1] + u"/favicon.ico"

    def extendHistory(self, url):
        if self.historyLocation is None:
            self.historyLocation = 0
            self.history = [url]
        else:
            if self.history[self.historyLocation] == url: # moved backwards
                return
            if self.historyLocation != len(self.history) - 1:
                self.history = self.history[:self.historyLocation+1]
            self.history.append(url)
            self.historyLocation += 1


    def getHistoryURL(self, direction):
        if direction is not None:
            location = self.historyLocation + direction
            if location < 0:
                return
            elif location >= len(self.history):
                return
        else:
            location = 0 # go home
        self.historyLocation = location
        return self.history[self.historyLocation]

# Grabs the feed link from the given webpage
class GuideHTMLParser(HTMLParser):
    def __init__(self, url):
        self.title = None
        self.in_title = False
        self.baseurl = url
        self.favicon = None
        HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        attrdict = {}
        for (key, value) in attrs:
            attrdict[key] = value
        if tag == 'title' and self.title == None:
            self.in_title = True
            self.title = u""
        if (tag == 'link' and attrdict.has_key('rel') and
            attrdict.has_key('type') and attrdict.has_key('href') and
            'icon' in attrdict['rel'].split(' ') and
            attrdict['type'].startswith("image/")):

            self.favicon = urljoin(self.baseurl,attrdict['href']).decode('ascii', 'ignore')

    def handle_data(self, data):
        if self.in_title:
            self.title += data

    def handle_endtag(self, tag):
        if tag == 'title' and self.in_title:
            self.in_title = False

def getGuideByURL(url):
    return views.guides.getItemWithIndex(indexes.guidesByURL, url)
