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
from miro.frontends.widgets import dialogs
from miro.frontends.widgets import dialogwidgets
from miro.frontends.widgets import prefpanel
from miro.plat import resources
from miro.gtcache import gettext as _
from miro import gtcache
from miro.plat.frontends.widgets.threads import call_on_ui_thread

class DonatePowerToys(object):
    # NB: not translated on purpose
    def __init__(self):
        title = 'Donate PowerToys'
        widget = self.build_widgets()
        w, h  = widget.get_size_request()
        rect = widgetset.Rect(0, 0, w, h)
        self.window = widgetset.DialogWindow(title, rect)
        self.window.set_content_widget(widget)

    def run_dialog(self):
        self.window.show()

    def on_reset_clicked(self, obj):
        app.donate_manager.reset()

    def on_run_clicked(self, obj):
        donate_url = self.donate_url_textentry.get_text()
        payment_url = self.payment_url_textentry.get_text()
        if not donate_url:
            donate_url = None
        if not payment_url:
            payment_url = None
        app.donate_manager.show_donate(url=donate_url, payment_url=payment_url)

    def on_set_ratelimit_clicked(self, obj):
        app.donate_manager.set_ratelimit()

    def on_reset_ratelimit_clicked(self, obj):
        app.donate_manager.reset_ratelimit()
        
    def on_reset_donate_url_clicked(self, obj):
        self.donate_url = None
        self.donate_url_textentry.set_text('')

    def on_reset_payment_url_clicked(self, obj):
        self.payment_url = None
        self.payment_url_textentry.set_text('')

    def build_widgets(self):
        self.vlayout = widgetset.VBox(spacing=5)
        grid = dialogwidgets.ControlGrid()

        donate_nothanks_textentry = widgetset.TextEntry()
        donate_nothanks_textentry.set_width(5)
        prefpanel.attach_integer(donate_nothanks_textentry,
                       prefs.DONATE_NOTHANKS,
                       prefpanel.build_error_image(),
                       prefpanel.create_value_checker(min_=0))

        last_donate_time_textentry = widgetset.TextEntry()
        last_donate_time_textentry .set_width(16)
        prefpanel.attach_integer(last_donate_time_textentry, 
                       prefs.LAST_DONATE_TIME,
                       prefpanel.build_error_image(),
                       prefpanel.create_value_checker(min_=0))

        donate_counter_textentry = widgetset.TextEntry()
        donate_counter_textentry.set_width(5)
        prefpanel.attach_integer(donate_counter_textentry,
                       prefs.DONATE_COUNTER,
                       prefpanel.build_error_image(),
                       prefpanel.create_value_checker(min_=0))

        set_ratelimit_button = widgetset.Button('Force ratelimit')
        set_ratelimit_button.connect('clicked', self.on_set_ratelimit_clicked)

        reset_ratelimit_button = widgetset.Button('Force no ratelimit')
        reset_ratelimit_button.connect('clicked',
                                       self.on_reset_ratelimit_clicked)

        reset_button = widgetset.Button('Reset counters to factory defaults')
        reset_button.connect('clicked', self.on_reset_clicked)

        reset_donate_url_button = widgetset.Button('Reset')
        reset_donate_url_button.connect('clicked',
                                        self.on_reset_donate_url_clicked)

        reset_payment_url_button = widgetset.Button('Reset')
        reset_payment_url_button.connect('clicked',
                                          self.on_reset_payment_url_clicked)

        self.donate_url_textentry = widgetset.TextEntry()
        self.donate_url_textentry.set_width(16)

        self.payment_url_textentry = widgetset.TextEntry()
        self.payment_url_textentry.set_width(16)

        run_button = widgetset.Button('Run dialog')
        run_button.connect('clicked', self.on_run_clicked)

        grid.pack_label('Set DONATE_NOTHANKS', grid.ALIGN_RIGHT)
        grid.pack(donate_nothanks_textentry, span=2)
        grid.end_line(spacing=4)

        grid.pack_label('Set LAST_DONATE_TIME', grid.ALIGN_RIGHT)
        grid.pack(last_donate_time_textentry, span=2)
        grid.end_line(spacing=4)

        grid.pack_label('Set DONATE_COUNTER', grid.ALIGN_RIGHT)
        grid.pack(donate_counter_textentry, span=2)
        grid.end_line(spacing=4)

        grid.pack(reset_button, grid.FILL, span=3)
        grid.end_line(spacing=4)

        hbox = widgetset.HBox()
        hbox.pack_start(set_ratelimit_button)
        hbox.pack_start(reset_ratelimit_button)

        grid.pack(widgetutil.align_center(hbox), grid.FILL, span=3)
        grid.end_line(spacing=4)
        grid.pack_label('Use donate url', grid.ALIGN_RIGHT)
        grid.pack(self.donate_url_textentry)
        grid.pack(reset_donate_url_button, grid.FILL)
        grid.end_line(spacing=4)

        grid.pack_label('Use payment donate url', grid.ALIGN_RIGHT)
        grid.pack(self.payment_url_textentry)
        grid.pack(reset_payment_url_button, grid.FILL)
        grid.end_line(spacing=4)

        grid.pack(run_button, grid.FILL, span=3)
        grid.end_line(spacing=12)

        alignment = widgetset.Alignment(xalign=0.5, yalign=0.5)
        alignment.set_padding(20, 20, 20, 20)
        alignment.add(grid.make_table())

        return alignment

