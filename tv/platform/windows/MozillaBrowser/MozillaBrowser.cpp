#include "MozillaBrowser.h"
#include "MozillaBrowser_python.h"
#include <stdio.h>

///////////////////////////////////////////////////////////////////////////////
// Subclass of Control, with appropriate Python callback support             //
///////////////////////////////////////////////////////////////////////////////

nsresult PyControl::Create(HWND hwnd, wchar_t *initialURL, wchar_t *userAgent,
			   PyObject *onURLLoad, PyObject *onActionURL,
			   PyObject *onDocumentLoadFinished) {
  if (!onURLLoad || !onActionURL)
    return NS_ERROR_NULL_POINTER;

  m_onURLLoad = onURLLoad;
  Py_XINCREF(onURLLoad);
  m_onActionURL = onActionURL;
  Py_XINCREF(onActionURL);
  m_onDocumentLoadFinished = onDocumentLoadFinished;
  Py_XINCREF(onDocumentLoadFinished);

  return Control::Create(hwnd, initialURL, userAgent);
}

PyControl::~PyControl() {
  if (m_onURLLoad)
    Py_DECREF(m_onURLLoad);
  if (m_onActionURL)
    Py_DECREF(m_onActionURL);
}

PRBool PyControl::onURLLoad(const char *url) {
  if (m_onURLLoad == Py_None)
    return PR_TRUE;

  // Get the Python lock so we can call into Python
  PyGILState_STATE gstate = PyGILState_Ensure();
  
  PyObject *result = PyObject_CallFunction(m_onURLLoad, "s", url);
  if (!result) {
    fprintf(stderr, "Warning: ignoring exception in MozillaBrowser "
	    "onLoad callback (Python-side).\n");
    PyErr_Print();
    PyGILState_Release(gstate);
    return PR_TRUE;
  }

  PRBool ret;
  if (result == Py_None)
    ret = PR_TRUE;
  else 
    ret = PyObject_IsTrue(result) ? PR_TRUE : PR_FALSE;
  Py_DECREF(result);

  PyGILState_Release(gstate);
  return ret;
}

void PyControl::onActionURL(const char *url) {
  if (m_onActionURL == Py_None)
    return;

  // Get the Python lock so we can call into Python
  PyGILState_STATE gstate = PyGILState_Ensure();

  PyObject *result = PyObject_CallFunction(m_onActionURL, "s", url);
  Py_DECREF(result);

  if (PyErr_Occurred()) {
    fprintf(stderr, "Warning: ignoring exception in MozillaBrowser "
	    "onActionURL callback (Python-side).\n");
    PyErr_Print();
  }

  PyGILState_Release(gstate);
}

void PyControl::onDocumentLoadFinished(void) {
  if (m_onDocumentLoadFinished == Py_None)
    return;

  // Get the Python lock so we can call into Python
  PyGILState_STATE gstate = PyGILState_Ensure();

  PyObject *result = PyObject_CallFunction(m_onDocumentLoadFinished, "");
  Py_DECREF(result);

  if (PyErr_Occurred()) {
    fprintf(stderr, "Warning: ignoring exception in MozillaBrowser "
	    "onDocumentLoadFinished callback (Python-side).\n");
    PyErr_Print();
  }

  PyGILState_Release(gstate);
}

///////////////////////////////////////////////////////////////////////////////
// Python object definition                                                  //
///////////////////////////////////////////////////////////////////////////////

static void MozillaBrowser_dealloc(PyObject *self);
static PyObject *MozillaBrowser_getattr(PyObject *self, char *attrname);
static PyObject *MozillaBrowser_repr(PyObject *self);

PyTypeObject MozillaBrowser_Type = {
  PyObject_HEAD_INIT(&PyType_Type)
  0,
  "MozillaBrowser",         /* char *tp_name; */
  sizeof(MozillaBrowser),   /* int tp_basicsize; */
  0,                        /* int tp_itemsize;       /* not used much */
  MozillaBrowser_dealloc,   /* destructor tp_dealloc; */
  0,                        /* printfunc  tp_print;   */
  MozillaBrowser_getattr,   /* getattrfunc  tp_getattr; /* __getattr__ */
  0,                        /* setattrfunc  tp_setattr;  /* __setattr__ */
  0,                        /* cmpfunc  tp_compare;  /* __cmp__ */
  MozillaBrowser_repr,      /* reprfunc  tp_repr;    /* __repr__ */
  0,                        /* PyNumberMethods *tp_as_number; */
  0,                        /* PySequenceMethods *tp_as_sequence; */
  0,                        /* PyMappingMethods *tp_as_mapping; */
  0,                        /* hashfunc tp_hash;     /* __hash__ */
  0,                        /* ternaryfunc tp_call;  /* __call__ */
  0,                        /* reprfunc tp_str;      /* __str__ */
};

