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
from miro.plat.frontends.widgets import embeddingwidget

class GtkVideoWidget(embeddingwidget.EmbeddingWidget):
    """GtkVideoWidget -- GTK widget for embedding gstreamer."""

    def __init__(self, renderer):
        embeddingwidget.EmbeddingWidget.__init__(self)
        self.embedding_window.enable_motion_events(True)
        self.renderer = renderer
        self.renderer.set_window_id(self.embedding_window.hwnd)

    def destroy(self):
        # stop our renderer
        self.renderer.reset()
        self.renderer.set_window_id(None)
        # let EmbeddingWidget take care of the rest
        embeddingwidget.EmbeddingWidget.destroy(self)

    # EmbeddingWindow callbacks

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
