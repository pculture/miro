#ifndef MOZILLA_BROWSER_XPCOM_H
#define MOZILLA_BROWSER_XPCOM_H

#include <gtkmozembed.h>
#include <nscore.h>

#ifdef __cplusplus
extern "C" {
#endif
nsresult addItemBefore(GtkMozEmbed *gtkembed, char *newXml, char *id);
nsresult addItemAtEnd(GtkMozEmbed *gtkembed, char *newXml, char *id);
nsresult changeItem(GtkMozEmbed *gtkembed, char *id, char *newXml);
nsresult removeItem(GtkMozEmbed *gtkembed, char *id);
nsresult showItem(GtkMozEmbed *gtkembed, char *id);
nsresult hideItem(GtkMozEmbed *gtkembed, char *id);
#ifdef __cplusplus
}
#endif

#endif /* MOZILLA_BROWSER_XPCOM_H */
