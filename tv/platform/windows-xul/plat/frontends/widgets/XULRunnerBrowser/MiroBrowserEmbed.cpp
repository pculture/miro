/*
 * Miro - an RSS based video player application
 * Copyright (C) 2005-2008 Participatory Culture Foundation
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
 *
 * In addition, as a special exception, the copyright holders give
 * permission to link the code of portions of this program with the OpenSSL
 * library.
 *
 * You must obey the GNU General Public License in all respects for all of
 * the code used other than OpenSSL. If you modify file(s) with this
 * exception, you may extend this exception to your version of the file(s),
 * but you are not obligated to do so. If you do not wish to do so, delete
 * this exception statement from your version. If you delete this exception
 * statement from all source files in the program, then also delete it here.
**/

/*
 * MiroBrowserEmbed.cpp
 *
 * Implementation of our embedded xulrunner browser.
 */

#include <windows.h>
#include <Python.h>
#include "nsCOMPtr.h"
#include "nsComponentManagerUtils.h"
#include "nsEmbedCID.h"
#include "nsEmbedString.h"
#include "nsIDOMWindow.h"
#include "nsIInterfaceRequestorUtils.h"
#include "nsISupportsImpl.h"
#include "nsIWebBrowser.h"
#include "nsIWebBrowserFocus.h"
#include "docshell/nsDocShellCID.h"
#include "docshell/nsIDocShellTreeItem.h"
#include "docshell/nsIWebNavigationInfo.h"
#include "necko/nsIURI.h"
#include "xpcom/nsServiceManagerUtils.h"

#include "MiroBrowserEmbed.h"
#include "xulrunnerbrowser.h"
#include "FixFocus.h"

#include <stdio.h>

MiroBrowserEmbed::MiroBrowserEmbed()
{
    mWindow = nsnull;
    mFocusCallback = nsnull;
}

MiroBrowserEmbed::~MiroBrowserEmbed()
{
    log_info("destroying MiroBrowserEmbed");
}

nsresult MiroBrowserEmbed::init(unsigned long parentWindow, int x, 
        int y, int width, int height)
{
    nsresult rv;

    mWebBrowser = do_CreateInstance(NS_WEBBROWSER_CONTRACTID, &rv);
    NS_ENSURE_SUCCESS(rv, rv);
    mWindow = reinterpret_cast<nativeWindow>(parentWindow);

    mWebBrowser->SetContainerWindow(static_cast<nsIWebBrowserChrome*>(this));

    nsCOMPtr<nsIDocShellTreeItem> dsti = do_QueryInterface(mWebBrowser);
    dsti->SetItemType(nsIDocShellTreeItem::typeContentWrapper);

    nsCOMPtr<nsIBaseWindow> browserBaseWindow(do_QueryInterface(mWebBrowser));
    browserBaseWindow->InitWindow(mWindow, nsnull, x, y, width, height);
    browserBaseWindow->Create();
    browserBaseWindow->SetVisibility(PR_TRUE);
    browserBaseWindow->SetEnabled(PR_TRUE);

    install_focus_fixes((HWND)mWindow);
    rv = mWebBrowser->GetParentURIContentListener(
            getter_AddRefs(mParentContentListener));
    NS_ENSURE_SUCCESS(rv, rv);
    rv = mWebBrowser->SetParentURIContentListener(
            static_cast<nsIURIContentListener *>(this));
    NS_ENSURE_SUCCESS(rv, rv);

    nsCOMPtr<nsIWeakReference> weakRef;
    rv = GetWeakReference(getter_AddRefs(weakRef));
    NS_ENSURE_SUCCESS(rv, rv);

    rv = mWebBrowser->AddWebBrowserListener(weakRef,
            NS_GET_IID(nsIWebProgressListener));
    NS_ENSURE_SUCCESS(rv, rv);
    mWebNavigation = do_QueryInterface(mWebBrowser);
    return NS_OK;
}

