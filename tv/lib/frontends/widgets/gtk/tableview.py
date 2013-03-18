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
from collections import namedtuple

# These are probably wrong, and are placeholders for now, until custom headers
# are also implemented for GTK.
CUSTOM_HEADER_HEIGHT = 25
HEADER_HEIGHT = 25

from miro import signals
from miro.errors import (WidgetActionError, WidgetDomainError, WidgetRangeError,
        WidgetNotReadyError)
from miro.frontends.widgets.tableselection import SelectionOwnerMixin
from miro.frontends.widgets.tablescroll import ScrollbarOwnerMixin
from miro.frontends.widgets.gtk import pygtkhacks
from miro.frontends.widgets.gtk import drawing
from miro.frontends.widgets.gtk import fixedliststore
from miro.frontends.widgets.gtk import wrappermap
from miro.frontends.widgets.gtk.base import Widget
from miro.frontends.widgets.gtk.simple import Image
from miro.frontends.widgets.gtk.layoutmanager import LayoutManager
from miro.frontends.widgets.gtk.weakconnect import weak_connect
from miro.frontends.widgets.gtk.tableviewcells import (GTKCustomCellRenderer,
     GTKCheckboxCellRenderer, ItemListRenderer, ItemListRendererText)

PathInfo = namedtuple('PathInfo', 'path column x y') 
Rect = namedtuple('Rect', 'x y width height') 

_album_view_gtkrc_installed = False
def _install_album_view_gtkrc():
    """Hack for styling GTKTreeView for the album view widget.

    We do a couple things:
      - Remove the focus ring
      - Remove any separator space.

    We do this so that we don't draw a box through the album view column for
    selected rows.
    """
    global _album_view_gtkrc_installed
    if _album_view_gtkrc_installed:
        return
    rc_string = ('style "album-view-style"\n'
                 '{ \n'
                 '  GtkTreeView::vertical-separator = 0\n'
                 '  GtkTreeView::horizontal-separator = 0\n'
                 '  GtkWidget::focus-line-width = 0 \n'
                 '}\n'
                 'widget "*.miro-album-view" style "album-view-style"\n')
    gtk.rc_parse_string(rc_string)
    _album_view_gtkrc_installed = True

def rect_contains_rect(outside, inside):
    # currently unused
    return (outside.x <= inside.x and
            outside.y <= inside.y and
            outside.x + outside.width >= inside.x + inside.width and
            outside.y + outside.height >= inside.y + inside.height)

def rect_contains_point(rect, x, y):
    return ((rect.x <= x < rect.x + rect.width) and
            (rect.y <= y < rect.y + rect.height))

class TreeViewScrolling(object):
    def __init__(self):
        self.scrollbars = []
        self.scroll_positions = None, None
        self.restoring_scroll = None
        self.connect('parent-set', self.on_parent_set)
        self.scroller = None
        # hack necessary because of our weird widget hierarchy (GTK doesn't deal
        # well with the Scroller's widget not being the direct parent of the
        # TableView's widget.)
        self._coords_working = False

    def scroll_range_changed(self):
        """Faux-signal; this should all be integrated into
        GTKScrollbarOwnerMixin, making this unnecessary.
        """

    @property
    def manually_scrolled(self):
        """Return whether the view has been scrolled explicitly by the user
        since the last time it was set automatically.
        """
        auto_pos = self.scroll_positions[1]
        if auto_pos is None:
            # if we don't have any position yet, user can't have manually
            # scrolled
            return False
        real_pos = self.scrollbars[1].get_value()
        return abs(auto_pos - real_pos) > 5 # allowing some fuzziness

    @property
    def position_set(self):
        """Return whether the scroll position has been set in any way."""
        return any(x is not None for x in self.scroll_positions)

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
        if self.restoring_scroll:
            self.set_scroll_position(self.restoring_scroll)

    def on_scroll_range_changed(self, adjustment, bar):
        """The scrollbar might have a range now. Set its initial position if
        we haven't already.
        """
        self._coords_working = True
        if self.restoring_scroll:
            self.set_scroll_position(self.restoring_scroll)
        # our wrapper handles the same thing for iters
        self.scroll_range_changed()

    def set_scroll_position(self, scroll_position):
        """Restore the scrollbars to a remembered state."""
        try:
            self.scroll_positions = tuple(self._clip_pos(adj, x)
                    for adj, x in zip(self.scrollbars, scroll_position))
        except WidgetActionError, error:
            logging.debug("can't scroll yet: %s", error.reason)
            # try again later
            self.restoring_scroll = scroll_position
        else:
            for adj, pos in zip(self.scrollbars, self.scroll_positions):
                adj.set_value(pos)
            self.restoring_scroll = None

    def _clip_pos(self, adj, pos):
        lower = adj.get_lower()
        upper = adj.get_upper() - adj.get_page_size()
        # currently, StandardView gets an upper of 2.0 when it's not ready
        # FIXME: don't count on that
        if pos > upper and upper < 5:
            raise WidgetRangeError("scrollable area", pos, lower, upper)
        return min(max(pos, lower), upper)

    def get_path_rect(self, path):
        """Return the Rect for the given item, in tree coords."""
        if not self._coords_working:
            # part of solution to #17405; widget_to_tree_coords tends to return
            # y=8 before the first scroll-range-changed signal. ugh.
            raise WidgetNotReadyError('_coords_working')
        rect = self.get_background_area(path, self.get_columns()[0])
        x, y = self.widget_to_tree_coords(rect.x, rect.y)
        return Rect(x, y, rect.width, rect.height)

    @property
    def _scrollbars(self):
        if not self.scrollbars:
            raise WidgetNotReadyError
        return self.scrollbars

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

