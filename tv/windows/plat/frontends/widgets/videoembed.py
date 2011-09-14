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

"""Embed GStreamer Renderers.  """

import gobject
import gtk

from miro import signals
from miro.frontends.widgets.gtk import base
from miro.frontends.widgets.gtk import wrappermap
from miro.frontends.widgets.gtk import pygtkhacks
from miro.plat.frontends.widgets import embeddingwindow

class GtkVideoWidget(gtk.DrawingArea):
    """GtkVideoWidget -- GTK widget for embedding gstreamer."""

    def __init__(self, renderer):
        gtk.DrawingArea.__init__(self)
        self.renderer = renderer
        # make a HWND for gstreamer to use.
        self.embedding_window = embeddingwindow.EmbeddingWindow()
        self.embedding_window.set_event_handler(self)
        self.embedding_window.enable_motion_events(True)
        # pass it to our renderer
        self.renderer.set_window_id(self.embedding_window.hwnd)

    def _get_window_area(self):
        """Get the area of our window relative to a native window

        This method calculates where our window is relative to it's nearest
        parent that's a native window.
        """

        offsets = pygtkhacks.get_gdk_window_offset(self.window)
        # offsets are relative to our window, we need to negate them to make
        # them relative to our native parent window.
        return (-offsets[0], -offsets[1],
                self.allocation.width, self.allocation.height)

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

    def on_mouse_move(self, x, y):
        wrappermap.wrapper(self).emit('mouse-motion')

    def on_double_click(self, x, y):
        wrappermap.wrapper(self).emit('double-click')

    def on_paint(self):
        if self.renderer.ready_for_expose():
            # our renderer is setup, have it handle the expose
            self.renderer.expose()
        else:
            # our renderer is not ready yet, draw black
            self.embedding_window.paint_black()

    def destroy(self):
        # unrealize if we need to
        if self.flags() & gtk.REALIZED:
            self.unrealize()
        # stop our renderer
        self.renderer.reset()
        self.renderer.set_window_id(None)
        # destroy our embedding window
        self.embedding_window.destroy()
        self.embedding_window = None
        # let DrawingArea take care of the rest
        gtk.DrawingArea.destroy(self)
gobject.type_register(GtkVideoWidget)

class VideoWidget(base.Widget):
    """VideoWidget -- embed gstreamer inside a wrapped Widget

    VideoWidget takes care of everything needed to display a gstreamer
    renderer inside a widget.

    VideoWidget emits the following signals:

    - mouse-motion
    - double-click

    Note: code using VideoWidget should connect to it's signals, rather than
    the underlying GTK widget.  Platforms may create a window on top of normal
    one and change how event handling works.
    """

    def __init__(self, renderer):
        base.Widget.__init__(self)
        self.set_widget(GtkVideoWidget(renderer))
        self.create_signal("mouse-motion")
        self.create_signal("double-click")
        self.renderer = renderer

    def destroy(self):
        self._widget.destroy()
