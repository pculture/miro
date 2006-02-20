/*
 * DO NOT EDIT.  THIS FILE IS GENERATED FROM c:/moz/mozilla/docshell/base/nsIWebNavigation.idl
 */

#ifndef __gen_nsIWebNavigation_h__
#define __gen_nsIWebNavigation_h__


#ifndef __gen_nsISupports_h__
#include "nsISupports.h"
#endif

/* For IDL files that don't want to include root IDL files. */
#ifndef NS_NO_VTABLE
#define NS_NO_VTABLE
#endif
class nsIDOMDocument; /* forward declaration */

class nsIInputStream; /* forward declaration */

class nsISHistory; /* forward declaration */

class nsISHEntry; /* forward declaration */

class nsIURI; /* forward declaration */


/* starting interface:    nsIWebNavigation */
#define NS_IWEBNAVIGATION_IID_STR "f5d9e7b0-d930-11d3-b057-00a024ffc08c"

#define NS_IWEBNAVIGATION_IID \
  {0xf5d9e7b0, 0xd930, 0x11d3, \
    { 0xb0, 0x57, 0x00, 0xa0, 0x24, 0xff, 0xc0, 0x8c }}

class NS_NO_VTABLE nsIWebNavigation : public nsISupports {
 public: 

  NS_DEFINE_STATIC_IID_ACCESSOR(NS_IWEBNAVIGATION_IID)

  /**
  * Indicates if the object can go back.  If true this indicates that
  * there is back session history available for navigation.
  */
  /* readonly attribute boolean canGoBack; */
  NS_IMETHOD GetCanGoBack(PRBool *aCanGoBack) = 0;

  /**
  * Indicates if the object can go forward.  If true this indicates that
  * there is forward session history available for navigation
  */
  /* readonly attribute boolean canGoForward; */
  NS_IMETHOD GetCanGoForward(PRBool *aCanGoForward) = 0;

  /**
  * Tells the object to navigate to the previous session history item.  When
  * a page is loaded from session history, all content is loaded from the
  * cache (if available) and page state (such as form values, scroll position)
  * is restored.
  *
  * @return NS_OK               - Backward navigation was successful.
  *         NS_ERROR_UNEXPECTED - This call was unexpected at this time.  Most
  *                               likely you can't go back right now.
  */
  /* void goBack (); */
  NS_IMETHOD GoBack(void) = 0;

  /**
  * Tells the object to navigate to the next Forward session history item.
  * When a page is loaded from session history, all content is loaded from
  * the cache (if available) and page state (such as form values, scroll
  * position) is restored.
  *
  * @return NS_OK               - Forward was successful.
  *         NS_ERROR_UNEXPECTED - This call was unexpected at this time.  Most
  *                               likely you can't go forward right now.
  */
  /* void goForward (); */
  NS_IMETHOD GoForward(void) = 0;

  /**
  * Tells the object to navigate to the session history item at index.
  *
  * @return NS_OK -               GotoIndex was successful.
  *         NS_ERROR_UNEXPECTED - This call was unexpected at this time.  Most
  *                               likely you can't goto that index
  */
  /* void gotoIndex (in long index); */
  NS_IMETHOD GotoIndex(PRInt32 index) = 0;

  /**
  * Load flags for use with loadURI() and reload()
  */
  enum { LOAD_FLAGS_MASK = 65535U };

  /**
  * loadURI() specific flags
  */
/**
  * Normal load flag.
  */
  enum { LOAD_FLAGS_NONE = 0U };

  /**
  * Meta-refresh flag.  The cache is bypassed.  This type of load is
  *                     usually the result of a meta-refresh tag, or a HTTP
  *                     'refresh' header.
  */
  enum { LOAD_FLAGS_IS_REFRESH = 16U };

  /**
  * Link-click flag. 
  */
  enum { LOAD_FLAGS_IS_LINK = 32U };

  /**
  * Bypass history flag.
  */
  enum { LOAD_FLAGS_BYPASS_HISTORY = 64U };

