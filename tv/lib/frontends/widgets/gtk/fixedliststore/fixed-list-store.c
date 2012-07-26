/*
# Miro - an RSS based video player application
# Copyright (C) 2012
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

/*
 * fixed-list-store.c - MiroFixedListStore implementation
 */

#include "fixed-list-store.h"

static void
miro_fixed_list_store_init (MiroFixedListStore *self);

static GtkTreeModelFlags
miro_fixed_list_store_get_flags (GtkTreeModel *tree_model);

static gint
miro_fixed_list_store_get_n_columns (GtkTreeModel *tree_model);

static GType
miro_fixed_list_store_get_column_type (GtkTreeModel *tree_model,
                                       gint index);

static gboolean
miro_fixed_list_store_make_iter (GtkTreeModel *tree_model,
                                 GtkTreeIter *iter,
                                 gint index);

static gboolean
miro_fixed_list_store_get_iter (GtkTreeModel *tree_model,
                                GtkTreeIter *iter,
                                GtkTreePath *path);

static GtkTreePath *
miro_fixed_list_store_get_path (GtkTreeModel *tree_model,
                                GtkTreeIter *iter);

static void
miro_fixed_list_store_get_value (GtkTreeModel *tree_model,
                                 GtkTreeIter *iter,
                                 gint column,
                                 GValue *value);

static gboolean
miro_fixed_list_store_iter_next (GtkTreeModel *tree_model,
                                 GtkTreeIter *iter);

static gboolean
miro_fixed_list_store_iter_children (GtkTreeModel *tree_model,
                                     GtkTreeIter *iter,
                                     GtkTreeIter *parent);

static gboolean
miro_fixed_list_store_iter_has_child (GtkTreeModel *tree_model,
                                      GtkTreeIter *iter);

static gint
miro_fixed_list_store_iter_n_children (GtkTreeModel *tree_model,
                                       GtkTreeIter *iter);

static gboolean
miro_fixed_list_store_iter_nth_child (GtkTreeModel *tree_model,
                                      GtkTreeIter *iter,
                                      GtkTreeIter *parent,
                                      gint n);

static gboolean
miro_fixed_list_store_iter_parent (GtkTreeModel *tree_model,
                                   GtkTreeIter *iter,
                                   GtkTreeIter *child);

static void
miro_fixed_list_store_interface_init (GtkTreeModelIface *iface);

/* Properties */

enum {
    PROP_0,
    PROP_ROW_COUNT,
    N_PROPERTIES
};

static GParamSpec *obj_properties[N_PROPERTIES] = { NULL, };

/* Implement GObject stuff */

G_DEFINE_TYPE_WITH_CODE(MiroFixedListStore,
                        miro_fixed_list_store,
                        G_TYPE_OBJECT,
                        G_IMPLEMENT_INTERFACE(GTK_TYPE_TREE_MODEL,
                                              miro_fixed_list_store_interface_init));

static void
miro_fixed_list_store_set_property (GObject    *object,
                                    guint         property_id,
                                    const GValue *value,
                                    GParamSpec   *pspec)
{
    MiroFixedListStore *self = MIRO_FIXED_LIST_STORE (object);

    switch (property_id)
    {
        case PROP_ROW_COUNT:
            self->row_count = g_value_get_uint(value);
            break;

        default:
            G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
            break;
    }
}

static void
miro_fixed_list_store_get_property (GObject    *object,
                                    guint       property_id,
                                    GValue     *value,
                                    GParamSpec *pspec)
{
    MiroFixedListStore *self = MIRO_FIXED_LIST_STORE (object);

    switch (property_id)
    {
        case PROP_ROW_COUNT:
            g_value_set_uint (value, self->row_count);
            break;

        default:
            G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
            break;
    }
}

static void
miro_fixed_list_store_class_init (MiroFixedListStoreClass *klass)
{
    GObjectClass *gobject_class = G_OBJECT_CLASS (klass);

    obj_properties[PROP_ROW_COUNT] =
        g_param_spec_uint ("row_count", "row_count",
                           "number of table rows",
                           0, G_MAXUINT,
                           0,
                           G_PARAM_READWRITE| G_PARAM_CONSTRUCT_ONLY);

    gobject_class->set_property = miro_fixed_list_store_set_property;
    gobject_class->get_property = miro_fixed_list_store_get_property;
    g_object_class_install_properties (gobject_class,
                                       N_PROPERTIES,
                                       obj_properties);
}

static void
miro_fixed_list_store_init (MiroFixedListStore *self)
{
    // Random int to check whether an iter belongs to our model
    self->stamp = g_random_int();
}

static GtkTreeModelFlags
miro_fixed_list_store_get_flags (GtkTreeModel *tree_model)
{
    return (GtkTreeModelFlags)(GTK_TREE_MODEL_LIST_ONLY |
                               GTK_TREE_MODEL_ITERS_PERSIST);
}

static gint
miro_fixed_list_store_get_n_columns (GtkTreeModel *tree_model)
{
    return 0;
}

static GType
miro_fixed_list_store_get_column_type (GtkTreeModel *tree_model,
                                       gint index)
{
    return G_TYPE_INVALID;
}

