/*
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
*/

// infolist-gtk.cpp -- GTK code to implement infolist

#include <Python.h>
#include <pygobject.h>
#include <pygtk/pygtk.h>
#include "infolist-nodelist.h"
#include "infolist-gtk.h"

static PyTypeObject *PyGObject_Type=NULL;

static void
miro_list_store_init (MiroListStore *self);

static void
miro_list_store_finalize (GObject *self);

static GtkTreeModelFlags
miro_list_store_get_flags (GtkTreeModel *tree_model);

static gint
miro_list_store_get_n_columns (GtkTreeModel *tree_model);

static GType
miro_list_store_get_column_type (GtkTreeModel *tree_model,
                                 gint index);

static gboolean
miro_list_store_make_iter (GtkTreeModel *tree_model,
                           GtkTreeIter *iter,
                           gint index);

static gboolean
miro_list_store_get_iter (GtkTreeModel *tree_model,
                          GtkTreeIter *iter,
                          GtkTreePath *path);

static GtkTreePath *
miro_list_store_get_path (GtkTreeModel *tree_model,
                          GtkTreeIter *iter);

static void
miro_list_store_get_value (GtkTreeModel *tree_model,
                           GtkTreeIter *iter,
                           gint column,
                           GValue *value);

static gboolean
miro_list_store_iter_next (GtkTreeModel *tree_model,
                           GtkTreeIter *iter);

static gboolean
miro_list_store_iter_children (GtkTreeModel *tree_model,
                               GtkTreeIter *iter,
                               GtkTreeIter *parent);

static gboolean
miro_list_store_iter_has_child (GtkTreeModel *tree_model,
                                GtkTreeIter *iter);

static gint
miro_list_store_iter_n_children (GtkTreeModel *tree_model,
                                 GtkTreeIter *iter);

static gboolean
miro_list_store_iter_nth_child (GtkTreeModel *tree_model,
                                GtkTreeIter *iter,
                                GtkTreeIter *parent,
                                gint n);

static gboolean
miro_list_store_iter_parent (GtkTreeModel *tree_model,
                             GtkTreeIter *iter,
                             GtkTreeIter *child);

static void
miro_list_store_interface_init (GtkTreeModelIface *iface);

static void
miro_list_store_set_path_row(MiroListStore* self, int row);


/* Create the "miro.infolist.gtk" module */

static PyObject*
convert_obj_to_utf8(PyObject* obj) {
        PyObject* obj_as_unicode;
        PyObject* obj_as_utf8;

        if(PyString_Check(obj)) {
                /* obj is a string already, we can use it's value directly */
                Py_INCREF(obj);
                return obj;
        }
        /* Convert the object to unicode */
        if(PyUnicode_Check(obj)) {
                /* fast path for objects that are already unicode */
                obj_as_unicode = obj;
                Py_INCREF(obj_as_unicode);
        } else {
                obj_as_unicode = PyObject_Unicode(obj);
                if(!obj_as_unicode) return NULL;
        }
        /* Convert the unicode to utf-8 */
        obj_as_utf8 = PyUnicode_AsUTF8String(obj_as_unicode);
        Py_DECREF(obj_as_unicode);
        return obj_as_utf8;
}

static void 
text_cell_data_func(GtkTreeViewColumn *tree_column,
                    GtkCellRenderer *cell,
                    GtkTreeModel *tree_model,
                    GtkTreeIter *iter,
                    gchar* attr_name)
{
        PyObject* attr_obj;
        PyObject* attr_as_utf8;
        InfoListNode *node;
        PyGILState_STATE gstate;

        /* Aquire the GIL before touching python data */
        gstate = PyGILState_Ensure();
        /* Get the python object for this cell */
        node = (InfoListNode*)iter->user_data;
        attr_obj = PyObject_GetAttrString(node->info, attr_name);
        if(!attr_obj) {
                PyErr_Print();
                return;
        }
        if(attr_obj == Py_None) {
                /* Special-case empty values */
                Py_DECREF(attr_obj);
                PyGILState_Release(gstate);
                g_object_set(G_OBJECT(cell), "text", "", NULL);
                return;
        }

        /* Convert object to utf-8 */
        attr_as_utf8 = convert_obj_to_utf8(attr_obj);
        if(!attr_as_utf8) {
                PyErr_Print();
                Py_DECREF(attr_obj);
                return;
        }
        /* Set the value */
        g_object_set(G_OBJECT(cell), "text", PyString_AS_STRING(attr_as_utf8),
                     NULL);
        /* All done.  Release references then the GIL */
        Py_DECREF(attr_as_utf8);
        Py_DECREF(attr_obj);
        PyGILState_Release(gstate);
}


