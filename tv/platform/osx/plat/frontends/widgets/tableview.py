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

"""miro.plat.frontends.widgets.tableview -- TableView widget and it's
associated classes.
"""

from AppKit import *
from Foundation import *
from objc import YES, NO, nil

from miro.plat.frontends.widgets import osxmenus
from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets import tablemodel
from miro.plat.frontends.widgets.base import Widget
from miro.plat.frontends.widgets.drawing import DrawingContext, DrawingStyle
from miro.plat.frontends.widgets.helpers import NotificationForwarder
from miro.plat.frontends.widgets.layoutmanager import LayoutManager

def get_all_indexes(tableview, index_set):
    rows = list()
    index = index_set.firstIndex()
    while (index != NSNotFound):
        rows.append(index)
        index = index_set.indexGreaterThanIndex_(index)
    return rows

# Disclosure button used as a reference in get_left_offset()
_disclosure_button = NSButton.alloc().init()
_disclosure_button.setButtonType_(NSOnOffButton)
_disclosure_button.setBezelStyle_(NSDisclosureBezelStyle)
_disclosure_button.sizeToFit()
_disclosure_button_width = _disclosure_button.frame().size.width 

EXPANDER_PADDING = 6

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
        self.name = self.calc_hotspot()
        self.hit = (self.name is not None)

    def calc_cell_hotspot(self, column, row):
        if (self.hit and self.column == column.identifier() 
                and self.row == row):
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

class MiroTableCell(NSCell):
    def calcHeight_(self, view):
        font = self.font()
        return font.ascender() + abs(font.descender) + font.leading

    def highlightColorWithFrame_inView_(self, frame, view):
        if wrappermap.wrapper(view).draws_selection:
            return NSCell.highlightColorWithFrame_inView_(self, frame, view)
        else:
            return nil

    def setObjectValue_(self, value_dict):
        NSCell.setObjectValue_(self, value_dict['value'])

class MiroTableImageCell(NSImageCell):
    def calcHeight_(self, view):
        return self.value_dict['image'].size().height

    def highlightColorWithFrame_inView_(self, frame, view):
        if wrappermap.wrapper(view).draws_selection:
            return NSCell.highlightColorWithFrame_inView_(self, frame, view)
        else:
            return nil

    def setObjectValue_(self, value_dict):
        NSImageCell.setObjectValue_(self, value_dict['image'])

class CellRenderer(object):
    def setDataCell_(self, column):
        column.setDataCell_(MiroTableCell.alloc().init())

class ImageCellRenderer(object):
    def setDataCell_(self, column):
        column.setDataCell_(MiroTableImageCell.alloc().init())

class CustomTableCell(NSCell):
    def init(self):
        self = NSCell.init(self)
        self.layout_manager = LayoutManager()
        self.hotspot = None
        return self

    def highlightColorWithFrame_inView_(self, frame, view):
        if wrappermap.wrapper(view).draws_selection:
            return NSCell.highlightColorWithFrame_inView_(self, frame, view)
        else:
            return nil

    def calcHeight_(self, view):
        self.layout_manager.reset()
        style = self.make_drawing_style(None, view)
        self.set_wrapper_data()
        cell_size = self.wrapper.get_size(style, self.layout_manager)
        return cell_size[1]

    def make_drawing_style(self, frame, view):
        if self.isHighlighted() and frame is not None:
            highlight = NSCell.highlightColorWithFrame_inView_(self, frame, view)
            text_color = None
            table_view = self.wrapper.column.tableView()
            if table_view.isDescendantOf_(table_view.window().firstResponder()):
                text_color = NSColor.whiteColor()
            return DrawingStyle(highlight, text_color)
        else:
            return DrawingStyle()

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
                self.hotspot)
        NSGraphicsContext.currentContext().restoreGraphicsState()

    def setObjectValue_(self, value_dict):
        self.value_dict = value_dict

    def set_wrapper_data(self):
        for name, value in self.value_dict.items():
            setattr(self.wrapper, name, value)

class CustomCellRenderer(object):
    def __init__(self):
        self.outline_column = False
        self.column = None

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
        self.column = column

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
    return row_height

class TableViewDelegate(NSObject):
    def tableView_willDisplayCell_forTableColumn_row_(self, view, cell,
            column, row):
        if view.hotspot_tracker:
            cell.hotspot = view.hotspot_tracker.calc_cell_hotspot(column, row)
        else:
            cell.hotspot = None

class VariableHeightTableViewDelegate(TableViewDelegate):
    def tableView_heightOfRow_(self, table_view, row):
        iter = table_view.dataSource().model.iter_for_row(table_view, row)
        return calc_row_height(table_view, iter.value().values)

class OutlineViewDelegate(NSObject):
    def outlineView_willDisplayCell_forTableColumn_item_(self, view, cell,
            column, item):
        if view.hotspot_tracker:
            row = view.rowForItem_(item)
            cell.hotspot = view.hotspot_tracker.calc_cell_hotspot(column, row)
        else:
            cell.hotspot = None

