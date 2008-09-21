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

"""cellpack.py -- Code to layout CustomTableCells.

We use the hbox/vbox model to lay things out with a couple changes.  The main
difference here is that layouts are one-shot.  We don't keep state around
inside the cell renderers, so we just set up the objects at the start, then
use them to calculate info.
"""

class Margin(object):
    """Helper object used to calculate margins."""
    def __init__(self , margin):
        if margin is None:
            margin = (0, 0, 0, 0)
        self.margin_left = margin[3]
        self.margin_top = margin[0]
        self.margin_width = margin[1] + margin[3]
        self.margin_height = margin[0] + margin[2]

    def inner_rect(self, x, y, width, height):
        return (x + self.margin_left,
                y + self.margin_top,
                width - self.margin_width,
                height - self.margin_height)

    def outer_size(self, inner_size):
        return (inner_size[0] + self.margin_width,
                inner_size[1] + self.margin_height)

    def point_in_margin(self, x, y, width, height):
        return ((0 <= x - self.margin_left < width - self.margin_width) and
                (0 <= y  - self.margin_top < height - self.margin_height))

class Packing(object):
    """Helper object used to layout Boxes."""
    def __init__(self, child, expand):
        self.child = child
        self.expand = expand

    def calc_size(self, translate_func):
        return translate_func(*self.child.get_size())

    def draw(self, context, x, y, width, height):
        self.child.draw(context, x, y, width, height)

class WhitespacePacking(object):
    """Helper object used to layout Boxes."""
    def __init__(self, size, expand):
        self.size = size
        self.expand = expand

    def calc_size(self, translate_func):
        return self.size, 0

    def draw(self, context, x, y, width, height):
        pass

class Packer(object):
    """Base class packing objects.  Packer objects work similarly to widgets,
    but they only used in custom cell renderers so there's a couple
    differences.  The main difference is that cell renderers don't keep state
    around.  Therefore Packers just get set up, used, then discarded.
    Also Packers can't recieve events directly, so they have a different
    system to figure out where mouse clicks happened (the Hotspot class).
    """

    def render_layout(self, context):
        """position the child elements then call draw() on them."""
        self._layout(context, 0, 0, context.width, context.height)

    def draw(self, context, x, y, width, height):
        """Included so that Packer objects have a draw() method that matches
        ImageSurfaces, TextBoxes, etc.
        """
        self._layout(context, x, y, width, height)

    def get_size(self):
        """Get the minimum size required to hold the Box.  """
        try:
            return self._size
        except AttributeError:
            self._size = self._calc_size()
            return self._size

    def find_hotspot(self, x, y, width, height):
        """Find the hotspot at (x, y).  width and height are the size of the
        cell this Packer is rendering.

        If a hotspot is found, return the tuple (name, x, y, width, height)
        where name is the name of the hotspot, x, y is the position relative
        to the top-left of the hotspot area and width, height are the
        dimensions of the hotspot.

        If no Hotspot is found return None.
        """
        child_pos = self._find_child_at(x, y, width, height)
        if child_pos:
            child, child_x, child_y, child_width, child_height = child_pos
            try:
                return child.find_hotspot(x - child_x, y - child_y,
                        child_width, child_height)
            except AttributeError:
                pass # child is a TextBox, Button or something like that
        return None

    def _layout(self):
        """Layout our children and call draw() on them.  """
        raise NotImplementedError()

    def _calc_size(self):
        """Calculate the size needed to hold the box.  The return value gets
        cached and return in get_size().
        """
        raise NotImplementedError()

