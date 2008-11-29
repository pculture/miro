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

"""tableview.py -- Wrapper for the GTKTreeView widget.  It's used for the tab
list and the item list (AKA almost all of the miro).
"""
import itertools

import gobject
import gtk
import pango

from miro import signals
from miro.frontends.widgets.gtk import pygtkhacks
from miro.frontends.widgets.gtk import drawing
from miro.frontends.widgets.gtk import wrappermap
from miro.frontends.widgets.gtk.base import Widget, make_gdk_color
from miro.frontends.widgets.gtk.simple import Image
from miro.frontends.widgets.gtk.layoutmanager import LayoutManager
from miro.frontends.widgets.gtk.weakconnect import weak_connect

def rect_contains_rect(outside, inside):
    return (outside.x <= inside.x and 
            outside.y <= inside.y and 
            outside.x + outside.width >= inside.x + inside.width and
            outside.y + outside.height >= inside.y + inside.height)

def rect_contains_point(rect, x, y):
    return ((rect.x <= x < rect.x + rect.width) and 
            (rect.y <= y < rect.y + rect.height))

class CellRenderer(object):
    """Simple Cell Renderer
    https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPITableView"""
    def __init__(self):
        self._renderer = gtk.CellRendererText()

    def setup_attributes(self, column, attr_map): 
        column.add_attribute(self._renderer, 'text', attr_map['value'])

    def set_color(self, color):
        self._renderer.props.foreground_gdk = make_gdk_color(color)

    def set_bold(self, bold):
        font_desc = self._renderer.props.font_desc
        if bold:
            font_desc.set_weight(pango.WEIGHT_BOLD)
        else:
            font_desc.set_weight(pango.WEIGHT_NORMAL)
        self._renderer.props.font_desc = font_desc

class ImageCellRenderer(object):
    """Cell Renderer for images
    https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPITableView"""
    def __init__(self):
        self._renderer = gtk.CellRendererPixbuf()

    def setup_attributes(self, column, attr_map):
        column.add_attribute(self._renderer, 'pixbuf', attr_map['image'])

class GTKCheckboxCellRenderer(gtk.CellRendererToggle):
    def do_activate(self, event, treeview, path, background_area, cell_area,
            flags):
        iter = treeview.get_model().get_iter(path)
        self.set_active(not self.get_active())
        wrappermap.wrapper(self).emit('clicked', iter)

gobject.type_register(GTKCheckboxCellRenderer)

class CheckboxCellRenderer(signals.SignalEmitter):
    """Cell Renderer for booleans
    https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPITableView"""
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.create_signal("clicked")
        self._renderer = GTKCheckboxCellRenderer()
        wrappermap.add(self._renderer, self)

    def setup_attributes(self, column, attr_map):
        column.add_attribute(self._renderer, 'active', attr_map['value'])

class GTKCustomCellRenderer(gtk.GenericCellRenderer):
    """Handles the GTK hide of CustomCellRenderer
    https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPITableView"""

    def on_get_size(self, widget, cell_area=None):
        wrapper = wrappermap.wrapper(self)
        widget_wrapper = wrappermap.wrapper(widget)
        style = drawing.DrawingStyle(widget_wrapper, use_base_color=True)
        # NOTE: CustomCellRenderer.cell_data_func() sets up its attributes
        # from the model itself, so we don't have to worry about setting them
        # here.
        width, height = wrapper.get_size(style, widget_wrapper.layout_manager)
        x_offset = self.props.xpad
        y_offset = self.props.ypad
        width += self.props.xpad * 2
        height += self.props.ypad * 2
        if cell_area:
            x_offset += cell_area.x
            y_offset += cell_area.x
            extra_width = max(0, cell_area.width - width)
            extra_height = max(0, cell_area.height - height)
            x_offset += int(round(self.props.xalign * extra_width))
            y_offset += int(round(self.props.yalign * extra_height))
        return x_offset, y_offset, width, height

    def on_render(self, window, widget, background_area, cell_area, expose_area,
            flags):
        selected = (flags & gtk.CELL_RENDERER_SELECTED)
        if selected: 
            if widget.flags() & gtk.HAS_FOCUS:
                state = gtk.STATE_SELECTED
            else:
                state = gtk.STATE_ACTIVE
        else: 
            state = gtk.STATE_NORMAL
        xpad = self.props.xpad
        ypad = self.props.ypad
        area = gtk.gdk.Rectangle(cell_area.x + xpad, cell_area.y + ypad,
                cell_area.width - xpad * 2, cell_area.height - ypad * 2)
        context = drawing.DrawingContext(window, area, expose_area)
        widget_wrapper = wrappermap.wrapper(widget)
        if selected and widget_wrapper.use_custom_style:
            # Draw the base color as our background.  This erases the gradient
            # that GTK draws for selected items.
            area = widget.get_background_area(self.path, self.column)
            window.draw_rectangle(widget.style.base_gc[state], True,
                    area.x, area.y, area.width, area.height)
        context.style = drawing.DrawingStyle(widget_wrapper,
                use_base_color=True, state=state)
        owner = wrappermap.wrapper(self)
        widget_wrapper.layout_manager.update_cairo_context(context.context)
        hotspot_tracker = widget_wrapper.hotspot_tracker
        if (hotspot_tracker and hotspot_tracker.hit and 
                hotspot_tracker.column == self.column and
                hotspot_tracker.path == self.path):
            hotspot = hotspot_tracker.name
        else:
            hotspot = None
        widget_wrapper.layout_manager.reset()
        hover = (self.path, self.column) == widget_wrapper.hover_info
        # NOTE: CustomCellRenderer.cell_data_func() sets up its attributes
        # from the model itself, so we don't have to worry about setting them
        # here.
        owner.render(context, widget_wrapper.layout_manager, selected,
                hotspot, hover)

    def on_activate(self, event, widget, path, background_area, cell_area, 
            flags):
        pass

    def on_start_editing(self, event, widget, path, background_area, 
            cell_area, flags):
        pass
