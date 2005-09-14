#include <Python.h>
#include <windows.h>
#include <atlbase.h>
#include <atlcom.h>
#include <atlhost.h>
#include <exdisp.h>
#include <exdispid.h>
#include <urlmon.h>
// possibly need: atlapp, atlwin, atlctl?

#import "shdocvw.dll"

// Make sure _pAtlModule is non-NULL; ATL needs this for locking. If you
// don't do this then AtlAxCreateControl returns "out of memory" or segfaults.
class MyAtlModule : public CAtlModuleT<MyAtlModule> {
} ;
static MyAtlModule atlModule;

///////////////////////////////////////////////////////////////////////////////
// Object definition                                                         //
///////////////////////////////////////////////////////////////////////////////

#define WebBrowser_Check(v)  ((v)->ob_type == &WebBrowser_Type)
#define WebBrowser_obj(v)  (((WebBrowser *)(v))->obj)

class CWebEventsSink;
struct WebBrowserData {
  PyObject_HEAD
  IWebBrowser2 *wb2;
  // Oddly enough, IHTMLDocument3 inherits directly from IDispatch instead of
  // IHTMLDocument2, and basic methods like write() aren't defined on it.
  // So use IHTMLDocument2.
  IHTMLDocument2 *doc2;
  CWebEventsSink *sink;
  HWND hwnd; // Cosmetic use (repr()) only
} ;

void WebBrowser_dealloc(PyObject *self);
PyObject *WebBrowser_getattr(PyObject *self, char *attrname);
PyObject *WebBrowser_repr(PyObject *self);

PyTypeObject WebBrowser_Type = {
  PyObject_HEAD_INIT(&PyType_Type)
  0,
  "WebBrowser",             /* char *tp_name; */
  sizeof(WebBrowserData),   /* int tp_basicsize; */
  0,                        /* int tp_itemsize;       /* not used much */
  WebBrowser_dealloc,       /* destructor tp_dealloc; */
  0,                        /* printfunc  tp_print;   */
  WebBrowser_getattr,       /* getattrfunc  tp_getattr; /* __getattr__ */
  0,                        /* setattrfunc  tp_setattr;  /* __setattr__ */
  0,                        /* cmpfunc  tp_compare;  /* __cmp__ */
  WebBrowser_repr,          /* reprfunc  tp_repr;    /* __repr__ */
  0,                        /* PyNumberMethods *tp_as_number; */
  0,                        /* PySequenceMethods *tp_as_sequence; */
  0,                        /* PyMappingMethods *tp_as_mapping; */
  0,                        /* hashfunc tp_hash;     /* __hash__ */
  0,                        /* ternaryfunc tp_call;  /* __call__ */
  0,                        /* reprfunc tp_str;      /* __str__ */
};

// Convert a NULL-terminated string containing UTF8-encoded Unicode data to
// a Windows BSTR. A BSTR is always (usually?) a array of UTF16 characters.
// It is null-terminated, but it also contains a length field immediately
// **before** the pointer. It is the caller's responsibility to free the
// returned string with SysFreeString. Most COM methods take BSTRs.
static BSTR _utf8_to_BSTR(const char *utf8) {
  int encoding_len = strlen(utf8);
  int chars = MultiByteToWideChar(CP_UTF8, 0, utf8, encoding_len, NULL, 0);
  wchar_t *utf16 = new wchar_t[chars];
  MultiByteToWideChar(CP_UTF8, 0, utf8, encoding_len, utf16, chars);
  BSTR ret = SysAllocString(utf16);
  delete[] utf16;
  return ret;
}

///////////////////////////////////////////////////////////////////////////////
// COM event sink                                                            //
///////////////////////////////////////////////////////////////////////////////

