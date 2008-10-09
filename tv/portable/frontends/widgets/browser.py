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
from miro.plat.frontends.widgets import widgetset
from miro.plat.frontends.widgets.threads import call_on_ui_thread
from miro.frontends.widgets import linkhandler
from miro.frontends.widgets import style
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets import widgetutil
from miro.gtcache import gettext as _

PROTOCOLS_MIRO_HANDLES = ("http:", "https:", "ftp:", "feed:", "feeds:", "mailto:")

def _should_miro_handle(url):
    for mem in PROTOCOLS_MIRO_HANDLES:
        if url.startswith(mem):
            return True
    return False


class BrowserToolbar(widgetset.HBox):
    """
    Forward/back/home & "display in browser" buttons
    """
    def __init__(self):
        widgetset.HBox.__init__(self)

        self.create_signal('browser-reload')
        self.create_signal('browser-back')
        self.create_signal('browser-forward')
        self.create_signal('browser-stop')
        self.create_signal('browser-home')
        self.create_signal('address-entered')
        self.create_signal('browser-open')

        self.back_button = widgetset.Button(_('Back'), style='smooth')
        self.back_button.set_size(widgetconst.SIZE_SMALL)
        self.back_button.connect('clicked', self._on_back_button_clicked)
        self.back_button.disable_widget()
        self.pack_start(
            widgetutil.align_left(self.back_button, top_pad=5, bottom_pad=5),
            expand=False)
        
        self.forward_button = widgetset.Button(_('Forward'), style='smooth')
        self.forward_button.set_size(widgetconst.SIZE_SMALL)
        self.forward_button.connect('clicked', self._on_forward_button_clicked)
        self.forward_button.disable_widget()
        self.pack_start(
            widgetutil.align_left(self.forward_button, top_pad=5, bottom_pad=5),
            expand=False)

        self.reload_button = widgetset.Button(_('Reload'), style='smooth')
        self.reload_button.set_size(widgetconst.SIZE_SMALL)
        self.reload_button.connect('clicked', self._on_reload_button_clicked)
        self.pack_start(
            widgetutil.align_left(self.reload_button, top_pad=5, bottom_pad=5),
            expand=False)

        self.stop_button = widgetset.Button(_('Stop'), style='smooth')
        self.stop_button.set_size(widgetconst.SIZE_SMALL)
        self.stop_button.connect('clicked', self._on_stop_button_clicked)
        self.pack_start(
            widgetutil.align_left(self.stop_button, top_pad=5, bottom_pad=5),
            expand=False)

        self.home_button = widgetset.Button(_('Home'), style='smooth')
        self.home_button.set_size(widgetconst.SIZE_SMALL)
        self.home_button.connect('clicked', self._on_home_button_clicked)
        self.pack_start(
            widgetutil.align_left(self.home_button, top_pad=5, bottom_pad=5),
            expand=False)

        self.address_entry = widgetset.TextEntry()
        self.address_entry.connect('activate', self._on_address_bar_activate)
        self.pack_start(self.address_entry, expand=True)

        self.go_button = widgetset.Button(_('Go'), style='smooth')
        self.go_button.set_size(widgetconst.SIZE_SMALL)
        self.go_button.connect('clicked', self._on_address_bar_activate)
        self.pack_start(
            widgetutil.align_right(self.go_button, top_pad=5, bottom_pad=5),
            expand=False)

        self.browser_open_button = widgetset.Button(
            _('Open in browser'), style='smooth')
        self.browser_open_button.set_size(widgetconst.SIZE_SMALL)
        self.browser_open_button.connect(
            'clicked', self._on_browser_open_activate)
        self.pack_start(
            widgetutil.align_right(
                    self.browser_open_button, top_pad=5, bottom_pad=5),
            expand=False)

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

    def _on_address_bar_activate(self, widget):
        self.emit('address-entered')

    def _on_browser_open_activate(self, button):
        self.emit('browser-open')


class Browser(widgetset.Browser):
    def __init__(self, guide_info):
        widgetset.Browser.__init__(self)
        self.guide_info = guide_info
    
    def should_load_url(self, url):
        logging.info ("got %s", url)
        # FIXME, this seems really weird.  How are we supposed to pick an
        # encoding?
        url = util.toUni(url)
        if subscription.is_subscribe_link(url):
            messages.SubscriptionLinkClicked(url).send_to_backend()
            return False

        if (guide.isPartOfGuide(url, self.guide_info.url,
                self.guide_info.allowed_urls) and
                not filetypes.isFeedFilename(url) and
                not filetypes.isAllowedFilename(url)):
            return True

        if not _should_miro_handle(url):
            # javascript: link, or some other weird URL scheme.  Let the
            # browser handle it.
            return True

        # handle_external_url could pop up dialogs and other complex things.
        # Let's return from the callback before we call it.
        call_on_ui_thread(linkhandler.handle_external_url, url)
        return False


class BrowserNav(widgetset.VBox):
    def __init__(self, guide_info):
        widgetset.VBox.__init__(self)
        self.browser = Browser(guide_info)
        self.toolbar = BrowserToolbar()
        self.guide_info = guide_info
        self.home_url = guide_info.url
        self.browser.navigate(guide_info.url)
        self.toolbar.address_entry.set_text(guide_info.url)
        self.pack_start(self.toolbar, expand=False)
        self.pack_start(self.browser, expand=True)

        self.toolbar.connect('browser-back', self._on_browser_back)
        self.toolbar.connect('browser-forward', self._on_browser_forward)
        self.toolbar.connect('browser-reload', self._on_browser_reload)
        self.toolbar.connect('browser-stop', self._on_browser_stop)
        self.toolbar.connect('browser-home', self._on_browser_home)
        self.toolbar.connect('address-entered', self._on_address_entered)
        self.toolbar.connect('browser-open', self._on_browser_open)

        self.browser.connect('net-start', self._on_net_start)
        self.browser.connect('net-stop', self._on_net_stop)

    def enable_disable_navigation(self):
        if self.browser.can_go_back():
            self.toolbar.back_button.enable_widget()
        else:
            self.toolbar.back_button.disable_widget()

        if self.browser.can_go_forward():
            self.toolbar.forward_button.enable_widget()
        else:
            self.toolbar.forward_button.disable_widget()

    def _on_net_start(self, widget):
        self.toolbar.stop_button.enable_widget()
        self.toolbar.address_entry.set_text(self.browser.url)
        self.enable_disable_navigation()

    def _on_net_stop(self, widget):
        self.toolbar.stop_button.disable_widget()
        self.enable_disable_navigation()

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

    def _on_address_entered(self, widget):
        self.browser.navigate(self.toolbar.address_entry.get_text())

    def _on_browser_open(self, widget):
        app.widgetapp.open_url(self.browser.url)
