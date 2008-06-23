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

"""Interfaces for the platform code.

This module exists purely to document what the platform code needs to
implement in terms of widgets.

Platforms must define a module/package called
miro.platform.frontends.widgets.widgets that contains a class that implements
each of these interfaces.  The class name must be the same as the name in this
module.

Platforms don't need to subclass these classes, just implement the interfaces.

Platforms need to provide the following constants:

DRAG_ACTION_MOVE 
DRAG_ACTION_COPY
DRAG_ACTION_LINK
DRAG_ACTION_ALL = (DRAG_ACTION_MOVE | DRAG_ACTION_COPY | DRAG_ACTION_LINK)

"""

class Rect:
    """Represents a rectangle af area on screen.

    Attributes:

    x, y -- position of the rectangle
    width, height -- size of the rectangle
    
    """
    def __init__(self, x, y, width, height):
        pass

class ImageSurface:
    """Represents an image that can be drawn on a DrawingContext().
    
    All image files must be in PNG format.

    Attributes:

    width -- width of the image
    height -- height of the image
    """
    def __init__(self, image):
        """Create a new ImageSurface.  image is an Image object"""

class DrawingContext:
    """Class used to draw things on widgets.  It's a wrapper for Cairo and
    Quartz.

    Attributes:

    width -- width of the area that is drawable.  This can be different from
        the widget's width, for example on GTK it doesn't include space to
        draw the focus box.
    height -- height of the area that is drawable.

    This class basically follows the Cairo API.  If a method isn't documented,
    then it means it works exactly the same as the cairo version.

    Check out the PyCairo tutorial for details:

    http://www.tortall.net/mu/wiki/CairoTutorial

    DrawingContext objects get constructed in a platform-specific way.
    """

    def move_to(self, x, y):
        pass

    def rel_move_to(self, dx, dy):
        pass

    def line_to(self, x, y):
        pass

    def rel_line_to(self, dx, dy):
        pass

    def arc(self, x, y, radius, angle1, angle2):
        pass

    def arc_negative(self, x, y, radius, angle1, angle2):
        pass

    def curve_to(self, x1, y1, x2, y2, x3, y3):
        pass

    def rel_curve_to(self, dx1, dy1, dx2, dy2, dx3, dy3):
        pass

    def rectangle(self, x, y, width, height):
        pass

    def set_source_rgba(self, red, green, blue, alpha):
        pass

    def set_source_rgb(self, red, green, blue):
        pass

    def set_line_width(self, width):
        pass

    def stroke(self):
        pass

    def stroke_preserve(self):
        pass

    def fill(self):
        pass

    def fill_preserve(self):
        pass

    def clip(self):
        pass

    def save(self):
        pass

    def restore(self):
        pass

    def draw_image(self, image, x, y, width, height):
        """Draw an ImageSurface.  (x, y, width, height) define the portion of
        the context to draw on.  If width or height is larger than the images
        width and height the image will be repeated.
        """

    def set_font_bold(self, bold):
        """Sets if the current font is bold or not."""

    def set_font_size(self, size):
        """Sets the current font size in pixels."""

    def set_font_color(self, red, green, blue):
        """Sets the current font color."""

    def draw_text(self, text, x, y, right_align=True, max_width=None):
        """Draw text on the surface.  font_size is measured in points.
        (x, y) specifies the baseline point for the text.  max_width specifies
        the maximum width of the text.  Text will be truncated at character
        boundaries if it exceeds max_width.
        """

    def text_size(self, text):
        """Calculate the size needed to display a string.  """

class Window:
    """Top-level window.

    Signals:

    active-change -- The window has been activated or de-activated

    """

    def __init__(self, title, rect):
        """Create a Window.  Title is the name to give the window, rect
        specifies the position it should have on screen.
        """

    def set_content_widget(self, widget):
        """Set the widget that will be drawn in the content area for this
        window.

        It will be allocated the entire area of the widget, except the space
        needed for the titlebar, frame and other decorations.  When the window
        is resived, content should also be resized.
        """
        pass

    def get_content_widget(self, widget):
        """Get the current content widget."""

    def show(self):
        """Display the window on screen."""

    def close(self):
        pass

    def destroy(self):
        """Close a window and destroy it's resources.  It can't be shown
        again."""

    def is_active(self):
        """Is the window the active?"""

