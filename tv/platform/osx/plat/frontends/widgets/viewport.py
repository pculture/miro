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

"""miro.plat.frontends.widgets.viewport.py -- Viewport classes

A Viewport represents the area where a Widget is located.
"""

from objc import YES, NO, nil

class Viewport(object):
    """Used when a widget creates it's own NSView."""
    def __init__(self, view, initial_frame):
        self.view = view
        self.view.setFrame_(initial_frame)

    def reposition(self, rect):
        """Move the viewport to a differennt position."""
        self.view.setFrame_(rect)

    def remove(self):
        self.view.removeFromSuperview()

    def area(self):
        """Area of our view that is occupied by the viewport."""
        return self.view.bounds()

    def queue_redraw(self):
        """Make the viewport redraw itself."""

    def get_width(self):
        return self.view.frame().size.width

    def get_height(self):
        return self.view.frame().size.height

    def queue_redraw(self):
        opaque_view = self.view.opaqueAncestor()
        rect = opaque_view.convertRect_fromView_(self.view.bounds(), self.view)
        opaque_view.setNeedsDisplayInRect_(rect)

class BorrowedViewport(Viewport):
    """Used when a widget uses the NSView of one of it's ancestors.  We store
    the view that we borrow as well as an NSRect specifying where on that view
    we are placed.
    """
    def __init__(self, view, placement):
        self.view = view
        self.placement = placement

    def reposition(self, rect):
        self.placement = rect

    def remove(self):
        pass

    def area(self):
        return self.placement

    def get_width(self):
        return self.placement.size.width

    def get_height(self):
        return self.placement.size.height

    def queue_redraw(self):
        opaque_view = self.view.opaqueAncestor()
        rect = opaque_view.convertRect_fromView_(self.placement, self.view)
        opaque_view.setNeedsDisplayInRect_(rect)
