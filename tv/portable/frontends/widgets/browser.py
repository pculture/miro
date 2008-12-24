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

from miro import app
from miro import filetypes
from miro import guide
from miro import messages
from miro import subscription
from miro import util
from miro.plat import resources
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets.threads import call_on_ui_thread
from miro.frontends.widgets import linkhandler
from miro.frontends.widgets import imagebutton
from miro.frontends.widgets import style
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets import separator
from miro.gtcache import gettext as _

class BrowserToolbar(widgetset.HBox):
    """
    Forward/back/home & "display in browser" buttons
    """
    def __init__(self):
        widgetset.HBox.__init__(self)

        self.set_size_request(-1, 25)
        self.create_signal('browser-reload')
        self.create_signal('browser-back')
        self.create_signal('browser-forward')
        self.create_signal('browser-stop')
        self.create_signal('browser-home')
        self.create_signal('address-entered')
        self.create_signal('browser-open')

        self.back_button = imagebutton.ImageButton('navback')
        self.back_button.set_squish_width(True)
        self.back_button.connect('clicked', self._on_back_button_clicked)
        self.back_button.disable()
        self.pack_start(widgetutil.align_middle(self.back_button, left_pad=4))
        
        self.forward_button = imagebutton.ImageButton('navforward')
        self.forward_button.set_squish_width(True)
        self.forward_button.connect('clicked', self._on_forward_button_clicked)
        self.forward_button.disable()
        self.pack_start(widgetutil.align_middle(self.forward_button))

        self.reload_button = imagebutton.ImageButton('navreload')
        self.reload_button.connect('clicked', self._on_reload_button_clicked)
        self.pack_start(widgetutil.align_middle(self.reload_button, left_pad=4))

        self.stop_button = imagebutton.ImageButton('navstop')
        self.stop_button.connect('clicked', self._on_stop_button_clicked)
        self.pack_start(widgetutil.align_middle(self.stop_button, left_pad=4))

        self.home_button = imagebutton.ImageButton('navhome')
        self.home_button.connect('clicked', self._on_home_button_clicked)
        self.pack_start(widgetutil.align_middle(self.home_button, left_pad=4))

        self.browser_open_button = widgetset.Button(
            _('Open in browser'), style='smooth')
        self.browser_open_button.set_size(widgetconst.SIZE_SMALL)
        self.browser_open_button.connect(
            'clicked', self._on_browser_open_activate)
        self.pack_end(widgetutil.align_middle(self.browser_open_button, right_pad=4))

        self.loading_icon = widgetutil.HideableWidget(
                widgetset.AnimatedImageDisplay(
                    resources.path('images/load-indicator.gif')))
        self.pack_end(widgetutil.align_middle(self.loading_icon, right_pad=6))

    def _on_back_button_clicked(self, button):
        self.emit('browser-back')

    def _on_forward_button_clicked(self, button):
        self.emit('browser-forward')

    def _on_stop_button_clicked(self, button):
        self.emit('browser-stop')

    def _on_reload_button_clicked(self, button):
        self.emit('browser-reload')

    def _on_home_button_clicked(self, button):
        self.emit('browser-home')

    def _on_browser_open_activate(self, button):
        self.emit('browser-open')

class Browser(widgetset.Browser):
    def __init__(self, guide_info):
        widgetset.Browser.__init__(self)
        self.guide_info = guide_info
    
    def should_load_url(self, url):
        """Returns True if the Miro browser should handle the url and False
        otherwise.

        Situations which should return false:

        * if the url is something that Miro should download instead
        * other things?
        """
        logging.info("got %s", url)

        url = util.toUni(url)
        if subscription.is_subscribe_link(url):
            messages.SubscriptionLinkClicked(url).send_to_backend()
            return False

        # FIXME - handle downloadable items here

        return True

class BrowserNav(widgetset.VBox):
    def __init__(self, guide_info):
        widgetset.VBox.__init__(self)
        self.browser = Browser(guide_info)
        self.toolbar = BrowserToolbar()
        self.guide_info = guide_info
        self.home_url = guide_info.url
        self.browser.navigate(guide_info.url)
        self.pack_start(self.toolbar, expand=False)
        self.pack_start(separator.HThinSeparator((0.6, 0.6, 0.6)))
        self.pack_start(self.browser, expand=True)

        self.toolbar.connect('browser-back', self._on_browser_back)
        self.toolbar.connect('browser-forward', self._on_browser_forward)
        self.toolbar.connect('browser-reload', self._on_browser_reload)
        self.toolbar.connect('browser-stop', self._on_browser_stop)
        self.toolbar.connect('browser-home', self._on_browser_home)
        self.toolbar.connect('browser-open', self._on_browser_open)

        self.browser.connect('net-start', self._on_net_start)
        self.browser.connect('net-stop', self._on_net_stop)

    def enable_disable_navigation(self):
        if self.browser.can_go_back():
            self.toolbar.back_button.enable()
        else:
            self.toolbar.back_button.disable()

        if self.browser.can_go_forward():
            self.toolbar.forward_button.enable()
        else:
            self.toolbar.forward_button.disable()

    def _on_net_start(self, widget):
        self.toolbar.stop_button.enable()
        self.enable_disable_navigation()
        self.toolbar.loading_icon.show()

    def _on_net_stop(self, widget):
        self.toolbar.stop_button.disable()
        self.enable_disable_navigation()
        self.toolbar.loading_icon.hide()

    def _on_browser_back(self, widget):
        self.browser.back()

    def _on_browser_forward(self, widget):
        self.browser.forward()

    def _on_browser_reload(self, widget):
        self.browser.reload()

    def _on_browser_stop(self, widget):
        self.browser.stop()

    def _on_browser_home(self, widget):
        self.browser.navigate(self.home_url)

    def _on_browser_open(self, widget):
        app.widgetapp.open_url(self.browser.get_current_url())
