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

"""miro.plat.frontends.widgets.layout -- Widgets that handle laying out other
widgets.

We basically follow GTK's packing model.  Widgets are packed into vboxes,
hboxes or other container widgets.  The child widgets request a minimum size,
and the container widgets allocate space for their children.  Widgets may get
more size then they requested in which case they have to deal with it.  In
rare cases, widgets may get less size then they requested in which case they
should just make sure they don't throw an exception or segfault.

Check out the GTK tutorial for more info.
"""

import itertools

from AppKit import *
from Foundation import *
from objc import YES, NO, nil
import WebKit

from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets.base import Container, Bin, FlippedView
from miro.plat.frontends.widgets.helpers import NotificationForwarder
from miro.util import Matrix

def _extra_space_iter(extra_length, count):
    """Utility function to allocate extra space left over in containers."""
    if count == 0:
        return
    extra_space, leftover = divmod(extra_length, count)
    while leftover >= 1:
        yield extra_space + 1
        leftover -= 1
    yield extra_space + leftover
    while True:
        yield extra_space

class BoxPacking:
    """Utility class to store how we are packing a single widget."""

    def __init__(self, widget, expand, padding):
        self.widget = widget
        self.expand = expand
        self.padding = padding

class Box(Container):
    """Base class for HBox and VBox.  """
    CREATES_VIEW = False

    def __init__(self, spacing=0):
        self.spacing = spacing
        Container.__init__(self)
        self.packing_start = []
        self.packing_end = []
        self.expand_count = 0

    def packing_both(self):
        return itertools.chain(self.packing_start, self.packing_end)

    def get_children(self):
        for packing in self.packing_both():
            yield packing.widget
    children = property(get_children)

    # Internally Boxes use a (length, breadth) coordinate system.  length and
    # breadth will be either x or y depending on which way the box is
    # oriented.  The subclasses must provide methods to translate between the
    # 2 coordinate systems.

    def translate_size(self, size):
        """Translate a (width, height) tulple to (length, breadth)."""
        raise NotImplementedError()

    def untranslate_size(self, size):
        """Reverse the work of translate_size."""
        raise NotImplementedError()

    def make_child_rect(self, position, length):
        """Create a rect to position a child with."""
        raise NotImplementedError()

    def pack_start(self, child, expand=False, padding=0):
        self.packing_start.append(BoxPacking(child, expand, padding))
        if expand:
            self.expand_count += 1
        self.child_added(child)

    def pack_end(self, child, expand=False, padding=0):
        self.packing_end.append(BoxPacking(child, expand, padding))
        if expand:
            self.expand_count += 1
        self.child_added(child)

    def _remove_from_packing(self, child):
        for i in xrange(len(self.packing_start)):
            if self.packing_start[i].widget is child:
                return self.packing_start.pop(i)
        for i in xrange(len(self.packing_end)):
            if self.packing_end[i].widget is child:
                return self.packing_end.pop(i)
        raise LookupError("%s not found" % child)

    def remove(self, child):
        packing = self._remove_from_packing(child)
        if packing.expand:
            self.expand_count -= 1
        self.child_removed(child)

    def translate_widget_size(self, widget):
        return self.translate_size(widget.get_size_request())

    def calc_size_request(self):
        length = breadth = 0
        for packing in self.packing_both():
            child_length, child_breadth = \
                    self.translate_widget_size(packing.widget)
            length += child_length
            if packing.padding:
                length += packing.padding * 2 # Need to pad on both sides
            breadth = max(breadth, child_breadth)
        spaces = max(0, len(self.packing_start) + len(self.packing_end) - 1)
        length += spaces * self.spacing
        return self.untranslate_size((length, breadth))

    def place_children(self):
        request_length, request_breadth = self.translate_widget_size(self)
        ps = self.viewport.placement.size
        total_length, dummy = self.translate_size((ps.width, ps.height))
        total_extra_space = total_length - request_length
        extra_space_iter = _extra_space_iter(total_extra_space,
                self.expand_count)
        start_end = self._place_packing_list(self.packing_start, 
                extra_space_iter, 0)
        if self.expand_count == 0:
            start_end += total_extra_space
        self._place_packing_list(reversed(self.packing_end), extra_space_iter, 
                start_end)

    def _place_packing_list(self, packing_list, extra_space_iter, position):
        for packing in packing_list:
            child_length, child_breadth = \
                    self.translate_widget_size(packing.widget)
            if packing.expand:
                child_length += extra_space_iter.next()
            position += packing.padding # space before
            child_rect = self.make_child_rect(position, child_length)
            position += packing.padding # space after
            packing.widget.place(child_rect, self.viewport.view)
            position += child_length + self.spacing
        return position

    def enable_widget(self):
        Container.enable_widget(self)
        for mem in self.children:
            mem.enable_widget()

    def disable_widget(self):
        Container.disable_widget(self)
        for mem in self.children:
            mem.disable_widget()

