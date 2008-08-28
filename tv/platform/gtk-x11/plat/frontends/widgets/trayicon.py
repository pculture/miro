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

import pygtk
pygtk.require("2.0")
import gtk
from gettext import gettext as _

from miro import app

trayicon_is_supported = False

# first check to see whether the version of GTK+ natively supports
# trayicons (the GtkStatusIcon widget).  Specifically we are looking
# for GTK+ version 2.10 or newer.  If we have it, we use our native
# python implementation.
if gtk.check_version(2,10,0) == None:        
    trayicon_is_supported = True
    class Trayicon(gtk.StatusIcon):
        def __init__(self, icon, main_frame):
            gtk.StatusIcon.__init__(self)
            self.main_frame = main_frame
            self.set_from_file(icon)
            self.set_visible(False)
            self.connect("activate", self.on_click)
            self.connect("popup-menu", self.on_popup_menu)

        def make_popup_menu_items(self):
            #cb_handler = self.main_frame.callbackHandler
            menu_items = []
            window = self.main_frame.window
            if window.is_visible():
                menu_items.append((_("Hide"), self.on_click))
            else:
                menu_items.append((_("Show"), self.on_click))
            menu_items.append((gtk.STOCK_PREFERENCES, self.on_preferences))
            menu_items.append((gtk.STOCK_QUIT, self.on_quit))
            return menu_items

        def on_popup_menu(self, status_icon, button, activate_time):
            popup_menu = gtk.Menu()
            for label, callback in self.make_popup_menu_items():
                item = gtk.ImageMenuItem(label)
                item.connect('activate', callback)
                popup_menu.append(item)

            popup_menu.show_all()
            popup_menu.popup(None, None, gtk.status_icon_position_menu,
                    button, activate_time, status_icon)

        def on_preferences(self, widget):
            app.widgetapp.preferences()

        def on_quit(self, widget):
            app.widgetapp.quit()

        def on_click(self, widget):
            window = self.main_frame.window
            if window.is_visible():
                window.close()
            else:
                window.show()

        def displayNotification(self, text):
            try:
                import pynotify
            except ImportError:
                return
            n = pynotify.Notification()
            n.set_property("status-icon", self)
            n.show()

# if we don't have GTK+ 2.10, then try to import our custom module,
# based on the older libegg code.
else:
    try:
        import _trayicon
        class Trayicon(_trayicon.Trayicon):
            pass
        trayicon_is_supported = True
    except ImportError:
        pass
