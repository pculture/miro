/*
# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.
*/

/*
 * HttpObserver.cc
 *
 * Watches http requests as they are created and adds an X-Miro header.
 */

// NOTE: we could have code to register the class with XPCOM, but since we
// only construct it from inside miro, there's no need.

#ifndef PCF_USING_XULRUNNER19
#define MOZILLA_INTERNAL_API
#endif

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

#ifndef PCF_USING_XULRUNNER19
#include <nsString.h>
#else
#include <nsStringAPI.h>
#endif

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
#ifndef PCF_USING_XULRUNNER19
        nsDependentCString locale, currentLanguages;
        nsDependentCString language = nsDependentCString("");
#else
        nsDependentCString locale(setlocale(LC_ALL, NULL)), currentLanguages;
#endif

        PRUint32 sep;
        nsCOMPtr<nsIHttpChannel> channel(do_QueryInterface(subject, &rv));
        if(NS_FAILED(rv)) return rv;
        channel->GetRequestHeader(nsDependentCString("Accept-Language"), currentLanguages);
#ifndef PCF_USING_XULRUNNER19
        locale = nsDependentCString(setlocale(LC_ALL, NULL));
#endif
        sep = locale.FindChar('.');
#ifndef PCF_USING_XULRUNNER19
        locale.Left(language, sep);
        language.ReplaceChar('_', '-');
#else
        nsDependentCSubstring languageSub = StringHead(locale, sep);

        nsCString language(languageSub);
        char* cstr = ToNewCString(language);
        char* i = cstr;
        while (*i++) {
            if (*i == '_')
                *i = '-';
        }
        language = cstr;
        NS_Free(cstr);
#endif
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
