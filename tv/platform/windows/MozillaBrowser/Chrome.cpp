#include "MozillaBrowser.h"

///////////////////////////////////////////////////////////////////////////////
// Our methods                                                               //
///////////////////////////////////////////////////////////////////////////////

nsresult Chrome::Create(HWND hwnd, nsIWebBrowser *browser) {
  NS_ENSURE_ARG_POINTER(browser);
  nsresult rv;

  if (m_webBrowser != nsnull)
    return NS_ERROR_ALREADY_INITIALIZED;
  m_webBrowser = browser;
  m_hwnd = hwnd;

  RECT clientArea;
  if (!GetClientRect(m_hwnd, &clientArea))
    return NS_ERROR_FAILURE;
  
  if (NS_FAILED(rv = browser->SetContainerWindow(this)))
    return rv;

  nsCOMPtr<nsIBaseWindow> baseWindow = do_QueryInterface(browser);
  if (NS_FAILED(rv = baseWindow->InitWindow(m_hwnd,
					    nsnull /* parent nsIWidget */,
					    0, 0, /* position */
					    clientArea.right,
					    clientArea.bottom /* size */))) {
    browser->SetContainerWindow(nsnull);
    return rv;
  }
  if (NS_FAILED(rv = baseWindow->Create())) {
    browser->SetContainerWindow(nsnull);
    return rv;
  }

  // Necessary, or it won't show up!
  if (NS_FAILED(rv = baseWindow->SetVisibility(PR_TRUE))) {
    browser->SetContainerWindow(nsnull);
    return rv;
  }
  
  puts("LoadURI");
  nsCOMPtr<nsIWebNavigation> nav = do_QueryInterface(browser);
  if (nav == nsnull) {
    puts("Couldn't get nsIWebNavigation");
    browser->SetContainerWindow(nsnull);
    return rv;
  }
  printf("Got %p\n", (void *)nav);
  if (NS_FAILED(rv = nav->LoadURI(L"http://www.google.com",
				  nsIWebNavigation::LOAD_FLAGS_NONE,
				  nsnull /* referrer */, nsnull /* postData */,
				  nsnull /* headers */))) {
    puts("nav failed");
    browser->SetContainerWindow(nsnull);
    return rv;
  }
#ifdef notdef

  puts("GetContentDOMWindow");
  nsCOMPtr<nsIDOMWindow> domWindow;
  if (NS_FAILED(rv = browser->
		GetContentDOMWindow(getter_AddRefs(domWindow)))) {
    DissociateFromCurrentBrowser();
    return rv;
  }
  printf("Got %p\n", (void *)domWindow);

  puts("GetDocument");
  nsCOMPtr<nsIDOMDocument> domDocument;
  if (NS_FAILED(rv = domWindow->
		GetDocument(getter_AddRefs(domDocument)))) {
    DissociateFromCurrentBrowser();
    return rv;
  }
  printf("Got %p\n", (void *)domDocument);

  puts("QI for htmlDocument");
  nsCOMPtr<nsIDOMHTMLDocument> htmlDocument;
  htmlDocument = do_QueryInterface(htmlDocument);
  printf("Got %p\n", (void *)htmlDocument);

  // Listeners and so on would be registered here.
#endif
  
  return NS_OK;
}

Chrome::~Chrome() {
  // Let the WebBrowser know that we're going away (it doesn't hold a
  // reference to us -- see documentation for SetContainerWindow)
  puts("** Chrome destroyed");
  if (m_webBrowser)
    m_webBrowser->SetContainerWindow(nsnull);
}

nsresult Chrome::recomputeSize(void) {
  RECT clientArea;
  if (!GetClientRect(m_hwnd, &clientArea))
    return NS_ERROR_FAILURE;

  nsCOMPtr<nsIBaseWindow> window = do_QueryInterface(m_webBrowser);
  return window->SetPositionAndSize(0, 0, clientArea.right, clientArea.bottom,
				    PR_TRUE);
}

///////////////////////////////////////////////////////////////////////////////
// nsISupports implementation                                                //
///////////////////////////////////////////////////////////////////////////////
NS_IMPL_ADDREF(Chrome)
NS_IMPL_RELEASE(Chrome)

