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

import gtk
import os
import gconf
import shutil

try:
    import pynotify
except ImportError:
    print "PyNotify support disabled on your platform."
    PYNOTIFY_SUPPORT = False
else:
    pynotify.init('miro')
    PYNOTIFY_SUPPORT = True

from miro import app
from miro import config
from miro import prefs
from miro.frontends.widgets.application import Application
from miro.plat.frontends.widgets import threads
from miro.plat import mozsetup, renderers, options
from miro.plat.utils import set_properties
from miro.plat.config import gconf_lock
from miro.frontends.widgets.gtk import trayicon
from miro.plat import resources

from miro.frontends.widgets.gtk.widgetset import Rect

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

def check_kde():
    return os.environ.get("KDE_FULL_SESSION", None) != None

class GtkX11Application(Application):
    def run(self, props_to_set):
        threads.call_on_ui_thread(mozsetup.setup_mozilla_environment)
        gtk.gdk.threads_init()
        self.startup()
        set_properties(props_to_set)

        logging.info("Python version:    %s", sys.version)
        logging.info("Gtk+ version:      %s", gtk.gtk_version)
        logging.info("PyGObject version: %s", gtk.ver)
        logging.info("PyGtk version:     %s", gtk.pygtk_version)
        langs = ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")
        langs = [(l, os.environ.get(l)) for l in langs if os.environ.get(l)]
        logging.info("Language:          %s", langs)
        renderers.init_renderer()
        gtk.main()
        app.controller.onShutdown()

    def on_pref_changed(self, key, value):
        """Any time a preference changes, this gets notified so that we
        can adjust things.
        """
        if key == options.SHOW_TRAYICON.key:
            self.trayicon.set_visible(value)

        elif key == prefs.RUN_DTV_AT_STARTUP.key:
            self.update_autostart()

        elif key == options.VIZ_PLUGIN.key:
            if hasattr(app, "renderer") and app.renderer:
                app.renderer.change_visualization(value)

    def build_window(self):
        Application.build_window(self)
        self.window.connect('save-dimensions', self.set_main_window_dimensions)
        self.window.connect('save-maximized', self.set_main_window_maximized)

        maximized = self.get_main_window_maximized()
        if maximized != None:
            if maximized:
                self.window._window.maximize()
            else:
                self.window._window.unmaximize()

        if trayicon.trayicon_is_supported:
            self.trayicon = trayicon.Trayicon(resources.sharePath("pixmaps/miro-24x24.png"))
            if config.get(options.SHOW_TRAYICON):
                self.trayicon.set_visible(True)
            else:
                self.trayicon.set_visible(False)
            config.add_change_callback(self.on_pref_changed)

        self.window._window.set_icon_from_file(resources.sharePath('pixmaps/miro-128x128.png'))

    def quit_ui(self):
        gtk.main_quit()

    def update_autostart(self):
        if check_kde():
            if os.environ.get("KDE_SESSION_VERSION") == "4":
                autostart_dir = "~/.kde/share/autostart"
            else:
                autostart_dir = "~/.kde/Autostart"
        else:
            config_home = os.environ.get('XDG_CONFIG_HOME', '~/.config')
            autostart_dir = os.path.join(config_home, "autostart")

        autostart_dir = os.path.expanduser(autostart_dir)
        logging.debug("autostart_dir: %s", autostart_dir)
        destination = os.path.join(autostart_dir, "miro.desktop")
        if config.get(prefs.RUN_DTV_AT_STARTUP):
            if os.path.exists(destination):
                return
            try:
                if not os.path.exists(autostart_dir):
                    os.makedirs(autostart_dir)
                shutil.copy(resources.sharePath('applications/miro.desktop'),
                            destination)
            except OSError:
                logging.exception("Problems creating or populating autostart dir.")

        else:
            if not os.path.exists(destination):
                return
            try:
                os.remove(destination)
            except OSError:
                logging.exception("Problems removing autostart dir.")

    def open_url(self, url):
        # We could use Python's webbrowser.open() here, but
        # unfortunately, it doesn't have the same semantics under UNIX
        # as under other OSes. Sometimes it blocks, sometimes it doesn't.
        if check_kde():
            os.spawnlp (os.P_NOWAIT, "kfmclient", "kfmclient", "exec", url)
        else:
            os.spawnlp (os.P_NOWAIT, "gnome-open", "gnome-open", url)

    def open_file(self, filename):
        if not os.path.isdir(filename):
            filename = os.path.dirname(filename)

        if check_kde():
            os.spawnlp(os.P_NOWAIT, "kfmclient", "kfmclient", "exec", "file://" + filename)
        else:
            os.spawnlp(os.P_NOWAIT, "nautilus", "nautilus", "file://" + filename)

    def get_clipboard_text(self):
        """Pulls text from the clipboard and returns it.

        This text is not filtered/transformed in any way--that's the job of
        the caller.
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
                and config.get(options.SHOW_TRAYICON)):
            notification.attach_to_status_icon(self.trayicon)
        if timeout:
            notification.set_timeout(timeout)
        notification.show()
