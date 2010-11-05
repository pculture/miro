# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

from miro import signals
from miro.frontends.widgets import widgetconst
from miro.plat.frontends.widgets import osxmenus
from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets import tablemodel
from miro.plat.frontends.widgets.base import Widget, FlippedView
from miro.plat.frontends.widgets.drawing import DrawingContext, DrawingStyle, Gradient
from miro.plat.frontends.widgets.helpers import NotificationForwarder
from miro.plat.frontends.widgets.layoutmanager import LayoutManager


# Disclosure button used as a reference in get_left_offset()
_disclosure_button = NSButton.alloc().init()
_disclosure_button.setButtonType_(NSOnOffButton)
_disclosure_button.setBezelStyle_(NSDisclosureBezelStyle)
_disclosure_button.sizeToFit()
_disclosure_button_width = _disclosure_button.frame().size.width 

EXPANDER_PADDING = 6
HEADER_HEIGHT = 17

def _pack_row_column(row, column):
    """Convert a row, column pair into a integer suitable for passing to
    NSView.addTrackingRect_owner_userData_assumeInside_.
    """
    if column > (1 << 16):
        raise ValueError("column value too big: ", column)
    return (row << 16) + column

def _unpack_row_column(value):
    """Reverse the work of _pack_row_column()."""
    row = value >> 16
    column = value & ((1 << 16) - 1)
    return row, column

