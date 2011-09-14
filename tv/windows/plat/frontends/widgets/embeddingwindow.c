/*
# Miro - an RSS based video player application
# Copyright (C) 2011
# Participatory Culture Foundation
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
*/

/* embeddingwindow -- Create Windows for embedding
 *
 * This module handles creating HWNDs to use to embed other components like
 * gstreamer.
 *
 * We define an extension type that allows us to control the HWND from python.
 *
 */

#include <windows.h>
#include <windowsx.h>
#include <Python.h>
#include "structmember.h"

/* Module-level variables */

static int initialized = 0;
static HWND hidden_window = 0;
static TCHAR window_class_name[] = TEXT("Miro Embedding Window");

/* EmbeddingWindow extension type */

typedef struct {
    PyObject_HEAD
    HWND hwnd;
    PyObject* py_hwnd;
    PyObject* event_handler;
    unsigned char enable_motion;
    int last_mouse_x;
    int last_mouse_y;
} EmbeddingWindow;

/*
 * call_event_handler -- Call an event handler method for our EmbeddingWindow
 */
static void
call_event_handler(EmbeddingWindow* self,
                   const char* method_name,
                   PyObject *args)
{
    PyObject* method = NULL;
    PyObject* result = NULL;

    /* Exit if we don't have an event handler */
    if(!self->event_handler || self->event_handler == Py_None) {
        return;
    }

    /* Call the method for this event */
    method = PyObject_GetAttrString(self->event_handler, method_name);
    if(!method) goto error;

    result = PyObject_CallObject(method, args);
    if(!result) goto error;

    goto finally;

error:
    /* Error handling code */
    PyErr_Print();
    PyErr_Clear();

finally:
    /* cleanup code */
    Py_XDECREF(method);
    Py_XDECREF(result);
}

/*
 * win32 windows procedure
 */

static LRESULT CALLBACK
wnd_proc(HWND hwnd, UINT msg, WPARAM wparam, LPARAM lparam)
{
    PyObject* arglist;
    EmbeddingWindow* self;
    PyGILState_STATE gstate;
    int x, y;

    self = (EmbeddingWindow*) GetWindowLongPtr(hwnd, GWLP_USERDATA);
    if(!self) {
        /* We've already destroyed the window, just call DefWindowProc */
        return DefWindowProc(hwnd, msg, wparam, lparam);
    }

    switch (msg) {
        /* Handle message.  If we are doing anything with the python
         * interpreter, make sure to acquire the GIL first
         */
        case WM_MOUSEMOVE:
            x = GET_X_LPARAM(lparam);
            y = GET_Y_LPARAM(lparam);

            /* Threading issue: Normally we should acquire the GIL before
             * accessing enable_motion, but it's safe here since it's a
             * boolean var.
             */
            if(self->enable_motion) {
                /* Check that we actually have a new coordinate.  When we
                 * map/unmap windows, we get an extra WM_MOUSEMOVE message.
                 */
                if(x == self->last_mouse_x &&
                   y == self->last_mouse_y) {
                    break;
                }
                self->last_mouse_x = x;
                self->last_mouse_y = y;

                gstate = PyGILState_Ensure();
                arglist = Py_BuildValue("(ii)", GET_X_LPARAM(lparam),
                                        GET_Y_LPARAM(lparam));
                call_event_handler(self, "on_mouse_move", arglist);
                Py_DECREF(arglist);
                PyGILState_Release(gstate);
            }
            break;

        case WM_PAINT:
            gstate = PyGILState_Ensure();
            arglist = Py_BuildValue("()");
            call_event_handler(self, "on_paint", arglist);
            Py_DECREF(arglist);
            PyGILState_Release(gstate);
            break;

        case WM_LBUTTONDBLCLK:
            gstate = PyGILState_Ensure();
            arglist = Py_BuildValue("(ii)", GET_X_LPARAM(lparam),
                                    GET_Y_LPARAM(lparam));
            call_event_handler(self, "on_double_click", arglist);
            Py_DECREF(arglist);
            PyGILState_Release(gstate);
            break;

        default:
            return DefWindowProc(hwnd, msg, wparam, lparam);
    }
    return 0;
}

