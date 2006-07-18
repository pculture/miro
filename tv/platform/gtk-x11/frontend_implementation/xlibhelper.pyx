cdef extern from "Xlib.h":
    int CXInitThreads "XInitThreads" ()

def XInitThreads():
    cdef int status
    return CXInitThreads()
