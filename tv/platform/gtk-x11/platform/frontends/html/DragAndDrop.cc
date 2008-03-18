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

#include "DragAndDrop.h"
#include "XPCOMUtil.h"
#include <nsICommandManager.h>
#include <gtkmozembed.h>
#include <gtkmozembed_internal.h>

#include <nsIDragService.h>
#include <nsIDragSession.h>
#include <nsIDOMEvent.h>
#include <nsIDOMEventListener.h>
#include <nsIDOMEventTarget.h>
#include <nsIDOMMouseEvent.h>
#include <nsIDOMWindow.h>
#include <nsILocalFile.h>
#include <nsIComponentRegistrar.h>
#include <nsIWebBrowser.h>

#ifndef PCF_USING_XULRUNNER19
#include <nsString.h>
#else
#include <nsStringAPI.h>
#endif
#include <nsIClipboardDragDropHooks.h>
#include <nsIDragSession.h>
#include <nsISupportsPrimitives.h>
#include <nsITransferable.h>
#include <nsISupportsArray.h>
#include <nsICollection.h>
#include <stdio.h>
#include <string.h>

#ifdef MOZILLA_INTERNAL_API
#include <nsEscape.h>
#else
#include <nsINetUtil.h>
#include <nsServiceManagerUtils.h>
#include <nsComponentManagerUtils.h>
#endif

PRInt32 stringToDragAction(const nsAString &str) {
    nsCAutoString cstr = NS_ConvertUTF16toUTF8(str);
    if(cstr.Equals("move")) return nsIDragService::DRAGDROP_ACTION_MOVE;
    if(cstr.Equals("copy")) return nsIDragService::DRAGDROP_ACTION_COPY;
    if(cstr.Equals("link")) return nsIDragService::DRAGDROP_ACTION_LINK;
    printf("WARNING: bad dragEffect string: %s\n", 
            PromiseFlatCString(cstr).get());
    return nsIDragService::DRAGDROP_ACTION_NONE;
}

nsresult makeDragData(nsIDOMElement* element, nsISupportsArray *dragArray) {
    // Create a transferable
    nsresult rv;
    nsCOMPtr<nsITransferable> trans(do_CreateInstance(
                "@mozilla.org/widget/transferable;1", &rv));
    // Add the mime-type
    nsAutoString dragSourceTypeStr = NS_ConvertUTF8toUTF16(
            nsDependentCString("dragsourcetype"));
    nsAutoString dragType;
    rv = element->GetAttribute(dragSourceTypeStr, dragType);
    nsCAutoString mimeType = NS_ConvertUTF16toUTF8(dragType);
    mimeType.Insert("application/x-miro-", 0);
    mimeType.Append("-drag");
    trans->AddDataFlavor(PromiseFlatCString(mimeType).get());
    if(NS_FAILED(rv)) return rv;
    // Add the data
    nsAutoString dragSourceDataStr = NS_ConvertUTF8toUTF16(
            nsDependentCString("dragsourcedata"));
    nsAutoString sourceDataStr;
    rv = element->GetAttribute(dragSourceDataStr, sourceDataStr);
    nsCOMPtr<nsISupportsString> sourceData(do_CreateInstance(
                "@mozilla.org/supports-string;1", &rv));
    rv = sourceData->SetData(sourceDataStr);
    if(NS_FAILED(rv)) return rv;
    rv = trans->SetTransferData(PromiseFlatCString(mimeType).get(), sourceData,
            sourceDataStr.Length() * 2);
    if(NS_FAILED(rv)) return rv;
    // Turn that transferable into an nsISupportsArray
    nsCOMPtr<nsISupports> transSupports(do_QueryInterface(trans, &rv));
    if(NS_FAILED(rv)) return rv;
    nsCOMPtr<nsICollection> dragCollection(do_QueryInterface(dragArray, &rv));
    if(NS_FAILED(rv)) return rv;
    rv = dragCollection->AppendElement(transSupports);
    return rv;
}

nsresult startDrag(nsISupportsArray* dragArray) {
    nsresult rv;
    // Get the drag service and make sure we're not already doing a drop
    nsCOMPtr<nsIDragService> dragService(do_GetService(
                "@mozilla.org/widget/dragservice;1", &rv));
    if(NS_FAILED(rv)) return rv;
    nsCOMPtr<nsIDragSession> dragSession;
    rv = dragService->GetCurrentSession(getter_AddRefs(dragSession));
    if(NS_FAILED(rv)) return rv;
    if(dragSession != nsnull) return NS_ERROR_FAILURE;
    rv = dragService->InvokeDragSession(NULL, dragArray, NULL, 
            nsIDragService::DRAGDROP_ACTION_COPY);
    return rv;
}

