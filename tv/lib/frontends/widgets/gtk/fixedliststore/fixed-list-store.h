/*
 * Miro - an RSS based video player application
 * Copyright (C) 2012
 * Participatory Culture Foundation
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
 *
 * In addition, as a special exception, the copyright holders give
 * permission to link the code of portions of this program with the OpenSSL
 * library.
 *
 * You must obey the GNU General Public License in all respects for all of
 * the code used other than OpenSSL. If you modify file(s) with this
 * exception, you may extend this exception to your version of the file(s),
 * but you are not obligated to do so. If you do not wish to do so, delete
 * this exception statement from your version. If you delete this exception
 * statement from all source files in the program, then also delete it here.
 */

/*
 * fixed-list-store.h - MiroFixedListStore interface
 *
 * MiroFixedListStore is a GtkTreeModel for a simple fixed-size list of items.
 *
 * MiroFixedListStore does next to nothing, but at least it does it fast :)
 * It stores no data at all, nor can rows be added, deleted, or reordered.  On
 * the plus side, this means that it implements the GtkTreeModel API pretty
 * close to as fast as possible.
 *
 * The intended use is alongside another class to actually fetch the data and
 * to use a custom cell renderer function to set up the cell renderers.
 */

#include <glib-object.h>
#include <gtk/gtk.h>

/* boilerplate GObject defines. */

#define MIRO_TYPE_FIXED_LIST_STORE            (miro_fixed_list_store_get_type ())
#define MIRO_FIXED_LIST_STORE(obj)            (G_TYPE_CHECK_INSTANCE_CAST ((obj), MIRO_TYPE_FIXED_LIST_STORE, MiroFixedListStore))
#define MIRO_FIXED_LIST_STORE_CLASS(klass)    (G_TYPE_CHECK_CLASS_CAST ((klass),  MIRO_TYPE_FIXED_LIST_STORE, MiroFixedListStore))
#define MIRO_FIXED_IS_LIST_STORE(obj)         (G_TYPE_CHECK_INSTANCE_TYPE ((obj), MIRO_TYPE_FIXED_LIST_STORE))
#define MIRO_FIXED_IS_LIST_STORE_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE ((klass),  MIRO_TYPE_FIXED_LIST_STORE))
#define MIRO_FIXED_LIST_STORE_GET_CLASS(obj)  (G_TYPE_INSTANCE_GET_CLASS ((obj),  MIRO_TYPE_FIXED_LIST_STORE, MiroFixedListStore))

struct _MiroFixedListStore
{
  GObject parent_instance;

  /* instance members */
  gint row_count;
  gint stamp;
};

struct _MiroFixedListStoreClass
{
  GObjectClass parent_class;
};

typedef struct _MiroFixedListStore MiroFixedListStore;
typedef struct _MiroFixedListStoreClass MiroFixedListStoreClass;

/*
 * Create a new MiroFixedListStore
 *
 * :param row_count: number of rows in the model
 * column) and return a python string.
 */
MiroFixedListStore* miro_fixed_list_store_new(int row_count);

/*
 * Convert a python TreeModelIter to an index.
 */

gint
miro_fixed_list_store_row_of_iter(MiroFixedListStore* miro_fls,
                                  GtkTreeIter* iter);
