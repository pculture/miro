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

#ifndef PCF_USING_XULRUNNER19
#define MOZILLA_INTERNAL_API
#endif

#include "MozillaBrowserXPCOM.h"
#include "XPCOMUtil.h"
#include <gtkmozembed.h>
#include <gtkmozembed_internal.h>
#include <nsCOMPtr.h>
#include <nsIDOMCSSStyleDeclaration.h>
#include <nsIDOMDocument.h>
#include <nsIDOMDocumentFragment.h>
#include <nsIDOMDocumentRange.h>
#include <nsIDOMElement.h>
#include <nsIDOMElementCSSInlineStyle.h>
#include <nsIDOMMouseEvent.h>
#include <nsIDOMNSHTMLElement.h>
#include <nsIDOMNSRange.h>
#include <nsIDOMNodeList.h>
#include <nsIDOMRange.h>
#include <nsIDOMWindow.h>
#include <nsIURIContentListener.h>
#include <nsIWebBrowser.h>

#ifdef PCF_USING_XULRUNNER19
#include <nsMemory.h>
#endif

#include <stdio.h>

//////////////////////////////////////////////////////////////////////////////
// MozillaBrowserXPCOM.cc
//
// This file contains implementations the MozillaBrowser methods that need to
// access XPCOM.  XPCOM is a C++ only technology, so we can't use pyrex to
// define these.  
//////////////////////////////////////////////////////////////////////////////

nsresult GetDocument(GtkMozEmbed *gtkembed,
        nsCOMPtr<nsIDOMDocument> &document)
{
    nsresult rv;
    nsCOMPtr<nsIWebBrowser> browser;
    nsCOMPtr<nsIDOMWindow> domWindow;

    gtk_moz_embed_get_nsIWebBrowser(gtkembed, getter_AddRefs(browser));
    rv = browser->GetContentDOMWindow(getter_AddRefs(domWindow));
    if (NS_FAILED(rv)) return rv;
    rv = domWindow->GetDocument(getter_AddRefs(document));
    return rv;
}

nsresult CreateNode(nsIDOMDocument *document, nsString xml,
        nsCOMPtr<nsIDOMNode> &node)
{
    // Apparently, the only way to create a DOMNode from an xml string is to
    // using an nsIDOMNSRange object which has a CreateContextualFragment
    // method.  It's not clear what "contextual" means in this case, but this
    // seems to work.  See platform/windows/MozillaBrowser/Control.cpp for
    // more discussion.

    nsresult rv;
    nsCOMPtr<nsIDOMDocumentRange> rangeDoc(do_QueryInterface(document, &rv));
    if (NS_FAILED(rv)) return rv;
    nsCOMPtr<nsIDOMRange> range;
    rv = rangeDoc->CreateRange(getter_AddRefs(range));
    if (NS_FAILED(rv)) return rv;

    // We have to initialize the range by pointing it somewhere. 
    // The windows port uses the 1st BODY element, but I think that using 
    // GetDocumentElement is safer, since it's conceivable that a BODY element
    // doesn't exist yet.
    nsCOMPtr<nsIDOMElement> htmlElement;
    rv = document->GetDocumentElement(getter_AddRefs(htmlElement));
    if (NS_FAILED(rv)) return rv;
    nsCOMPtr<nsIDOMNode> htmlElementNode(do_QueryInterface(htmlElement, &rv));
    if (NS_FAILED(rv)) return rv;
    rv = range->SelectNodeContents(htmlElement);
    if (NS_FAILED(rv)) return rv;

    // Now that the range is initialized, we create an nsiDOMNSRange, then
    // call CreateContextualFragment.
    nsCOMPtr<nsIDOMNSRange> nsRange(do_QueryInterface(range, &rv));
    if (NS_FAILED(rv)) return rv;
    nsCOMPtr<nsIDOMDocumentFragment> frag;
    rv = nsRange->CreateContextualFragment(xml, getter_AddRefs(frag));
    if (NS_FAILED(rv)) return rv;

    // Done, convert the DocumentFragment to a plain Node and return
    //rv = CallQueryInterface(frag, getter_AddRefs(node));
    rv = frag->QueryInterface(NS_GET_IID(nsIDOMNode), getter_AddRefs(node));
    return rv;
}

