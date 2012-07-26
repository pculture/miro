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

"""tableviewcells.py - Cell renderers for TableView."""

import gobject
import gtk
import pango

from miro import signals
from miro import infolist
from miro.frontends.widgets import widgetconst
from miro.frontends.widgets.gtk import drawing
from miro.frontends.widgets.gtk import wrappermap
from miro.frontends.widgets.gtk.base import make_gdk_color

class CellRenderer(object):
    """Simple Cell Renderer
    https://develop.participatoryculture.org/index.php/WidgetAPITableView"""
    def __init__(self):
        self._renderer = self.build_renderer()
        self.want_hover = False

    def build_renderer(self):
        return gtk.CellRendererText()

    def setup_attributes(self, column, attr_map):
        column.add_attribute(self._renderer, 'text', attr_map['value'])

    def set_align(self, align):
        if align == 'left':
            self._renderer.props.xalign = 0.0
        elif align == 'center':
            self._renderer.props.xalign = 0.5
        elif align == 'right':
            self._renderer.props.xalign = 1.0
        else:
            raise ValueError("unknown alignment: %s" % align)

    def set_color(self, color):
        self._renderer.props.foreground_gdk = make_gdk_color(color)

    def set_bold(self, bold):
        font_desc = self._renderer.props.font_desc
        if bold:
            font_desc.set_weight(pango.WEIGHT_BOLD)
        else:
            font_desc.set_weight(pango.WEIGHT_NORMAL)
        self._renderer.props.font_desc = font_desc

    def set_text_size(self, size):
        if size == widgetconst.SIZE_NORMAL:
            self._renderer.props.scale = 1.0
        elif size == widgetconst.SIZE_SMALL:
            # FIXME: on 3.5 we just ignored the call.  Always setting scale to
            # 1.0 basically replicates that behavior, but should we actually
            # try to implement the semantics of SIZE_SMALL?
            self._renderer.props.scale = 1.0
        else:
            raise ValueError("unknown size: %s" % size)

    def set_font_scale(self, scale_factor):
        self._renderer.props.scale = scale_factor

class ImageCellRenderer(CellRenderer):
    """Cell Renderer for images
    https://develop.participatoryculture.org/index.php/WidgetAPITableView"""
    def build_renderer(self):
        return gtk.CellRendererPixbuf()

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
    https://develop.participatoryculture.org/index.php/WidgetAPITableView"""
    def __init__(self):
        signals.SignalEmitter.__init__(self)
        self.create_signal("clicked")
        self._renderer = GTKCheckboxCellRenderer()
        wrappermap.add(self._renderer, self)
        self.want_hover = False

    def set_control_size(self, size):
        pass

    def setup_attributes(self, column, attr_map):
        column.add_attribute(self._renderer, 'active', attr_map['value'])

class GTKCustomCellRenderer(gtk.GenericCellRenderer):
    """Handles the GTK hide of CustomCellRenderer
    https://develop.participatoryculture.org/index.php/WidgetAPITableView"""

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
        widget_wrapper = wrappermap.wrapper(widget)
        cell_wrapper = wrappermap.wrapper(self)

        selected = (flags & gtk.CELL_RENDERER_SELECTED)
        if selected:
            if widget.flags() & gtk.HAS_FOCUS:
                state = gtk.STATE_SELECTED
            else:
                state = gtk.STATE_ACTIVE
        else:
            state = gtk.STATE_NORMAL
        if cell_wrapper.IGNORE_PADDING:
            area = background_area
        else:
            xpad = self.props.xpad
            ypad = self.props.ypad
            area = gtk.gdk.Rectangle(cell_area.x + xpad, cell_area.y + ypad,
                    cell_area.width - xpad * 2, cell_area.height - ypad * 2)
        context = drawing.DrawingContext(window, area, expose_area)
        if (selected and not widget_wrapper.draws_selection and
                widget_wrapper.use_custom_style):
            # Draw the base color as our background.  This erases the gradient
            # that GTK draws for selected items.
            window.draw_rectangle(widget.style.base_gc[state], True,
                    background_area.x, background_area.y,
                    background_area.width, background_area.height)
        context.style = drawing.DrawingStyle(widget_wrapper,
                use_base_color=True, state=state)
        widget_wrapper.layout_manager.update_cairo_context(context.context)
        hotspot_tracker = widget_wrapper.hotspot_tracker
        if (hotspot_tracker and hotspot_tracker.hit and
                hotspot_tracker.column == self.column and
                hotspot_tracker.path == self.path):
            hotspot = hotspot_tracker.name
        else:
            hotspot = None
        if (self.path, self.column) == widget_wrapper.hover_info:
            hover = widget_wrapper.hover_pos
            hover = (hover[0] - xpad, hover[1] - ypad)
        else:
            hover = None
        # NOTE: CustomCellRenderer.cell_data_func() sets up its attributes
        # from the model itself, so we don't have to worry about setting them
        # here.
        widget_wrapper.layout_manager.reset()
        cell_wrapper.render(context, widget_wrapper.layout_manager, selected,
                hotspot, hover)

    def on_activate(self, event, widget, path, background_area, cell_area,
            flags):
        pass

    def on_start_editing(self, event, widget, path, background_area,
            cell_area, flags):
        pass
gobject.type_register(GTKCustomCellRenderer)

class CustomCellRenderer(CellRenderer):
    """Customizable Cell Renderer
    https://develop.participatoryculture.org/index.php/WidgetAPITableView"""

    IGNORE_PADDING = False

    def __init__(self):
        CellRenderer.__init__(self)
        wrappermap.add(self._renderer, self)

    def build_renderer(self):
        return GTKCustomCellRenderer()

    def setup_attributes(self, column, attr_map):
        column.set_cell_data_func(self._renderer, self.cell_data_func,
                attr_map)

    def cell_data_func(self, column, cell, model, iter, attr_map):
        cell.column = column
        cell.path = model.get_path(iter)
        row = model[iter]
        # Set attributes on self instead cell This works because cell is just
        # going to turn around and call our methods to do the rendering.
        for name, index in attr_map.items():
            setattr(self, name, row[index])

    def hotspot_test(self, style, layout, x, y, width, height):
        return None

class ItemListRenderer(CustomCellRenderer):
    """Custom Renderer for InfoListModels
    https://develop.participatoryculture.org/index.php/WidgetAPITableView"""

    def cell_data_func(self, column, cell, model, it, attr_map):
        item_list = wrappermap.wrapper(model).item_list
        row = model.row_of_iter(it)
        self.info = item_list.get_row(row)
        self.attrs = item_list.get_attrs(self.info.id)
        self.group_info = item_list.get_group_info(row)
        cell.column = column
        cell.path = row

class ItemListRendererText(CellRenderer):
    """Renderer for InfoListModels that only display text
    https://develop.participatoryculture.org/index.php/WidgetAPITableView"""

    def setup_attributes(self, column, attr_map):
        column.set_cell_data_func(self._renderer, self.cell_data_func,
                attr_map)

    def cell_data_func(self, column, cell, model, it, attr_map):
        item_list = wrappermap.wrapper(model).item_list
        info = item_list.get_row(model.row_of_iter(it))
        cell.set_property("text", self.get_value(info))

    def get_value(self, info):
        """Get the text to render for this cell

        :param info: ItemInfo to render.
        """