nsresult isSingleDragTypeSupported(const nsAString &dragType, PRBool *supported)
{
    nsresult rv;


    nsCAutoString dragMimeType = NS_ConvertUTF16toUTF8(dragType);
    dragMimeType.Insert("application/x-miro-", 0);
    dragMimeType.Append("-drag");
    nsCOMPtr<nsIDragService> dragService(do_GetService(
                "@mozilla.org/widget/dragservice;1", &rv));
    if(NS_FAILED(rv)) return rv;
    nsCOMPtr<nsIDragSession> dragSession;
    rv = dragService->GetCurrentSession(getter_AddRefs(dragSession));
    if(NS_FAILED(rv)) return rv;
    rv = dragSession->IsDataFlavorSupported(
            PromiseFlatCString(dragMimeType).get(), supported);
    return rv;
}

nsresult checkForURLs(PRBool* hasURLs)
{
    nsresult rv;
    nsCOMPtr<nsIDragService> dragService(do_GetService(
                "@mozilla.org/widget/dragservice;1", &rv));
    if(NS_FAILED(rv)) return rv;
    nsCOMPtr<nsIDragSession> dragSession;
    rv = dragService->GetCurrentSession(getter_AddRefs(dragSession));
    if(NS_FAILED(rv)) return rv;
    rv = dragSession->IsDataFlavorSupported(kURLMime, hasURLs);
    if(NS_FAILED(rv)) return rv;
    return NS_OK;
}

nsresult isDragTypeSupported(const nsAString& dragAttribute, 
        PRBool *supported, nsAString* dragType = nsnull)
{
    PRInt32 start, currentColon;
    start = currentColon = 0;
    *supported = false;
    nsresult rv;

    while(start < dragAttribute.Length()) {
        currentColon = dragAttribute.FindChar(':', start);
        if(currentColon < 0) {
            const nsAString& singleDragType = Substring(dragAttribute, start, 
                    dragAttribute.Length() - start);
            rv = isSingleDragTypeSupported(singleDragType, supported);
            if(NS_FAILED(rv)) return rv;
            if(*supported && dragType) {
                dragType->Replace(0, dragType->Length(), singleDragType);
            }
            return NS_OK;
        }
        const nsAString& singleDragType = Substring(dragAttribute, start, 
                currentColon - start);
        rv = isSingleDragTypeSupported(singleDragType, supported);

        if(NS_FAILED(rv)) return rv;
        if(*supported) {
            if(dragType) {
                dragType->Replace(0, dragType->Length(), singleDragType);
            }
            return NS_OK;
        }
        start = currentColon + 1;
    }
    return NS_OK;
}

nsresult extractDragData(const char* mimeType, nsAString& output, int index=0) 
{
    nsresult rv;
    nsCOMPtr<nsIDragService> dragService(do_GetService(
                "@mozilla.org/widget/dragservice;1", &rv));
    if(NS_FAILED(rv)) return rv;
    nsCOMPtr<nsIDragSession> dragSession;
    rv = dragService->GetCurrentSession(getter_AddRefs(dragSession));
    if(NS_FAILED(rv)) return rv;
    nsCOMPtr<nsITransferable> trans(do_CreateInstance(
                "@mozilla.org/widget/transferable;1", &rv));
    if(NS_FAILED(rv)) return rv;
    trans->AddDataFlavor(mimeType);
    if(NS_FAILED(rv)) return rv;
    rv = dragSession->GetData(trans, index);
    if(NS_FAILED(rv)) return rv;
    nsCOMPtr<nsISupportsString> data;
    PRUint32 length;
    rv = trans->GetTransferData(mimeType, getter_AddRefs(data), &length);
    if(NS_FAILED(rv)) return rv;
    rv = data->GetData(output);
    return rv;
}

nsresult getDragSourceData(const nsAString &dragType, nsAString &output)
{
    nsresult rv;

    nsCAutoString dragMimeType = NS_ConvertUTF16toUTF8(dragType);
    dragMimeType.Insert("application/x-miro-", 0);
    dragMimeType.Append("-drag");
    rv = extractDragData(PromiseFlatCString(dragMimeType).get(), output);
    if(NS_FAILED(rv)) return rv;
    return NS_OK;
}