class Box(Packer):
    """Box is the base class for VBox and HBox.  Box objects lay out children
    linearly either left to right or top to bottom.
    """

    def __init__(self, spacing=0):
        """Create a new Box.  spacing is the amount of space to place
        in-between children.
        """
        self.spacing = spacing
        self.children = []
        self.expand_count = 0

    def pack(self, child, expand=False):
        """Add a new child to the box.  The child will be placed after all the
        children packed before with pack_start.  Arguments:
        
        child -- child to pack.  It can be anything with a get_size() method,
            including TextBoxes, ImageSurfarces, Buttons, Boxes and
            Backgrounds.
        expand -- If True, then the child will enlarge if space available is
            more than the space required.
        """
        if not (hasattr(child, 'draw') and hasattr(child, 'get_size')):
            raise TypeError("%s can't be drawn" % child)
        self.children.append(Packing(child, expand))
        if expand:
            self.expand_count += 1

    def pack_space(self, size, expand=False):
        """Pack whitespace into the box."""
        self.children.append(WhitespacePacking(size, expand))
        if expand:
            self.expand_count += 1

    def _calc_size(self):
        length = 0
        breadth = 0 
        for packing in self.children:
            child_length, child_breadth = packing.calc_size(self._translate)
            length += child_length
            breadth = max(breadth, child_breadth)
        length += self.spacing * len(self.children)
        return self._translate(length, breadth)

    def _extra_space_iter(self, total_extra_space):
        """Generate the amount of extra space for children with expand set."""
        if total_extra_space <= 0:
            while True:
                yield 0
        extra_space, leftover = divmod(total_extra_space, self.expand_count)
        while leftover > 1:
            yield extra_space + 1
            leftover -= 1
        yield extra_space + leftover
        while True:
            yield extra_space

    def _position_children(self, total_length):
        my_length, my_breadth = self._translate(*self.get_size())
        extra_space_iter = self._extra_space_iter(total_length - my_length)

        pos = 0
        for packing in self.children:
            child_length, child_breadth = packing.calc_size(self._translate)
            if packing.expand:
                child_length += extra_space_iter.next()
            yield packing, pos, child_length
            pos += child_length + self.spacing

    def _layout(self, context, x, y, width, height):
        total_length, total_breadth = self._translate(width, height)
        pos, offset = self._translate(x, y)
        position_iter = self._position_children(total_length)
        for packing, child_pos, child_length in position_iter:
            x, y = self._translate(pos + child_pos, offset)
            width, height = self._translate(child_length, total_breadth)
            packing.draw(context, x, y, width, height)

    def _find_child_at(self, x, y, width, height):
        total_length, total_breadth = self._translate(width, height)
        pos, offset = self._translate(x, y)
        position_iter = self._position_children(total_length)
        for packing, child_pos, child_length in position_iter:
            if child_pos <= pos < child_pos + child_length:
                x, y = self._translate(child_pos, 0)
                width, height = self._translate(child_length, total_breadth)
                return packing.child, x, y, width, height
            elif child_pos > pos:
                break
        return None

    def _translate(self, x, y):
        """Translate (x, y) coordinates into (length, breadth) and
        vice-versa.
        """
        raise NotImplementedError()

class HBox(Box):
    def _translate(self, x, y):
        return x, y

class VBox(Box):
    def _translate(self, x, y):
        return y, x