static PyObject*
EmbeddingWindow_new(PyTypeObject *type,
                    PyObject* args,
                    PyObject* kwargs)
{
    EmbeddingWindow* self;

    self = (EmbeddingWindow *)type->tp_alloc(type, 0);
    if (self != NULL) {
        /* Initialize python objects to None */
        Py_INCREF(Py_None);
        self->py_hwnd = Py_None;
        Py_INCREF(Py_None);
        self->event_handler = Py_None;
        /* C object are already initialized to 0 */
    }
    return (PyObject *)self;
}

static int
destroy_window(EmbeddingWindow* self)
{
    int success;
    PyObject* tmp;

    SetWindowLongPtr(self->hwnd, GWLP_USERDATA, NULL);
    success = DestroyWindow(self->hwnd);
    /* Regardless of if DestroyWindow worked or not, unset attributes */
    tmp = self->py_hwnd;
    Py_INCREF(Py_None);
    self->py_hwnd = Py_None;
    self->hwnd = 0;
    return success;
}

static void
EmbeddingWindow_dealloc(EmbeddingWindow* self)
{
    /* Ensure HWND is destroyed */
    if(self->hwnd) {
        destroy_window(self);
        /* We can't really handle errors here if DestroyWindow fails, so we
         * just ignore them.
         */
    }
    /* DECREF our python objects */
    Py_XDECREF(self->event_handler);
    Py_XDECREF(self->py_hwnd);
}

/*
 * Check to see that the hwnd member variable is valid
 */

static int
ensure_hwnd(EmbeddingWindow* self)
{
    if(!self->hwnd) {
        PyErr_SetString(PyExc_ValueError,
                        "HWND is NULL (was the window destroyed?)");
        return 0;
    }
    return 1;
}

static int
EmbeddingWindow_init(EmbeddingWindow* self,
                     PyObject* args,
                     PyObject* kwargs)
{
    PyObject* tmp;

    if(!initialized) {
        PyErr_SetString(PyExc_ValueError, "Not initialized");
        return -1;
    }

    /* Create Window, use hidden_window as it's parent. */
    self->hwnd = CreateWindow(window_class_name, window_class_name,
                              WS_CHILD, CW_USEDEFAULT, CW_USEDEFAULT,
                              1, 1, hidden_window, NULL,
                              GetModuleHandle(NULL), NULL);
    if(!self->hwnd) {
        PyErr_SetFromWindowsErr(0);
        return -1;
    }

    /* Convert our HWND to a python int for our member variable.
     * This seems dangerous because on 64-bit windows an HWND is 64 bits,
     * however, it seems that the upper 32 bits are never used.  See:
     * http://stackoverflow.com/questions/1822667/how-can-i-share-hwnd-between-32-and-64-bit-applications-in-win-x64
     *
     * The advantage of using a python int is that's what Gdk and Gstreamer
     * use.
     */
    tmp = self->py_hwnd;
    self->py_hwnd = PyInt_FromLong((long)self->hwnd);
    if(!self->py_hwnd) {
        self->py_hwnd = tmp;
        DestroyWindow(self->hwnd);
        self->hwnd = 0;
        return -1;
    }
    Py_XDECREF(tmp);

    /* Set window user data to point to our python object
     * NOTE: a return value of 0 may or may not mean failure.  We have to
     * call SetError(0), then SetWindowLongPtr, then GetError() to check
     * if the function fails.  Let's just assume it works.
     * */
    SetWindowLongPtr(self->hwnd, GWLP_USERDATA, (LONG_PTR)self);

    return 0;
}

