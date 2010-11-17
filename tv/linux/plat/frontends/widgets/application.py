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

try:
    import gtk
except RuntimeError:
    print "You do not appear to have a working display."
    import sys
    sys.exit(1)
import gobject
import os
import gconf
import shutil
import platform

try:
    import pynotify
except ImportError:
    print "PyNotify support disabled on your platform."
    PYNOTIFY_SUPPORT = False
else:
    pynotify.init('miro')
    PYNOTIFY_SUPPORT = True

from miro import app
from miro import prefs
from miro.frontends.widgets.application import Application
# from miro.plat.frontends.widgets import threads
from miro.plat import renderers, options
from miro.plat.utils import set_properties
from miro.plat.config import gconf_lock
from miro.frontends.widgets.gtk import trayicon
from miro.plat import resources
from miro.plat.frontends.widgets import mediakeys

from miro.frontends.widgets.gtk.widgetset import Rect
from miro.frontends.widgets.gtk import webkitgtkhacks

import logging
import sys

def _get_pref(key, getter_name):
    gconf_lock.acquire()
    try:
        client = gconf.client_get_default()
        fullkey = '/apps/miro/' + key
        value = client.get(fullkey)
        if value is not None:
            getter = getattr(value, getter_name)
            return getter()
        else:
            return None
    finally:
        gconf_lock.release()

def _set_pref(key, setter_name, value):
    gconf_lock.acquire()
    try:
        client = gconf.client_get_default()
        fullkey = '/apps/miro/' + key
        setter = getattr(client, setter_name)
        setter(fullkey, value)
    finally:
        gconf_lock.release()

def get_int(key): return _get_pref('window/' + key, 'get_int')
def get_bool(key): return _get_pref('window/' + key, 'get_bool')
def get_player_int(key): return _get_pref(key, 'get_int')
def get_player_bool(key): return _get_pref(key, 'get_bool')

def set_int(key, value): return _set_pref('window/' + key, 'set_int', value)
def set_bool(key, value): return _set_pref('window/' + key, 'set_bool', value)
def set_player_int(key, value): return _set_pref(key, 'set_int', value)
def set_player_bool(key, value): return _set_pref(key, 'set_bool', value)

def run_application(props_to_set, theme):
    from miro import startup
    startup.initialize(theme)
    LinuxApplication().run(props_to_set)