class VariableHeightOutlineViewDelegate(OutlineViewDelegate):
    def outlineView_heightOfRowByItem_(self, outline_view, item):
        return calc_row_height(outline_view, item.values)

# TableViewCommon is a hack to do a Mixin class.  We want the same behaviour
# for our table views and our outline views.  Normally we would use a Mixin,
# but that doesn't work with pyobjc.  Instead we define the common code in
# TableViewCommon, then copy it into MiroTableView and MiroOutlineView

class TableViewCommon(object):
    def init(self):
        self = self.SuperClass.init(self)
        self.hotspot_tracker = None
        return self

    def highlightSelectionInClipRect_(self, rect):
        if wrappermap.wrapper(self).draws_selection:
            self.SuperClass.highlightSelectionInClipRect_(self, rect)

    def draggingSourceOperationMaskForLocal_(self, local):
        drag_source = wrappermap.wrapper(self).drag_source
        if drag_source and local:
            return drag_source.allowed_actions()
        return NSDragOperationNone

    def mouseDown_(self, event):
        if event.modifierFlags() & NSControlKeyMask:
            self.handleContextMenu_(event)
            return
        point = self.convertPoint_fromView_(event.locationInWindow(), nil)
        hotspot_tracker = HotspotTracker(self, point)
        if hotspot_tracker.hit:
            self.hotspot_tracker = hotspot_tracker
            self.hotspot_tracker.redraw_cell()
        else:
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

class MiroTableView(NSTableView):
    SuperClass = NSTableView
    for name, value in TableViewCommon.__dict__.items():
        locals()[name] = value

class MiroOutlineView(NSOutlineView):
    SuperClass = NSOutlineView
    for name, value in TableViewCommon.__dict__.items():
        locals()[name] = value

