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

"""miro.plat.frontends.widgets.base.py -- Widget base classes."""

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

from miro import signals
from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets.viewport import Viewport, BorrowedViewport

class Widget(signals.SignalEmitter):
    """Base class for Cocoa widgets.
    
    attributes:

    CREATES_VIEW -- Does the widget create a view for itself?  If this is True
    the widget must have an attribute named view, which is the view that the
    widget uses.

    placement -- What portion of view the widget occupies.
    """

    CREATES_VIEW = True 

    def __init__(self):
        signals.SignalEmitter.__init__(self, 'size-request-changed')
        self.viewport = None
        self.manual_size_request = None
        self.cached_size_request = None
        self._disabled = False

    def set_size_request(self, width, height):
        self.manual_size_request = (width, height)
        self.invalidate_size_request()

    def get_size_request(self):
        if self.manual_size_request:
            width, height = self.manual_size_request
            if width == -1:
                width = self.get_natural_size_request()[0]
            if height == -1:
                height = self.get_natural_size_request()[1]
            return width, height
        return self.get_natural_size_request()

    def get_natural_size_request(self):
        if self.cached_size_request:
            return self.cached_size_request
        else:
            self.cached_size_request = self.calc_size_request()
            return self.cached_size_request

    def invalidate_size_request(self):
        """Recalculate the size request for this widget."""
        old_size_request = self.cached_size_request
        self.cached_size_request = None
        self.emit('size-request-changed', old_size_request)

    def calc_size_request(self):
        """Return the minimum size needed to display this widget.
        Must be Implemented by subclasses.  
        """
        raise NotImplementedError()

    def place(self, rect, containing_view):
        """Place this widget on a view.  """
        if self.viewport is None:
            if self.CREATES_VIEW:
                self.viewport = Viewport(self.view, rect)
                containing_view.addSubview_(self.view)
                wrappermap.add(self.view, self)
            else:
                self.viewport = BorrowedViewport(containing_view, rect)
            self.viewport_created()
        else:
            if not self.viewport.at_position(rect):
                self.viewport.reposition(rect)
                self.viewport_repositioned()

    def remove_viewport(self):
        self.viewport.remove()
        self.viewport = None
        if self.CREATES_VIEW:
            wrappermap.remove(self.view)

    def create_view(self, rect):
        """Implemented by subclasses with CREATES_VIEW set.  It must return a
        NSView with a frame size equal to rect.
        """
        raise NotImplementedError("%s has CREATES_VIEW set, but doesn't implement create_view" % self.__class__)

    def viewport_created(self):
        """Called after we first create a viewport.  Subclasses can override
        this method if they want to handle this event.
        """

    def viewport_repositioned(self):
        """Called when we reposition our viewport.  Subclasses can override
        this method if they want to handle this event.
        """

    def get_width(self):
        return int(self.viewport.get_width())
    width = property(get_width)

    def get_height(self):
        return int(self.viewport.get_height())
    height = property(get_height)

    def get_window(self):
        if not self.viewport.view:
            return None
        return wrappermap.wrapper(self.viewport.view.window())

    def queue_redraw(self):
        if self.viewport:
            self.viewport.queue_redraw()

    def relative_position(self, other_widget):
        """Get the position of another widget, relative to this widget."""
        basePoint = self.viewport.view.convertPoint_fromView_(
                other_widget.viewport.area().origin,
                other_widget.viewport.view)
        return (basePoint.x - self.viewport.area().origin.x,
                basePoint.y - self.viewport.area().origin.y)

    def make_color(self, (red, green, blue)):
        return NSColor.colorWithDeviceRed_green_blue_alpha_(red, green, blue, 
                1.0)

    def enable_widget(self):
        self._disabled = False

    def disable_widget(self):
        self._disabled = True

    def get_disabled(self):
        return self._disabled

class Container(Widget):
    """Widget that holds other widgets.  """

    def __init__(self):
        Widget.__init__(self)
        self.callback_handles = {}

    def on_child_size_request_changed(self, child, old_size):
        self.children_changed()

    def connect_child_signals(self, child):
        handle = child.connect_weak('size-request-changed',
                self.on_child_size_request_changed)
        self.callback_handles[child] = handle

    def disconnect_child_signals(self, child):
        child.disconnect(self.callback_handles.pop(child))

    def remove_viewport(self):
        for child in self.children:
            child.remove_viewport()
        Widget.remove_viewport(self)

    def child_added(self, child):
        """Must be called by subclasses when a child is added to the
        Container."""
        self.connect_child_signals(child)
        self.children_changed()

    def child_removed(self, child):
        """Must be called by subclasses when a child is removed from the
        Container."""
        self.disconnect_child_signals(child)
        child.remove_viewport()
        self.children_changed()

    def child_changed(self, old_child, new_child):
        """Must be called by subclasses when a child is replaced by a new
        child in the Container.  To simplify things a bit for subclasses,
        old_child can be None in which case this is the same as
        child_added(new_child).
        """
        if old_child is not None:
            self.disconnect_child_signals(old_child)
        self.connect_child_signals(new_child)
        self.children_changed()

    def children_changed(self):
        self.invalidate_size_request()
        if self.viewport:
            self.place_children()
            self.queue_redraw()

    def viewport_created(self):
        self.place_children()

    def viewport_repositioned(self):
        self.place_children()

    def place_children(self):
        """Layout our child widgets.  Must be implemented by subclasses."""
        raise NotImplementedError()

class Bin(Container):
    """Container that only has one child widget."""

    def __init__(self, child=None):
        Container.__init__(self)
        self.child = None
        if child is not None:
            self.add(child)

    def get_children(self):
        if self.child:
            return [self.child]
        else:
            return []
    children = property(get_children)

    def add(self, child):
        if self.child is not None:
            raise ValueError("Already have a child: %s" % self.child)
        self.child = child
        self.child_added(self.child)

    def remove(self):
        if self.child is not None:
            old_child = self.child
            self.child = None
            self.child_removed(old_child)

    def set_child(self, new_child):
        old_child = self.child
        self.child = new_child
        self.child_changed(old_child, new_child)

    def enable_widget(self):
        Container.enable_widget(self)
        self.child.enable_widget()

    def disable_widget(self):
        Container.disable_widget(self)
        self.child.disable_widget()

class SimpleBin(Bin):
    """Bin that whose child takes up it's entire space."""

    def calc_size_request(self):
        if self.child is None:
            return (0, 0)
        else:
            return self.child.get_size_request()

    def place_children(self):
        if self.child:
            self.child.place(self.viewport.area(), self.viewport.view)

class FlippedView(NSView):
    """Flipped NSView.  We use these internally to lessen the differences
    between Cocoa and GTK.
    """

    def init(self):
        self = NSView.init(self)
        self.background = None
        return self

    def initWithFrame_(self, rect):
        self = NSView.initWithFrame_(self, rect)
        self.background = None
        return self

    def isFlipped(self):
        return YES

    def isOpaque(self):
        return self.background is not None

    def setBackgroundColor_(self, color):
        self.background = color

    def drawRect_(self, rect):
        if self.background:
            self.background.set()
            NSBezierPath.fillRect_(rect)
