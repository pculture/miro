/*
 * Miro - an RSS based video player application
 * Copyright (C) 2005-2007 Participatory Culture Foundation
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
*/

/*
 * HttpObserver.cc
 *
 * Watches http requests as they are created and adds an X-Miro header.
 */

// NOTE: we could have code to register the class with XPCOM, but since we
// only construct it from inside miro, there's no need.

#define MOZILLA_INTERNAL_API
#include "HttpObserver.h"
#include <nscore.h>
#include <nsCOMPtr.h>
#ifdef NS_I_SERVICE_MANAGER_UTILS
#include <nsIServiceManagerUtils.h>
#else
#include <nsServiceManagerUtils.h>
#endif
#include <nsIHttpChannel.h>
#include <nsIObserver.h>
#include <nsIObserverService.h>
#include <nsString.h>
#include <locale.h>

class HttpObserver: public nsIObserver {     
public:   
  HttpObserver();   
  virtual ~HttpObserver();   
  NS_IMETHOD Observe(nsISupports *subject, const char *topic, 
          const PRUnichar *data);
 
  NS_DECL_ISUPPORTS 
};   
 
HttpObserver::HttpObserver()   
{   
}   
HttpObserver::~HttpObserver()   
{   
}   
 
NS_IMPL_ISUPPORTS2(HttpObserver, nsISupports, nsIObserver); 

nsresult HttpObserver::Observe(nsISupports *subject, const char *topic,
        const PRUnichar *data)
{
    if(strcmp(topic, "http-on-modify-request") == 0) {
        nsresult rv;
        nsDependentCString locale, currentLanguages;
        nsDependentCString language = nsDependentCString("");
        PRUint32 sep;
        nsCOMPtr<nsIHttpChannel> channel(do_QueryInterface(subject, &rv));
        if(NS_FAILED(rv)) return rv;
        channel->GetRequestHeader(nsDependentCString("Accept-Language"), currentLanguages);
        locale = nsDependentCString(setlocale(LC_ALL, NULL));
        sep = locale.FindChar('.');
        locale.Left(language, sep);
        language.ReplaceChar('_', '-');
        channel->SetRequestHeader(nsDependentCString("Accept-Language"),
                language, false);
        channel->SetRequestHeader(nsDependentCString("Accept-Language"),
                currentLanguages, true);
        channel->SetRequestHeader(nsDependentCString("X-Miro"), 
                nsDependentCString("1"), false);
    }
    return NS_OK;
}

nsresult startObserving()
{
    nsresult rv;

    nsCOMPtr<nsIObserverService> observerService(do_GetService(
                "@mozilla.org/observer-service;1", &rv));
    if(NS_FAILED(rv)) return rv;

    HttpObserver* observer = new HttpObserver();
    rv = observerService->AddObserver(observer, "http-on-modify-request",
            false);
    return rv;
}