  /**
  * Replace history entry flag.
  */
  enum { LOAD_FLAGS_REPLACE_HISTORY = 128U };

  enum { LOAD_FLAGS_BYPASS_CACHE = 256U };

  enum { LOAD_FLAGS_BYPASS_PROXY = 512U };

  enum { LOAD_FLAGS_CHARSET_CHANGE = 1024U };

  /**
  * Loads a given URI.  This will give priority to loading the requested URI
  * in the object implementing	this interface.  If it can't be loaded here
  * however, the URL dispatcher will go through its normal process of content
  * loading.
  *
  * @param uri       - The URI string to load.
  * @param loadFlags - Flags modifying load behaviour. Generally you will pass
  *                    LOAD_FLAGS_NONE for this parameter.
  * @param referrer  - The referring URI.  If this argument is NULL, the
  *                    referring URI will be inferred internally.
  * @param postData  - nsIInputStream containing POST data for the request.
  */
  /* void loadURI (in wstring uri, in unsigned long loadFlags, in nsIURI referrer, in nsIInputStream postData, in nsIInputStream headers); */
  NS_IMETHOD LoadURI(const PRUnichar *uri, PRUint32 loadFlags, nsIURI *referrer, nsIInputStream *postData, nsIInputStream *headers) = 0;

  /**
  * Tells the Object to reload the current page.
  *
  * @param reloadFlags - Flags modifying reload behaviour. Generally you will
  *                      pass LOAD_FLAGS_NONE for this parameter.
  */
  /* void reload (in unsigned long reloadFlags); */
  NS_IMETHOD Reload(PRUint32 reloadFlags) = 0;

  /**
  * Stop() flags:
  */
/**
  * Stop all network activity.  This includes both active network loads and
  * pending meta-refreshes.
  */
  enum { STOP_NETWORK = 1U };

  /**
  * Stop all content activity.  This includes animated images, plugins and
  * pending Javascript timeouts.
  */
  enum { STOP_CONTENT = 2U };

  /**
  * Stop all activity.
  */
  enum { STOP_ALL = 3U };

  /**
  * Stops a load of a URI.
  *
  * @param stopFlags - Flags indicating the stop behavior.
  */
  /* void stop (in unsigned long stopFlags); */
  NS_IMETHOD Stop(PRUint32 stopFlags) = 0;

  /**
  * Retrieves the current DOM document for the frame, or lazily creates a
  * blank document if there is none. This attribute never returns null except
  * for unexpected error situations.
  */
  /* readonly attribute nsIDOMDocument document; */
  NS_IMETHOD GetDocument(nsIDOMDocument * *aDocument) = 0;

  /**
  * The currently loaded URI or null.
  */
  /* readonly attribute nsIURI currentURI; */
  NS_IMETHOD GetCurrentURI(nsIURI * *aCurrentURI) = 0;

  /**
  * The referring URI.
  */
  /* readonly attribute nsIURI referringURI; */
  NS_IMETHOD GetReferringURI(nsIURI * *aReferringURI) = 0;

  /**
  * The session history object used to store the session history for the
  * session.
  */
  /* attribute nsISHistory sessionHistory; */
  NS_IMETHOD GetSessionHistory(nsISHistory * *aSessionHistory) = 0;
  NS_IMETHOD SetSessionHistory(nsISHistory * aSessionHistory) = 0;

};

/* Use this macro when declaring classes that implement this interface. */
#define NS_DECL_NSIWEBNAVIGATION \
  NS_IMETHOD GetCanGoBack(PRBool *aCanGoBack); \
  NS_IMETHOD GetCanGoForward(PRBool *aCanGoForward); \
  NS_IMETHOD GoBack(void); \
  NS_IMETHOD GoForward(void); \
  NS_IMETHOD GotoIndex(PRInt32 index); \
  NS_IMETHOD LoadURI(const PRUnichar *uri, PRUint32 loadFlags, nsIURI *referrer, nsIInputStream *postData, nsIInputStream *headers); \
  NS_IMETHOD Reload(PRUint32 reloadFlags); \
  NS_IMETHOD Stop(PRUint32 stopFlags); \
  NS_IMETHOD GetDocument(nsIDOMDocument * *aDocument); \
  NS_IMETHOD GetCurrentURI(nsIURI * *aCurrentURI); \
  NS_IMETHOD GetReferringURI(nsIURI * *aReferringURI); \
  NS_IMETHOD GetSessionHistory(nsISHistory * *aSessionHistory); \
  NS_IMETHOD SetSessionHistory(nsISHistory * aSessionHistory); 

