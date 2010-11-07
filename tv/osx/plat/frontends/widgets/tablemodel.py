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

"""tablemodel.py -- Model classes for TableView.  """

import itertools

from AppKit import NSDragOperationNone, NSTableViewDropOn, protocols
from Foundation import NSObject, NSNotFound
from objc import YES, NO, nil

from miro import fasttypes
from miro import signals
from miro.plat.frontends.widgets import wrappermap
from miro.plat.frontends.widgets.simple import Image

def list_from_nsindexset(index_set):
    rows = list()
    index = index_set.firstIndex()
    while (index != NSNotFound):
        rows.append(index)
        index = index_set.indexGreaterThanIndex_(index)
    return rows

class RowList(object):
    """RowList is a Linked list that has some optimizations for looking up
    rows by index number.
    """
    def __init__(self):
        self.list = fasttypes.LinkedList()
        self.iter_cache = []

    def firstIter(self):
        return self.list.firstIter()

    def lastIter(self):
        return self.list.lastIter()

    def insertBefore(self, iter, value):
        self.iter_cache = []
        if iter is None:
            return self.list.append(value)
        else:
            return self.list.insertBefore(iter, value)
        
    def append(self, value):
        return self.list.append(value)

    def __len__(self):
        return len(self.list)

    def __getitem__(self, iter):
        return self.list[iter]

    def __iter__(self):
        iter = self.firstIter()
        while iter != self.lastIter():
            yield iter.value()
            iter.forward()

    def remove(self, iter):
        self.iter_cache = []
        return self.list.remove(iter)

    def nth_iter(self, index):
        if index < 0:
            raise IndexError()
        elif index >= len(self):
            return None
        if len(self.iter_cache) == 0:
            self.iter_cache.append(self.firstIter())
        try:
            return self.iter_cache[index].copy()
        except IndexError:
            pass
        iter = self.iter_cache[-1].copy()
        index -= len(self.iter_cache) - 1
        for x in xrange(index):
            iter.forward()
            self.iter_cache.append(iter.copy())
        return iter

class TableModelBase(signals.SignalEmitter):
    """Base class for TableModel and TreeTableModel."""
    def __init__(self, *column_types):
        signals.SignalEmitter.__init__(self)
        self.row_list = RowList()
        self.column_types = column_types
        self.create_signal('row-changed')
        self.create_signal('row-added')
        self.create_signal('row-will-be-removed')

    def check_column_values(self, column_values):
        if len(self.column_types) != len(column_values):
            raise ValueError("Wrong number of columns")
        # We might want to do more typechecking here

    def update_value(self, iter, index, value):
        old_row = list(iter.value().values)
        iter.value().values[index] = value
        self.emit('row-changed', iter, old_row)

    def update(self, iter, *column_values):
        old_row = list(iter.value().values)
        iter.value().update_values(column_values)
        self.emit('row-changed', iter, old_row)

    def remove(self, iter):
        row_list = self.containing_list(iter)
        self.emit('row-will-be-removed', iter)
        rv = row_list.remove(iter)
        if rv == row_list.lastIter():
            rv = None
        return rv

    def nth_iter(self, index):
        return self.row_list.nth_iter(index)

    def next_iter(self, iter):
        row_list = self.containing_list(iter)
        retval = iter.copy()
        retval.forward()
        if retval == row_list.lastIter():
            return None
        else:
            return retval

    def first_iter(self):
        if len(self.row_list) > 0:
            return self.row_list.firstIter()
        else:
            return None

    def __len__(self):
        return len(self.row_list)

    def __getitem__(self, iter):
        return iter.value()

    def __iter__(self):
        return iter(self.row_list)

class TableRow(object):
    """See https://develop.participatoryculture.org/index.php/WidgetAPITableView for a description of the API for this class."""
    def __init__(self, column_values):
        self.update_values(column_values)

    def update_values(self, column_values):
        self.values = list(column_values)

    def __getitem__(self, index):
        return self.values[index]

    def __len__(self):
        return len(self.values)

    def __iter__(self):
        return iter(self.values)

