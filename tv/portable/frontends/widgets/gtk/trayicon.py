# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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

import os
import pygtk
pygtk.require("2.0")
import gtk
from miro.gtcache import gettext as _

from miro import app
from miro import messages
from miro import config
from miro import prefs
from miro.frontends.widgets import prefpanel
from miro.frontends.widgets.gtk import window as window_mod

trayicon_is_supported = False

# First check to see whether the version of GTK+ natively supports
# trayicons (the GtkStatusIcon widget).  Specifically we are looking
# for GTK+ version 2.10 or newer.
if gtk.check_version(2, 10, 0) == None:
    trayicon_is_supported = True

    class Trayicon(gtk.StatusIcon):
        def __init__(self, icon):
            gtk.StatusIcon.__init__(self)
            if os.sep in icon:
                self.set_from_file(icon)
            else:
                self.set_from_icon_name(icon)
            self.set_visible(False)
            self._hid_pref_panel = False
            self.connect("activate", self.on_click)
            self.connect("popup-menu", self.on_popup_menu)

        def make_popup_menu_items(self):
            menu_items = []
            window = app.widgetapp.window

            if config.get(prefs.SINGLE_VIDEO_PLAYBACK_MODE):
                menu_items.append((_("Play Next Unplayed (%(unplayed)d)",
                                {"unplayed": app.widgetapp.unwatched_count}),
                        self.on_play_unwatched))
            else:
                menu_items.append((_("Play All Unplayed (%(unplayed)d)",
                                {"unplayed": app.widgetapp.unwatched_count}),
                        self.on_play_unwatched))
            menu_items.append((_("Pause All Downloads (%(downloading)d)",
                            {"downloading": app.widgetapp.download_count}),
                    self.on_pause_downloads))
            menu_items.append((_("Resume All Downloads (%(paused)d)",
                            {"paused": app.widgetapp.paused_count}),
                    self.on_resume))

            menu_items.append((None, None))
            menu_items.append((gtk.STOCK_PREFERENCES, self.on_preferences))
            menu_items.append((None, None))
            if window.is_visible():
                menu_items.append((_("Hide"), self.on_click))
            else:
                menu_items.append((_("Show"), self.on_click))
            menu_items.append((gtk.STOCK_QUIT, self.on_quit))
            return menu_items

        def on_popup_menu(self, status_icon, button, activate_time):
            popup_menu = gtk.Menu()
            for label, callback in self.make_popup_menu_items():
                if not label and not callback:
                    item = gtk.SeparatorMenuItem()
                else:
                    item = gtk.ImageMenuItem(label)
                    item.connect('activate', callback)
                popup_menu.append(item)

            popup_menu.show_all()
            popup_menu.popup(None, None, gtk.status_icon_position_menu,
                    button, activate_time, status_icon)

        def on_play_unwatched(self, widget):
            self._show_window()
            messages.PlayAllUnwatched().send_to_backend()

        def on_pause_downloads(self, widget):
            messages.PauseAllDownloads().send_to_backend()

        def on_resume(self, widget):
            messages.ResumeAllDownloads().send_to_backend()

        def on_preferences(self, widget):
            self._show_window()
            app.widgetapp.preferences()

        def on_quit(self, widget):
            app.widgetapp.quit()

        def _show_window(self):
            window = app.widgetapp.window
            if window.is_visible():
                return
            window.show()
            window._window.deiconify()
            if self._hid_pref_panel:
                prefpanel.show_window()

        def _hide_window(self):
            window = app.widgetapp.window
            if not window.is_visible():
                return
            window.close()
            for dialog in window_mod.running_dialogs:
                dialog._window.hide()
            if prefpanel.is_window_shown():
                self._hid_pref_panel = True
                prefpanel.hide_window()
            else:
                self._hid_pref_panel = False

        def on_click(self, widget):
            window = app.widgetapp.window
            if window.is_visible():
                self._hide_window()
            else:
                self._show_window()

        def displayNotification(self, text):
            try:
                import pynotify
            except ImportError:
                return
            n = pynotify.Notification()
            n.set_property("status-icon", self)
            n.show()
