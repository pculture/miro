# Miro - an RSS based video player application
# Copyright (C) 2011
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

"""embeddingwidget.py -- GTKWidget for embedding other components

class for our video and browser widgets.
"""

import gobject
import gtk

from miro.frontends.widgets.gtk import pygtkhacks
from miro.plat.frontends.widgets import embeddingwindow

# _live_widgets tracks the EmbeddingWidget that haven't had destroy() called
# on them yet
_live_widgets = set()

def init():
    embeddingwindow.init()

def shutdown():
    # XXX Force a destroy of all outstanding embedding widgets.  Otherwise we
    # may get mysterious hangs on Windows (bz18632).  But breaking this sort
    # of open reference is probably bad; we should investigate more how to fix
    # this properly.
    to_destroy = list(_live_widgets)
    for d in to_destroy:
        d.destroy()

class EmbeddingWidget(gtk.DrawingArea):
    """EmbeddingWidget -- GTK widget for embedding other components."""

    def __init__(self):
        gtk.DrawingArea.__init__(self)
        # Create an EmbeddingWindow to use
        self.embedding_window = embeddingwindow.EmbeddingWindow()
        self.embedding_window.set_event_handler(self)
        _live_widgets.add(self)

    def _get_window_area(self):
        """Get the area of our window relative to a native window

        This method calculates where our window is relative to it's nearest
        parent that's a native window.
        """

        offsets = pygtkhacks.get_gdk_window_offset(self.window)
        # offsets are relative to our window, we need to negate them to make
        # them relative to our native parent window.
        return (-offsets[0], -offsets[1], self.allocation.width,
                self.allocation.height)

    def do_realize(self):
        # call base class
        gtk.DrawingArea.do_realize(self)
        # attach our embedded window to our window
        self.embedding_window.attach(self.window.handle,
                                     *self._get_window_area())

    def do_unrealize(self):
        # detach our embedded window
        self.embedding_window.detach()
        # call base class
        gtk.DrawingArea.do_unrealize(self)

    def do_size_allocate(self, allocation):
        # call our base class
        gtk.DrawingArea.do_size_allocate(self, allocation)
        if self.flags() & gtk.REALIZED:
            # move our embedded window
            self.embedding_window.reposition(*self._get_window_area())

    def destroy(self):
        # NB: here we call the embedding_window's destroy() method after
        # the DrawingArea's destroy() because apparently DrawingArea's
        # destroy() can invoke do_unrealize(), which detaches the embedding
        # window.  Therefore only free the embedding_window after we
        # are adament that nobody can be using it.
        gtk.DrawingArea.destroy(self)
        self.embedding_window.destroy()
        self.embedding_window = None
        # let DrawingArea take care of the rest
        _live_widgets.discard(self)

    # EmbeddingWindow callback functions.  Child classes can overide these if
    # they need to handle the events
    def on_mouse_move(self, x, y):
        pass

    def on_double_click(self, x, y):
        pass

    def on_paint(self):
        pass

    def on_mouseactivate(self):
        pass
gobject.type_register(EmbeddingWidget)