class MiroTreeView(gtk.TreeView, TreeViewScrolling):
    """Extends the GTK TreeView widget to help implement TableView
    https://develop.participatoryculture.org/index.php/WidgetAPITableView"""
    # Add a tiny bit of padding so that the user can drag feeds below
    # the table, i.e. to the bottom row, as a top-level
    PAD_BOTTOM = 3
    def __init__(self):
        gtk.TreeView.__init__(self)
        TreeViewScrolling.__init__(self)
        self.drag_dest_at_bottom = False
        self.height_without_pad_bottom = -1
        self.set_enable_search(False)
        self.horizontal_separator = self.style_get_property("horizontal-separator")
        self.expander_size = self.style_get_property("expander-size")
        self.group_lines_enabled = False
        self.group_line_color = (0, 0, 0)
        self.group_line_width = 1
        self._scroll_before_model_change = None

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
        if self._scroll_before_model_change is not None:
            self._restore_scroll_after_model_change()
        gtk.TreeView.do_expose_event(self, event)
        if self.drag_dest_at_bottom:
            gc = self.get_style().fg_gc[self.state]
            x1, x2, y = self.bottom_drag_dest_coords()
            event.window.draw_line(gc, x1, y, x2, y)
        if self.group_lines_enabled and event.window == self.get_bin_window():
            self.draw_group_lines(event)

    def draw_group_lines(self, expose_event):
        # we need both the GTK TreeModel and the ItemList for this one
        gtk_model = self.get_model()
        modelwrapper = wrappermap.wrapper(self).model
        if (not isinstance(modelwrapper, ItemListModel) or
                modelwrapper.item_list.group_func is None):
            return
        # prepare a couple variables for the drawing
        expose_bottom = expose_event.area.y + expose_event.area.height
        cr = expose_event.window.cairo_create()
        cr.set_source_rgb(*self.group_line_color)
        first_column = self.get_columns()[0]
        # start on the top row of the expose event
        path_info = self.get_path_at_pos(expose_event.area.x, expose_event.area.y)
        if path_info is None:
            return
        else:
            path = path_info[0]
            gtk_iter = gtk_model.get_iter(path)
        # draw the lines
        while True:
            # calculate the row's area in the y direction.  We don't care
            # about the x-axis, but PyGTK forces us to pass in a column, so we
            # send in the first one and ignore the x/width attributes.
            background_area = self.get_background_area(path, first_column)
            if background_area.y > expose_bottom:
                break
            # draw stuff if we're on the last row
            index = gtk_model.row_of_iter(gtk_iter)
            group_info = modelwrapper.item_list.get_group_info(index)
            if group_info[0] == group_info[1] - 1:
                y = (background_area.y + background_area.height -
                        self.group_line_width)
                cr.rectangle(expose_event.area.x, y, expose_event.area.width,
                        self.group_line_width)
                cr.fill()
            # prepare for next row
            gtk_iter = gtk_model.iter_next(gtk_iter)
            if gtk_iter is None:
                break
            path = (path[0] + 1,)

    def bottom_drag_dest_coords(self):
        visible = self.get_visible_rect()
        x1 = visible.x
        x2 = visible.x + visible.width
        y = visible.height - self.PAD_BOTTOM
        x1, _ = self.tree_to_widget_coords(x1, y)
        x2, y = self.tree_to_widget_coords(x2, y)
        return x1, x2, y

    def get_position_info(self, x, y):
        """Wrapper for get_path_at_pos that converts the path_info to a named
        tuple and handles rounding the coordinates.
        """
        path_info = self.get_path_at_pos(int(round(x)), int(round(y)))
        if path_info:
            return PathInfo(*path_info)

    def save_scroll_position_before_model_change(self):
        """This method implements a hack to keep our scroll position when we
        change our model.

        For performance reasons, sometimes it's better to to change a model
        than keep a model in place and make a bunch of changes to it (we
        currently do this for ItemListModel).  However, one issue that we run
        into is that when we set the new model, the scroll position is lost.

        Call this method before changing the model to keep the scroll
        position between changes.
        """
        vadjustment = self.get_vadjustment()
        hadjustment = self.get_hadjustment()
        self._scroll_before_model_change = \
                (vadjustment.get_value(), hadjustment.get_value())

    def _restore_scroll_after_model_change(self):
        v_value, h_value = self._scroll_before_model_change
        self._scroll_before_model_change = None
        self.get_vadjustment().set_value(v_value)
        self.get_hadjustment().set_value(h_value)

