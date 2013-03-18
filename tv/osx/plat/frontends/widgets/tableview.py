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

"""miro.plat.frontends.widgets.tableview -- TableView widget and it's
associated classes.
"""

import math
import logging
from contextlib import contextmanager
from collections import namedtuple

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

from miro import signals
from miro import errors
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets.tableselection import SelectionOwnerMixin
from miro.frontends.widgets.tablescroll import ScrollbarOwnerMixin
from miro.plat import resources
from miro.plat.utils import filename_to_unicode
from miro.plat.frontends.widgets import osxmenus
from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets import tablemodel
from miro.plat.frontends.widgets.base import Widget
from miro.plat.frontends.widgets.simple import Image
from miro.plat.frontends.widgets.drawing import DrawingContext, DrawingStyle, Gradient, ImageSurface
from miro.plat.frontends.widgets.helpers import NotificationForwarder
from miro.plat.frontends.widgets.layoutmanager import LayoutManager
from miro.plat.frontends.widgets.widgetset import CustomButton

EXPANDER_PADDING = 6
HEADER_HEIGHT = 17
CUSTOM_HEADER_HEIGHT = 25

def iter_range(ns_range):
    """Iterate over an NSRange object"""
    return xrange(ns_range.location, ns_range.location + ns_range.length)

Rect = namedtuple('Rect', 'x y width height') 
def NSRectToRect(nsrect):
    origin, size = nsrect.origin, nsrect.size
    return Rect(origin.x, origin.y, size.width, size.height)

Point = namedtuple('Point', 'x y')
def NSPointToPoint(nspoint):
    return Point(int(nspoint.x), int(nspoint.y))

class HotspotTracker(object):
    """Contains the info on the currently tracked hotspot.  See:
    https://develop.participatoryculture.org/index.php/WidgetAPITableView
    """
    def __init__(self, tableview, point):
        self.tableview = tableview
        self.row = tableview.rowAtPoint_(point)
        self.column = tableview.columnAtPoint_(point)
        if self.row == -1 or self.column == -1:
            self.hit = False
            return
        model = tableview.dataSource().model
        self.iter = model.iter_for_row(tableview, self.row)
        self.table_column = tableview.tableColumns()[self.column]
        self.cell = self.table_column.dataCell()
        self.update_position(point)
        if isinstance(self.cell, CustomTableCell):
            self.name = self.calc_hotspot()
        else:
            self.name = None
        self.hit = (self.name is not None)

    def is_for_context_menu(self):
        return self.name == '#show-context-menu'

    def calc_cell_hotspot(self, column, row):
        if (self.hit and self.column == column and self.row == row):
            return self.name
        else:
            return None

    def update_position(self, point):
        cell_frame = self.tableview.frameOfCellAtColumn_row_(self.column,
                self.row)
        self.pos = NSPoint(point.x - cell_frame.origin.x, 
                point.y - cell_frame.origin.y)

    def update_hit(self):
        old_hit = self.hit
        self.hit = (self.calc_hotspot() == self.name)
        if old_hit != self.hit:
            self.redraw_cell()

    def set_cell_data(self):
        model = self.tableview.dataSource().model
        row = model[self.iter]
        value_dict = model.get_column_data(row, self.table_column)
        self.cell.setObjectValue_(value_dict)
        self.cell.set_wrapper_data()

    def calc_hotspot(self):
        self.set_cell_data()
        cell_frame = self.tableview.frameOfCellAtColumn_row_(self.column,
                self.row)
        style = self.cell.make_drawing_style(cell_frame, self.tableview)
        layout_manager = self.cell.layout_manager
        layout_manager.reset()
        return self.cell.wrapper.hotspot_test(style, layout_manager,
                self.pos.x, self.pos.y, cell_frame.size.width,
                cell_frame.size.height)

    def redraw_cell(self):
        # Check to see if we removed the table in response to a hotspot click.
        if self.tableview.superview() is not nil:
            cell_frame = self.tableview.frameOfCellAtColumn_row_(self.column,
                    self.row)
            self.tableview.setNeedsDisplayInRect_(cell_frame)

def _calc_interior_frame(total_frame, tableview):
    """Calculate the inner cell area for a table cell.

    We tell cocoa that the intercell spacing is (0, 0) and instead handle the
    spacing ourselves.  This method calculates the area that a cell should
    render to, given the total spacing.
    """
    return NSMakeRect(total_frame.origin.x + tableview.column_spacing // 2,
            total_frame.origin.y + tableview.row_spacing // 2,
            total_frame.size.width - tableview.column_spacing,
            total_frame.size.height - tableview.row_spacing)

class MiroTableCell(NSTextFieldCell):
    def init(self):
        return super(MiroTableCell, self).initTextCell_('')

    def calcHeight_(self, view):
        font = self.font()
        return math.ceil(font.ascender() + abs(font.descender()) +
                font.leading())

    def highlightColorWithFrame_inView_(self, frame, view):
        return nil

    def setObjectValue_(self, value_dict):
        if isinstance(value_dict, dict):
            NSCell.setObjectValue_(self, value_dict['value'])
        else:
            # OS X calls setObjectValue_('') on intialization
            NSCell.setObjectValue_(self, value_dict)

    def drawInteriorWithFrame_inView_(self, frame, view):
        return NSTextFieldCell.drawInteriorWithFrame_inView_(self,
                _calc_interior_frame(frame, view), view)

class MiroTableItemListTextCell(MiroTableCell):
    def initWithAttrGetter_(self, attr_getter):
        self = self.init()
        self.setWraps_(NO)
        self.attr_getter = attr_getter
        self._textColor = self.textColor()
        return self

    def drawWithFrame_inView_(self, frame, view):
        # adjust frame based on the cell spacing
        frame = _calc_interior_frame(frame, view)
        if (self.isHighlighted() and frame is not None and
            (view.isDescendantOf_(view.window().firstResponder()) or
             view.gradientHighlight) and view.window().isMainWindow()):
            self.setTextColor_(NSColor.whiteColor())
        else:
            self.setTextColor_(self._textColor)
        return MiroTableCell.drawWithFrame_inView_(self, frame, view)

    def titleRectForBounds_(self, rect):
        frame = MiroTableCell.titleRectForBounds_(self, rect)
        text_size = self.attributedStringValue().size()
        frame.origin.y = rect.origin.y + (rect.size.height - text_size.height) / 2.0
        return frame

    def drawInteriorWithFrame_inView_(self, frame, view):
        rect = self.titleRectForBounds_(frame)
        self.attributedStringValue().drawInRect_(rect)

    def setObjectValue_(self, value):
        if isinstance(value, tuple):
            info, attrs, group_info = value
            cell_text = self.attr_getter(info)
            NSCell.setObjectValue_(self, cell_text)
        else:
            # Getting set to a something other than a model row, usually this
            # happens in initialization
            NSCell.setObjectValue_(self, '')

class MiroTableImageCell(NSImageCell):
    def calcHeight_(self, view):
        return self.value_dict['image'].size().height

    def highlightColorWithFrame_inView_(self, frame, view):
        return nil

    def setObjectValue_(self, value_dict):
        NSImageCell.setObjectValue_(self, value_dict['image'])

    def drawInteriorWithFrame_inView_(self, frame, view):
        return NSImageCell.drawInteriorWithFrame_inView_(self,
                _calc_interior_frame(frame, view), view)

