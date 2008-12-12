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

#include "MiroWindowCreator.h"
#include "nsCOMPtr.h"
#include "xulrunnerbrowser.h"
#include "nsIWebBrowserChrome.h"
#include "nsIWindowWatcher.h"
#include "necko/nsIURI.h"
#include "xpcom/nsServiceManagerUtils.h"

NS_IMPL_ISUPPORTS2(MiroWindowCreator, nsIWindowCreator, nsIWindowCreator2)

MiroWindowCreator::MiroWindowCreator()
{
    this->AddRef();
    // This isn't ideal, but there's something screwy about calling AddRef
    // from Pyrex.  Besides, we only create 1 MiroWindowCreator and never
    // destroy it, so it's not that bad.
}

MiroWindowCreator::~MiroWindowCreator()
{
}

nsresult MiroWindowCreator::install()
{
    nsresult rv;
    nsCOMPtr<nsIWindowWatcher> window_watcher(
                do_GetService(NS_WINDOWWATCHER_CONTRACTID, &rv));
    NS_ENSURE_SUCCESS(rv, rv);

    rv = window_watcher->SetWindowCreator(this);
    NS_ENSURE_SUCCESS(rv, rv);
    return rv;
}

void MiroWindowCreator::SetNewWindowCallback(windowCallback callback, void* data)
{
    mWindowCallback = callback;
    mWindowCallbackData = data;
}

NS_IMETHODIMP MiroWindowCreator::CreateChromeWindow(nsIWebBrowserChrome
        *parent, PRUint32 chrameFlags, nsIWebBrowserChrome **__retval)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

NS_IMETHODIMP MiroWindowCreator::CreateChromeWindow2(
        nsIWebBrowserChrome *parent, PRUint32 chromeFlags, 
        PRUint32 contextFlags, nsIURI *uri, PRBool *cancel,
        nsIWebBrowserChrome **_retval)
{
    nsCAutoString specString;
    if((chromeFlags & nsIWebBrowserChrome::CHROME_OPENAS_CHROME) == 0) {
        if(uri) {
            uri->GetSpec(specString);
            if(mWindowCallback) {
                mWindowCallback((char*)specString.get(), mWindowCallbackData);
            }
        } else {
            log_warning("Trying to open window with no URI");
        }
    }

    *cancel = PR_TRUE;
    *_retval = nsnull;
    return NS_OK;
}
