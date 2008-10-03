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

##############################################################################
# Xine module.  
#
# Contains the Xine class which is used to control libxine.
# Code in here is basically just a wrapper for the functions in xine_impl.c.
# See that file if you want to know what's going on under the hood
#
##############################################################################

cdef extern from "X11/Xlib.h":
    ctypedef unsigned long Drawable

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

cdef extern from "xine.h":
    ctypedef struct xine_event_t:
        int type
    ctypedef void (*xine_event_listener_cb_t) (void *user_data,
            xine_event_t *event)
    enum dummy:
        XINE_EVENT_UI_PLAYBACK_FINISHED

cdef extern from "xine_impl.h":
    ctypedef struct _Xine

    _Xine* xineCreate(xine_event_listener_cb_t event_callback, 
            void* event_callback_data)
    void xineDestroy(_Xine* xine)
    void xineAttach(_Xine* xine, char* displayName, Drawable d, char *driver, int sync, int use_xv_hack)
    void xineSetArea(_Xine* xine, int xpos, int ypos, int width, int height)
    void xineDetach(_Xine* xine)
    int xineCanPlayFile(_Xine* xine, char* filename)
    void xineSelectFile(_Xine* xine, char* filename)
    void xineSetPlaying(_Xine* xine, int isPlaying)
    void xineSetViz(_Xine* xine, char *viz)
    void xineSetVolume(_Xine* xine, int volume)
    int xineGetVolume(_Xine* xine)
    void xineGotExposeEvent(_Xine* xine, int x, int y, int width, int height)
    void xineSeek(_Xine* xine, int position)
    int xineGetPosLength(_Xine* xine, int* position, int* length)
    char* xineVersion()

def getXineVersion():
    return xineVersion()

class CantQueryPositionLength(Exception):
    pass

cdef class Xine:
    # Wrapper for the Xine class
    cdef _Xine* xine
    cdef object eosCallback

    def __new__(self):
        self.xine = xineCreate(on_xine_event, <void*>self)
        self.eosCallback = None
    def __dealloc__(self):
        xineDestroy(self.xine)
    def attach(self, char* displayName, int drawable, char *driver, sync, use_xv_hack):
        xineAttach(self.xine, displayName, drawable, driver, sync, use_xv_hack)
    def detach(self):
        xineDetach(self.xine)
    def set_area(self, int xpos, int ypos, int width, int height):
        xineSetArea(self.xine, xpos, ypos, width, height)
    def can_play_file(self, char* filename):
        # we convert xineCanPlayFile's return value to a python boolean
        return xineCanPlayFile(self.xine, filename) and True or False
    def select_file(self, char* filename):
        xineSelectFile(self.xine, filename)
    def play(self):
        xineSetPlaying(self.xine, 1)
    def pause(self):
        xineSetPlaying(self.xine, 0)
    def set_viz(self, viz):
        xineSetViz(self.xine, viz)
    def set_volume(self, volume):
        volume = min(max(volume, 0), 100)
        xineSetVolume(self.xine, volume)
    def get_volume(self):
        return xineGetVolume(self.xine)
    def got_expose_event(self, int x, int y, int width, int height):
        xineGotExposeEvent(self.xine, x, y, width, height)
    def seek(self, int position):
        xineSeek(self.xine, position)
    def set_eos_callback(self, callback):
        """Set the callback invoke when xine reaches the end of its stream.
        Pass in None to clear the callback

        NOTE: this callback will be invoked outside of the gtk main thread,
        use gobject.idle_add if you need to use any gtk methods.
        """
        self.eosCallback = callback
    def on_eos_event(self):
        if self.eosCallback:
            self.eosCallback()
    def get_position_and_length(self):
        """Try to query the current stream position and stream length.  If
        Xine doesn't know the values yet we throw a CantQueryPositionLength
        Exception.
        """
        cdef int position, length
        if xineGetPosLength(self.xine, &position, &length) == 0:
            raise CantQueryPositionLength
        else:
            return position, length

cdef void on_xine_event(void* data, xine_event_t* event):
    cdef PyObject* self
    cdef PyGILState_STATE gil
    cdef PyObject* result

    if event.type == XINE_EVENT_UI_PLAYBACK_FINISHED:
        self = <PyObject*>data
        gil = PyGILState_Ensure()
        Py_INCREF(self)
        result = PyObject_CallMethod(self, "onEosEvent", "", NULL)
        if(result == NULL):
            PyErr_Print()
        else:
            Py_DECREF(result)
        Py_DECREF(self)
        PyGILState_Release(gil)