gobject.type_register(MiroTreeView)

class HotspotTracker(object):
    """Handles tracking hotspots.
    https://develop.participatoryculture.org/index.php/WidgetAPITableView"""

    def __init__(self, treeview, event):
        self.treeview = treeview
        self.treeview_wrapper = wrappermap.wrapper(treeview)
        self.hit = False
        self.button = event.button
        path_info = treeview.get_position_info(event.x, event.y)
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
    # GTK hard-codes 4px of padding for each column
    FIXED_PADDING = 4
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
        self._column.props.min_width = width + TableColumn.FIXED_PADDING

    def set_max_width(self, width):
        self._column.props.max_width = width

    def set_width(self, width):
        self._column.set_fixed_width(width + TableColumn.FIXED_PADDING)

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
        return self.gtk_model.get_string_from_iter(iter_)

    def _iter_from_string(self, string):
        try:
            return self.gtk_model.get_iter_from_string(string)
        except ValueError:
            raise WidgetDomainError(
                  "model iters", string, "%s other iters" % len(self.model))

    def select_path(self, path):
        self.selection.select_path(path)

    def _validate_iter(self, iter_):
        if self.get_path(iter_) is None:
            raise WidgetDomainError(
                  "model iters", iter_, "%s other iters" % len(self.model))
        real_model = self._widget.get_model()
        if not real_model:
            raise WidgetActionError("no model")
        elif real_model != self.gtk_model:
            raise WidgetActionError("wrong model?")

    def get_cursor(self):
        """Return the path of the 'focused' item."""
        path, column = self._widget.get_cursor()
        return path

    def set_cursor(self, path):
        """Set the path of the 'focused' item."""
        if path is None:
            # XXX: is there a way to clear the cursor?
            return
        path_as_string = ':'.join(str(component) for component in path)
        with self.preserving_selection(): # set_cursor() messes up the selection
            self._widget.set_cursor(path_as_string)

class DNDHandlerMixin(object):
    """TableView row DnD.
    
    Depends on arbitrary TableView methods; otherwise self-contained except:
        on_button_press: may call start_drag
        on_button_release: may unset drag_button_down
        on_motion_notify: may call potential_drag_motion
    """
    def __init__(self):
        self.drag_button_down = False
        self.drag_data = {}
        self.drag_source = self.drag_dest = None
        self.drag_start_x, self.drag_start_y = None, None
        self.wrapped_widget_connect('drag-data-get', self.on_drag_data_get)
        self.wrapped_widget_connect('drag-end', self.on_drag_end)
        self.wrapped_widget_connect('drag-motion', self.on_drag_motion)
        self.wrapped_widget_connect('drag-leave', self.on_drag_leave)
        self.wrapped_widget_connect('drag-drop', self.on_drag_drop)
        self.wrapped_widget_connect('drag-data-received',
                self.on_drag_data_received)
        self.wrapped_widget_connect('unrealize', self.on_drag_unrealize)

    def set_drag_source(self, drag_source):
        self.drag_source = drag_source
        # XXX: the following note no longer seems accurate:
        # No need to call enable_model_drag_source() here, we handle it
        # ourselves in on_motion_notify()

    def set_drag_dest(self, drag_dest):
        """Set the drop handler."""
        self.drag_dest = drag_dest
        if drag_dest is not None:
            targets = self._gtk_target_list(drag_dest.allowed_types())
            self._widget.enable_model_drag_dest(targets,
                    drag_dest.allowed_actions())
            self._widget.drag_dest_set(0, targets,
                    drag_dest.allowed_actions())
        else:
            self._widget.unset_rows_drag_dest()
            self._widget.drag_dest_unset()

    def start_drag(self, treeview, event, path_info):
        """Check whether the event is a drag event; return whether handled
        here.
        """
        if event.state & (gtk.gdk.CONTROL_MASK | gtk.gdk.SHIFT_MASK):
            return False
        model, row_paths = treeview.get_selection().get_selected_rows()

        if path_info.path not in row_paths:
            # something outside the selection is being dragged.
            # make it the new selection.
            self.unselect_all(signal=False)
            self.select_path(path_info.path)
            row_paths = [path_info.path]
        rows = self.model.get_rows(row_paths)
        self.drag_data = rows and self.drag_source.begin_drag(self, rows)
        self.drag_button_down = bool(self.drag_data)
        if self.drag_button_down:
            self.drag_start_x = int(event.x)
            self.drag_start_y = int(event.y)

        if len(row_paths) > 1 and path_info.path in row_paths:
            # handle multiple selection.  If the current row is already
            # selected, stop propagating the signal.  We will only change
            # the selection if the user doesn't start a DnD operation.
            # This makes it more natural for the user to drag a block of
            # selected items.
            renderer = path_info.column.get_cell_renderers()[0]
            if (not self._x_coord_in_expander(treeview, path_info)
                    and not isinstance(renderer, GTKCheckboxCellRenderer)):
                self.delaying_press = True
                # grab keyboard focus since we handled the event
                self.focus()
                return True

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
        model = self.gtk_model
        try:
            gtk_path, gtk_position = self._widget.get_dest_row_at_pos(x, y)
        except TypeError:
            # Below the last row
            yield (None, model.iter_n_children(None), None, None)
            return

        iter_ = model.get_iter(gtk_path)
        if gtk_position in (gtk.TREE_VIEW_DROP_INTO_OR_BEFORE,
                gtk.TREE_VIEW_DROP_INTO_OR_AFTER):
            yield (iter_, -1, gtk_path, gtk_position)

        assert model.iter_is_valid(iter_)
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
            if isinstance(drop_action, (list, tuple)):
                drop_action, iter = drop_action
                path = self.model.get_path(iter)
                pos = gtk.TREE_VIEW_DROP_INTO_OR_BEFORE
            else:
                path, pos = pos_info[2:4]
            
            if drop_action:
                self.set_drag_dest_row(path, pos)
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

    def on_drag_data_received(self,
            treeview, drag_context, x, y, selection, info, timestamp):
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

    def on_drag_unrealize(self, treeview):
        self.drag_button_down = False

    def potential_drag_motion(self, treeview, event):
        """A motion event has occurred and did not hit a hotspot; start a drag
        if applicable.
        """
        if (self.drag_data and self.drag_button_down and
                treeview.drag_check_threshold(self.drag_start_x,
                    self.drag_start_y, int(event.x), int(event.y))):
            self.delaying_press = False
            treeview.drag_begin(self._gtk_target_list(self.drag_data.keys()),
                    self.drag_source.allowed_actions(), 1, event)

    @staticmethod
    def _gtk_target_list(types):
        count = itertools.count()
        return [(type, gtk.TARGET_SAME_APP, count.next()) for type in types]