class TableView(Widget):
    """Displays data as a tabular list.  TableView follows the GTK TreeView
    widget fairly closely.
    """

    def __init__(self, model):
        Widget.__init__(self)
        self.create_signal('selection-changed')
        self.create_signal('hotspot-clicked')
        self.model = model
        self.context_menu_callback = None
        if self.is_tree():
            self.create_signal('row-expanded')
            self.create_signal('row-collapsed')
            self.view = MiroOutlineView.alloc().init()
            self.data_source = tablemodel.MiroOutlineViewDataSource.alloc()
        else:
            self.view = MiroTableView.alloc().init()
            self.data_source = tablemodel.MiroTableViewDataSource.alloc()
        self.data_source.initWithModel_(self.model)
        self.view.setDataSource_(self.data_source)
        self.view.setVerticalMotionCanBeginDrag_(YES)
        self.draws_selection = True
        self.row_height_set = False
        self.set_fixed_height(False)
        self.header_view = self.view.headerView()
        self.notifications = NotificationForwarder.create(self.view)
        if self.is_tree():
            self.notifications.connect(self.on_expanded,
                'NSOutlineViewItemDidExpandNotification')
            self.notifications.connect(self.on_collapsed,
                'NSOutlineViewItemDidCollapseNotification')
            self.notifications.connect(self.on_selection_change,
                    'NSOutlineViewSelectionDidChangeNotification')
        else:
            self.notifications.connect(self.on_selection_change,
                    'NSTableViewSelectionDidChangeNotification')
        self.model.connect_weak('row-changed', self.on_row_change)
        self.model.connect_weak('row-added', self.on_row_added)
        self.model.connect_weak('row-will-be-removed', self.on_row_removed)
        self.iters_to_update = []
        self.height_changed = self.selection_removed = self.reload_needed = False

    def send_hotspot_clicked(self):
        tracker = self.view.hotspot_tracker
        self.emit('hotspot-clicked', tracker.name, tracker.iter)

    def set_draws_selection(self, draws_selection):
        self.draws_selection = draws_selection

    def get_left_offset(self):
        offset = self.view.intercellSpacing().width / 2
        # Yup this can be a non-integer, it seems like that's what OS X does,
        # because either way I round it looks worse than this.
        if self.is_tree():
            offset +=  _disclosure_button_width + EXPANDER_PADDING
        return offset

    def on_row_change(self, model, iter, old_row):
        self.iters_to_update.append(iter)
        if not self.fixed_height:
            old_height = calc_row_height(self.view, old_row)
            new_height = calc_row_height(self.view, self.model[iter])
            if new_height != old_height:
                self.height_changed = True
        if self.view.hotspot_tracker is not None:
            self.view.hotspot_tracker.update_hit()

    def on_row_added(self, model, iter):
        self.reload_needed = True
        self.cancel_hotspot_track()

    def on_row_removed(self, model, iter):
        self.reload_needed = True
        if self.view.isRowSelected_(self.row_for_iter(iter)):
            self.selection_removed = True
        self.cancel_hotspot_track()

    def cancel_hotspot_track(self):
        if self.view.hotspot_tracker is not None:
            self.view.hotspot_tracker.redraw_cell()
            self.view.hotspot_tracker = None

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

    def is_tree(self):
        return isinstance(self.model, tablemodel.TreeTableModel)

    def set_row_expanded(self, iter, expanded):
        item = iter.value()
        if expanded:
            self.view.expandItem_(item)
        else:
            self.view.collapseItem_(item)
        self.invalidate_size_request()

    def is_row_expanded(self, iter):
        return self.view.isItemExpanded_(iter.value())

    def calc_size_request(self):
        self.view.tile()
        return self.calc_width(), self.view.frame().size.height

    def viewport_repositioned(self):
        self.view.sizeToFit()

    def calc_width(self):
        if self.column_count() == 0:
            return 0
        width = 0
        for column in self.view.tableColumns():
            width += column.minWidth()
        width += self.view.intercellSpacing().width * (self.column_count()-1)
        return width

    def model_changed(self):
        if not self.row_height_set and self.fixed_height:
            self.try_to_set_row_height()
        if self.reload_needed:
            self.view.reloadData()
            self.invalidate_size_request()
            if self.selection_removed:
                self.emit('selection-changed')
        elif self.iters_to_update:
            if self.fixed_height or not self.height_changed:
                # our rows don't change height, just update cell areas
                if self.is_tree():
                    for iter in self.iters_to_update:
                        self.view.reloadItem_(iter.value())
                else:
                    for iter in self.iters_to_update:
                        row = self.row_for_iter(iter)
                        rect = self.view.rectOfRow_(row)
                        self.view.setNeedsDisplayInRect_(rect)
            else:
                # our rows can change height inform Cocoa that their heights
                # might have changed (this will redraw them)
                rows_to_change = [ self.row_for_iter(iter) for iter in \
                    self.iters_to_update]
                index_set = NSMutableIndexSet.alloc().init()
                for iter in self.iters_to_update:
                    index_set.addIndex_(self.row_for_iter(iter))
                self.view.noteHeightOfRowsWithIndexesChanged_(index_set)
        else:
            return
        self.height_changed = self.selection_removed = self.reload_needed = False
        self.iters_to_update = []

    def add_column(self, title, renderer, min_width, **attrs):
        column = NSTableColumn.alloc().initWithIdentifier_(attrs)
        column.headerCell().setStringValue_(title)
        column.setEditable_(NO)
        column.setMinWidth_(min_width)
        renderer.setDataCell_(column)
        self.view.addTableColumn_(column)
        if self.column_count() == 1 and self.is_tree():
            self.view.setOutlineTableColumn_(column)
            renderer.outline_column = True
        self.invalidate_size_request()

    def column_count(self):
        return len(self.view.tableColumns())

    def remove_column(self, index):
        column = self.view.tableColumns()[index]
        self.view.removeTableColumn_(column)
        self.invalidate_size_request()

    def set_background_color(self, (red, green, blue)):
        color = NSColor.colorWithDeviceRed_green_blue_alpha_(red, green, blue,
                1.0)
        self.view.setBackgroundColor_(color)

    def set_show_headers(self, show):
        if show:
            self.view.setHeaderView_(self.header_view)
        else:
            self.view.setHeaderView_(nil)

    def set_search_column(self, model_index):
        pass

    def try_to_set_row_height(self):
        if len(self.model) > 0:
            first_iter = self.model.first_iter()
            height = calc_row_height(self.view, self.model[first_iter])
            self.view.setRowHeight_(height)
            self.row_height_set = True

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
        self.view.setDelegate_(self.delegate)
        self.view.reloadData()

    def allow_multiple_select(self, allow):
        self.view.setAllowsMultipleSelection_(allow)

    def get_selection(self):
        selection = self.view.selectedRowIndexes()
        return [self.model.iter_for_row(self.view, row)  \
                for row in get_all_indexes(self.view, selection)]

    def get_selected(self):
        if self.view.allowsMultipleSelection():
            raise ValueError("Table allows multiple selection")
        row = self.view.selectedRow()
        if row == -1:
            return None
        return self.model.iter_for_row(self.view, row)

    def num_rows_selected(self):
        return self.view.selectedRowIndexes().count()

    def row_for_iter(self, iter):
        if self.is_tree():
            return self.view.rowForItem_(iter.value())
        else:
            return self.model.get_index_of_row(iter.value())

    def select(self, iter):
        index_set = NSIndexSet.alloc().initWithIndex_(self.row_for_iter(iter))
        self.view.selectRowIndexes_byExtendingSelection_(index_set, YES)

    def unselect(self, iter):
        self.view.deselectRow_(self.row_for_iter(iter))

    def unselect_all(self):
        self.view.deselectAll_(nil)

    def set_context_menu_callback(self, callback):
        self.context_menu_callback = callback

    def set_drag_source(self, drag_source):
        self.drag_source = drag_source
        if drag_source is None:
            self.data_source.setDragSource_(None)
        else:
            self.data_source.setDragSource_(drag_source)

    def set_drag_dest(self, drag_dest):
        self.drag_dest = drag_dest
        if drag_dest is None:
            self.view.unregisterDraggedTypes()
            self.data_source.setDragDest_(None)
        else:
            types = drag_dest.allowed_types()
            self.view.registerForDraggedTypes_(types)
            self.data_source.setDragDest_(drag_dest)
