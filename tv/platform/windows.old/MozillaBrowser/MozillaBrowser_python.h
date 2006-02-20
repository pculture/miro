#ifndef __MOZILLABROWSER_PYTHON_H
#define __MOZILLABROWSER_PYTHON_H

/* Important: our header should come second. Python.h include a bogus
   definition of snprintf to _snprintf. See MozillaBrowser.h. */
#include <Python.h>
#include "MozillaBrowser.h"

extern PyTypeObject MozillaBrowser_Type;

#define MozillaBrowser_Check(v)  ((v)->ob_type == &MozillaBrowser_Type)
#define MozillaBrowser_control(v)  (((MozillaBrowser *)(v))->control)

class PyControl : public Control {
public:
  PyControl() : m_onURLLoad(NULL), m_onActionURL(NULL) {}
  
  virtual nsresult Create(HWND hwnd, wchar_t *initialURL, wchar_t *userAgent,
			  PyObject *onURLLoad, PyObject *onActionURL,
			  PyObject *onDocumentLoadFinished);
  virtual PRBool onURLLoad(const char *url);
  virtual void onActionURL(const char *url);
  virtual void onDocumentLoadFinished(void);
  virtual ~PyControl();
  
protected:
  PyObject *m_onURLLoad;
  PyObject *m_onActionURL;
  PyObject *m_onDocumentLoadFinished;
} ;

struct MozillaBrowser {
  PyObject_HEAD
  PyControl *control;
} ;

#endif /* __MOZILLABROWSER_PYTHON_H */