class HotspotTrackingMixin(object):
    def __init__(self):
        self.hotspot_tracker = None
        self.create_signal('hotspot-clicked')
        self._hotspot_callback_handles = []
        self._connect_hotspot_signals()
        self.wrapped_widget_connect('unrealize', self.on_hotspot_unrealize)

    def _connect_hotspot_signals(self):
        SIGNALS = {
            'row-inserted': self.on_row_inserted,
            'row-deleted': self.on_row_deleted,
            'row-changed': self.on_row_changed,
        }
        self._hotspot_callback_handles.extend(
                weak_connect(self.gtk_model, signal, handler)
                for signal, handler in SIGNALS.iteritems())

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

    def handle_hotspot_hit(self, treeview, event):
        """Check whether the event is a hotspot event; return whether handled
        here.
        """
        if self.hotspot_tracker:
            return
        hotspot_tracker = HotspotTracker(treeview, event)
        if hotspot_tracker.hit:
            self.hotspot_tracker = hotspot_tracker
            hotspot_tracker.redraw_cell()
            if hotspot_tracker.is_for_context_menu():
                menu = self._popup_context_menu(self.hotspot_tracker.path, event)
                if menu:
                    menu.connect('selection-done',
                            self._on_hotspot_context_menu_selection_done)
            # grab keyboard focus since we handled the event
            self.focus()
            return True

    def _on_hotspot_context_menu_selection_done(self, menu):
        # context menu is closed, we won't get the button-release-event in
        # this case, but we can unset hotspot tracker here.
        if self.hotspot_tracker:
            self.hotspot_tracker.redraw_cell()
            self.hotspot_tracker = None

    def on_hotspot_unrealize(self, treeview):
        self.hotspot_tracker = None

    def release_on_hotspot(self, event):
        """A button_release occurred; return whether it has been handled as a
        hotspot hit.
        """
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

class ColumnOwnerMixin(object):
    """Keeps track of the table's columns - including the list of columns, and
    properties that we set for a table but need to apply to each column.

    This manages:
        columns
        attr_map_for_column
        gtk_column_to_wrapper
    for use throughout tableview.
    """
    def __init__(self):
        self._columns_draggable = False
        self._renderer_xpad = self._renderer_ypad = 0
        self.columns = []
        self.attr_map_for_column = {}
        self.gtk_column_to_wrapper = {}
        self.create_signal('reallocate-columns') # not emitted on GTK

    def remove_column(self, index):
        """Remove a column from the display and forget it from the column lists.
        """
        column = self.columns.pop(index)
        del self.attr_map_for_column[column._column]
        del self.gtk_column_to_wrapper[column._column]
        self._widget.remove_column(column._column)

    def get_columns(self):
        """Returns the current columns, in order, by title."""
        # FIXME: this should probably return column objects, and really should
        # not be keeping track of columns by title at all
        titles = [column.get_title().decode('utf-8')
                for column in self._widget.get_columns()]
        return titles

    def add_column(self, column):
        """Append a column to this table; setup all necessary mappings, and
        setup the new column's properties to match the table's settings.
        """
        self.model.check_new_column(column)
        self._widget.append_column(column._column)
        self.columns.append(column)
        self.attr_map_for_column[column._column] = column.attrs
        self.gtk_column_to_wrapper[column._column] = column
        self.setup_new_column(column)

    def setup_new_column(self, column):
        """Apply properties that we keep track of at the table level to a
        newly-created column.
        """
        if self.background_color:
            column.renderer._renderer.set_property('cell-background-gdk',
                    self.background_color)
        column._column.set_reorderable(self._columns_draggable)
        if column.do_horizontal_padding:
            column.renderer._renderer.set_property('xpad', self._renderer_xpad)
        column.renderer._renderer.set_property('ypad', self._renderer_ypad)

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

    def set_columns_draggable(self, setting):
        """Set the draggability of existing and future columns."""
        self._columns_draggable = setting
        for column in self.columns:
            column._column.set_reorderable(setting)

    def set_column_background_color(self):
        """Set the background color of existing columns to the table's
        background_color.
        """
        for column in self.columns:
            column.renderer._renderer.set_property('cell-background-gdk',
                    self.background_color)

    def set_auto_resizes(self, setting):
        # FIXME: to be implemented.
        # At this point, GTK somehow does the right thing anyway in terms of
        # auto-resizing.  I'm not sure exactly what's happening, but I believe
        # that if the column widths don't add up to the total width,
        # gtk.TreeView allocates extra width for the last column.  This works
        # well enough for the tab list and item list, since there's only one
        # column.
        pass

