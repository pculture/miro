/*
 * HttpObserver.cc
 *
 * Watches http requests as they are created and adds an X-Miro header.
 */

// NOTE: we could have code to register the class with XPCOM, but since we
// only construct it from inside democracy, there's no need.

#define MOZILLA_INTERNAL_API
#include "HttpObserver.h"
#include <nscore.h>
#include <nsCOMPtr.h>
#include <nsIServiceManagerUtils.h>
#include <nsIHttpChannel.h>
#include <nsIObserver.h>
#include <nsIObserverService.h>
#include <nsString.h>

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
        nsCOMPtr<nsIHttpChannel> channel(do_QueryInterface(subject, &rv));
        if(NS_FAILED(rv)) return rv;
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
