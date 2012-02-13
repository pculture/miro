# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

"""Defines the donate window.  Please help Miro!
"""

import logging
import sys
import os

from miro import app
from miro import messages
from miro import prefs
from miro.plat.frontends.widgets import widgetset
from miro.frontends.widgets import widgetutil
from miro.frontends.widgets.widgetstatestore import WidgetStateStore
from miro.plat import resources
from miro.gtcache import gettext as _
from miro import gtcache
from miro.plat.frontends.widgets.threads import call_on_ui_thread

_donate_window = None
# XXX TEMPORARY
def show():
    global _donate_window
    if not _donate_window:
        _donate_window = DonateWindow()
    _donate_window.show()

class DonateWindow(widgetset.DonateWindow):
    DONATE_URL = 'http://127.0.0.1'
    PAYMENT_URL = 'http://127.0.0.1'
    def __init__(self):
        widgetset.DonateWindow.__init__(self, _("Donate"))
        self.vbox = widgetset.VBox(spacing=5)
        self.hbox = widgetset.HBox(spacing=5)
        self.button_yes = widgetset.Button(_('Yes'))
        self.button_no = widgetset.Button(_('No thanks'))
        self.button_yes.connect('clicked', self._on_button_clicked)
        self.button_no.connect('clicked', self._on_button_clicked)
        self.browser = widgetset.Browser()
        self.browser.set_size_request(640, 440)
        self.browser.connect('net-error', self._on_browser_error)
        self.browser.navigate(DonateWindow.DONATE_URL)
        self.hbox.pack_end(widgetutil.align_middle(self.button_no,
                                                   right_pad=10))
        self.hbox.pack_end(widgetutil.align_middle(self.button_yes))
        self.vbox.pack_start(self.browser, padding=10, expand=True)
        self.vbox.pack_start(self.hbox, padding=5)
        self.set_content_widget(self.vbox)

    def _on_button_clicked(self, widget):
        if widget == self.button_yes:
            app.widgetapp.open_url(DonateWindow.PAYMENT_URL)   
        elif widget == self.button_no:
            _donate_window.close()

    def _on_browser_error(self, widget):
        # XXX Linux/GTK can't directly issue a self.navigate() here on error.
        # Don't know why.  :-(
        fallback_path = resources.url('donate.html')
        call_on_ui_thread(lambda: self.browser.navigate(fallback_path))
