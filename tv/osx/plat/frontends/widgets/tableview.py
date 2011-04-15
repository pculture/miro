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

from __future__ import with_statement # for python2.5

import math
import logging
from contextlib import contextmanager

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

from miro import signals
from miro import errors
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets.tableselection import SelectionOwnerMixin
from miro.plat import resources
from miro.plat.utils import filename_to_unicode
from miro.plat.frontends.widgets import osxmenus
from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets import tablemodel
from miro.plat.frontends.widgets.base import Widget
from miro.plat.frontends.widgets.drawing import DrawingContext, DrawingStyle, Gradient
from miro.plat.frontends.widgets.helpers import NotificationForwarder
from miro.plat.frontends.widgets.layoutmanager import LayoutManager
from miro.plat.frontends.widgets.widgetset import CustomButton


# Disclosure button used as a reference in get_left_offset()
_disclosure_button = NSButton.alloc().init()
_disclosure_button.setButtonType_(NSOnOffButton)
_disclosure_button.setBezelStyle_(NSDisclosureBezelStyle)
_disclosure_button.sizeToFit()
_disclosure_button_width = _disclosure_button.frame().size.width 

EXPANDER_PADDING = 6
HEADER_HEIGHT = 17
CUSTOM_HEADER_HEIGHT = 25

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

class MiroTableInfoListTextCell(MiroTableCell):
    def initWithAttrGetter_(self, attr_getter):
        self = self.init()
        self.setWraps_(NO)
        self.attr_getter = attr_getter
        self._textColor = self.textColor()
        return self

    def drawWithFrame_inView_(self, frame, view):
        if self.isHighlighted():
            self.setTextColor_(NSColor.whiteColor())
        else:
            self.setTextColor_(self._textColor)
        return MiroTableCell.drawWithFrame_inView_(self, frame, view)

    def setObjectValue_(self, value):
        if isinstance(value, tuple):
            info, attrs = value
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

class CellRendererBase(object):
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
                    view.gradientHighlight)):
            text_color = NSColor.whiteColor()
        return DrawingStyle(text_color=text_color)

    def drawInteriorWithFrame_inView_(self, frame, view):
        NSGraphicsContext.currentContext().saveGraphicsState()
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
        self.wrapper.render(context, self.layout_manager, self.isHighlighted(),
                self.hotspot, hover_pos)
        NSGraphicsContext.currentContext().restoreGraphicsState()

    def setObjectValue_(self, value):
        self.object_value = value

    def set_wrapper_data(self):
        self.wrapper.__dict__.update(self.object_value)

class CustomCellRenderer(CellRendererBase):
    CellClass = CustomTableCell

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
    
class InfoListTableCell(CustomTableCell):
    def set_wrapper_data(self):
        self.wrapper.info, self.wrapper.attrs = self.object_value

class InfoListRenderer(CustomCellRenderer):
    CellClass = InfoListTableCell

    def hotspot_test(self, style, layout, x, y, width, height):
        return None

class InfoListRendererText(CellRenderer):
    def build_cell(self):
        cell = MiroTableInfoListTextCell.alloc()
        return cell.initWithAttrGetter_(self.get_value)

def calc_row_height(view, model_row):
    row_height = 0
    model = view.dataSource().model
    for column in view.tableColumns():
        cell = column.dataCell()
        data = model.get_column_data(model_row, column)
        cell.setObjectValue_(data)
        cell_height = cell.calcHeight_(view)
        row_height = max(row_height, cell_height)
    if row_height == 0:
        row_height = 12
    return row_height

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
        self._column_wrappers = []
        self.tracking_area = None
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
        self._column_wrappers.append(column)
        self.column_index_map[column._column] = index
        self.SuperClass.addTableColumn_(self, column._column)

    def removeTableColumn_(self, column):
        self.SuperClass.removeTableColumn_(self, column)
        removed = self.column_index_map.pop(column)
        for key, index in self.column_index_map.items():
            if index > removed:
                self.column_index_map[key] -= 1
        for column in self._column_wrappers[:]:
            if column._column == column:
                del self._column_wrappers[column]

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
            start_color = (0.588, 0.717, 0.843)
            end_color = (0.416, 0.568, 0.713)
            top_line_color = (0.416, 0.569, 0.714, 1.0)
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
                wrapper.emit('row-double-clicked', iter)
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
                self.hotspot_tracker.redraw_cell()
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
        row = self.rowAtPoint_(point)
        self.popup_context_menu(row, event)

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
        self._column = NSTableColumn.alloc().initWithIdentifier_(attrs)
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
        renderer.setDataCell_(self._column)

    def set_do_horizontal_padding(self, horizontal_padding):
        self.do_horizontal_padding = horizontal_padding

    def set_right_aligned(self, right_aligned):
        if right_aligned:
            self._column.headerCell().setAlignment_(NSRightTextAlignment)
        else:
            self._column.headerCell().setAlignment_(NSLeftTextAlignment)

    def set_min_width(self, width):
        self._column.setMinWidth_(width)

    def set_max_width(self, width):
        self._column.setMaxWidth_(width)

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
        self.custom_header = False
        self.selected = None
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
        self.button.draw(context, self.layout_manager)
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

