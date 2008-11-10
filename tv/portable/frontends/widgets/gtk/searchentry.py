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
from miro.frontends.widgets.gtk.weakconnect import weak_connect
from miro.plat import resources

class GtkSearchTextEntry(gtk.EventBox):
    def __init__(self):
        gtk.EventBox.__init__(self)
        self.add_events(gtk.gdk.EXPOSURE_MASK)
        self.alignment = gtk.Alignment(yalign=0.5)
        self.entry = gtk.Entry()
        self.entry.set_has_frame(False)
        self.alignment.add(self.entry)
        self._align_entry()
        self.add(self.alignment)
        self.alignment.show_all()

        self.entry.connect('focus-in-event', self._entry_focus_change)
        self.entry.connect('focus-out-event', self._entry_focus_change)

        icon_path = resources.path('images/search_icon_all.png')
        self.pixbuf = gtk.gdk.pixbuf_new_from_file(icon_path)

    def _align_entry(self):
        # Make it so we handle the inner border of the entry ourselves.
        #
        # By default entries have 2px padding on all sides.  Change that to 0,
        # and make our Alignment widget handle it.
        # NOTE we use has 3px padding on the right side to compensate for the
        # fact that GTKEntry draws itself 1 extra pixel on the right
        #
        # We also want 6 px padding on the top, bottom and left sides of the
        # icon and 4 px padding on the right (because there is no border).
        # Since icons are 16x16, this gives us 26px padding on the left
        # and a minimum height of 28px
        pygtkhacks.set_entry_border(self.entry, 0, 0, 0, 0)
        self.alignment.set_padding(2, 2, 26, 3)
        self.min_height = 28

    def do_size_request(self, requesition):
        gtk.EventBox.do_size_request(self, requesition)
        if requesition.height < self.min_height:
            requesition.height = self.min_height

    def _entry_focus_change(self, entry, event):
        # Redraw our border to reflect the focus change.
        self.queue_draw()

    def _icon_position(self):
        x = 6
        y = (self.allocation.height - 16) / 2
        return x, y

    def do_expose_event(self, event):
        gtk.EventBox.do_expose_event(self, event)
        self.entry.style.paint_shadow(event.window, gtk.STATE_NORMAL,
                gtk.SHADOW_IN, event.area, self.entry, "entry",
                0, 0, self.allocation.width, self.allocation.height)
        x, y = self._icon_position()
        exposed = event.area.intersect(gtk.gdk.Rectangle(x, y, 16, 16))
        event.window.draw_pixbuf(None, self.pixbuf, exposed.x-x, exposed.y-y,
                exposed.x, exposed.y, exposed.width, exposed.height)

    # Forward a bunch of method calls to our gtk.Entry widget
    def get_text(self): return self.entry.get_text()
    def set_text(self, text): return self.entry.set_text(text)

gobject.type_register(GtkSearchTextEntry)

class SearchTextEntry(controls.TextEntry):
    entry_class = GtkSearchTextEntry

    def forward_signal(self, signal_name, forwarded_signal_name=None):
        if forwarded_signal_name is None:
            forwarded_signal_name = signal_name
        return weak_connect(self._widget.entry, signal_name,
                self.do_forward_signal, forwarded_signal_name)

class GtkVideoSearchTextEntry(GtkSearchTextEntry):
    def __init__(self):
        GtkSearchTextEntry.__init__(self)
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
        menu_item = gtk.ImageMenuItem(engine.title)
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

    def _event_inside_icon(self, event):
        x, y = self._icon_position()
        return (x <= event.x < x + 16) and (y <= event.y < y + 16)

    def do_button_press_event(self, event):
        if self._event_inside_icon(event):
            self.menu.popup(None, None, None, event.button, event.time)

gobject.type_register(GtkVideoSearchTextEntry)

class VideoSearchTextEntry(SearchTextEntry):
    entry_class = GtkVideoSearchTextEntry
    def __init__(self):
        controls.TextEntry.__init__(self)
        self.wrapped_widget_connect('key-release-event', self.on_key_release)

    def on_key_release(self, widget, event):
        if gtk.gdk.keyval_name(event.keyval) in ('Return', 'KP_Enter'):
            self.emit('validate')

    def selected_engine(self):
        return self._widget.selected_engine()