// See support.microsoft.com/kb/q194179 for information about the lightweight
// IDispEventImpl mechanism for creating event sinks.
class CWebEventsSink : public IDispEventImpl<1, CWebEventsSink,
		       &DIID_DWebBrowserEvents2, &LIBID_SHDocVw> {
public:
  CWebEventsSink(PyObject *_onLoadCallback)
    : onLoadCallback(_onLoadCallback) {
    Py_XINCREF(onLoadCallback);
  }

  ~CWebEventsSink() {
    Py_XDECREF(onLoadCallback);
  }
  
  BEGIN_SINK_MAP(CWebEventsSink)
    SINK_ENTRY_EX(1, DIID_DWebBrowserEvents2, DISPID_BEFORENAVIGATE2,
		  BeforeNavigate2)
  END_SINK_MAP()

  void __stdcall BeforeNavigate2(IDispatch *pDisp, VARIANT *&url,
				 VARIANT *&flags, VARIANT *&targetFrameName,
				 VARIANT *&postData, VARIANT *&headers,
				 VARIANT_BOOL *&cancel) {
    int shouldCancel = 0;
    puts("Got BeforeNavigate2");

    // Get ready to make Python calls, taking Python's global lock.
    // Assumes that there is only one Python interpreter, the initial
    // one created by Py_Initialize (as opposed to other Python worlds
    // created with Py_NewInterpreter.)
    PyGILState_STATE gstate = PyGILState_Ensure();
    
    if (onLoadCallback != Py_None) {
      PyObject *arglist = Py_BuildValue("()"); // NEEDS
      PyObject *result = PyEval_CallObject(onLoadCallback, arglist);
      Py_DECREF(arglist);

      if (result == NULL)
	fprintf(stderr,
		"Warning: BeforeNavigate2 Python callback threw exception.\n");
      else {
	if (result != Py_None && !PyBool_Check(result))
	  fprintf(stderr,
		  "Warning: BeforeNavigate2 Python callback returned "
		  "bad value.\n");
	else if (result == Py_False)
	  shouldCancel = 1;
      }
    }

    *cancel = shouldCancel ? VARIANT_TRUE : VARIANT_FALSE;

    // Release Python's global lock.
    PyGILState_Release(gstate);
  }

protected:
  PyObject *onLoadCallback;
} ;

///////////////////////////////////////////////////////////////////////////////
// Construction and destruction                                              //
///////////////////////////////////////////////////////////////////////////////

static PyObject *WebBrowser_NEW(HWND hwnd, BSTR initialHTML,
				PyObject *onLoadCallback, BSTR userAgent) {
  IWebBrowser2 *wb2 = NULL;
  IDispatch *docDisp = NULL;
  IHTMLDocument2 *doc2 = NULL;
  SAFEARRAY *sfArray = NULL;
  CWebEventsSink *sink = NULL;
  
  // Create an IWebBrowser2, hosted in the provided HWND.
  IUnknown *pUnkContainer, *pUnkControl;
  HRESULT hr =
    AtlAxCreateControlEx(OLESTR("about:"), hwnd, NULL, &pUnkContainer,
    			 &pUnkControl);
  
  if (!SUCCEEDED(hr)) {
    PyErr_SetString(PyExc_OSError, "Couldn't instantiate Explorer through "
		    "AtlAxCreateControl.");
    goto failure;
  }
  if (!SUCCEEDED(pUnkControl->
		 QueryInterface(IID_IWebBrowser2, (void **)&wb2))) {
    PyErr_SetString(PyExc_OSError, "Couldn't get IWebBrowser2 interface.");
    goto failure;
  }

  // Find the document object
  if (!SUCCEEDED(wb2->get_Document(&docDisp))) {
    PyErr_SetString(PyExc_OSError, "Couldn't get IWebBrowser2.Document.");
    goto failure;
  }
  if (!SUCCEEDED(docDisp->QueryInterface(IID_IHTMLDocument2,
					 (void **)&doc2))) {
    PyErr_SetString(PyExc_OSError, "Couldn't get IHTMLDocument2.");
    goto failure;
  }

  // NEEDS: set userAgent
  
  // Set up callback
  sink = new CWebEventsSink(onLoadCallback);
  sink->AddRef(); // not sure if necessary -- err on side of leaks
  if (!SUCCEEDED(sink->DispEventAdvise(wb2))) {
    PyErr_SetString(PyExc_OSError, "Couldn't register DWebBrowserEvents2 "
		    "callback.");
    goto failure;
  }

  // Load initial HTML
  // (This is *not* happening to me. I am safe at home in my Missouri
  // hometown.)
  VARIANT *param;
  if ((sfArray = SafeArrayCreateVector(VT_VARIANT, 0, 1)) == NULL) {
    PyErr_SetString(PyExc_OSError, "Couldn't create SafeArray.");
    goto failure;
  }
  if (!SUCCEEDED(SafeArrayAccessData(sfArray, (void **)&param))) goto failure;
  param->vt = VT_BSTR;
  param->bstrVal = initialHTML;
  if (!SUCCEEDED(SafeArrayUnaccessData(sfArray))) goto failure;
  hr = doc2->write(sfArray);
  if (!SUCCEEDED(hr)) {
    char buf[256];
    snprintf(buf, sizeof(buf),
	     "Couldn't write() HTML to IHTMLDocument2; HRESULT = %08x.", hr);
    PyErr_SetString(PyExc_OSError, buf);
    goto failure;
  }
  doc2->close(); // may not be necessary/appropriate
  
  // Now we know that everything went fine, make a Python object
  WebBrowserData *wb = PyObject_NEW(WebBrowserData, &WebBrowser_Type);
  if (!wb)
    goto failure;
  wb->wb2 = wb2;
  wb->wb2->AddRef();
  wb->doc2 = doc2;
  wb->doc2->AddRef();
  wb->sink = sink;
  wb->sink->AddRef();
  wb->hwnd = hwnd;
    
  return (PyObject *)wb;
  
 failure:
  if (sink)
    sink->Release();
  if (sfArray)
    SafeArrayDestroy(sfArray);
  if (doc2)
    doc2->Release();
  if (docDisp)
    docDisp->Release();
  if (wb2)
    wb2->Release();
  return NULL;
}

