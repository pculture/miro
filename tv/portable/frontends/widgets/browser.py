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

        back_button = widgetset.Button(_('Back'), style='smooth')
        back_button.set_size(widgetconst.SIZE_SMALL)
        back_button.set_color(style.TOOLBAR_GRAY)
        back_button.connect('clicked', self._on_back_button_clicked)
        self.pack_start(
            widgetutil.align_left(back_button, top_pad=5, bottom_pad=5),
            expand=False)
        
        forward_button = widgetset.Button(_('Forward'), style='smooth')
        forward_button.set_size(widgetconst.SIZE_SMALL)
        forward_button.set_color(style.TOOLBAR_GRAY)
        forward_button.connect('clicked', self._on_forward_button_clicked)
        self.pack_start(
            widgetutil.align_left(forward_button, top_pad=5, bottom_pad=5),
            expand=False)

        reload_button = widgetset.Button(_('Reload'), style='smooth')
        reload_button.set_size(widgetconst.SIZE_SMALL)
        reload_button.set_color(style.TOOLBAR_GRAY)
        reload_button.connect('clicked', self._on_reload_button_clicked)
        self.pack_start(
            widgetutil.align_left(reload_button, top_pad=5, bottom_pad=5),
            expand=False)

        stop_button = widgetset.Button(_('Stop'), style='smooth')
        stop_button.set_size(widgetconst.SIZE_SMALL)
        stop_button.set_color(style.TOOLBAR_GRAY)
        stop_button.connect('clicked', self._on_stop_button_clicked)
        self.pack_start(
            widgetutil.align_left(stop_button, top_pad=5, bottom_pad=5),
            expand=False)

        home_button = widgetset.Button(_('Home'), style='smooth')
        home_button.set_size(widgetconst.SIZE_SMALL)
        home_button.set_color(style.TOOLBAR_GRAY)
        home_button.connect('clicked', self._on_home_button_clicked)
        self.pack_start(
            widgetutil.align_left(home_button, top_pad=5, bottom_pad=5),
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
        self.pack_start(self.toolbar, expand=False)
        self.pack_start(self.browser, expand=True)

        self.toolbar.connect('browser-back', self._on_browser_back)
        self.toolbar.connect('browser-forward', self._on_browser_forward)
        self.toolbar.connect('browser-reload', self._on_browser_reload)
        self.toolbar.connect('browser-stop', self._on_browser_stop)
        self.toolbar.connect('browser-home', self._on_browser_home)

    def _on_browser_back(self, widget):
        self.browser.back()

    def _on_browser_forward(self, widget):
        self.browser.forward()

    def _on_browser_reload(self, widget):
        self.browser.reload()

    def _on_browser_stop(self, widget):
        self.browser.reload()

    def _on_browser_home(self, widget):
        self.browser.navigate(self.home_url)
