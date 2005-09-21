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

  printf("chrome %p listener %p\n", m_chrome, m_listener);
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
  puts("new Chrome");
  m_chrome = new Chrome();
  puts("grabbing a ref");
  printf("m_chrome = %p\n", m_chrome);
  nsISupports *nsI = NS_ISUPPORTS_CAST(nsIWebBrowserChrome *, m_chrome);
  printf("nsI = %p\n", nsI);
  m_ref_chrome = do_QueryInterface(nsI);
  printf("m_ref_chrome = %p\n", m_ref_chrome);
  
  m_ref_chrome =
    do_QueryInterface( NS_ISUPPORTS_CAST(nsIWebBrowserChrome *, m_chrome));
  puts("create");
  if (NS_FAILED(rv = m_chrome->Create(hwnd, m_webBrowser)))
    goto done;
  puts("all's good in the hood");
  
  // Create one of our Listeners, pointed at us, and hooked up to the
  // browser, in order that we receive event callbacks. IMPORTANT: make
  // sure the class is sufficiently initialized that we are fully prepared
  // for any callbacks before we do this.
  puts("create listener");
  Listener *listener = new Listener();
  puts("did it");
  // It's important to hold a reference across the call :)
  m_listener =
    do_QueryInterface(NS_ISUPPORTS_CAST(nsIWebProgressListener *, listener));
  puts("qi'd");
  if (NS_FAILED(rv = listener->Create(m_webBrowser, this)))
    goto done;
  puts("created");

  // Load the URL given, or a blank page if omitted.
  wchar_t *url = initialURL ? initialURL : L"about:blank";
  nav = do_QueryInterface(m_webBrowser);
  if (nav == nsnull)
    goto done;
  printf("Got %p\n", (void *)nav);
  // documentLoadFinished may have already been called by the time this
  // function returns. In fact for a file it's likely.
  printf("About to LoadURI: '%S' (len %d)\n", url, wcslen(url));
  if (NS_FAILED(rv = nav->LoadURI(url,
				  nsIWebNavigation::LOAD_FLAGS_NONE,
				  nsnull /* referrer */, nsnull /* postData */,
				  nsnull /* headers */))) {
    printf("LoadURI failed with %08x\n", rv);
    goto done;
  }
  puts("Back from loaduri");

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

  return doc->GetElementById(nsEmbedString(id), _retval);
}
  
nsresult Control::addElementAtEnd(wchar_t *xml, wchar_t *id) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

nsresult Control::addElementBefore(wchar_t *xml, wchar_t *id) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

nsresult Control::removeElement(wchar_t *id) {
  nsresult rv;

  nsCOMPtr<nsIDOMElement> elt;
  if (NS_FAILED(rv = getElementById(id, getter_AddRefs(elt))))
    return rv;
  printf("remove: got %p for elt\n", elt);
  return NS_OK; // NEEDS
}

nsresult Control::changeElement(wchar_t *id, wchar_t *xml) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

nsresult Control::hideElement(wchar_t *id) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

nsresult Control::showElement(wchar_t *id) { 
  return NS_ERROR_NOT_IMPLEMENTED;
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
