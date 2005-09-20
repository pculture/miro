#include "MozillaBrowser.h"

///////////////////////////////////////////////////////////////////////////////
// Our methods                                                               //
///////////////////////////////////////////////////////////////////////////////

nsresult Listener::Create(nsIWebBrowser *webBrowser, Control *control) {
  nsresult rv;

  puts("Create");
  printf("wb %p\n", m_webBrowser);
  NS_ENSURE_ARG_POINTER(webBrowser);
  NS_ENSURE_ARG_POINTER(control);

  if (m_webBrowser != nsnull)
    return NS_ERROR_ALREADY_INITIALIZED;

  puts("save");
  // Save our binding
  m_control = control;
  m_webBrowser = do_QueryInterface(webBrowser);

  puts("reg");
  // Register for load progress events
  nsCOMPtr<nsIWebProgressListener>
    progressListener(NS_STATIC_CAST(nsIWebProgressListener*, this));
  nsCOMPtr<nsIWeakReference>
    weakProgress(do_GetWeakReference(progressListener));
  if (NS_FAILED(rv = m_webBrowser->
		AddWebBrowserListener(weakProgress, 
				      NS_GET_IID(nsIWebProgressListener)))) {
    printf("err = %08x\n", rv);
    return rv;
  }

  // Register for URI load events. No need for a weak pointer since
  // the WebBrowser does not addref the pointer; instead it is our
  // responsibility to call SetParentURIContentListener(nsnull) before
  // we die.
  nsCOMPtr<nsIURIContentListener> uriListener
    (NS_STATIC_CAST(nsIURIContentListener*, this));
  if (NS_FAILED(rv = m_webBrowser->SetParentURIContentListener(uriListener))) {
    printf("no love on listener; err = %08x\n", rv);
    return rv;
  }
  
  puts("OK");
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
  printf("OnStartURIOpen\n");
  //  if (NS_FAILED(aURI->GetAsciiSpec(url))) {
  //    fprintf(stderr, "Warning: couldn't get URL for onURLLoad callback.\n");
  //    return NS_OK;
  //  }
  //  printf("URI is %s (length %d)\n", url.get(), url.Length());

  nsEmbedCString url2;
  aURI->GetSpec(url2);
  printf("URI (in utf8, oddly) is %s (length %d)\n", url2.get(), url2.Length());
  nsEmbedCString path;
  aURI->GetPath(path);
  printf("URI path part (utf8) is %s (length %d)\n", path.get(), path.Length());
  
  if (!m_control->onURLLoad(url.get())) {
    puts("Got STOP (FALSE)\n");
    *_retval = TRUE; // Cancel load
  }
  else {
    puts("Got CONTINUE (TRUE)\n");
    *_retval = FALSE; // Allow load to continue
  }
    
  return NS_OK;
}

NS_IMETHODIMP
Listener::DoContent(const char *aContentType, PRBool aIsContentPreferred,
		    nsIRequest *aRequest, nsIStreamListener **aContentHandler,
		    PRBool *_retval) {
  puts("DoContent");
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP
Listener::IsPreferred(const char *aContentType, char **aDesiredContentType,
		      PRBool *_retval) {
  puts("IsPreferred");
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP
Listener::CanHandleContent(const char *aContentType,
			   PRBool aIsContentPreferred,
			   char **aDesiredContentType,
			   PRBool *_retval) {
  puts("CanHandleContent");
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP
Listener::GetLoadCookie(nsISupports **aLoadCookie) {
  puts("GetLoadCookie");
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP
Listener::SetLoadCookie(nsISupports *aLoadCookie) {
  puts("SetLoadCookie");
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP Listener::
GetParentContentListener(nsIURIContentListener **aParentContentListener) {
  puts("GetParentContentListener");
  return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP Listener::
SetParentContentListener(nsIURIContentListener *aParentContentListener) {
  puts("SetParentContentListener");
  return NS_ERROR_NOT_IMPLEMENTED;
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
