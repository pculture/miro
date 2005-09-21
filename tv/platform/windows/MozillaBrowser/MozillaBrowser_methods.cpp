#include <python.h>
#include "MozillaBrowser.h"
#include "MozillaBrowser_python.h"

// The boring Python wrapper code for class Control.

///////////////////////////////////////////////////////////////////////////////
// Helpers, to make it a little less tedious. See usage below.               //
///////////////////////////////////////////////////////////////////////////////

// Accepts zero to two arguments, all to be read as Unicode strings.
#define MAXARGS 2
static int unicodeArgs(PyObject *self, PyObject *args, PyObject *kwargs,
		       int count, char *fmt,
		       char *name1=NULL, wchar_t **var1=NULL,
		       char *name2=NULL, wchar_t **var2=NULL) {
  if (!MozillaBrowser_Check(self))
    return FALSE;

  int ret = FALSE;
  int len[MAXARGS];
  wchar_t *raw[MAXARGS];
  wchar_t *out[MAXARGS];

  // Construct keyword argument list
  char *kwlist[MAXARGS + 1];
  kwlist[0] = name1;
  kwlist[1] = name2;
  kwlist[2] = NULL;

  // Clear out conversion structures
  for(int i=0; i<count; i++)
    raw[i] = out[i] = NULL;

  // Parse argument list
  if (!PyArg_ParseTupleAndKeywords(args, kwargs, fmt, kwlist,
				   "utf16", (char **)&raw[0], &len[0],
				   "utf16", (char **)&raw[1], &len[1]))
    goto failure;

  // Convert strings
  for(int i=0; i<count; i++) {
    if (raw[i]) {
      if (len[i] & 1)
	goto failure;
      out[i] = unPythonifyString(raw[i], len[i] / 2);
      PyMem_Free(raw[i]);
    }
  }

  // Success: output strings and return.
  if (var1) *var1 = out[0];
  if (var2) *var2 = out[1];
  return TRUE;

 failure:
  // Clean up intermediate state from failed conversion
  for(int i=0; i<count; i++) {
    if (raw[i])
      PyMem_Free(raw[i]);
    if (out[i])
      free(out[i]);
  }

  return FALSE;
}

static PyObject *handleNsresultAndFree(const char *name, nsresult rv,
				       void *free1=NULL, void *free2=NULL) {
  PyObject *ret;

  // Determine return value and error string
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

  // Free strings allocated by converter in unicodeArgs
  if (free1)
    free(free1);
  if (free2)
    free(free1);

  return ret;
}

///////////////////////////////////////////////////////////////////////////////
// Window maintenance methods                                                //
///////////////////////////////////////////////////////////////////////////////

PyObject *MozillaBrowser_recomputeSize(PyObject *self, PyObject *args,
				       PyObject *kwargs) {
  if (!unicodeArgs(self, args, kwargs, 0, ":recomputeSize"))
    return NULL;
  return handleNsresultAndFree("recomputeSize",
			       MozillaBrowser_control(self)
			       ->recomputeSize());
}

PyObject *MozillaBrowser_activate(PyObject *self, PyObject *args,
				  PyObject *kwargs) {
  if (!unicodeArgs(self, args, kwargs, 0, ":activate"))
    return NULL;
  return handleNsresultAndFree("activate",
			       MozillaBrowser_control(self)
			       ->activate());
}

PyObject *MozillaBrowser_deactivate(PyObject *self, PyObject *args,
				    PyObject *kwargs) {
  if (!unicodeArgs(self, args, kwargs, 0, ":deactivate"))
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

  if (!unicodeArgs(self, args, kwargs, 2, "es#es#:addElementAtEnd",
		   "xml", &xml, "id", &id))
    return NULL;
  return handleNsresultAndFree("addElementAtEnd",
			       MozillaBrowser_control(self)->
			       addElementAtEnd(xml, id),
			       xml, id);
}

PyObject *MozillaBrowser_addElementBefore(PyObject *self, PyObject *args,
					  PyObject *kwargs) {
  wchar_t *xml, *id;

  if (!unicodeArgs(self, args, kwargs, 2, "es#es#:addElementBefore",
		   "xml", &xml, "id", &id))
    return NULL;
  return handleNsresultAndFree("addElementBefore",
			       MozillaBrowser_control(self)->
			       addElementBefore(xml, id),
			       xml, id);
}

PyObject *MozillaBrowser_removeElement(PyObject *self, PyObject *args,
				       PyObject *kwargs) {
  wchar_t *id;

  if (!unicodeArgs(self, args, kwargs, 1, "es#:removeElement", "id", &id))
    return NULL;
  return handleNsresultAndFree("removeElement",
			       MozillaBrowser_control(self)->
			       removeElement(id),
			       id);
}

PyObject *MozillaBrowser_changeElement(PyObject *self, PyObject *args,
					PyObject *kwargs) {
  wchar_t *id, *xml;

  if (!unicodeArgs(self, args, kwargs, 2, "es#es#:changeElement", "id", &id,
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

  if (!unicodeArgs(self, args, kwargs, 1, "es#:hideElement", "id", &id))
    return NULL;
  return handleNsresultAndFree("hideElement",
			       MozillaBrowser_control(self)->
			       hideElement(id),
			       id);
}

PyObject *MozillaBrowser_showElement(PyObject *self, PyObject *args,
				     PyObject *kwargs) {
  wchar_t *id;

  if (!unicodeArgs(self, args, kwargs, 1, "es#:showElement", "id", &id))
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

  if (!unicodeArgs(self, args, kwargs, 1, "es#:execJS", "expr", &expr))
    return NULL;
  return handleNsresultAndFree("execJS",
			       MozillaBrowser_control(self)->execJS(expr),
			       expr);
}

///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////