class VBox(Box):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def translate_size(self, size):
        return (size[1], size[0])

    def untranslate_size(self, size):
        return (size[1], size[0])

    def make_child_rect(self, position, length):
        placement = self.viewport.placement
        return NSMakeRect(placement.origin.x, placement.origin.y + position,
                placement.size.width, length)

class HBox(Box):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def translate_size(self, size):
        return (size[0], size[1])

    def untranslate_size(self, size):
        return (size[0], size[1])

    def make_child_rect(self, position, length):
        placement = self.viewport.placement
        return NSMakeRect(placement.origin.x + position, placement.origin.y,
                length, placement.size.height)

class Alignment(Bin):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    CREATES_VIEW = False

    def __init__(self, xalign=0.0, yalign=0.0, xscale=0.0, yscale=0.0,
            top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
        Bin.__init__(self)
        self.xalign = xalign
        self.yalign = yalign
        self.xscale = xscale
        self.yscale = yscale
        self.top_pad = top_pad
        self.bottom_pad = bottom_pad
        self.left_pad = left_pad
        self.right_pad = right_pad
        if self.child is not None:
            self.place_children()

    def set(self, xalign=0.0, yalign=0.0, xscale=0.0, yscale=0.0):
        self.xalign = xalign
        self.yalign = yalign
        self.xscale = xscale
        self.yscale = yscale
        if self.child is not None:
            self.place_children()

    def set_padding(self, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
        self.top_pad = top_pad
        self.bottom_pad = bottom_pad
        self.left_pad = left_pad
        self.right_pad = right_pad
        if self.child is not None:
            self.place_children()

    def vertical_pad(self):
        return self.top_pad + self.bottom_pad

    def horizontal_pad(self):
        return self.left_pad + self.right_pad

    def calc_size_request(self):
        if self.child:
            child_width, child_height = self.child.get_size_request()
            return (child_width + self.horizontal_pad(),
                    child_height + self.vertical_pad())
        else:
            return (0, 0)

    def calc_size(self, requested, total, scale):
        extra_width = max(0, total - requested)
        return requested + int(round(extra_width * scale))

    def calc_position(self, size, total, align):
        return int(round((total - size) * align))

    def place_children(self):
        if self.child is None:
            return

        total_width = self.viewport.placement.size.width
        total_height = self.viewport.placement.size.height
        total_width -= self.horizontal_pad()
        total_height -= self.vertical_pad()
        request_width, request_height = self.child.get_size_request()

        child_width = self.calc_size(request_width, total_width, self.xscale)
        child_height = self.calc_size(request_height, total_height, self.yscale)
        child_x = self.calc_position(child_width, total_width, self.xalign)
        child_y = self.calc_position(child_height, total_height, self.yalign)
        child_x += self.left_pad
        child_y += self.top_pad
        
        my_origin = self.viewport.area().origin
        child_rect = NSMakeRect(my_origin.x + child_x, my_origin.y + child_y,  child_width, child_height)
        self.child.place(child_rect, self.viewport.view)

class MiroSplitView (NSSplitView):
    """Subclass NSSplitView to control how the divider gets drawn."""

    def initWithFrame_(self, rect):
        self = NSSplitView.initWithFrame_(self, rect)
        self.setVertical_(YES)
        self.setDelegate_(self)
        self.color = NSColor.colorWithDeviceWhite_alpha_(64.0/255.0, 1.0)
        self.color2 = NSColor.colorWithDeviceWhite_alpha_(135.0/255.0, 1.0)
        self.min_left_width = self.min_right_width = 0
        return self

    def setMinRightWidth(self, width):
        self.min_right_width = width

    def setMinLeftWidth(self, width):
        self.min_left_width = width
    
    def dividerThickness(self):
        return 1.0

    def splitView_constrainMinCoordinate_ofSubviewAt_(self, sender, proposedMin, offset):
        if offset == 0:
            proposedMin = max(self.min_left_width, proposedMin)
        return proposedMin

    def splitView_constrainMaxCoordinate_ofSubviewAt_(self, sender, proposedMax, offset):
        if offset == 0:
            proposedMax = min(self.frame().size.width - self.min_right_width, 
                    proposedMax)
        return proposedMax

    def splitView_effectiveRect_forDrawnRect_ofDividerAtIndex_(self, sender, effective_rect, drawn_rect, index):
        # 10.5 only delegate method, allows to widen the clickable zone of
        # the splitview divider
        effective_rect.origin.x -= 3
        effective_rect.size.width += 6
        return effective_rect

    def placeViewsWithLeftWidth_(self, left_width):
        if self.subviews().count() != 2:
            return
        left_view, right_view = self.subviews()
        my_size = self.bounds().size
        left_view.setFrame_(NSMakeRect(0, 0, left_width, my_size.height))
        space_taken = left_width + self.dividerThickness()
        right_view.setFrame_ (NSMakeRect(space_taken, 0,
            my_size.width - space_taken, my_size.height))
        left_view.display()
        right_view.display()

    def placeViewsWithRightWidth_(self, right_width):
        if self.subviews().count() != 2:
            return
        left_view, right_view = self.subviews()
        my_size = self.bounds().size
        left_width = my_size - right_width - self.dividerThickness()
        left_view.setFrame_(NSMakeRect(0, 0, left_width, my_size.height))
        right_view.setFrame_ (NSMakeRect(left_width + self.dividerThickness(), 
            0, right_width, my_size.height))

    def resizeSubviewsWithOldSize_(self, oldSize):
        if self.subviews().count() != 2:
            # If we don't have a left and right view let Cocoa handle it
            self.adjustSubviews()
            return
        left_view = self.subviews()[0]
        right_view = self.subviews()[1]
        difference  = self.frame().size.width - oldSize.width
        right_x = right_view.frame().origin.x
        right_width = right_view.frame().size.width + difference
        if right_width < self.min_right_width:
            left_size = left_view.frame().size
            left_shrink = self.min_right_width - right_width
            left_view.setFrameSize_(NSSize(left_size.width - left_shrink, 
                    self.frame().size.height))
            right_width = self.min_right_width
            right_x -= left_shrink
        else:
            left_view.setFrameSize_(NSSize(left_view.frame().size.width,
                    self.frame().size.height))
        right_view.setFrame_(NSMakeRect(right_x, 0, 
            right_width, self.frame().size.height))
        
    def drawDividerInRect_(self, rect):
        p1 = rect.origin
        p1.x += 0.5
        p2 = NSPoint(p1.x, rect.size.height)
        if self.window().isMainWindow():
            self.color.set()
        else:
            self.color2.set()
        NSBezierPath.strokeLineFromPoint_toPoint_(p1, p2)

    def setDividerNeedsDisplay(self):
        if self.subviews().count() != 2:
            return # no divider needed
        left_frame = self.subviews()[0].frame()
        rect = NSMakeRect(left_frame.size.width, 0,
                self.dividerThickness(), self.bounds().size.height)
        self.setNeedsDisplayInRect_(rect)

class Splitter(Container):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self):
        Container.__init__(self)
        self.left = self.right = None
        self.view = MiroSplitView.alloc().init()
        self.left_view = FlippedView.alloc().init()
        self.right_view = FlippedView.alloc().init()
        self.view.addSubview_(self.left_view)
        self.view.addSubview_(self.right_view)
        self.notifications = NotificationForwarder.create(self.view)
        self.notifications.connect(self.on_views_resized,
                'NSSplitViewDidResizeSubviewsNotification')

    def get_children(self):
        children = []
        if self.left:
            children.append(self.left)
        if self.right:
            children.append(self.right)
        return children

    def calc_size_request(self):
        if self.viewport is not None:
            width = self.view.dividerThickness()
        else:
            width = 1 # default divider thinkness
        height = 0
        for child in self.get_children():
            child_width, child_height = child.get_size_request()
            width += child_width
            height = max(height, child_height)
        return width, height

    def on_views_resized(self, notification):
        self.place_children()
        self.view.setDividerNeedsDisplay()

    def place_children(self):
        if self.left:
            self.left.place(self.left_view.bounds(), self.left_view)
        if self.right:
            self.right.place(self.right_view.bounds(), self.right_view)

    def set_left(self, widget):
        """Set the left child widget."""
        old_left = self.left
        self.left = widget
        self.set_min_left_width()
        self.child_changed(old_left, self.left)

    def set_right(self, widget):
        """Set the right child widget.  """
        old_right = self.right
        self.right = widget
        self.set_min_right_width()
        self.child_changed(old_right, self.right)

    def set_left_width(self, width):
        self.view.placeViewsWithLeftWidth_(width)
        self.place_children()
        self.view.setDividerNeedsDisplay()
        self.view.setNeedsDisplay_(YES)

    def get_left_width(self):
        left, right = self.view.subviews()
        return left.frame().size[0]

    def set_right_width(self, width):
        self.view.placeViewsWithRightWidth_(width)
        self.place_children()
        self.view.setDividerNeedsDisplay()

    def set_min_right_width(self):
        min_width = self.right.get_size_request()[0]
        self.view.setMinRightWidth(min_width)

    def set_min_left_width(self):
        min_width = self.left.get_size_request()[0]
        self.view.setMinLeftWidth(min_width)

    def remove_left(self):
        """Remove the left child widget."""
        old_left = self.left
        self.left = None
        self.child_removed(old_left)

    def remove_right(self):
        """Remove the right child widget."""
        old_right = self.right
        self.right = None
        self.child_removed(old_right)
        
    def remove_viewport(self):
        Container.remove_viewport(self)
        self.notifications.disconnect()

class _TablePacking(object):
    """Utility class to help with packing Table widgets."""
    def __init__(self, widget, column, row, column_span, row_span):
        self.widget = widget
        self.column = column
        self.row = row
        self.column_span = column_span
        self.row_span = row_span

    def column_indexes(self):
        return range(self.column, self.column + self.column_span)

    def row_indexes(self):
        return range(self.row, self.row + self.row_span)

class Table(Container):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    CREATES_VIEW = False

    def __init__(self, columns, rows):
        Container.__init__(self)
        self._cells = Matrix(columns, rows)
        self._children = [] # List of _TablePacking objects
        self._children_sorted = True
        self.rows = rows
        self.columns = columns
        self.row_spacing = self.column_spacing = 0

    def _ensure_children_sorted(self):
        if not self._children_sorted:
            def cell_area(table_packing):
                return table_packing.column_span * table_packing.row_span
            self._children.sort(key=cell_area)
            self._children_sorted = True

    def get_children(self):
        return [cell.widget for cell in self._children]
    children = property(get_children)

    def calc_size_request(self):
        self._ensure_children_sorted()
        self._calc_dimensions()
        return self.total_width, self.total_height

    def _calc_dimensions(self):
        self.column_widths = [0] * self.columns
        self.row_heights = [0] * self.rows

        for tp in self._children:
            child_width, child_height = tp.widget.get_size_request()
            # recalc the width of the child's columns
            self._recalc_dimension(child_width, self.column_widths,
                    tp.column_indexes())
            # recalc the height of the child's rows
            self._recalc_dimension(child_height, self.row_heights,
                    tp.row_indexes())

        self.total_width = (self.column_spacing * (self.columns - 1) +
                sum(self.column_widths))
        self.total_height = (self.row_spacing * (self.rows - 1) +
                sum(self.row_heights))

    def _recalc_dimension(self, child_size, size_array, positions):
        current_size = sum(size_array[p] for p in positions)
        child_size_needed = child_size - current_size
        if child_size_needed > 0:
            iter = _extra_space_iter(child_size_needed, len(positions))
            for p in positions:
                size_array[p] += iter.next()

    def place_children(self):
        column_positions = [0]
        for width in self.column_widths[:-1]:
            column_positions.append(width + column_positions[-1])
        row_positions = [0]
        for height in self.row_heights[:-1]:
            row_positions.append(height + row_positions[-1])

        my_x= self.viewport.placement.origin.x
        my_y = self.viewport.placement.origin.y
        for tp in self._children:
            x = my_x + column_positions[tp.column]
            y = my_y + row_positions[tp.row]
            width = sum(self.column_widths[i] for i in tp.column_indexes())
            height = sum(self.row_heights[i] for i in tp.row_indexes())
            rect = NSMakeRect(x, y, width, height)
            tp.widget.place(rect, self.viewport.view)

    def pack(self, widget, column, row, column_span=1, row_span=1):
        tp = _TablePacking(widget, column, row, column_span, row_span)
        for c in tp.column_indexes():
            for r in tp.row_indexes():
                if self._cells[c, r]:
                    raise ValueError("Cell %d x %d is already taken" % (c, r))
        self._cells[column, row] = widget
        self._children.append(tp)
        self._children_sorted = False
        self.child_added(widget)

    def remove(self, child):
        for i in xrange(len(self._children)):
            if self._children[i].widget is child:
                self._children.remove(i)
                break
        else:
            raise ValueError("%s is not a child of this Table" % child)
        self._cells.remove(child)
        self.child_removed(widget)

    def set_column_spacing(self, spacing):
        self.column_spacing = spacing
        self.invalidate_size_request()

    def set_row_spacing(self, spacing):
        self.row_spacing = spacing
        self.invalidate_size_request()

    def enable_widget(self, row=None, column=None):
        Container.enable_widget(self)
        if row != None and column != None:
            if self._cells[column, row]:
                self._cells[column, row].enable_widget()
        elif row != None:
            for mem in self._cells.row(row):
                if mem: mem.enable_widget()
        elif column != None:
            for mem in self._cells.column(column):
                if mem: mem.enable_widget()
        else:
            for mem in self._cells:
                if mem: mem.enable_widget()

    def disable_widget(self, row=None, column=None):
        Container.disable_widget(self)
        if row != None and column != None:
            if self._cells[column, row]: 
                self._cells[column, row].disable_widget()
        elif row != None:
            for mem in self._cells.row(row):
                if mem: mem.disable_widget()
        elif column != None:
            for mem in self._cells.column(column):
                if mem: mem.disable_widget()
        else:
            for mem in self._cells:
                if mem: mem.disable_widget()

class Scroller(Bin):
    """See https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPI for a description of the API for this class."""
    def __init__(self, horizontal, vertical):
        Bin.__init__(self)
        self.view = NSScrollView.alloc().init()
        self.view.setAutohidesScrollers_(YES)
        self.view.setHasHorizontalScroller_(horizontal)
        self.view.setHasVerticalScroller_(vertical)
        self.document_view = FlippedView.alloc().init()
        self.view.setDocumentView_(self.document_view)
        clip_view = self.view.contentView()
        self.clip_notifications = NotificationForwarder.create(clip_view)
        clip_view.setPostsFrameChangedNotifications_(YES)
        clip_view.setPostsBoundsChangedNotifications_(YES)
        self.clip_notifications.connect(self._on_clip_view_frame_change,
                'NSViewFrameDidChangeNotification')
        self.clip_notifications.connect(self._on_clip_view_bounds_change,
                'NSViewBoundsDidChangeNotification')

    def remove_viewport(self):
        Bin.remove_viewport(self)
        self.clip_notifications.disconnect()

    def _on_clip_view_frame_change(self, notification):
        # If the clip view is larger than the document view (probably because
        # we auto-hid a scrollbar), resize the document view to be at least as
        # big as the clip view.
        if not self.child:
            return
        clip_size = self.view.contentView().frame().size
        document_size = self.document_view.frame().size
        max_width = max(clip_size.width, document_size.width)
        max_height = max(clip_size.height, document_size.height)
        if (max_width != document_size.width or
                max_height != document_size.height):
            self.document_view.setFrameSize_(NSSize(max_width, max_height))

    def _on_clip_view_bounds_change(self, notification):
        if self.child:
            self.child.viewport_scrolled()

    def calc_size_request(self):
        if self.child:
            width = height = 0
            if not self.view.hasHorizontalScroller():
                width = self.child.get_size_request()[0]
            if not self.view.hasVerticalScroller():
                height = self.child.get_size_request()[1]
            # Add a little room for the scrollbars
            if self.view.hasHorizontalScroller():
                height += 10
            if self.view.hasVerticalScroller():
                width += 10
            return width, height
        else:
            return 0, 0

    def place_children(self):
        if self.child:
            child_width, child_height = self.child.get_size_request()
            child_width = max(child_width, self.view.contentSize().width)
            child_height = max(child_height, self.view.contentSize().height)
            self.document_view.setFrameSize_(NSSize(child_width,
                child_height))
            self.child.place(self.document_view.frame(), self.document_view)
            self.document_view.setNeedsDisplay_(YES)

class ExpanderView(FlippedView):
    def init(self):
        self = FlippedView.init(self)
        self.label_rect = None
        self.content_view = None
        self.button = NSButton.alloc().init()
        self.button.setState_(NSOffState)
        self.button.setTitle_("")
        self.button.setBezelStyle_(NSDisclosureBezelStyle)
        self.button.setButtonType_(NSPushOnPushOffButton)
        self.button.sizeToFit()
        self.addSubview_(self.button)
        self.button.setTarget_(self)
        self.button.setAction_('buttonChanged:')
        self.content_view = FlippedView.alloc().init()
        return self

    def buttonChanged_(self, button):
        if button.state() == NSOnState:
            self.addSubview_(self.content_view)
        else:
            self.content_view.removeFromSuperview()
        if self.window():
            wrappermap.wrapper(self).invalidate_size_request()

    def mouseDown_(self, event):
        pass  # Just need to respond to the selector so we get mouseUp_

    def mouseUp_(self, event):
        position = event.locationInWindow()
        window_label_rect = self.convertRect_toView_(self.label_rect, None)
        if NSPointInRect(position, window_label_rect):
            self.button.setNextState()
            self.buttonChanged_(self.button)

class Expander(Bin):
    BUTTON_PAD_TOP = 2
    BUTTON_PAD_LEFT = 4
    LABEL_SPACING = 4

    def __init__(self, child):
        Bin.__init__(self)
        if child:
            self.add(child)
        self.label = None
        self.spacing = 0
        self.view = ExpanderView.alloc().init()
        self.button = self.view.button
        self.button.setFrameOrigin_(NSPoint(self.BUTTON_PAD_LEFT,
            self.BUTTON_PAD_TOP))
        self.content_view = self.view.content_view

    def set_spacing(self, spacing):
        self.spacing = spacing

    def set_label(self, widget):
        self.label = widget
        self.children_changed()

    def set_expanded(self, expanded):
        if expanded:
            self.button.setState_(NSOnState)
        else:
            self.button.setState_(NSOffState)
        self.view.buttonChanged_(self.button)

    def calc_top_size(self):
        width = self.button.bounds().size.width
        height = self.button.bounds().size.height
        if self.label is not None:
            label_width, label_height = self.label.get_size_request()
            width += self.LABEL_SPACING + label_width
            height = max(height, label_height)
        width += self.BUTTON_PAD_LEFT
        height += self.BUTTON_PAD_TOP
        return width, height

    def calc_size_request(self):
        width, height = self.calc_top_size()
        if self.child is not None and self.button.state() == NSOnState:
            child_width, child_height = self.child.get_size_request()
            width = max(width, child_width)
            height += self.spacing + child_height
        return width, height

    def place_children(self):
        top_width, top_height = self.calc_top_size()
        if self.label:
            label_width, label_height = self.label.get_size_request()
            button_width = self.button.bounds().size.width
            label_x = self.BUTTON_PAD_LEFT + button_width + self.LABEL_SPACING
            label_rect = NSMakeRect(label_x, self.BUTTON_PAD_TOP, 
                    label_width, label_height)
            self.label.place(label_rect, self.viewport.view)
            self.view.label_rect = label_rect
        if self.child:
            size = self.viewport.area().size
            child_rect = NSMakeRect(0, 0, size.width, size.height -
                    top_height)
            self.content_view.setFrame_(NSMakeRect(0, top_height, size.width,
                size.height - top_height))
            self.child.place(child_rect, self.content_view)


class TabViewDelegate(NSObject):
    def tabView_willSelectTabViewItem_(self, tab_view, tab_view_item):
        try:
            wrapper = wrappermap.wrapper(tab_view)
        except KeyError:
            pass # The NSTabView hasn't been placed yet, don't worry about it.
        else:
            wrapper.place_child_with_item(tab_view_item)

class TabContainer(Container):
    def __init__(self):
        Container.__init__(self)
        self.children = []
        self.item_to_child = {}
        self.view = NSTabView.alloc().init()
        self.view.setAllowsTruncatedLabels_(NO)
        self.delegate = TabViewDelegate.alloc().init()
        self.view.setDelegate_(self.delegate)

    def append_tab(self, child_widget, label, image):
        item = NSTabViewItem.alloc().init()
        item.setLabel_(label)
        item.setView_(FlippedView.alloc().init())
        self.view.addTabViewItem_(item)
        self.children.append(child_widget)
        self.child_added(child_widget)
        self.item_to_child[item] = child_widget

    def select_tab(self, index):
        self.view.selectTabViewItemAtIndex_(index)

    def place_children(self):
        self.place_child_with_item(self.view.selectedTabViewItem())

    def place_child_with_item(self, tab_view_item):
        child = self.item_to_child[tab_view_item]
        child_view = tab_view_item.view()
        content_rect =self.view.contentRect()
        child_view.setFrame_(content_rect)
        child.place(child_view.bounds(), child_view)

    def calc_size_request(self):
        tab_size = self.view.minimumSize()
        # make sure there's enough room for the tabs, plus a little extra
        # space to make things look good
        max_width = tab_size.width + 60
        max_height = 0
        for child in self.children:
            width, height = child.get_size_request()
            max_width = max(width, max_width)
            max_height = max(height, max_height)
        max_height += tab_size.height

        return max_width, max_height
