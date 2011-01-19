
#include <glib-object.h>
#include <gtk/gtk.h>
#include "infolist-nodelist.h"

/* boilerplate GObject defines. */

#define MIRO_TYPE_LIST_STORE            (miro_list_store_get_type ())
#define MIRO_LIST_STORE(obj)            (G_TYPE_CHECK_INSTANCE_CAST ((obj), MIRO_TYPE_LIST_STORE, MiroListStore))
#define MIRO_LIST_STORE_CLASS(klass)    (G_TYPE_CHECK_CLASS_CAST ((klass),  MIRO_TYPE_LIST_STORE, MiroListStoreClass))
#define MIRO_IS_LIST_STORE(obj)         (G_TYPE_CHECK_INSTANCE_TYPE ((obj), MIRO_TYPE_LIST_STORE))
#define MIRO_IS_LIST_STORE_CLASS(klass) (G_TYPE_CHECK_CLASS_TYPE ((klass),  MIRO_TYPE_LIST_STORE))
#define MIRO_LIST_STORE_GET_CLASS(obj)  (G_TYPE_INSTANCE_GET_CLASS ((obj),  MIRO_TYPE_LIST_STORE, MiroListStoreClass))

struct _MiroListStore
{
  GObject parent;
  InfoListNodeList* nodelist;
  gint stamp;
  GtkTreePath* path; // for sending out in signals
};

struct _MiroListStoreClass
{
  GObjectClass parent_class;
};

typedef struct _MiroListStore MiroListStore;
typedef struct _MiroListStoreClass MiroListStoreClass;

MiroListStore* miro_list_store_new(InfoListNodeList* nodelist);