static nsCOMPtr<nsIDOMElement> highlightedElement;
static nsAutoString currentHighlightClass;

nsresult removeCurrentHighlight() {
    if(!highlightedElement) return NS_OK;
    nsAutoString classStr = NS_ConvertUTF8toUTF16(nsDependentCString("class"));
    nsAutoString cssClass;
    nsresult rv;
    rv = highlightedElement->GetAttribute(classStr, cssClass);
    if(NS_FAILED(rv)) return rv;
    int hlLength = currentHighlightClass.Length();
    for(int i = 0; i <= cssClass.Length() - hlLength; i++) {
        if(Substring(cssClass, i, hlLength).Equals(currentHighlightClass)) {
            cssClass.Cut(i, hlLength);
            break;
        }
    }
    rv = highlightedElement->SetAttribute(classStr, cssClass);
    if(NS_FAILED(rv)) return rv;
    highlightedElement = nsnull;
    return NS_OK;
}

nsresult setNewHighlight(nsIDOMElement *element, const nsAString &dragType) {
    nsresult rv;
    if(highlightedElement) {
        rv = removeCurrentHighlight();
        if(NS_FAILED(rv)) return rv;
    }
    nsAutoString classStr = NS_ConvertUTF8toUTF16(nsDependentCString("class"));
    nsAutoString cssClass;
    rv = element->GetAttribute(classStr, cssClass);
    if(NS_FAILED(rv)) return rv;

    currentHighlightClass.Cut(0, currentHighlightClass.Length());
    if(!cssClass.IsEmpty()) {
        currentHighlightClass.Append(NS_ConvertUTF8toUTF16(
                    nsDependentCString(" ")));
    }
    currentHighlightClass.Append(NS_ConvertUTF8toUTF16(
                nsDependentCString("drag-highlight ")));
    currentHighlightClass.Append(dragType);

    cssClass.Append(currentHighlightClass);
    rv = element->SetAttribute(classStr, cssClass);
    if(NS_FAILED(rv)) return rv;
    highlightedElement = element;
    return NS_OK;
}

nsresult findDropElement(nsIDOMEvent* event, nsIDOMElement** element,
        nsString& singleDragType)
{
    nsresult rv;
    *element = nsnull;
    if(event == nsnull) return NS_OK;
    nsCOMPtr<nsIDOMEventTarget> target;
    rv = event->GetTarget(getter_AddRefs(target));
    if (NS_FAILED(rv)) return rv;
    if(target == nsnull) return NS_OK;
    nsCOMPtr<nsIDOMNode> node (do_QueryInterface(target, &rv));
    if (NS_FAILED(rv)) return rv;

    nsAutoString dragDestTypeString = NS_ConvertUTF8toUTF16(
            nsDependentCString("dragdesttype"));
    nsAutoString dragDestType;
    nsCOMPtr <nsIDOMElement> currentElement;
    PRBool supported;
    while(1) {
        rv = searchUpForElementWithAttribute(node, dragDestTypeString,
                getter_AddRefs(currentElement));
        if(NS_FAILED(rv)) return rv;
        if(currentElement == nsnull) return NS_OK;
        rv = currentElement->GetAttribute(dragDestTypeString, dragDestType);
        if(NS_FAILED(rv)) return rv;
        rv = isDragTypeSupported(dragDestType, &supported, &singleDragType);
        if(NS_FAILED(rv)) return rv;
        if(supported) {
            *element = currentElement;
            (*element)->AddRef();
            return NS_OK;
        } 
        nsCOMPtr<nsIDOMNode> parent;
        rv = node->GetParentNode(getter_AddRefs(parent));
        if(NS_FAILED(rv)) return rv;
        if(parent == nsnull) return NS_OK;
        node = parent;
    }
}

class MiroDNDHook : public nsIClipboardDragDropHooks, nsIDOMEventListener {
protected:
    GtkMozEmbed* embed;

public:   
    MiroDNDHook(GtkMozEmbed* embed) {
        this->embed = embed;
    }

    NS_DECL_ISUPPORTS 

