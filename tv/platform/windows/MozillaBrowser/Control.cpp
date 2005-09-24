#include "MozillaBrowser.h"
#include <stdio.h>

///////////////////////////////////////////////////////////////////////////////
// Creation and destruction                                                  //
///////////////////////////////////////////////////////////////////////////////

Control::~Control() {
  puts("** Control destroyed.");
  PR_DestroyLock(m_mutex);
}

nsresult Control::Create(HWND hwnd, wchar_t *initialURL, wchar_t *userAgent) {
  nsresult rv;
  nsCOMPtr<nsIWebNavigation> nav;

  PR_Lock(m_mutex);

  if (m_chrome != nsnull || m_listener != nsnull) {
    rv = NS_ERROR_ALREADY_INITIALIZED;
    goto done;
  }
  
  if (NS_FAILED(rv = startMozilla()))
    goto done;
  m_hwnd = hwnd;

  // Create a new WebBrowser
  if (NS_FAILED(rv = CreateInstance(NS_WEBBROWSER_CONTRACTID,
				    NS_GET_IID(nsIWebBrowser),
				    getter_AddRefs(m_webBrowser))))
    goto done;

  // Must call InitWindow before registering listeners -- see Mozilla
  // bug 309232, filed by Geoff. We call InitWindow in Chrome::Create().

  // Create a Chrome object to allow Mozilla to control and
  // occasionally query the embedding site
  m_chrome = new Chrome();
  nsISupports *nsI = NS_ISUPPORTS_CAST(nsIWebBrowserChrome *, m_chrome);
  m_ref_chrome = do_QueryInterface(nsI);
  
  m_ref_chrome =
    do_QueryInterface( NS_ISUPPORTS_CAST(nsIWebBrowserChrome *, m_chrome));
  if (NS_FAILED(rv = m_chrome->Create(hwnd, m_webBrowser)))
    goto done;
  
  // Create one of our Listeners, pointed at us, and hooked up to the
  // browser, in order that we receive event callbacks. IMPORTANT: make
  // sure the class is sufficiently initialized that we are fully prepared
  // for any callbacks before we do this.
  Listener *listener = new Listener();
  // It's important to hold a reference across the call :)
  m_listener =
    do_QueryInterface(NS_ISUPPORTS_CAST(nsIWebProgressListener *, listener));
  if (NS_FAILED(rv = listener->Create(m_webBrowser, this)))
    goto done;

  // Load the URL given, or a blank page if omitted.
  wchar_t *url = initialURL ? initialURL : L"about:blank";
  nav = do_QueryInterface(m_webBrowser);
  if (nav == nsnull)
    goto done;
  // documentLoadFinished may have already been called by the time this
  // function returns. In fact for a file it's likely.
  if (NS_FAILED(rv = nav->LoadURI(url,
				  nsIWebNavigation::LOAD_FLAGS_NONE,
				  nsnull /* referrer */, nsnull /* postData */,
				  nsnull /* headers */)))
    goto done;

  if (userAgent) {
    // NEEDS: set userAgent :)
  }

  rv = NS_OK;

 done:
  PR_Unlock(m_mutex);
  return rv;
}

///////////////////////////////////////////////////////////////////////////////
// Window maintenance                                                        //
///////////////////////////////////////////////////////////////////////////////

nsresult Control::recomputeSize(void) {
  PR_Lock(m_mutex);
  m_chrome->recomputeSize();
  PR_Unlock(m_mutex);
  return NS_OK;
}

nsresult Control::activate(void) {
  nsresult rv;
  PR_Lock(m_mutex);

  nsCOMPtr<nsIWebBrowserFocus> focus = do_QueryInterface(m_webBrowser);
  if (!focus)
    rv = NS_ERROR_UNEXPECTED;
  else
    rv = focus->Activate();
    
  PR_Unlock(m_mutex);
  return rv;
}

nsresult Control::deactivate(void) {
  nsresult rv;
  PR_Lock(m_mutex);

  nsCOMPtr<nsIWebBrowserFocus> focus = do_QueryInterface(m_webBrowser);
  if (!focus)
    rv = NS_ERROR_UNEXPECTED;
  else
    rv = focus->Deactivate();
    
  PR_Unlock(m_mutex);
  return rv;
}

