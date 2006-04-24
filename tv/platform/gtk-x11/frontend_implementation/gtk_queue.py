"""Queue methods to be run later in the gtk main loop.

Background (skip if you don't care):

These methods are nessecary because we need to prevent different threads from
accessing gtk and gdk methods simultaniously.  Pygtk provides locking around
gtk, but using this is very tricky.  Instead, we use gobject.idle_add(), which
forces a methods to be run in the gtk main loop.  However, idle_add has a
problem as well.  It doesn't specify which order the methods added will be run
in.  In facte, the most straight-forward implementation of it would use a
priority queue which would allow methods to run out of order.  The
queueMethod function defined here doesn't have that problem.

The short story is: use the queueMethod() to safely run methods that use gtk
methods.

"""

import gobject
import threading

gtkQueue = []
gtkQueueLock = threading.Lock()
def queueMethod(func, *args):
    """Queue a methods to be run at a later time in the gtk main loop.
    Methods queued with this method will be run in the order they are queued.
    """

    gtkQueueLock.acquire()
    try:
        gtkQueue.append((func, args))
        if len(gtkQueue) == 1:
            gobject.idle_add(_runQueue)
    finally:
        gtkQueueLock.release()

def _runQueue():
    global gtkQueue

    gtkQueueLock.acquire()
    try:
        queueCopy = gtkQueue[:]
        gtkQueue = []
    finally:
        gtkQueueLock.release()

    for func, args in queueCopy:
        func(*args)

def gtkMethod(func):
    """Decorator to make a methods run in the main gtk loop.  

    Suppose you have 2 methods, foo and bar

    @gtkMethod
    def foo():
        # gtk operations

    def bar():
        # same gtk operations as foo

    Then calling foo() is exactly the same as calling queueMethod(bar).
    """

    def queuer(*args):
        queueMethod(func, *args)
    return queuer