static gboolean
miro_fixed_list_store_make_iter (GtkTreeModel *tree_model,
                                 GtkTreeIter  *iter,
                                 gint         index)
{
    MiroFixedListStore *miro_fls;

    miro_fls = MIRO_FIXED_LIST_STORE(tree_model);

    if (index < 0 || index >= miro_fls->row_count) {
        return FALSE;
    }

    iter->stamp = miro_fls->stamp;
    iter->user_data = (gpointer)index;
    return TRUE;
}

static gboolean
miro_fixed_list_store_get_iter (GtkTreeModel *tree_model,
                                GtkTreeIter  *iter,
                                GtkTreePath  *path)
{
    g_assert(path);
    g_assert(gtk_tree_path_get_depth(path) == 1);

    return miro_fixed_list_store_make_iter(tree_model, iter,
                                           gtk_tree_path_get_indices(path)[0]);
}

static GtkTreePath *
miro_fixed_list_store_get_path (GtkTreeModel *tree_model,
                                GtkTreeIter  *iter)
{
    MiroFixedListStore *miro_fls;
    GtkTreePath* path;

    miro_fls = MIRO_FIXED_LIST_STORE(tree_model);
    // Couple of sanity checks
    g_assert (iter != NULL);
    g_assert (iter->stamp == miro_fls->stamp);

    path = gtk_tree_path_new();
    gtk_tree_path_append_index(path, (gint)iter->user_data);
    return path;
}

static void
miro_fixed_list_store_get_value (GtkTreeModel *tree_model,
                                 GtkTreeIter  *iter,
                                 gint          column,
                                 GValue       *value)
{
    g_value_init(value, G_TYPE_NONE);
}

static gboolean
miro_fixed_list_store_iter_next (GtkTreeModel  *tree_model,
                                 GtkTreeIter   *iter)
{
    MiroFixedListStore *miro_fls;
    gint next;

    miro_fls = MIRO_FIXED_LIST_STORE(tree_model);
    g_assert(iter);
    if (iter->stamp != miro_fls->stamp) return FALSE;

    next = (gint)iter->user_data + 1;
    if(next >= miro_fls->row_count) {
        return FALSE;
    } else {
        iter->user_data = (gpointer)next;
    }
    return TRUE;
}

static gboolean
miro_fixed_list_store_iter_children (GtkTreeModel *tree_model,
                                     GtkTreeIter  *iter,
                                     GtkTreeIter  *parent)
{
    // We don't have children, only works for special case when parent=NULL
    if(parent != NULL) return FALSE;
    return miro_fixed_list_store_make_iter(tree_model, iter,  0);
}

static gboolean
miro_fixed_list_store_iter_has_child (GtkTreeModel *tree_model,
                                      GtkTreeIter  *iter)
{
    return FALSE;
}

static gint
miro_fixed_list_store_iter_n_children (GtkTreeModel *tree_model,
                                       GtkTreeIter  *iter)
{
    MiroFixedListStore* miro_fls;
    // We don't have children, only works for special case when iter=NULL
    if(iter) {
        return 0;
    }
    miro_fls = MIRO_FIXED_LIST_STORE(tree_model);
    return miro_fls->row_count;
}

static gboolean
miro_fixed_list_store_iter_nth_child (GtkTreeModel *tree_model,
                                      GtkTreeIter  *iter,
                                      GtkTreeIter  *parent,
                                      gint          n)
{
    if(parent) {
        return FALSE; // non-toplevel row fails
    }
    return miro_fixed_list_store_make_iter(tree_model, iter, n);
}

static gboolean
miro_fixed_list_store_iter_parent (GtkTreeModel *tree_model,
                                   GtkTreeIter  *iter,
                                   GtkTreeIter  *child)
{
    return FALSE;
}

static void
miro_fixed_list_store_interface_init (GtkTreeModelIface *iface)
{
    iface->get_flags       = miro_fixed_list_store_get_flags;
    iface->get_n_columns   = miro_fixed_list_store_get_n_columns;
    iface->get_column_type = miro_fixed_list_store_get_column_type;
    iface->get_iter        = miro_fixed_list_store_get_iter;
    iface->get_path        = miro_fixed_list_store_get_path;
    iface->get_value       = miro_fixed_list_store_get_value;
    iface->iter_next       = miro_fixed_list_store_iter_next;
    iface->iter_children   = miro_fixed_list_store_iter_children;
    iface->iter_has_child  = miro_fixed_list_store_iter_has_child;
    iface->iter_n_children = miro_fixed_list_store_iter_n_children;
    iface->iter_nth_child  = miro_fixed_list_store_iter_nth_child;
    iface->iter_parent     = miro_fixed_list_store_iter_parent;
}

MiroFixedListStore* miro_fixed_list_store_new(int row_count)
{
    MiroFixedListStore *rv;
    g_assert(row_count >= 0);

    rv = MIRO_FIXED_LIST_STORE(g_object_new (MIRO_TYPE_FIXED_LIST_STORE,
                                             NULL));
    rv->row_count = row_count;
    return rv;
}

gint
miro_fixed_list_store_row_of_iter(MiroFixedListStore* miro_fls,
                                  GtkTreeIter* iter)
{
    g_assert (iter->stamp == miro_fls->stamp);
    return (gint)iter->user_data;
}