/* Use this macro to declare functions that forward the behavior of this interface to another object. */
#define NS_FORWARD_NSIWEBNAVIGATION(_to) \
  NS_IMETHOD GetCanGoBack(PRBool *aCanGoBack) { return _to GetCanGoBack(aCanGoBack); } \
  NS_IMETHOD GetCanGoForward(PRBool *aCanGoForward) { return _to GetCanGoForward(aCanGoForward); } \
  NS_IMETHOD GoBack(void) { return _to GoBack(); } \
  NS_IMETHOD GoForward(void) { return _to GoForward(); } \
  NS_IMETHOD GotoIndex(PRInt32 index) { return _to GotoIndex(index); } \
  NS_IMETHOD LoadURI(const PRUnichar *uri, PRUint32 loadFlags, nsIURI *referrer, nsIInputStream *postData, nsIInputStream *headers) { return _to LoadURI(uri, loadFlags, referrer, postData, headers); } \
  NS_IMETHOD Reload(PRUint32 reloadFlags) { return _to Reload(reloadFlags); } \
  NS_IMETHOD Stop(PRUint32 stopFlags) { return _to Stop(stopFlags); } \
  NS_IMETHOD GetDocument(nsIDOMDocument * *aDocument) { return _to GetDocument(aDocument); } \
  NS_IMETHOD GetCurrentURI(nsIURI * *aCurrentURI) { return _to GetCurrentURI(aCurrentURI); } \
  NS_IMETHOD GetReferringURI(nsIURI * *aReferringURI) { return _to GetReferringURI(aReferringURI); } \
  NS_IMETHOD GetSessionHistory(nsISHistory * *aSessionHistory) { return _to GetSessionHistory(aSessionHistory); } \
  NS_IMETHOD SetSessionHistory(nsISHistory * aSessionHistory) { return _to SetSessionHistory(aSessionHistory); } 

/* Use this macro to declare functions that forward the behavior of this interface to another object in a safe way. */
#define NS_FORWARD_SAFE_NSIWEBNAVIGATION(_to) \
  NS_IMETHOD GetCanGoBack(PRBool *aCanGoBack) { return !_to ? NS_ERROR_NULL_POINTER : _to->GetCanGoBack(aCanGoBack); } \
  NS_IMETHOD GetCanGoForward(PRBool *aCanGoForward) { return !_to ? NS_ERROR_NULL_POINTER : _to->GetCanGoForward(aCanGoForward); } \
  NS_IMETHOD GoBack(void) { return !_to ? NS_ERROR_NULL_POINTER : _to->GoBack(); } \
  NS_IMETHOD GoForward(void) { return !_to ? NS_ERROR_NULL_POINTER : _to->GoForward(); } \
  NS_IMETHOD GotoIndex(PRInt32 index) { return !_to ? NS_ERROR_NULL_POINTER : _to->GotoIndex(index); } \
  NS_IMETHOD LoadURI(const PRUnichar *uri, PRUint32 loadFlags, nsIURI *referrer, nsIInputStream *postData, nsIInputStream *headers) { return !_to ? NS_ERROR_NULL_POINTER : _to->LoadURI(uri, loadFlags, referrer, postData, headers); } \
  NS_IMETHOD Reload(PRUint32 reloadFlags) { return !_to ? NS_ERROR_NULL_POINTER : _to->Reload(reloadFlags); } \
  NS_IMETHOD Stop(PRUint32 stopFlags) { return !_to ? NS_ERROR_NULL_POINTER : _to->Stop(stopFlags); } \
  NS_IMETHOD GetDocument(nsIDOMDocument * *aDocument) { return !_to ? NS_ERROR_NULL_POINTER : _to->GetDocument(aDocument); } \
  NS_IMETHOD GetCurrentURI(nsIURI * *aCurrentURI) { return !_to ? NS_ERROR_NULL_POINTER : _to->GetCurrentURI(aCurrentURI); } \
  NS_IMETHOD GetReferringURI(nsIURI * *aReferringURI) { return !_to ? NS_ERROR_NULL_POINTER : _to->GetReferringURI(aReferringURI); } \
  NS_IMETHOD GetSessionHistory(nsISHistory * *aSessionHistory) { return !_to ? NS_ERROR_NULL_POINTER : _to->GetSessionHistory(aSessionHistory); } \
  NS_IMETHOD SetSessionHistory(nsISHistory * aSessionHistory) { return !_to ? NS_ERROR_NULL_POINTER : _to->SetSessionHistory(aSessionHistory); } 