nsresult addItemBefore(GtkMozEmbed *gtkembed, char *newXml, char *id)
{
    nsresult rv;
    nsString xmlConverted = NS_ConvertUTF8toUTF16(nsDependentCString(newXml));
    nsString idConverted = NS_ConvertUTF8toUTF16(nsDependentCString(id));
    nsCOMPtr<nsIDOMDocument> domDocument;
    GetDocument(gtkembed, domDocument);
    // Get the node
    nsCOMPtr<nsIDOMElement> elt;
    rv = domDocument->GetElementById(idConverted, getter_AddRefs(elt));
    if (NS_FAILED(rv)) return rv;
    nsCOMPtr<nsIDOMNode> node(do_QueryInterface(elt, &rv));
    if (NS_FAILED(rv)) return rv;
    // Get that node's parent
    nsCOMPtr<nsIDOMNode> parent;
    rv = node->GetParentNode(getter_AddRefs(parent));
    if (NS_FAILED(rv)) return rv;
    // Create the new node
    nsCOMPtr<nsIDOMNode> newNode;
    rv = CreateNode(domDocument, xmlConverted, newNode);
    if (NS_FAILED(rv)) return rv;
    // Insert the new node 
    nsCOMPtr<nsIDOMNode> nodeOut;
    rv = parent->InsertBefore(newNode, node, getter_AddRefs(nodeOut));
    return rv;
}

nsresult addItemAtEnd(GtkMozEmbed *gtkembed, char *newXml, char *id)
{
    nsresult rv;
    nsString xmlConverted = NS_ConvertUTF8toUTF16(nsDependentCString(newXml));
    nsString idConverted = NS_ConvertUTF8toUTF16(nsDependentCString(id));
    nsCOMPtr<nsIDOMDocument> domDocument;
    GetDocument(gtkembed, domDocument);
    // Get the node
    nsCOMPtr<nsIDOMElement> elt;
    rv = domDocument->GetElementById(idConverted, getter_AddRefs(elt));
    if (NS_FAILED(rv)) return rv;
    nsCOMPtr<nsIDOMNode> node(do_QueryInterface(elt, &rv));
    if (NS_FAILED(rv)) return rv;
    // Create the new node
    nsCOMPtr<nsIDOMNode> newNode;
    rv = CreateNode(domDocument, xmlConverted, newNode);
    if (NS_FAILED(rv)) return rv;
    // Insert the new node 
    nsCOMPtr<nsIDOMNode> nodeOut;
    rv = node->InsertBefore(newNode, nsnull, getter_AddRefs(nodeOut));
    return rv;
}

nsresult changeItem(GtkMozEmbed *gtkembed, char *id, char *newXml)
{
    nsresult rv;
    nsString xmlConverted = NS_ConvertUTF8toUTF16(nsDependentCString(newXml));
    nsString idConverted = NS_ConvertUTF8toUTF16(nsDependentCString(id));
    nsCOMPtr<nsIDOMDocument> domDocument;
    GetDocument(gtkembed, domDocument);
    // Get the node to change
    nsCOMPtr<nsIDOMElement> elt;
    rv = domDocument->GetElementById(idConverted, getter_AddRefs(elt));
    if (NS_FAILED(rv)) return rv;
    nsCOMPtr<nsIDOMNode> nodeToChange(do_QueryInterface(elt, &rv));
    if (NS_FAILED(rv)) return rv;
    // Get that node's parent
    nsCOMPtr<nsIDOMNode> parent;
    rv = nodeToChange->GetParentNode(getter_AddRefs(parent));
    if (NS_FAILED(rv)) return rv;
    // Get the next sibling, so that we can remember the old node's position 
    nsCOMPtr<nsIDOMNode> nextSibling;
    rv = nodeToChange->GetNextSibling(getter_AddRefs(nextSibling));
    if (NS_FAILED(rv)) return rv;
    // Remove the old node 
    nsCOMPtr<nsIDOMNode> nodeOut;
    rv = parent->RemoveChild(nodeToChange, getter_AddRefs(nodeOut));
    if (NS_FAILED(rv)) return rv;
    // Create the new node and insert it
    nsCOMPtr<nsIDOMNode> newNode;
    rv = CreateNode(domDocument, xmlConverted, newNode);
    if (NS_FAILED(rv)) return rv;
    nsCOMPtr<nsIDOMNode> nodeOut2;
    rv = parent->InsertBefore(newNode, nextSibling, getter_AddRefs(nodeOut2));
    return rv;
}

nsresult removeAttribute(GtkMozEmbed *gtkembed, char *id, char *name)
{
    nsresult rv;
    nsString idConverted = NS_ConvertUTF8toUTF16(nsDependentCString(id));
    nsString nameConverted = NS_ConvertUTF8toUTF16(nsDependentCString(name));
    nsCOMPtr<nsIDOMDocument> domDocument;
    GetDocument(gtkembed, domDocument);
    // Get the node to change
    nsCOMPtr<nsIDOMElement> elt;
    rv = domDocument->GetElementById(idConverted, getter_AddRefs(elt));
    if (NS_FAILED(rv)) return rv;
    rv = elt->RemoveAttribute(nameConverted);
    return rv;
}

