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

"""miro.frontends.widgets.gtk.widgets -- Contains portable implementations of
the GTK Widgets.  These are shared between the windows port and the x11 port.
"""

import gtk

from miro import app

# Just use the GDK Rectangle class
class Rect(gtk.gdk.Rectangle):
    @classmethod
    def from_string(cls, rect_string):
        x, y, width, height = [int(i) for i in rect_string.split(',')]
        return Rect(x, y, width, height)

    def __str__(self):
        return "%d,%d,%d,%d" % (self.x, self.y, self.width, self.height)

    def get_width(self):
        return self.width

class Window:
    """The main Miro window.  """

    def __init__(self, title, rect):
        """Create the Miro Main Window.  Title is the name to give the window,
        rect specifies the position it should have on screen.
        """
        self._widget = gtk.Window()
        self._widget.set_title(title)
        self._widget.set_default_size(rect.width, rect.height)
        self._widget.connect('delete-event', self.on_delete)

    def on_delete(self, widget, event):
        app.widgetapp.quit()
        return True

    def close(self):
        self._widget.destroy()

    def set_content_widget(self, widget):
        """Set the widget that will be drawn in the content area for this
        window.

        It will be allocated the entire area of the widget, except the space
        needed for the titlebar, frame and other decorations.  When the window
        is resized, content should also be resized.
        """
        self._widget.add(widget._widget)
        self._widget.child.show()

    def get_content_widget(self, widget):
        """Get the current content widget."""

    def show(self):
        """Display the window on screen."""
        self._widget.show()
