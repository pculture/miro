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

import gtkmozembed
import gtk

# Most of our stuff comes from the portable code, except the video renderer
# and the browser.
from miro.frontends.widgets.gtk.widgetset import *

# We need to provide a Browser
from miro.plat.frontends.widgets import mozprompt
xpcom_setup = False


class Browser(Widget):
    """Web browser widget.  """

    def __init__(self):
        Widget.__init__(self)
        self.set_widget(gtkmozembed.MozEmbed())
        self.url = None
        self.wrapped_widget_connect('open-uri', self.on_open_uri)
        self.wrapped_widget_connect('realize', self.on_realize)
        self._widget.set_size_request(200, 100)
        # Seems like a reasonable min-size

    def on_open_uri(self, browser, uri):
        if self.should_load_url(uri):
            self.url = uri
            return False
        else:
            return True

    def forward(self):
        if self._widget.can_go_forward():
            self._widget.go_forward()

    def back(self):
        if self._widget.can_go_back():
            self._widget.go_back()

    def should_load_url(self, url):
        return True

    def navigate(self, url):
        self._widget.load_url(url)

    def on_realize(self, widget):
        if not xpcom_setup:
            do_xpcom_setup()

    def reload(self):
        self._widget.load_url(self.url)

    def stop(self):
        self._widget.stop_load()


def do_xpcom_setup():
    global xpcom_setup

    mozprompt.stop_prompts()
    xpcom_setup = True
