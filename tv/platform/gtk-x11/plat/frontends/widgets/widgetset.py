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
import gobject

from miro import app
# Most of our stuff comes from the portable code, except the video renderer
# and the browser.
from miro.frontends.widgets.gtk.widgetset import *

# We need to provide a Browser
from miro.plat.frontends.widgets import mozprompt
from miro.plat.frontends.widgets import httpobserver
from miro.plat.frontends.widgets import windowcreator
from miro.plat.frontends.widgets import pluginsdir
xpcom_setup = False

# Use the default font
ITEM_TITLE_FONT = None
ITEM_DESC_FONT  = None

class MiroMozEmbed(gtkmozembed.MozEmbed):
    def do_destroy(self):
        # For some reason this hangs everything (#10700), so we just ignore it
        # instead.  This probably will cause a memory leak if we create and
        # destroy browser often, but we only destroy a browser on shutdown and
        # if a site is deleted, which is not too often.
        pass

gobject.type_register(MiroMozEmbed)

class Browser(Widget):
    """Web browser widget.  """

    def __init__(self):
        Widget.__init__(self)
        self.set_widget(MiroMozEmbed())
        self.wrapped_widget_connect('open-uri', self.on_open_uri)
        self.wrapped_widget_connect('realize', self.on_realize)
        self.wrapped_widget_connect('net-start', self.on_net_start)
        self.wrapped_widget_connect('net-stop', self.on_net_stop)
        self._widget.set_size_request(200, 100)
        # Seems like a reasonable min-size

        self.create_signal('net-start')
        self.create_signal('net-stop')

    def on_net_start(self, browser):
        self.emit('net-start')

    def on_net_stop(self, browser):
        self.emit('net-stop')

    def on_open_uri(self, browser, uri):
        if self.should_load_url(uri):
            return False
        else:
            return True

    def get_current_url(self):
        return self._widget.get_location()

    url = property(get_current_url)

    def forward(self):
        if self._widget.can_go_forward():
            self._widget.go_forward()

    def back(self):
        if self._widget.can_go_back():
            self._widget.go_back()

    def can_go_forward(self):
        return self._widget.can_go_forward()

    def can_go_back(self):
        return self._widget.can_go_back()

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


class NewWindowMonitor:
    def on_new_window(self, uri):
        app.widgetapp.open_url(uri)
_new_window_monitor = NewWindowMonitor()

def do_xpcom_setup():
    global xpcom_setup

    mozprompt.stop_prompts()
    httpobserver.start_http_observer()
    xpcom_setup = True
    windowcreator.install_window_creator(_new_window_monitor)
    pluginsdir.setup_plugins_dir()
