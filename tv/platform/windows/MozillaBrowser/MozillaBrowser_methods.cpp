#include <python.h>
#include "MozillaBrowser.h"
#include "MozillaBrowser_python.h"

// The boring Python wrapper code for class Control.

///////////////////////////////////////////////////////////////////////////////
// Helpers, to make it a little less tedious. See usage below.               //
///////////////////////////////////////////////////////////////////////////////

// Accepts zero to two arguments, all to be read as Unicode strings.
static int unicodeArgs(PyObject *self, PyObject *args, PyObject *kwargs,
		       char *fmt,
		       char *name1=NULL, wchar_t **var1=NULL,
		       char *name2=NULL, wchar_t **var2=NULL) {
  if (!MozillaBrowser_Check(self))
    return NULL;

  int len1 = 0, len2 = 0;
  char *kwlist[3];
  kwlist[0] = name1;
  kwlist[1] = name2;
  kwlist[2] = NULL;
  
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, fmt, kwlist,
				   "utf16", (char **)var1, &len1,
				   "utf16", (char **)var2, &len2))
    return FALSE;
  if (len1 & 1 || len2 & 1)
    return FALSE;

  return TRUE;
}

static PyObject *handleNsresultAndFree(const char *name, nsresult rv,
				       void *free1=NULL, void *free2=NULL) {
  PyObject *ret;

  if (NS_FAILED(rv)) {
    char buf[256];
    snprintf(buf, sizeof(buf),
	     "MozillaBrowser: %s failed; error code is %08x.", rv);
    PyErr_SetString(PyExc_OSError, buf);
    ret = NULL;
  }
  else {
    ret = Py_None;
    Py_INCREF(ret);
  }
    
  if (free1)
    PyMem_Free(free1);
  if (free2)
    PyMem_Free(free1);

  return ret;
}

///////////////////////////////////////////////////////////////////////////////
// Window maintenance methods                                                //
///////////////////////////////////////////////////////////////////////////////

PyObject *MozillaBrowser_recomputeSize(PyObject *self, PyObject *args,
				       PyObject *kwargs) {
  if (!unicodeArgs(self, args, kwargs, ":recomputeSize"))
    return NULL;
  return handleNsresultAndFree("recomputeSize",
			       MozillaBrowser_control(self)
			       ->recomputeSize());
}

PyObject *MozillaBrowser_activate(PyObject *self, PyObject *args,
				  PyObject *kwargs) {
  puts("---> Top of activate");
  if (!unicodeArgs(self, args, kwargs, ":activate"))
    return NULL;
  return handleNsresultAndFree("activate",
			       MozillaBrowser_control(self)
			       ->activate());
}

PyObject *MozillaBrowser_deactivate(PyObject *self, PyObject *args,
				    PyObject *kwargs) {
  puts("---> Top of deactivate");
  if (!unicodeArgs(self, args, kwargs, ":deactivate"))
    return NULL;
  return handleNsresultAndFree("deactivate",
			       MozillaBrowser_control(self)
			       ->deactivate());
}


///////////////////////////////////////////////////////////////////////////////
// DOM mutators                                                              //
///////////////////////////////////////////////////////////////////////////////

PyObject *MozillaBrowser_addElementAtEnd(PyObject *self, PyObject *args,
					 PyObject *kwargs) {
  wchar_t *xml, *id;

  if (!unicodeArgs(self, args, kwargs, "es#es#:addElementAtEnd", "xml", &xml,
		   "id", &id))
    return NULL;
  return handleNsresultAndFree("addElementAtEnd",
			       MozillaBrowser_control(self)->
			       addElementAtEnd(xml, id),
			       xml, id);
}

PyObject *MozillaBrowser_addElementBefore(PyObject *self, PyObject *args,
					  PyObject *kwargs) {
  wchar_t *xml, *id;

  if (!unicodeArgs(self, args, kwargs, "es#es#:addElementBefore", "xml", &xml,
		   "id", &id))
    return NULL;
  return handleNsresultAndFree("addElementBefore",
			       MozillaBrowser_control(self)->
			       addElementBefore(xml, id),
			       xml, id);
}

PyObject *MozillaBrowser_removeElement(PyObject *self, PyObject *args,
				       PyObject *kwargs) {
  wchar_t *id;

  if (!unicodeArgs(self, args, kwargs, "es#:removeElement", "id", &id))
    return NULL;
  return handleNsresultAndFree("removeElement",
			       MozillaBrowser_control(self)->
			       removeElement(id),
			       id);
}

PyObject *MozillaBrowser_changeElement(PyObject *self, PyObject *args,
					PyObject *kwargs) {
  wchar_t *id, *xml;

  if (!unicodeArgs(self, args, kwargs, "es#:removeElement", "id", &id,
		   "xml", &xml))
    return NULL;
  return handleNsresultAndFree("changeElement",
			       MozillaBrowser_control(self)->
			       changeElement(id, xml),
			       id, xml);
}

PyObject *MozillaBrowser_hideElement(PyObject *self, PyObject *args,
				     PyObject *kwargs) {
  wchar_t *id;

  if (!unicodeArgs(self, args, kwargs, "es#:hideElement", "id", &id))
    return NULL;
  return handleNsresultAndFree("hideElement",
			       MozillaBrowser_control(self)->
			       hideElement(id),
			       id);
}

PyObject *MozillaBrowser_showElement(PyObject *self, PyObject *args,
				     PyObject *kwargs) {
  wchar_t *id;

  if (!unicodeArgs(self, args, kwargs, "es#:showElement", "id", &id))
    return NULL;
  return handleNsresultAndFree("showElement",
			       MozillaBrowser_control(self)->
			       showElement(id),
			       id);
}

///////////////////////////////////////////////////////////////////////////////
// Miscellaneous                                                             //
///////////////////////////////////////////////////////////////////////////////

PyObject *MozillaBrowser_execJS(PyObject *self, PyObject *args,
				PyObject *kwargs) {
  wchar_t *expr;

  if (!unicodeArgs(self, args, kwargs, "es#:execJS", "expr", &expr))
    return NULL;
  return handleNsresultAndFree("execJS",
			       MozillaBrowser_control(self)->execJS(expr),
			       expr);
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