class HoverTrackingMixin(object):
    """Handle mouse hover events - tooltips for some cells and hover events for
    renderers which support them.
    """
    def __init__(self):
        self.hover_info = None
        self.hover_pos = None
        if hasattr(self, 'get_tooltip'):
            # this should probably be something like self.set_tooltip_source
            self._widget.set_property('has-tooltip', True)
            self.wrapped_widget_connect('query-tooltip', self.on_tooltip)
            self._last_tooltip_place = None

    def on_tooltip(self, treeview, x, y, keyboard_mode, tooltip):
        # x, y are relative to the entire widget, but we want them to be
        # relative to our bin window.  The bin window doesn't include things
        # like the column headers.
        origin = treeview.window.get_origin()
        bin_origin = treeview.get_bin_window().get_origin()
        x += origin[0] - bin_origin[0]
        y += origin[1] - bin_origin[1]
        path_info = treeview.get_position_info(x, y)
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
        iter_ = treeview.get_model().get_iter(path_info.path)
        column = self.gtk_column_to_wrapper[path_info.column]
        text = self.get_tooltip(iter_, column)
        if text is None:
            return False
        pygtkhacks.set_tooltip_text(tooltip, text)
        return True

    def _update_hover(self, treeview, event):
        old_hover_info, old_hover_pos = self.hover_info, self.hover_pos
        path_info = treeview.get_position_info(event.x, event.y)
        if (path_info and
                self.gtk_column_to_wrapper[path_info.column].renderer.want_hover):
            self.hover_info = path_info.path, path_info.column
            self.hover_pos = path_info.x, path_info.y
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

class GTKScrollbarOwnerMixin(ScrollbarOwnerMixin):
    # XXX this is half a wrapper for TreeViewScrolling. A lot of things will
    # become much simpler when we integrate TVS into this
    def __init__(self):
        ScrollbarOwnerMixin.__init__(self)
        # super uses this for postponed scroll_to_iter
        # it's a faux-signal from our _widget; this hack is only necessary until
        # we integrate TVS
        self._widget.scroll_range_changed = (lambda *a:
                self.emit('scroll-range-changed'))

    def set_scroller(self, scroller):
        """Set the Scroller object for this widget, if its ScrolledWindow is
        not a direct ancestor of the object. Standard View needs this.
        """
        self._widget.set_scroller(scroller._widget)

    def _set_scroll_position(self, scroll_pos):
        self._widget.set_scroll_position(scroll_pos)

    def _get_item_area(self, iter_):
        return self._widget.get_path_rect(self.get_path(iter_))

    @property
    def _manually_scrolled(self):
        return self._widget.manually_scrolled

    @property
    def _position_set(self):
        return self._widget.position_set

    def _get_visible_area(self):
        """Return the Rect of the visible area, in tree coords.

        get_visible_rect gets this wrong for StandardView, always returning an
        origin of (0, 0) - this is because our ScrolledWindow is not our direct
        parent.
        """
        bars = self._widget._scrollbars
        x, y = (int(adj.get_value()) for adj in bars)
        width, height = (int(adj.get_page_size()) for adj in bars)
        if height == 0:
            # this happens even after _widget._coords_working
            raise WidgetNotReadyError('visible height')
        return Rect(x, y, width, height)
    
    def _get_scroll_position(self):
        """Get the current position of both scrollbars, to restore later."""
        try:
            return tuple(int(bar.get_value()) for bar in self._widget._scrollbars)
        except WidgetNotReadyError:
            return None

