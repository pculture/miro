# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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
import _winreg

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
from miro.plat.renderers.vlc import VLCRenderer, get_item_type
from miro.plat.frontends.widgets import xulrunnerbrowser
from miro.frontends.widgets.gtk import trayicon
from miro.frontends.widgets.gtk import persistentwindow
from miro.frontends.widgets.gtk import widgets
from miro.plat.frontends.widgets import flash
from miro.plat.frontends.widgets import update
from miro.plat.frontends.widgets.threads import call_on_ui_thread

class WindowsApplication(Application):
    def run(self):
        logging.info("Python version:    %s", sys.version)
        logging.info("Gtk+ version:      %s", gtk.gtk_version)
        logging.info("PyGObject version: %s", gtk.ver)
        logging.info("PyGtk version:     %s", gtk.pygtk_version)
        try:
            import libtorrent
            logging.info("libtorrent:        %s", libtorrent.version)
        except AttributeError:
            logging.info("libtorrent:        unknown version")
        except ImportError:
            logging.exception("libtorrent won't load")
        try:
            import pycurl
            logging.info("pycurl:            %s", pycurl.version)
        except ImportError:
            logging.exception("pycurl won't load")
        app.video_renderer = app.audio_renderer = VLCRenderer()
        app.get_item_type = get_item_type
        self.initXULRunner()
        gtk.gdk.threads_init()
        self.startup()
        gtk.gdk.threads_enter()
        settings = gtk.settings_get_default()
        settings.set_property('gtk-theme-name', "MS-Windows")
        settings.set_property('gtk-tooltip-browse-mode-timeout', 0)
        # I'm not exactly sure why, but if the previous statement is not
        # present, we can get segfaults when displaying tooltips
        try:
            gtk.main()
        finally:
            gtk.gdk.threads_leave()
        xulrunnerbrowser.shutdown()
        app.controller.on_shutdown()

    def on_pref_changed(self, key, value):
        """Any time a preference changes, this gets notified so that we
        can adjust things.
        """
        if key == options.SHOW_TRAYICON.key:
            self.trayicon.set_visible(value)

        elif key == prefs.RUN_AT_STARTUP.key:
            self.set_run_at_startup(value)

    def _set_default_icon(self):
        # we set the icon first (if available) so that it doesn't flash
        # on when the window is realized in Application.build_window()
        icopath = os.path.join(resources.appRoot(), "Miro.ico")
        if config.get(prefs.THEME_NAME) and config.get(options.WINDOWS_ICON):
            themeIcoPath = resources.theme_path(config.get(prefs.THEME_NAME),
                                                config.get(options.WINDOWS_ICON))
            if os.path.exists(themeIcoPath):
                icopath = themeIcoPath
                gtk.window_set_default_icon_from_file(icopath)
        return icopath

    def build_window(self):
        icopath = self._set_default_icon()
        Application.build_window(self)
        self.window.connect('save-dimensions', self.set_main_window_dimensions)
        self.window.connect('save-maximized', self.set_main_window_maximized)

        maximized = self.get_main_window_maximized()
        if maximized != None:
            if maximized:
                self.window._window.maximize()
            else:
                self.window._window.unmaximize()

        config.add_change_callback(self.on_pref_changed)

        if trayicon.trayicon_is_supported:
            self.trayicon = trayicon.Trayicon(icopath)
            if config.get(options.SHOW_TRAYICON):
                self.trayicon.set_visible(True)
            else:
                self.trayicon.set_visible(False)
        else:
            logging.info("trayicon is not supported.")

    def on_close(self):
        if config.get(prefs.MINIMIZE_TO_TRAY_ASK_ON_CLOSE):
            ret = dialogs.show_choice_dialog(
                _("Close to tray?"),
                _("When you click the red close button, would you like %(appname)s to "
                  "close to the system tray or quit?  You can change this "
                  "setting later in the Options.",
                  {"appname": config.get(prefs.SHORT_APP_NAME)}),
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
        app.video_renderer.shutdown()
        for widget in persistentwindow.get_widgets():
            widget.destroy()
        if hasattr(self, "trayicon"):
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
        xulrunnerbrowser.setup_user_agent(config.get(prefs.LONG_APP_NAME),
                config.get(prefs.APP_VERSION), config.get(prefs.PROJECT_URL))
        xulrunnerbrowser.install_window_creator(self)

    def on_new_window(self, uri):
        self.open_url(uri)

    def startup_ui(self):
        Application.startup_ui(self)
        call_on_ui_thread(migrateappname.migrateVideos, 'Democracy', 'Miro')
        call_on_ui_thread(flash.check_flash_install)

    def open_url(self, url):
        # It looks like the maximum URL length is about 2k. I can't
        # seem to find the exact value
        if len(url) > 2047:
            url = url[:2047]
        try:
            webbrowser.get("windows-default").open_new(url)
        except:
            logging.warn("Error opening URL: %r\n%s", url,
                    traceback.format_exc())
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

    def reveal_file(self, fn):
        if not os.path.isdir(fn):
            fn = os.path.dirname(fn)
        os.startfile(fn)

    def open_file(self, fn):
        os.startfile(fn)

    def get_main_window_dimensions(self):
        max_width = gtk.gdk.screen_width()
        max_height = gtk.gdk.screen_height()
        rect = widgets.Rect.from_string(config.get(options.WINDOW_DIMENSIONS))
        rect.x = max(min(rect.x, max_width - 20), 0)
        rect.y = max(min(rect.y, max_height - 20), 0)
        rect.width = max(min(rect.width, max_width), 800)
        rect.height = max(min(rect.height, max_height - 20), 480)
        return rect

    def get_main_window_maximized(self):
        return config.get(options.WINDOW_MAXIMIZED)

    def set_main_window_dimensions(self, window, x, y, width, height):
        config.set(options.WINDOW_DIMENSIONS, "%s,%s,%s,%s" % (x, y, width, height))

    def set_main_window_maximized(self, window, maximized):
        config.set(options.WINDOW_MAXIMIZED, maximized)

    def send_notification(self, title, body,
                          timeout=5000, attach_trayicon=True):
        print '--- %s ---' % title
        print body

    def set_run_at_startup(self, value):
        runSubkey = "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        try:
            folder = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, runSubkey, 0,
                                     _winreg.KEY_SET_VALUE)
        except WindowsError, e:
            if e.errno == 2:
                # registry key doesn't exist
                folder = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER,
                                           runSubkey)
            else:
                raise

        if value:
            # We don't use the app name for the .exe, so branded
            # versions work
            filename = os.path.join(resources.root(), "..", "Miro.exe")
            filename = os.path.normpath(filename)
            themeName = config.get(prefs.THEME_NAME)
            if themeName is not None:
                themeName = themeName.replace("\\", "\\\\").replace('"', '\\"')
                filename = "%s --theme \"%s\"" % (filename, themeName)

            _winreg.SetValueEx(folder, config.get(prefs.LONG_APP_NAME), 0,
                               _winreg.REG_SZ, filename)

        else:
            try:
                _winreg.DeleteValue(folder, config.get(prefs.LONG_APP_NAME))
            except WindowsError, e:
                if e.errno == 2:
                    # registry key doesn't exist, user must have deleted it
                    # manual
                    pass
                else:
                    raise

    def handle_first_time(self, callback):
        self._set_default_icon()
        Application.handle_first_time(self, callback)
        
    def handle_update_available(self, obj, item):
        call_on_ui_thread(self.show_update_available, item)

    def show_update_available(self, item):
        releaseNotes = item.get('description', '')
        dialog = update.UpdateAvailableDialog(releaseNotes)
        try:
            ret = dialog.run()

            if ret == dialogs.BUTTON_YES:
                enclosures = [enclosure for enclosure in item['enclosures']
                              if enclosure['type'] == 'application/octet-stream']
                downloadURL = enclosures[0]['href']
                self.open_url(downloadURL)
        finally:
            dialog.destroy()