nsresult MiroBrowserEmbed::disable()
{
    nsresult rv;
    nsCOMPtr<nsIBaseWindow> browserBaseWindow(do_QueryInterface(mWebBrowser));

    rv = browserBaseWindow->SetVisibility(PR_FALSE);
    NS_ENSURE_SUCCESS(rv, rv);
    rv = browserBaseWindow->SetEnabled(PR_FALSE);
    NS_ENSURE_SUCCESS(rv, rv);
    return NS_OK;
}

nsresult MiroBrowserEmbed::enable()
{
    nsresult rv;
    nsCOMPtr<nsIBaseWindow> browserBaseWindow(do_QueryInterface(mWebBrowser));

    rv = browserBaseWindow->SetVisibility(PR_TRUE);
    NS_ENSURE_SUCCESS(rv, rv);
    rv = browserBaseWindow->SetEnabled(PR_TRUE);
    NS_ENSURE_SUCCESS(rv, rv);
    rv = browserBaseWindow->Repaint(PR_FALSE);
    NS_ENSURE_SUCCESS(rv, rv);
    return NS_OK;
}

void MiroBrowserEmbed::destroy()
{
    nsCOMPtr<nsIBaseWindow> browserBaseWindow(do_QueryInterface(mWebBrowser));
    browserBaseWindow->Destroy();
}

// Load a URI into the browser
nsresult MiroBrowserEmbed::loadURI(const char* uri)
{
    mWebNavigation->LoadURI(NS_ConvertASCIItoUTF16(uri).get(),
            nsIWebNavigation::LOAD_FLAGS_NONE, 0, 0, 0);
    return NS_OK;
}

// Called when the parent window changes size
nsresult MiroBrowserEmbed::resize(int x, int y, int width, int height)
{
    nsCOMPtr<nsIBaseWindow>browserBaseWindow(
            do_QueryInterface(mWebBrowser));
    if(!browserBaseWindow) return NS_ERROR_FAILURE;
    return browserBaseWindow->SetPositionAndSize(x, y, width, height,
            PR_TRUE);
}

// Give the browser keyboard focus
nsresult MiroBrowserEmbed::focus()
{
    nsCOMPtr<nsIWebBrowserFocus> browserFocus(
            do_GetInterface(mWebBrowser));
    if(!browserFocus) return NS_ERROR_FAILURE;
    return browserFocus->Activate();
}

// Set the focus callback.  This will be called when the user tabs through all
// the elements in the browser and the next Widget should be given focus.
void MiroBrowserEmbed::SetFocusCallback(focusCallback callback, void* data)
{
    mFocusCallback = callback;
    mFocusCallbackData = data;
}

void MiroBrowserEmbed::SetURICallback(uriCallback callback, void* data)
{
    mURICallback = callback;
    mURICallbackData = data;
}

void MiroBrowserEmbed::SetNetworkCallback(networkCallback callback, void* data)
{
    mNetworkCallback = callback;
    mNetworkCallbackData = data;
}

int MiroBrowserEmbed::canGoBack()
{
    PRBool retval;
    mWebNavigation->GetCanGoBack(&retval);
    return retval;
}

int MiroBrowserEmbed::canGoForward()
{
    PRBool retval;
    mWebNavigation->GetCanGoForward(&retval);
    return retval;
}

void MiroBrowserEmbed::goBack()
{
    mWebNavigation->GoBack();
}

void MiroBrowserEmbed::goForward()
{
    mWebNavigation->GoForward();
}

void MiroBrowserEmbed::stop()
{
    mWebNavigation->Stop(nsIWebNavigation::STOP_ALL);
}

void MiroBrowserEmbed::reload()
{
    mWebNavigation->Reload(nsIWebNavigation::LOAD_FLAGS_NONE);
}

//*****************************************************************************
// MiroBrowserEmbed::nsISupports
//*****************************************************************************   

NS_IMPL_ADDREF(MiroBrowserEmbed)
NS_IMPL_RELEASE(MiroBrowserEmbed)