///////////////////////////////////////////////////////////////////////////////
// Construction and destruction                                              //
///////////////////////////////////////////////////////////////////////////////

static PyObject *MozillaBrowser_new(PyObject *self, PyObject *args,
				PyObject *kwargs) {
  HWND hwnd;
  wchar_t *url    = NULL;
  wchar_t *agent  = NULL;
  wchar_t *_url   = NULL;
  wchar_t *_agent = NULL;
  PyObject *onLoadCallback = Py_None;
  PyObject *onActionCallback = Py_None;
  PyObject *onDocumentLoadFinishedCallback = Py_None;
  int url_len, agent_len;
  PyObject *ret = NULL;

  static char *kwlist[] = {"hwnd",
			   "onLoadCallback",
			   "onActionCallback",
			   "onDocumentLoadFinishedCallback",
			   "initialURL", "userAgent", NULL};

  // Python 2.4.0 will raise a cryptic exception about '<bad format
  // char>' if it has to skip an 'es#' keyword argument while walking
  // the argument list.  So, structure the order of the arguments to
  // minimize the chance of that happening.
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "l|OOOes#es#:MozillaBrowser",
				   kwlist, &hwnd,
				   &onLoadCallback,
				   &onActionCallback,
				   &onDocumentLoadFinishedCallback,
				   "utf16", (char **)&url, &url_len,
				   "utf16", (char **)&agent, &agent_len))
    goto done;
  
  if (onLoadCallback != Py_None && !PyCallable_Check(onLoadCallback)) {
    PyErr_SetString(PyExc_TypeError, "onLoadCallback must be a function");
    goto done;
  }
  if (onActionCallback != Py_None && !PyCallable_Check(onActionCallback)) {
    PyErr_SetString(PyExc_TypeError, "onActionCallback must be a function");
    goto done;
  }
  if (onDocumentLoadFinishedCallback != Py_None &&
      !PyCallable_Check(onDocumentLoadFinishedCallback)) {
    PyErr_SetString(PyExc_TypeError,
		    "onDocumentLoadFinishedCallback must be a function");
    goto done;
  }

  if ((url   && (url_len   & 1)) ||
      (agent && (agent_len & 1)) )
    goto done;
  _url   = unPythonifyString(url, url_len / 2);
  _agent = unPythonifyString(agent, agent_len / 2);
  
  PyControl *control = new PyControl();
  nsresult rv = control->Create(hwnd, _url, _agent, onLoadCallback,
				onActionCallback,
				onDocumentLoadFinishedCallback);
  if (NS_FAILED(rv)) {
    char buf[128];
    delete control;
    if (_url && rv == NS_ERROR_FILE_NOT_FOUND)
      // Give a descriptive message for a common error
      snprintf(buf, sizeof(buf),
	       "Couldn't instantiate Gecko; file not found: %S", _url);
    else
      snprintf(buf, sizeof(buf),
	       "Couldn't instantiate Gecko; nsresult = %08x.", rv);
    PyErr_SetString(PyExc_OSError, buf);
    goto done;
  }

  MozillaBrowser *mb = PyObject_NEW(MozillaBrowser, &MozillaBrowser_Type);
  if (!mb) {
    delete control;
    goto done;
  }
  mb->control = control;
  ret = (PyObject *)mb;

 done:
  if (_url)
    free(_url);
  if (_agent)
    free(_agent);
  if (url)
    PyMem_Free(url);
  if (agent)
    PyMem_Free(agent);
  
  return ret;
}

static void MozillaBrowser_dealloc(PyObject *self) {
  fprintf(stderr, "Note: MozillaBrowser_dealloc called.\n");
  if (MozillaBrowser_Check(self)) {
    MozillaBrowser *mb = (MozillaBrowser *)self;
    delete mb->control;
    PyMem_DEL(self);
  }
}