class DonateWindow(widgetset.DonateWindow):
    def __init__(self):
        widgetset.DonateWindow.__init__(self, _("Donate"))
        self.create_signal('donate-clicked')
        self.vbox = widgetset.VBox(spacing=5)
        self.hbox = widgetset.HBox(spacing=5)
        self.button_yes = widgetset.Button(_('Yes, I can donate now'))
        self.button_no = widgetset.Button(_('Ask me later'))
        self.button_yes.connect('clicked', self._on_button_clicked)
        self.button_no.connect('clicked', self._on_button_clicked)
        self.browser = widgetset.Browser()
        self.browser.set_size_request(640, 440)
        self.browser.connect('net-stop', self._on_browser_stop)
        self.browser.connect('net-error', self._on_browser_error)
        self.hbox.pack_end(widgetutil.align_middle(self.button_no,
                                                   right_pad=10))
        self.hbox.pack_end(widgetutil.align_middle(self.button_yes))
        self.vbox.pack_start(self.browser, padding=10, expand=True)
        self.vbox.pack_start(self.hbox, padding=5)
        self.set_content_widget(self.vbox)
        self.was_shown_invoked = False

        self.callback_object = None

    def _on_button_clicked(self, widget):
        callback_object = self.callback_object
        self.callback_object = None
        if widget == self.button_yes:
            self.emit('donate-clicked', True, callback_object)
        elif widget == self.button_no:
            self.emit('donate-clicked', False, callback_object)

    def navigate(self, url):
        self.browser.navigate(url)

    def show(self, url, callback_object):
        if url:
            self.callback_object = callback_object
            logging.debug('Donate: Navigating to %s (callback object = %s)',
                          url, callback_object)
            self.was_shown_invoked = True
            self.browser.navigate(url)
        else:
            widgetset.DonateWindow.show(self)

    def _on_browser_stop(self, widget):
        logging.debug('Donate: _on_browser_stop')
        if self.was_shown_invoked:
            widgetset.DonateWindow.show(self)
            self.was_shown_invoked = False

    def _on_browser_error(self, widget):
        # XXX Linux/GTK can't directly issue a self.navigate() here on error.
        # Don't know why.  :-(
        logging.debug('Donate: _on_browser_error')
        # only need to nav to fallback if the window was requested to be
        # shown
        if self.was_shown_invoked:
            fallback_path = resources.url('donate.html')
            call_on_ui_thread(lambda: self.browser.navigate(fallback_path))
            self.was_shown_invoked = False