NS_INTERFACE_MAP_BEGIN(MiroBrowserEmbed)
   NS_INTERFACE_MAP_ENTRY_AMBIGUOUS(nsISupports, nsIWebBrowserChrome)
   NS_INTERFACE_MAP_ENTRY(nsIWebBrowserChrome)
   NS_INTERFACE_MAP_ENTRY(nsIEmbeddingSiteWindow)
   NS_INTERFACE_MAP_ENTRY(nsIInterfaceRequestor)
   NS_INTERFACE_MAP_ENTRY(nsIWebBrowserChromeFocus)
   NS_INTERFACE_MAP_ENTRY(nsIURIContentListener)
   NS_INTERFACE_MAP_ENTRY(nsIWebProgressListener)
   NS_INTERFACE_MAP_ENTRY(nsISupportsWeakReference)
NS_INTERFACE_MAP_END


//*****************************************************************************
// MiroBrowserEmbed::nsIWebBrowserChrome
//*****************************************************************************   

NS_IMETHODIMP MiroBrowserEmbed::SetStatus(PRUint32 aType, const PRUnichar* aStatus)
{

    return NS_OK;
}

NS_IMETHODIMP MiroBrowserEmbed::GetWebBrowser(nsIWebBrowser** aWebBrowser)
{
    NS_ENSURE_ARG_POINTER(aWebBrowser);
    *aWebBrowser = mWebBrowser;
    NS_IF_ADDREF(*aWebBrowser);
    return NS_OK;
}

NS_IMETHODIMP MiroBrowserEmbed::SetWebBrowser(nsIWebBrowser* aWebBrowser)
{
    mWebBrowser = aWebBrowser;
    return NS_OK;
}

NS_IMETHODIMP MiroBrowserEmbed::GetChromeFlags(PRUint32* aChromeMask)
{
    *aChromeMask = mChromeFlags;
    return NS_OK;
}

NS_IMETHODIMP MiroBrowserEmbed::SetChromeFlags(PRUint32 aChromeMask)
{
    mChromeFlags = aChromeMask;
    return NS_OK;
}

NS_IMETHODIMP MiroBrowserEmbed::DestroyBrowserWindow(void)
{
    log_warning("DestroyBrowserWindow() not implemented");
    return NS_OK;
}


// IN: The desired browser client area dimensions.
NS_IMETHODIMP MiroBrowserEmbed::SizeBrowserTo(PRInt32 aWidth, PRInt32 aHeight)
{
  return NS_OK;
}


NS_IMETHODIMP MiroBrowserEmbed::ShowAsModal(void)
{
  mContinueModalLoop = PR_TRUE;
  //AppCallbacks::RunEventLoop(mContinueModalLoop);

  return NS_OK;
}

