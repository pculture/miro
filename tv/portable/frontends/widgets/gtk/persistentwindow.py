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

"""persistentwindow.py -- Contains a GTK widget that displays a GDK window
that stays around as long as the widget is alive (i.e. after unrealize).  This
makes it a nice place to embed video renderers and XULRunner inside, since
they XWindow/HWND that we pass to them doesn't go away when the widget is
unrealized.
"""

import gtk
import gobject
import weakref

_dummy_window = gtk.gdk.Window(None,
        x=0, y=0, width=1, height=1,
        window_type=gtk.gdk.WINDOW_TOPLEVEL,
        wclass=gtk.gdk.INPUT_OUTPUT, event_mask=0)

_persistent_window_to_widget = weakref.WeakValueDictionary()

class PersistentWindow(gtk.DrawingArea):
    """GTK Widget that keeps around a GDK window from the time it's realized
    to the time it's destroyed.

    Attributes:

        persistent_window -- Window that we keep around
    """

    def __init__(self):
        gtk.DrawingArea.__init__(self)
        self.persistent_window = gtk.gdk.Window(_dummy_window,
                x=0, y=0, width=1, height=1, window_type=gtk.gdk.WINDOW_CHILD,
                wclass=gtk.gdk.INPUT_OUTPUT, event_mask=self.get_events())
        _persistent_window_to_widget[self.persistent_window] = self

    def set_events(self, event_mask):
        gtk.DrawingArea.set_events(self, event_mask)
        self.persistent_window.set_events(self.get_events())

    def add_events(self, event_mask):
        gtk.DrawingArea.add_events(self, event_mask)
        self.persistent_window.set_events(self.get_events())

    def do_realize(self):
        gtk.DrawingArea.do_realize(self)
        self.persistent_window.reparent(self.window, 0, 0)
        self.persistent_window.resize(self.allocation.width,
                self.allocation.height)
        self.persistent_window.show()
        self.persistent_window.set_events(self.get_events())
        self.persistent_window.set_user_data(self)

    def do_configure_event(self, event):
        self.persistent_window.resize(event.width, event.height)

    def do_size_allocate(self, allocation):
        gtk.DrawingArea.do_size_allocate(self, allocation)
        self.persistent_window.resize(allocation.width, allocation.height)

    def do_unrealize(self):
        self.persistent_window.set_user_data(None)
        self.persistent_window.hide()
        self.persistent_window.reparent(_dummy_window, 0, 0)
        gtk.DrawingArea.do_unrealize(self)

    def do_destroy(self):
        try:
            gtk.DrawingArea.do_destroy(self)
            self.persistent_window.destroy()
            self.persistent_window = None
        except AttributeError:
            # Probably means we're in shutdown, so our symbols have been
            # deleted
            pass
gobject.type_register(PersistentWindow)

def get_widgets():
    retval = []
    for window in _dummy_window.get_children():
        retval.append(_persistent_window_to_widget[window])
    return retval
