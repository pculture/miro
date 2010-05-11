# Miro - an RSS based video player application
# Copyright (C) 2010 Participatory Culture Foundation
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

"""
Code for a WebKit based browser.

Documentation for WebKitGTK+:
http://webkitgtk.org/reference/index.html

Documentation for PyWebKitGTK: 
http://code.google.com/p/pywebkitgtk/
"""

from miro import config, prefs

import gtk
import webkit

def fix_user_agent(agent):
    """Default user agent for WebKitGTK+ is something like:

    Mozilla/5.0 (X11; U; Linux x86_64; c) AppleWebKit/531.2+ (KHTML, like Gecko) Safari/531.2+

    This function takes that string, drops the last bit, and adds Miro
    bits.
    """
    agent = agent.split(" ")[:-1]
    agent.append("%s/%s (%s)" % (config.get(prefs.SHORT_APP_NAME),
                                 config.get(prefs.APP_VERSION),
                                 config.get(prefs.PROJECT_URL)))
    return " ".join(agent)

class WebKitEmbed(webkit.WebView):
    def __init__(self):
        webkit.WebView.__init__(self)
        settings = self.get_settings()
        settings.set_property("enable-developer-extras", True)

        self.set_full_content_zoom(True)
        self.set_maintains_back_forward_list(True)

        agent = settings.get_property('user-agent')
        agent = fix_user_agent(agent)
        settings.set_property('user-agent', agent)

        self.connect_after("populate-popup", self.handle_populate_popup)

    def get_frame(self):
        # our browser isn't tabbed, so we always get the main
        # frame and operate on that.
        return self.get_main_frame()

    def handle_zoom_in(self, menu_item, view):
        view.zoom_in()

    def handle_zoom_out(self, menu_item, view):
        view.zoom_out()

    def handle_zoom_full(self, menu_item, view):
        if not (view.get_zoom_level() == 1.0):
            view.set_zoom_level(1.0)

    def handle_populate_popup(self, view, menu):
        zoom_in = gtk.ImageMenuItem(gtk.STOCK_ZOOM_IN)
        zoom_in.connect('activate', self.handle_zoom_in, view)
        menu.append(zoom_in)

        zoom_out = gtk.ImageMenuItem(gtk.STOCK_ZOOM_OUT)
        zoom_out.connect('activate', self.handle_zoom_out, view)
        menu.append(zoom_out)

        zoom_full = gtk.ImageMenuItem(gtk.STOCK_ZOOM_100)
        zoom_full.connect('activate', self.handle_zoom_full, view)
        menu.append(zoom_full)

        menu.show_all()
        return False