NS_IMETHODIMP MiroBrowserEmbed::IsWindowModal(PRBool *_retval)
{
    *_retval = PR_FALSE;
    return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP MiroBrowserEmbed::ExitModalEventLoop(nsresult aStatus)
{
  mContinueModalLoop = PR_FALSE;
  return NS_OK;
}


//*****************************************************************************
// MiroBrowserEmbed::nsIWebBrowserChromeFocus
//*****************************************************************************   
NS_IMETHODIMP MiroBrowserEmbed::FocusNextElement()
{
    if(mFocusCallback) mFocusCallback(PR_TRUE, mFocusCallbackData);
    return NS_OK;
}

NS_IMETHODIMP MiroBrowserEmbed::FocusPrevElement()
{
    if(mFocusCallback) mFocusCallback(PR_FALSE, mFocusCallbackData);
    return NS_OK;
}


//*****************************************************************************
// MiroBrowserEmbed::nsIEmbeddingSiteWindow
//*****************************************************************************   

NS_IMETHODIMP MiroBrowserEmbed::SetDimensions(PRUint32 aFlags, PRInt32 x, PRInt32 y, PRInt32 cx, PRInt32 cy)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP MiroBrowserEmbed::GetDimensions(PRUint32 aFlags, PRInt32 *x, PRInt32 *y, PRInt32 *cx, PRInt32 *cy)
{
    if (aFlags & nsIEmbeddingSiteWindow::DIM_FLAGS_POSITION)
    {
        *x = 0;
        *y = 0;
    }
    if (aFlags & nsIEmbeddingSiteWindow::DIM_FLAGS_SIZE_INNER ||
        aFlags & nsIEmbeddingSiteWindow::DIM_FLAGS_SIZE_OUTER)
    {
        *cx = 0;
        *cy = 0;
    }
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* void setFocus (); */
NS_IMETHODIMP MiroBrowserEmbed::SetFocus()
{
    return NS_OK;
}

/* attribute wstring title; */
NS_IMETHODIMP MiroBrowserEmbed::GetTitle(PRUnichar * *aTitle)
{
   NS_ENSURE_ARG_POINTER(aTitle);

   *aTitle = nsnull;
   
   return NS_ERROR_NOT_IMPLEMENTED;
}
NS_IMETHODIMP MiroBrowserEmbed::SetTitle(const PRUnichar * aTitle)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* attribute boolean visibility; */
NS_IMETHODIMP MiroBrowserEmbed::GetVisibility(PRBool * aVisibility)
{
    NS_ENSURE_ARG_POINTER(aVisibility);
    *aVisibility = PR_TRUE;
    return NS_OK;
}
NS_IMETHODIMP MiroBrowserEmbed::SetVisibility(PRBool aVisibility)
{
    return NS_OK;
}

/* attribute nativeSiteWindow siteWindow */
NS_IMETHODIMP MiroBrowserEmbed::GetSiteWindow(void * *aSiteWindow)
{
   NS_ENSURE_ARG_POINTER(aSiteWindow);

   *aSiteWindow = mWindow;
   return NS_OK;
}

//*****************************************************************************
// MiroBrowserEmbed::nsIURIContentListener
//*****************************************************************************   
/* boolean onStartURIOpen (in nsIURI aURI); */
NS_IMETHODIMP MiroBrowserEmbed::OnStartURIOpen(nsIURI *aURI, PRBool *_retval)
{
    nsresult rv;
    nsCAutoString specString;
    *_retval = PR_FALSE;

    rv = aURI->GetSpec(specString);
    NS_ENSURE_SUCCESS(rv, rv);

    // Hmm, the docs seem to suggest that retval should be TRUE if we want to
    // continue the load.  However, it seems like the opposite is actually the
    // case.
    if(mURICallback) {
        if(mURICallback((char*)specString.get(), mURICallbackData) == 0) {
            *_retval = PR_TRUE;
        }
    }
    return NS_OK;
}

/* boolean doContent (in string aContentType, in boolean aIsContentPreferred, in nsIRequest aRequest, out nsIStreamListener aContentHandler); */
NS_IMETHODIMP MiroBrowserEmbed::DoContent(const char *aContentType, PRBool aIsContentPreferred, nsIRequest *aRequest, nsIStreamListener **aContentHandler, PRBool *_retval)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* boolean isPreferred (in string aContentType, out string aDesiredContentType); */
NS_IMETHODIMP MiroBrowserEmbed::IsPreferred(const char *aContentType, char **aDesiredContentType, PRBool *_retval)
{
    // This method was pretty much copied from GtkMozEmbed
    *_retval = PR_FALSE;
    *aDesiredContentType = nsnull;

    if (aContentType) {
        nsCOMPtr<nsIWebNavigationInfo> webNavInfo(
                do_GetService(NS_WEBNAVIGATION_INFO_CONTRACTID));
        if (webNavInfo) {
            PRUint32 canHandle;
            nsresult rv =
                webNavInfo->IsTypeSupported(nsDependentCString(aContentType),
                        mWebNavigation, &canHandle);
            NS_ENSURE_SUCCESS(rv, rv);
            *_retval = (canHandle != nsIWebNavigationInfo::UNSUPPORTED);
        }
    }
    return NS_OK;
}

/* boolean canHandleContent (in string aContentType, in boolean aIsContentPreferred, out string aDesiredContentType); */
NS_IMETHODIMP MiroBrowserEmbed::CanHandleContent(const char *aContentType, PRBool aIsContentPreferred, char **aDesiredContentType, PRBool *_retval)
{
    *_retval = PR_FALSE;
    return NS_OK;
}

/* attribute nsISupports loadCookie; */
NS_IMETHODIMP MiroBrowserEmbed::GetLoadCookie(nsISupports * *aLoadCookie)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}
NS_IMETHODIMP MiroBrowserEmbed::SetLoadCookie(nsISupports * aLoadCookie)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* attribute nsIURIContentListener parentContentListener; */
NS_IMETHODIMP MiroBrowserEmbed::GetParentContentListener(nsIURIContentListener * *aParentContentListener)
{
    *aParentContentListener = mParentContentListener;
    (*aParentContentListener)->AddRef();
    return NS_OK;
}
NS_IMETHODIMP MiroBrowserEmbed::SetParentContentListener(nsIURIContentListener * aParentContentListener)
{
    mParentContentListener = aParentContentListener;
    return NS_OK;
}

//*****************************************************************************
// MiroBrowserEmbed::nsIWebProgressListener
//*****************************************************************************   

/* void onStateChange (in nsIWebProgress aWebProgress, in nsIRequest aRequest, in unsigned long aStateFlags, in nsresult aStatus); */
NS_IMETHODIMP MiroBrowserEmbed::OnStateChange(nsIWebProgress *aWebProgress, nsIRequest *aRequest, PRUint32 aStateFlags, nsresult aStatus)
{
    if((aStateFlags & nsIWebProgressListener::STATE_IS_NETWORK) &&
            mNetworkCallback) {
        if(aStateFlags & nsIWebProgressListener::STATE_START) {
            mNetworkCallback(PR_TRUE, mNetworkCallbackData);
        } else if(aStateFlags & nsIWebProgressListener::STATE_STOP) {
            mNetworkCallback(PR_FALSE, mNetworkCallbackData);
        }
    }
    return NS_OK;
}

/* void onProgressChange (in nsIWebProgress aWebProgress, in nsIRequest aRequest, in long aCurSelfProgress, in long aMaxSelfProgress, in long aCurTotalProgress, in long aMaxTotalProgress); */
NS_IMETHODIMP MiroBrowserEmbed::OnProgressChange(nsIWebProgress *aWebProgress, nsIRequest *aRequest, PRInt32 aCurSelfProgress, PRInt32 aMaxSelfProgress, PRInt32 aCurTotalProgress, PRInt32 aMaxTotalProgress)
{
    return NS_OK;
}

/* void onLocationChange (in nsIWebProgress aWebProgress, in nsIRequest aRequest, in nsIURI aLocation); */
NS_IMETHODIMP MiroBrowserEmbed::OnLocationChange(nsIWebProgress *aWebProgress, nsIRequest *aRequest, nsIURI *aLocation)
{
    return NS_OK;
}

/* void onStatusChange (in nsIWebProgress aWebProgress, in nsIRequest aRequest, in nsresult aStatus, in wstring aMessage); */
NS_IMETHODIMP MiroBrowserEmbed::OnStatusChange(nsIWebProgress *aWebProgress, nsIRequest *aRequest, nsresult aStatus, const PRUnichar *aMessage)
{
    return NS_OK;
}

/* void onSecurityChange (in nsIWebProgress aWebProgress, in nsIRequest aRequest, in unsigned long aState); */
NS_IMETHODIMP MiroBrowserEmbed::OnSecurityChange(nsIWebProgress *aWebProgress, nsIRequest *aRequest, PRUint32 aState)
{
    return NS_OK;
}


//*****************************************************************************
// MiroBrowserEmbed::nsIInterfaceRequestor
//*****************************************************************************   

NS_IMETHODIMP MiroBrowserEmbed::GetInterface(const nsIID &aIID, void** aInstancePtr)
{
    NS_ENSURE_ARG_POINTER(aInstancePtr);

    *aInstancePtr = 0;
    if (aIID.Equals(NS_GET_IID(nsIDOMWindow)))
    {
        if (mWebBrowser)
        {
            return mWebBrowser->GetContentDOMWindow((nsIDOMWindow **) aInstancePtr);
        }
        return NS_ERROR_NOT_INITIALIZED;
    }
    return QueryInterface(aIID, aInstancePtr);
}

void addref(MiroBrowserEmbed* browser)
{
    NS_ADDREF(browser);
}
void release(MiroBrowserEmbed* browser)
{
    NS_RELEASE(browser);
}
