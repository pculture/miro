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

# Most of our stuff comes from the portable code.
from miro.frontends.widgets.gtk.widgetset import *

# We need to provide a Browser
from miro.plat.frontends.widgets import mozprompt
xpcom_setup = False

class Browser(Widget):
    """Web browser widget.  """

    def __init__(self):
        Widget.__init__(self)
        self.set_widget(gtkmozembed.MozEmbed())
        self.uri = None
        self.wrapped_widget_connect('open-uri', self.on_open_uri)
        self._widget.set_size_request(200, 100)
        # Seems like a reasonable min-size

    def on_open_uri(self, browser, uri):
        self.uri = uri

    def navigate(self, url):
        self._widget.load_url(url)

    def get_current_url(self):
        return self.uri

    def on_realize(self, widget):
        if not xpcom_setup:
            do_xpcom_setup()

def do_xpcom_setup():
    global xpcom_setup

    mozprompt.stop_prompts()
    xpcom_setup = True