static PyObject *
setup_text_cell_data_func(PyObject *self, PyObject *args)
{
        PyObject* column;
        PyObject* renderer;
        GObject* g_column;
        GObject* g_renderer;

        const char *attr_name;

        if (!PyArg_ParseTuple(args, "O!O!s",
                              PyGObject_Type, &column,
                              PyGObject_Type, &renderer,
                              &attr_name)) {
                return NULL;
        }
        /* Convert Python objects to GObjects */
        g_column = pygobject_get(column);
        g_renderer = pygobject_get(renderer);

        /* Set the cell data func
         * Copy attr_name so that we own the reference, use g_free as our
         * destroy func to free it when we're done.
         * */
        gtk_tree_view_column_set_cell_data_func(GTK_TREE_VIEW_COLUMN(g_column),
                                                GTK_CELL_RENDERER(g_renderer),
                                                (GtkTreeCellDataFunc)
                                                text_cell_data_func,
                                                g_strdup(attr_name),
                                                g_free);

        Py_INCREF(Py_None);
        return Py_None;
}

static PyMethodDef InfoListGTKMethods[] = {
        {"setup_text_cell_data_func",  setup_text_cell_data_func, METH_VARARGS,
                "Setup a Text Cell data function for an InfoList model" },
        {NULL, NULL, 0, NULL}        /* Sentinel */
};

/* Implement GTK stuff */

G_DEFINE_TYPE_WITH_CODE(MiroListStore, miro_list_store, G_TYPE_OBJECT,
                        G_IMPLEMENT_INTERFACE(GTK_TYPE_TREE_MODEL,
                                              miro_list_store_interface_init));

static void
miro_list_store_class_init (MiroListStoreClass *klass)
{
        GObjectClass *gobject_class = G_OBJECT_CLASS (klass);

        gobject_class->finalize = miro_list_store_finalize;
}

static void
miro_list_store_init (MiroListStore *self)
{
        // Random int to check whether an iter belongs to our model
        self->stamp = g_random_int();
        // make a path with depth == 1, we can use this to send out signals
        self->path = gtk_tree_path_new();
        gtk_tree_path_append_index(self->path, 0);
}

static void
miro_list_store_finalize (GObject *self)
{
        gtk_tree_path_free(MIRO_LIST_STORE(self)->path);
}

static GtkTreeModelFlags
miro_list_store_get_flags (GtkTreeModel *tree_model)
{
        return (GtkTreeModelFlags)(GTK_TREE_MODEL_LIST_ONLY |
                                   GTK_TREE_MODEL_ITERS_PERSIST);
}

static gint
miro_list_store_get_n_columns (GtkTreeModel *tree_model)
{
        return 0;
}

static GType
miro_list_store_get_column_type (GtkTreeModel *tree_model,
                                 gint index)
{
        return G_TYPE_INVALID;
}

static gboolean
miro_list_store_make_iter (GtkTreeModel *tree_model,
                           GtkTreeIter  *iter,
                           gint         index)
{
        MiroListStore *miro_list_store;

        miro_list_store = MIRO_LIST_STORE(tree_model);

        if (index < 0 || index >= miro_list_store->nodelist->node_count) {
                return FALSE;
        }

        iter->stamp = miro_list_store->stamp;
        iter->user_data = infolist_nodelist_nth_node(miro_list_store->nodelist,
                                                     index);
        return TRUE;
}

