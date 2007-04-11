import resources
from database import DDBObject
from template import fillStaticTemplate
from httpclient import grabURL
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

class ChannelGuide(DDBObject):
    def __init__(self, url=None):
        checkU(url)
        self.url = url
        DDBObject.__init__(self)

    def __str__(self):
        return "Channel Guide <%s>" % (self.url,)

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

    def getURL(self):
        if self.url is not None:
            return self.url
        else:
            return config.get(prefs.CHANNEL_GUIDE_URL)

    def getDefault(self):
        return self.url is None

    # For the tabs
    @returnsUnicode
    def getTitle(self):
        if self.getDefault():
            return _('Channel Guide')
        else:
            return self.getURL()

    @returnsUnicode
    def getIconURL(self):
        return resources.url("images/channelguide-icon-tablist.png")

def getGuideByURL(url):
    return views.guides.getItemWithIndex(indexes.guidesByURL, url)