class MiroCheckboxCell(NSButtonCell):
    def init(self):
        self = super(MiroCheckboxCell, self).init()
        self.setButtonType_(NSSwitchButton)
        self.setTitle_('')
        return self

    def calcHeight_(self, view):
        return self.cellSize().height

    def highlightColorWithFrame_inView_(self, frame, view):
        return nil

    def setObjectValue_(self, value_dict):
        if isinstance(value_dict, dict):
            NSButtonCell.setObjectValue_(self, value_dict['value'])
        else:
            # OS X calls setObjectValue_('') on intialization
            NSCell.setObjectValue_(self, value_dict)

    def startTrackingAt_inView_(self, point, view):
        return YES

    def continueTracking_at_inView_(self, lastPoint, at, view):
        return YES

    def stopTracking_at_inView_mouseIsUp_(self, lastPoint, at, tableview, mouseIsUp):
        if mouseIsUp:
            column = tableview.columnAtPoint_(at)
            row = tableview.rowAtPoint_(at)
            if column != -1 and row != -1:
                wrapper = wrappermap.wrapper(tableview)
                column = wrapper.columns[column]
                itr = wrapper.model.iter_for_row(tableview, row)
                column.renderer.emit('clicked', itr)
        return NSButtonCell.stopTracking_at_inView_mouseIsUp_(self, lastPoint,
                at, tableview, mouseIsUp)

    def drawInteriorWithFrame_inView_(self, frame, view):
        return NSButtonCell.drawInteriorWithFrame_inView_(self,
                _calc_interior_frame(frame, view), view)

class CellRendererBase(object):
    DRAW_BACKGROUND = True

    def set_index(self, index):
        self.index = index
    
    def get_index(self):
        return self.index

class CellRenderer(CellRendererBase):
    def __init__(self):
        self.cell = self.build_cell()
        self._font_scale_factor = 1.0
        self._font_bold = False
        self.set_align('left')

    def build_cell(self):
        return MiroTableCell.alloc().init()

    def setDataCell_(self, column):
        column.setDataCell_(self.cell)

    def set_text_size(self, size):
        if size == widgetconst.SIZE_NORMAL:
            self._font_scale_factor = 1.0
        elif size == widgetconst.SIZE_SMALL:
            # make the scale factor such so that the font size is 11.0
            self._font_scale_factor = 11.0 / NSFont.systemFontSize()
        else:
            raise ValueError("Unknown size: %s" % size)
        self._set_font()

    def set_font_scale(self, scale_factor):
        self._font_scale_factor = scale_factor
        self._set_font()

    def set_bold(self, bold):
        self._font_bold = bold
        self._set_font()

    def _set_font(self):
        size = NSFont.systemFontSize() * self._font_scale_factor
        if self._font_bold:
            font = NSFont.boldSystemFontOfSize_(size)
        else:
            font = NSFont.systemFontOfSize_(size)
        self.cell.setFont_(font)

    def set_color(self, color):
        color = NSColor.colorWithDeviceRed_green_blue_alpha_(color[0],
                color[1], color[2], 1.0)
        self.cell._textColor = color
        self.cell.setTextColor_(color)

    def set_align(self, align):
        if align == 'left':
            ns_alignment = NSLeftTextAlignment
        elif align == 'center':
            ns_alignment = NSCenterTextAlignment
        elif align == 'right':
            ns_alignment = NSRightTextAlignment
        else:
            raise ValueError("unknown alignment: %s", align)
        self.cell.setAlignment_(ns_alignment)

class ImageCellRenderer(CellRendererBase):
    def setDataCell_(self, column):
        column.setDataCell_(MiroTableImageCell.alloc().init())

class CheckboxCellRenderer(CellRendererBase, signals.SignalEmitter):
    def __init__(self):
        signals.SignalEmitter.__init__(self, 'clicked')
        self.size = widgetconst.SIZE_NORMAL

    def set_control_size(self, size):
        self.size = size

    def setDataCell_(self, column):
        cell = MiroCheckboxCell.alloc().init()
        if self.size == widgetconst.SIZE_SMALL:
            cell.setControlSize_(NSSmallControlSize)
        column.setDataCell_(cell)

class CustomTableCell(NSCell):
    def init(self):
        self = super(CustomTableCell, self).init()
        self.layout_manager = LayoutManager()
        self.hotspot = None
        self.default_drawing_style = DrawingStyle()
        return self

    def highlightColorWithFrame_inView_(self, frame, view):
        return nil

    def calcHeight_(self, view):
        self.layout_manager.reset()
        self.set_wrapper_data()
        cell_size = self.wrapper.get_size(self.default_drawing_style,
                self.layout_manager)
        return cell_size[1]

    def make_drawing_style(self, frame, view):
        text_color = None
        if (self.isHighlighted() and frame is not None and
                (view.isDescendantOf_(view.window().firstResponder()) or
                    view.gradientHighlight) and view.window().isMainWindow()):
            text_color = NSColor.whiteColor()
        return DrawingStyle(text_color=text_color)

    def drawInteriorWithFrame_inView_(self, frame, view):
        NSGraphicsContext.currentContext().saveGraphicsState()
        if not self.wrapper.IGNORE_PADDING:
            # adjust frame based on the cell spacing. We also have to adjust
            # the hover position to account for the new frame
            original_frame = frame
            frame = _calc_interior_frame(frame, view)
            hover_adjustment = (frame.origin.x - original_frame.origin.x,
                                frame.origin.y - original_frame.origin.y)
        else:
            hover_adjustment = (0, 0)
        if self.wrapper.outline_column:
            pad_left = EXPANDER_PADDING
        else:
            pad_left = 0
        drawing_rect = NSMakeRect(frame.origin.x + pad_left, frame.origin.y,
                frame.size.width - pad_left, frame.size.height)
        context = DrawingContext(view, drawing_rect, drawing_rect)
        context.style = self.make_drawing_style(frame, view)
        self.layout_manager.reset()
        self.set_wrapper_data()
        column = self.wrapper.get_index()
        hover_pos = view.get_hover(self.row, column)
        if hover_pos is not None:
            hover_pos = [hover_pos[0] - hover_adjustment[0],
                         hover_pos[1] - hover_adjustment[1]]
        self.wrapper.render(context, self.layout_manager, self.isHighlighted(),
                self.hotspot, hover_pos)
        NSGraphicsContext.currentContext().restoreGraphicsState()

    def setObjectValue_(self, value):
        self.object_value = value

    def set_wrapper_data(self):
        self.wrapper.__dict__.update(self.object_value)

class CustomCellRenderer(CellRendererBase):
    CellClass = CustomTableCell

    IGNORE_PADDING = False

    def __init__(self):
        self.outline_column = False
        self.index = None

    def setDataCell_(self, column):
        # Note that the ownership is the opposite of what happens in widgets.
        # The NSObject owns it's wrapper widget.  This happens for a couple
        # reasons:
        # 1) The data cell gets copied a bunch of times, so wrappermap won't
        # work with it.
        # 2) The Wrapper should only needs to stay around as long as the
        # NSCell that it's wrapping is around.  Once the column gets removed
        # from the table, the wrapper can be deleted.
        nscell = self.CellClass.alloc().init()
        nscell.wrapper = self
        column.setDataCell_(nscell)

    def hotspot_test(self, style, layout, x, y, width, height):
        return None
    
class ItemListTableCell(CustomTableCell):
    def set_wrapper_data(self):
        self.wrapper.info, self.wrapper.attrs, self.wrapper.group_info = \
                self.object_value

class ItemListRenderer(CustomCellRenderer):
    CellClass = ItemListTableCell

    def hotspot_test(self, style, layout, x, y, width, height):
        return None

class ItemListRendererText(CellRenderer):
    def build_cell(self):
        cell = MiroTableItemListTextCell.alloc()
        return cell.initWithAttrGetter_(self.get_value)