class Dialog:
    """Dialog windows.  

    Dialog windows are windows that display some text to a user and ask them
    to respond.  They contain buttons at the bottom which the user can choose
    from.  Dialogs run modally, meaning only the dialog will recieve user
    input while they are running.  
    """

    def __init__(self, title, description):
        """Create a dialog."""

    def add_button(self, text):
        """Add a new button to the dialog.  Buttons will normally be placed
        starting from the right-hand side of the window.
        """

    def run(self):
        """Run the dialog.  This method will block until the user has clicked
        a button or closed the dialog.  The return value will be the index of
        the button clicked, or -1 if the user closes the dialog.
        """

    def destroy(self):
        """Destroys the dialog."""

    def set_extra_widget(self, widget):
        """Set a widget that will contain extra things to display to the user.
        It will be positioned in between the message text and the buttons.
        """

    def get_extra_widget(self):
        pass

class Widget:
    """Widget base class.

    attributes:

    width -- width of the widget
    height -- height of the widget
    """

    def set_size_request(self, width, height):
        """Set the size that this widget will request from it's container.

        We basically follow the GTK model for laying out widgets.
        set_size_request() sets the minimum size that this widget should have.
        Sometimes it's container will give it more space, in rare cases.
        it might give it less.

        If -1 is given for either value, then the "natural" size will be used,
        meaning the size the widget would have requested if set_size_request()
        wasn't called.
        """

    def get_size_request(self):
        """Get the size request for this widget as the tuple (width, height).  

        If set_size_request() was called, then this should return the value
        passed in to that.  Otherwise the widget should figure out the size
        needed to display it's contents.
        """

    def get_window(self):
        """Returns the window that this widget is in."""

    def queue_draw(self):
        """Mark this widget's area as invalid and cause it to be re-drawn."""

    def relative_position(self, other_widget):
        """Get the position of another widget, relative to this widget."""

class Box(Widget):
    """Simple box-packing widget.   This works like GTK's HBox/VBox
    classes.  Check out the GTK tutorial for how it should act.
    """

    def __init__(self, spacing=0):
        """Construct a Box object.  spacing is the amount of space to put
        inbetween widgets."""

    def pack_start(self, widget, expand=False, padding=0):
        """Add a child widget to this widget."""

    def remove(self, widget):
        """Remove a child widget to this widget."""

class VBox(Box):
    """Verticle box-packing widget.  It's child widgets will be aranged from
    top to bottom.
    """

class HBox(Box):
    """Horizontal box-packing widget.  It's child widgets will be aranged from
    left to right.
    """

class Table(Widget):
    """Lays out widgets in a table.  It works very similar to the GTK Table
    widget, or an HTML table.
    """
    def __init__(self, columns, rows):
        """Create a new Table."""

    def set_cell(self, widget, column, row):
        """Add a widget to the table."""

    def get_cell(self, column, row):
        """Return the widget at (row, column)."""

    def remove(self, child):
        """Remove a child widget."""

    def set_column_spacing(self, spacing):
        """Sets the amount of space that will be added between columns."""

    def set_row_spacing(self, spacing):
        """Sets the amount of space that will be added between rows."""

class Browser(Widget):
    """Web browser widget.  """

    def __init__(self):
        pass

    def navigate(self, url):
        pass

    def get_current_url(self):
        pass

class Bin(Widget):
    """Container Widget that stores exactly 1 child.
    
    Attributes:

    child -- The current child or None
    """

    def add(self, child):
        """Add a new child, if a child has already been added, this method
        throws an exception.
        """

    def remove(self):
        """Remove our current child (if any)."""

    def set_child(self, new_child):
        """Set the current child.  This will remove the current child if there
        is one, then add a new child.
        """