class TableView(Widget, GTKSelectionOwnerMixin, DNDHandlerMixin,
        HotspotTrackingMixin, ColumnOwnerMixin, HoverTrackingMixin,
        GTKScrollbarOwnerMixin):
    """https://develop.participatoryculture.org/index.php/WidgetAPITableView"""

    draws_selection = True

    def __init__(self, model, custom_headers=False):
        Widget.__init__(self)
        self.set_widget(MiroTreeView())
        self.init_model(model)
        self._setup_colors()
        self.background_color = None
        self.context_menu_callback = None
        self.delaying_press = False
        self._use_custom_headers = False
        self.layout_manager = LayoutManager(self._widget)
        self.height_changed = None # 17178 hack
        self._connect_signals()
        # setting up mixins after general TableView init
        GTKSelectionOwnerMixin.__init__(self)
        DNDHandlerMixin.__init__(self)
        HotspotTrackingMixin.__init__(self)
        ColumnOwnerMixin.__init__(self)
        HoverTrackingMixin.__init__(self)
        GTKScrollbarOwnerMixin.__init__(self)
        if custom_headers:
            self._enable_custom_headers()

    def init_model(self, model):
        self.model = model
        self.model_handler = make_model_handler(model, self._widget)

    @property
    def gtk_model(self):
        return self.model._model

    # FIXME: should implement set_model() and make None a special case.
    def unset_model(self):
        """Disconnect our model from this table view.

        This should be called when you want to destroy a TableView and
        there's a new TableView sharing its model.
        """
        self.model.cleanup()
        self._widget.set_model(None)
        self.model_handler = self.model = None

    def _connect_signals(self):
        self.create_signal('row-expanded')
        self.create_signal('row-collapsed')
        self.create_signal('row-clicked')
        self.create_signal('row-activated')
        self.wrapped_widget_connect('row-activated', self.on_row_activated)
        self.wrapped_widget_connect('row-expanded', self.on_row_expanded)
        self.wrapped_widget_connect('row-collapsed', self.on_row_collapsed)
        self.wrapped_widget_connect('button-press-event', self.on_button_press)
        self.wrapped_widget_connect('button-release-event',
            self.on_button_release)
        self.wrapped_widget_connect('motion-notify-event',
            self.on_motion_notify)

    def set_gradient_highlight(self, gradient):
        # This is just an OS X thing.
        pass

    def set_background_color(self, color):
        self.background_color = self.make_color(color)
        self.modify_style('base', gtk.STATE_NORMAL, self.background_color)
        if not self.draws_selection:
            self.modify_style('base', gtk.STATE_SELECTED,
                              self.background_color)
            self.modify_style('base', gtk.STATE_ACTIVE, self.background_color)
        if self.use_custom_style:
            self.set_column_background_color()

    def set_group_lines_enabled(self, enabled):
        """Enable/Disable group lines.

        This only has an effect if our model is an ItemListModel and it has a
        grouping set.

        If group lines are enabled, we will draw a line below the last item in
        the group.  Use set_group_line_style() to change the look of the line.
        """
        self._widget.group_lines_enabled = enabled
        self.queue_redraw()

    def set_group_line_style(self, color, width):
        self._widget.group_line_color = color
        self._widget.group_line_width = width
        self.queue_redraw()

    def handle_custom_style_change(self):
        if self.background_color is not None:
            if self.use_custom_style:
                self.set_column_background_color()
            else:
                for column in self.columns:
                    column.renderer._renderer.set_property(
                            'cell-background-set', False)

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

    def width_for_columns(self, total_width):
        """Given the width allocated for the TableView, return how much of that
        is available to column contents. Note that this depends on the number of
        columns.
        """
        column_spacing = TableColumn.FIXED_PADDING * len(self.columns)
        return total_width - column_spacing

    def enable_album_view_focus_hack(self):
        _install_album_view_gtkrc()
        self._widget.set_name("miro-album-view")

    def focus(self):
        self._widget.grab_focus()

    def _enable_custom_headers(self):
        # NB: this is currently not used because the GTK tableview does not
        # support custom headers.
        self._use_custom_headers = True

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
        path = self.get_path(iter_)
        if expanded:
            self._widget.expand_row(path, False)
        else:
            self._widget.collapse_row(path)
        if bool(self._widget.row_expanded(path)) != bool(expanded):
            raise WidgetActionError("cannot expand the given item - it "
                    "probably has no children.")

    def is_row_expanded(self, iter_):
        path = self.get_path(iter_)
        return self._widget.row_expanded(path)

    def set_context_menu_callback(self, callback):
        self.context_menu_callback = callback

    # GTK is really good and it is safe to operate on table even when
    # cells may be constantly changing in flux.
    def set_volatile(self, volatile):
        return

    def on_row_expanded(self, _widget, iter_, path):
        self.emit('row-expanded', iter_)

    def on_row_collapsed(self, _widget, iter_, path):
        self.emit('row-collapsed', iter_)

    def on_button_press(self, treeview, event):
        """Handle a mouse button press"""
        if event.type == gtk.gdk._2BUTTON_PRESS:
            # already handled as row-activated
            return False

        path_info = treeview.get_position_info(event.x, event.y)
        if not path_info:
            # no item was clicked, so it's not going to be a hotspot, drag, or
            # context menu
            return False
        if event.type == gtk.gdk.BUTTON_PRESS:
            # single click; emit the event but keep on running so we can handle
            # stuff like drag and drop.
            if not self._x_coord_in_expander(treeview, path_info):
                iter_ = treeview.get_model().get_iter(path_info.path)
                self.emit('row-clicked', iter_)

        if (event.button == 1 and self.handle_hotspot_hit(treeview, event)):
            return True
        if event.window != treeview.get_bin_window():
            # click is outside the content area, don't try to handle this.
            # In particular, our DnD code messes up resizing table columns.
            return False
        if (event.button == 1 and self.drag_source and
          not self._x_coord_in_expander(treeview, path_info)):
            return self.start_drag(treeview, event, path_info)
        elif event.button == 3 and self.context_menu_callback:
            self.show_context_menu(treeview, event, path_info)
            return True

        # FALLTHROUGH
        return False

    def show_context_menu(self, treeview, event, path_info):
        """Pop up a context menu for the given click event (which is a
        right-click on a row).
        """
        # hack for album view
        if (treeview.group_lines_enabled and
            path_info.column == treeview.get_columns()[0]):
            self._select_all_rows_in_group(treeview, path_info.path)
        self._popup_context_menu(path_info.path, event)
        # grab keyboard focus since we handled the event
        self.focus()

    def _select_all_rows_in_group(self, treeview, path):
        """Select all items in the group """

        # FIXME: this is very tightly coupled with the portable code.

        modelwrapper = self.model
        gtk_model = treeview.get_model()
        if (not isinstance(modelwrapper, ItemListModel) or
            modelwrapper.item_list.group_func is None):
            return
        modelwrapper.item_list.group_info(path[0])

        start_row = path[0] - group_info[0]
        total_rows = group_info[1]

        with self._ignoring_changes():
            self.unselect_all()
            for row in xrange(start_row, start_row + total_rows):
                self.select_path((row,))
            self.emit('selection-changed')

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

    # XXX treeview.get_cell_area handles what we're trying to use this for
    def _x_coord_in_expander(self, treeview, path_info):
        """Calculate if an x coordinate is over the expander triangle

        :param treeview: Gtk.TreeView
        :param path_info: PathInfo(
            tree path for the cell,
            Gtk.TreeColumn,
            x coordinate relative to column's cell area,
            y coordinate relative to column's cell area (ignored),
        )
        """
        if path_info.column != treeview.get_expander_column():
            return False
        model = treeview.get_model()
        if not model.iter_has_child(model.get_iter(path_info.path)):
            return False
        # GTK allocateds an extra 4px to the right of the expanders.  This
        # seems to be hardcoded as EXPANDER_EXTRA_PADDING in the source code.
        total_exander_size = treeview.expander_size + 4
        # include horizontal_separator
        # XXX: should this value be included in total_exander_size ?
        offset = treeview.horizontal_separator / 2
        # allocate space for expanders for parent nodes
        expander_start = total_exander_size * (len(path_info.path) - 1) + offset
        expander_end = expander_start + total_exander_size + offset
        return expander_start <= path_info.x < expander_end

    def on_row_activated(self, treeview, path, view_column):
        iter_ = treeview.get_model().get_iter(path)
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
        if self.release_on_hotspot(event):
            return True
        if event.button == 1:
            self.drag_button_down = False

            if self.delaying_press:
                # if dragging did not happen, unselect other rows and
                # select current row
                path_info = treeview.get_position_info(event.x, event.y)
                if path_info is not None:
                    self.unselect_all(signal=False)
                    self.select_path(path_info.path)
        self.delaying_press = False

    def _redraw_cell(self, treeview, path, column):
        cell_area = treeview.get_cell_area(path, column)
        x, y = treeview.convert_bin_window_to_widget_coords(cell_area.x,
                                                            cell_area.y)
        treeview.queue_draw_area(x, y, cell_area.width, cell_area.height)

    def on_motion_notify(self, treeview, event):
        self._update_hover(treeview, event)

        if self.hotspot_tracker:
            self.hotspot_tracker.update_position(event)
            self.hotspot_tracker.update_hit()
            return True

        self.potential_drag_motion(treeview, event)
        return None # XXX: used to fall through; not sure what retval does here

    def model_changed(self):
        self.model_handler.model_changed()

    def get_path(self, iter_):
        """Always use this rather than the model's get_path directly -
        if the iter isn't valid, a GTK assertion causes us to exit
        without warning; this wrapper changes that to a much more useful
        AssertionError. Example related bug: #17362.
        """
        assert self.model.iter_is_valid(iter_)
        return self.gtk_model.get_path(iter_)

