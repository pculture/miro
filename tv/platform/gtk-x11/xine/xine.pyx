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
    void xineAttach(_Xine* xine, char* displayName, Drawable d)
    void xineSetArea(_Xine* xine, int xpos, int ypos, int width, int height)
    void xineDetach(_Xine* xine)
    int xineCanPlayFile(_Xine* xine, char* filename)
    void xinePlayFile(_Xine* xine, char* filename)
    void xineSetPlaying(_Xine* xine, int isPlaying)
    void xineSetVolume(_Xine* xine, int volume)
    int xineGetVolume(_Xine* xine)
    void xineGotExposeEvent(_Xine* xine, int x, int y, int width, int height)
    void xineSeek(_Xine* xine, int position)
    int xineGetPosLength(_Xine* xine, int* position, int* length)

class CantQueryPositionLength(Exception):
    pass

cdef class Xine:
    # Wrapper for the Xine class
    cdef _Xine* xine
    cdef object eosCallback

    def __new__(self):
        self.xine = xineCreate(onXineEvent, <void*>self)
        self.eosCallback = None
    def __dealloc__(self):
        xineDestroy(self.xine)
    def attach(self, char* displayName, int drawable):
        xineAttach(self.xine, displayName, drawable)
    def detach(self):
        xineDetach(self.xine)
    def setArea(self, int xpos, int ypos, int width, int height):
        xineSetArea(self.xine, xpos, ypos, width, height)
    def canPlayFile(self, char* filename):
        # we convert xineCanPlayFile's return value to a python boolean
        return xineCanPlayFile(self.xine, filename) and True or False
    def playFile(self, char* filename):
        xinePlayFile(self.xine, filename)
    def play(self):
        xineSetPlaying(self.xine, 1)
    def pause(self):
        xineSetPlaying(self.xine, 0)
    def getVolume(self):
        return xineGetVolume(self.xine)
    def setVolume(self, volume):
        volume = min(max(volume, 0), 100)
        xineSetVolume(self.xine, volume)
    def gotExposeEvent(self, int x, int y, int width, int height):
        xineGotExposeEvent(self.xine, x, y, width, height)
    def seek(self, int position):
        xineSeek(self.xine, position)
    def setEosCallback(self, callback):
        """Set the callback invoke when xine reaches the end of its stream.
        Pass in None to clear the callback

        NOTE: this callback will be invoked outside of the gtk main thread,
        use gobject.idle_add if you need to use any gtk methods.
        """
        self.eosCallback = callback
    def onEosEvent(self):
        if self.eosCallback:
            self.eosCallback()
    def getPositionAndLength(self):
        """Try to query the current stream position and stream length.  If
        Xine doesn't know the values yet we throw a CantQueryPositionLength
        Exception.
        """
        cdef int position, length
        if xineGetPosLength(self.xine, &position, &length) == 0:
            raise CantQueryPositionLength
        else:
            return position, length

cdef void onXineEvent(void* data, xine_event_t* event):
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
