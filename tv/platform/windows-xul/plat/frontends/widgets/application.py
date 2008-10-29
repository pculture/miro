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

import logging
import os
import sys
import traceback
import webbrowser
from urlparse import urlparse

import gtk

from miro.gtcache import gettext as _
from miro import app
from miro import config
from miro import eventloop
from miro import prefs
from miro.frontends.widgets import dialogs
from miro.frontends.widgets.application import Application
from miro.plat import migrateappname
from miro.plat import clipboard
from miro.plat import options
from miro.plat import resources
from miro.plat.renderers.vlc import VLCRenderer
from miro.plat.frontends.widgets import xulrunnerbrowser
from miro.frontends.widgets.gtk import trayicon
from miro.frontends.widgets.gtk import persistentwindow

class WindowsApplication(Application):
    def run(self):
        app.renderer = VLCRenderer()
        self.initXULRunner()
        gtk.gdk.threads_init()
        self.startup()
        gtk.gdk.threads_enter()
        try:
            gtk.main()
        finally:
            gtk.gdk.threads_leave()
        xulrunnerbrowser.shutdown()
        app.controller.onShutdown()

    def on_pref_changed(self, key, value):
        """Any time a preference changes, this gets notified so that we
        can adjust things.
        """
        if key == options.SHOW_TRAYICON.key:
            self.trayicon.set_visible(value)

    def build_window(self):
        Application.build_window(self)
        config.add_change_callback(self.on_pref_changed)

        if trayicon.trayicon_is_supported:
            icopath = os.path.join(resources.appRoot(), "Miro.ico")
            self.trayicon = trayicon.Trayicon(icopath)
            if config.get(options.SHOW_TRAYICON):
                logging.info("showing trayicon")
                self.trayicon.set_visible(True)
            else:
                logging.info("not showing trayicon")
                self.trayicon.set_visible(False)
        else:
            logging.info("trayicon is not supported.")

    def on_close(self):
        if config.get(prefs.MINIMIZE_TO_TRAY_ASK_ON_CLOSE):
            ret = dialogs.show_choice_dialog(
                _("Close to tray?"),
                _("When you click the red close button, would you like Miro to "
                  "close to the system tray or quit?  You can change this "
                  "setting later in the Options."),
                (dialogs.BUTTON_QUIT, dialogs.BUTTON_CLOSE_TO_TRAY))
            config.set(prefs.MINIMIZE_TO_TRAY_ASK_ON_CLOSE, False)
            if ret == dialogs.BUTTON_CLOSE_TO_TRAY:
                config.set(prefs.MINIMIZE_TO_TRAY, True)
            else:
                config.set(prefs.MINIMIZE_TO_TRAY, False)

        if config.get(prefs.MINIMIZE_TO_TRAY):
            self.trayicon.on_click(None)
        else:
            self.quit()

    def quit_ui(self):
        for widget in persistentwindow.get_widgets():
            widget.destroy()
        self.trayicon.set_visible(False)
        gtk.main_quit()

    def get_clipboard_text(self):
        return clipboard.get_text()

    def copy_text_to_clipboard(self, text):
        clipboard.set_text(text)

    def initXULRunner(self):
        app_dir = os.path.dirname(sys.executable)
        xul_dir = os.path.join(app_dir, 'xulrunner')
        xulrunnerbrowser.initialize(xul_dir, app_dir)

    def handleStartupSuccess(self, obj):
        migrateappname.migrateVideos('Democracy', 'Miro')
        Application.handleStartupSuccess(self, obj)

    def open_url(self, url):
        # It looks like the maximum URL length is about 2k. I can't
        # seem to find the exact value
        if len(url) > 2047:
            url = url[:2047]
        try:
            webbrowser.get("windows-default").open_new(url)
        except:
            logging.warn("Error opening URL: %r\n%s", url,
                    traceback.format_ext())
            recommendURL = config.get(prefs.RECOMMEND_URL)

            if url.startswith(config.get(prefs.VIDEOBOMB_URL)):
                title = _('Error Bombing Item')
            elif url.startswith(recommendURL):
                title = _('Error Recommending Item')
            else:
                title = _("Error Opening Website")

            scheme, host, path, params, query, fragment = urlparse(url)
            shortURL = '%s:%s%s' % (scheme, host, path)
            msg = _(
                "There was an error opening %(url)s.  Please try again in a few "
                "seconds",
                {"url": shortURL}
            )
            dialogs.show_message(title, msg, dialogs.WARNING_MESSAGE)

    def open_file(self, fn):
        if not os.path.isdir(fn):
            fn = os.path.dirname(fn)
        os.startfile(fn)

    def send_notification(self, title, body,
                          timeout=5000, attach_trayicon=True):
        print '--- %s ---' % title
        print body
