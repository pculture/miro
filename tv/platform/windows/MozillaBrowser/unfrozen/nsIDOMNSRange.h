/*
 * DO NOT EDIT.  THIS FILE IS GENERATED FROM c:/moz/mozilla/dom/public/idl/range/nsIDOMNSRange.idl
 */

#ifndef __gen_nsIDOMNSRange_h__
#define __gen_nsIDOMNSRange_h__


#ifndef __gen_domstubs_h__
#include "domstubs.h"
#endif

/* For IDL files that don't want to include root IDL files. */
#ifndef NS_NO_VTABLE
#define NS_NO_VTABLE
#endif

/* starting interface:    nsIDOMNSRange */
#define NS_IDOMNSRANGE_IID_STR "a6cf90f2-15b3-11d2-932e-00805f8add32"

#define NS_IDOMNSRANGE_IID \
  {0xa6cf90f2, 0x15b3, 0x11d2, \
    { 0x93, 0x2e, 0x00, 0x80, 0x5f, 0x8a, 0xdd, 0x32 }}

class NS_NO_VTABLE nsIDOMNSRange : public nsISupports {
 public: 

  NS_DEFINE_STATIC_IID_ACCESSOR(NS_IDOMNSRANGE_IID)

  /* nsIDOMDocumentFragment createContextualFragment (in DOMString fragment); */
  NS_IMETHOD CreateContextualFragment(const nsAString & fragment, nsIDOMDocumentFragment **_retval) = 0;

  /* boolean isPointInRange (in nsIDOMNode parent, in long offset); */
  NS_IMETHOD IsPointInRange(nsIDOMNode *parent, PRInt32 offset, PRBool *_retval) = 0;

  /* short comparePoint (in nsIDOMNode parent, in long offset); */
  NS_IMETHOD ComparePoint(nsIDOMNode *parent, PRInt32 offset, PRInt16 *_retval) = 0;

  /* boolean intersectsNode (in nsIDOMNode n); */
  NS_IMETHOD IntersectsNode(nsIDOMNode *n, PRBool *_retval) = 0;

  enum { NODE_BEFORE = 0U };

  enum { NODE_AFTER = 1U };

  enum { NODE_BEFORE_AND_AFTER = 2U };

  enum { NODE_INSIDE = 3U };

  /* unsigned short compareNode (in nsIDOMNode n); */
  NS_IMETHOD CompareNode(nsIDOMNode *n, PRUint16 *_retval) = 0;

  /* void nSDetach (); */
  NS_IMETHOD NSDetach(void) = 0;

};

/* Use this macro when declaring classes that implement this interface. */
#define NS_DECL_NSIDOMNSRANGE \
  NS_IMETHOD CreateContextualFragment(const nsAString & fragment, nsIDOMDocumentFragment **_retval); \
  NS_IMETHOD IsPointInRange(nsIDOMNode *parent, PRInt32 offset, PRBool *_retval); \
  NS_IMETHOD ComparePoint(nsIDOMNode *parent, PRInt32 offset, PRInt16 *_retval); \
  NS_IMETHOD IntersectsNode(nsIDOMNode *n, PRBool *_retval); \
  NS_IMETHOD CompareNode(nsIDOMNode *n, PRUint16 *_retval); \
  NS_IMETHOD NSDetach(void); 

/* Use this macro to declare functions that forward the behavior of this interface to another object. */
#define NS_FORWARD_NSIDOMNSRANGE(_to) \
  NS_IMETHOD CreateContextualFragment(const nsAString & fragment, nsIDOMDocumentFragment **_retval) { return _to CreateContextualFragment(fragment, _retval); } \
  NS_IMETHOD IsPointInRange(nsIDOMNode *parent, PRInt32 offset, PRBool *_retval) { return _to IsPointInRange(parent, offset, _retval); } \
  NS_IMETHOD ComparePoint(nsIDOMNode *parent, PRInt32 offset, PRInt16 *_retval) { return _to ComparePoint(parent, offset, _retval); } \
  NS_IMETHOD IntersectsNode(nsIDOMNode *n, PRBool *_retval) { return _to IntersectsNode(n, _retval); } \
  NS_IMETHOD CompareNode(nsIDOMNode *n, PRUint16 *_retval) { return _to CompareNode(n, _retval); } \
  NS_IMETHOD NSDetach(void) { return _to NSDetach(); } 

