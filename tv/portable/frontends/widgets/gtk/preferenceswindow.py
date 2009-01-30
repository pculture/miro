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

"""preferenceswindow.py -- Preferences window. """

import gtk
import gobject

from miro.frontends.widgets.gtk import layout
from miro.frontends.widgets.gtk import simple
from miro.frontends.widgets.gtk import window
from miro.frontends.widgets.gtk import wrappermap
from miro.plat import resources

class PreferencesWindow(window.Window):
    def __init__(self, title):
        window.Window.__init__(self, title)
        self.tab_container = layout.TabContainer()
        self.content_widget = gtk.VBox(spacing=12)
        self.content_widget.pack_start(self.tab_container._widget)
        close_button = gtk.Button(stock=gtk.STOCK_CLOSE)
        close_button.connect_object('clicked', gtk.Window.hide, self._window)
        alignment = gtk.Alignment(xalign=1.0)
        alignment.set_padding(0, 10, 0, 10)
        alignment.add(close_button)
        self.content_widget.pack_start(alignment)
        self._window.add(self.content_widget)
        self.connect('will-close', self.on_close)

    def on_close(self, window):
        gtk.Window.hide_on_delete(self._window)

    def append_panel(self, name, panel, title, image_name):
        image = simple.Image(resources.path(image_name))
        self.tab_container.append_tab(panel, title, image)

    def finish_panels(self):
        self.content_widget.show_all()

    def select_panel(self, index):
        self.tab_container.select_tab(index)

    def show(self):
        self._window.show()