gobject.type_register(GTKCustomCellRenderer)

class CustomCellRenderer(object):
    """Customizable Cell Renderer
    https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPITableView"""
    def __init__(self):
        self._renderer = GTKCustomCellRenderer()
        wrappermap.add(self._renderer, self)

    def setup_attributes(self, column, attr_map):
        column.set_cell_data_func(self._renderer, self.cell_data_func,
                attr_map)

    def cell_data_func(self, column, cell, model, iter, attr_map):
        cell.column = column
        cell.path = model.get_path(iter)
        row = model[iter]
        # Set attributes on self instead cell This works because cell is just
        # going to turn around and call our methods to do the renderering.
        for name, index in attr_map.items():
            setattr(self, name, row[index])

    def hotspot_test(self, style, layout, x, y, width, height):
        return None

class MiroTreeView(gtk.TreeView):
    """Extends the GTK TreeView widget to help implement TableView
    https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPITableView"""
    # Add a tiny bit of padding so that the user can drag channels below
    # the table, i.e. to the bottom row, as a top-level
    PAD_BOTTOM = 3
    def __init__(self, model=None):
        gtk.TreeView.__init__(self, model)
        self.drag_dest_at_bottom = False
        self.height_without_pad_bottom = -1

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
        x, y = self.tree_to_widget_coords(0, self.height_without_pad_bottom)
        event.window.draw_rectangle(self.style.base_gc[self.state], True,
                x, y, self.allocation.width, self.PAD_BOTTOM)
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
    https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPITableView"""

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
        old_hit = self.hit
        self.hit = (self.calc_hotspot() == self.name)
        if self.hit != old_hit:
            self.redraw_cell()

    def redraw_cell(self):
        # Check that the treeview is still around.  We might have switched
        # views in response to a hotspot being clicked.
        if self.treeview.flags() & gtk.REALIZED:
            cell_area = self.treeview.get_cell_area(self.path, self.column)
            self.treeview.queue_draw_area(cell_area.x, cell_area.y,
                    cell_area.width, cell_area.height)

class TableColumn(signals.SignalEmitter):
    """A single column of a TableView.
    
    Signals:

        clicked (table_column) -- The header for this column was clicked.
    """
    def __init__(self, title, renderer, **attrs):
        signals.SignalEmitter.__init__(self)
        self.create_signal('clicked')
        self._column = gtk.TreeViewColumn(title, renderer._renderer)
        self._column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self._column.set_clickable(True)
        self.attrs = attrs
        renderer.setup_attributes(self._column, attrs)
        self.renderer = renderer
        weak_connect(self._column, 'clicked', self._header_clicked)

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
        self._column.props.fixed_width = width

    def _header_clicked(self, tablecolumn):
        self.emit('clicked')

    def set_resizable(self, resizable):
        """Set if the user can resize the column."""
        self._column.set_resizable(resizable)

    def set_sort_indicator_visible(self, visible):
        """Show/Hide the sort indicator for this column."""
        self._column.set_sort_indicator(visible)

    def get_sort_indicator_visible(self):
        return self._column.get_sort_indicator()

    def set_sort_order(self, ascending):
        """Display a sort indicator on the column header.  Ascending can be
        either True or False which affects the diraction of the indicator.
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

