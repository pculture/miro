#ifndef __MOZILLABROWSER_H
#define __MOZILLABROWSER_H

#include <windows.h>
#include <wchar.h>

#include "nsCOMPtr.h"
#include "nsStringAPI.h"
#include "nsEmbedAPI.h"         
#include "nsEmbedString.h"         
#include "nsError.h"
#include "nsXPCOM.h"
#include "nsXPCOMGlue.h"
#include "prenv.h"
#include "prlock.h"

#include "nsIComponentManager.h"
#include "nsIWebBrowser.h"
#include "nsIWebBrowserChrome.h"
#include "nsIEmbeddingSiteWindow.h"
#include "nsIBaseWindow.h"
#include "nsIWebNavigation.h"
#include "nsIDOMWindow.h"
#include "nsIDOMDocument.h"
#include "nsIDOMHTMLDocument.h"
#include "nsIWebBrowserFocus.h"
#include "nsIWebProgressListener.h"
#include "nsIWeakReference.h"
#include "nsIWeakReferenceUtils.h"
#include "nsWeakReference.h"
#include "nsIURIContentListener.h"
#include "nsIURI.h"

// Forward declaration
class Control;

///////////////////////////////////////////////////////////////////////////////
// Miscellaneous                                                             //
///////////////////////////////////////////////////////////////////////////////

// These will be in a nsEmbedCID.h in the GRE SDK in the future, but
// that doesn't seem to have landed in yet in the 1.7.8 GRE, so I'll
// just stash 'em here. See http://bugzilla.mozilla.org/show_bug.cgi?id=258039
#define NS_WEBBROWSER_CONTRACTID \
        "@mozilla.org/embedding/browser/nsWebBrowser;1"

#ifdef WIN32
// I guess their hearts were in the right place.
#define snprintf _snprintf
#endif

///////////////////////////////////////////////////////////////////////////////
// helpers.cpp                                                               //
///////////////////////////////////////////////////////////////////////////////

nsresult CreateInstance(const char *aContractID, const nsIID &aIID,
			void **aInstancePtr);
nsresult startMozilla(void);

// Mozilla chokes on Unicode byte-order marks, at least in URLs. This
// function is provided to strip the byte-order marks from a string,
// performing any necessary conversion. A newly malloc()'d string is
// returned which must be free()'d by the caller. Note that only a
// simple case is implemented presently; see comments in the
// function. As a special case, passing NULL to this function causes
// it to return NULL.
wchar_t *stripBOM(wchar_t *str);

///////////////////////////////////////////////////////////////////////////////
// Chrome.cpp                                                                //
///////////////////////////////////////////////////////////////////////////////

/* In the Gecko framework, every WebBrowser object requires a Chrome
   object that defines the window it is hosted in (there is a
   one-to-one relationship between the two.) Gecko calls into this
   object to request changes in the size and title of the window, to
   make it modal, to change the decorations present (there are a set
   of flags that can force, eg, the address bar off if one would
   otherwise be present), and it even calls into this object to
   request things like tooltip display.

   The Chrome object also has an interface for Gecko to *request* the
   size, native window handle, etc, of the host window, but this isn't
   the primary way Gecko gets this information. That is through the
   nsIBaseWindow interface on the WebBrowser.
*/

class Chrome: public nsIWebBrowserChrome,
	      public nsIEmbeddingSiteWindow {
public:
  Chrome() {    puts("** Chrome created");}

  ~Chrome();

  NS_DECL_ISUPPORTS
  NS_DECL_NSIEMBEDDINGSITEWINDOW
  NS_DECL_NSIWEBBROWSERCHROME

  // Associate with the give WebBrowser and start managing the given
  // physical window. May only be called once.
  nsresult Create(HWND hwnd, nsIWebBrowser *browser);
  nsresult recomputeSize(void);

  // Get the mananged HWND. This will be the exact value passed into the
  // constructor for HWND. (For simplicity, not an XPCOM-friendly method.)
  HWND getHwnd(void) { return m_hwnd; }

protected:
  HWND m_hwnd;
  nsCOMPtr<nsIWebBrowser> m_webBrowser;
  PRUint32 m_chromeFlags;
} ; 

///////////////////////////////////////////////////////////////////////////////
// Listener.cpp                                                              //
///////////////////////////////////////////////////////////////////////////////

/* We register this object with Gecko via various interfaces for callbacks
   that allow us to track browser state changes. For now we only use this
   for page load activity.
*/
class Listener: public nsIWebProgressListener,
		public nsIURIContentListener,
                public nsSupportsWeakReference {
public:
  Listener() {puts("** Listener created");}
  ~Listener();

  NS_DECL_ISUPPORTS
  NS_DECL_NSIWEBPROGRESSLISTENER
  NS_DECL_NSIURICONTENTLISTENER

  // Initialize, setting the WebBrowser we will monitor and selecting
  // the Control object on which we will call methods in response to
  // events.
  nsresult Create(nsIWebBrowser *webBrowser, Control *control);

protected:
  Control *m_control;
  nsCOMPtr<nsIWebBrowser> m_webBrowser;
} ;

///////////////////////////////////////////////////////////////////////////////
// Control.cpp                                                               //
///////////////////////////////////////////////////////////////////////////////