def calc_row_height(view, model_row):
    max_height = 0
    model = view.dataSource().model
    for column in view.tableColumns():
        cell = column.dataCell()
        data = model.get_column_data(model_row, column)
        cell.setObjectValue_(data)
        cell_height = cell.calcHeight_(view)
        max_height = max(max_height, cell_height)
    if max_height == 0:
        max_height = 12
    return max_height + view.row_spacing

class TableViewDelegate(NSObject):
    def tableView_willDisplayCell_forTableColumn_row_(self, view, cell,
            column, row):
        column = view.column_index_map[column]
        cell.column = column
        cell.row = row
        if view.hotspot_tracker:
            cell.hotspot = view.hotspot_tracker.calc_cell_hotspot(column, row)
        else:
            cell.hotspot = None

    def tableView_didClickTableColumn_(self, tableview, column):
        wrapper = wrappermap.wrapper(tableview)
        for column_wrapper in wrapper.columns:
            if column_wrapper._column is column:
                column_wrapper.emit('clicked')

    def tableView_toolTipForCell_rect_tableColumn_row_mouseLocation_(self, tableview, cell, rect, column, row, location):
        wrapper = wrappermap.wrapper(tableview)
        iter = tableview.dataSource().model.iter_for_row(tableview, row)
        for wrapper_column in wrapper.columns:
            if wrapper_column._column is column:
                break
        return (wrapper.get_tooltip(iter, wrapper_column), rect)

class VariableHeightTableViewDelegate(TableViewDelegate):
    def tableView_heightOfRow_(self, table_view, row):
        model = table_view.dataSource().model
        iter = model.iter_for_row(table_view, row)
        if iter is None:
            return 12
        return calc_row_height(table_view, model[iter])

class OutlineViewDelegate(NSObject):
    expanded_path = resources.path('images/tab-expanded.png')
    collapsed_path = resources.path('images/tab-collapsed.png')

    def outlineView_willDisplayCell_forTableColumn_item_(self, view, cell,
            column, item):
        row = view.rowForItem_(item)
        column = view.column_index_map[column]
        cell.column = column
        cell.row = row
        if view.hotspot_tracker:
            cell.hotspot = view.hotspot_tracker.calc_cell_hotspot(column, row)
        else:
            cell.hotspot = None

    def outlineView_willDisplayOutlineCell_forTableColumn_item_(self, view,
                                                                cell, column,
                                                                item):
        cell.setImage_(NSImage.alloc().initByReferencingFile_(
                filename_to_unicode(self.collapsed_path)))
        cell.setAlternateImage_(NSImage.alloc().initByReferencingFile_(
                filename_to_unicode(self.expanded_path)))

    def outlineView_didClickTableColumn_(self, tableview, column):
        wrapper = wrappermap.wrapper(tableview)
        for column_wrapper in wrapper.columns:
            if column_wrapper._column is column:
                column_wrapper.emit('clicked')

    def outlineView_toolTipForCell_rect_tableColumn_row_mouseLocation_(self, tableview, cell, rect, column, row, location):
        wrapper = wrappermap.wrapper(tableview)
        iter = tableview.dataSource().model.iter_for_row(tableview, row)
        for wrapper_column in wrapper.columns:
            if wrapper_column._column is column:
                break
        return (wrapper.get_tooltip(iter, wrapper_column), rect)

class VariableHeightOutlineViewDelegate(OutlineViewDelegate):
    def outlineView_heightOfRowByItem_(self, outline_view, item):
        return calc_row_height(outline_view, item.values)

# TableViewCommon is a hack to do a Mixin class.  We want the same behaviour
# for our table views and our outline views.  Normally we would use a Mixin,
# but that doesn't work with pyobjc.  Instead we define the common code in
# TableViewCommon, then copy it into MiroTableView and MiroOutlineView

