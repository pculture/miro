# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

import gtk
import gobject

from miro import app
# Most of our stuff comes from the portable code, except the video renderer
# and the browser.
from miro.frontends.widgets.gtk.widgetset import *
from miro.frontends.widgets.gtk.weakconnect import weak_connect

# We need to provide a Browser
from miro.plat.frontends.widgets import webkitbrowser

# Use the default font
ITEM_TITLE_FONT = None
ITEM_DESC_FONT  = None

class ScrolledBrowser(gtk.ScrolledWindow):
    def __init__(self):
        gtk.ScrolledWindow.__init__(self)
        self.browser = webkitbrowser.WebKitEmbed()
        # self.add_with_viewport(self.browser)
        self.add(self.browser)
        self.show_all()

class Browser(Widget):
    """Web browser widget.
    """
    def __init__(self):
        Widget.__init__(self)
        self.set_widget(ScrolledBrowser())
        self._browser = self._widget.browser

        self.wrapped_browser_connect('load-started', self.on_net_start)
        self.wrapped_browser_connect('load-finished', self.on_net_stop)
        self.wrapped_browser_connect(
            'mime-type-policy-decision-requested', self.on_mime_type)

        self.create_signal('net-start')
        self.create_signal('net-stop')

        # FIXME - handle new windows

    def wrapped_browser_connect(self, signal, method, *user_args):
        """Connect to a signal of the widget we're wrapping.

        We use a weak reference to ensures that we don't have circular
        references between the wrapped widget and the wrapper widget.
        """
        return weak_connect(self._browser, signal, method, *user_args)

    def on_net_start(self, view, frame):
        self.emit('net-start')

    def on_net_stop(self, view, frame):
        self.emit('net-stop')

    def on_mime_type(self, view, frame, request, mtype, policy_decision):
        uri = request.get_uri()
        if not self.should_load_url(uri, mtype):
            policy_decision.ignore()
            return True

    def get_current_url(self):
        return self._browser.get_property("uri")

    url = property(get_current_url)

    def get_current_title(self):
        return self._browser.get_frame().get_title()

    def forward(self):
        if self._browser.can_go_forward():
            self._browser.go_forward()

    def back(self):
        if self._browser.can_go_back():
            self._browser.go_back()

    def can_go_forward(self):
        return self._browser.can_go_forward()

    def can_go_back(self):
        return self._browser.can_go_back()

    def should_load_url(self, url, mimetype=None):
        """This gets overriden by frontends/widgets/browser.Browser."""
        return True

    def navigate(self, url):
        self._browser.get_frame().load_uri(url)

    def reload(self):
        self._browser.get_frame().load_uri(self.url)

    def stop(self):
        self._browser.stop_loading()
