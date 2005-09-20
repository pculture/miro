#include "MozillaBrowser.h"
#include <stdio.h>

Control::~Control() {
  puts("** Control destroyed.");
  PR_DestroyLock(m_mutex);
  if (m_initialHTML)
    delete[] m_initialHTML;
  m_initialHTML = NULL;
}

nsresult Control::Create(HWND hwnd, wchar_t *initialHTML, wchar_t *userAgent) {
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
  
  // Save the initial HTML until the load finishes and we can push it is
  // with document.write.
  wchar_t *effectiveInitialHTML = initialHTML ? initialHTML : L"";
  int initialHTML_len = wcslen(effectiveInitialHTML) + 1;
  m_initialHTML = new wchar_t[initialHTML_len];
  wmemcpy(m_initialHTML, effectiveInitialHTML, initialHTML_len);

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

  // Load a blank html document to force the creation of
  // nsIDOMHTMLDocument. Use a file: URL instead of, eg, chrome: to
  // ensure that the document we subsequently construct has no special
  // privileges. Use an empty file instead of about:blank because the
  // latter actually has tags for a null head and body.
  puts("LoadURI");
  nav = do_QueryInterface(m_webBrowser);
  if (nav == nsnull)
    goto done;
  printf("Got %p\n", (void *)nav);
  // documentLoadFinished may have already been called by the time this
  // function returns. In fact for a file it's likely.
  // NEEDS: make checkin-safe
  //  if (NS_FAILED(rv = nav->LoadURI(L"file://c:/tmp/blank.html",
  if (NS_FAILED(rv = nav->LoadURI(L"http://www.google.com",
				  nsIWebNavigation::LOAD_FLAGS_NONE,
				  nsnull /* referrer */, nsnull /* postData */,
				  nsnull /* headers */)))
    goto done;
  puts("Back from loaduri");

  if (userAgent) {
    // NEEDS: set userAgent :)
  }

  rv = NS_OK;

 done:
  PR_Unlock(m_mutex);
  return rv;
}

// NEEDS: return value? queuing?
nsresult Control::execJS(wchar_t *expr) {
  PR_Lock(m_mutex);
  puts("Control: punt js");
  PR_Unlock(m_mutex);
  return NS_OK;
}

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

void Control::documentLoadFinished(void) {
  nsresult rv;
  nsCOMPtr<nsIDOMWindow> domWindow;
  nsCOMPtr<nsIDOMDocument> domDocument;
  nsCOMPtr<nsIDOMHTMLDocument> htmlDocument;

  PR_Lock(m_mutex);
  puts("documentLoadFinished");
  printf("m_initialHTML = %p\n", m_initialHTML);
  
  if (!m_initialHTML)
    goto done;
  puts("I'm glad I can at least test it for truth.");
  
  puts("GetContentDOMWindow");
  if (NS_FAILED(rv = m_webBrowser->
		GetContentDOMWindow(getter_AddRefs(domWindow)))) {
    puts("fail!");
    goto done;
  }
  printf("Got %p\n", (void *)domWindow);

  puts("GetDocument");
  if (NS_FAILED(rv = domWindow->
		GetDocument(getter_AddRefs(domDocument)))) {
    puts("fail!");    
    goto done;
  }
  printf("Got %p\n", (void *)domDocument);

  puts("QI for htmlDocument");
  htmlDocument = do_QueryInterface(htmlDocument);
  printf("Got %p\n", (void *)htmlDocument);
  if (htmlDocument == nsnull) {
    puts("fail!");
    goto done;
  }

  puts("doc->write");
  if (NS_FAILED(rv = htmlDocument->Write(nsEmbedString(m_initialHTML)))) {
    puts("fail!");
    goto done;
  }
  puts("sweet it is");

 done:
  puts("at done:");
  if (m_initialHTML) {
    puts("try to delete");
    delete[] m_initialHTML;
  }
  m_initialHTML = NULL;
  PR_Unlock(m_mutex);
  puts("post mutex, return");
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