class TableViewCommon(object):
    def init(self):
        self = super(self.__class__, self).init()
        self.hotspot_tracker = None
        self._tracking_rects = []
        self.hover_info = None
        self.column_index_map = {}
        self.setFocusRingType_(NSFocusRingTypeNone)
        self.handled_last_mouse_down = False
        self.gradientHighlight = False
        self.tracking_area = None
        self.group_lines_enabled = False
        self.group_line_width = 1
        self.group_line_color = (0, 0, 0, 1.0)
        # we handle cell spacing manually
        self.setIntercellSpacing_(NSSize(0, 0))
        self.column_spacing = 3
        self.row_spacing = 2
        return self

    def updateTrackingAreas(self):
        # remove existing tracking area if needed
        if self.tracking_area:
            self.removeTrackingArea_(self.tracking_area)

        # create a new tracking area for the entire view.  This allows us to
        # get mouseMoved events whenever the mouse is inside our view.
        self.tracking_area = NSTrackingArea.alloc()
        self.tracking_area.initWithRect_options_owner_userInfo_(
                self.visibleRect(),
                NSTrackingMouseEnteredAndExited | NSTrackingMouseMoved |
                NSTrackingActiveInKeyWindow,
                self,
                nil)
        self.addTrackingArea_(self.tracking_area)

    def addTableColumn_(self, column):
        index = len(self.tableColumns())
        column.set_index(index)
        self.column_index_map[column._column] = index
        self.SuperClass.addTableColumn_(self, column._column)

    def removeTableColumn_(self, column):
        self.SuperClass.removeTableColumn_(self, column)
        removed = self.column_index_map.pop(column)
        for key, index in self.column_index_map.items():
            if index > removed:
                self.column_index_map[key] -= 1

    def moveColumn_toColumn_(self, src, dest):
        # Need to switch the TableColumn objects too
        columns = wrappermap.wrapper(self).columns
        columns[src], columns[dest] = columns[dest], columns[src]
        for index, column in enumerate(columns):
            column.set_index(index)
        self.SuperClass.moveColumn_toColumn_(self, src, dest)

    def highlightSelectionInClipRect_(self, rect):
        if wrappermap.wrapper(self).draws_selection:
            if not self.gradientHighlight:
                return self.SuperClass.highlightSelectionInClipRect_(self,
                        rect)
            context = NSGraphicsContext.currentContext()
            focused = self.isDescendantOf_(self.window().firstResponder())
            for row in tablemodel.list_from_nsindexset(self.selectedRowIndexes()):
                self.drawBackgroundGradient(context, focused, row)
    
    def setFrameSize_(self, size):
        if size.height == 0:
            size.height = 4
        self.SuperClass.setFrameSize_(self, size)

    def drawBackgroundGradient(self, context, focused, row):
        widget = wrappermap.wrapper(self)
        window = widget.get_window()
        if window and window.is_active():
            if focused:
                start_color = (0.588, 0.717, 0.843)
                end_color = (0.416, 0.568, 0.713)
                top_line_color = (0.416, 0.569, 0.714, 1.0)
                bottom_line_color = (0.416, 0.569, 0.714, 1.0)
            else:
                start_color = (168 / 255.0, 188 / 255.0, 208 / 255.0)
                end_color = (129 / 255.0, 152 / 255.0, 176 / 255.0)
                top_line_color = (129 / 255.0, 152 / 255.0, 175 / 255.0, 1.0)
                bottom_line_color = (0.416, 0.569, 0.714, 1.0)
        else:
            start_color = (0.675, 0.722, 0.765)
            end_color = (0.592, 0.659, 0.710)
            top_line_color = (0.596, 0.635, 0.671, 1.0)
            bottom_line_color = (0.522, 0.576, 0.620, 1.0)

        rect = self.rectOfRow_(row)
        top = NSMakeRect(rect.origin.x, rect.origin.y, rect.size.width, 1)
        context.saveGraphicsState()
        # draw the top line
        NSColor.colorWithDeviceRed_green_blue_alpha_(*top_line_color).set()
        NSRectFill(top)
        bottom = NSMakeRect(rect.origin.x, rect.origin.y + rect.size.height - 2,
                            rect.size.width, 1)
        NSColor.colorWithDeviceRed_green_blue_alpha_(*bottom_line_color).set()
        NSRectFill(bottom)
        highlight = NSMakeRect(rect.origin.x, rect.origin.y + rect.size.height - 1,
                               rect.size.width, 1)
        NSColor.colorWithDeviceRed_green_blue_alpha_(0.918, 0.925, 0.941, 1.0).set()
        NSRectFill(highlight)

        # draw the gradient
        rect.origin.y += 1
        rect.size.height -= 3
        NSRectClip(rect)
        gradient = Gradient(rect.origin.x, rect.origin.y,
                rect.origin.x, rect.origin.y + rect.size.height)
        gradient.set_start_color(start_color)
        gradient.set_end_color(end_color)
        gradient.draw()
        context.restoreGraphicsState()

    def drawBackgroundInClipRect_(self, clip_rect):
        # save our graphics state, since we are about to modify the clip path
        graphics_context = NSGraphicsContext.currentContext()
        graphics_context.saveGraphicsState()
        # create a NSBezierPath that contains the rects of the columns with
        # DRAW_BACKGROUND True.
        clip_path = NSBezierPath.bezierPath()
        number_of_columns = len(self.tableColumns())
        for col_index in iter_range(self.columnsInRect_(clip_rect)):
            column = wrappermap.wrapper(self.tableColumns()[col_index])
            column_rect = None
            if column.renderer.DRAW_BACKGROUND:
                # We should draw the background for this column, add it's rect
                # to our clip rect.
                column_rect = self.rectOfColumn_(col_index)
                clip_path.appendBezierPathWithRect_(column_rect)
            else:
                # We shouldn't draw the background for this column.  Don't add
                # anything to the clip rect, but do draw the area before the
                # first row and after the last row.
                self.drawBackgroundOutsideContent_clipRect_(col_index,
                        clip_rect)
            if col_index == number_of_columns - 1: # last column
                if not column_rect:
                    column_rect = self.rectOfColumn_(col_index)
                column_right = column_rect.origin.x + column_rect.size.width
                clip_right = clip_rect.origin.x + clip_rect.size.width
                if column_right < clip_right:
                    # there's space to the right, so add that to the clip_rect
                    remaining = clip_right - column_right
                    left_rect = NSMakeRect(column_right, clip_rect.origin.y,
                                           remaining, clip_rect.size.height)
                    clip_path.appendBezierPathWithRect_(left_rect)
        # clip to that path
        clip_path.addClip()
        # do the default drawing
        self.SuperClass.drawBackgroundInClipRect_(self, clip_rect)
        # restore graphics state
        graphics_context.restoreGraphicsState()

    def drawBackgroundOutsideContent_clipRect_(self, index, clip_rect):
        """Draw our background outside the rows with content

        We call this for cells with DRAW_BACKGROUND set to False.  For those,
        we let the cell draw their own background, but we still need to draw
        the background before the first cell and after the last cell.
        """

        self.backgroundColor().set()

        total_rect = NSIntersectionRect(self.rectOfColumn_(index), clip_rect)

        if self.numberOfRows() == 0:
            # if no rows are selected, draw the background over everything
            NSRectFill(total_rect)
            return

        # fill the area above the first row
        first_row_rect = self.rectOfRow_(0)
        if first_row_rect.origin.y > total_rect.origin.y:
            height = first_row_rect.origin.y - total_rect.origin.y
            NSRectFill(NSMakeRect(total_rect.origin.x, total_rect.origin.y,
                    total_rect.size.width, height))

        # fill the area below the last row
        last_row_rect = self.rectOfRow_(self.numberOfRows()-1)
        if NSMaxY(last_row_rect) < NSMaxY(total_rect):
            y = NSMaxY(last_row_rect) + 1
            height = NSMaxY(total_rect) - NSMaxY(last_row_rect)
            NSRectFill(NSMakeRect(total_rect.origin.x, y,
                    total_rect.size.width, height))

    def drawRow_clipRect_(self, row, clip_rect):
        self.SuperClass.drawRow_clipRect_(self, row, clip_rect)
        if self.group_lines_enabled:
            self.drawGroupLine_(row)

    def drawGroupLine_(self, row):
        model = wrappermap.wrapper(self).model
        if (not isinstance(model, tablemodel.ItemListModel) or
                model.item_list.get_grouping() is None):
            return

        info, attrs, group_info = model[row]
        if group_info[0] == group_info[1] - 1:
            rect = self.rectOfRow_(row)
            rect.origin.y = NSMaxY(rect) - self.group_line_width
            rect.size.height = self.group_line_width
            NSColor.colorWithDeviceRed_green_blue_alpha_(
                    *self.group_line_color).set()
            NSRectFill(rect)

    def canDragRowsWithIndexes_atPoint_(self, indexes, point):
        return YES

    def draggingSourceOperationMaskForLocal_(self, local):
        drag_source = wrappermap.wrapper(self).drag_source
        if drag_source and local:
            return drag_source.allowed_actions()
        return NSDragOperationNone

    def mouseMoved_(self, event):
        location = self.convertPoint_fromView_(event.locationInWindow(), nil)
        row = self.rowAtPoint_(location)
        column = self.columnAtPoint_(location)
        if (self.hover_info is not None and self.hover_info != (row, column)):
            # left a cell, redraw it the old one
            rect = self.frameOfCellAtColumn_row_(self.hover_info[1],
                    self.hover_info[0])
            self.setNeedsDisplayInRect_(rect)
        if row == -1 or column == -1:
            # corner case: we got a mouseMoved_ event, but the pointer is
            # outside the view
            self.hover_pos = self.hover_info = None
            return
        # queue a redraw on the cell currently hovered over
        rect = self.frameOfCellAtColumn_row_(column, row)
        self.setNeedsDisplayInRect_(rect)
        # recalculate hover_pos and hover_info
        self.hover_pos = (location[0] - rect[0][0],
                location[0] - rect[0][1])
        self.hover_info = (row, column)

    def mouseExited_(self, event):
        if self.hover_info:
            # mouse left our window, unset hover and redraw the cell that the
            # mouse was in
            rect = self.frameOfCellAtColumn_row_(self.hover_info[1],
                    self.hover_info[0])
            self.setNeedsDisplayInRect_(rect)
            self.hover_pos = self.hover_info = None

    def get_hover(self, row, column):
        if self.hover_info == (row, column):
            return self.hover_pos
        else:
            return None

    def mouseDown_(self, event):
        if event.modifierFlags() & NSControlKeyMask:
            self.handleContextMenu_(event)
            self.handled_last_mouse_down = True
            return

        point = self.convertPoint_fromView_(event.locationInWindow(), nil)

        if event.clickCount() == 2:
            if self.handled_last_mouse_down:
                return
            wrapper = wrappermap.wrapper(self)
            row = self.rowAtPoint_(point)
            if (row != -1 and self.point_should_click(point, row)):
                iter = wrapper.model.iter_for_row(self, row)
                wrapper.emit('row-activated', iter)
            return

        # Like clickCount() == 2 but keep running so we can get to run the 
        # hotspot tracker et al.
        if event.clickCount() == 1:
            wrapper = wrappermap.wrapper(self)
            row = self.rowAtPoint_(point)
            if (row != -1 and self.point_should_click(point, row)):

                iter = wrapper.model.iter_for_row(self, row)
                wrapper.emit('row-clicked', iter)

        hotspot_tracker = HotspotTracker(self, point)
        if hotspot_tracker.hit:
            self.hotspot_tracker = hotspot_tracker
            self.hotspot_tracker.redraw_cell()
            self.handled_last_mouse_down = True
            if hotspot_tracker.is_for_context_menu():
                self.popup_context_menu(self.hotspot_tracker.row, event)
                # once we're out of that call, we know the context menu is
                # gone
                hotspot_tracker.redraw_cell()
                self.hotspot_tracker = None
        else:
            self.handled_last_mouse_down = False
            self.SuperClass.mouseDown_(self, event)

    def point_should_click(self, point, row):
        """Should a click on a point result in a row-clicked signal?

        Subclasses can override if not every point should result in a click.
        """
        return True

    def rightMouseDown_(self, event):
        self.handleContextMenu_(event)

    def handleContextMenu_(self, event):
        self.window().makeFirstResponder_(self)
        point = self.convertPoint_fromView_(event.locationInWindow(), nil)
        column = self.columnAtPoint_(point)
        row = self.rowAtPoint_(point)
        if self.group_lines_enabled and column == 0:
            self.selectAllItemsInGroupForRow_(row)
        self.popup_context_menu(row, event)

    def selectAllItemsInGroupForRow_(self, row):
        wrapper = wrappermap.wrapper(self)
        model = wrapper.model
        if (not isinstance(model, tablemodel.ItemListModel) or
                model.item_list.get_grouping() is None):
            return

        info, attrs, group_info = model[row]
        select_range = NSMakeRange(row - group_info[0], group_info[1])
        index_set = NSIndexSet.indexSetWithIndexesInRange_(select_range)
        self.selectRowIndexes_byExtendingSelection_(index_set, NO)

    def popup_context_menu(self, row, event):
        selection = self.selectedRowIndexes()
        if row != -1 and not selection.containsIndex_(row):
            index_set = NSIndexSet.alloc().initWithIndex_(row)
            self.selectRowIndexes_byExtendingSelection_(index_set, NO)
        wrapper = wrappermap.wrapper(self)
        if wrapper.context_menu_callback is not None:
            menu_items = wrapper.context_menu_callback(wrapper)
            menu = osxmenus.make_context_menu(menu_items)
            NSMenu.popUpContextMenu_withEvent_forView_(menu, event, self)

    def mouseDragged_(self, event):
        if self.hotspot_tracker is not None:
            point = self.convertPoint_fromView_(event.locationInWindow(), nil)
            self.hotspot_tracker.update_position(point)
            self.hotspot_tracker.update_hit()
        else:
            self.SuperClass.mouseDragged_(self, event)

    def mouseUp_(self, event):
        if self.hotspot_tracker is not None:
            point = self.convertPoint_fromView_(event.locationInWindow(), nil)
            self.hotspot_tracker.update_position(point)
            self.hotspot_tracker.update_hit()
            if self.hotspot_tracker.hit:
                wrappermap.wrapper(self).send_hotspot_clicked()
            if self.hotspot_tracker:
                self.hotspot_tracker.redraw_cell()
                self.hotspot_tracker = None
        else:
            self.SuperClass.mouseUp_(self, event)

    def keyDown_(self, event):
        mods = osxmenus.translate_event_modifiers(event)
        if event.charactersIgnoringModifiers() == ' ' and len(mods) == 0:
            # handle spacebar with no modifiers by sending the row-activated
            # signal
            wrapper = wrappermap.wrapper(self)
            row = self.selectedRow()
            if row >= 0:
                iter = wrapper.model.iter_for_row(self, row)
                wrapper.emit('row-activated', iter)
        else:
            self.SuperClass.keyDown_(self, event)