class TableModelBase(object):
    """Base class for all TableModels."""
    def cleanup(self):
        pass

    def first_iter(self):
        return self._model.get_iter_first()

    def next_iter(self, iter_):
        return self._model.iter_next(iter_)

    def nth_iter(self, index):
        assert index >= 0
        return self._model.iter_nth_child(None, index)

    def get_path(self, iter_):
        return self._model.get_path(iter_)

    def iter_is_valid(self, iter_):
        return self._model.iter_is_valid(iter_)

    def __len__(self):
        return len(self._model)

class TableModel(TableModelBase):
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
        assert self._model.iter_is_valid(iter_)
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

    def __iter__(self):
        return iter(self._model)

    def __getitem__(self, iter_):
        return self._model[iter_]

    def get_rows(self, row_paths):
        return [self._model[path] for path in row_paths]

class TreeTableModel(TableModel):
    """https://develop.participatoryculture.org/index.php/WidgetAPITableView"""
    MODEL_CLASS = gtk.TreeStore

    def append(self, *column_values):
        return self._model.append(None, self.convert_row_for_gtk(
            column_values))

    def insert_before(self, iter_, *column_values):
        parent = self.parent_iter(iter_)
        row = self.convert_row_for_gtk(column_values)
        return self._model.insert_before(parent, iter_, row)

    def append_child(self, iter_, *column_values):
        return self._model.append(iter_, self.convert_row_for_gtk(
            column_values))

    def child_iter(self, iter_):
        return self._model.iter_children(iter_)

    def nth_child_iter(self, iter_, index):
        assert index >= 0
        return self._model.iter_nth_child(iter_, index)

    def has_child(self, iter_):
        return self._model.iter_has_child(iter_)

    def children_count(self, iter_):
        return self._model.iter_n_children(iter_)

    def parent_iter(self, iter_):
        assert self._model.iter_is_valid(iter_)
        return self._model.iter_parent(iter_)

