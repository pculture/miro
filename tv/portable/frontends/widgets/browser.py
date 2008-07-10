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

"""browser.py -- portable browser code.  It checks if incomming URLs to see
what to do with them.
"""

import logging

from miro import guide
from miro import messages
from miro import subscription
from miro import util
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import linkhandler

class Browser(widgetset.Browser):
    def __init__(self, guide_info):
        widgetset.Browser.__init__(self)
        self.guide_info = guide_info
        self.navigate(guide_info.url)

    def should_load_url(self, url):
        logging.info ("got %s", url)
        # FIXME, this seems really weird.  How are we supposed to pick an
        # encoding?
        url = util.toUni(url)
        if subscription.isSubscribeLink(url):
            messages.SubscriptionLinkClicked(url).send_to_backend()
            return False
        if (not guide.isPartOfGuide(url, self.guide_info.url,
            self.guide_info.allowed_urls) and (url.startswith(u'http://')
                or url.startswith(u'https://') or
                url.startswith(u'ftp://') or url.startswith(u'mailto:') or
                url.startswith(u'feed://'))):
            linkhandler.handle_external_url(url)
            return False
        return True