class TableColumn(signals.SignalEmitter):
    def __init__(self, title, renderer, header=None, **attrs):
        signals.SignalEmitter.__init__(self)
        self.create_signal('clicked')
        self._column = MiroTableColumn.alloc().initWithIdentifier_(title)
        self._column.set_attrs(attrs)
        wrappermap.add(self._column, self)
        header_cell = MiroTableHeaderCell.alloc().init()
        self.custom_header = False
        if header:
            header_cell.set_widget(header)
            self.custom_header = True
        self._column.setHeaderCell_(header_cell)
        self._column.headerCell().setStringValue_(title)
        self._column.setEditable_(NO)
        self._column.setResizingMask_(NSTableColumnNoResizing)
        self.renderer = renderer
        self.sort_order_ascending = True
        self.sort_indicator_visible = False
        self.do_horizontal_padding = True
        self.min_width = self.max_width = None
        renderer.setDataCell_(self._column)

    def set_do_horizontal_padding(self, horizontal_padding):
        self.do_horizontal_padding = horizontal_padding

    def set_right_aligned(self, right_aligned):
        if right_aligned:
            self._column.headerCell().setAlignment_(NSRightTextAlignment)
        else:
            self._column.headerCell().setAlignment_(NSLeftTextAlignment)

    def set_min_width(self, width):
        self.min_width = width

    def set_max_width(self, width):
        self.max_width = width

    def set_width(self, width):
        self._column.setWidth_(width)

    def get_width(self):
        return self._column.width()

    def set_resizable(self, resizable):
        mask = 0
        if resizable:
            mask |= NSTableColumnUserResizingMask
        self._column.setResizingMask_(mask)

    def set_sort_indicator_visible(self, visible):
        self.sort_indicator_visible = visible
        self._column.tableView().headerView().setNeedsDisplay_(True)

    def get_sort_indicator_visible(self):
        return self.sort_indicator_visible

    def set_sort_order(self, ascending):
        self.sort_order_ascending = ascending
        self._column.tableView().headerView().setNeedsDisplay_(True)

    def get_sort_order_ascending(self):
        return self.sort_order_ascending

    def set_index(self, index):
        self.index = index
        self.renderer.set_index(index)

class MiroTableColumn(NSTableColumn):
    def set_attrs(self, attrs):
        self._attrs = attrs

    def attrs(self):
        return self._attrs

class MiroTableView(NSTableView):
    SuperClass = NSTableView
    for name, value in TableViewCommon.__dict__.items():
        locals()[name] = value

class MiroOutlineView(NSOutlineView):
    SuperClass = NSOutlineView
    for name, value in TableViewCommon.__dict__.items():
        locals()[name] = value

    def point_should_click(self, point, row):
        return not NSPointInRect(point, self.frameOfOutlineCellAtRow_(row))

class MiroTableHeaderView(NSTableHeaderView):
    def initWithFrame_(self, frame):
        # frame is not used
        self = super(MiroTableHeaderView, self).initWithFrame_(frame)
        self.selected = None
        self.custom_header = False
        return self

    def drawRect_(self, rect):
        wrapper = wrappermap.wrapper(self.tableView())
        if self.selected:
            self.selected.set_selected(False)
        for column in wrapper.columns:
            if column.sort_indicator_visible:
                self.selected = column._column.headerCell()
                self.selected.set_selected(True)
                self.selected.set_ascending(column.sort_order_ascending)
                break
        NSTableHeaderView.drawRect_(self, rect)
        if self.custom_header:
            NSGraphicsContext.currentContext().saveGraphicsState()
            # Draw the separator between the header and the contents.
            context = DrawingContext(self, rect, rect)
            context.set_line_width(1)
            context.set_color((2 / 255.0, 2 / 255.0, 2 / 255.0))
            context.move_to(0, context.height - 0.5)
            context.rel_line_to(context.width, 0)
            context.stroke()
            NSGraphicsContext.currentContext().restoreGraphicsState()