    nsresult AllowDrop(nsIDOMEvent *event, nsIDragSession *session, 
                    PRBool* retval) {
        nsresult rv;
        *retval = false;

        rv = removeCurrentHighlight();
        if(NS_FAILED(rv)) return rv;
        
        nsCOMPtr<nsIDOMElement> element;
        nsString singleDragType;
        rv = findDropElement(event, getter_AddRefs(element), singleDragType);
        if(NS_FAILED(rv)) return rv;
        if(element) {
            nsAutoString dragEffectStr = NS_ConvertUTF8toUTF16(
                    nsDependentCString("drageffect"));
            dragEffectStr.Append(singleDragType);
            nsAutoString dragEffect;
            rv = element->GetAttribute(dragEffectStr, dragEffect);
            if(NS_FAILED(rv)) return rv;
            *retval = true;
            rv = session->SetDragAction(stringToDragAction(dragEffect));
            if(NS_FAILED(rv)) return rv;
            rv = setNewHighlight(element, singleDragType);
            if(NS_FAILED(rv)) return rv;
        } else {
            PRBool hasURLs;
            rv = checkForURLs(&hasURLs);
            if(NS_FAILED(rv)) return rv;
            if(hasURLs) {
                rv = session->SetDragAction(
                        nsIDragService::DRAGDROP_ACTION_COPY);
                if(NS_FAILED(rv)) return rv;
                *retval = true;
                return NS_OK;
            }
        }
        return NS_OK;
    }

    nsresult AllowStartDrag(nsIDOMEvent *event, PRBool* retval) {
        *retval = true;

        nsCOMPtr<nsIDOMElement> element;
        nsAutoString dragSourceTypeStr = NS_ConvertUTF8toUTF16(
                nsDependentCString("dragsourcetype"));
        nsresult rv = searchUpForElementWithAttribute(event, 
                dragSourceTypeStr, getter_AddRefs(element));
        if (NS_FAILED(rv)) return rv;
        if(element) {
            nsCOMPtr<nsISupportsArray> dragArray(do_CreateInstance(
                        "@mozilla.org/supports-array;1", &rv));
            if (NS_FAILED(rv)) return rv;
            makeDragData(element, dragArray);
            rv = startDrag(dragArray);
            if (NS_FAILED(rv)) {
                printf("WARNING: startDrag failed\n");
                return rv;
            } else {
                event->StopPropagation();
                event->PreventDefault();
                *retval = false;
            }
        } 
        return NS_OK;
    }

    nsresult OnCopyOrDrag(nsIDOMEvent *event, nsITransferable *trans, 
                    PRBool* retval) {
        /* This gets called when the default drop handler needs to copy
         * something.  Don't mess with things in this case.
         */
        *retval = true;
        return NS_OK;
    }

    nsresult OnPasteOrDrop(nsIDOMEvent *event, nsITransferable *trans, 
                    PRBool* retval) {
        if(event == nsnull) {
            // Event was a paste, let mozilla handle it.
            *retval = true;
            return NS_OK;
        }
        *retval = false;
        nsresult rv;
        rv = removeCurrentHighlight();
        if(NS_FAILED(rv)) return rv;
        nsCOMPtr<nsIDOMElement> element;
        nsString singleDragType;
        rv = findDropElement(event, getter_AddRefs(element), singleDragType);
        if(NS_FAILED(rv)) return rv;
        if(element) {
            nsAutoString dragDestDataString = NS_ConvertUTF8toUTF16(
                nsDependentCString("dragdestdata"));
            nsAutoString dragDestData;
            rv = element->GetAttribute(dragDestDataString, dragDestData);
            if(NS_FAILED(rv)) return rv;
            nsAutoString sourceData;
            rv = getDragSourceData(singleDragType, sourceData);
            if(NS_FAILED(rv)) return rv;
            *retval = true;
            nsCAutoString url = NS_ConvertUTF16toUTF8(dragDestData);
            url.Insert("action:handleDrop?data=", 0);
            url.Append("&type=");
            url.Append(NS_ConvertUTF16toUTF8(singleDragType));
            url.Append("&sourcedata=");
            url.Append(NS_ConvertUTF16toUTF8(sourceData));
            gtk_moz_embed_load_url(this->embed,
                    PromiseFlatCString(url).get());
            return rv;
        } else {
            PRBool hasURLs;
            rv = checkForURLs(&hasURLs);
            if(NS_FAILED(rv)) return rv;
            if(hasURLs) {
                nsCOMPtr<nsIDragService> dragService(do_GetService(
                            "@mozilla.org/widget/dragservice;1", &rv));
                if(NS_FAILED(rv)) return rv;
                nsCOMPtr<nsIDragSession> dragSession;
                rv = dragService->GetCurrentSession(getter_AddRefs(dragSession));
                if(NS_FAILED(rv)) return rv;
                PRUint32 urlCount;
                rv = dragSession->GetNumDropItems(&urlCount);
                if(NS_FAILED(rv)) return rv;

                nsAutoString data;
                nsCAutoString utf8Data, escapedData;
                if(NS_FAILED(rv)) return rv;
                nsCAutoString url("action:handleURIDrop?data=");
#ifdef PCF_USING_XULRUNNER19
                nsCOMPtr<nsINetUtil> netUtil(do_GetService("@mozilla.org/network/util;1", &rv));
                if(NS_FAILED(rv)) return rv;
#endif
                for(int i = 0; i < urlCount; i++) {
                    rv = extractDragData(kURLMime, data, i);
                    if(NS_FAILED(rv)) return rv;
                    utf8Data = NS_ConvertUTF16toUTF8(data);

#ifndef PCF_USING_XULRUNNER19
                    NS_EscapeURL(PromiseFlatCString(utf8Data).get(),
                            utf8Data.Length(), 
                            esc_Query | esc_Forced | esc_AlwaysCopy,
                            escapedData);
#else
                    netUtil->EscapeURL(utf8Data,
                                       nsINetUtil::ESCAPE_URL_QUERY | nsINetUtil::ESCAPE_URL_FORCED,
                                       escapedData);
#endif
                    url.Append(escapedData);
                    url.Append("%0A"); // "\n" 
                }
                gtk_moz_embed_load_url(this->embed,
                        PromiseFlatCString(url).get());
            }
            return NS_OK;
        }
    }