class Alignment(Bin):
    """Alignment widgets are used to position a child widget when it's
    allocated more space than it's requested.  They follow the GTK Alignment
    widget model, check out the GTK tutorial for details on how this should
    work.
    """
    def __init__(self, xalign=0.0, yalign=0.0, xscale=0.0, yscale=0.0,
            top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
        """Create a new alignment."""

    def set(self, xalign=0.0, yalign=0.0, xscale=0.0, yscale=0.0):
        """Change the current alignment values.  the scale values specify what
        portion of the extra space to use.  The align values specify where the
        child widget should be positioned if it uses less space than the
        Alignment is allocated.
        """

    def set_padding(self, top_pad=0, bottom_pad=0, left_pad=0, right_pad=0):
        """Change the padding for this widget.  This will add extra space at
        the edges of the Alignment."""

class Splitter(Widget):
    """Splits the main miro window between the left and right sides.  In
    between is a bar that the user can use to change the portion of space each
    child widget gets.  
    
    What happens when a splitter doesn't have both of it's children set is
    platform-dependant.

    Attributes:

    left -- The left child widget
    right -- The right child widget
    """

    def __init__(self):
        """Create a new spliter."""

    def set_left(self, widget):
        """Set the left child widget."""

    def set_right(self, widget):
        """Set the right child widget.  """

    def remove_left(self):
        """Remove the left child widget."""

    def remove_right(self):
        """Remove the right child widget."""

    def set_left_width(self, width):
        """Set the width of the left side."""

    def set_right_width(self, width):
        """Set the width of the right side."""


class Drawable:
    """Widgets that allow subclasses to customize how their backgrounds get
    drawn.
    """

    def size_request(self):
        """Get the minimum size needed to draw this widget."""

    def draw(self, context):
        """Called when the widget must draw itself.  context is a
        DrawingContext to use. It's (0, 0) coordinate will be the top-left of
        this widget.
        """

    def is_opaque(self):
        """Returns True, if this widget draws on it's entire area.  This is
        used a hint to the widget toolkit to make certain drawing
        optimizations.  By default it is not opaque.
        """

class CustomButton(Widget, Drawable):
    """Custom Button widget.
    
    signals:

    'clicked' -- Emitted when the button is clicked
    """

    def __init__(self):
        """Create a new CustomButton.  """

    def draw_pressed(self, context):
        """Draw the button in it's pressed state."""

class ContinuousCustomButton(CustomButton):
    """Custom Button widget that continuously emits signals.
    
    signals:

    'held-down' -- Emitted when the button is held down.  This will be emitted
        repeatedly while the button is held down.
    """

    def set_delays(self, initial, repeat):
        """Set the amount of time before the held-down signal is emitted.

        initial is the time before the first signal, repeat is the time before
        subsequent signals.

        If this method isn't called, the amount of time is platform-dependant.
        """

class CustomSlider(Widget, Drawable):
    """Custom slider widget.  Used to implement the volume and time
    sliders.

    Signals:

    'changed' -- A new value has been choosen.
    'moved' -- The slider position has moved.  This is different from changed
        if the widget is not continuous.
    """

    def is_horizontal(self):
        """Return if the slider is horizontally oriented
        Must be implemented by subclasses
        """

    def slider_size(self):
        """The size of the slider in pixels.
        
        Must be implemented by subclasses
        """

    def is_continuous(self):
        """Return if this widget is continuous.  If True, it will emit changed
        signals as the user moves the slider.  If False, it will only emit a
        changed signals when the user has let go of the mouse button.

        Must be implemented by subclasses
        """

    def get_value(self):
        """Get the current value for the slider."""

    def set_value(self, value):
        """Set a current value for the slider."""

    def get_range(self):
        """Get the range of values for the slider."""

    def set_range(self, min_value, max_value):
        """Set the range of values for the slider."""

    def set_increments(self, increment, big_increment):
        """Sets the amount the slider changes when the user adjusts it with
        keyboard input.  increment is the standard change, it's usually used
        for the arrow keys.  big_increment is the large change, it's usually
        used with PageUp/PageDown.
        """

class DrawingArea(Widget, Drawable):
    """Widget used to do custom drawing."""

class Background(Bin, Drawable):
    """Like a Drawable, but can contain child widgets."""

class Label(Widget):
    """Widget that displays simple text."""
    def __init__(self, text="", bold=False, wrap=False):
        """Create a label."""

    def set_text(self, text):
        """Change the current text."""

    def get_text(self):
        """Get the current text."""

    def set_wrap(self, wrap):
        """Sets if this widget will word-wrap it's text.  If this wrap is set
        to True, then set_size_request() should be called with a width
        argument, otherwise the widget won't know how to wrap it's text when
        requesting it's size.
        """

class Image(object):
    """Represents an Image that can be displayed onscreen.

    Attributes:

    width -- width of the image
    height -- height of the image
    
    """

    def __init__(self, path):
        pass


class ImageDisplay(Widget):
    """Widget that displays an image."""

    def __init__(self, image):
        pass

class TextEntry(Widget):
    """Widget used it input text."""

    def __init__(self, intial_text=None, hidden=False):
        """Construct a TextEntry.

        hidden specifies if the widget will hide it's value.  It's good for
        passwords.
        """

    def set_text(self, text):
        """Change the current text."""

    def get_text(self, text):
        """Get the current text."""

    def set_width(self, chars):
        """Sets the width that this widget will request, in characters."""

    def set_activates_default(self, setting):
        """Sets if hitting Enter in the entry causes the default action of the
        window to happen.  This basically means in a form, hitting enter will
        click the default button.
        """

class Checkbox(Widget):
    """Widget that the user can toggle on or off."""

    def __init__(self, label):
        """Create a checkbox."""

    def get_checked(self):
        """Get if the check box is checked."""

    def set_checked(self, value):
        """Check/Uncheck the checkbox."""

class CellRenderer(object):
    """Renders simple data for a TableView.  This cell can render text and
    numeric values, but nothing more complicated than that.
    """

class ImageCellRenderer(object):
    """Renders an Image object."""

class CustomCellRenderer(object):
    """Renders data for a TableView in a custom way.  This class is meant to
    be subclassed by the portable code. 

    A single cell renderer is used to render every cell in a column for a
    TableView.  For each row that it renders, the TableView will set an
    attribute called 'data' which will have the data from column in the
    TableModel that this cell is rendering.
    """

    def get_size(self):
        """Return the width and height needed to render this cell."""

    def render(self, context, selected):
        """Render the contents of this cell.  context is a DrawingContext to
        use. It's (0, 0) coordinate will be the top-left of the area allocated
        to this cell.  It's width and height will be the size of the area
        allocated to this cell.
        """


class TableViewDragSource(object):
    """Handles Drag and Drop requests originating from a table."""

    def allowed_actions(self):
        """Returns the types of drags that are allowed.  The return value is
        a bitwise combination of DRAG_ACTION_* constants.
        """

    def allowed_types(self):
        """Returns what type of data can be dragged from the table.  The
        return value is a list of types.  Each type is an is an arbitrary
        string name specifying the type of data.
        """

    def begin_drag(self, table_view, rows):
        """Start a drag operation.  rows is a list containing the column data
        for the current selection.

        This method should return the a dictionary mapping types to data for
        all it's supported drag types.  The data should be python string
        values.
        """

class TableViewDragDest(object):
    """Handles Drag and Drop requests ending on a table."""

    def allowed_actions(self):
        """Returns the types of drags that are allowed.  The return value is
        a bitwise combination of DRAG_ACTION_* constants.
        """

    def allowed_types(self):
        """Returns what type of data can be dropped onto the table.  The types
        should be in preferred order.
        """

    def validate_drop(self, table_view, model, type, source_actions,
            parent_path, position):
        """Called to finish the drag process.  

        type is the type of data being dropped.  source_actions is a bitwise
        combination of DRAG_ACTION_* constants, specifying the actions that
        the drag source allows.
        
        parent_path is the path that points to the parent of the row to be
        dropped on or None if it's a top-level row.  position is the child
        index of parent_path that the dropped data should be placed.  If
        position is -1, which signifies dropping "on top" of the row at
        parent_path.

        validate_drop should return one of the DRAG_ACTION_* constants
        describing what action will be taken.  If the drop should not be
        allowed, validate_drop should return DRAG_ACTION_NONE.
        """

    def accept_drop(self, table_view, model, type, source_actions,
            parent_path, position, data):
        """Called to finish the drag process.    The arguments are identical
        to validate_drop.  In addition, data holds the actual data to be
        dropped.

        accept_drop should return True if the drop was successful, False
        otherwise.
        """

class TableView(Widget):
    """Displays data as a tabular list.  TableView follows the GTK TreeView
    widget fairly closely.

    TableViews should be placed inside a scroll window that automatically
    creates a veritcal scrollbar when enough rows are in the table.

    signals:

    'row-expanded' -- an item was expanded
    'row-collapsed' -- an item was unexpanded
    """

    def __init__(self, model):
        """Create a TableView widget.  model is either TableModel or a
        TreeTableModel object that holds the data for this TableView.
        """

    def add_column(self, title, model_index, renderer, min_width):
        """Add a column to this TableView.  title is the title for the column,
        it's shown in the table headers.  model_index is the index of the
        column in the TreeModel that provides the source of date.  renderer is
        a CellRenderer object.
        """

    def column_count(self):
        """Get the number of columns in this table."""

    def remove_column(self, index):
        """Remove a column from the table."""

    def model_change(self):
        """Must be called after changes are made to the TableView's model.
        This causes the new data to be reloaded.
        
        If you modify the table, it is extremely important you call this
        method or else you can cause a segfault on OSX.  It's probably best
        to put code that modifies the table in a try...finally block to ensure
        that this gets called.
        """

    def set_background_color(self, red, green, blue):
        """Set the background color of the tree view.  red, green and blue
        range from 0.0 to 1.0."""

    def set_show_headers(self, show):
        """Enables/disables displaying the table headers."""

    def set_search_column(self, model_index):
        """Set the search column.  If the user starts typing then we will do
        an incremental search using this column.  Pass in -1 to disable.
        """

    def set_fixed_height(self, height):
        """Set a fixed height for every row in the table.  The table
        can make certain optimizations based on this.  Send in -1 if rows have
        a variable height.
        """

    def allow_multiple_select(self, allow):
        """Sets if multiple rows can be selected."""

    def get_selection(self):
        """Returns the current selection as a list of table paths."""

    def get_selected(self):
        """Returns a row iterator to the currently selected row.  Only works
        when multiple-selection is not allowed
        """

    def set_row_expanded(self, path, expanded):
        """Changes if a row is expanded."""

    def is_row_expanded(self, path):
        """Check if a row is expanded."""

    def set_drag_source(self, drag_source):
        """Sets the TableViewDragSource for this table."""

    def set_drag_dest(self, drag_dest):
        """Sets the TableViewDragDest for this table."""

    def iter_ordering(self, iter):
        """Given a row iterator, return a value that can be used to order it.
        The type of the return value is undefined, but it is guaranteed to be
        less than the values return for rows after iter and more than the
        values return for rows before iter.
        """

class TableModel(object):
    """Stores data for a TableView widget.  This class stores data as a simple
    list, TreeTableModel extends it to support hierarchical data.

    When specifying a position in the table, a "row path" is used.  Row paths
    work very similaryly to GTKTreePath objects.  They are tuples containing
    indexes to levels in the hierarchy.  (5,) refers to the 6th top-level row
    in the table.  (5,2,3) refers to the 4th child of the 3rd child of the 6th
    top-level row.

    Table models support a list-like interface.  model[path] will return the
    row for that path, len(model) will return the number of top-level rows
    and for row in model can be used to iterate over the top-level row paths.
    """

    def __init__(self, *column_types):
        """Create a new TableTreeModel.  column types is an list specifying
        the type of data in this TableModel.  Note that the order of columns
        in the model does not have to line up with the order displayed in the
        TableView.

        column types should be one of the following:

        'numeric' -- Numeric data
        'image' -- Image data (an Image object)
        'text' -- Text data
        'datetime' -- Datetime data
        'object' -- A Python object
        """

    def append(self, *column_values):
        """Append a row.  Returns the path for the new row.  """

    def update(self, path, *column_values):
        """Update a row in the table."""

    def remove(self, path):
        """Remove a row from the table."""

    def insert_before(self, path, *column_values):
        """Insert a row in the middle of the table.  Returns the path for the
        new row."""

    def next_path(self, path):
        """Returns the path for the row following path, or None if there are
        no more rows.
        """

    def first_path(self):
        """Get the path of the first row in the list or None if there are no
        rows."""

class TreeTableModel(TableModel):
    """Stores data for a TableView widget that is organized in a hierarchical
    fashion.

    For TreeTableModels, append() adds the object at the root level of the
    tree,  insert_before() adds the object at the same level in the hierarchy,
    next_path() returns a paths for rows at the same level as path.
    """

    def append_child(self, path, *column_values):
        """Add a new row to this model as a child of another row.  If path is
        None, the child will be appended to the bottom of the list.  Returns
        the path of the new row.
        """

    def child_path(self, path):
        """Returns the path of the first child of a row, or None if the row
        has no children.
        """

    def nth_child_path(self, path, index):
        """Returns the nth child of path.  If path is None, it will return the
        nth toplevel path.
        """

    def has_child(self, path):
        """Returns True if the a path has children."""

    def children_count(self, path):
        """Returns the number of children of a row.  If path is None, then it
        will return the number of toplevel rows.
        """

    def children_paths(self, path):
        """Returns the paths to all of the children for a row as a list."""

    def parent_path(self, path):
        """Returns the path of the parent of a row, or None if it's a toplevel
        row.
        """
