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

"""searchentry.py -- Search entry text box.
"""

import gobject
import gtk

from miro import searchengines
from miro.frontends.widgets.gtk import controls
from miro.frontends.widgets.gtk import pygtkhacks
from miro.plat import resources

class GtkSearchTextEntry(gtk.Entry):
    def __init__(self):
        gtk.Entry.__init__(self)
        # By default the border is 2 pixels.  Give an extra 16 pixels for the
        # icon and 4 pixels for padding on the left side.
        pygtkhacks.set_entry_border(self, 2, 2, 2, 22)
        self.menu = gtk.Menu()
        self._engine_to_pixbuf = {}
        for engine in searchengines.get_search_engines():
            self._add_engine(engine)
        self.select_engine(searchengines.get_last_engine())

    def _add_engine(self, engine):
        icon_path = resources.path('images/search_icon_%s.png' % engine.name)
        pixbuf = gtk.gdk.pixbuf_new_from_file(icon_path)
        self._engine_to_pixbuf[engine] = pixbuf
        image = gtk.Image()
        image.set_from_pixbuf(pixbuf)
        menu_item = gtk.ImageMenuItem()
        menu_item.set_image(image)
        menu_item.connect('activate', self._on_menu_item_activate, engine)
        menu_item.show()
        self.menu.append(menu_item)

    def _on_menu_item_activate(self, item, engine):
        self.select_engine(engine)

    def select_engine(self, engine):
        self.pixbuf = self._engine_to_pixbuf[engine]
        self._engine = engine
        self.queue_draw()

    def selected_engine(self):
        return self._engine

    def _calc_image_position(self):
        layout_offsets = self.get_layout_offsets()
        # x and y are a bit artificial.  They are just what looked good to me
        # at the time (BDK)
        x = layout_offsets[0] - 22
        y = layout_offsets[1] - 1
        if self.flags() & gtk.NO_WINDOW:
            x += self.allocation.x
            y += self.allocation.y
        return x, y

    def _event_inside_icon(self, event):
        x, y = self._calc_image_position()
        return (x <= event.x < x + 16) and (y <= event.y < y + 16)

    def do_expose_event(self, event):
        gtk.Entry.do_expose_event(self, event)
        x, y = self._calc_image_position()
        event.window.draw_pixbuf(None, self.pixbuf, 0, 0, x, y, 16, 16)

    def do_button_press_event(self, event):
        if self._event_inside_icon(event):
            self.menu.popup(None, None, None, event.button, event.time)
        else:
            gtk.Entry.do_button_press_event(self, event)

    def do_realize(self):
        gtk.Entry.do_realize(self)
        # Create an INPUT_ONLY window to change the icon to a pointer when
        # it's over the icon.
        x, y = self._calc_image_position()
        self.icon_window = gtk.gdk.Window(self.window, 16, 16,
                gtk.gdk.WINDOW_CHILD, 0, gtk.gdk.INPUT_ONLY, x=x, y=y)
        self.icon_window.set_cursor(gtk.gdk.Cursor(gtk.gdk.ARROW))
        self.icon_window.show()

    def do_unrealize(self):
        self.icon_window.hide()
        del self.icon_window
        gtk.Entry.do_unrealize(self)

gobject.type_register(GtkSearchTextEntry)

class SearchTextEntry(controls.TextEntry):
    entry_class = GtkSearchTextEntry

class VideoSearchTextEntry(SearchTextEntry):
    def __init__(self):
        SearchTextEntry.__init__(self)
        self.wrapped_widget_connect('key-release-event', self.on_key_release)

    def on_key_release(self, widget, event):
        # FIXME - not sure if there's a better way to test for Return or not.
        if gtk.gdk.keyval_name(event.keyval) == 'Return':
            self.emit('validate')

    # TODO: implement the inline engines popup menu
    def selected_engine(self):
        return self._widget.selected_engine()