class TableView(Widget):
    """https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPITableView"""
    def __init__(self, model):
        Widget.__init__(self)
        self.model = model
        self.set_widget(MiroTreeView(model._model))
        self.selection = self._widget.get_selection()
        self.columns = []
        self.attr_map_for_column = {}
        self.background_color = None
        self.drag_button_down = False
        self._renderer_xpad = self._renderer_ypad = 0
        self.context_menu_callback = self.drag_source = self.drag_dest = None
        self.hotspot_tracker = None
        self.hover_info = None
        self.ignore_selection_changed = False
        self.set_columns_draggable(False)
        self.create_signal('row-expanded')
        self.create_signal('row-collapsed')
        self.create_signal('selection-changed')
        self.create_signal('hotspot-clicked')
        self.create_signal('row-double-clicked')
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
        self.wrapped_widget_connect('drag-data-received',
                self.on_drag_data_received)
        weak_connect(self.selection, 'changed', self.on_selection_changed)
        weak_connect(self.model._model, 'row-inserted', self.on_row_inserted)
        weak_connect(self.model._model, 'row-deleted', self.on_row_deleted)
        weak_connect(self.model._model, 'row-changed', self.on_row_changed)
        self.layout_manager = LayoutManager(self._widget)

    def set_background_color(self, color):
        self.background_color = self.make_color(color)
        self.modify_style('base', gtk.STATE_NORMAL, self.background_color)
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

    def _check_attr_map(self, attrs):
        for value in attrs.values():
            if not isinstance(value, int):
                msg = "Attribute values must be integers, not %r" % value
                raise TypeError(msg)
            if value < 0 or value >= len(self.model._column_types):
                raise ValueError("Attribute index out of range: %s" % value)

    def set_column_spacing(self, space):
        """Set the amount of space between columns."""
        self._renderer_xpad = space / 2
        for column in self.columns:
            column.renderer._renderer.set_property('xpad', self._renderer_xpad)

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
            value = gtk.TREE_VIEW_GRID_LINES_NONE
        self._widget.set_grid_lines(setting)

    def add_column(self, column):
        self._check_attr_map(column.attrs)
        self._widget.append_column(column._column)
        self.columns.append(column)
        self.attr_map_for_column[column._column] = column.attrs
        self.setup_new_column(column)

    def remove_column(self, index):
        column = self.columns.pop(index)
        del self.attr_map_for_column[column._column]
        self._widget.remove_column(index)

    def width_for_columns(self, total_width):
        # as far as I can tell, GTK includes the column spacing in the column
        # widths
        return total_width

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

    def column_count(self):
        return len(self._widget.get_columns())

    def set_show_headers(self, show):
        self._widget.set_headers_visible(show)
        self._widget.set_headers_clickable(show)

    def set_draws_selection(self, draws_selection):
        style = self._widget.style
        if not draws_selection:
            self.modify_style('base', gtk.STATE_SELECTED,
                style.base[gtk.STATE_NORMAL])
            self.modify_style('base', gtk.STATE_ACTIVE,
                style.base[gtk.STATE_NORMAL])
        else:
            self.unmodify_style('base', gtk.STATE_SELECTED)
            self.unmodify_style('base', gtk.STATE_ACTIVE)

    def set_search_column(self, model_index):
        self._widget.set_search_column(model_index)

    def set_fixed_height(self, fixed_height):
        self._widget.set_fixed_height_mode(fixed_height)

    def allow_multiple_select(self, allow):
        if allow:
            mode = gtk.SELECTION_MULTIPLE
        else:
            mode = gtk.SELECTION_SINGLE
        self.selection.set_mode(mode)

    def get_selection(self):
        iters = []
        def collect(treemodel, path, iter):
            iters.append(iter)
        self.selection.selected_foreach(collect)
        return iters

    def get_selected(self):
        model, iter = self.selection.get_selected()
        return iter

    def num_rows_selected(self):
        return self.selection.count_selected_rows()

    def select(self, iter):
        return self.selection.select_iter(iter)

    def unselect(self, iter):
        return self.selection.unselect_iter(iter)

    def unselect_all(self):
        return self.selection.unselect_all()

    def set_row_expanded(self, iter, expanded):
        path = self.model._model.get_path(iter)
        if expanded:
            self._widget.expand_row(path, False)
        else:
            self._widget.collapse_row(path)

    def is_row_expanded(self, iter):
        path = self.model._model.get_path(iter)
        return self._widget.row_expanded(path)

    def set_context_menu_callback(self, callback):
        self.context_menu_callback = callback

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
        else:
            self._widget.unset_rows_drag_dest()

    def on_row_expanded(self, widget, iter, path):
        self.emit('row-expanded', iter)

    def on_row_collapsed(self, widget, iter, path):
        self.emit('row-collapsed', iter)

    def on_selection_changed(self, selection):
        if not self.ignore_selection_changed:
            self.emit('selection-changed')

    def on_row_inserted(self, model, path, iter):
        if self.hotspot_tracker:
            self.hotspot_tracker.redraw_cell(self._widget)
            self.hotspot_tracker = None

    def on_row_deleted(self, model, path):
        if self.hotspot_tracker:
            self.hotspot_tracker.redraw_cell(self._widget)
            self.hotspot_tracker = None

    def on_row_changed(self, model, path, iter):
        if self.hotspot_tracker:
            self.hotspot_tracker.update_hit()

    def on_button_press(self, treeview, event):
        if event.type == gtk.gdk._2BUTTON_PRESS:
            path_info = treeview.get_path_at_pos(int(event.x), int(event.y))
            if path_info is not None:
                iter = treeview.get_model().get_iter(path_info[0])
                self.emit('row-double-clicked', iter)
            return

        if self.hotspot_tracker is None:
            hotspot_tracker = HotspotTracker(treeview, event)
            if hotspot_tracker.hit:
                self.hotspot_tracker = hotspot_tracker
                hotspot_tracker.redraw_cell()
                return True
        if event.window != treeview.get_bin_window():
            # click is outsite the content area, don't try to handle this.  
            # In particular, our DnD code messes up resizing table columns.
            return
        if event.button == 1:
            self.drag_button_down = True
            self.drag_start_x = int(event.x)
            self.drag_start_y = int(event.y)
        elif event.button == 3 and self.context_menu_callback:
            path_info = treeview.get_path_at_pos(int(event.x), int(event.y))
            if path_info is not None:
                path, column, x, y = path_info
                selection = self._widget.get_selection()
                if not selection.path_is_selected(path):
                    self.ignore_selection_changed = True
                    selection.unselect_all()
                    self.ignore_selection_changed = False
                    selection.select_path(path)
                menu = self.make_context_menu()
                menu.popup(None, None, None, event.button, event.time)
            return True

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
                        submenu = gen_menu(callback)
                        item.set_submenu(gen_menu(callback))
                    else:
                        item.connect('activate', self.on_context_menu_activate,
                                     callback)
                menu.append(item)
                item.show()
            return menu

        return gen_menu(self.context_menu_callback(self))

    def on_context_menu_activate(self, item, callback):
        callback()

    def on_button_release(self, treeview, event):
        hotspot_tracker = self.hotspot_tracker
        if hotspot_tracker and event.button == hotspot_tracker.button:
            hotspot_tracker.update_position(event)
            hotspot_tracker.update_hit()
            if hotspot_tracker.hit:
                self.emit('hotspot-clicked', hotspot_tracker.name,
                        hotspot_tracker.iter)
            hotspot_tracker.redraw_cell()
            self.hotspot_tracker = None
            return True
        if event.button == 1:
            self.drag_button_down = False

    def _redraw_cell(self, path, column):
        cell_area = self._widget.get_cell_area(path, column)
        self._widget.queue_draw_area(cell_area.x, cell_area.y,
                cell_area.width, cell_area.height)

    def _update_hover(self, treeview, event):
        old_hover_info = self.hover_info
        path_info = treeview.get_path_at_pos(int(event.x), int(event.y))
        if path_info is None:
            self.hover_info = None
        else:
            self.hover_info = path_info[:2]
        if old_hover_info != self.hover_info:
            if old_hover_info is not None:
                self._redraw_cell(*old_hover_info)
            if self.hover_info is not None:
                self._redraw_cell(*self.hover_info)

    def on_motion_notify(self, treeview, event):
        self._update_hover(treeview, event)

        if self.hotspot_tracker:
            self.hotspot_tracker.update_position(event)
            self.hotspot_tracker.update_hit()
            return True

        if (self.drag_button_down and 
                self.drag_source and
                treeview.drag_check_threshold(self.drag_start_x,
                    self.drag_start_y, int(event.x), int(event.y))):
            model, row_paths = treeview.get_selection().get_selected_rows()
            rows = [model[path] for path in row_paths]
            drag_data = self.drag_source.begin_drag(self, rows)
            if drag_data is None:
                return True
            self.drag_data = drag_data
            treeview.drag_begin(gtk_target_list(self.drag_data.keys()),
                    self.drag_source.allowed_actions(), 1, event)

    def on_drag_data_get(self, treeview, context, selection, info, timestamp):
        if self.drag_data:
            for type, data in self.drag_data.items():
                selection.set(type, 8, data)

    def on_drag_end(self, treeview, context):
        self.drag_data = None

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
        model = self.model._model
        try:
            gtk_path, gtk_position = self._widget.get_dest_row_at_pos(x, y)
        except TypeError:
            # Below the last row
            yield (None, len(model), None, None)
            return

        iter = model.get_iter(gtk_path)
        if gtk_position in (gtk.TREE_VIEW_DROP_INTO_OR_BEFORE,
                gtk.TREE_VIEW_DROP_INTO_OR_AFTER):
            yield (iter, -1, gtk_path, gtk_position)

        parent_iter = model.iter_parent(iter)
        position = gtk_path[-1]
        if gtk_position in (gtk.TREE_VIEW_DROP_BEFORE,
                gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
            # gtk gave us a "before" postion, no need to change it
            yield (parent_iter, position, gtk_path, gtk.TREE_VIEW_DROP_BEFORE)
        else:
            # gtk gave us an "after" postion, translate that to before the
            # next row for miro.
            if (self._widget.row_expanded(gtk_path) and
                    model.iter_has_child(iter)):
                child_path = gtk_path + (0,)
                yield (iter, 0, child_path, gtk.TREE_VIEW_DROP_BEFORE)
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
        drag_context.drag_status(drop_action, timestamp)
        return True

    def set_drag_dest_row(self, path, position):
        self._widget.set_drag_dest_row(path, position)

    def on_drag_leave(self, treeview, drag_context, timestamp):
        treeview.unset_drag_dest_row()

    def on_drag_data_received(self, treeview, drag_context, x, y, selection, 
            info, timestamp):
        if not self.drag_dest:
            return
        type = self.find_type(drag_context)
        if type == "NONE":
            return
        drop_action = 0
        for pos_info in self.calc_positions(x, y):
            drop_action = self.drag_dest.validate_drop(self, self.model, type, 
                    drag_context.actions, pos_info[0], pos_info[1])
            if drop_action:
                self.drag_dest.accept_drop(self, self.model, type,
                        drag_context.actions, pos_info[0], pos_info[1],
                        selection.data)
                return True
        return False

    def model_changed(self):
        pass # This gets automatically handled in GTK

    def get_left_offset(self):
        return self._widget.get_left_offset()

class TableModel(object):
    """https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPITableView"""
    MODEL_CLASS = gtk.ListStore

    def __init__(self, *column_types):
        self._model = self.MODEL_CLASS(*self.map_types(column_types))
        self._column_types = column_types

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

    def convert_value_for_gtk(self, column_value):
        if isinstance(column_value, Image):
            return column_value.pixbuf
        else:
            return column_value

    def convert_for_gtk(self, column_values):
        return tuple(self.convert_value_for_gtk(c) for c in column_values)

    def append(self, *column_values):
        return self._model.append(self.convert_for_gtk(column_values))

    def update_value(self, iter, index, value):
        self._model.set(iter, index, self.convert_value_for_gtk(value))

    def update(self, iter, *column_values):
        self._model[iter] = self.convert_for_gtk(column_values)

    def remove(self, iter):
        if self._model.remove(iter):
            return iter
        else:
            return None

    def insert_before(self, iter, *column_values):
        row = self.convert_value_for_gtk(column_values)
        return self._model.insert_before(iter, row)

    def first_iter(self):
        return self._model.get_iter_first()

    def next_iter(self, iter):
        return self._model.iter_next(iter)

    def nth_iter(self, index):
        return self._model.iter_nth_child(None, index)

    def __iter__(self):
        return iter(self._model)

    def __len__(self):
        return len(self._model)

    def __getitem__(self, iter):
        return self._model[iter]

class TreeTableModel(TableModel):
    """https://develop.participatoryculture.org/trac/democracy/wiki/WidgetAPITableView"""
    MODEL_CLASS = gtk.TreeStore

    def append(self, *column_values):
        return self._model.append(None, self.convert_for_gtk(column_values))

    def insert_before(self, iter, *column_values):
        parent = self._model.iter_parent(iter)
        row = self.convert_for_gtk(column_values)
        return self._model.insert_before(parent, iter, row)

    def append_child(self, iter, *column_values):
        return self._model.append(iter, self.convert_for_gtk(column_values))

    def child_iter(self, iter):
        return self._model.iter_children(iter)

    def nth_child_iter(self, iter, index):
        return self._model.iter_nth_child(iter, index)

    def has_child(self, iter):
        return self._model.iter_has_child(iter)

    def children_count(self, iter):
        return self._model.iter_n_children(iter)

    def parent_iter(self, iter):
        return self._model.iter_parent(iter)
