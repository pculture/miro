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

"""tableview.py -- Wrapper for the GTKTreeView widget.  It's used for the tab
list and the item list (AKA almost all of the miro).
"""

import logging

import itertools
import gobject
import gtk

# These are probably wrong, and are placeholders for now, until custom headers
# are also implemented for GTK.
CUSTOM_HEADER_HEIGHT = 25
HEADER_HEIGHT = 25

from miro import signals
from miro import infolist
from miro.errors import WidgetActionError, WidgetDomainError, WidgetRangeError
from miro.frontends.widgets.tableselection import SelectionOwnerMixin
from miro.frontends.widgets.gtk import pygtkhacks
from miro.frontends.widgets.gtk import drawing
from miro.frontends.widgets.gtk import wrappermap
from miro.frontends.widgets.gtk.base import Widget
from miro.frontends.widgets.gtk.simple import Image
from miro.frontends.widgets.gtk.layoutmanager import LayoutManager
from miro.frontends.widgets.gtk.weakconnect import weak_connect
from miro.frontends.widgets.gtk.tableviewcells import (GTKCustomCellRenderer,
     GTKCheckboxCellRenderer, InfoListRenderer, InfoListRendererText)

def rect_contains_rect(outside, inside):
    # currently unused
    return (outside.x <= inside.x and
            outside.y <= inside.y and
            outside.x + outside.width >= inside.x + inside.width and
            outside.y + outside.height >= inside.y + inside.height)

def rect_contains_point(rect, x, y):
    return ((rect.x <= x < rect.x + rect.width) and
            (rect.y <= y < rect.y + rect.height))

class ScrollbarOwnerMixin(object):
    def __init__(self):
        self.scrollbars = []
        self.scroll_positions = [None, None]
        self.scroll_positions_set = False
        self.connect('parent-set', self.on_parent_set)
        self.scroller = None

    def on_parent_set(self, widget, old_parent):
        """We have parent window now; we need to control its scrollbars."""
        self.set_scroller(widget.get_parent())

    def set_scroller(self, window):
        """Take control of the scrollbars of window."""
        if not isinstance(window, gtk.ScrolledWindow):
            return
        self.scroller = window
        scrollbars = tuple(bar.get_adjustment()
            for bar in (window.get_hscrollbar(), window.get_vscrollbar()))
        self.scrollbars = scrollbars
        for i, bar in enumerate(scrollbars):
            weak_connect(bar, 'changed', self.on_scroll_range_changed, i)
        self.set_scroll_position(self.scroll_positions)

    def on_scroll_range_changed(self, adjustment, bar):
        """The scrollbar might have a range now. Set its initial position if
        we haven't already.
        """
        if not self.scroll_positions_set:
            self.set_scroll_position(self.scroll_positions)

    def set_scroll_position(self, scroll_position):
        """Restore the scrollbars to a remembered state."""
        self.scroll_positions = list(scroll_position)
        try:
            for i, scrollbar in enumerate(self.scrollbars):
                self._update_scrollbar_position(i)
        except WidgetActionError, error:
            logging.debug("can't scroll yet: %s", error.reason)
            # try again later
        else:
            self.scroll_positions_set = True

    def get_scroll_position(self):
        """Get the current position of both scrollbars, to restore later."""
        return tuple(int(bar.get_value()) for bar in self.scrollbars)

    def _update_scrollbar_position(self, bar):
        """Move the specified scrollbar to its saved position, if it has one.
        Succeeds or raises WidgetActionError.
        """
        if not self.scroll_positions[bar]:
            # nothing to restore it to yet
            return
        adj = self.scrollbars[bar]
        pos = self.scroll_positions[bar]
        lower = adj.get_lower()
        upper = adj.get_upper() - adj.get_page_size()
        # currently, StandardView gets an upper of 2.0 when it's not ready
        # FIXME: don't count on that
        if upper < 5:
            self.scroll_positions_set = False
            raise WidgetRangeError("scrollable area", pos, lower, upper)
        # have to clip it ourselves
        pos = min(max(pos, lower), upper)
        adj.set_value(pos)

    def scroll_to_path(self, path):
        """Center the view vertically on the given path."""
        if not self.scrollbars:
            return
        vadjustment = self.scrollbars[1]
        rect = self.get_background_area(path, self.get_columns()[0])
        vadjustment.set_value(rect.y + (rect.height - vadjustment.page_size) / 2)

    def scroll_ancestor(self, newly_selected, down):
        # Try to figure out what just became selected.  If multiple things
        # somehow became selected, select the outermost one
        if len(newly_selected) == 0:
            raise WidgetActionError("need at an item to scroll to")
        if down:
            path_to_show = max(newly_selected)
        else:
            path_to_show = min(newly_selected)

        if not self.scrollbars:
            return
        vadjustment = self.scrollbars[1]

        rect = self.get_background_area(path_to_show, self.get_columns()[0])
        _, top = self.translate_coordinates(self.scroller, 0, rect.y)
        top += vadjustment.value
        bottom = top + rect.height
        if down:
            if bottom > vadjustment.value + vadjustment.page_size:
                bottom_value = min(bottom, vadjustment.upper)
                vadjustment.set_value(bottom_value - vadjustment.page_size)
        else:
            if top < vadjustment.value:
                vadjustment.set_value(max(vadjustment.lower, top))