///////////////////////////////////////////////////////////////////////////////
// Methods                                                                   //
///////////////////////////////////////////////////////////////////////////////

// These functions simply wrap corresponding methods in class
// Control. They are dull as rocks and reside in
// MozillaBrowser_methods.cpp.
PyObject *MozillaBrowser_execJS
(PyObject *self, PyObject *args, PyObject *kwargs);
PyObject *MozillaBrowser_recomputeSize
(PyObject *self, PyObject *args, PyObject *kwargs);
PyObject *MozillaBrowser_activate
(PyObject *self, PyObject *args, PyObject *kwargs);
PyObject *MozillaBrowser_deactivate
(PyObject *self, PyObject *args, PyObject *kwargs);
PyObject *MozillaBrowser_addElementAtEnd
(PyObject *self, PyObject *args, PyObject *kwargs);
PyObject *MozillaBrowser_addElementBefore
(PyObject *self, PyObject *args, PyObject *kwargs);
PyObject *MozillaBrowser_removeElement
(PyObject *self, PyObject *args, PyObject *kwargs);
PyObject *MozillaBrowser_changeElement
(PyObject *self, PyObject *args, PyObject *kwargs);
PyObject *MozillaBrowser_hideElement
(PyObject *self, PyObject *args, PyObject *kwargs);
PyObject *MozillaBrowser_showElement
(PyObject *self, PyObject *args, PyObject *kwargs);

static PyMethodDef MozillaBrowser_methods[] = {
//{"execJS", (PyCFunction)MozillaBrowser_execJS, METH_VARARGS|METH_KEYWORDS},
  {"recomputeSize", (PyCFunction)MozillaBrowser_recomputeSize,
   METH_VARARGS|METH_KEYWORDS},
  {"activate", (PyCFunction)MozillaBrowser_activate,
   METH_VARARGS|METH_KEYWORDS},
  {"deactivate", (PyCFunction)MozillaBrowser_deactivate,
   METH_VARARGS|METH_KEYWORDS},
  {"addElementAtEnd", (PyCFunction)MozillaBrowser_addElementAtEnd,
   METH_VARARGS|METH_KEYWORDS},
  {"addElementBefore", (PyCFunction)MozillaBrowser_addElementBefore,
   METH_VARARGS|METH_KEYWORDS},
  {"removeElement", (PyCFunction)MozillaBrowser_removeElement,
   METH_VARARGS|METH_KEYWORDS},
  {"changeElement", (PyCFunction)MozillaBrowser_changeElement,
   METH_VARARGS|METH_KEYWORDS},
  {"hideElement", (PyCFunction)MozillaBrowser_hideElement,
   METH_VARARGS|METH_KEYWORDS},
  {"showElement", (PyCFunction)MozillaBrowser_showElement,
   METH_VARARGS|METH_KEYWORDS},
  {NULL, NULL},
};

static PyObject *MozillaBrowser_getattr(PyObject *self, char *attrname) {
  if (!MozillaBrowser_Check(self))
    return NULL;
  return Py_FindMethod(MozillaBrowser_methods, self, attrname);
}

///////////////////////////////////////////////////////////////////////////////
// Miscellaneous                                                             //
///////////////////////////////////////////////////////////////////////////////

static PyObject *MozillaBrowser_repr(PyObject *self) {
    if (!MozillaBrowser_Check(self))
      return NULL;
    MozillaBrowser *mb = (MozillaBrowser *)self;

    char buf[128];
    snprintf(buf, sizeof(buf), "<MozillaBrowser %p on HWND %d>", mb,
	     mb->control->getHwnd());
    return PyString_FromString(buf);
  }

///////////////////////////////////////////////////////////////////////////////
// Module                                                                    //
///////////////////////////////////////////////////////////////////////////////

static PyMethodDef methods[] = {
  {"MozillaBrowser", (PyCFunction)MozillaBrowser_new,
   METH_VARARGS|METH_KEYWORDS},
  {NULL, NULL},
};

extern "C" void initMozillaBrowser(void) {
  (void)Py_InitModule("MozillaBrowser", methods);
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
