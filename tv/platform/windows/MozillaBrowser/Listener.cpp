#include "MozillaBrowser.h"

///////////////////////////////////////////////////////////////////////////////
// Our methods                                                               //
///////////////////////////////////////////////////////////////////////////////

nsresult Listener::Create(nsIWebBrowser *webBrowser, Control *control) {
  nsresult rv;

  NS_ENSURE_ARG_POINTER(webBrowser);
  NS_ENSURE_ARG_POINTER(control);

  if (m_webBrowser != nsnull)
    return NS_ERROR_ALREADY_INITIALIZED;

  // Save our binding
  m_control = control;
  m_webBrowser = do_QueryInterface(webBrowser);

  // Register for load progress events
  nsCOMPtr<nsIWebProgressListener>
    progressListener(NS_STATIC_CAST(nsIWebProgressListener*, this));
  nsCOMPtr<nsIWeakReference>
    weakProgress(do_GetWeakReference(progressListener));
  if (NS_FAILED(rv = m_webBrowser->
		AddWebBrowserListener(weakProgress, 
				      NS_GET_IID(nsIWebProgressListener))))
    return rv;

  // Register for URI load events. No need for a weak pointer since
  // the WebBrowser does not addref the pointer; instead it is our
  // responsibility to call SetParentURIContentListener(nsnull) before
  // we die.
  nsCOMPtr<nsIURIContentListener> uriListener
    (NS_STATIC_CAST(nsIURIContentListener*, this));
  if (NS_FAILED(rv = m_webBrowser->SetParentURIContentListener(uriListener)))
    return rv;
  
  return NS_OK;
}

Listener::~Listener() {
  puts("** Listener destroyed");
  if (m_webBrowser)
    m_webBrowser->SetParentURIContentListener(nsnull);
}    

///////////////////////////////////////////////////////////////////////////////
// nsISupports implementation                                                //
///////////////////////////////////////////////////////////////////////////////

NS_IMPL_ADDREF(Listener)
NS_IMPL_RELEASE(Listener)

NS_INTERFACE_MAP_BEGIN(Listener)
  NS_INTERFACE_MAP_ENTRY_AMBIGUOUS(nsISupports, nsIWebProgressListener)
  NS_INTERFACE_MAP_ENTRY(nsIWebProgressListener)
  NS_INTERFACE_MAP_ENTRY(nsIURIContentListener)
  NS_INTERFACE_MAP_ENTRY(nsISupportsWeakReference)
NS_INTERFACE_MAP_END

///////////////////////////////////////////////////////////////////////////////
// nsIWebProgressListener implementation                                     //
///////////////////////////////////////////////////////////////////////////////

NS_IMETHODIMP
Listener::OnStateChange(nsIWebProgress *aWebProgress, nsIRequest *aRequest,
			PRUint32 aStateFlags, nsresult aStatus) {
  if (aStateFlags & STATE_IS_DOCUMENT) {
    if (aStateFlags & STATE_START) {
      // Load of top-level document began
    }

    if (aStateFlags & STATE_STOP) {
      // Load of top-level document finished
      m_control->onDocumentLoadFinished();
    }
  }

  return NS_OK;
}

NS_IMETHODIMP
Listener::OnProgressChange(nsIWebProgress *aWebProgress, nsIRequest *aRequest,
			   PRInt32 aCurSelfProgress, PRInt32 aMaxSelfProgress,
			   PRInt32 aCurTotalProgress,
			   PRInt32 aMaxTotalProgress) {
  return NS_OK;
}

NS_IMETHODIMP
Listener::OnLocationChange(nsIWebProgress *aWebProgress, nsIRequest *aRequest,
			   nsIURI *aLocation) {
  return NS_OK;
}

NS_IMETHODIMP
Listener::OnStatusChange(nsIWebProgress *aWebProgress, nsIRequest *aRequest,
			 nsresult aStatus, const PRUnichar *aMessage) {
  return NS_OK;
}

NS_IMETHODIMP
Listener::OnSecurityChange(nsIWebProgress *aWebProgress, nsIRequest *aRequest,
			   PRUint32 aState) {
  return NS_OK;
}

///////////////////////////////////////////////////////////////////////////////
// nsIURIContentHandler implementation                                       //
///////////////////////////////////////////////////////////////////////////////

NS_IMETHODIMP
Listener::OnStartURIOpen(nsIURI *aURI, PRBool *_retval) {
  nsEmbedCString url;
  if (NS_FAILED(aURI->GetAsciiSpec(url))) {
    fprintf(stderr, "Warning: couldn't get URL for onURLLoad callback.\n");
    return NS_OK;
  }
  
  if (!m_control->onURLLoad(url.get())) {
    *_retval = TRUE; // Cancel load
  }
  else {
    *_retval = FALSE; // Allow load to continue
    // Doing this seems to cause Mozilla to load the document
    // normally, complete with appropriate OnStateChange messages, and
    // then not bother to display the document. I suspect we need to
    // paste some of the code in embedding/browser/webBrowser/ (?)
    // into DoContent instead of just returning
    // NS_ERROR_NOT_IMPLEMENTED.  But this doesn't actually matter to
    // us for now.
  }
    
  return NS_OK;
}

NS_IMETHODIMP
Listener::DoContent(const char *aContentType, PRBool aIsContentPreferred,
		    nsIRequest *aRequest, nsIStreamListener **aContentHandler,
		    PRBool *_retval) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP
Listener::IsPreferred(const char *aContentType, char **aDesiredContentType,
		      PRBool *_retval) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP
Listener::CanHandleContent(const char *aContentType,
			   PRBool aIsContentPreferred,
			   char **aDesiredContentType,
			   PRBool *_retval) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP
Listener::GetLoadCookie(nsISupports **aLoadCookie) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP
Listener::SetLoadCookie(nsISupports *aLoadCookie) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP Listener::
GetParentContentListener(nsIURIContentListener **aParentContentListener) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP Listener::
SetParentContentListener(nsIURIContentListener *aParentContentListener) {
  return NS_ERROR_NOT_IMPLEMENTED;
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