class MiroTreeView(gtk.TreeView, ScrollbarOwnerMixin):
    """Extends the GTK TreeView widget to help implement TableView
    https://develop.participatoryculture.org/index.php/WidgetAPITableView"""
    # Add a tiny bit of padding so that the user can drag feeds below
    # the table, i.e. to the bottom row, as a top-level
    PAD_BOTTOM = 3
    def __init__(self):
        gtk.TreeView.__init__(self)
        ScrollbarOwnerMixin.__init__(self)
        self.drag_dest_at_bottom = False
        self.height_without_pad_bottom = -1
        self.set_enable_search(False)

    def do_size_request(self, req):
        gtk.TreeView.do_size_request(self, req)
        self.height_without_pad_bottom = req.height
        req.height += self.PAD_BOTTOM

    def set_drag_dest_at_bottom(self, value):
        if value != self.drag_dest_at_bottom:
            self.drag_dest_at_bottom = value
            x1, x2, y = self.bottom_drag_dest_coords()
            area = gtk.gdk.Rectangle(x1-1, y-1, x2-x1+2,2)
            self.window.invalidate_rect(area, True)

    def do_move_cursor(self, step, count):
        if step == gtk.MOVEMENT_VISUAL_POSITIONS:
            # GTK is asking us to move left/right.  Since our TableViews don't
            # support this, return False to let the key press propagate.  See
            # #15646 for more info.
            return False
        if isinstance(self.get_parent(), gtk.ScrolledWindow):
            # If our parent is a ScrolledWindow, let GTK take care of this
            handled = gtk.TreeView.do_move_cursor(self, step, count)
            return handled
        else:
            # Otherwise, we have to search up the widget tree for a
            # ScrolledWindow to take care of it
            selection = self.get_selection()
            model, start_selection = selection.get_selected_rows()
            gtk.TreeView.do_move_cursor(self, step, count)

            model, end_selection = selection.get_selected_rows()
            newly_selected = set(end_selection) - set(start_selection)
            down = (count > 0)

            try:
                self.scroll_ancestor(newly_selected, down)
            except WidgetActionError:
                # not possible
                return False
            return True

    def set_drag_dest_row(self, row, position):
        """Works like set_drag_dest_row, except row can be None which will
        cause the treeview to set the drag indicator below the bottom of the
        TreeView.  This is slightly different than below the last row of the
        tree, since the last row might be a child row.
        set_drag_dest_at_bottom() makes the TreeView indicate that the drop
        will be appended as a top-level row.
        """
        if row is not None:
            gtk.TreeView.set_drag_dest_row(self, row, position)
            self.set_drag_dest_at_bottom(False)
        else:
            pygtkhacks.unset_tree_view_drag_dest_row(self)
            self.set_drag_dest_at_bottom(True)

    def unset_drag_dest_row(self):
        pygtkhacks.unset_tree_view_drag_dest_row(self)
        self.set_drag_dest_at_bottom(False)

    def do_expose_event(self, event):
        gtk.TreeView.do_expose_event(self, event)
        if self.drag_dest_at_bottom:
            gc = self.get_style().fg_gc[self.state]
            x1, x2, y = self.bottom_drag_dest_coords()
            event.window.draw_line(gc, x1, y, x2, y)

    def bottom_drag_dest_coords(self):
        visible = self.get_visible_rect()
        x1 = visible.x
        x2 = visible.x + visible.width
        y = visible.height - self.PAD_BOTTOM
        x1, _ = self.tree_to_widget_coords(x1, y)
        x2, y = self.tree_to_widget_coords(x2, y)
        return x1, x2, y

    def last_path(self):
        model = self.get_model()
        if model.iter_n_children(None) == 0:
            return None
        last = model.iter_nth_child(None, model.iter_n_children(None) - 1)
        if last is None:
            return None
        while self.row_expanded(model.get_path(last)):
            last = model.iter_nth_child(last, model.iter_n_children(last) - 1)
        return model.get_path(last)

    def get_left_offset(self):
        offset = self.style_get_property("horizontal-separator") / 2
        if 1 or isinstance(self.get_model(), TreeTableModel):
            offset += self.style_get_property("expander-size")
            offset += 4
            # This seems to be hardcoded in GTK see:
            # http://svn.gnome.org/viewvc/gtk%2B/trunk/gtk/gtktreeview.c
            # (look for "#define EXPANDER_EXTRA_PADDING")
        return offset

gobject.type_register(MiroTreeView)

def gtk_target_list(types):
    count = itertools.count()
    return [(type, gtk.TARGET_SAME_APP, count.next()) for type in types]

class HotspotTracker(object):
    """Handles tracking hotspots.
    https://develop.participatoryculture.org/index.php/WidgetAPITableView"""

    def __init__(self, treeview, event):
        self.treeview = treeview
        self.treeview_wrapper = wrappermap.wrapper(treeview)
        self.hit = False
        self.button = event.button
        path_info = treeview.get_path_at_pos(int(event.x), int(event.y))
        if path_info is None:
            return
        self.path, self.column, background_x, background_y = path_info
        # We always pack 1 renderer for each column
        gtk_renderer = self.column.get_cell_renderers()[0]
        if not isinstance(gtk_renderer, GTKCustomCellRenderer):
            return
        self.renderer = wrappermap.wrapper(gtk_renderer)
        self.attr_map = self.treeview_wrapper.attr_map_for_column[self.column]
        if not rect_contains_point(self.calc_cell_area(), event.x, event.y):
            # Mouse is in the padding around the actual cell area
            return
        self.update_position(event)
        self.iter = treeview.get_model().get_iter(self.path)
        self.name = self.calc_hotspot()
        if self.name is not None:
            self.hit = True

    def is_for_context_menu(self):
        return self.name == "#show-context-menu"

    def calc_cell_area(self):
        cell_area = self.treeview.get_cell_area(self.path, self.column)
        xpad = self.renderer._renderer.props.xpad
        ypad = self.renderer._renderer.props.ypad
        cell_area.x += xpad
        cell_area.y += ypad
        cell_area.width -= xpad * 2
        cell_area.height -= ypad * 2
        return cell_area

    def update_position(self, event):
        self.x, self.y = int(event.x), int(event.y)

    def calc_cell_state(self):
        if self.treeview.get_selection().path_is_selected(self.path):
            if self.treeview.flags() & gtk.HAS_FOCUS:
                return gtk.STATE_SELECTED
            else:
                return gtk.STATE_ACTIVE
        else:
            return gtk.STATE_NORMAL

    def calc_hotspot(self):
        cell_area = self.calc_cell_area()
        if rect_contains_point(cell_area, self.x, self.y):
            model = self.treeview.get_model()
            self.renderer.cell_data_func(self.column, self.renderer._renderer,
                    model, self.iter, self.attr_map)
            style = drawing.DrawingStyle(self.treeview_wrapper,
                use_base_color=True, state=self.calc_cell_state())
            x = self.x - cell_area.x
            y = self.y - cell_area.y
            return self.renderer.hotspot_test(style,
                    self.treeview_wrapper.layout_manager,
                    x, y, cell_area.width, cell_area.height)
        else:
            return None

    def update_hit(self):
        if self.is_for_context_menu():
            return # we always keep hit = True for this one
        old_hit = self.hit
        self.hit = (self.calc_hotspot() == self.name)
        if self.hit != old_hit:
            self.redraw_cell()

    def redraw_cell(self):
        # Check that the treeview is still around.  We might have switched
        # views in response to a hotspot being clicked.
        if self.treeview.flags() & gtk.REALIZED:
            cell_area = self.treeview.get_cell_area(self.path, self.column)
            x, y = self.treeview.tree_to_widget_coords(cell_area.x,
                                                       cell_area.y)
            self.treeview.queue_draw_area(x, y,
                    cell_area.width, cell_area.height)

