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
/*
 * Determine if we need to pop up a context menu in response to a mouse down
 * dom event.  domEvent should be an nsIDOMMouseEvent object, we accept a void
 * here because C code doesn't understand what a nsIDOMMouseEvent is.  Returns
 * a string specifying the context menu or NULL if we shouldn't pop one up.
 */
char* getContextMenu(void* domEvent);
/*
 * If we return a non-NULL string from getContextMenu, the callers must free
 * it using freeString
 */
void freeString(char* str);
#ifdef __cplusplus
}
#endif

#endif /* MOZILLA_BROWSER_XPCOM_H */
