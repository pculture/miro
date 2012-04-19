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

import pygtk
pygtk.require("2.0")
import gtk
import gobject
import appindicator
if not hasattr(appindicator.Indicator, 'set_icon_theme_path'):
    # looks like there's no versionining in appindicator, so we do this
    # to make sure we have a version of appindicator that has the
    # things we need.  amongst other things, this prevents the appindicator
    # code from kicking off on Ubuntu Lucid where it doesn't work.
    # bug #17445.
    raise ImportError

from miro.gtcache import gettext as _

from miro import app
from miro import eventloop
from miro import messages
from miro import prefs
from miro.frontends.widgets import prefpanel
from miro.frontends.widgets.gtk import window as window_mod
from miro.plat import resources

# Note: this requires GTK+ version 2.10 or newer.

class MiroAppIndicator:
    """Implements the trayicon.  It produces the same menu 
       as the trayicon, but updates the menu based
       on callbacks instead of user clicks. Also both
       left and right click show/hide the menu.
    """
    def __init__(self, icon):
        self.indicator = appindicator.Indicator(
            app.config.get(prefs.SHORT_APP_NAME),
            icon,
            appindicator.CATEGORY_APPLICATION_STATUS)
        self.indicator.set_status(appindicator.STATUS_PASSIVE)
        self.menu_items = []
        self.indicator.set_icon_theme_path(resources.share_path('icons'))
        self.calculate_popup_menu()

        #FIXME: this is a bit of a hack since the signal probably
        # wasn't meant to be used this way. However, it is emitted
        # every time app.menu_manager.update_menus() is called
        # and therefore it covers all situations where we want to
        # update the app indicator menu. The signal is also emitted 
        # sometimes when no update to the app indicator menu is needed
        # (espcecially during downloads). Therefore we later only set 
        # a new app indicator menu if there actually is a change in 
        # the menu text. This avoids a flickering menu.
        app.menu_manager.connect('menus-updated', self._on_menu_update)

    def _on_menu_update(self, manager, reason):
        self.calculate_popup_menu()

    def set_visible(self, visible):
        if visible:
            self.indicator.set_status(appindicator.STATUS_ACTIVE)
        else:
            self.indicator.set_status(appindicator.STATUS_PASSIVE)

    def make_popup_menu_items(self):
        menu_items = []
        window = app.widgetapp.window
        if window._window is None or hasattr(window, '_closing'):
            # The main window was destroyed, but we still ended up here somehow
            # (#18937).  Don't bother doing anything else.
            return None

        if app.playback_manager.is_playing:
            if app.playback_manager.is_paused:
                menu_items.append(
                    (gtk.STOCK_MEDIA_PLAY, self.on_play_pause))
            else:
                menu_items.append(
                    (gtk.STOCK_MEDIA_PAUSE, self.on_play_pause))
            menu_items.append((gtk.STOCK_MEDIA_STOP, self.on_stop))
            menu_items.append((gtk.STOCK_MEDIA_NEXT, self.on_next))
            menu_items.append((gtk.STOCK_MEDIA_PREVIOUS, self.on_previous))
            menu_items.append((None, None))
        else:
            # We need to see if there are playable items before we
            # go forward with adding that menu option.
            for item in app.item_list_controller_manager.get_selection():
                if item.downloaded:
                    # Yay!  We found a playable item.
                    menu_items.append(
                        (gtk.STOCK_MEDIA_PLAY, self.on_play_pause))
                    menu_items.append((None, None))
                    break

        if ((app.playback_manager.is_playing and
            app.playback_manager.item_continuous_playback_mode(
                    app.playback_manager.playlist.currently_playing))):
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

    def calculate_popup_menu(self):
        menu_items = self.make_popup_menu_items()
        if menu_items is None:
            return
        if self.menu_items != menu_items:
            popup_menu = gtk.Menu()
            for label, callback in menu_items:
                if not label and not callback:
                    item = gtk.SeparatorMenuItem()
                else:
                    item = gtk.ImageMenuItem(label)
                    item.connect('activate', callback)
                popup_menu.append(item)

            popup_menu.show_all()
            self.indicator.set_menu(popup_menu)
            self.menu_items = menu_items

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

    def on_play_pause(self, widget):
        app.widgetapp.on_play_clicked()

    def on_stop(self, widget):
        app.widgetapp.on_stop_clicked()

    def on_previous(self, widget):
        app.widgetapp.on_previous_clicked()

    def on_next(self, widget):
        app.widgetapp.on_forward_clicked()

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
        self.calculate_popup_menu()

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
        self.calculate_popup_menu()

    def on_click(self, widget):
        window = app.widgetapp.window
        if window.is_visible():
            self._hide_window()
        else:
            self._show_window()

