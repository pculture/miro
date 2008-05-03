/*
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
*/

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
nsresult changeAttribute(GtkMozEmbed *gtkembed, char *id, char *name, char *value);
nsresult removeAttribute(GtkMozEmbed *gtkembed, char *id, char *name);
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
