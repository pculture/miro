#include "MozillaBrowserXPCOM.h"

#include <gtkmozembed.h>
#include <gtkmozembed_internal.h>
#include <nsCOMPtr.h>
#include <nsIDOMCSSStyleDeclaration.h>
#include <nsIDOMDocument.h>
#include <nsIDOMDocumentFragment.h>
#include <nsIDOMDocumentRange.h>
#include <nsIDOMElement.h>
#include <dom/nsIDOMElementCSSInlineStyle.h>
#include <nsIDOMEventTarget.h>
#include <nsIDOMMouseEvent.h>
#include <dom/nsIDOMNSRange.h>
#include <nsIDOMNodeList.h>
#include <nsIDOMRange.h>
#include <nsIDOMWindow.h>
#include <nsIURIContentListener.h>
#include <nsIWebBrowser.h>
#include <nsString.h>
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
    rv = parent->InsertBefore(newNode, nextSibling, getter_AddRefs(nodeOut));
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
    nsCOMPtr<nsIDOMEventTarget> target;
    result = mouseEvent->GetTarget(getter_AddRefs(target));
    if (NS_FAILED(result)) return NULL;
    nsCOMPtr<nsIDOMElement> element = do_QueryInterface(target);
    if (!element) return NULL;
    // We need to pass in a nsString to GetAttribute().  Create one now, so we
    // only need to do the conversion once.
    nsString contextMenuString = NS_ConvertUTF8toUTF16(
            nsDependentCString("t:contextMenu"));
    while(1) {
        // Check the current element for a context menu attribute
        nsString contextMenu;
        result = element->GetAttribute(contextMenuString, contextMenu);
        if(NS_FAILED(result)) return NULL;
        if(!contextMenu.IsEmpty()) {
            return ToNewCString(contextMenu);
        } 
        // Get the parent of the current element and try again.  If we fail it
        // probably means we reached the document node, or it could mean some
        // generic xpcom error, either way we should return NULL.
        nsCOMPtr<nsIDOMNode> node = do_QueryInterface(element);
        if(node == nsnull) return NULL;
        nsCOMPtr<nsIDOMNode> parent;
        result = node->GetParentNode(getter_AddRefs(parent));
        if(NS_FAILED(result)) return NULL;
        if(parent == nsnull) return NULL;
        element = do_QueryInterface(parent, &result);
        if(NS_FAILED(result)) return NULL;
    }
    // We shouldn't get here, but return NULL just in case.
    return NULL;
}