class HotspotTracker(object):
    """Contains the info on the currently tracked hotspot.  See:
    https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPITableView
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
        row = self.tableview.dataSource().model[self.iter]
        value_dict = tablemodel.get_column_data(row, self.table_column)
        self.cell.setObjectValue_(value_dict)

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

class CellRenderer(object):
    def __init__(self):
        self.cell = MiroTableCell.alloc().init()

    def setDataCell_(self, column):
        column.setDataCell_(self.cell)

    def set_text_size(self, size):
        if size == widgetconst.SIZE_NORMAL:
            self.cell.setFont_(NSFont.systemFontOfSize_(NSFont.systemFontSize()))
        elif size == widgetconst.SIZE_SMALL:
            self.cell.setFont_(NSFont.systemFontOfSize_(11))
        else:
            raise ValueError("Unknown size: %s" % size)

    def set_bold(self, bold):
        if bold:
            font = NSFont.boldSystemFontOfSize_(NSFont.systemFontSize())
        else:
            font = NSFont.systemFontOfSize_(NSFont.systemFontSize())
        self.cell.setFont_(font)

    def set_color(self, color):
        color = NSColor.colorWithDeviceRed_green_blue_alpha_(color[0],
                color[1], color[2], 1.0)
        self.cell.setTextColor_(color)

class ImageCellRenderer(object):
    def setDataCell_(self, column):
        column.setDataCell_(MiroTableImageCell.alloc().init())

class CheckboxCellRenderer(signals.SignalEmitter):
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
        self.wrapper.render(context, self.layout_manager, self.isHighlighted(),
                self.hotspot, view.cell_is_hovered(self.row, self.column))
        NSGraphicsContext.currentContext().restoreGraphicsState()

    def setObjectValue_(self, value_dict):
        self.value_dict = value_dict

    def set_wrapper_data(self):
        self.wrapper.__dict__.update(self.value_dict)

class CustomCellRenderer(object):
    def __init__(self):
        self.outline_column = False

    def setDataCell_(self, column):
        # Note that the ownership is the opposite of what happens in widgets.
        # The NSObject owns it's wrapper widget.  This happens for a couple
        # reasons:
        # 1) The data cell gets copied a bunch of times, so wrappermap won't
        # work with it.
        # 2) The Wrapper should only needs to stay around as long as the
        # NSCell that it's wrapping is around.  Once the column gets removed
        # from the table, the wrapper can be deleted.
        nscell = CustomTableCell.alloc().init()
        nscell.wrapper = self
        column.setDataCell_(nscell)

    def hotspot_test(self, style, layout, x, y, width, height):
        return None

def calc_row_height(view, model_row):
    row_height = 0
    for column in view.tableColumns():
        cell = column.dataCell()
        value_dict = tablemodel.get_column_data(model_row, column)
        cell.setObjectValue_(value_dict)
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
        iter = table_view.dataSource().model.iter_for_row(table_view, row)
        if iter is None:
            return 12
        return calc_row_height(table_view, iter.value().values)

class OutlineViewDelegate(NSObject):
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
        return self

    def addTableColumn_(self, column):
        self.column_index_map[column] = len(self.tableColumns())
        self.SuperClass.addTableColumn_(self, column)

    def removeTableColumn_(self, column):
        del self.column_index_map[column]
        for after_index in xrange(index+1, len(self.tableColumns())):
            self.column_index_map[column_list[after_index]] -= 1
        self.SuperClass.removeTableColumn_(self, column)

    def moveColumn_toColumn_(self, src, dest):
        # Need to switch the TableColumn objects too
        columns = wrappermap.wrapper(self).columns
        columns[src], columns[dest] = columns[dest], columns[src]
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
        if focused:
            start_color = (0.412, 0.584, 0.792)
            end_color = (0.153, 0.345, 0.62)
            line_color = NSColor.colorWithDeviceRed_green_blue_alpha_(
                    0.322, 0.506, 0.733, 1.0)
        else:
            start_color = (0.671, 0.694, 0.776)
            end_color = (0.447, 0.471, 0.596)
            line_color = NSColor.colorWithDeviceRed_green_blue_alpha_(
                    0.514, 0.537, 0.655, 1.0)

        rect = self.rectOfRow_(row)
        top = NSMakeRect(rect.origin.x, rect.origin.y, rect.size.width, 1)
        context.saveGraphicsState()
        # draw the top line
        line_color.set()
        NSRectFill(top)
        # draw the gradient
        rect.origin.y += 1
        rect.size.height -= 1
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

    def recalcTrackingRects(self):
        # We aren't using mouse hover for 2.0, so let's skip this.  It just
        # wastes CPU cycles
        return
        if self.hover_info is not None:
            rect = self.frameOfCellAtColumn_row_(self.hover_info[1],
                    self.hover_info[0])
            self.hover_info = None
            self.setNeedsDisplayInRect_(rect)
        for tr in self._tracking_rects:
            self.removeTrackingRect_(tr)
        visible = self.visibleRect()
        row_range = self.rowsInRect_(visible)
        column_range = self.columnsInRect_(visible)
        self._tracking_rects = []
        for row in xrange(row_range.location, row_range.location +
                row_range.length):
            for column in xrange(column_range.location, column_range.location
                    + column_range.length):
                rect = self.frameOfCellAtColumn_row_(column, row)
                tr = self.addTrackingRect_owner_userData_assumeInside_( rect,
                        self, _pack_row_column(row, column), False)
                self._tracking_rects.append(tr)

    def mouseEntered_(self, event):
        window = self.window()
        if window is not nil and window.isMainWindow():
            row, column = _unpack_row_column(event.userData())
            self.hover_info = (row, column)
            rect = self.frameOfCellAtColumn_row_(column, row)
            self.setNeedsDisplayInRect_(rect)

    def mouseExited_(self, event):
        window = self.window()
        if window is not nil and window.isMainWindow():
            row, column = _unpack_row_column(event.userData())
            if self.hover_info == (row, column):
                self.hover_info = None
            rect = self.frameOfCellAtColumn_row_(column, row)
            self.setNeedsDisplayInRect_(rect)

    def cell_is_hovered(self, row, column):
        return self.hover_info == (row, column)

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
            if row != -1:
                iter = wrapper.model.iter_for_row(self, row)
                wrapper.emit('row-double-clicked', iter)
            return

        hotspot_tracker = HotspotTracker(self, point)
        if hotspot_tracker.hit:
            self.hotspot_tracker = hotspot_tracker
            self.hotspot_tracker.redraw_cell()
            self.handled_last_mouse_down = True
        else:
            self.handled_last_mouse_down = False
            self.SuperClass.mouseDown_(self, event)

    def rightMouseDown_(self, event):
        self.handleContextMenu_(event)

    def handleContextMenu_(self, event):
        self.window().makeFirstResponder_(self)
        point = self.convertPoint_fromView_(event.locationInWindow(), nil)
        row = self.rowAtPoint_(point)
        selection = self.selectedRowIndexes()
        if not selection.containsIndex_(row):
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

class TableColumn(signals.SignalEmitter):
    def __init__(self, title, renderer, **attrs):
        signals.SignalEmitter.__init__(self)
        self.create_signal('clicked')
        self._column = NSTableColumn.alloc().initWithIdentifier_(attrs)
        self._column.setHeaderCell_(MiroTableHeaderCell.alloc().init())
        self._column.headerCell().setStringValue_(title)
        self._column.setEditable_(NO)
        self._column.setResizingMask_(NSTableColumnNoResizing)
        self.renderer = renderer
        self.sort_order_ascending = True
        self.sort_indicator_visible = False
        renderer.setDataCell_(self._column)

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

class MiroTableView(NSTableView):
    SuperClass = NSTableView
    for name, value in TableViewCommon.__dict__.items():
        locals()[name] = value

class MiroOutlineView(NSOutlineView):
    SuperClass = NSOutlineView
    for name, value in TableViewCommon.__dict__.items():
        locals()[name] = value

class MiroTableHeaderView(NSTableHeaderView):
    def drawRect_(self, rect):
        NSTableHeaderView.drawRect_(self, rect)
        wrapper = wrappermap.wrapper(self.tableView())
        # Manually handle sort column drawing
        for i, column in enumerate(wrapper.columns):
            if column.sort_indicator_visible:
                cell = column._column.headerCell()
                frame = self.headerRectOfColumn_(i)
                cell.highlight_withFrame_inView_(True, frame, self)
                cell.drawSortIndicatorWithFrame_inView_ascending_priority_(
                        frame, self, column.sort_order_ascending, 0)

class MiroTableHeaderCell(NSTableHeaderCell):
    def drawInteriorWithFrame_inView_(self, frame, view):
        # Take into account differences in intercellSpacing() (the default is
        # 3, but that can change using TableView.set_column_spacing())
        extra_space = view.tableView().intercellSpacing().width - 3
        padded_frame = NSMakeRect(frame.origin.x + (extra_space / 2),
                frame.origin.y, frame.size.width - extra_space,
                frame.size.height)
        NSTableHeaderCell.drawInteriorWithFrame_inView_(self, padded_frame, view)

class TableView(Widget):
    """Displays data as a tabular list.  TableView follows the GTK TreeView
    widget fairly closely.
    """

    CREATES_VIEW = False
    # Bit of a hack.  We create several views.  By setting CREATES_VIEW to
    # False, we get to position the views manually.

    def __init__(self, model):
        Widget.__init__(self)
        self.create_signal('selection-changed')
        self.create_signal('hotspot-clicked')
        self.create_signal('row-double-clicked')
        self.model = model
        self.columns = []
        self.context_menu_callback = None
        if self.is_tree():
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
        self.draws_selection = True
        self.row_height_set = False
        self.set_fixed_height(False)
        self.auto_resizing = False
        self.header_view = MiroTableHeaderView.alloc().initWithFrame_(
            NSMakeRect(0, 0, 0, HEADER_HEIGHT))
        self.set_show_headers(True)
        self.notifications = NotificationForwarder.create(self.tableview)
        self.model.connect_weak('row-changed', self.on_row_change)
        self.model.connect_weak('row-added', self.on_row_added)
        self.model.connect_weak('row-will-be-removed', self.on_row_removed)
        self.iters_to_update = []
        self.height_changed = self.selection_removed = self.reload_needed = False

    def send_hotspot_clicked(self):
        tracker = self.tableview.hotspot_tracker
        self.emit('hotspot-clicked', tracker.name, tracker.iter)

    def set_draws_selection(self, draws_selection):
        self.draws_selection = draws_selection

    def get_left_offset(self):
        offset = self.tableview.intercellSpacing().width / 2
        # Yup this can be a non-integer, it seems like that's what OS X does,
        # because either way I round it looks worse than this.
        if self.is_tree():
            offset +=  _disclosure_button_width + EXPANDER_PADDING
        return offset

    def on_row_change(self, model, iter, old_row):
        self.iters_to_update.append(iter)
        if not self.fixed_height:
            old_height = calc_row_height(self.tableview, old_row)
            new_height = calc_row_height(self.tableview, self.model[iter])
            if new_height != old_height:
                self.height_changed = True
        if self.tableview.hotspot_tracker is not None:
            self.tableview.hotspot_tracker.update_hit()

    def on_row_added(self, model, iter):
        self.reload_needed = True
        self.cancel_hotspot_track()

    def on_row_removed(self, model, iter):
        self.reload_needed = True
        if self.tableview.isRowSelected_(self.row_for_iter(iter)):
            self.tableview.deselectAll_(nil)
            self.selection_removed = True
        self.cancel_hotspot_track()

    def cancel_hotspot_track(self):
        if self.tableview.hotspot_tracker is not None:
            self.tableview.hotspot_tracker.redraw_cell()
            self.tableview.hotspot_tracker = None

    def on_expanded(self, notification):
        self.invalidate_size_request()
        item = notification.userInfo()['NSObject']
        self.emit('row-expanded', self.model.iter_for_item[item])

    def on_collapsed(self, notification):
        self.invalidate_size_request()
        item = notification.userInfo()['NSObject']
        self.emit('row-collapsed', self.model.iter_for_item[item])

    def on_selection_change(self, notification):
        self.emit('selection-changed')

    def on_column_resize(self, notification):
        if not self.auto_resizing:
            self.invalidate_size_request()

    def is_tree(self):
        return isinstance(self.model, tablemodel.TreeTableModel)

    def set_row_expanded(self, iter, expanded):
        item = iter.value()
        if expanded:
            self.tableview.expandItem_(item)
        else:
            self.tableview.collapseItem_(item)
        self.invalidate_size_request()

    def is_row_expanded(self, iter):
        return self.tableview.isItemExpanded_(iter.value())

    def calc_size_request(self):
        self.tableview.tile()
        height = self.tableview.frame().size.height
        if self._show_headers:
            height += HEADER_HEIGHT
        return self.calc_width(), height

    def viewport_repositioned(self):
        self._do_layout()
        self.tableview.recalcTrackingRects()

    def viewport_created(self):
        wrappermap.add(self.tableview, self)
        self._do_layout()
        self._add_views()
        if self.is_tree():
            self.notifications.connect(self.on_expanded,
                'NSOutlineViewItemDidExpandNotification')
            self.notifications.connect(self.on_collapsed,
                'NSOutlineViewItemDidCollapseNotification')
            self.notifications.connect(self.on_selection_change,
                    'NSOutlineViewSelectionDidChangeNotification')
            self.notifications.connect(self.on_column_resize,
                    'NSOutlineViewColumnDidResizeNotification')
        else:
            self.notifications.connect(self.on_selection_change,
                    'NSTableViewSelectionDidChangeNotification')
            self.notifications.connect(self.on_column_resize,
                    'NSTableViewColumnDidResizeNotification')
        self.tableview.recalcTrackingRects()

    def remove_viewport(self):
        if self.viewport is not None:
            self._remove_views()
            wrappermap.remove(self.tableview)
            self.notifications.disconnect()
            self.viewport = None

    def viewport_scrolled(self):
        self.tableview.recalcTrackingRects()

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
            self.header_view.setFrame_(NSMakeRect(x, y, width, HEADER_HEIGHT))
            self.tableview.setFrame_(NSMakeRect(x, y + HEADER_HEIGHT, 
                width, height - HEADER_HEIGHT))
        else:
            self.tableview.setFrame_(NSMakeRect(x, y, width, height))

        if self.auto_resize:
            self.auto_resizing = True
            self._autoresize_columns()
            self.auto_resizing = False
        self.queue_redraw()

    def _autoresize_columns(self):
        # Resize the column so that they take up the width we are allocated,
        # but keep in mind the min/max width constraints.
        # The algorithm we use is to add/subtract width evenly between the
        # columns, but not more than their max/min width.  Repeat the process
        # until there is no extra space.
        columns = self.tableview.tableColumns()
        if len(columns) == 1:
            # we can special case this easily
            total_width = self.viewport.area().size.width
            columns[0].setWidth_(total_width)
            return
        column_width = sum(column.width() for column in columns)
        width_difference = self.viewport.area().size.width - column_width
        width_difference -= self.tableview.intercellSpacing().width * len(columns)
        while width_difference != 0:
            did_something = False
            columns_left = len(columns)
            for column in columns:
                old_width = column.width()
                ideal_change = round(width_difference / columns_left)
                ideal_new_width = old_width + ideal_change
                if width_difference < 0:
                    column.setWidth_(max(ideal_new_width, column.minWidth()))
                else:
                    column.setWidth_(min(ideal_new_width, column.maxWidth()))
                if column.width() != old_width:
                    width_difference -= (column.width() - old_width)
                    did_something = True
                columns_left -= 1
            if not did_something:
                # We couldn't change any widths because they were all at their
                # max/min sizes.  Bailout
                break

    def calc_width(self):
        if self.column_count() == 0:
            return 0
        width = 0
        columns = self.tableview.tableColumns()
        if self.auto_resize:
            # Table auto-resizes, we can shrink to min-width for each column
            width = sum(column.minWidth() for column in columns)
        else:
            # Table doesn't auto-resize, the columns can't get smaller than
            # their current width
            width = sum(column.width() for column in columns)
        width += self.tableview.intercellSpacing().width * self.column_count()
        return width

    def start_bulk_change(self):
        # TODO: Implementing this might provide performance benefits
        pass

    def model_changed(self):
        if not self.row_height_set and self.fixed_height:
            self.try_to_set_row_height()
        if self.reload_needed:
            self.tableview.reloadData()
            self.invalidate_size_request()
            if self.selection_removed:
                self.emit('selection-changed')
            self.tableview.recalcTrackingRects()
        elif self.iters_to_update:
            if self.fixed_height or not self.height_changed:
                # our rows don't change height, just update cell areas
                if self.is_tree():
                    for iter in self.iters_to_update:
                        self.tableview.reloadItem_(iter.value())
                else:
                    for iter in self.iters_to_update:
                        row = self.row_for_iter(iter)
                        rect = self.tableview.rectOfRow_(row)
                        self.tableview.setNeedsDisplayInRect_(rect)
            else:
                # our rows can change height inform Cocoa that their heights
                # might have changed (this will redraw them)
                rows_to_change = [ self.row_for_iter(iter) for iter in \
                    self.iters_to_update]
                index_set = NSMutableIndexSet.alloc().init()
                for iter in self.iters_to_update:
                    index_set.addIndex_(self.row_for_iter(iter))
                self.tableview.noteHeightOfRowsWithIndexesChanged_(index_set)
                self.tableview.recalcTrackingRects()
            # FIXME
            # Could get here during shutdown.  Case for example is we
            # got stuck in a contextual menu and quit was called.  For
            # some reason when that happens it thinks the tabs have changed
            # (even during shutdown) and wants to update the tableview.  I
            # think updating it is probably bogus and updating it is an
            # error but let's just try and then continue if it didn't work.
            #
            # I really don't like this try ... except ... block here.
            try:
                self.invalidate_size_request()
            except AttributeError:
                pass
        else:
            return
        self.height_changed = self.selection_removed = self.reload_needed = False
        self.iters_to_update = []

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
        self.columns.append(column)
        self.tableview.addTableColumn_(column._column)
        if self.column_count() == 1 and self.is_tree():
            self.tableview.setOutlineTableColumn_(column._column)
            column.renderer.outline_column = True
        # Adding a column means that each row could have a different height.
        # call noteNumberOfRowsChanged() to have OS X recalculate the heights
        self.tableview.noteNumberOfRowsChanged()
        self.invalidate_size_request()

    def column_count(self):
        return len(self.tableview.tableColumns())

    def remove_column(self, index):
        columns = self.columns.pop(index)
        self.tableview.removeTableColumn_(column._column)
        self.invalidate_size_request()

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

    def allow_multiple_select(self, allow):
        self.tableview.setAllowsMultipleSelection_(allow)

    def get_selection(self):
        selection = self.tableview.selectedRowIndexes()
        return [self.model.iter_for_row(self.tableview, row)  \
                for row in tablemodel.list_from_nsindexset(selection)]

    def get_selected(self):
        if self.tableview.allowsMultipleSelection():
            raise ValueError("Table allows multiple selection")
        row = self.tableview.selectedRow()
        if row == -1:
            return None
        return self.model.iter_for_row(self.tableview, row)

    def num_rows_selected(self):
        return self.tableview.selectedRowIndexes().count()

    def row_for_iter(self, iter):
        if self.is_tree():
            return self.tableview.rowForItem_(iter.value())
        else:
            return self.model.get_index_of_row(iter.value())

    def select(self, iter):
        index_set = NSIndexSet.alloc().initWithIndex_(self.row_for_iter(iter))
        self.tableview.selectRowIndexes_byExtendingSelection_(index_set, YES)

    def unselect(self, iter):
        self.tableview.deselectRow_(self.row_for_iter(iter))

    def unselect_all(self):
        self.tableview.deselectAll_(nil)

    def set_context_menu_callback(self, callback):
        self.context_menu_callback = callback

    # disable the drag when the cells are constantly updating.  Mac OS X
    # deals badly with this..
    def set_volatile(self, volatile):
        if volatile:
            self.data_source.setDragSource_(None)
        else:
            self.data_source.setDragSource_(self.drag_source)

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