///////////////////////////////////////////////////////////////////////////////
// DOM mutators                                                              //
///////////////////////////////////////////////////////////////////////////////

nsresult Control::getDocument(nsIDOMDocument **_retval) {
  nsresult rv;

  nsCOMPtr<nsIDOMWindow> domWindow;
  if (NS_FAILED(rv = m_webBrowser->
		GetContentDOMWindow(getter_AddRefs(domWindow))))
    return rv;

  return domWindow->GetDocument(_retval);
}

nsresult Control::getElementById(wchar_t *id, nsIDOMElement **_retval) {
  nsresult rv;

  nsCOMPtr<nsIDOMDocument> doc;
  if (NS_FAILED(rv = getDocument(getter_AddRefs(doc))))
    return rv;

  nsCOMPtr<nsIDOMElement> elt;
  if (NS_FAILED(rv = doc->GetElementById(nsEmbedString(id),
					 getter_AddRefs(elt))))
    return rv;

  if (elt == nsnull) {
    // This is GetElementById's way of telling us that the element
    // wasn't found AFAICT.
    *_retval = nsnull;
    return NS_ERROR_FAILURE;
  }
  
  *_retval = elt;
  NS_IF_ADDREF(*_retval);
  return NS_OK;
}

nsresult Control::createElement(wchar_t *xml, nsIDOMNode **_retval) {
  nsresult rv;

  // Get the document.
  nsCOMPtr<nsIDOMDocument> doc;
  if (NS_FAILED(rv = getDocument(getter_AddRefs(doc))))
    return rv;

  // Cast from Document to DocumentRange to get at createRange, which,
  // though specified, is not core DOM, but rather the 'Traversal and
  // Range' addon profile.
  nsCOMPtr<nsIDOMDocumentRange> docRange = do_QueryInterface(doc, &rv);
  if (!docRange || NS_FAILED(rv))
    return rv;

  // Create a new range. I don't really understand why
  // createContextualFragment is defined on ranges, or what makes the
  // fragment "contextual" in the first place if I can successfully
  // create one from only a document as I do in this function, but I
  // can roll with it.
  nsCOMPtr<nsIDOMRange> range;
  if (NS_FAILED(rv = docRange->CreateRange(getter_AddRefs(range))))
    return rv;

  // We have to initialize the range by pointing it somewhere. Nobody
  // seems to know what difference it makes where you point it. Maybe
  // it doesn't make any difference for balanced HTML. We might as
  // well pick the BODY tag (NEEDS: hoping there is one.)
  nsCOMPtr<nsIDOMNodeList> bodyNodes;
  if (NS_FAILED(rv = doc->GetElementsByTagName(nsEmbedString(L"BODY"),
					       getter_AddRefs(bodyNodes))))
    return rv;

  nsCOMPtr<nsIDOMNode> bodyNode;
  if (NS_FAILED(rv = bodyNodes->Item(0, getter_AddRefs(bodyNode))))
      return rv;

  if (NS_FAILED(rv = range->SelectNodeContents(bodyNode)))
    return rv;

  // Now get the Mozilla extended range interface that includes
  // createContextualFragment.
  nsCOMPtr<nsIDOMNSRange> nsRange = do_QueryInterface(range, &rv);
  if (!nsRange || NS_FAILED(rv))
    return rv;

  // Finally, we can parse the XML.
  nsEmbedString markup(xml);
  nsCOMPtr<nsIDOMDocumentFragment> frag;
  if (NS_FAILED(rv = nsRange->
		CreateContextualFragment(markup, getter_AddRefs(frag))))
    return rv;

  // Now we have a document fragment. I don't really understand the
  // difference between a document fragment and a document -- the
  // former has no methods and inherits from node, not document. A
  // quick glance at the source of GreateContextualFragment was not
  // enlightening. In any event, it is apparently sufficient for our
  // purposes to return the fragment returned by
  // CreateContextualFragment cast down to node.
  *_retval = frag;
  NS_IF_ADDREF(*_retval);
  return NS_OK;
}