static gboolean
miro_list_store_get_iter (GtkTreeModel *tree_model,
                          GtkTreeIter  *iter,
                          GtkTreePath  *path)
{
        g_assert(path);
        g_assert(gtk_tree_path_get_depth(path) == 1);

        return miro_list_store_make_iter(tree_model, iter,
                                         gtk_tree_path_get_indices(path)[0]);
}

static GtkTreePath *
miro_list_store_get_path (GtkTreeModel *tree_model,
                          GtkTreeIter  *iter)
{
        GtkTreePath  *path;
        MiroListStore *miro_list_store;
        InfoListNode* node;
        int index;

        miro_list_store = MIRO_LIST_STORE(tree_model);
        g_assert (iter != NULL);
        if (iter->stamp != miro_list_store->stamp) return NULL;
        g_assert (iter->user_data != NULL);

        node = (InfoListNode*)iter->user_data;
        index = infolist_nodelist_node_index(miro_list_store->nodelist, node);
        if(index < 0) return NULL;
        path = gtk_tree_path_new();
        gtk_tree_path_append_index(path, index);
        return path;
}

static void
miro_list_store_get_value (GtkTreeModel *tree_model,
                           GtkTreeIter  *iter,
                           gint          column,
                           GValue       *value)
{
        return; // no visible columns
}

static gboolean
miro_list_store_iter_next (GtkTreeModel  *tree_model,
                           GtkTreeIter   *iter)
{
        MiroListStore *miro_list_store;
        InfoListNode *node;

        miro_list_store = MIRO_LIST_STORE(tree_model);
        g_assert(iter);
        if (iter->stamp != miro_list_store->stamp) return FALSE;
        g_assert(iter->user_data);

        node = iter->user_data;
        if(infolist_node_is_sentinal(node->next)) return FALSE;
        iter->user_data = node->next;
        return TRUE;
}

static gboolean
miro_list_store_iter_children (GtkTreeModel *tree_model,
                               GtkTreeIter  *iter,
                               GtkTreeIter  *parent)
{
        // We don't have children, only works for special case when parent=NULL
        if(parent != NULL) return FALSE;
        return miro_list_store_make_iter(tree_model, iter,  0);
}

static gboolean
miro_list_store_iter_has_child (GtkTreeModel *tree_model,
                                GtkTreeIter  *iter)
{
        return FALSE;
}

static gint
miro_list_store_iter_n_children (GtkTreeModel *tree_model,
                                 GtkTreeIter  *iter)
{
        MiroListStore* miro_list_store;
        // We don't have children, only works for special case when iter=NULL
        if(iter) {
                return 0;
        }
        miro_list_store = MIRO_LIST_STORE(tree_model);
        return miro_list_store->nodelist->node_count;
}

static gboolean
miro_list_store_iter_nth_child (GtkTreeModel *tree_model,
                                GtkTreeIter  *iter,
                                GtkTreeIter  *parent,
                                gint          n)
{
        if(parent) {
                return FALSE; // non-toplevel row fails
        }
        return miro_list_store_make_iter(tree_model, iter, n);
}

static gboolean
miro_list_store_iter_parent (GtkTreeModel *tree_model,
                             GtkTreeIter  *iter,
                             GtkTreeIter  *child)
{
        return FALSE;
}

static void
miro_list_store_interface_init (GtkTreeModelIface *iface)
{
        iface->get_flags       = miro_list_store_get_flags;
        iface->get_n_columns   = miro_list_store_get_n_columns;
        iface->get_column_type = miro_list_store_get_column_type;
        iface->get_iter        = miro_list_store_get_iter;
        iface->get_path        = miro_list_store_get_path;
        iface->get_value       = miro_list_store_get_value;
        iface->iter_next       = miro_list_store_iter_next;
        iface->iter_children   = miro_list_store_iter_children;
        iface->iter_has_child  = miro_list_store_iter_has_child;
        iface->iter_n_children = miro_list_store_iter_n_children;
        iface->iter_nth_child  = miro_list_store_iter_nth_child;
        iface->iter_parent     = miro_list_store_iter_parent;
}