/* This class represents an instance of our MozillaBrowser control. It
   is the public interface to all of the code in this directory. Its
   implementation is in Control.cpp, and its binding to Python is in
   MozillaBrowser.cpp. Generally one would subclass Control and
   implement any onXXX functions necessary to catch desired events.

   On the subject of threading, the threading model expected by the
   Gecko interfaces we use is unclear to me, so we'll do our
   best. It's a lot of work to confine our calls to just one thread,
   the thread that called GRE_Startup for example, so we won't go that
   far. Instead we'll assume that the public interfaces don't care
   what thread they were called from and can be called at any time
   (that is, manage any reentrancy issues versus their internal
   threads) but we will ensure that we only ever have one call into
   Mozilla per instance of our control at a time, by putting a big
   lock in each control.
*/

class Control {
public:
  Control() : m_mutex(PR_NewLock()), m_chrome(NULL)
  {puts("** Control created");
      printf("at ctor chrome %p listener %p\n", m_chrome, m_listener);

  }
  virtual ~Control();

  // Initialize the control. Must be called first. May only be called
  // exactly once.
  virtual nsresult Create(HWND hwnd, wchar_t *initialURL=NULL,
			  wchar_t *userAgent=NULL);

  // NEEDS: direct event gateway -- see mozilla.org/projects/embedding/faq.html
  /* NEEDS:
    # NEEDS: right-click menu.
    # Protocol: if type(getContextClickMenu) == "function", call it and
    # pass the DOM node that was clicked on. That returns "URL|description"
    # with blank lines for separators. On a click, force navigation of that
    # frame to that URL, maybe by setting document.location.href.
  */

  /**** Window maintenance methods ****/

  // Call this whenever the size of the window passed into the constructor
  // changes. Otherwise the size of the browser will not track the size
  // of the window.
  nsresult recomputeSize(void);

  // Get the mananged HWND. This will be the exact value passed into the
  // constructor for HWND.
  HWND getHwnd(void) { return m_chrome->getHwnd(); }

  // *Must* be called when the top-level window containing this
  // control is activated, and the control was what was previously
  // focused when the window was last activated. May also be called at
  // other times to give the browser focus at the application's
  // discretion. See nsIWebBrowserFocus.
  nsresult activate(void);

  // *Must* be called when this control is focused, and the top-level
  // window containing it is deactivated. "On non-windows platforms,
  // deactivate() should also be called when focus moves from the
  // browser to the embedding chrome" -- see nsIWebBrowserFocus.
  nsresult deactivate(void);

  /**** DOM mutators ****/
  
  // Parse 'xml'; this should yield a single DOM element. Insert it as
  // the last child of the element on the currently loaded page with
  // id 'id'.

  nsresult addElementAtEnd(wchar_t *xml, wchar_t *id);

  // Parse 'xml'; this should yield a single DOM element. Find the
  // element E in the currently loaded page with id 'id'. Insert the
  // new element as a child of E's parent, immediately before E in the
  // child ordering.
  nsresult addElementBefore(wchar_t *xml, wchar_t *id);

  // Remove the element with id 'id' in the currently loaded page.
  nsresult removeElement(wchar_t *id);

  // Parse 'xml'; this should yield a single DOM element. Find the
  // element with id 'id' in the currently loaded page, remove it, and
  // insert the newly constructed element exactly where it was.
  nsresult changeElement(wchar_t *id, wchar_t *xml);

  // Find the element with id 'id' in the currently loaded page and set
  // the value of its 'display' style property to 'none'.
  nsresult hideElement(wchar_t *id);

  // Find the element with id 'id' in the currently loaded page and
  // set the value of its 'display' style property to the empty
  // string, reversing hideElement().
  nsresult showElement(wchar_t *id);  

protected:
  // Internal use: get the nsIDOMDocument interface to the current document.
  nsresult getDocument(nsIDOMDocument **_retval);

  // Internal use: find an element in the current document by 'id' attribute.
  nsresult getElementById(wchar_t *id, nsIDOMElement **_retval);
public:
		       
  /**** Other methods ****/

  // NEEDS: return value?
  // NEEDS: define exact queuing semantics/interaction with document
  // loading
  nsresult execJS(wchar_t *expr);

  /**** Hooks for overriding ****/

  // For overriding: called when the given URL (UTF16 encoded) is
  // about to be loaded, and should return PR_TRUE if the load should
  // continue, or PR_FALSE if it should be cancelled. May be extended
  // in the future to pass POST data, etc.
  virtual PRBool onURLLoad(const char *url) { return PR_TRUE; }

  // For overriding: called when the given "action URL" (UTF16 encoded,
  // really just an arbitrary string) is delivered via Javascript.
  virtual void onActionURL(const char *url) { }

  // For overriding: called when a document load finishes.
  virtual void onDocumentLoadFinished(void) { }

protected:
  PRLock *m_mutex;
  HWND m_hwnd;

  // Convenience -- use m_ref_chrome to get automatic refcounting, but
  // keep m_chrome around as a direct pointer to the object so we can
  // call methods like execJS directly, even though we don't bother to
  // define a custom interface for them.
  Chrome *m_chrome;
  nsCOMPtr<nsIWebBrowserChrome> m_ref_chrome;
  nsCOMPtr<nsIWebBrowser> m_webBrowser;
  nsCOMPtr<nsISupports> m_listener;
} ;

#endif /* __MOZILLABROWSER_H */

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