    nsresult HandleEvent(nsIDOMEvent *event) {
        // This fires for dragexit events
        PRInt32 screenX, screenY;
        nsresult rv;
        nsCOMPtr<nsIDOMMouseEvent> mouseEvent(do_QueryInterface(event, &rv));
        if(NS_FAILED(rv)) return rv;
        rv = mouseEvent->GetScreenX(&screenX);
        if(NS_FAILED(rv)) return rv;
        rv = mouseEvent->GetScreenY(&screenY);
        if(NS_FAILED(rv)) return rv;
        if(screenX == 0 && screenY == 0) {
            rv = removeCurrentHighlight();
            if(NS_FAILED(rv)) return rv;
        }
        return NS_OK;
    }
};

NS_IMPL_ISUPPORTS2(MiroDNDHook, nsIClipboardDragDropHooks, nsIDOMEventListener)

nsresult setupDragAndDrop(GtkMozEmbed* gtkembed)
{
    nsresult rv;

    nsCOMPtr<nsIWebBrowser> browser;
    nsCOMPtr<nsIDOMWindow> domWindow;

    gtk_moz_embed_get_nsIWebBrowser(gtkembed, getter_AddRefs(browser));
    rv = browser->GetContentDOMWindow(getter_AddRefs(domWindow));
    if (NS_FAILED(rv)) return rv;

    nsCOMPtr<nsICommandManager> commandManager(do_GetService(
            "@mozilla.org/embedcomp/command-manager;1", &rv));

    if (NS_FAILED(rv)) return rv;

    nsIClipboardDragDropHooks *rawPtr = new MiroDNDHook(gtkembed);
    if (!rawPtr)
        return NS_ERROR_OUT_OF_MEMORY;
    nsCOMPtr<nsIClipboardDragDropHooks> miroDNDHook(do_QueryInterface(
                rawPtr, &rv));
    if (NS_FAILED(rv)) return rv;
    nsCOMPtr<nsICommandParams> params(do_CreateInstance(
        "@mozilla.org/embedcomp/command-params;1", &rv));
    if (NS_FAILED(rv)) return rv;
    rv = params->SetISupportsValue("addhook", miroDNDHook);
    if (NS_FAILED(rv)) return rv;
    rv = commandManager->DoCommand("cmd_clipboardDragDropHook", params,
            domWindow);
    nsCOMPtr<nsIDOMEventTarget> eventTarget(
            do_QueryInterface(domWindow, &rv));
    if(NS_FAILED(rv)) return rv;
    nsCOMPtr<nsIDOMEventListener> dndEventListener(
            do_QueryInterface(miroDNDHook, &rv));
    if(NS_FAILED(rv)) return rv;
    nsAutoString type = NS_ConvertUTF8toUTF16(
            nsDependentCString("dragexit"));
    rv = eventTarget->AddEventListener(type, dndEventListener, true);
    if(NS_FAILED(rv)) return rv;
    return rv;
}