class TableModel(TableModelBase):
    """See https://develop.participatoryculture.org/index.php/WidgetAPITableView for a description of the API for this class."""
    def __init__(self, *column_types):
        TableModelBase.__init__(self, column_types)
        self.row_indexes = {}

    def remember_row_at_index(self, row, index):
        if row not in self.row_indexes:
            self.row_indexes[row] = index

    def get_index_of_row(self, row):
        try:
            return self.row_indexes[row]
        except KeyError:
            iter = self.row_list.firstIter()
            index = 0
            while iter != self.row_list.lastIter():
                current_row = iter.value()
                self.row_indexes[current_row] = index
                if current_row is row:
                    return index
                index += 1
                iter.forward()
            raise LookupError("%s is not in this table" % row)

    def containing_list(self, iter):
        return self.row_list

    def append(self, *column_values):
        self.row_indexes = {}
        retval = self.row_list.append(TableRow(column_values))
        self.emit('row-added', retval)
        return retval

    def remove(self, iter):
        self.row_indexes = {}
        return TableModelBase.remove(self, iter)

    def insert_before(self, iter, *column_values):
        self.row_indexes = {}
        row = TableRow(column_values)
        retval = self.row_list.insertBefore(iter, row)
        self.emit('row-added', retval)
        return retval

    def iter_for_row(self, tableview, row):
        return self.row_list.nth_iter(row)

class TreeNode(NSObject, TableRow):
    """A row in a TreeTableModel"""

    # Implementation note: these need to be NSObjects because we return them 
    # to the NSOutlineView.

    def initWithValues_parent_(self, column_values, parent):
        self.children = RowList()
        self.update_values(column_values)
        self.parent = parent
        return self

    @staticmethod
    def create_(values, parent):
        return TreeNode.alloc().initWithValues_parent_(values, parent)

    def iterchildren(self):
        return iter(self.children)

class TreeTableModel(TableModelBase):
    """https://develop.participatoryculture.org/index.php/WidgetAPITableView"""
    def __init__(self, *column_values):
        TableModelBase.__init__(self, *column_values)
        self.iter_for_item = {}

    def containing_list(self, iter):
        return self.row_list_for_iter(iter.value().parent)

    def row_list_for_iter(self, iter):
        if iter is None:
            return self.row_list
        else:
            return iter.value().children

    def remember_iter(self, iter):
        self.iter_for_item[iter.value()] = iter
        return iter

    def append(self, *column_values):
        retval = self.row_list.append(TreeNode.create_(column_values, None))
        self.emit('row-added', retval)
        return self.remember_iter(retval)

    def forget_iter_for_item(self, item):
        del self.iter_for_item[item]
        for child in item.children:
            self.forget_iter_for_item(child)

    def remove(self, iter):
        self.forget_iter_for_item(iter.value())
        return TableModelBase.remove(self, iter)

    def insert_before(self, iter, *column_values):
        row = TreeNode.create_(column_values, self.parent_iter(iter))
        retval = self.containing_list(iter).insertBefore(iter, row)
        self.emit('row-added', retval)
        return self.remember_iter(retval)

    def append_child(self, iter, *column_values):
        row_list = self.row_list_for_iter(iter)
        retval = row_list.append(TreeNode.create_(column_values, iter))
        self.emit('row-added', retval)
        return self.remember_iter(retval)

    def child_iter(self, iter):
        row_list = iter.value().children
        if len(row_list) == 0:
            return None
        else:
            return row_list.firstIter()

    def nth_child_iter(self, iter, index):
        row_list = self.row_list_for_iter(iter)
        return row_list.nth_iter(index)

    def has_child(self, iter):
        return  len(iter.value().children) > 0

    def children_count(self, iter):
        if iter is not None:
            return len(iter.value().children)
        else:
            return len(self.row_list)

    def children_iters(self, iter):
        return self.iters_in_rowlist(self.row_list_for_iter(iter))

    def parent_iter(self, iter):
        return iter.value().parent

    def iter_for_row(self, tableview, row):
        return self.iter_for_item[tableview.itemAtRow_(row)]

def get_column_data(row, column):
    attr_map = column.identifier()
    return dict((name, row[index]) for name, index in attr_map.items())