static PyObject*
EmbeddingWindow_set_event_handler(EmbeddingWindow* self,
                                  PyObject* args)
{
    PyObject* event_handler;
    PyObject* tmp;

    if (!PyArg_ParseTuple(args, "O:EmbeddingWindow.set_event_handler",
                          &event_handler)) {
        return NULL;
    }

    tmp = self->event_handler;
    Py_INCREF(event_handler);
    self->event_handler = event_handler;
    Py_XDECREF(tmp);

    Py_RETURN_NONE;
}

static PyObject*
EmbeddingWindow_enable_motion_events(EmbeddingWindow* self,
                                     PyObject* args)
{
    PyObject* enable;

    if (!PyArg_ParseTuple(args, "O:EmbeddingWindow.set_motion_events",
                          &enable)) {
        return NULL;
    }
    self->enable_motion = PyObject_IsTrue(enable);
    Py_RETURN_NONE;
}

static PyObject*
EmbeddingWindow_attach(EmbeddingWindow* self,
                       PyObject* args)
{
    long parent_hwnd;
    long x, y, width, height;

    if(!ensure_hwnd(self)) return NULL;

    if (!PyArg_ParseTuple(args, "lllll:EmbeddingWindow.attach",
                          &parent_hwnd, &x, &y, &width, &height)) {
        return NULL;
    }

    /* Cast long value to an HWND.  See the note in EmbeddingWindow_init()
     * for why this is okay
     */
    SetParent(self->hwnd, (HWND)parent_hwnd);
    MoveWindow(self->hwnd, x, y, width, height, FALSE);
    ShowWindow(self->hwnd, SW_SHOW);

    Py_RETURN_NONE;
}

static PyObject*
EmbeddingWindow_reposition(EmbeddingWindow* self,
                           PyObject* args)
{
    long x, y, width, height;

    if(!ensure_hwnd(self)) return NULL;
    if (!PyArg_ParseTuple(args, "llll:EmbeddingWindow.reposition",
                          &x, &y, &width, &height)) {
        return NULL;
    }

    MoveWindow(self->hwnd, x, y, width, height, TRUE);

    Py_RETURN_NONE;
}

static PyObject*
EmbeddingWindow_detach(EmbeddingWindow* self,
                       PyObject* args)
{
    if(!ensure_hwnd(self)) return NULL;

    ShowWindow(self->hwnd, SW_HIDE);
    SetParent(self->hwnd, hidden_window);

    Py_RETURN_NONE;
}

static PyObject*
EmbeddingWindow_destroy(EmbeddingWindow* self,
                        PyObject* args)
{
    PyObject* tmp;

    if(self->hwnd) {
        if(!destroy_window(self)) {
            PyErr_SetFromWindowsErr(0);
            return NULL;
        }
    }

    Py_RETURN_NONE;
}

static PyObject*
EmbeddingWindow_paint_black(EmbeddingWindow* self,
                            PyObject* args)
{
    PAINTSTRUCT ps;
    HDC hdc;

    if(!ensure_hwnd(self)) return NULL;

    hdc = BeginPaint(self->hwnd, &ps);
    FillRect(hdc, &ps.rcPaint, (HBRUSH) GetStockObject(BLACK_BRUSH));
    EndPaint(self->hwnd, &ps);

    Py_RETURN_NONE;
}

/* Module functions */