MiroListStore*
miro_list_store_new(InfoListNodeList* nodelist)
{
        MiroListStore *rv;
        rv = MIRO_LIST_STORE(g_object_new (MIRO_TYPE_LIST_STORE, NULL));
        rv->nodelist = nodelist;
        return rv;
}

static void
miro_list_store_set_path_row(MiroListStore* self, int row)
{
        gtk_tree_path_get_indices(self->path)[0] = row;
}

// Implement InfoListNodeList hooks

static void
do_init_pygtk(void)
{
        // This is pretty weird, init_pygtk is a macro that sometimes calls
        // return, so we have to put this call in it's own function.
        init_pygtk();
}

int
infolistplat_init(void)
{
        PyObject* gobject_mod;
        PyObject* infolist_mod;
        PyObject* infolist_gtk_mod;

        g_type_init();
        if(!pygobject_init(2, -1, -1)) return -1;
        do_init_pygtk();
        if(PyErr_Occurred()) return -1;

        /* Setup PyGObject_Type */
        gobject_mod = PyImport_ImportModule("gobject");
        if (!gobject_mod) {
                return -1;
        }
        PyGObject_Type = (PyTypeObject*)PyObject_GetAttrString(gobject_mod,
                                                               "GObject");
        Py_DECREF(gobject_mod);

        /* Create our GTK infolist submodule. */
        infolist_gtk_mod = Py_InitModule("miro.infolist.gtk",
                                         InfoListGTKMethods);
        if(!infolist_gtk_mod) {
                return -1;
        }

        infolist_mod = PyImport_ImportModule("miro.infolist");
        if(!infolist_mod) {
                return -1;
        }
        if(PyModule_AddObject(infolist_mod, "gtk", infolist_gtk_mod) < 0) {
                return -1;
        }
        return 0;
}


int
infolistplat_nodelist_created(InfoListNodeList* nodelist)
{
        MiroListStore* new_list_store;
        new_list_store = miro_list_store_new(nodelist);
        if(!new_list_store) {
                PyErr_SetNone(PyExc_MemoryError);
                return -1;
        }
        nodelist->plat_data = new_list_store;
        return 0;
}

int
infolistplat_nodelist_will_destroy(InfoListNodeList* nodelist)
{
        GObject* miro_list_store;

        miro_list_store = G_OBJECT(nodelist->plat_data);
        g_object_unref(miro_list_store);
        return 0;
}

void
infolistplat_will_add_nodes(InfoListNodeList* nodelist)
{
        infolist_nodelist_calc_positions(nodelist);
}

int
infolistplat_node_added(InfoListNodeList* nodelist,
                        InfoListNode* node)
{
        MiroListStore* miro_list_store;
        GtkTreeIter iter;
        int row;

        miro_list_store = MIRO_LIST_STORE(nodelist->plat_data);
        iter.stamp      = miro_list_store->stamp;
        iter.user_data  = node;
        if(!infolist_node_is_sentinal(node->prev)) {
                // we call infolist_nodelist_calc_positions() before we start
                // inserting, then add nodes from the end of the list.  We
                // can calculate our position using the previous node.
                row = node->prev->position + 1;
        } else {
                row = 0;
        }
        miro_list_store_set_path_row(miro_list_store, row);
        gtk_tree_model_row_inserted(GTK_TREE_MODEL(miro_list_store),
                                    miro_list_store->path,
                                    &iter);
        return 0;
}

void
infolistplat_will_change_nodes(InfoListNodeList* nodelist)
{
        infolist_nodelist_calc_positions(nodelist);
}

int
infolistplat_node_changed(InfoListNodeList* nodelist,
                          InfoListNode* node)
{
        MiroListStore* miro_list_store;
        GtkTreeIter iter;

        miro_list_store = MIRO_LIST_STORE(nodelist->plat_data);
        iter.stamp      = miro_list_store->stamp;
        iter.user_data  = node;
        // node->position should still be valid from the
        // infolist_nodelist_calc_positions() call in
        // infolistplat_will_change_nodes
        miro_list_store_set_path_row(miro_list_store, node->position);
        gtk_tree_model_row_changed(GTK_TREE_MODEL(miro_list_store),
                                   miro_list_store->path,
                                   &iter);
        return 0;
}