class LinuxApplication(Application):
    def run(self, props_to_set):
        gobject.set_application_name(app.config.get(prefs.SHORT_APP_NAME))
        os.environ["PULSE_PROP_media.role"] = "video"

        gtk.gdk.threads_init()
        self._setup_webkit()
        self.startup()
        set_properties(props_to_set)
        
        logging.info("Linux version:     %s %s %s",
                     platform.system(),
                     platform.release(),
                     platform.machine())
        logging.info("Python version:    %s", sys.version)
        logging.info("Gtk+ version:      %s", gtk.gtk_version)
        logging.info("PyGObject version: %s", gtk.ver)
        logging.info("PyGtk version:     %s", gtk.pygtk_version)
        langs = ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")
        langs = [(l, os.environ.get(l)) for l in langs if os.environ.get(l)]
        logging.info("Language:          %s", langs)
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
        renderers.init_renderer()
        gtk.main()
        app.controller.on_shutdown()

    def _setup_webkit(self):
        support_dir = app.config.get(prefs.SUPPORT_DIRECTORY)
        cookie_path = os.path.join(support_dir, 'cookies.txt')
        webkitgtkhacks.setup_cookie_storage(cookie_path)

    def on_config_changed(self, obj, key, value):
        """Any time a preference changes, this gets notified so that we
        can adjust things.
        """
        if key == options.SHOW_TRAYICON.key:
            self.trayicon.set_visible(value)

        elif key == prefs.RUN_AT_STARTUP.key:
            self.update_autostart(value)

    def startup_ui(self):
        sys.excepthook = self.exception_handler
        Application.startup_ui(self)

    def _set_default_icon(self):
        # set the icon so that it doesn't flash when the window is
        # realized in Application.build_window().
        # if this isn't a themed Miro, then we use the default icon set
        ico_path = resources.share_path("icons/hicolor/24x24/apps/miro.png")
        if ((app.config.get(prefs.THEME_NAME) != prefs.THEME_NAME.default
             and app.config.get(options.WINDOWS_ICON))):
            theme_ico_path = resources.theme_path(
                app.config.get(prefs.THEME_NAME),
                app.config.get(options.WINDOWS_ICON))
            if os.path.exists(theme_ico_path):
                ico_path = theme_ico_path
                gtk.window_set_default_icon_from_file(ico_path)
        else:
            gtk.icon_theme_get_default().append_search_path(
                resources.share_path('icons'))
            gtk.window_set_default_icon_name("miro")

        return ico_path

    def build_window(self):
        self._set_default_icon()
        Application.build_window(self)
        self.window.connect('save-dimensions', self.set_main_window_dimensions)
        self.window.connect('save-maximized', self.set_main_window_maximized)

        # handle maximized
        maximized = self.get_main_window_maximized()
        if maximized != None:
            if maximized:
                self.window._window.maximize()
            else:
                self.window._window.unmaximize()

        # handle the trayicon
        if trayicon.trayicon_is_supported:
            self.trayicon = trayicon.Trayicon('miro')
            if app.config.get(options.SHOW_TRAYICON):
                self.trayicon.set_visible(True)
            else:
                self.trayicon.set_visible(False)

        # check x, y to make sure the window is visible and fix it
        # if not
        self.window.check_position_and_fix()

        # handle media keys
        self.mediakeyhandler = mediakeys.get_media_key_handler(self.window)

    def quit_ui(self):
        gtk.main_quit()

    def update_autostart(self, value):
        autostart_dir = resources.get_autostart_dir()
        destination = os.path.join(autostart_dir, "miro.desktop")

        if value:
            if os.path.exists(destination):
                return
            try:
                if not os.path.exists(autostart_dir):
                    os.makedirs(autostart_dir)
                shutil.copy(resources.share_path('applications/miro.desktop'),
                            destination)
            except OSError:
                logging.exception("Problems creating or populating "
                                  "autostart dir.")

        else:
            if not os.path.exists(destination):
                return
            try:
                os.remove(destination)
            except OSError:
                logging.exception("Problems removing autostart dir.")

    def open_url(self, url):
        resources.open_url(url)

    def reveal_file(self, filename):
        if not os.path.isdir(filename):
            filename = os.path.dirname(filename)
        self.open_file(filename)

    def open_file(self, filename):
        resources.open_file(filename)

    def get_clipboard_text(self):
        """Pulls text from the clipboard and returns it.

        This text is not filtered/transformed in any way--that's the
        job of the caller.
        """
        text = gtk.Clipboard(selection="PRIMARY").wait_for_text()
        if text is None:
            text = gtk.Clipboard(selection="CLIPBOARD").wait_for_text()

        if text:
            text = unicode(text)
        return text

    def copy_text_to_clipboard(self, text):
        gtk.Clipboard(selection="CLIPBOARD").set_text(text)
        gtk.Clipboard(selection="PRIMARY").set_text(text)

    def get_main_window_dimensions(self):
        x = get_int("x") or 100
        y = get_int("y") or 300
        width = get_int("width") or 800
        height = get_int("height") or 600

        return Rect(x, y, width, height)

    def get_main_window_maximized(self):
        return get_bool("maximized") == True

    def set_main_window_dimensions(self, window, x, y, width, height):
        set_int("width", width)
        set_int("height", height)
        set_int("x", x)
        set_int("y", y)

    def set_main_window_maximized(self, window, maximized):
        set_bool("maximized", maximized)

    def send_notification(self, title, body,
                          timeout=5000, attach_trayicon=True):
        if not PYNOTIFY_SUPPORT:
            return

        notification = pynotify.Notification(title, body)
        if (attach_trayicon
                and trayicon.trayicon_is_supported
                and app.config.get(options.SHOW_TRAYICON)):
            notification.attach_to_status_icon(self.trayicon)
        if timeout:
            notification.set_timeout(timeout)
        notification.show()

    def handle_first_time(self, callback):
        self._set_default_icon()
        Application.handle_first_time(self, callback)