class TableColumn(signals.SignalEmitter):
    """A single column of a TableView.

    Signals:

        clicked (table_column) -- The header for this column was clicked.
    """
    def __init__(self, title, renderer, header=None, **attrs):
        # header widget not used yet in GTK (#15800)
        signals.SignalEmitter.__init__(self)
        self.create_signal('clicked')
        self._column = gtk.TreeViewColumn(title, renderer._renderer)
        self._column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self._column.set_clickable(True)
        self.attrs = attrs
        renderer.setup_attributes(self._column, attrs)
        self.renderer = renderer
        weak_connect(self._column, 'clicked', self._header_clicked)
        self.do_horizontal_padding = True

    def set_right_aligned(self, right_aligned):
        """Horizontal alignment of the header label."""
        if right_aligned:
            self._column.set_alignment(1.0)
        else:
            self._column.set_alignment(0.0)

    def set_min_width(self, width):
        self._column.props.min_width = width

    def set_max_width(self, width):
        self._column.props.max_width = width

    def set_width(self, width):
        self._column.set_fixed_width(width)

    def get_width(self):
        return self._column.get_width()

    def _header_clicked(self, tablecolumn):
        self.emit('clicked')

    def set_resizable(self, resizable):
        """Set if the user can resize the column."""
        self._column.set_resizable(resizable)

    def set_do_horizontal_padding(self, horizontal_padding):
        self.do_horizontal_padding = False

    def set_sort_indicator_visible(self, visible):
        """Show/Hide the sort indicator for this column."""
        self._column.set_sort_indicator(visible)

    def get_sort_indicator_visible(self):
        return self._column.get_sort_indicator()

    def set_sort_order(self, ascending):
        """Display a sort indicator on the column header.  Ascending can be
        either True or False which affects the direction of the indicator.
        """
        if ascending:
            self._column.set_sort_order(gtk.SORT_ASCENDING)
        else:
            self._column.set_sort_order(gtk.SORT_DESCENDING)

    def get_sort_order_ascending(self):
        """Returns if the sort indicator is displaying that the sort is
        ascending.
        """
        return self._column.get_sort_order() == gtk.SORT_ASCENDING

class GTKSelectionOwnerMixin(SelectionOwnerMixin):
    """GTK-specific methods for selection management.

    This subclass should not define any behavior. Methods that cannot be
    completed in this widget state should raise WidgetActionError.
    """
    def __init__(self):
        SelectionOwnerMixin.__init__(self)
        self.selection = self._widget.get_selection()
        weak_connect(self.selection, 'changed', self.on_selection_changed)

    def _set_allow_multiple_select(self, allow):
        if allow:
            mode = gtk.SELECTION_MULTIPLE
        else:
            mode = gtk.SELECTION_SINGLE
        self.selection.set_mode(mode)

    def _get_allow_multiple_select(self):
        return self.selection.get_mode() == gtk.SELECTION_MULTIPLE

    def _get_selected_iters(self):
        iters = []
        def collect(treemodel, path, iter_):
            iters.append(iter_)
        self.selection.selected_foreach(collect)
        return iters

    def _get_selected_iter(self):
        model, iter_ = self.selection.get_selected()
        return iter_

    @property
    def num_rows_selected(self):
        return self.selection.count_selected_rows()

    def _is_selected(self, iter_):
        return self.selection.iter_is_selected(iter_)

    def _select(self, iter_):
        self.selection.select_iter(iter_)

    def _unselect(self, iter_):
        self.selection.unselect_iter(iter_)

    def _unselect_all(self):
        self.selection.unselect_all()

    def _iter_to_string(self, iter_):
        return self._model.get_string_from_iter(iter_)

    def _iter_from_string(self, string):
        try:
            return self._model.get_iter_from_string(string)
        except ValueError:
            raise WidgetDomainError(
                  "model iters", string, "%s other iters" % len(self.model))

    def select_path(self, path):
        self.selection.select_path(path)

    def _validate_iter(self, iter_):
        if self._model.get_path(iter_) is None:
            raise WidgetDomainError(
                  "model iters", iter_, "%s other iters" % len(self.model))
        real_model = self._widget.get_model()
        if not real_model:
            raise WidgetActionError("no model")
        elif real_model != self._model:
            raise WidgetActionError("wrong model?")