class ItemListModel(TableModelBase):
    """Special model to use with ItemLists
    """

    def __init__(self, item_list):
        self.item_list = item_list
        self.list_changed_handle = self.item_list.connect_before(
            "list-changed", self.on_list_changed)
        self._model = fixedliststore.FixedListStore(len(item_list))

    def cleanup(self):
        if self.list_changed_handle is not None:
            self.item_list.disconnect(self.list_changed_handle)
            self.list_changed_handle = None

    def on_list_changed(self, item_list):
        # When the list changes, we need to create a new FixedListStore object
        # to handle it.  ItemListModelHandler then updates the GtkTreeView
        # with this new model.
        self._model = fixedliststore.FixedListStore(len(item_list))

    def get_item(self, it):
        return self.item_list.get_row(self._model.row_of_iter(it))

    def iter_for_id(self, item_id):
        """Get an iter that points to an item in this list."""
        row = self.item_list.get_index(item_id)
        return self._model.iter_nth_child(None, row)

    def __getitem__(self, it):
        """Get a row of data
        
        For ItemListModel, this is the tuple (info, attrs, group_info)
        """
        index = self._model.row_of_iter(it)
        item = self.item_list.get_row(index)
        attrs = self.item_list.get_attrs(item.id)
        group_info = self.item_list.get_group_info(index)
        return (item, attrs, group_info)

    def check_new_column(self, column):
        if not (isinstance(column.renderer, ItemListRenderer) or
                isinstance(column.renderer, ItemListRendererText)):
            raise TypeError("ItemListModel only supports ItemListRenderer "
                    "or ItemListRendererText")

    def get_rows(self, row_paths):
        return [(self.item_list.get_row(path[0]),) for path in row_paths]

    def iter_is_valid(self, iter_):
        # there's no way to check this for FixedListStore.  Let's just assume
        # that iters are valid, since the model never changes.
        return True

    def __len__(self):
        return self._model.get_property("row_count")

class ModelHandler(object):
    """Used by TableModel to handle its TableModel

    This class defines the default behavior.  Subclasses extend it handle
    specific models.  make_model_handler() is a factory method to create the
    correct ModelHandler for a given TableModel.
    """
    def __init__(self, model, gtk_treeview):
        self.model = model
        self.gtk_treeview = gtk_treeview
        self._set_gtk_model()

    def _set_gtk_model(self):
        gtk_model = self.model._model
        self.gtk_treeview.set_model(gtk_model)
        wrappermap.add(gtk_model, self.model)

    def reset_gtk_model(self):
        self.gtk_treeview.save_scroll_position_before_model_change()
        self._set_gtk_model()

    # Note: by default, we don't need to do anything special for
    # model_changed().
    def model_changed(self):
        return

class ItemListModelHandler(ModelHandler):
    """
    """
    def __init__(self, model, gtk_treeview):
        ModelHandler.__init__(self, model, gtk_treeview)
        item_list = self.model.item_list

    def model_changed(self):
        if self.model._model != self.gtk_treeview.get_model():
            # Items have been added or removed and ItemListModel has created a
            # FixedListStore for the new list.  Update our widget.
            self.reset_gtk_model()
        else:
            # Some of the items have changed, but the list is the same.  Ask
            # the treeview to redraw itself.
            self.gtk_treeview.queue_draw()

def make_model_handler(model, gtk_treeview):
    if isinstance(model, ItemListModel):
        return ItemListModelHandler(model, gtk_treeview)
    else:
        return ModelHandler(model, gtk_treeview)
