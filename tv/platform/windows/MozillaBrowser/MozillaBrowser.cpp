#include <Python.h>
#include "MozillaBrowser.h"
#include <stdio.h>

///////////////////////////////////////////////////////////////////////////////
// Subclass of Control, with appropriate Python callback support             //
///////////////////////////////////////////////////////////////////////////////

class PyControl : public Control {
public:
  PyControl() : m_onURLLoad(NULL), m_onActionURL(NULL) {}
  
  virtual nsresult Create(HWND hwnd, wchar_t *initialHTML, wchar_t *userAgent,
			  PyObject *onURLLoad, PyObject *onActionURL);
  virtual PRBool onURLLoad(wchar_t *url);
  virtual void onActionURL(wchar_t *url);
  virtual ~PyControl();
  
protected:
  PyObject *m_onURLLoad;
  PyObject *m_onActionURL;
} ;

nsresult PyControl::Create(HWND hwnd, wchar_t *initialHTML, wchar_t *userAgent,
			   PyObject *onURLLoad, PyObject *onActionURL) {
  if (!onURLLoad || !onActionURL)
    return NS_ERROR_NULL_POINTER;

  m_onURLLoad = onURLLoad;
  Py_XINCREF(onURLLoad);
  m_onActionURL = onActionURL;
  Py_XINCREF(onActionURL);

  return Control::Create(hwnd, initialHTML, userAgent);
}

PyControl::~PyControl() {
  if (m_onURLLoad)
    Py_DECREF(m_onURLLoad);
  if (m_onActionURL)
    Py_DECREF(m_onActionURL);
}

PRBool PyControl::onURLLoad(wchar_t *url) {
  if (m_onActionURL == Py_None)
    return PR_TRUE;

  // Get the Python lock so we can call into Python
  PyGILState_STATE gstate = PyGILState_Ensure();
  
  PyObject *result = PyObject_CallFunction(m_onURLLoad, "u", url);
  if (!result) {
    fprintf(stderr, "Warning: ignoring exception in MozillaBrowser "
	    "onLoad callback (Python-side).\n");
    PyGILState_Release(gstate);
    return PR_TRUE;
  }

  PRBool ret = PyObject_IsTrue(result) ? PR_TRUE : PR_FALSE;
  Py_DECREF(result);

  PyGILState_Release(gstate);
  return ret;
}

void PyControl::onActionURL(wchar_t *url) {
  if (m_onActionURL == Py_None)
    return;

  // Get the Python lock so we can call into Python
  PyGILState_STATE gstate = PyGILState_Ensure();

  PyObject *result = PyObject_CallFunction(m_onActionURL, "u", url);
  Py_DECREF(result);
  PyGILState_Release(gstate);
}

///////////////////////////////////////////////////////////////////////////////
// Python object definition                                                  //
///////////////////////////////////////////////////////////////////////////////

#define MozillaBrowser_Check(v)  ((v)->ob_type == &MozillaBrowser_Type)
#define MozillaBrowser_control(v)  (((MozillaBrowser *)(v))->control)

struct MozillaBrowser {
  PyObject_HEAD
  PyControl *control;
} ;

void MozillaBrowser_dealloc(PyObject *self);
PyObject *MozillaBrowser_getattr(PyObject *self, char *attrname);
PyObject *MozillaBrowser_repr(PyObject *self);

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
  wchar_t *html = NULL;
  PyObject *onLoadCallback = Py_None;
  PyObject *onActionCallback = Py_None;
  wchar_t *agent = NULL;
  int junk_int;

  static char *kwlist[] = {"hwnd", "initialHTML", "onLoadCallback",
			   "onActionCallback", "userAgent", NULL};

  if (!PyArg_ParseTupleAndKeywords(args, kwargs, "l|es#OOes#:MozillaBrowser",
				   kwlist, &hwnd, "utf16", (char **)&html,
				   &junk_int, &onLoadCallback,
				   &onActionCallback, "utf16",
				   &agent, &junk_int))
    return NULL;

  if (onLoadCallback != Py_None && !PyCallable_Check(onLoadCallback)) {
    PyErr_SetString(PyExc_TypeError, "onLoadCallback must be a function");
    return NULL;
  }
  if (onActionCallback != Py_None && !PyCallable_Check(onActionCallback)) {
    PyErr_SetString(PyExc_TypeError, "onActionCallback must be a function");
    return NULL;
  }

  puts("new pycontrol");
  PyControl *control = new PyControl();
  puts("pycontrol create");
  nsresult rv = control->Create(hwnd, html, agent, onLoadCallback,
				onActionCallback);
  puts("came back");
  if (NS_FAILED(rv)) {
    char buf[128];
    snprintf(buf, sizeof(buf),
	     "Couldn't instantiate Gecko; nsresult = %08x.", rv);
    PyErr_SetString(PyExc_OSError, buf);
    delete control;
    return NULL;
  }
  puts("it was ok");

  MozillaBrowser *mb = PyObject_NEW(MozillaBrowser, &MozillaBrowser_Type);
  if (!mb) {
    delete control;
    return NULL;
  }
  mb->control = control;

  PyMem_Free(html);
  PyMem_Free(agent);

  return (PyObject *)mb;
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

static PyObject *MozillaBrowser_execJS(PyObject *self, PyObject *args) {
  wchar_t *expr = NULL;
  int expr_len;
  PyObject *ret = NULL;
  
  if (!MozillaBrowser_Check(self))
    return NULL;
  if (!PyArg_ParseTuple(args, "es#:execJS",
			"utf16", (char **)&expr, &expr_len))
    goto finish;
  if (expr_len & 1)
    goto finish;

  nsresult rv = MozillaBrowser_control(self)->execJS(expr);
  if (NS_FAILED(rv)) {
    char buf[128];
    snprintf(buf, sizeof(buf),
	     "Couldn't execute Javascript; nsresult = %08x.", rv);
    PyErr_SetString(PyExc_OSError, buf);
    goto finish;
  }

  ret = Py_None;
  Py_INCREF(Py_None);

 finish:
  PyMem_Free(expr);
  return ret;
}

static PyObject *MozillaBrowser_recomputeSize(PyObject *self, PyObject *args) {
  if (!MozillaBrowser_Check(self))
    return NULL;
  if (!PyArg_ParseTuple(args, ":recomputeSize"))
    return NULL;

  MozillaBrowser_control(self)->recomputeSize();
  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject *MozillaBrowser_activate(PyObject *self, PyObject *args) {
  if (!MozillaBrowser_Check(self))
    return NULL;
  if (!PyArg_ParseTuple(args, ":activate"))
    return NULL;

  MozillaBrowser_control(self)->activate();
  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject *MozillaBrowser_deactivate(PyObject *self, PyObject *args) {
  if (!MozillaBrowser_Check(self))
    return NULL;
  if (!PyArg_ParseTuple(args, ":deactivate"))
    return NULL;

  MozillaBrowser_control(self)->deactivate();
  Py_INCREF(Py_None);
  return Py_None;
}

static PyMethodDef MozillaBrowser_methods[] = {
  {"execJS", MozillaBrowser_execJS, METH_VARARGS},
  {"recomputeSize", MozillaBrowser_recomputeSize, METH_VARARGS},
  {"activate", MozillaBrowser_activate, METH_VARARGS},
  {"deactivate", MozillaBrowser_deactivate, METH_VARARGS},
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