class TableView(Widget, GTKSelectionOwnerMixin):
    """https://develop.participatoryculture.org/index.php/WidgetAPITableView"""

    draws_selection = True

    def __init__(self, model):
        Widget.__init__(self)
        self.set_widget(MiroTreeView())
        GTKSelectionOwnerMixin.__init__(self)
        self.model = model
        self.model.add_to_tableview(self._widget)
        self._model = self._widget.get_model()
        wrappermap.add(self._model, model)
        self._setup_colors()
        self.columns = []
        self.attr_map_for_column = {}
        self.gtk_column_to_wrapper = {}
        self.background_color = None
        self.drag_button_down = False
        self.drag_data = {}
        self._renderer_xpad = self._renderer_ypad = 0
        self.context_menu_callback = self.drag_source = self.drag_dest = None
        self.hotspot_tracker = None
        self.hover_info = None
        self.hover_pos = None
        self.in_bulk_change = False
        self.handled_last_button_press = False
        self.delaying_press = False
        self.set_columns_draggable(False)
        self.layout_manager = LayoutManager(self._widget)
        if hasattr(self, 'get_tooltip'):
            self._widget.set_property('has-tooltip', True)
            self.wrapped_widget_connect('query-tooltip', self.on_tooltip)
            self._last_tooltip_place = None
        self._connect_signals()

    def _connect_signals(self):
        self.create_signal('reallocate-columns') # not emitted on GTK
        self.create_signal('row-expanded')
        self.create_signal('row-collapsed')
        self.create_signal('hotspot-clicked')
        self.create_signal('row-clicked')
        self.create_signal('row-double-clicked')
        self.create_signal('row-activated')
        self.wrapped_widget_connect('row-activated', self.on_row_activated)
        self.wrapped_widget_connect('row-expanded', self.on_row_expanded)
        self.wrapped_widget_connect('row-collapsed', self.on_row_collapsed)
        self.wrapped_widget_connect('button-press-event', self.on_button_press)
        self.wrapped_widget_connect('button-release-event',
            self.on_button_release)
        self.wrapped_widget_connect('motion-notify-event',
            self.on_motion_notify)
        self.wrapped_widget_connect('drag-data-get', self.on_drag_data_get)
        self.wrapped_widget_connect('drag-end', self.on_drag_end)
        self.wrapped_widget_connect('drag-motion', self.on_drag_motion)
        self.wrapped_widget_connect('drag-leave', self.on_drag_leave)
        self.wrapped_widget_connect('drag-drop', self.on_drag_drop)
        self.wrapped_widget_connect('drag-data-received',
                self.on_drag_data_received)
        self.wrapped_widget_connect('unrealize', self.on_unrealize)
        self._connect_hotspot_signals()

    def _connect_hotspot_signals(self):
        self._hotspot_callback_handles = []
        self._hotspot_callback_handles.append(weak_connect(self._model,
            'row-inserted', self.on_row_inserted))
        self._hotspot_callback_handles.append(weak_connect(self._model,
            'row-deleted', self.on_row_deleted))
        self._hotspot_callback_handles.append(weak_connect(self._model,
            'row-changed', self.on_row_changed))

    def _disconnect_hotspot_signals(self):
        for handle in self._hotspot_callback_handles:
            self._model.disconnect(handle)

    def set_gradient_highlight(self, gradient):
        # This is just an OS X thing.
        pass

    def on_tooltip(self, treeview, x, y, keyboard_mode, tooltip):
        # x, y are relative to the entire widget, but we want them to be
        # relative to our bin window.  The bin window doesn't include things
        # like the column headers.
        origin = treeview.window.get_origin()
        bin_origin = treeview.get_bin_window().get_origin()
        x += origin[0] - bin_origin[0]
        y += origin[1] - bin_origin[1]
        path_info = treeview.get_path_at_pos(x, y)
        if path_info is None:
            self._last_tooltip_place = None
            return False
        if (self._last_tooltip_place is not None and
                path_info[:2] != self._last_tooltip_place):
            # the default GTK behavior is to keep the tooltip in the same
            # position, but this is looks bad when we move to a different row.
            # So return False once to stop this.
            self._last_tooltip_place = None
            return False
        self._last_tooltip_place = path_info[:2]
        iter_ = treeview.get_model().get_iter(path_info[0])
        column = self.gtk_column_to_wrapper[path_info[1]]
        text = self.get_tooltip(iter_, column)
        if text is None:
            return False
        pygtkhacks.set_tooltip_text(tooltip, text)
        return True

    def set_background_color(self, color):
        self.background_color = self.make_color(color)
        self.modify_style('base', gtk.STATE_NORMAL, self.background_color)
        if not self.draws_selection:
            self.modify_style('base', gtk.STATE_SELECTED,
                              self.background_color)
            self.modify_style('base', gtk.STATE_ACTIVE, self.background_color)
        if self.use_custom_style:
            for column in self.columns:
                column.renderer._renderer.set_property('cell-background-gdk',
                        self.background_color)

    def handle_custom_style_change(self):
        if self.background_color is not None:
            if self.use_custom_style:
                for column in self.columns:
                    column.renderer._renderer.set_property(
                            'cell-background-gdk', self.background_color)
            else:
                for column in self.columns:
                    column.renderer._renderer.set_property(
                            'cell-background-set', False)

    def set_column_spacing(self, space):
        """Set the amount of space between columns."""
        self._renderer_xpad = space / 2
        for column in self.columns:
            if column.do_horizontal_padding:
                column.renderer._renderer.set_property('xpad',
                                                       self._renderer_xpad)

    def set_row_spacing(self, space):
        """Set the amount of space between columns."""
        self._renderer_ypad = space / 2
        for column in self.columns:
            column.renderer._renderer.set_property('ypad', self._renderer_ypad)

    def set_alternate_row_backgrounds(self, setting):
        self._widget.set_rules_hint(setting)

    def set_grid_lines(self, horizontal, vertical):
        if horizontal and vertical:
            setting = gtk.TREE_VIEW_GRID_LINES_BOTH
        elif horizontal:
            setting = gtk.TREE_VIEW_GRID_LINES_HORIZONTAL
        elif vertical:
            setting = gtk.TREE_VIEW_GRID_LINES_VERTICAL
        else:
            setting = gtk.TREE_VIEW_GRID_LINES_NONE
        self._widget.set_grid_lines(setting)

    def add_column(self, column):
        self.model.check_new_column(column)
        self._widget.append_column(column._column)
        self.columns.append(column)
        self.attr_map_for_column[column._column] = column.attrs
        self.gtk_column_to_wrapper[column._column] = column
        self.setup_new_column(column)

    def remove_column(self, index):
        column = self.columns.pop(index)
        del self.attr_map_for_column[column._column]
        del self.gtk_column_to_wrapper[column._column]
        self._widget.remove_column(column._column)

    def width_for_columns(self, total_width):
        # as far as I can tell, GTK includes the column spacing in the column
        # widths
        scrollbar = 30 # TODO: query the actual width
        return total_width - scrollbar

    def set_auto_resizes(self, setting):
        # FIXME: to be implemented.
        # At this point, GTK somehow does the right thing anyway in terms of
        # auto-resizing.  I'm not sure exactly what's happening, but I believe
        # that if the column widths don't add up to the total width,
        # gtk.TreeView allocates extra width for the last column.  This works
        # well enough for the tab list and item list, since there's only one
        # column.
        pass

    def set_columns_draggable(self, setting):
        self._columns_draggable = setting
        for column in self.columns:
            column._column.set_reorderable(setting)

    def setup_new_column(self, column):
        if self.background_color:
            column.renderer._renderer.set_property('cell-background-gdk',
                    self.background_color)
        column._column.set_reorderable(self._columns_draggable)
        column.renderer._renderer.set_property('xpad', self._renderer_xpad)
        column.renderer._renderer.set_property('ypad', self._renderer_ypad)

    def get_columns(self):
        titles = []
        columns = self._widget.get_columns()
        for column in columns:
            titles.append(column.get_title().decode('utf-8'))
        return titles

    def column_count(self):
        return len(self._widget.get_columns())

    def focus(self):
        self._widget.grab_focus()

    def set_show_headers(self, show):
        self._widget.set_headers_visible(show)
        self._widget.set_headers_clickable(show)

    def _setup_colors(self):
        style = self._widget.style
        if not self.draws_selection:
            # if we don't want to draw selection, make the selected/active
            # colors the same as the normal ones 
            self.modify_style('base', gtk.STATE_SELECTED,
                style.base[gtk.STATE_NORMAL])
            self.modify_style('base', gtk.STATE_ACTIVE,
                style.base[gtk.STATE_NORMAL])

    def set_search_column(self, model_index):
        self._widget.set_search_column(model_index)

    def set_fixed_height(self, fixed_height):
        self._widget.set_fixed_height_mode(fixed_height)

    def set_row_expanded(self, iter_, expanded):
        """Expand or collapse the row specified by iter_. Succeeds or raises
        WidgetActionError. Causes row-expanded or row-collapsed to be emitted
        when successful.
        """
        path = self._model.get_path(iter_)
        if expanded:
            self._widget.expand_row(path, False)
        else:
            self._widget.collapse_row(path)
        if bool(self._widget.row_expanded(path)) != bool(expanded):
            raise WidgetActionError("cannot expand the given item - it "
                    "probably has no children.")

    def is_row_expanded(self, iter_):
        path = self._model.get_path(iter_)
        return self._widget.row_expanded(path)

    def set_context_menu_callback(self, callback):
        self.context_menu_callback = callback

    # GTK is really good and it is safe to operate on table even when
    # cells may be constantly changing in flux.
    def set_volatile(self, volatile):
        return

    def set_drag_source(self, drag_source):
        self.drag_source = drag_source
        # No need to call enable_model_drag_source() here, we handle it
        # ourselves in on_motion_notify()

    def set_drag_dest(self, drag_dest):
        self.drag_dest = drag_dest
        if drag_dest is not None:
            targets = gtk_target_list(drag_dest.allowed_types())
            self._widget.enable_model_drag_dest(targets,
                    drag_dest.allowed_actions())
            self._widget.drag_dest_set(0, targets,
                    drag_dest.allowed_actions())
        else:
            self._widget.unset_rows_drag_dest()
            self._widget.drag_dest_unset()

    def on_row_expanded(self, _widget, iter_, path):
        self.emit('row-expanded', iter_, path)

    def on_row_collapsed(self, _widget, iter_, path):
        self.emit('row-collapsed', iter_, path)

    def on_row_inserted(self, model, path, iter_):
        if self.hotspot_tracker:
            self.hotspot_tracker.redraw_cell()
            self.hotspot_tracker = None

    def on_row_deleted(self, model, path):
        if self.hotspot_tracker:
            self.hotspot_tracker.redraw_cell()
            self.hotspot_tracker = None

    def on_row_changed(self, model, path, iter_):
        if self.hotspot_tracker:
            self.hotspot_tracker.update_hit()

    def on_button_press(self, treeview, event):
        if event.type == gtk.gdk._2BUTTON_PRESS:
            if self.handled_last_button_press:
                return
            path_info = treeview.get_path_at_pos(int(event.x), int(event.y))
            if path_info is not None:
                send_clicked = True
                if (treeview.get_show_expanders() and
                    path_info[1] is treeview.get_expander_column()):
                    if event.x < treeview.style_get_property('expander-size'):
                        send_clicked = False
                if send_clicked:
                    iter_ = treeview.get_model().get_iter(path_info[0])
                    self.emit('row-double-clicked', iter_)
            return

        # Check for single click.  Emit the event but keep on running
        # so we can handle stuff like drag and drop.
        if event.type == gtk.gdk.BUTTON_PRESS:
            path_info = treeview.get_path_at_pos(int(event.x), int(event.y))
            if path_info is not None:
                send_clicked = True
                if (treeview.get_show_expanders() and
                    path_info[1] is treeview.get_expander_column()):
                    if event.x < treeview.style_get_property('expander-size'):
                        send_clicked = False
                if send_clicked:
                    iter_ = treeview.get_model().get_iter(path_info[0])
                    self.emit('row-clicked', iter_)

        if self.hotspot_tracker is None:
            hotspot_tracker = HotspotTracker(treeview, event)
            if hotspot_tracker.hit:
                self.hotspot_tracker = hotspot_tracker
                hotspot_tracker.redraw_cell()
                self.handled_last_button_press = True
                if hotspot_tracker.is_for_context_menu():
                    self._popup_hotspot_context_menu(event)
                # grab keyboard focus since we handled the event
                self.focus()
                return True
        if event.window != treeview.get_bin_window():
            # click is outside the content area, don't try to handle this.
            # In particular, our DnD code messes up resizing table columns.
            self.handled_last_button_press = False
            return
        if event.button == 1 and self.drag_source:
            model, row_paths = treeview.get_selection().get_selected_rows()
            rows = self.model.get_rows(row_paths)
            self.drag_data = rows and self.drag_source.begin_drag(self, rows)
            self.drag_button_down = bool(self.drag_data)
            if not self.drag_button_down:
                self.handled_last_button_press = False
                return

            self.drag_start_x = int(event.x)
            self.drag_start_y = int(event.y)

            # handle multiple selection.  If the current row is already
            # selected and neither the control nor shift key is pressed,
            # stop propagating the signal.  We will only change the selection
            # if the user doesn't start a DnD operation.  This makes it more
            # natural for the user to drag a block of selected items.
            if not (event.state & (gtk.gdk.CONTROL_MASK|gtk.gdk.SHIFT_MASK)):
                path_info = treeview.get_path_at_pos(int(event.x),
                        int(event.y))
                if path_info is not None:
                    path, column, x, y = path_info
                    selection = self._widget.get_selection()
                    renderer = column.get_cell_renderers()[0]
                    click_in_expander = self._x_coord_in_expander(treeview,
                            x, column, path)
                    if (selection.path_is_selected(path) and
                            not click_in_expander and
                            not isinstance(renderer, GTKCheckboxCellRenderer)):
                        self.delaying_press = True
                        # grab keyboard focus since we handled the event
                        self.focus()
                        return True

        elif event.button == 3 and self.context_menu_callback:
            path_info = treeview.get_path_at_pos(int(event.x), int(event.y))
            if path_info is not None:
                path_info = treeview.get_path_at_pos(int(event.x),
                                                     int(event.y))
                if path_info is not None:
                    path, column, x, y = path_info
                    self._popup_context_menu(path, event)
            self.handled_last_button_press = True
            # grab keyboard focus since we handled the event
            self.focus()
            return True
        self.handled_last_button_press = False

    def _popup_context_menu(self, path, event):
        if not self.selection.path_is_selected(path):
            self.unselect_all(signal=False)
            self.select_path(path)
        menu = self.make_context_menu()
        if menu:
            menu.popup(None, None, None, event.button, event.time)
            return menu
        else:
            return None

    def _popup_hotspot_context_menu(self, event):
        menu = self._popup_context_menu(self.hotspot_tracker.path, event)
        if menu:
            menu.connect('selection-done',
                    self._on_hotspot_context_menu_selection_done)

    def _on_hotspot_context_menu_selection_done(self, menu):
        # context menu is closed, we won't get the button-release-event in
        # this case, but we can unset hotspot tracker here.
        if self.hotspot_tracker:
            self.hotspot_tracker.redraw_cell()
            self.hotspot_tracker = None

    def _x_coord_in_expander(self, treeview, x, column, path):
        """Calculate if an x coordinate is over the expander triangle

        :param treeview: Gtk.TreeView
        :param column: Gtk.TreeColumn
        :param x: x coordinate, relative to column's cell area
        :param path: tree path for the cell
        """
        if column != treeview.get_expander_column():
            return False
        model = treeview.get_model()
        if not model.iter_has_child(model.get_iter(path)):
            return False
        expander_size = treeview.style_get_property(
                "expander_size")
        # GTK allocateds an extra 4px to the right of the expanders.  This
        # seems to be hardcoded as EXPANDER_EXTRA_PADDING in the source code.
        total_exander_size = expander_size + 4
        # allocate space for expanders for parent nodes
        expander_start = total_exander_size * (len(path) - 1)
        expander_end = expander_start + total_exander_size
        return expander_start <= x < expander_end

    def on_row_activated(self, treeview, path, view_column):
        iter_ = treeview.get_model().get_iter(path[0])
        self.emit('row-activated', iter_)

    def make_context_menu(self):
        def gen_menu(menu_items):
            menu = gtk.Menu()
            for menu_item_info in menu_items:
                if menu_item_info is None:
                    item = gtk.SeparatorMenuItem()
                else:
                    label, callback = menu_item_info

                    if isinstance(label, tuple) and len(label) == 2:
                        text_label, icon_path = label
                        pixbuf = gtk.gdk.pixbuf_new_from_file(icon_path)
                        image = gtk.Image()
                        image.set_from_pixbuf(pixbuf)
                        item = gtk.ImageMenuItem(text_label)
                        item.set_image(image)
                    else:
                        item = gtk.MenuItem(label)

                    if callback is None:
                        item.set_sensitive(False)
                    elif isinstance(callback, list):
                        item.set_submenu(gen_menu(callback))
                    else:
                        item.connect('activate', self.on_context_menu_activate,
                                     callback)
                menu.append(item)
                item.show()
            return menu

        items = self.context_menu_callback(self)
        if items:
            return gen_menu(items)
        else:
            return None

    def on_context_menu_activate(self, item, callback):
        callback()

    def on_button_release(self, treeview, event):
        hotspot_tracker = self.hotspot_tracker
        if hotspot_tracker and event.button == hotspot_tracker.button:
            hotspot_tracker.update_position(event)
            hotspot_tracker.update_hit()
            if (hotspot_tracker.hit and
                    not hotspot_tracker.is_for_context_menu()):
                self.emit('hotspot-clicked', hotspot_tracker.name,
                        hotspot_tracker.iter)
            hotspot_tracker.redraw_cell()
            self.hotspot_tracker = None
            return True
        if event.button == 1:
            self.drag_button_down = False

            if self.delaying_press:
                # if dragging did not happen, unselect other rows and
                # select current row
                path_info = treeview.get_path_at_pos(int(event.x), int(event.y))
                if path_info is not None:
                    path, column, x, y = path_info
                    self.unselect_all(signal=False)
                    self.select_path(path)
        self.delaying_press = False

    def on_unrealize(self, treeview):
        self.hotspot_tracker = None
        self.drag_button_down = False

    def _redraw_cell(self, treeview, path, column):
        cell_area = treeview.get_cell_area(path, column)
        x, y = treeview.convert_bin_window_to_widget_coords(cell_area.x,
                                                            cell_area.y)
        treeview.queue_draw_area(x, y, cell_area.width, cell_area.height)

    def _update_hover(self, treeview, event):
        old_hover_info, old_hover_pos = self.hover_info, self.hover_pos
        path_info = treeview.get_path_at_pos(int(event.x), int(event.y))
        if (path_info and
                self.gtk_column_to_wrapper[path_info[1]].renderer.want_hover):
            path, column = path_info[:2]
            self.hover_info = path, column
            self.hover_pos = path_info[2:]
        else:
            self.hover_info = None
            self.hover_pos = None
        if (old_hover_info != self.hover_info or
            old_hover_pos != self.hover_pos):
            if (old_hover_info != self.hover_info and
                old_hover_info is not None):
                self._redraw_cell(treeview, *old_hover_info)
            if self.hover_info is not None:
                self._redraw_cell(treeview, *self.hover_info)

    def on_motion_notify(self, treeview, event):
        self._update_hover(treeview, event)

        if self.hotspot_tracker:
            self.hotspot_tracker.update_position(event)
            self.hotspot_tracker.update_hit()
            return True

        if (self.drag_data and self.drag_button_down and
                treeview.drag_check_threshold(self.drag_start_x,
                    self.drag_start_y, int(event.x), int(event.y))):
            self.delaying_press = False
            treeview.drag_begin(gtk_target_list(self.drag_data.keys()),
                    self.drag_source.allowed_actions(), 1, event)

    def on_drag_data_get(self, treeview, context, selection, info, timestamp):
        for typ, data in self.drag_data.items():
            selection.set(typ, 8, repr(data))

    def on_drag_end(self, treeview, context):
        self.drag_data = {}

    def find_type(self, drag_context):
        return self._widget.drag_dest_find_target(drag_context,
            self._widget.drag_dest_get_target_list())

    def calc_positions(self, x, y):
        """Given x and y coordinates, generate a list of drop positions to
        try.  The values are tuples in the form of (parent_path, position,
        gtk_path, gtk_position), where parent_path and position is the
        position to send to the Miro code, and gtk_path and gtk_position is an
        equivalent position to send to the GTK code if the drag_dest validates
        the drop.
        """
        model = self._model
        try:
            gtk_path, gtk_position = self._widget.get_dest_row_at_pos(x, y)
        except TypeError:
            # Below the last row
            yield (None, len(model), None, None)
            return

        iter_ = model.get_iter(gtk_path)
        if gtk_position in (gtk.TREE_VIEW_DROP_INTO_OR_BEFORE,
                gtk.TREE_VIEW_DROP_INTO_OR_AFTER):
            yield (iter_, -1, gtk_path, gtk_position)

        parent_iter = model.iter_parent(iter_)
        position = gtk_path[-1]
        if gtk_position in (gtk.TREE_VIEW_DROP_BEFORE,
                gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
            # gtk gave us a "before" position, no need to change it
            yield (parent_iter, position, gtk_path, gtk.TREE_VIEW_DROP_BEFORE)
        else:
            # gtk gave us an "after" position, translate that to before the
            # next row for miro.
            if (self._widget.row_expanded(gtk_path) and
                    model.iter_has_child(iter_)):
                child_path = gtk_path + (0,)
                yield (iter_, 0, child_path, gtk.TREE_VIEW_DROP_BEFORE)
            else:
                yield (parent_iter, position+1, gtk_path,
                        gtk.TREE_VIEW_DROP_AFTER)

    def on_drag_motion(self, treeview, drag_context, x, y, timestamp):
        if not self.drag_dest:
            return True
        type = self.find_type(drag_context)
        if type == "NONE":
            drag_context.drag_status(0, timestamp)
            return True
        drop_action = 0
        for pos_info in self.calc_positions(x, y):
            drop_action = self.drag_dest.validate_drop(self, self.model, type,
                    drag_context.actions, pos_info[0], pos_info[1])
            if drop_action:
                self.set_drag_dest_row(pos_info[2], pos_info[3])
                break
        else:
            self.unset_drag_dest_row()
        drag_context.drag_status(drop_action, timestamp)
        return True

    def set_drag_dest_row(self, path, position):
        self._widget.set_drag_dest_row(path, position)

    def unset_drag_dest_row(self):
        self._widget.unset_drag_dest_row()

    def on_drag_leave(self, treeview, drag_context, timestamp):
        treeview.unset_drag_dest_row()

    def on_drag_drop(self, treeview, drag_context, x, y, timestamp):
        # prevent the default handler
        treeview.emit_stop_by_name('drag-drop')
        target = self.find_type(drag_context)
        if target == "NONE":
            return False
        treeview.drag_get_data(drag_context, target, timestamp)
        treeview.unset_drag_dest_row()

    def on_drag_data_received(self, treeview, drag_context, x, y, selection,
            info, timestamp):
        # prevent the default handler
        treeview.emit_stop_by_name('drag-data-received')
        if not self.drag_dest:
            return
        type = self.find_type(drag_context)
        if type == "NONE":
            return
        if selection.data is None:
            return
        drop_action = 0
        for pos_info in self.calc_positions(x, y):
            drop_action = self.drag_dest.validate_drop(self, self.model, type,
                    drag_context.actions, pos_info[0], pos_info[1])
            if drop_action:
                self.drag_dest.accept_drop(self, self.model, type,
                        drag_context.actions, pos_info[0], pos_info[1],
                        eval(selection.data))
                return True
        return False

    def start_bulk_change(self):
        self._widget.freeze_child_notify()
        self._widget.set_model(None)
        self._disconnect_hotspot_signals()
        self.in_bulk_change = True

    def model_changed(self):
        if self.in_bulk_change:
            self._widget.set_model(self._model)
            self._widget.thaw_child_notify()
            self._connect_hotspot_signals()
            if self.hotspot_tracker:
                self.hotspot_tracker.redraw_cell()
                self.hotspot_tracker.update_hit()
            self.in_bulk_change = False

    def get_left_offset(self):
        return self._widget.get_left_offset()

    def scroll_to_iter(self, iter_):
        path = self._model.get_path(iter_)
        self._widget.scroll_to_path(path)

    def set_scroll_position(self, scroll_pos):
        self._widget.set_scroll_position(scroll_pos)
    
    def get_scroll_position(self):
        return self._widget.get_scroll_position()

    def set_scroller(self, scroller):
        """Set the Scroller object for this widget, if its ScrolledWindow is
        not a direct ancestor of the object. Standard View needs this.
        """
        self._widget.set_scroller(scroller._widget)

class TableModel(object):
    """https://develop.participatoryculture.org/index.php/WidgetAPITableView"""
    MODEL_CLASS = gtk.ListStore

    def __init__(self, *column_types):
        self._model = self.MODEL_CLASS(*self.map_types(column_types))
        self._column_types = column_types
        if 'image' in self._column_types:
            self.convert_row_for_gtk = self.convert_row_for_gtk_slow
            self.convert_value_for_gtk = self.convert_value_for_gtk_slow
        else:
            self.convert_row_for_gtk = self.convert_row_for_gtk_fast
            self.convert_value_for_gtk = self.convert_value_for_gtk_fast

    def add_to_tableview(self, widget):
        widget.set_model(self._model)

    def map_types(self, miro_column_types):
        type_map = {
                'boolean': bool,
                'numeric': float,
                'integer': int,
                'text': str,
                'image': gtk.gdk.Pixbuf,
                'datetime': object,
                'object': object,
        }
        try:
            return [type_map[type] for type in miro_column_types]
        except KeyError, e:
            raise ValueError("Unknown column type: %s" % e[0])

    # If we store image data, we need to do some work to convert row data to
    # send to GTK
    def convert_value_for_gtk_slow(self, column_value):
        if isinstance(column_value, Image):
            return column_value.pixbuf
        else:
            return column_value

    def convert_row_for_gtk_slow(self, column_values):
        return tuple(self.convert_value_for_gtk(c) for c in column_values)

    def check_new_column(self, column):
        for value in column.attrs.values():
            if not isinstance(value, int):
                msg = "Attribute values must be integers, not %r" % value
                raise TypeError(msg)
            if value < 0 or value >= len(self._column_types):
                raise ValueError("Attribute index out of range: %s" % value)

    # If we don't store image data, we can don't need to do any work to
    # convert row data to gtk
    def convert_value_for_gtk_fast(self, value):
        return value

    def convert_row_for_gtk_fast(self, column_values):
        return column_values

    def append(self, *column_values):
        return self._model.append(self.convert_row_for_gtk(column_values))

    def update_value(self, iter_, index, value):
        self._model.set(iter_, index, self.convert_value_for_gtk(value))

    def update(self, iter_, *column_values):
        self._model[iter_] = self.convert_value_for_gtk(column_values)

    def remove(self, iter_):
        if self._model.remove(iter_):
            return iter_
        else:
            return None

    def insert_before(self, iter_, *column_values):
        row = self.convert_row_for_gtk(column_values)
        return self._model.insert_before(iter_, row)

    def first_iter(self):
        return self._model.get_iter_first()

    def next_iter(self, iter_):
        return self._model.iter_next(iter_)

    def nth_iter(self, index):
        return self._model.iter_nth_child(None, index)

    def __iter__(self):
        return iter(self._model)

    def __len__(self):
        return len(self._model)

    def __getitem__(self, iter_):
        return self._model[iter_]

    def get_rows(self, row_paths):
        return [self._model[path] for path in row_paths]

    def get_path(self, iter_):
        return self._model.get_path(iter_)

class TreeTableModel(TableModel):
    """https://develop.participatoryculture.org/index.php/WidgetAPITableView"""
    MODEL_CLASS = gtk.TreeStore

    def append(self, *column_values):
        return self._model.append(None, self.convert_row_for_gtk(
            column_values))

    def insert_before(self, iter_, *column_values):
        parent = self._model.iter_parent(iter_)
        row = self.convert_row_for_gtk(column_values)
        return self._model.insert_before(parent, iter_, row)

    def append_child(self, iter_, *column_values):
        return self._model.append(iter_, self.convert_row_for_gtk(
            column_values))

    def child_iter(self, iter_):
        return self._model.iter_children(iter_)

    def nth_child_iter(self, iter_, index):
        return self._model.iter_nth_child(iter_, index)

    def has_child(self, iter_):
        return self._model.iter_has_child(iter_)

    def children_count(self, iter_):
        return self._model.iter_n_children(iter_)

    def parent_iter(self, iter_):
        return self._model.iter_parent(iter_)

class InfoListModel(infolist.InfoList):
    # InfoList is a special model for quick handling of ItemInfo lists
    # we we wrap it slightly so that it matches some of the TableModel
    # interface
    def check_new_column(self, column):
        if not (isinstance(column.renderer, InfoListRenderer) or
                isinstance(column.renderer, InfoListRendererText)):
            raise TypeError("InfoListModel only supports InfoListRenderer "
                    "or InfoListRendererText")

    def get_rows(self, row_paths):
        return [self.nth_row(path[0]) for path in row_paths]
