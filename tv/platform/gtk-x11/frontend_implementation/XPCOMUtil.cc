#define MOZILLA_INTERNAL_API
#include "XPCOMUtil.h"
#include <nsCOMPtr.h>
#include <nsIDOMEventTarget.h>
#include <nsIDOMElement.h>
#include <nsIDOMNode.h>
#include <nsString.h>

//////////////////////////////////////////////////////////////////////////////
// XPCOMUtil.cc
//
// Contains utility functions for XPCOM.  
//
//////////////////////////////////////////////////////////////////////////////

nsresult searchUpForElementWithAttribute(nsIDOMEvent *event, 
        nsAString& attributeName, nsIDOMElement** element)
{
    nsresult result;
    *element = nsnull;
    nsCOMPtr<nsIDOMEventTarget> target;
    result = event->GetTarget(getter_AddRefs(target));
    if (NS_FAILED(result)) return result;
    nsCOMPtr<nsIDOMNode> node (do_QueryInterface(target, &result));
    if (NS_FAILED(result)) return result;
    return searchUpForElementWithAttribute(node, attributeName, element);
}

nsresult searchUpForElementWithAttribute(nsIDOMNode* startNode,
        nsAString& attributeName, nsIDOMElement** element)
{
    nsresult result;
    *element = nsnull;
    nsCOMPtr<nsIDOMNode> node = startNode;
    while(1) {
        PRUint16 nodeType;
        result = node->GetNodeType(&nodeType);
        if (NS_FAILED(result)) return result;
        if(nodeType == 1) {
            // Element node. Check the current element for the attribute
            nsCOMPtr<nsIDOMElement> elt(do_QueryInterface(node, &result));
            if (NS_FAILED(result)) return result;
            nsString value;
            result = elt->GetAttribute(attributeName, value);
            if(NS_FAILED(result)) return result;
            if(!value.IsEmpty()) {
                *element = elt;
                (*element)->AddRef();
                return NS_OK;
            } 
        } else if(nodeType == 9) {
            // Document node... return nsnull
            return NS_OK;
        }
        nsCOMPtr<nsIDOMNode> parent;
        result = node->GetParentNode(getter_AddRefs(parent));
        if(NS_FAILED(result)) return result;
        if(parent == nsnull) return NS_OK;
        node = parent;
    }
    return NS_ERROR_FAILURE;
}
