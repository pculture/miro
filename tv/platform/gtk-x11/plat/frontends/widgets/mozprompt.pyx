import logging

cdef extern from "nsError.h":
    ctypedef unsigned int nsresult

cdef extern from "PromptService.h":
    nsresult installPromptService()

cdef public void log_warning(char* msg):
    gil = PyGILState_Ensure()
    logging.warn(msg)
    PyGILState_Release(gil)

def stop_prompts():
    installPromptService()