static PyObject*
embeddingwindow_init(PyObject* self, PyObject* args)
{
    WNDCLASSEX wcex;
    HANDLE hInstance;

    if(initialized) {
        /* already initialized, just return */
        Py_RETURN_NONE;
    }

    /* Register the window class */
    hInstance = GetModuleHandle(NULL);

    wcex.cbSize = sizeof(WNDCLASSEX);
    wcex.style          = CS_HREDRAW | CS_VREDRAW | CS_DBLCLKS;
    wcex.lpfnWndProc    = wnd_proc;
    wcex.cbClsExtra     = 0;
    wcex.cbWndExtra     = 0;
    wcex.hInstance      = hInstance;
    wcex.hIcon          = NULL;
    wcex.hCursor        = LoadCursor(NULL, IDC_ARROW);
    wcex.hbrBackground  = NULL;
    wcex.lpszMenuName   = NULL;
    wcex.lpszClassName  = window_class_name;
    wcex.hIconSm        = NULL;
    if (!RegisterClassEx(&wcex)) {
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }

    /* Set double-click time to match GTK's */
    SetDoubleClickTime(250);

    /* Create a hidden toplevel window to for detached windows */
    hidden_window = CreateWindow(window_class_name, window_class_name,
                                 WS_OVERLAPPED, CW_USEDEFAULT, CW_USEDEFAULT,
                                 1, 1, NULL, NULL, hInstance, NULL);
    if(!hidden_window) {
        /* Undo our previous work */
        UnregisterClass(window_class_name, hInstance);
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }

    /* Success!  Set global initialized variable and return */

    initialized = 1;
    Py_RETURN_NONE;
}


static PyMethodDef EmbeddingWindow_methods[] = {
    { "set_event_handler", (PyCFunction)EmbeddingWindow_set_event_handler,
        METH_VARARGS, "Set object to handle events on the window" },
    { "enable_motion_events",
            (PyCFunction)EmbeddingWindow_enable_motion_events, METH_VARARGS,
            "enable/disable motion events on a windows"},
    { "attach", (PyCFunction)EmbeddingWindow_attach, METH_VARARGS,
        "attach window to a parent window and show it" },
    { "reposition", (PyCFunction)EmbeddingWindow_reposition, METH_VARARGS,
        "Move window inside its parent window" },
    { "detach", (PyCFunction)EmbeddingWindow_detach, METH_NOARGS,
        "Detach window to a parent window and hide it" },
    { "destroy", (PyCFunction)EmbeddingWindow_destroy, METH_NOARGS,
        "destroy a window" },
    { "paint_black", (PyCFunction)EmbeddingWindow_paint_black, METH_NOARGS,
        "Fill a window with black" },
    {NULL}  /* Sentinel */
};

static PyMemberDef EmbeddingWindow_members[] = {
    {"hwnd", T_OBJECT_EX, offsetof(EmbeddingWindow, py_hwnd), READONLY,
        "window handle"},
    {NULL}  /* Sentinel */
};

static PyTypeObject EmbeddingWindowType = {
    PyObject_HEAD_INIT(NULL)
        0,                         /*ob_size*/
    "embeddingwindow.EmbeddingWindow", /*tp_name*/
    sizeof(EmbeddingWindow),   /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)EmbeddingWindow_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT,        /*tp_flags*/
    "Window for embedding other components", /* tp_doc */
    0,                         /* tp_traverse */
    0,                         /* tp_clear */
    0,                         /* tp_richcompare */
    0,                         /* tp_weaklistoffset */
    0,                         /* tp_iter */
    0,                         /* tp_iternext */
    EmbeddingWindow_methods,   /* tp_methods */
    EmbeddingWindow_members,   /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)EmbeddingWindow_init, /* tp_init */
    0,                         /* tp_alloc */
    EmbeddingWindow_new,       /* tp_new */
};



static PyMethodDef embeddingwindow_methods[] = 
{
    { "init", embeddingwindow_init, METH_NOARGS,
        "initialize module" },
    { NULL, NULL, 0, NULL }
};

PyMODINIT_FUNC initembeddingwindow(void)
{
    PyObject* m;

    if (PyType_Ready(&EmbeddingWindowType) < 0)
        return;

    m = Py_InitModule("embeddingwindow", embeddingwindow_methods);
    Py_INCREF(&EmbeddingWindowType);
    PyModule_AddObject(m, "EmbeddingWindow",
                       (PyObject *)&EmbeddingWindowType);
}
