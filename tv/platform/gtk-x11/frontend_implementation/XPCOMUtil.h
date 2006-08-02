#ifndef XPCOM_UTIL_H
#define XPCOM_UTIL_H

#include <nscore.h>
#include <nsString.h>
#include <nsIDOMEvent.h>
#include <nsIDOMElement.h>

/* Walk up the DOM tree, starting with target of event, until an element has
 * attributeName set.  Return that element, or nsnull if nothing was found.
 */
nsresult searchUpForElementWithAttribute(nsIDOMEvent* event, 
        nsAString& attributeName, nsIDOMElement** retval);

#endif /* XPCOM_UTIL_H */