void
infolistplat_will_remove_nodes(InfoListNodeList* nodelist)
{
        infolist_nodelist_calc_positions(nodelist);
}

int
infolistplat_node_removed(InfoListNodeList* nodelist,
                          InfoListNode* node)
{
        MiroListStore* miro_list_store;

        miro_list_store = MIRO_LIST_STORE(nodelist->plat_data);
        // node->position should still be valid from the
        // infolist_nodelist_calc_positions() call in
        // infolistplat_will_change_nodes.  Note that node->position will be
        // invalid for all nodes after this one, but since we remove things in
        // back-to-front order this doesn't matter
        miro_list_store_set_path_row(miro_list_store, node->position);
        gtk_tree_model_row_deleted(GTK_TREE_MODEL(miro_list_store),
                                   miro_list_store->path);
        return 0;
}

void
infolistplat_will_reorder_nodes(InfoListNodeList* nodelist)
{
        infolist_nodelist_calc_positions(nodelist);
}

int
infolistplat_nodes_reordered(InfoListNodeList* nodelist)
{
        MiroListStore* miro_list_store;
        int* new_order;
        int i;
        InfoListNode* node;
        GtkTreePath* path;

        if(nodelist->node_count == 0) return 0;

        miro_list_store = MIRO_LIST_STORE(nodelist->plat_data);
        new_order = g_new(int, nodelist->node_count);
        if(!new_order) {
                PyErr_SetNone(PyExc_MemoryError);
                return -1;
        }
        path = gtk_tree_path_new();
        node = infolist_nodelist_head(nodelist);
        // node->position was set in infolistplat_will_reorder_nodes(), it
        // contains the old position.
        for(i = 0; i < nodelist->node_count; i++) {
                new_order[i] = node->position;
                node = node->next;
        }
        gtk_tree_model_rows_reordered(GTK_TREE_MODEL(miro_list_store), path,
                                      NULL, new_order);
        gtk_tree_path_free(path);
        return 0;
}

int
infolistplat_add_to_tableview(InfoListNodeList* nodelist,
                              PyObject* pyobject)
{
        GtkTreeView* treeview;

        if(!PyObject_TypeCheck(pyobject,
                               pygobject_lookup_class(GTK_TYPE_TREE_VIEW))) {
                PyErr_SetString(PyExc_TypeError,
                                "param must be a gtk.TreeView");
                return -1;
        }

        treeview = GTK_TREE_VIEW(pygobject_get(pyobject));
        gtk_tree_view_set_model(treeview,
                                GTK_TREE_MODEL(nodelist->plat_data));
        return 0;
}

InfoListNode*
infolistplat_node_for_pos(InfoListNodeList* nodelist,
                          PyObject* pos)
{
        GtkTreeIter* iter;
        MiroListStore* miro_list_store;

        if(!pyg_boxed_check(pos, GTK_TYPE_TREE_ITER)) {
                PyErr_SetString(PyExc_TypeError,
                                "param must be a gtk.TreeIter");
                return NULL;
        }
        iter = pyg_boxed_get(pos, GtkTreeIter);
        miro_list_store = (MiroListStore*)nodelist->plat_data;
        if (iter->stamp != miro_list_store->stamp) {
                PyErr_SetString(PyExc_ValueError,
                                "iter not from this nodelist");
                return NULL;
        }

        return (InfoListNode*)iter->user_data;
}

PyObject*
infolistplat_iter_for_node(InfoListNodeList* nodelist,
                           InfoListNode* node)
{
        GtkTreeIter iter;
        MiroListStore* miro_list_store;

        miro_list_store = (MiroListStore*)nodelist->plat_data;

        iter.stamp = miro_list_store->stamp;
        iter.user_data = node;
        /* This call to pyg_boxed_new copies the iter, so it's okay that we're
         * using a value from the stack */
        return pyg_boxed_new(GTK_TYPE_TREE_ITER, &iter, TRUE, TRUE);
}
