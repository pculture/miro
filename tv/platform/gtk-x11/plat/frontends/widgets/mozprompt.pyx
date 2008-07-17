import logging

cdef extern from "nsError.h":
    ctypedef unsigned int nsresult

cdef extern from "PromptService.h":
    nsresult installPromptService()

cdef extern from "Python.h":
    ctypedef int PyGILState_STATE
    PyGILState_STATE PyGILState_Ensure()
    void PyGILState_Release(PyGILState_STATE)

cdef public void log_warning(char* msg):
    cdef PyGILState_STATE gil 
    gil = PyGILState_Ensure()
    logging.warn(msg)
    PyGILState_Release(gil)

def stop_prompts():
    installPromptService()