/* Use this macro to declare functions that forward the behavior of this interface to another object in a safe way. */
#define NS_FORWARD_SAFE_NSIDOMNSRANGE(_to) \
  NS_IMETHOD CreateContextualFragment(const nsAString & fragment, nsIDOMDocumentFragment **_retval) { return !_to ? NS_ERROR_NULL_POINTER : _to->CreateContextualFragment(fragment, _retval); } \
  NS_IMETHOD IsPointInRange(nsIDOMNode *parent, PRInt32 offset, PRBool *_retval) { return !_to ? NS_ERROR_NULL_POINTER : _to->IsPointInRange(parent, offset, _retval); } \
  NS_IMETHOD ComparePoint(nsIDOMNode *parent, PRInt32 offset, PRInt16 *_retval) { return !_to ? NS_ERROR_NULL_POINTER : _to->ComparePoint(parent, offset, _retval); } \
  NS_IMETHOD IntersectsNode(nsIDOMNode *n, PRBool *_retval) { return !_to ? NS_ERROR_NULL_POINTER : _to->IntersectsNode(n, _retval); } \
  NS_IMETHOD CompareNode(nsIDOMNode *n, PRUint16 *_retval) { return !_to ? NS_ERROR_NULL_POINTER : _to->CompareNode(n, _retval); } \
  NS_IMETHOD NSDetach(void) { return !_to ? NS_ERROR_NULL_POINTER : _to->NSDetach(); } 

#if 0
/* Use the code below as a template for the implementation class for this interface. */

/* Header file */
class nsDOMNSRange : public nsIDOMNSRange
{
public:
  NS_DECL_ISUPPORTS
  NS_DECL_NSIDOMNSRANGE

  nsDOMNSRange();

private:
  ~nsDOMNSRange();

protected:
  /* additional members */
};

/* Implementation file */
NS_IMPL_ISUPPORTS1(nsDOMNSRange, nsIDOMNSRange)

nsDOMNSRange::nsDOMNSRange()
{
  /* member initializers and constructor code */
}

nsDOMNSRange::~nsDOMNSRange()
{
  /* destructor code */
}

/* nsIDOMDocumentFragment createContextualFragment (in DOMString fragment); */
NS_IMETHODIMP nsDOMNSRange::CreateContextualFragment(const nsAString & fragment, nsIDOMDocumentFragment **_retval)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* boolean isPointInRange (in nsIDOMNode parent, in long offset); */
NS_IMETHODIMP nsDOMNSRange::IsPointInRange(nsIDOMNode *parent, PRInt32 offset, PRBool *_retval)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* short comparePoint (in nsIDOMNode parent, in long offset); */
NS_IMETHODIMP nsDOMNSRange::ComparePoint(nsIDOMNode *parent, PRInt32 offset, PRInt16 *_retval)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* boolean intersectsNode (in nsIDOMNode n); */
NS_IMETHODIMP nsDOMNSRange::IntersectsNode(nsIDOMNode *n, PRBool *_retval)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* unsigned short compareNode (in nsIDOMNode n); */
NS_IMETHODIMP nsDOMNSRange::CompareNode(nsIDOMNode *n, PRUint16 *_retval)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* void nSDetach (); */
NS_IMETHODIMP nsDOMNSRange::NSDetach()
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* End of implementation class template. */
#endif


#endif /* __gen_nsIDOMNSRange_h__ */
