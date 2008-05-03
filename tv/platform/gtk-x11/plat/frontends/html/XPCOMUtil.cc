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

#include "XPCOMUtil.h"
#include <nsCOMPtr.h>
#include <nsIDOMEventTarget.h>
#include <nsIDOMElement.h>
#include <nsIDOMNode.h>

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