#if 0
/* Use the code below as a template for the implementation class for this interface. */

/* Header file */
class nsWebNavigation : public nsIWebNavigation
{
public:
  NS_DECL_ISUPPORTS
  NS_DECL_NSIWEBNAVIGATION

  nsWebNavigation();

private:
  ~nsWebNavigation();

protected:
  /* additional members */
};

/* Implementation file */
NS_IMPL_ISUPPORTS1(nsWebNavigation, nsIWebNavigation)

nsWebNavigation::nsWebNavigation()
{
  /* member initializers and constructor code */
}

nsWebNavigation::~nsWebNavigation()
{
  /* destructor code */
}

/* readonly attribute boolean canGoBack; */
NS_IMETHODIMP nsWebNavigation::GetCanGoBack(PRBool *aCanGoBack)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* readonly attribute boolean canGoForward; */
NS_IMETHODIMP nsWebNavigation::GetCanGoForward(PRBool *aCanGoForward)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* void goBack (); */
NS_IMETHODIMP nsWebNavigation::GoBack()
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* void goForward (); */
NS_IMETHODIMP nsWebNavigation::GoForward()
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* void gotoIndex (in long index); */
NS_IMETHODIMP nsWebNavigation::GotoIndex(PRInt32 index)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* void loadURI (in wstring uri, in unsigned long loadFlags, in nsIURI referrer, in nsIInputStream postData, in nsIInputStream headers); */
NS_IMETHODIMP nsWebNavigation::LoadURI(const PRUnichar *uri, PRUint32 loadFlags, nsIURI *referrer, nsIInputStream *postData, nsIInputStream *headers)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* void reload (in unsigned long reloadFlags); */
NS_IMETHODIMP nsWebNavigation::Reload(PRUint32 reloadFlags)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* void stop (in unsigned long stopFlags); */
NS_IMETHODIMP nsWebNavigation::Stop(PRUint32 stopFlags)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* readonly attribute nsIDOMDocument document; */
NS_IMETHODIMP nsWebNavigation::GetDocument(nsIDOMDocument * *aDocument)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* readonly attribute nsIURI currentURI; */
NS_IMETHODIMP nsWebNavigation::GetCurrentURI(nsIURI * *aCurrentURI)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* readonly attribute nsIURI referringURI; */
NS_IMETHODIMP nsWebNavigation::GetReferringURI(nsIURI * *aReferringURI)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* attribute nsISHistory sessionHistory; */
NS_IMETHODIMP nsWebNavigation::GetSessionHistory(nsISHistory * *aSessionHistory)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}
NS_IMETHODIMP nsWebNavigation::SetSessionHistory(nsISHistory * aSessionHistory)
{
    return NS_ERROR_NOT_IMPLEMENTED;
}

/* End of implementation class template. */
#endif


#endif /* __gen_nsIWebNavigation_h__ */