class MiroTableHeaderCell(NSTableHeaderCell):
    def init(self):
        self = super(MiroTableHeaderCell, self).init()
        self.layout_manager = LayoutManager()
        self.button = None
        return self

    def set_selected(self, selected):
        self.button._enabled = selected

    def set_ascending(self, ascending):
        self.button._ascending = ascending

    def set_widget(self, widget):
        self.button = widget

    def drawWithFrame_inView_(self, frame, view):
        if self.button is None:
            # use the default behavior when set_widget hasn't been called
            return NSTableHeaderCell.drawWithFrame_inView_(self, frame, view)

        NSGraphicsContext.currentContext().saveGraphicsState()
        drawing_rect = NSMakeRect(frame.origin.x, frame.origin.y,
                       frame.size.width, frame.size.height)
        context = DrawingContext(view, drawing_rect, drawing_rect)
        context.style = self.make_drawing_style(frame, view)
        self.layout_manager.reset()
        columns = wrappermap.wrapper(view.tableView()).columns
        header_cells = [c._column.headerCell() for c in columns]
        background_only = not self in header_cells
        self.button.draw(context, self.layout_manager, background_only)
        NSGraphicsContext.currentContext().restoreGraphicsState()

    def make_drawing_style(self, frame, view):
        text_color = None
        if (self.isHighlighted() and frame is not None and
                (view.isDescendantOf_(view.window().firstResponder()) or
                    view.gradientHighlight)):
            text_color = NSColor.whiteColor()
        return DrawingStyle(text_color=text_color)

class CocoaSelectionOwnerMixin(SelectionOwnerMixin):
    """Cocoa-specific methods for selection management.

    This subclass should not define any behavior. Methods that cannot be
    completed in this widget state should raise WidgetActionError.
    """

    def _set_allow_multiple_select(self, allow):
        self.tableview.setAllowsMultipleSelection_(allow)

    def _get_allow_multiple_select(self):
        return self.tableview.allowsMultipleSelection()

    def _get_selected_iters(self):
        selection = self.tableview.selectedRowIndexes()
        selrows = tablemodel.list_from_nsindexset(selection)
        return [self.model.iter_for_row(self.tableview, row) for row in selrows]

    def _get_selected_iter(self):
        row = self.tableview.selectedRow()
        if row == -1:
            return None
        return self.model.iter_for_row(self.tableview, row)

    def _get_selected_rows(self):
        return [self.model[i] for i in self._get_selected_iters()]

    @property
    def num_rows_selected(self):
        return self.tableview.numberOfSelectedRows()

    def _is_selected(self, iter_):
        row = self.row_of_iter(iter_)
        return self.tableview.isRowSelected_(row)

    def _select(self, iter_):
        row = self.row_of_iter(iter_)
        index_set = NSIndexSet.alloc().initWithIndex_(row)
        self.tableview.selectRowIndexes_byExtendingSelection_(index_set, YES)

    def _unselect(self, iter_):
        self.tableview.deselectRow_(self.row_of_iter(iter_))

    def _unselect_all(self):
        self.tableview.deselectAll_(nil)

    def _iter_to_string(self, iter_):
        return unicode(self.model.row_of_iter(self.tableview, iter_))

    def _iter_from_string(self, row):
        return self.model.iter_for_row(self.tableview, int(row))

class CocoaScrollbarOwnerMixin(ScrollbarOwnerMixin):
    """Manages a TableView's scroll position."""
    def __init__(self):
        ScrollbarOwnerMixin.__init__(self, _work_around_17153=True)
        self.scroll_position = (0, 0)
        self.clipview_notifications = None
        self._position_set = False

    def _set_scroll_position(self, scroll_to):
        """Restore a saved scroll position."""
        self.scroll_position = scroll_to
        try:
            scroller = self._scroller
        except errors.WidgetNotReadyError:
            return
        self._position_set = True
        clipview = scroller.contentView()
        if not self.clipview_notifications:
            self.clipview_notifications = NotificationForwarder.create(clipview)
            # NOTE: intentional changes are BoundsChanged; bad changes are
            # FrameChanged
            clipview.setPostsFrameChangedNotifications_(YES)
            self.clipview_notifications.connect(self.on_scroll_changed,
                'NSViewFrameDidChangeNotification')
        # NOTE: scrollPoint_ just scrolls the point into view; we want to
        # scroll the view so that the point becomes the origin
        size = self.tableview.visibleRect().size
        size = (size.width, size.height)
        rect = NSMakeRect(scroll_to[0], scroll_to[1], size[0], size[1])
        self.tableview.scrollRectToVisible_(rect)

    @property
    def _manually_scrolled(self):
        """Return whether the view has been scrolled explicitly by the user
        since the last time it was set automatically. Ignores X coords.
        """
        auto_y = self.scroll_position[1]
        real_y = self.get_scroll_position()[1]
        return abs(auto_y - real_y) > 5

    def _get_item_area(self, iter_):
        rect = self.tableview.rectOfRow_(self.row_of_iter(iter_))
        return NSRectToRect(rect)

    def _get_visible_area(self):
        return NSRectToRect(self._scroller.contentView().documentVisibleRect())

    def _get_scroll_position(self):
        point = self._scroller.contentView().documentVisibleRect().origin
        return NSPointToPoint(point)

    def on_scroll_changed(self, notification):
        # we get this notification when the scroll position has been reset (when
        # it should not have been); put it back
        self.set_scroll_position(self.scroll_position)
        # this notification also serves as the Cocoa equivalent to
        # on_scroll_range_changed, which tells super when we may be ready to
        # scroll to an iter
        self.emit('scroll-range-changed')

    def set_scroller(self, scroller):
        """For GTK; Cocoa tableview knows its enclosingScrollView"""

    @property
    def _scroller(self):
        """Return an NSScrollView or raise WidgetNotReadyError"""
        scroller = self.tableview.enclosingScrollView()
        if not scroller:
            raise errors.WidgetNotReadyError('enclosingScrollView')
        return scroller

class SorterPadding(NSView):
    # Why is this a Mac only widget?  Because the wrappermap mechanism requires
    # us to layout the widgets (so that we may call back to the portable API
    # hooks of the widget.  Since we only set the view component, this fake
    # widget is never placed so the wrappermap mechanism fails to work.
    #
    # So far, this is okay because only the Mac uses custom headers.
    def init(self):
        self = super(SorterPadding, self).init()
        image = Image(resources.path('images/headertoolbar.png'))
        self.image = ImageSurface(image)
        return self

    def isFlipped(self):
        return YES

    def drawRect_(self, rect):
        context = DrawingContext(self, self.bounds(), rect)
        context.style = DrawingStyle()
        self.image.draw(context, 0, 0, context.width, context.height)
        # XXX this color doesn't take into account enable/disabled state
        # of the sorting widgets.
        edge = 72.0 / 255
        context.set_color((edge, edge, edge))
        context.set_line_width(1)
        context.move_to(0.5, 0)
        context.rel_line_to(0, context.height)
        context.stroke()
        
