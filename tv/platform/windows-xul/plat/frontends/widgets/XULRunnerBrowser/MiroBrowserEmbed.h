/*
 * Miro - an RSS based video player application
 * Copyright (C) 2005-2009 Participatory Culture Foundation
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
 * MiroBrowserEmbed.h
 *
 * Public interface for our embedded xulrunner browser.  MiroBrowserEmbed
 * serves 2 functions.  It provides an XPCOM interface for XULRunner to hook
 * up to.  It also provides a C++ interface that the .pyx file uses to
 * controll the browser and to hook up callbacks to it.
 */

#ifndef __PCF_MIRO_BROWSER_EMBED_H__
#define __PCF_MIRO_BROWSER_EMBED_H__

#include "nsCOMPtr.h"
#include "nsIWebBrowserChrome.h"
#include "nsIEmbeddingSiteWindow.h"
#include "nsIWebBrowser.h"
#include "nsIInterfaceRequestor.h"
#include "nsIWebBrowserChromeFocus.h"
#include "docshell/nsIWebNavigation.h"
#include "widget/nsIBaseWindow.h"
#include "uriloader/nsIURIContentListener.h"
#include "uriloader/nsIWebProgressListener.h"
#include "xpcom/nsWeakReference.h"
#include "shistory/nsIHistoryEntry.h"
#include "shistory/nsISHistory.h"

typedef void(*focusCallback)(PRBool forward, void* data);
typedef int(*uriCallback)(char* uri, void* data);
typedef void(*networkCallback)(PRBool is_start, void* data);

class MiroBrowserEmbed   : public nsIWebBrowserChrome,
                           public nsIWebBrowserChromeFocus,
                           public nsIEmbeddingSiteWindow,
                           public nsIInterfaceRequestor,
                           public nsIURIContentListener,
                           public nsIWebProgressListener,
                           public nsSupportsWeakReference

{
public:
    MiroBrowserEmbed();
    virtual ~MiroBrowserEmbed();

    /*
     * Methods from the XPCOM interfaces we implement.  These are proiveded
     * for XULRunner.
     */

    NS_DECL_ISUPPORTS
    NS_DECL_NSIWEBBROWSERCHROME
    NS_DECL_NSIEMBEDDINGSITEWINDOW
    NS_DECL_NSIINTERFACEREQUESTOR
    NS_DECL_NSIWEBBROWSERCHROMEFOCUS
    NS_DECL_NSIURICONTENTLISTENER
    NS_DECL_NSIWEBPROGRESSLISTENER

    /*
     * Methods to interact with the MiroBrowserEmbed from Cython.  These are
     * called by Miro.
     */

    // Create a WebBrowser object and place it inside parentWindow.  This must
    // be called before any other methods.  
    nsresult init(unsigned long parentWindow, int x, int y, int width, 
            int height);
    // Stop the browser from painting to the screen or handling input
    nsresult disable();
    // Startup the browser again after a call to disable()
    nsresult enable();
    // Load a URI into the browser
    nsresult loadURI(const char* uri);
    // Gets the current uri from mWebNavigator
    nsresult getCurrentURI(char ** uri);
    // Gets the current title from a long chain of things
    nsresult getCurrentTitle(wchar_t ** aTitle);
    // Call when the parent window changes size
    nsresult resize(int x, int y, int width, int height);
    // Give the browser keyboard focus
    nsresult focus();
    // Browser Navigation buttons.  Their functionality corresponds to the
    // nsIWebNavigation interface
    int canGoBack();
    int canGoForward();
    void goBack();
    void goForward();
    void stop();
    void reload();
    // Set the focus callback.  This will be called when the user tabs through
    // all the elements in the browser and the next Widget should be given
    // focus.
    void SetFocusCallback(focusCallback callback, void* data);
    // Set the URI callback.  This well be called when we are about to load a
    // new URI.  It should return 0 if the URI shouldn't be loaded.
    void SetURICallback(uriCallback callback, void* data);
    // Set the Network callback.  This is called when we start loading a
    // document and when all network activity for a document is finished
    // new URI.  It should return 0 if the URI shouldn't be loaded.
    void SetNetworkCallback(networkCallback callback, void* data);
    // Destroy the broswer
    void destroy();

protected:
    nativeWindow mWindow;
    PRUint32     mChromeFlags;
    PRBool       mContinueModalLoop;
    focusCallback mFocusCallback;
    uriCallback mURICallback;
    networkCallback mNetworkCallback;
    void* mFocusCallbackData;
    void* mURICallbackData;
    void* mNetworkCallbackData;

    nsCOMPtr<nsIWebBrowser> mWebBrowser;
    nsCOMPtr<nsIWebNavigation> mWebNavigation;
    nsCOMPtr<nsIURIContentListener> mParentContentListener;
    PRBool is_enabled();
};

/* Couple of utility functions, since the XPCOM Macros don't seem to work from
 * Cython.
 */
void addref(MiroBrowserEmbed* browser);
void release(MiroBrowserEmbed* browser);

#endif /* __PCF_MIRO_BROWSER_EMBED_H__ */
