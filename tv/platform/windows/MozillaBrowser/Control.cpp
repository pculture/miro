#include "MozillaBrowser.h"
#include <stdio.h>

nsresult Control::Create(HWND hwnd, wchar_t *initialHTML, wchar_t *userAgent) {
  nsresult rv;

  PR_Lock(m_mutex);

  if (NS_FAILED(rv = startMozilla())) {
    PR_Unlock(m_mutex);
    return rv;
  }
  m_hwnd = hwnd;

  if (NS_FAILED(rv = CreateInstance(NS_WEBBROWSER_CONTRACTID,
				    NS_GET_IID(nsIWebBrowser),
				    getter_AddRefs(m_webBrowser)))) {
    PR_Unlock(m_mutex);
    return rv;
  }

  m_chrome = new Chrome();
  if (NS_FAILED(rv = m_chrome->Create(hwnd, m_webBrowser))) {
    PR_Unlock(m_mutex);
    return rv;
  }

  // NEEDS: load initialHTML, set userAgent :)
  // hook callbacks
  
  PR_Unlock(m_mutex);
  return NS_OK;
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

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
