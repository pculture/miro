cdef extern from "X11/Xlib.h":
    int CXInitThreads "XInitThreads" ()

def XInitThreads():
    cdef int status
    return CXInitThreads()