nsresult Control::setElementStyle(wchar_t *id, wchar_t *name,
				  wchar_t *value, wchar_t *priority) {
  nsresult rv;

  nsCOMPtr<nsIDOMElement> elt;
  if (NS_FAILED(rv = getElementById(id, getter_AddRefs(elt))))
    return rv;    

  nsCOMPtr<nsIDOMElementCSSInlineStyle> styleElt = do_QueryInterface(elt, &rv);
  if (!styleElt || NS_FAILED(rv))
    return rv;      

  nsCOMPtr<nsIDOMCSSStyleDeclaration> style;
  if (NS_FAILED(rv = styleElt->GetStyle(getter_AddRefs(style))))
    return rv;

  return style->SetProperty(nsEmbedString(name),
			    nsEmbedString(value),
			    nsEmbedString(priority));
}

nsresult Control::addElementAtEnd(wchar_t *xml, wchar_t *id) {
  nsresult rv;

  nsCOMPtr<nsIDOMElement> parent;
  if (NS_FAILED(rv = getElementById(id, getter_AddRefs(parent))))
    return rv;    

  nsCOMPtr<nsIDOMNode> newNode;
  if (NS_FAILED(rv = createElement(xml, getter_AddRefs(newNode))))
    return rv;    

  nsCOMPtr<nsIDOMNode> nodeOut;
  return parent->InsertBefore(newNode, nsnull, getter_AddRefs(nodeOut));
}

nsresult Control::addElementBefore(wchar_t *xml, wchar_t *id) {
  nsresult rv;

  nsCOMPtr<nsIDOMElement> refElt;
  if (NS_FAILED(rv = getElementById(id, getter_AddRefs(refElt))))
    return rv;    

  nsCOMPtr<nsIDOMNode> parent;
  if (NS_FAILED(rv = refElt->GetParentNode(getter_AddRefs(parent))))
    return rv;
  if (parent == nsnull)
    return NS_ERROR_FAILURE;

  nsCOMPtr<nsIDOMNode> newNode;
  if (NS_FAILED(rv = createElement(xml, getter_AddRefs(newNode))))
    return rv;    

  nsCOMPtr<nsIDOMNode> nodeOut;
  return parent->InsertBefore(newNode, refElt, getter_AddRefs(nodeOut));
}

nsresult Control::removeElement(wchar_t *id) {
  nsresult rv;

  nsCOMPtr<nsIDOMElement> elt;
  if (NS_FAILED(rv = getElementById(id, getter_AddRefs(elt))))
    return rv;    

  nsCOMPtr<nsIDOMNode> parent;
  if (NS_FAILED(rv = elt->GetParentNode(getter_AddRefs(parent))))
    return rv;
  if (parent == nsnull)
    return NS_ERROR_FAILURE;
    
  nsCOMPtr<nsIDOMNode> nodeOut; // the removed node -- or an exception?
  if (NS_FAILED(rv = parent->RemoveChild(elt, getter_AddRefs(nodeOut))))
    return rv;

  // NEEDS: if indeed exceptions are returned in nodeOut, we don't
  // check 'em.

  return NS_OK;
}

nsresult Control::changeElement(wchar_t *id, wchar_t *xml) {
  nsresult rv;

  nsCOMPtr<nsIDOMElement> refElt;
  if (NS_FAILED(rv = getElementById(id, getter_AddRefs(refElt))))
    return rv;    

  nsCOMPtr<nsIDOMNode> parent;
  if (NS_FAILED(rv = refElt->GetParentNode(getter_AddRefs(parent))))
    return rv;
  if (parent == nsnull)
    return NS_ERROR_FAILURE;

  nsCOMPtr<nsIDOMNode> newNode;
  if (NS_FAILED(rv = createElement(xml, getter_AddRefs(newNode))))
    return rv;    

  nsCOMPtr<nsIDOMNode> nodeOut;
  if (NS_FAILED(rv = parent->
		ReplaceChild(newNode, refElt, getter_AddRefs(nodeOut))))
    return rv;

  return NS_OK;
}

nsresult Control::hideElement(wchar_t *id) { 
  return setElementStyle(id, L"display", L"none");
}

nsresult Control::showElement(wchar_t *id) { 
  return setElementStyle(id, L"display", L"");
}

///////////////////////////////////////////////////////////////////////////////
// Miscellaneous                                                             //
///////////////////////////////////////////////////////////////////////////////

// NEEDS: return value? queuing?
nsresult Control::execJS(wchar_t *expr) {
  PR_Lock(m_mutex);
  puts("Control: punt js");
  PR_Unlock(m_mutex);
  return NS_OK;
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
