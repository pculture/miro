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

"""miro.plat.frontends.widgets.browser -- Web Browser widget. """

from AppKit import *
from Foundation import *
import WebKit

from miro.plat.frontends.widgets.base import Widget

class Browser(Widget):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        Widget.__init__(self)
        self.url = None
        self.view = WebKit.WebView.alloc().init()

    def calc_size_request(self):
        return (200, 100) # Seems like a reasonable minimum size

    def navigate(self, url):
        self.url = NSURL.URLWithString_(url)
        request = NSURLRequest.requestWithURL_(self.url)
        self.view.mainFrame().loadRequest_(request)

    def get_current_url(self):
        if self.url:
            return self.url.absoluteURL()
        else:
            return None