static void WebBrowser_dealloc(PyObject *self) {
  puts("Note: WebBrowser_dealloc called.");
  if (WebBrowser_Check(self)) {
    WebBrowserData *wb = (WebBrowserData *)self;

    wb->sink->DispEventUnadvise(wb->wb2);
    wb->sink->Release();
    wb->doc2->Release();
    wb->wb2->Release();

    PyMem_DEL(self);
  }
}

static PyObject *WebBrowser_new(PyObject *self, PyObject *args,
				PyObject *kwargs) {
  HWND hwnd;
  char *html = NULL;
  PyObject *onLoadCallback = Py_None;
  char *agent = NULL;

  static char *kwlist[] = {"hwnd", "initialHTML", "onLoadCallback",
			   "userAgent", NULL};

  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "l|esOes:WebBrowser", kwlist,
				   &hwnd, "utf8", &html, &onLoadCallback,
				   "utf8", &agent))
    return NULL;

  if (onLoadCallback != Py_None && !PyCallable_Check(onLoadCallback)) {
    PyErr_SetString(PyExc_TypeError, "onLoadCallback must be callable");
    return NULL;
  }
  Py_XINCREF(onLoadCallback);

  BSTR initialHTML = _utf8_to_BSTR(html);
  PyMem_Free(html);
  BSTR userAgent = _utf8_to_BSTR(agent);
  PyMem_Free(agent);

  PyObject *ret = WebBrowser_NEW(hwnd, initialHTML, onLoadCallback, userAgent);

  Py_XDECREF(onLoadCallback);
  SysFreeString(initialHTML);
  SysFreeString(userAgent);
  return ret;
}

///////////////////////////////////////////////////////////////////////////////
// Methods                                                                   //
///////////////////////////////////////////////////////////////////////////////

static PyObject *WebBrowser_execJS(PyObject *self, PyObject *args) {
    if (!WebBrowser_Check(self))
      return NULL;
    puts("Punting execJS in WebBrowser.cpp");

    Py_INCREF(Py_None);
    return Py_None;
}

static PyMethodDef WebBrowser_methods[] = {
  {"execJS", WebBrowser_execJS, METH_VARARGS},
  {NULL, NULL},
};

static PyObject *WebBrowser_getattr(PyObject *self, char *attrname) {
  if (!WebBrowser_Check(self))
    return NULL;
  return Py_FindMethod(WebBrowser_methods, self, attrname);
}

///////////////////////////////////////////////////////////////////////////////
// Miscellaneous                                                             //
///////////////////////////////////////////////////////////////////////////////

static PyObject *WebBrowser_repr(PyObject *self) {
    if (!WebBrowser_Check(self))
      return NULL;
    WebBrowserData *wb = (WebBrowserData *)self;

    char buf[128];
    snprintf(buf, sizeof(buf), "<WebBrowser %p on HWND %d>", wb->wb2,
	     wb->hwnd);
    return PyString_FromString(buf);
  }

///////////////////////////////////////////////////////////////////////////////
// Module                                                                    //
///////////////////////////////////////////////////////////////////////////////

static PyMethodDef methods[] = {
  {"WebBrowser", (PyCFunction)WebBrowser_new, METH_VARARGS|METH_KEYWORDS},
  {NULL, NULL},
};

extern "C" void initWebBrowser(void) {
  CoInitialize(NULL);
  AtlAxWinInit();
#ifdef notdef
  CoInternetSetFeatureEnabled(FEATURE_LOCALMACHINE_LOCKDOWN,
			      SET_FEATURE_ON_PROCESS, FALSE);
#endif
  (void)Py_InitModule("WebBrowser", methods);
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