class DataSourceBase(NSObject):
    def initWithModel_(self, model):
        self.model = model
        self.drag_source = None
        self.drag_dest = None

    def setDragSource_(self, drag_source):
        self.drag_source = drag_source

    def setDragDest_(self, drag_dest):
        self.drag_dest = drag_dest

    def view_writeColumnData_ToPasteboard_(self, view, data, pasteboard):
        if not self.drag_source:
            return NO
        wrapper = wrappermap.wrapper(view)
        drag_data = self.drag_source.begin_drag(wrapper, data)
        if not drag_data:
            return NO
        pasteboard.declareTypes_owner_(drag_data.keys(), self)
        for typ, value in drag_data.items():
            pasteboard.setString_forType_(value, typ)
        return YES

    def calcType_(self, drag_info):
        source_actions = drag_info.draggingSourceOperationMask()
        if not (self.drag_dest and
                (self.drag_dest.allowed_actions() | source_actions)):
            return None
        types = self.drag_dest.allowed_types()
        return drag_info.draggingPasteboard().availableTypeFromArray_(types)

    def validateDrop_dragInfo_parentIter_position_(self, view, drag_info, 
            parent, position):
        typ = self.calcType_(drag_info)
        if typ:
            wrapper = wrappermap.wrapper(view)
            return self.drag_dest.validate_drop(wrapper, self.model, typ,
                    drag_info.draggingSourceOperationMask(), parent,
                    position)
        else:
            return NSDragOperationNone

    def acceptDrop_dragInfo_parentIter_position_(self, view, drag_info,
            parent, position):
        typ = self.calcType_(drag_info)
        if typ:
            data = drag_info.draggingPasteboard().stringForType_(typ)
            wrapper = wrappermap.wrapper(view)
            return self.drag_dest.accept_drop(wrapper, self.model, typ, 
                    drag_info.draggingSourceOperationMask(), parent,
                    position, data)
        else:
            return NO

class MiroTableViewDataSource(DataSourceBase, protocols.NSTableDataSource):
    def numberOfRowsInTableView_(self, table_view):
        return len(self.model)

    def tableView_objectValueForTableColumn_row_(self, table_view, column, row):
        node = self.model.nth_iter(row).value()
        self.model.remember_row_at_index(node, row)
        return get_column_data(node.values, column)

    def tableView_writeRowsWithIndexes_toPasteboard_(self, tableview, rowIndexes,
            pasteboard):
        indexes = list_from_nsindexset(rowIndexes)
        data = [self.model[self.model.nth_iter(i)] for i in indexes]
        return self.view_writeColumnData_ToPasteboard_(tableview, data, 
                pasteboard)

    def translateRow_operation_(self, row, operation):
        if operation == NSTableViewDropOn:
            return (self.model.nth_iter(row),), -1
        else:
            return None, row

    def tableView_validateDrop_proposedRow_proposedDropOperation_(self,
            tableview, drag_info, row, operation):
        parent, position  = self.translateRow_operation_(row, operation)
        return self.validateDrop_dragInfo_parentIter_position_(tableview,
                drag_info, parent, position)

    def tableView_acceptDrop_row_dropOperation_(self,
            tableview, drag_info, row, operation):
        parent, position = self.translateRow_operation_(row, operation)
        return self.acceptDrop_dragInfo_parentIter_position_(tableview, 
                drag_info, parent, position)

class MiroOutlineViewDataSource(DataSourceBase, protocols.NSOutlineViewDataSource):
    def outlineView_child_ofItem_(self, view, child, item):
        if item is nil:
            row_list = self.model.row_list
        else:
            row_list = item.children
        return row_list.nth_iter(child).value()

    def outlineView_isItemExpandable_(self, view, item):
        if item is not nil and hasattr(item, 'children'):
            return len(item.children) > 0
        else:
            return len(self.model) > 0

    def outlineView_numberOfChildrenOfItem_(self, view, item):
        if item is not nil and hasattr(item, 'children'):
            return len(item.children)
        else:
            return len(self.model)

    def outlineView_objectValueForTableColumn_byItem_(self, view, column,
            item):
        return get_column_data(item.values, column)

    def outlineView_writeItems_toPasteboard_(self, outline_view, items, 
            pasteboard):
        data = [i.values for i in items]
        return self.view_writeColumnData_ToPasteboard_(outline_view, data, 
                pasteboard)

    def outlineView_validateDrop_proposedItem_proposedChildIndex_(self,
            outlineview, drag_info, item, child_index):
        if item is None:
            iter = None
        else:
            iter = self.model.iter_for_item[item]
        return self.validateDrop_dragInfo_parentIter_position_( outlineview,
                drag_info, iter, child_index)

    def outlineView_acceptDrop_item_childIndex_(self, outlineview, drag_info,
            item, child_index):
        if item is None:
            iter = None
        else:
            iter = self.model.iter_for_item[item]
        return self.acceptDrop_dragInfo_parentIter_position_(outlineview, 
                drag_info, iter, child_index)
