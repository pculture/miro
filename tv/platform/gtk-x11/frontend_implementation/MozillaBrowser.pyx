"""MozillaBrowser extension."""

import gtkmozembed
import logging

cdef extern from "MozillaBrowser.h":
    ctypedef struct GtkMozEmbed
    ctypedef struct GObject 
    ctypedef struct PyGObject:
        GObject * obj
    ctypedef int gint
    ctypedef unsigned long gulong
    ctypedef char gchar
    ctypedef void * gpointer
    ctypedef void * GCallback
    cdef gulong g_signal_connect( gpointer *object, gchar *name, GCallback func, gpointer func_data )

cdef extern from "Python.h":
    ctypedef int PyGILState_STATE
    PyGILState_STATE PyGILState_Ensure()
    void PyGILState_Release(PyGILState_STATE)
    ctypedef struct PyThreadState
    ctypedef struct PyObject
    void Py_DECREF(PyObject*)
    void Py_INCREF(PyObject*)
    PyObject* PyObject_CallMethod(PyObject *o, char *method, char* format, ...)
    void PyErr_Print()
    int PyObject_IsTrue(PyObject*)

cdef extern from "nsError.h":
    ctypedef unsigned int nsresult
    cdef enum:
        NS_OK = 0

cdef extern from "MozillaBrowserXPCOM.h":
    nsresult addItemBefore(GtkMozEmbed *gtkembed, char *newXml, char *id)
    nsresult addItemAtEnd(GtkMozEmbed *gtkembed, char *newXml, char *id)
    nsresult changeItem(GtkMozEmbed *gtkembed, char *id, char *newXml)
    nsresult changeAttribute(GtkMozEmbed *gtkembed, char *id, char *name, char *value)
    nsresult removeAttribute(GtkMozEmbed *gtkembed, char *id, char *name)
    nsresult removeItem(GtkMozEmbed *gtkembed, char *id)
    nsresult showItem(GtkMozEmbed *gtkembed, char *id)
    nsresult hideItem(GtkMozEmbed *gtkembed, char *id)
    char* getContextMenu(void* domEvent)
    void freeString(char* str)

cdef extern from "DragAndDrop.h":
    nsresult setupDragAndDrop(GtkMozEmbed *gtkembed)

cdef extern from "HttpObserver.h":
    nsresult startObserving()

cdef extern from "stdio.h":
    int printf(char* str, ...)

class DOMError(Exception):
    pass
class XPCOMError(Exception):
    pass