class Table(Packer):
    def __init__(self, row_length=1, col_length=1,
                 row_spacing=0, col_spacing=0):
        """
        Create a new Table.

        Args:
          row_length: how many rows long this should be
          col_length: how many rows wide this should be
          row_spacing: amount of spacing (in pixels) between rows
          col_spacing: amount of spacing (in pixels) between columns
        """
        assert min(row_length, col_length) > 0
        assert isinstance(row_length, int) and isinstance(col_length, int)
        self.row_length = row_length
        self.col_length = col_length
        self.row_spacing = row_spacing
        self.col_spacing = col_spacing
        self.table_multiarray = self._generate_table_multiarray()

    def _generate_table_multiarray(self):
        table_multiarray = []
        row_count = 0
        table_multiarray = [
            [None for col in range(self.col_length)]
            for row in range(self.row_length)]
        return table_multiarray

    def pack(self, child, row, column, expand=False):
        # TODO: flesh out "expand" ability, maybe?
        #
        # possibly throw a special exception if outside the range.
        # For now, just allowing an IndexError to be thrown.
        self.table_multiarray[row][column] = Packing(child, expand)
    
    def _get_grid_sizes(self):
        """
        Get the width and eights for both rows and columns
        """
        row_sizes = {}
        col_sizes = {}
        for row_count, row in enumerate(self.table_multiarray):
            row_sizes.setdefault(row_count, 0)
            for col_count, col_packing in enumerate(row):
                col_sizes.setdefault(col_count, 0)
                if col_packing:
                    x, y = col_packing.calc_size(self._translate)
                    if y > row_sizes[row_count]:
                        row_sizes[row_count] = y
                    if x > col_sizes[col_count]:
                        col_sizes[col_count] = x
        return col_sizes, row_sizes

    def _find_child_at(self, x, y, width, height):
        col_sizes, row_sizes = self._get_grid_sizes()
        row_distance = 0
        for row_count, row in enumerate(self.table_multiarray):
            col_distance = 0
            for col_count, packing in enumerate(row):
                child_width, child_height = packing.calc_size(self._translate)
                if packing.child:
                    if (col_distance <= x < col_distance + child_width
                            and row_distance <= y < row_distance + child_height):
                        return (packing.child,
                                col_distance, row_distance,
                                child_width, child_height)
                col_distance += col_sizes[col_count] + self.col_spacing
            row_distance += row_sizes[row_count] + self.row_spacing

    def _calc_size(self):
        col_sizes, row_sizes = self._get_grid_sizes()
        x = sum(col_sizes.values()) + ((self.col_length - 1) * self.col_spacing)
        y = sum(row_sizes.values()) + ((self.row_length - 1) * self.row_spacing)
        return x, y
        
    def _layout(self, context, x, y, width, height):
        col_sizes, row_sizes = self._get_grid_sizes()
  
        row_distance = 0
        for row_count, row in enumerate(self.table_multiarray):
            col_distance = 0
            for col_count, packing in enumerate(row):
                if packing:
                    child_width, child_height = packing.calc_size(self._translate)
                    packing.child.draw(context,
                                       x + col_distance, y + row_distance,
                                       child_width, child_height)
                col_distance += col_sizes[col_count] + self.col_spacing
            row_distance += row_sizes[row_count] + self.row_spacing

    def _translate(self, x, y):
        return x, y


class Alignment(Packer):
    """Positions a child inside a larger space.  """
    def __init__(self, child, xscale=1.0, yscale=1.0, xalign=0.0, yalign=0.0,
            min_width=0, min_height=0):
        self.child = child
        self.xscale = xscale
        self.yscale = yscale
        self.xalign = xalign
        self.yalign = yalign
        self.min_width = min_width
        self.min_height = min_height

    def _calc_size(self):
        width, height = self.child.get_size()
        return max(self.min_width, width), max(self.min_height, height)

    def _calc_child_position(self, width, height):
        req_width, req_height = self.child.get_size()
        child_width = req_width + self.xscale * (width-req_width)
        child_height = req_height + self.yscale * (height-req_height)
        child_x = round(self.xalign * (width - child_width))
        child_y = round(self.yalign * (height - child_height))
        return child_x, child_y, child_width, child_height

    def _layout(self, context, x, y, width, height):
        child_x, child_y, child_width, child_height = \
                self._calc_child_position(width, height)
        self.child.draw(context, x + child_x, y + child_y, child_width,
                child_height)

    def _find_child_at(self, x, y, width, height):
        child_x, child_y, child_width, child_height = \
                self._calc_child_position(width, height)
        if ((child_x <= x < child_x + child_width) and
                (child_y <= y < child_y + child_height)):
            return self.child, child_x, child_y, child_width, child_height
        else:
            return None # (x, y) is in the empty space around child

class DrawingArea(Packer):
    """Area that uses custom drawing code."""
    def __init__(self, width, height, callback, *args):
        self.width = width
        self.height = height
        self.callback_info = (callback, args)

    def _calc_size(self):
        return self.width, self.height

    def _layout(self, context, x, y, width, height):
        callback, args = self.callback_info
        callback(context, x, y, width, height, *args)

    def _find_child_at(self, x, y, width, height):
        return None