nsresult changeAttribute(GtkMozEmbed *gtkembed, char *id, char *name, char *value)
{
    nsresult rv;
    nsString idConverted = NS_ConvertUTF8toUTF16(nsDependentCString(id));
    nsString nameConverted = NS_ConvertUTF8toUTF16(nsDependentCString(name));
    nsString valueConverted = NS_ConvertUTF8toUTF16(nsDependentCString(value));
    nsCOMPtr<nsIDOMDocument> domDocument;
    GetDocument(gtkembed, domDocument);
    // Get the node to change
    nsCOMPtr<nsIDOMElement> elt;
    rv = domDocument->GetElementById(idConverted, getter_AddRefs(elt));
    if (NS_FAILED(rv)) return rv;
    rv = elt->SetAttribute(nameConverted, valueConverted);
    return rv;
}
 
nsresult removeItem(GtkMozEmbed *gtkembed, char *id)
{
    nsresult rv;
    nsString idConverted = NS_ConvertUTF8toUTF16(nsDependentCString(id));
    nsCOMPtr<nsIDOMDocument> domDocument;
    GetDocument(gtkembed, domDocument);
    // Get the node
    nsCOMPtr<nsIDOMElement> elt;
    rv = domDocument->GetElementById(idConverted, getter_AddRefs(elt));
    if (NS_FAILED(rv)) return rv;
    nsCOMPtr<nsIDOMNode> nodeToRemove(do_QueryInterface(elt, &rv));
    if (NS_FAILED(rv)) return rv;
    // Get that node's parent
    nsCOMPtr<nsIDOMNode> parent;
    rv = nodeToRemove->GetParentNode(getter_AddRefs(parent));
    if (NS_FAILED(rv)) return rv;
    // Remove the node 
    nsCOMPtr<nsIDOMNode> nodeOut;
    rv = parent->RemoveChild(nodeToRemove, getter_AddRefs(nodeOut));
    return rv;
}

// Helper method for showItem and hideItem
nsresult setElementStyle(GtkMozEmbed *gtkembed, char *id, char *name,
        char *value)
{
    nsresult rv;
    nsString idConverted = NS_ConvertUTF8toUTF16(nsDependentCString(id));
    nsString nameConverted = NS_ConvertUTF8toUTF16(nsDependentCString(name));
    nsString valueConverted = NS_ConvertUTF8toUTF16(nsDependentCString(value));

    nsCOMPtr<nsIDOMDocument> domDocument;
    GetDocument(gtkembed, domDocument);
    // Get the node
    nsCOMPtr<nsIDOMElement> elt;
    rv = domDocument->GetElementById(idConverted, getter_AddRefs(elt));
    if (NS_FAILED(rv)) return rv;      

    nsCOMPtr<nsIDOMElementCSSInlineStyle> styleElt(do_QueryInterface(elt,
                &rv));
    if (NS_FAILED(rv)) return rv;      

    nsCOMPtr<nsIDOMCSSStyleDeclaration> style;
    rv = styleElt->GetStyle(getter_AddRefs(style));
    if (NS_FAILED(rv)) return rv;      

    nsAutoString emptyString;
    rv = style->SetProperty(nameConverted, valueConverted, emptyString);
    return rv;
}

nsresult showItem(GtkMozEmbed *gtkembed, char *id)
{
    return setElementStyle(gtkembed, id, "display", "");
}

nsresult hideItem(GtkMozEmbed *gtkembed, char *id)
{
    return setElementStyle(gtkembed, id, "display", "none");
}

char* getContextMenu(void* domEvent)
{
    // Cast domEvent to a nsIDOMMouseEvent.
    nsIDOMMouseEvent *mouseEvent =  (nsIDOMMouseEvent*)domEvent;
    PRUint16 button;
    nsresult result = mouseEvent->GetButton(&button);
    if(NS_FAILED(result)) return NULL;
    // If it wasn't a right button click, we don't want to pop up a menu
    if(button != 2) return NULL;
    // Get the target of the event.  That's the element we will begin
    // searching for a context menu.
    nsCOMPtr<nsIDOMEvent> event(mouseEvent);

    nsString contextMenuString = NS_ConvertUTF8toUTF16(
            nsDependentCString("t:contextMenu"));
    nsCOMPtr<nsIDOMElement> element;
    result = searchUpForElementWithAttribute(event, contextMenuString,
            getter_AddRefs(element));
    if(NS_FAILED(result)) return NULL;
    if(element == nsnull) return NULL;
    nsString value;
    result = element->GetAttribute(contextMenuString, value);
    if(NS_FAILED(result)) return NULL;
    nsCString cvalue = NS_ConvertUTF16toUTF8(value);
    return ToNewCString(cvalue);
}

void freeString(char* str)
{
    nsMemory::Free(str);
}
