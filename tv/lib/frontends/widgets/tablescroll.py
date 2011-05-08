# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
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

"""tablescroll.py -- High-level scroll management. This ensures that behavior
like scroll_to_item works the same way across platforms.
"""

from miro.errors import WidgetActionError

import logging

class ScrollbarOwnerMixin(object):
    """Scrollbar management for TableView.
    
    External methods have undecorated names; internal methods start with _.

    External methods:
    - handle failure themselves (e.g. return None or retry later)
    - return basic data types (e.g. (x, y) tuples)
    - use "tree" coordinates
        
    Internal methods (intended to be used by ScrollbarOwnerMixin and the
    platform implementations):
    - raise WidgetActionError subclasses on failure
    - use Rect/Point structs
    - also use "tree" coordinates
    """
    def __init__(self):
        pass

    def scroll_to_iter(self, iter_, auto=False):
        """If auto is not set, always centers the given iter.
        
        With auto set, scrolls to the given iter if we're auto-scrolling, or if
        the iter is recapturing the scroll by passing the current position.
        """
        try:
            item = self._get_item_area(iter_)
            visible = self._get_visible_area()
            manually_scrolled = self._manually_scrolled
        except WidgetActionError:
            return
        visible_bottom = visible.y + visible.height
        visible_middle = visible.y + visible.height // 2
        item_bottom = item.y + item.height
        item_middle = item.y + item.height // 2
        in_top = item_bottom >= visible.y and item.y <= visible_middle
        in_bottom = item_bottom >= visible_middle and item.y <= visible_bottom
        if not auto or in_bottom or (not manually_scrolled and not in_top):
            destination = item_middle - visible.height // 2
            try:
                self._set_vertical_scroll(destination)
            except WidgetActionError:
                return

    def reset_scroll(self):
        """To scroll back to the origin; platform code might want to do
        something special to forget the current position when this happens.
        """
        self.set_scroll_position((0, 0))

    def get_scroll_position(self):
        """Returns the current scroll position, or None if not ready."""
        try:
            return tuple(self._get_scroll_position())
        except WidgetActionError:
            return None

    def _set_vertical_scroll(self, pos):
        """Helper to set our vertical position without affecting our horizontal
        position.
        """
        # FIXME: shouldn't reset horizontal position
        self.set_scroll_position((0, pos))
