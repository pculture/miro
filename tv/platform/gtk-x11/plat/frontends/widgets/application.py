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

import traceback
import gtk
import os
import gconf

from miro import app
from miro import eventloop
from miro.frontends.widgets.application import Application
from miro.plat.frontends.widgets import threads
from miro.plat import mozsetup
from miro.plat.utils import setProperties
from miro.plat.config import gconf_lock

from miro.frontends.widgets.gtk.widgetset import Rect

import logging

def _getPref(key, getter_name):
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

def _setPref(key, setter_name, value):
    gconf_lock.acquire()
    try:
        client = gconf.client_get_default()
        fullkey = '/apps/miro/' + key
        setter = getattr(client, setter_name)
        setter(fullkey, value)
    finally:
        gconf_lock.release()

def getInt(key): return _getPref('window/' + key, 'get_int')
def getBool(key): return _getPref('window/' + key, 'get_bool')
def getPlayerInt(key): return _getPref(key, 'get_int')
def getPlayerBool(key): return _getPref(key, 'get_bool')

def setInt(key, value): return _setPref('window/' + key, 'set_int', value)
def setBool(key, value): return _setPref('window/' + key, 'set_bool', value)
def setPlayerInt(key, value): return _setPref(key, 'set_int', value)
def setPlayerBool(key, value): return _setPref(key, 'set_bool', value)


class GtkX11Application(Application):
    def run(self, props_to_set):
        threads.call_on_ui_thread(mozsetup.setupMozillaEnvironment)
        gtk.gdk.threads_init()
        self.startup()
        setProperties(props_to_set)
        self.in_kde = None

        logging.info("Gtk+ version:      %s", gtk.gtk_version)
        logging.info("PyGObject version: %s", gtk.ver)
        logging.info("PyGtk version:     %s", gtk.pygtk_version)
        langs = ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")
        langs = [(l, os.environ.get(l)) for l in langs if os.environ.get(l)]
        logging.info("Language:          %s", langs)

        gtk.main()
        app.controller.onShutdown()

    def buildUI(self):
        Application.buildUI(self)
        self.window.connect('save-dimensions', self.set_main_window_dimensions)

    def quit_ui(self):
        gtk.main_quit()

    def open_url(self, url):
        # We could use Python's webbrowser.open() here, but
        # unfortunately, it doesn't have the same semantics under UNIX
        # as under other OSes. Sometimes it blocks, sometimes it doesn't.
        if (self.check_kde()):
            os.spawnlp (os.P_NOWAIT, "kfmclient", "kfmclient", "exec", url)
        else:
            os.spawnlp (os.P_NOWAIT, "gnome-open", "gnome-open", url)

    def check_kde(self):
        if self.in_kde is None:
            self.in_kde = os.environ.get("KDE_FULL_SESSION", False)
        return self.in_kde

    def get_main_window_dimensions(self):
        x = getInt("x") or 100
        y = getInt("y") or 300
        width = getInt("width") or 800
        height = getInt("height") or 600

        return Rect(x, y, width, height)

    def set_main_window_dimensions(self, window, x, y, width, height):
        setInt("width", width)
        setInt("height", height)
        setInt("x", x)
        setInt("y", y)