class TableView(CocoaSelectionOwnerMixin, CocoaScrollbarOwnerMixin, Widget):
    """Displays data as a tabular list.  TableView follows the GTK TreeView
    widget fairly closely.
    """

    CREATES_VIEW = False
    # Bit of a hack.  We create several views.  By setting CREATES_VIEW to
    # False, we get to position the views manually.

    draws_selection = True

    def __init__(self, model, custom_headers=False):
        Widget.__init__(self)
        CocoaSelectionOwnerMixin.__init__(self)
        CocoaScrollbarOwnerMixin.__init__(self)
        self.create_signal('hotspot-clicked')
        self.create_signal('row-clicked')
        self.create_signal('row-activated')
        self.create_signal('reallocate-columns')
        self.model = model
        self.columns = []
        self.drag_source = self.drag_dest = None
        self.context_menu_callback = None
        if isinstance(model, tablemodel.ItemListModel):
            self.tableview = MiroTableView.alloc().init()
            self.data_source = tablemodel.MiroItemListDataSource.alloc()
        elif self.is_tree():
            self.create_signal('row-expanded')
            self.create_signal('row-collapsed')
            self.tableview = MiroOutlineView.alloc().init()
            self.data_source = tablemodel.MiroOutlineViewDataSource.alloc()
        else:
            self.tableview = MiroTableView.alloc().init()
            self.data_source = tablemodel.MiroTableViewDataSource.alloc()
        types = (tablemodel.MIRO_DND_ITEM_LOCAL,)
        self.tableview.registerForDraggedTypes_(types)
        self.view = self.tableview
        self.data_source.initWithModel_(self.model)
        self.tableview.setDataSource_(self.data_source)
        self.tableview.setVerticalMotionCanBeginDrag_(YES)
        self.set_columns_draggable(False)
        self.set_auto_resizes(False)
        self.row_height_set = False
        self.set_fixed_height(False)
        self.auto_resizing = False
        self.header_view = MiroTableHeaderView.alloc().initWithFrame_(
            NSMakeRect(0, 0, 0, 0))
        self.tableview.setCornerView_(None)
        self.custom_header = False
        self.header_height = HEADER_HEIGHT
        self.set_show_headers(True)
        self.notifications = NotificationForwarder.create(self.tableview)
        self.model_signal_ids = [
            self.model.connect_weak('row-changed', self.on_row_change),
            self.model.connect_weak('structure-will-change',
                    self.on_model_structure_change),
        ]
        self.iters_to_update = []
        self.height_changed = self.reload_needed = False
        self.old_selection = None
        self._resizing = False
        if custom_headers:
            self._enable_custom_headers()

    def unset_model(self):
        for signal_id in self.model_signal_ids:
            self.model.disconnect(signal_id)
        self.model = None
        self.tableview.setDataSource_(None)
        self.data_source = None

    def _enable_custom_headers(self):
        self.custom_header = True
        self.header_height = CUSTOM_HEADER_HEIGHT
        self.header_view.custom_header = True
        self.tableview.setCornerView_(SorterPadding.alloc().init())

    def enable_album_view_focus_hack(self):
        # this only matters on GTK
        pass

    def focus(self):
        if self.tableview.window() is not None:
            self.tableview.window().makeFirstResponder_(self.tableview)

    def send_hotspot_clicked(self):
        tracker = self.tableview.hotspot_tracker
        self.emit('hotspot-clicked', tracker.name, tracker.iter)

    def on_row_change(self, model, iter):
        self.iters_to_update.append(iter)
        if not self.fixed_height:
            self.height_changed = True
        if self.tableview.hotspot_tracker is not None:
            self.tableview.hotspot_tracker.update_hit()

    def on_model_structure_change(self, model):
        self.will_need_reload()
        self.cancel_hotspot_track()

    def will_need_reload(self):
        if not self.reload_needed:
            self.reload_needed = True
            self.old_selection = self._get_selected_rows()

    def cancel_hotspot_track(self):
        if self.tableview.hotspot_tracker is not None:
            self.tableview.hotspot_tracker.redraw_cell()
            self.tableview.hotspot_tracker = None

    def on_expanded(self, notification):
        self.invalidate_size_request()
        item = notification.userInfo()['NSObject']
        iter_ = self.model.iter_for_item[item]
        self.emit('row-expanded', iter_)

    def on_collapsed(self, notification):
        self.invalidate_size_request()
        item = notification.userInfo()['NSObject']
        iter_ = self.model.iter_for_item[item]
        self.emit('row-collapsed', iter_)

    def on_column_resize(self, notification):
        if self.auto_resizing or self._resizing:
            return
        self._resizing = True
        try:
            column = notification.userInfo()['NSTableColumn']
            label = column.headerCell().stringValue()
            self.emit('reallocate-columns', {label: column.width()})
        finally:
            self._resizing = False

    def is_tree(self):
        return isinstance(self.model, tablemodel.TreeTableModel)

    def set_row_expanded(self, iter, expanded):
        """Expand or collapse the specified row. Succeeds or raises
        WidgetActionError.
        """
        item = iter.value()
        if expanded:
            self.tableview.expandItem_(item)
        else:
            self.tableview.collapseItem_(item)
        if self.tableview.isItemExpanded_(item) != expanded:
            raise errors.WidgetActionError(
                "cannot expand iter. expandable: %r" % (
                    self.tableview.isExpandable_(item),))
        self.invalidate_size_request()

    def is_row_expanded(self, iter):
        return self.tableview.isItemExpanded_(iter.value())

    def calc_size_request(self):
        self.tableview.tile()
        height = self.tableview.frame().size.height
        if self._show_headers:
            height += self.header_height
        return self.calc_width(), height

    def viewport_repositioned(self):
        self._do_layout()

    def viewport_created(self):
        wrappermap.add(self.tableview, self)
        self._do_layout()
        self._add_views()
        if self.is_tree():
            self.notifications.connect(self.on_expanded,
                'NSOutlineViewItemDidExpandNotification')
            self.notifications.connect(self.on_collapsed,
                'NSOutlineViewItemDidCollapseNotification')
            self.notifications.connect(self.on_selection_changed,
                    'NSOutlineViewSelectionDidChangeNotification')
            self.notifications.connect(self.on_column_resize,
                    'NSOutlineViewColumnDidResizeNotification')
        else:
            self.notifications.connect(self.on_selection_changed,
                    'NSTableViewSelectionDidChangeNotification')
            self.notifications.connect(self.on_column_resize,
                    'NSTableViewColumnDidResizeNotification')
        # scroll has been unset
        self._position_set = False

    def remove_viewport(self):
        if self.viewport is not None:
            self._remove_views()
            wrappermap.remove(self.tableview)
            self.notifications.disconnect()
            self.viewport = None
        if self.clipview_notifications:
            self.clipview_notifications.disconnect()
            self.clipview_notifications = None

    def _should_place_header_view(self):
        return self._show_headers and not self.parent_is_scroller

    def _add_views(self):
        self.viewport.view.addSubview_(self.tableview)
        if self._should_place_header_view():
            self.viewport.view.addSubview_(self.header_view)

    def _remove_views(self):
        self.tableview.removeFromSuperview()
        self.header_view.removeFromSuperview()

    def _do_layout(self):
        x = self.viewport.placement.origin.x
        y = self.viewport.placement.origin.y
        width = self.viewport.get_width()
        height = self.viewport.get_height()
        if self._should_place_header_view():
            self.header_view.setFrame_(NSMakeRect(x, y,
                width, self.header_height))
            self.tableview.setFrame_(NSMakeRect(x, y + self.header_height, 
                width, height - self.header_height))
        else:
            self.header_view.setFrame_(NSMakeRect(x, y,
                width, self.header_height))
            self.tableview.setFrame_(NSMakeRect(x, y, width, height))

        if self.auto_resize:
            self.auto_resizing = True
            # ListView sizes itself in do_size_allocated;
            # this is necessary for tablist and StandardView
            columns = self.tableview.tableColumns()
            if len(columns) == 1:
                columns[0].setWidth_(self.viewport.area().size.width)
            self.auto_resizing = False
        self.queue_redraw()

    def calc_width(self):
        if self.column_count() == 0:
            return 0
        width = 0
        columns = self.tableview.tableColumns()
        if self.auto_resize:
            # Table auto-resizes, we can shrink to min-width for each column
            width = sum(column.minWidth() for column in columns)
            width += self.tableview.column_spacing * self.column_count()
        else:
            # Table doesn't auto-resize, the columns can't get smaller than
            # their current width
            width = sum(column.width() for column in columns)
        return width

    def start_bulk_change(self):
        # stop our model from emitting signals, which is slow if we're
        # adding/removing/changing a bunch of rows.  Instead, just reload the
        # model afterwards.
        self.will_need_reload()
        self.cancel_hotspot_track()
        self.model.freeze_signals()

    def model_changed(self):
        if not self.row_height_set and self.fixed_height:
            self.try_to_set_row_height()
        self.model.thaw_signals()
        size_changed = False
        if self.reload_needed:
            self.tableview.reloadData()
            new_selection = self._get_selected_rows()
            if new_selection != self.old_selection:
                self.on_selection_changed(self.tableview)
            self.old_selection = None
            size_changed = True
        elif self.iters_to_update:
            if self.fixed_height or not self.height_changed:
                # our rows don't change height, just update cell areas
                if self.is_tree():
                    for iter in self.iters_to_update:
                        self.tableview.reloadItem_(iter.value())
                else:
                    for iter in self.iters_to_update:
                        row = self.row_of_iter(iter)
                        rect = self.tableview.rectOfRow_(row)
                        self.tableview.setNeedsDisplayInRect_(rect)
            else:
                # our rows can change height inform Cocoa that their heights
                # might have changed (this will redraw them)
                index_set = NSMutableIndexSet.alloc().init()
                for iter in self.iters_to_update:
                    try:
                        index_set.addIndex_(self.row_of_iter(iter))
                    except LookupError:
                        # This happens when the iter's parent is unexpanded,
                        # just ignore.
                        pass
                self.tableview.noteHeightOfRowsWithIndexesChanged_(index_set)
                size_changed = True
        else:
            return
        if size_changed:
            self.invalidate_size_request()
        self.height_changed = self.reload_needed = False
        self.iters_to_update = []

    def width_for_columns(self, width):
        """If the table is width pixels big, how much width is available for
        the table's columns.
        """
        # XXX this used to do some calculation with the spacing of each column,
        # but it doesn't appear like we need it to be that complicated anymore
        # (see #18273)
        return width - 2

    def set_column_spacing(self, column_spacing):
        self.tableview.column_spacing = column_spacing

    def set_row_spacing(self, row_spacing):
        self.tableview.row_spacing = row_spacing

    def set_alternate_row_backgrounds(self, setting):
        self.tableview.setUsesAlternatingRowBackgroundColors_(setting)

    def set_grid_lines(self, horizontal, vertical):
        mask = 0
        if horizontal:
            mask |= NSTableViewSolidHorizontalGridLineMask
        if vertical:
            mask |= NSTableViewSolidVerticalGridLineMask
        self.tableview.setGridStyleMask_(mask)

    def set_gradient_highlight(self, setting):
        self.tableview.gradientHighlight = setting

    def set_group_lines_enabled(self, enabled):
        self.tableview.group_lines_enabled = enabled
        self.queue_redraw()

    def set_group_line_style(self, color, width):
        self.tableview.group_line_color = color + (1.0,)
        self.tableview.group_line_width = width
        self.queue_redraw()

    def get_tooltip(self, iter, column):
        return None

    def add_column(self, column):
        if not self.custom_header == column.custom_header:
            raise ValueError('Column header does not match type '
                             'required by TableView')
        self.columns.append(column)
        self.tableview.addTableColumn_(column)
        self._set_min_max_column_widths(column)
        if self.column_count() == 1 and self.is_tree():
            self.tableview.setOutlineTableColumn_(column._column)
            column.renderer.outline_column = True
        # Adding a column means that each row could have a different height.
        # call noteNumberOfRowsChanged() to have OS X recalculate the heights
        self.tableview.noteNumberOfRowsChanged()
        self.invalidate_size_request()
        self.try_to_set_row_height()

    def _set_min_max_column_widths(self, column):
        if column.do_horizontal_padding:
            spacing = self.tableview.column_spacing
        else:
            spacing = 0
        if column.min_width > 0:
            column._column.setMinWidth_(column.min_width + spacing)
        if column.max_width > 0:
            column._column.setMaxWidth_(column.max_width + spacing)

    def column_count(self):
        return len(self.tableview.tableColumns())

    def remove_column(self, index):
        column = self.columns.pop(index)
        self.tableview.removeTableColumn_(column._column)
        self.invalidate_size_request()

    def get_columns(self):
        titles = []
        columns = self.tableview.tableColumns()
        for column in columns:
            titles.append(column.headerCell().stringValue())
        return titles

    def set_background_color(self, (red, green, blue)):
        color = NSColor.colorWithDeviceRed_green_blue_alpha_(red, green, blue,
                1.0)
        self.tableview.setBackgroundColor_(color)

    def set_show_headers(self, show):
        self._show_headers = show
        if show:
            self.tableview.setHeaderView_(self.header_view)
        else:
            self.tableview.setHeaderView_(None)
        if self.viewport is not None:
            self._remove_views()
            self._do_layout()
            self._add_views()
        self.invalidate_size_request()
        self.queue_redraw()
    
    def is_showing_headers(self):
        return self._show_headers

    def set_search_column(self, model_index):
        pass

    def try_to_set_row_height(self):
        if len(self.model) > 0:
            first_iter = self.model.first_iter()
            height = calc_row_height(self.tableview, self.model[first_iter])
            self.tableview.setRowHeight_(height)
            self.row_height_set = True

    def set_auto_resizes(self, setting):
        self.auto_resize = setting

    def set_columns_draggable(self, dragable):
        self.tableview.setAllowsColumnReordering_(dragable)

    def set_fixed_height(self, fixed):
        if fixed:
            self.fixed_height = True
            if self.is_tree():
                delegate_class = OutlineViewDelegate
            else:
                delegate_class = TableViewDelegate
            self.row_height_set = False
            self.try_to_set_row_height()
        else:
            self.fixed_height = False
            if self.is_tree():
                delegate_class = VariableHeightOutlineViewDelegate
            else:
                delegate_class = VariableHeightTableViewDelegate
        self.delegate = delegate_class.alloc().init()
        self.tableview.setDelegate_(self.delegate)
        self.tableview.reloadData()

    def row_of_iter(self, iter):
        return self.model.row_of_iter(self.tableview, iter)

    def set_context_menu_callback(self, callback):
        self.context_menu_callback = callback

    # disable the drag when the cells are constantly updating.  Mac OS X
    # deals badly with this..
    def set_volatile(self, volatile):
        if volatile:
            self.data_source.setDragSource_(None)
            self.data_source.setDragDest_(None)
        else:
            self.data_source.setDragSource_(self.drag_source)
            self.data_source.setDragDest_(self.drag_dest)

    def set_drag_source(self, drag_source):
        self.drag_source = drag_source
        self.data_source.setDragSource_(drag_source)

    def set_drag_dest(self, drag_dest):
        self.drag_dest = drag_dest
        if drag_dest is None:
            self.data_source.setDragDest_(None)
        else:
            types = drag_dest.allowed_types()
            self.data_source.setDragDest_(drag_dest)