class Background(Packer):
    """Draws a background behind a child element."""
    def __init__(self, child, min_width=0, min_height=0, margin=None):
        self.child = child
        self.min_width = min_width
        self.min_height = min_height
        self.margin = Margin(margin)
        self.callback_info = None

    def set_callback(self, callback, *args):
        self.callback_info = (callback, args)

    def _calc_size(self):
        width, height = self.child.get_size()
        width = max(self.min_width, width)
        height = max(self.min_height, height)
        return self.margin.outer_size((width, height))

    def _layout(self, context, x, y, width, height):
        if self.callback_info:
            callback, args = self.callback_info
            callback(context, x, y, width, height, *args)
        self.child.draw(context, *self.margin.inner_rect(x, y, width, height))

    def _find_child_at(self, x, y, width, height):
        if not self.margin.point_in_margin(x, y, width, height):
            return None
        return (self.child,) + self.margin.inner_rect(0, 0, width, height)

class Padding(Packer):
    """Adds padding to the edges of a packer."""
    def __init__(self, child, top=0, right=0, bottom=0, left=0):
        self.child = child
        self.margin = Margin((top, right, bottom, left))

    def _calc_size(self):
        return self.margin.outer_size(self.child.get_size())

    def _layout(self, context, x, y, width, height):
        self.child.draw(context, *self.margin.inner_rect(x, y, width, height))

    def _find_child_at(self, x, y, width, height):
        if not self.margin.point_in_margin(x, y, width, height):
            return None
        return (self.child,) + self.margin.inner_rect(0, 0, width, height)

class TextBoxPacker(Packer):
    """Base class for ClippedTextLine and ClippedTextBox"""
    def _layout(self, context, x, y, width, height):
        self.textbox.draw(context, x, y, width, height)

    def _find_child_at(self, x, y, width, height):
        # We could return the TextBox here, but we know it doesn't have a 
        # find_hotspot() method
        return None 

class ClippedTextBox(TextBoxPacker):
    """A TextBox that gets clipped if it's larger than it's allocated
    width.
    """

    def __init__(self, textbox, min_width=0, min_height=0):
        self.textbox = textbox
        self.min_width = min_width
        self.min_height = min_height

    def _calc_size(self):
        height = max(self.min_height, self.textbox.font.line_height())
        return self.min_width, height

class ClippedTextLine(TextBoxPacker):
    """A single line of text that gets clipped if it's larger than the
    space allocated to it.  By default the clipping will happen at character
    boundaries.
    """

    def __init__(self, textbox, min_width=0):
        self.textbox = textbox
        self.textbox.set_wrap_style('char')
        self.min_width = min_width

    def _calc_size(self):
        return self.min_width, self.textbox.font.line_height()

class TruncatedTextLine(ClippedTextLine):
    def __init__(self, textbox, min_width=0):
        ClippedTextLine.__init__(self, textbox, min_width)
        self.textbox.set_wrap_style('truncated-char')

class Hotspot(Packer):
    """A Hotspot handles mouse click tracking.  It's only purpose is to store
    a name to return from find_hotspot().  In terms of layout, it simply
    renders it's child in it's allocated space.
    """

    def __init__(self, name, child):
        self.name = name
        self.child = child

    def _calc_size(self):
        return self.child.get_size()

    def _layout(self, context, x, y, width, height):
        self.child.draw(context, x, y, width, height)

    def find_hotspot(self, x, y, width, height):
        return self.name, x, y, width, height

def align_left(packer):
    """Align a packer to the left side of it's allocated space."""
    return Alignment(packer, xalign=0.0, xscale=0.0)

def align_right(packer):
    """Align a packer to the right side of it's allocated space."""
    return Alignment(packer, xalign=1.0, xscale=0.0)

def align_top(packer):
    """Align a packer to the top side of it's allocated space."""
    return Alignment(packer, yalign=0.0, yscale=0.0)

def align_bottom(packer):
    """Align a packer to the bottom side of it's allocated space."""
    return Alignment(packer, yalign=1.0, yscale=0.0)

def align_middle(packer):
    """Align a packer to the middle of it's allocated space."""
    return Alignment(packer, yalign=0.5, yscale=0.0)

def align_center(packer):
    """Align a packer to the center of it's allocated space."""
    return Alignment(packer, xalign=0.5, xscale=0.0)

def pad(packer, top=0, left=0, bottom=0, right=0):
    """Add padding to a packer."""
    return Padding(packer, top, right, bottom, left)