class ScrollbarOwnerMixin(object):
    """Manages a TableView's scroll position."""
    def __init__(self):
        self.scroll_position = (0, 0)
        self.clipview_notifications = None

    def scroll_to_iter(self, iter):
        self.tableview.scrollRowToVisible_(self.row_of_iter(iter))

    def set_scroll_position(self, scroll_to=None):
        """Restore a saved scroll position."""
        if scroll_to: # widgetstate restoring a saved position
            self.scroll_position = scroll_to
        else: # fixing position if it has changed
            scroll_to = self.scroll_position
        if self.get_scroll_position() == scroll_to: # position already correct
            return
        scroller = self.tableview.enclosingScrollView()
        if not scroller: # scroller not set yet
            return
        content = scroller.contentView() # NSClipView
        if not self.clipview_notifications:
            self.clipview_notifications = NotificationForwarder.create(content)
            # NOTE: intentional changes are BoundsChanged; bad changes are
            # FrameChanged
            content.setPostsFrameChangedNotifications_(YES)
            self.clipview_notifications.connect(self.on_scroll_changed,
                'NSViewFrameDidChangeNotification')
        # NOTE: scrollPoint_ just scrolls the point into view; we want to
        # scroll the view so that the point becomes the origin
        size = scroller.contentView().documentVisibleRect().size
        size = (size.width, size.height)
        rect = NSMakeRect(scroll_to[0], scroll_to[1], size[0], size[1])
        self.tableview.scrollRectToVisible_(rect)

    def get_scroll_position(self):
        scroller = self.tableview.enclosingScrollView()
        if not scroller:
            # no scroller yet
            return 0, 0
        # NOTE: getDoubleValue * contentSize is different from
        # documentVisibleRect.origin.
        point = scroller.contentView().documentVisibleRect().origin
        # NOTE: scroller.enclosingScrollView().contentView() gets this view's
        # NSClipView
        return int(point.x), int(point.y)
    
    def on_scroll_changed(self, notification):
        self.set_scroll_position()

    def set_scroller(self, scroller):
        """For GTK; Cocoa tableview knows its enclosingScrollView"""