NS_INTERFACE_MAP_BEGIN(Chrome)
  NS_INTERFACE_MAP_ENTRY_AMBIGUOUS(nsISupports, nsIWebBrowserChrome)
  NS_INTERFACE_MAP_ENTRY(nsIWebBrowserChrome)
  NS_INTERFACE_MAP_ENTRY(nsIEmbeddingSiteWindow)
NS_INTERFACE_MAP_END

///////////////////////////////////////////////////////////////////////////////
// nsIWebBrowserChrome implementation                                        //
///////////////////////////////////////////////////////////////////////////////

NS_IMETHODIMP Chrome::SetStatus(PRUint32 statusType,
				const PRUnichar *status) {
  return NS_OK;
}

NS_IMETHODIMP Chrome::GetWebBrowser(nsIWebBrowser * *aWebBrowser) {
  NS_ENSURE_ARG_POINTER(aWebBrowser);
  *aWebBrowser = m_webBrowser;
  NS_IF_ADDREF(*aWebBrowser);
  return NS_OK;
}

NS_IMETHODIMP Chrome::SetWebBrowser(nsIWebBrowser * aWebBrowser) {
  // I have no idea of the circumstances under which Mozilla would try
  // to do this, but since the semantics of implementing it correctly
  // are confusing, we'll punt.
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP Chrome::GetChromeFlags(PRUint32 *aChromeFlags) {
  NS_ENSURE_ARG_POINTER(aChromeFlags);
  *aChromeFlags = m_chromeFlags;
  return NS_OK;
}

NS_IMETHODIMP Chrome::SetChromeFlags(PRUint32 aChromeFlags) {
  m_chromeFlags = aChromeFlags;
  // Would adjust our window to match the supplied chrome flags here.
  return NS_OK;
}

NS_IMETHODIMP Chrome::DestroyBrowserWindow() {
  // That's up to us. Hope caller doesn't mind.
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP Chrome::SizeBrowserTo(PRInt32 aCX, PRInt32 aCY) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP Chrome::ShowAsModal() {
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP Chrome::IsWindowModal(PRBool *_retval) {
  NS_ENSURE_ARG_POINTER(_retval);
  *_retval = PR_FALSE;
  return NS_OK;
}

NS_IMETHODIMP Chrome::ExitModalEventLoop(nsresult aStatus) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

///////////////////////////////////////////////////////////////////////////////
// nsIEmbeddingSiteWindow implementation                                     //
///////////////////////////////////////////////////////////////////////////////

NS_IMETHODIMP Chrome::SetDimensions(PRUint32 flags, PRInt32 x, PRInt32 y,
				    PRInt32 cx, PRInt32 cy) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP Chrome::GetDimensions(PRUint32 flags, PRInt32 *x, PRInt32 *y,
				    PRInt32 *cx, PRInt32 *cy) {
  if (flags & nsIEmbeddingSiteWindow::DIM_FLAGS_POSITION)
    *x = *y = 0;
  if (flags & nsIEmbeddingSiteWindow::DIM_FLAGS_SIZE_INNER ||
      flags & nsIEmbeddingSiteWindow::DIM_FLAGS_SIZE_OUTER)
    *cx = *cy = 0;
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP Chrome::SetFocus(void) {
  ::SetFocus(m_hwnd);
  return NS_OK;
}

NS_IMETHODIMP Chrome::GetVisibility(PRBool *aVisibility) {
  NS_ENSURE_ARG_POINTER(aVisibility);
  *aVisibility = PR_TRUE;
  return NS_OK;
}

NS_IMETHODIMP Chrome::SetVisibility(PRBool aVisibility) {
  return NS_OK;
}

NS_IMETHODIMP Chrome::GetTitle(PRUnichar * *aTitle) {
  NS_ENSURE_ARG_POINTER(aTitle);
  *aTitle = nsnull;
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP Chrome::SetTitle(const PRUnichar * aTitle) {
  return NS_OK;
}

NS_IMETHODIMP Chrome::GetSiteWindow(void * *aSiteWindow) {
  NS_ENSURE_ARG_POINTER(aSiteWindow);
  * (HWND *)aSiteWindow = m_hwnd;
  return NS_OK;
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
