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

"""GTK Hacks.  GTK Code that can't be done in PyGTK for whatever reason."""

cdef extern from "gtk/gtk.h":
    ctypedef int gint
    ctypedef unsigned long gulong
    ctypedef unsigned int guint
    ctypedef unsigned short gboolean
    ctypedef char gchar
    ctypedef void * gpointer
    ctypedef void * GCallback
    ctypedef struct GtkWidget
    ctypedef struct GtkTreeView
    ctypedef struct GtkTreePath
    ctypedef struct GtkEntry
    ctypedef struct GObject
    ctypedef struct GtkTooltip
    ctypedef struct GtkBorder:
        gint left
        gint right
        gint top
        gint bottom
    ctypedef enum GtkTreeViewDropPosition:
            GTK_TREE_VIEW_DROP_BEFORE,
            GTK_TREE_VIEW_DROP_AFTER,
            GTK_TREE_VIEW_DROP_INTO_OR_BEFORE,
            GTK_TREE_VIEW_DROP_INTO_OR_AFTER
    cdef void gtk_tree_view_set_drag_dest_row(GtkTreeView *tree_view,
                                         GtkTreePath *path,
                                         GtkTreeViewDropPosition pos)
    cdef void gtk_entry_set_inner_border (GtkEntry        *entry,
                                     GtkBorder *border)
    cdef void gtk_entry_set_text (GtkEntry        *entry,
                                     char* text)
    cdef void gtk_tooltip_set_text (GtkTooltip  *tooltip, char *text)

cdef extern from "gdk/gdk.h":
    ctypedef struct GdkWindow
    ctypedef struct GdkDrawable

    void gdk_window_get_internal_paint_info (GdkWindow *window,
                                             GdkDrawable **real_drawable,
                                             gint *x_offset,
                                             gint *y_offset)
    gboolean gdk_window_ensure_native (GdkWindow *window)


cdef extern from "pango/pango.h":
    ctypedef struct PangoLayout
    cdef void pango_layout_set_height(PangoLayout *layout, int height)

cdef extern from "Python.h":
    ctypedef struct PyObject

cdef extern from "pygobject.h":
    ctypedef struct PyGObject
    cdef PyObject* pygobject_init(int req_major, int req_minor, int req_micro)
    cdef GObject* pygobject_get(PyGObject*)

cdef GObject* get_c_gobject(object py_gobject):
    """Get a C GObject pointer from a Python GObject."""
    cdef PyGObject *pygobject
    pygobject = <PyGObject *>py_gobject
    return pygobject_get(pygobject)

def initialize():
    if pygobject_init(-1, -1, -1) == NULL:
        raise ImportError("Can't initialize pygobject")

def unset_tree_view_drag_dest_row(object py_tree_view):
    cdef GtkTreeView* tree_view 
    tree_view = <GtkTreeView*>get_c_gobject(py_tree_view)
    gtk_tree_view_set_drag_dest_row(tree_view, NULL, GTK_TREE_VIEW_DROP_BEFORE)

def set_entry_border(object py_entry, int top, int right, int bottom, int left):
    cdef GtkEntry* entry
    cdef GtkBorder border

    entry = <GtkEntry*>get_c_gobject(py_entry)
    border.left = left
    border.right = right
    border.top = top
    border.bottom = bottom
    gtk_entry_set_inner_border(entry, &border)

def set_tooltip_text(object tooltip, text):
    # For some reason this isn't available on pygtk 2.12.1 for windows, so we
    # have to implement it ourselves.
    cdef GtkTooltip* gtk_tooltip
    gtk_tooltip = <GtkTooltip*>get_c_gobject(tooltip)
    gtk_tooltip_set_text(gtk_tooltip, text)

def set_pango_layout_height(object layout, height):
    cdef PangoLayout* pango_layout
    pango_layout = <PangoLayout*>get_c_gobject(layout)
    pango_layout_set_height(pango_layout, height)

def get_gdk_window_offset(py_gdk_window):
    cdef GdkWindow* window
    cdef GdkDrawable* drawable
    cdef gint x_offset, y_offset

    window = <GdkWindow*>get_c_gobject(py_gdk_window)
    gdk_window_get_internal_paint_info(window, &drawable, &x_offset,
            &y_offset)
    return (x_offset, y_offset)

def ensure_native_window(py_gdk_window):
    cdef GdkWindow* window

    window = <GdkWindow*>get_c_gobject(py_gdk_window)
    return gdk_window_ensure_native(window)
