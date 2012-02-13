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

"""``miro.donatemanager`` -- functions for handling donation
"""

import logging
import time

from miro import app
from miro import eventloop
from miro import prefs
from miro import signals

from miro.frontends.widgets import donate

from miro.plat.frontends.widgets.threads import call_on_ui_thread

class DonateManager(object):
    """DonateManager: anchor point for donation framework implementation.

    There is frontend stuff and backend stuff both anchored here, by
    necessity.  Most of the stuff here is backend except:

    (1) when you create the UI components
    (2) when you run the UI components
    (3) when the UI components issue callbacks in response to user input

    UI components can include the actual donate window as well as the debug
    powertoys.

    There are some preferences to do various housekeeping.

    DONATE_PAYMENT_URL - keeps track of the payment URL if user says yes
    DONATE_URL_TEMPLATE - a template url is used to ask the user for donation
                          The template is transformed into an actual URL
    DONATE_ASK{1,2,3} - number of downloads completed before we show 
                        DONATE_URL_TEMPLATE
    DONATE_NOTHANKS - the time the user last said no thanks to our request
    DONATE_COUNTER - count down timer.  When zero, the dialog will be shown.
                     When re-armed, it should be populated with values
                     from DONATE_ASK{1,2,3}
    LAST_DONATE_TIME - the last the user donated.  Starts off as 0.  If 0 on
                       shutdown it is reset to the current time.  Used to keep
                       track whether user has accepted as request for donation,
                       at which point we don't bother them again.  This is
                       reset every 0 months
    """
    def __init__(self):
        self.donate_ask_thresholds = [app.config.get(prefs.DONATE_ASK1),
                                      app.config.get(prefs.DONATE_ASK2),
                                      app.config.get(prefs.DONATE_ASK3)]
        self.donate_url_template = app.config.get(prefs.DONATE_URL_TEMPLATE)
        self.payment_url = app.config.get(prefs.DONATE_PAYMENT_URL)
        self.donate_nothanks = app.config.get(prefs.DONATE_NOTHANKS)
        self.donate_counter = app.config.get(prefs.DONATE_COUNTER)
        self.last_donate_time = app.config.get(prefs.LAST_DONATE_TIME)
        app.backend_config_watcher.connect('changed', self.on_config_changed)
        signals.system.connect('download-complete', self.on_download_complete)
        self.donate_window = self.powertoys = None
        self.donate_ratelimit = False
        self.ratelimit_dc = None
        # Tri-state: None/False/True: the close callback gets called
        # anyway even if the window's not shown!
        self.donate_response = None
        call_on_ui_thread(self.create_windows)

        # Reset counters if not shown for more than 1/2 year.  Only do this on
        # startup is fine.  Se have already waited half a year, we can wait
        # some more.
        #
        # The other part to this is in shutdown, if the last_donate_time
        # is still zero at the point in shutdown() set the current time.
        HALF_YEAR = 60 * 60 * 24 * 180
        if time.time() - self.last_donate_time > HALF_YEAR:
            self.reset()

    def create_windows(self):
        self.donate_window = donate.DonateWindow()
        self.powertoys = donate.DonatePowerToys()
        self.donate_window.connect('donate-clicked', self.on_donate_clicked)
        self.donate_window.connect('hide', self.on_window_close)

    def run_powertoys(self):
        if self.powertoys:
            self.powertoys.run_dialog()

    def on_config_changed(self, obj, key, value):
        if key == prefs.DONATE_NOTHANKS.key:
            self.donate_nothanks = value
        elif key == prefs.DONATE_COUNTER.key:
            self.donate_counter = value
        elif key == prefs.LAST_DONATE_TIME.key:
            self.last_donate_time = value

    def on_download_complete(self, obj, item):
        try:
            # Re-arm count is for the next threshold, not the current one,
            # so add 1.
            rearm_count = self.donate_ask_thresholds[self.donate_nothanks + 1]
        except IndexError:
            rearm_count = self.donate_ask_thresholds[-1]

        self.donate_counter -= 1

        # In case the donate counters are borked, then reset it
        if self.donate_counter < 0:
            self.donate_counter = 0
        if self.last_donate_time < 0:
            self.last_donate_time = 0

        # If the donate window has been shown recently, don't show it again
        # even if the timer is about to fire.  Defuse the timer and then
        # continue.
        if self.donate_ratelimit:
            logging.debug('donate: rate limiting donate window popup.')
            return

        logging.debug('donate: on_download_complete %s %s %s',
                      self.donate_nothanks, self.donate_counter,
                      self.last_donate_time)

        # Show it if the donate counter has reached zero and we have asked
        # less than 3 times
        show_donate = self.donate_counter == 0 and self.donate_nothanks < 3

        if show_donate:
            # re-arm the countdown
            self.donate_counter = rearm_count
            self.set_ratelimit()
            # 5 days
            self.ratelimit_dc = eventloop.add_timeout(3600 * 24 * 5,
                                                      self.reset_ratelimit,
                                                      'donate ratelimiter')
            self.show_donate()

        # Set the new value of donate_counter.
        app.config.set(prefs.DONATE_COUNTER, self.donate_counter)


    # ratelimit set/reset can be called from frontend but in this case it
    # should be okay
    def reset_ratelimit(self):
        logging.debug('donate: ratelimit flag reset')
        self.donate_ratelimit = False

    def set_ratelimit(self):
        logging.debug('donate: ratelimit flag set')
        self.donate_ratelimit = True

    def on_window_close(self, obj):
        if self.donate_response is None:
            return
        if not self.donate_response:
            self.donate_nothanks += 1
            app.config.set(prefs.DONATE_NOTHANKS, self.donate_nothanks)
        # Reset flag
        self.donate_response = None

    def on_donate_clicked(self, obj, donate, payment_url):
        # Save response then close.  Do it in the close callback because
        # we want to run common code for the no case for people who
        # simply close the window without responding.  But we do the yes
        # case in-line to open the payment_url as provided by the callback
        self.donate_response = donate
        if donate:
            app.widgetapp.open_url(payment_url)
        self.donate_window.close()

    def shutdown(self):
        # OK: shutdown() is executed on frontend
        if self.donate_window:
            self.donate_window.close()
            self.donate_window = None
        self.reset_ratelimit()
        # Don't forget to save the donate counter on shutdown!
        app.config.set(prefs.DONATE_COUNTER, self.donate_counter)
        # If last_donate_time is 0, reset it and pretend it to be something
        # sane so the prefs don't get reset on next startup.
        if self.last_donate_time == 0:
            app.config.set(prefs.LAST_DONATE_TIME, time.time())

    def reset(self):
        for pref in [prefs.DONATE_NOTHANKS, prefs.LAST_DONATE_TIME,
                     prefs.DONATE_COUNTER]:
            app.config.set(pref, pref.default)

    def show_donate(self, url=None, payment_url=None):
        if not url:
            args = [1, 2, 3]
            try:
                url = self.donate_url_template % args[self.donate_nothanks]
            except IndexError:
                url = self.donate_url_template % args[-1]
        if not payment_url:
            payment_url = self.payment_url
        if self.donate_window:
            self.last_donate_time = time.time()
            app.config.set(prefs.LAST_DONATE_TIME, self.last_donate_time)
            call_on_ui_thread(lambda: self.donate_window.show(url,
                                                              payment_url))
