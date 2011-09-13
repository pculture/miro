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

_dummy_window = None
def _get_dummy_window():
    """Get a hidden window to reparent gstreamer windows to.

    These windows are used when the GtkVideoWidget isn't currently realized.

    This method creates the hidden window lazily, as a singleton.
    """
    global _dummy_window
    if _dummy_window is None:
        _dummy_window = gtk.gdk.Window(None,
                x=0, y=0, width=1, height=1,
                window_type=gtk.gdk.WINDOW_TOPLEVEL,
                wclass=gtk.gdk.INPUT_OUTPUT, event_mask=0)
    return _dummy_window

class GtkVideoWidget(gtk.DrawingArea):
    """GtkVideoWidget -- GTK widget for embedding gstreamer."""

    def __init__(self, renderer):
        gtk.DrawingArea.__init__(self)
        self.renderer = renderer
        # make a window for gstreamer to use.  This window stays around, even
        # when the widget is unrealized.
        # This is a bit of cheating because we are not supposed to create
        # windows until we get the realize signal.  However, this is the
        # simplest way to get gstreamer working.
        self.gstreamer_window = gtk.gdk.Window(_get_dummy_window(),
                x=0, y=0, width=1, height=1, window_type=gtk.gdk.WINDOW_CHILD,
                wclass=gtk.gdk.INPUT_OUTPUT, event_mask=self.get_events())
        # make sure it's a native window, otherwise gstreamer gets confused
        pygtkhacks.ensure_native_window(self.gstreamer_window)
        # pass it to our renderer
        self.renderer.set_window_id(self.gstreamer_window.xid)

    def do_realize(self):
        # call base class
        gtk.DrawingArea.do_realize(self)
        # move our gstreamer_window on top of our regular window.
        self.gstreamer_window.resize(*self.window.get_size())
        self.gstreamer_window.reparent(self.window, 0, 0)
        self.gstreamer_window.show()
        # set user data so that events on gstreamer_window go to this widget
        self.gstreamer_window.set_user_data(self)
        self.gstreamer_window.set_events(self.get_events())

    def do_unrealize(self):
        # hide our gstreamer_window and reparent it to a hidden window
        self.gstreamer_window.reparent(_get_dummy_window(), 0, 0)
        # unset user data
        self.gstreamer_window.set_user_data(None)
        # call base class
        gtk.DrawingArea.do_unrealize(self)

    def do_size_allocate(self, allocation):
        gtk.DrawingArea.do_size_allocate(self, allocation)
        if self.flags() & gtk.REALIZED:
            # resize our gstreamer window.  We don't have to move it because
            # it always should be at (0, 0) relative to our regular window.
            self.gstreamer_window.resize(allocation.width, allocation.height)

    def do_motion_notify_event(self, event):
        wrappermap.wrapper(self).emit('mouse-motion')

    def do_button_press_event(self, event):
        if event.type == gtk.gdk._2BUTTON_PRESS:
            wrappermap.wrapper(self).emit('double-click')

    def do_expose_event(self, event):
        if self.renderer.ready_for_expose():
            # our renderer is setup, have it handle the expose
            self.renderer.expose()
        else:
            # our renderer is not ready yet, draw black
            cr = event.window.cairo_create()
            cr.set_source_rgb(0, 0, 0)
            cr.rectangle(*event.area)
            cr.fill()

    def destroy(self):
        # unrealize if we need to
        if self.flags() & gtk.REALIZED:
            self.unrealize()
        # unset our renderer window
        self.renderer.set_window_id(None)
        # destroy our gstreamer window
        self.gstreamer_window.destroy()
        # let DrawingArea take care of the rest
        gtk.DrawingArea.destroy(self)

    def add_events(self, mask):
        gtk.DrawingArea.add_events(self, mask)
        self.gstreamer_window.set_events(self.get_events())

    def set_events(self, mask):
        gtk.DrawingArea.set_events(self, mask)
        self.gstreamer_window.set_events(self.get_events())
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
        self._widget.add_events(gtk.gdk.BUTTON_PRESS_MASK |
                gtk.gdk.POINTER_MOTION_MASK)

    def destroy(self):
        self._widget.destroy()