class TableView(CocoaSelectionOwnerMixin, ScrollbarOwnerMixin, Widget):
    """Displays data as a tabular list.  TableView follows the GTK TreeView
    widget fairly closely.
    """

    CREATES_VIEW = False
    # Bit of a hack.  We create several views.  By setting CREATES_VIEW to
    # False, we get to position the views manually.

    draws_selection = True

    def __init__(self, model):
        Widget.__init__(self)
        SelectionOwnerMixin.__init__(self)
        ScrollbarOwnerMixin.__init__(self)
        self.create_signal('hotspot-clicked')
        self.create_signal('row-double-clicked')
        self.create_signal('row-clicked')
        self.create_signal('row-activated')
        self.create_signal('reallocate-columns')
        self.model = model
        self.columns = []
        self.drag_source = None
        self.context_menu_callback = None
        if isinstance(model, tablemodel.InfoListModel):
            self.tableview = MiroTableView.alloc().init()
            self.data_source = tablemodel.MiroInfoListDataSource.alloc()
        elif self.is_tree():
            self.create_signal('row-expanded')
            self.create_signal('row-collapsed')
            self.tableview = MiroOutlineView.alloc().init()
            self.data_source = tablemodel.MiroOutlineViewDataSource.alloc()
        else:
            self.tableview = MiroTableView.alloc().init()
            self.data_source = tablemodel.MiroTableViewDataSource.alloc()
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
        self.header_view.custom_header = False
        self.custom_header = 0
        self.header_height = HEADER_HEIGHT
        self.set_show_headers(True)
        self.notifications = NotificationForwarder.create(self.tableview)
        self.model.connect_weak('row-changed', self.on_row_change)
        self.model.connect_weak('structure-will-change',
                self.on_model_structure_change)
        self.iters_to_update = []
        self.height_changed = self.reload_needed = False
        self._resizing = False

    def focus(self):
        if self.tableview.window() is not None:
            self.tableview.window().makeFirstResponder_(self.tableview)

    def send_hotspot_clicked(self):
        tracker = self.tableview.hotspot_tracker
        self.emit('hotspot-clicked', tracker.name, tracker.iter)

    def get_left_offset(self):
        offset = self.tableview.intercellSpacing().width / 2
        # Yup this can be a non-integer, it seems like that's what OS X does,
        # because either way I round it looks worse than this.
        if self.is_tree():
            offset +=  _disclosure_button_width + EXPANDER_PADDING
        return offset

    def on_row_change(self, model, iter):
        self.iters_to_update.append(iter)
        if not self.fixed_height:
            self.height_changed = True
        if self.tableview.hotspot_tracker is not None:
            self.tableview.hotspot_tracker.update_hit()

    def on_model_structure_change(self, model):
        self.reload_needed = True
        self.cancel_hotspot_track()

    def cancel_hotspot_track(self):
        if self.tableview.hotspot_tracker is not None:
            self.tableview.hotspot_tracker.redraw_cell()
            self.tableview.hotspot_tracker = None

    def on_expanded(self, notification):
        self.invalidate_size_request()
        item = notification.userInfo()['NSObject']
        iter_ = self.model.iter_for_item[item]
        self.emit('row-expanded', iter_, self.model.get_path(iter_))

    def on_collapsed(self, notification):
        self.invalidate_size_request()
        item = notification.userInfo()['NSObject']
        iter_ = self.model.iter_for_item[item]
        self.emit('row-collapsed', iter_, self.model.get_path(iter_))

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
            raise errors.WidgetActionError("cannot expand iter. expandable: %s",
                    repr(self.tableview.isExpandable_(item)))
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
            width += self.tableview.intercellSpacing().width * self.column_count()
        else:
            # Table doesn't auto-resize, the columns can't get smaller than
            # their current width
            width = sum(column.width() for column in columns)
        return width

    def start_bulk_change(self):
        # stop our model from emitting signals, which is slow if we're
        # adding/removing/changing a bunch of rows.  Instead, just reload the
        # model afterwards.
        self.reload_needed = True
        self.cancel_hotspot_track()
        self.model.freeze_signals()

    def model_changed(self):
        if not self.row_height_set and self.fixed_height:
            self.try_to_set_row_height()
        self.model.thaw_signals()
        size_changed = False
        if self.reload_needed:
            self.tableview.reloadData()
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
        self.set_scroll_position()

    def width_for_columns(self, width):
        """If the table is width pixels big, how much width is available for
        the table's columns.
        """
        spacing = self.tableview.intercellSpacing().width * self.column_count()
        return width - spacing

    def set_column_spacing(self, column_spacing):
        spacing = self.tableview.intercellSpacing()
        spacing.width = column_spacing
        self.tableview.setIntercellSpacing_(spacing)

    def set_row_spacing(self, row_spacing):
        spacing = self.tableview.intercellSpacing()
        spacing.height = row_spacing
        self.tableview.setIntercellSpacing_(spacing)

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

    def get_tooltip(self, iter, column):
        return None

    def add_column(self, column):
        if column.custom_header:
            self.header_view.custom_header = True
            self.custom_header += 1
            self.header_height = CUSTOM_HEADER_HEIGHT
        self.columns.append(column)
        self.tableview.addTableColumn_(column)
        if self.column_count() == 1 and self.is_tree():
            self.tableview.setOutlineTableColumn_(column._column)
            column.renderer.outline_column = True
        # Adding a column means that each row could have a different height.
        # call noteNumberOfRowsChanged() to have OS X recalculate the heights
        self.tableview.noteNumberOfRowsChanged()
        self.invalidate_size_request()
        self.try_to_set_row_height()

    def column_count(self):
        return len(self.tableview.tableColumns())

    def remove_column(self, index):
        column = self.columns.pop(index)
        if column.custom_header:
            self.custom_header -= 1
        if self.custom_header == 0:
            self.header_view.custom_header = False
            self.header_height = HEADER_HEIGHT
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
            self.tableview.unregisterDraggedTypes()
            self.data_source.setDragDest_(None)
        else:
            types = drag_dest.allowed_types()
            self.tableview.registerForDraggedTypes_(types)
            self.data_source.setDragDest_(drag_dest)