cdef class MozillaBrowser:
    cdef GtkMozEmbed *cWidget
    cdef object widget, URICallBack, finishedCallBack, destroyCallBack
    cdef object contextMenuCallBack
    
    def __new__(self):
        self.widget = gtkmozembed.MozEmbed()
        self.cWidget = self.pygtkmozembed_to_c(self.widget)

    def __init__(self):
        setupHttpObserver()
        self.URICallBack = None
        self.finishedCallBack = None
        self.destroyCallBack = None
        self.contextMenuCallBack = None
        g_signal_connect(<gpointer *>self.cWidget, "open_uri", 
                <void *>open_uri_cb, <gpointer>self)
        g_signal_connect(<gpointer *>self.cWidget, "dom_mouse_down", 
                <void *>on_dom_mouse_down, <gpointer>self)
        self.widget.connect("realize", self.onRealize)

    def onRealize(self, widget):
        rv = setupDragAndDrop(self.cWidget)
        if rv != NS_OK:
            print "WARNING! setupDragAndDrop failed"

    def getWidget(self):
        return self.widget

    def addItemBefore(self, xml, id):
        result = addItemBefore(self.cWidget, xml, id)
        if result != NS_OK:
            raise DOMError("error in addItemBefore")

    def addItemAtEnd(self, xml, id):
        result = addItemAtEnd(self.cWidget, xml, id)
        if result != NS_OK:
            raise DOMError("error occured in addItemAtEnd")

    def changeItem(self, id, xml):
        result = changeItem(self.cWidget, id, xml)
        if result != NS_OK:
            raise DOMError("error occured in changeItem")

    def removeAttribute(self, id, name):
        result = removeAttribute(self.cWidget, id, name)
        if result != NS_OK:
            raise DOMError("error occured in removeAttribute")

    def changeAttribute(self, id, name, value):
        result = changeAttribute(self.cWidget, id, name, value)
        if result != NS_OK:
            raise DOMError("error occured in changeAttribute")

    def removeItem(self, id):
        result = removeItem(self.cWidget, id)
        if result != NS_OK:
            raise DOMError("error occured in removeItem")

    def showItem(self, id):
        result = showItem(self.cWidget, id)
        if result != NS_OK:
            raise DOMError("error occured in showItem")

    def hideItem(self, id):
        result = hideItem(self.cWidget, id)
        if result != NS_OK:
            raise DOMError("error occured in hideItem")

    def setURICallBack(self, callback):
        self.URICallBack = callback

    def getURICallBack(self):
        return self.URICallBack

    def setFinishedCallBack(self, callback):
        self.finishedCallBack = callback

    def getFinishedCallBack(self):
        return self.finishedCallBack

    def setDestroyCallBack(self, callback):
        self.destroyCallBack = callback

    def getDestroyCallBack(self):
        return self.destroyCallBack
        
    def setContextMenuCallBack(self, callback):
        self.contextMenuCallBack = callback

    def getContextMenuCallBack(self):
        return self.contextMenuCallBack

    cdef GtkMozEmbed *pygtkmozembed_to_c(MozillaBrowser self, object pygtkmoz):
        cdef PyGObject *tempObj
        cdef GObject *temp
        tempObj = <PyGObject *>pygtkmoz
        temp = tempObj.obj
        return <GtkMozEmbed *>temp

    def openUriCallback(self, uri):
        URICallBack = self.getURICallBack()
        if URICallBack is not None and not URICallBack(uri.decode('utf-8','replace')):
            return True
        else:
            return False

    def createContextMenu(self, menu):
        # Menu is the string from the DOM element.  It has newlines encoded as
        # "\n" and backslashes encoded as "\\".  Decode menu and pass it to
        # our context menu callback if we have one.
        if self.contextMenuCallBack is not None:
            menu = menu.replace("\\n", "\n")
            menu = menu.replace("\\\\", "\\")
            self.contextMenuCallBack(menu)

# Here's the deal on the open-uri callback hack:
#
# GtkMozEmbed doesn't define the open-uri callback correctly.  The uri value
# is declared as a gpointer, instead of a string.  It's not a problem in C
# but it doesn't work in Python.
#
# To get around this, we declare a C callback to handle things.  Since this
# callback is coming straight from the C code, we need to acquire the python
# GIL or we'll segfault.  Because of this, we can't create any local python
# object because they will be DECREFed at the end of the function -- after
# we've given back the GIL.  To make things less messy, the C callback 
# invokes OpenUriCallback to do most of the work.

cdef gint open_uri_cb (GtkMozEmbed *embed, char *uri, PyObject * self):
    cdef int rv 
    cdef PyGILState_STATE gil
    cdef PyObject* callbackResult
    gil = PyGILState_Ensure()
    Py_INCREF(self)
    callbackResult = PyObject_CallMethod(self, "openUriCallback", "s", uri,
            NULL)
    if(callbackResult == NULL):
        PyErr_Print()
        rv = 1
    else:
        rv = PyObject_IsTrue(callbackResult)
        Py_DECREF(callbackResult)
    Py_DECREF(self)
    PyGILState_Release(gil)
    return rv

cdef gint on_dom_mouse_down (GtkMozEmbed *embed, gpointer domEvent, 
        PyObject * self):
    cdef char* contextMenu
    cdef PyGILState_STATE gil
    cdef PyObject* callbackResult

    contextMenu = getContextMenu(domEvent)
    if contextMenu:
        gil = PyGILState_Ensure()
        Py_INCREF(self)
        callbackResult = PyObject_CallMethod(self, "createContextMenu", "s",
                contextMenu, NULL)
        freeString(contextMenu)
        if callbackResult == NULL:
            PyErr_Print()
        else:
            Py_DECREF(callbackResult)
        Py_DECREF(self)
        PyGILState_Release(gil)
    return 0

_httpObserverSetup = False
def setupHttpObserver():
    global _httpObserverSetup
    if _httpObserverSetup:
        return
    _httpObserverSetup = True
    result = startObserving()
    if result != NS_OK:
        logging.warn("Error setting up HTTP observer")
