# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

"""MozillaBrowser extension."""

import gtkmozembed
import logging
import gtk

cdef extern from "MozillaBrowserIncludes.h":
    ctypedef struct GtkWidget
    ctypedef struct GtkMozEmbed
    ctypedef struct GObject
    ctypedef struct PyGObject:
        GObject * obj
    ctypedef int gint
    ctypedef unsigned long gulong
    ctypedef unsigned int guint
    ctypedef char gchar
    ctypedef void * gpointer
    ctypedef void * GCallback
    cdef enum GtkWindowType:
        GTK_WINDOW_TOPLEVEL
    cdef GtkMozEmbed * gtk_moz_embed_new()
    cdef GtkWidget* gtk_window_new(GtkWindowType type)
    cdef void gtk_container_add(GtkWidget *, GtkWidget *)
    cdef void gtk_widget_destroy(GtkWidget* widget)
    cdef void gtk_widget_realize(GtkWidget* widget)
    cdef void gtk_widget_unrealize(GtkWidget* widget)
    cdef GtkWidget * gtk_widget_get_parent(GtkWidget* widget)
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
    nsresult setupDummyBrowser(GtkMozEmbed *gtkembed)

cdef extern from "PromptService.h":
    nsresult installPromptService()

cdef extern from "HttpObserver.h":
    nsresult startObserving()

cdef extern from "stdio.h":
    int printf(char* str, ...)

cdef public void log_warning(char* msg):
    gil = PyGILState_Ensure()
    logging.warn(msg)
    PyGILState_Release(gil)

class DOMError(Exception):
    pass
class XPCOMError(Exception):
    pass

cdef GtkMozEmbed *pygtkmozembed_to_c(object pygtkmoz):
    cdef PyGObject *tempObj
    cdef GObject *temp
    tempObj = <PyGObject *>pygtkmoz
    temp = tempObj.obj
    return <GtkMozEmbed *>temp

# setupDragAndDropDummy() exists to work around a weird drag and drop bug.
# DragAndDrop.cc contains the details, at this point we only need to create a
# gtkmozembed widget, that has an X window but isn't shown.  After that we
# pass it to setupDummyBrowser(), defined in DragAndDrop.cc.
def setupDragAndDropDummy():
    # make dummy_window a global in order to keep a reference around so that
    # it doesn't get garbage collected.
    global dummy_window 
    cdef GtkMozEmbed *cWidget

    dummy_window = gtk.Window()
    dummy_widget = gtkmozembed.MozEmbed()
    cWidget = pygtkmozembed_to_c(dummy_widget)
    dummy_window.add(dummy_widget)
    dummy_window.realize()
    dummy_widget.realize()
    rv = setupDummyBrowser(cWidget)
    if rv != NS_OK:
        print "WARNING! setupDummyBrowser failed"

cdef class MozillaBrowser:
    cdef GtkMozEmbed *cWidget
    cdef object widget, URICallBack, finishedCallBack, destroyCallBack
    cdef object contextMenuCallBack
    
    def __new__(self):
        self.widget = gtkmozembed.MozEmbed()
        self.cWidget = pygtkmozembed_to_c(self.widget)

    def __init__(self):
        initializeXPCOMComponents()
        self.URICallBack = None
        self.finishedCallBack = None
        self.destroyCallBack = None
        self.contextMenuCallBack = None
        g_signal_connect(<gpointer *>self.cWidget, "open_uri", 
                <void *>open_uri_cb, <gpointer>self)
        g_signal_connect(<gpointer *>self.cWidget, "dom_mouse_down", 
                <void *>on_dom_mouse_down, <gpointer>self)
        g_signal_connect(<gpointer *>self.cWidget, "new_window",
                <void *>new_window_cb, <gpointer>self);
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

cdef gint new_window_cb (GtkMozEmbed *embed, GtkMozEmbed **retval, guint mask,
        PyObject * self):
    cdef PyGILState_STATE gil
    cdef GtkWidget *w
    cdef GtkMozEmbed *newmoz
    gil = PyGILState_Ensure()
    Py_INCREF(self)
    w = gtk_window_new(GTK_WINDOW_TOPLEVEL)
    newmoz = gtk_moz_embed_new()
    gtk_container_add(w, <GtkWidget*>newmoz)
    g_signal_connect(<gpointer *>newmoz, "open_uri",
            <void *>new_window_open_uri_cb, <gpointer>self)
    gtk_widget_realize(w)
    gtk_widget_realize(<GtkWidget*>newmoz)
    retval[0] = newmoz
    Py_DECREF(self)
    PyGILState_Release(gil)
    return 0

cdef gint new_window_open_uri_cb (GtkMozEmbed *embed, char *uri, PyObject * self):
    cdef PyGILState_STATE gil
    cdef GtkWidget *w
    cdef PyObject* callbackResult
    gil = PyGILState_Ensure()
    Py_INCREF(self)
    callbackResult = PyObject_CallMethod(self, "openUriCallback", "s", uri,
            NULL)
    if(callbackResult == NULL):
        PyErr_Print()
    else:
        Py_DECREF(callbackResult)
    Py_DECREF(self)
    PyGILState_Release(gil)
    w = gtk_widget_get_parent(<GtkWidget*>embed)
    gtk_widget_unrealize(<GtkWidget*>embed)
    gtk_widget_unrealize(w)
    gtk_widget_destroy(<GtkWidget*>embed)
    gtk_widget_destroy(w)
    return 1

_xpcomComponentsInitialized = False
def initializeXPCOMComponents():
    global _xpcomComponentsInitialized
    if _xpcomComponentsInitialized:
        return
    _xpcomComponentsInitialized = True
    result = startObserving()
    if result != NS_OK:
        logging.warn("Error setting up HTTP observer")
    result = installPromptService()
    if result != NS_OK:
        logging.warn("Error setting up Prompt service")
    result = setupDragAndDropDummy()
    if result != NS_OK:
        logging.warn("Error setting up drag and drop dummy element")
