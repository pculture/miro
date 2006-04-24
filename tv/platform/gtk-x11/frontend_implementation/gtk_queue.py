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
import gtk
import Queue

class MainloopQueue:
    # Class to send data back to the other thread.
    class ReturnData:
        def __init__ (self, callback, *args, **kargs):
            # The action to take
            self.callback = callback
            self.args = args
            self.kargs = kargs
            # Condition to signal that the data is ready.
            self.cond = threading.Condition()
            # The return value
            self.retval = None
            # Whether retval is ready.
            self.done = False
        def main_thread (self):
            # Call the callback as requested, and then notify that the retval is calculated
            self.retval = self.callback (*self.args, **self.kargs)
            self.cond.acquire()
            self.done = True
            self.cond.notify()
            self.cond.release()
        def get_retval (self):
            # Check first and then wait just in case notify gets
            # called before we get to the wait.
            self.cond.acquire()
            while (True):
                if self.done:
                    retval = self.retval
                    break
                self.cond.wait()
            self.cond.release()
            return retval

    def __init__(self, main_thread = threading.currentThread()):
        # Set up our queue.
        self.queue = Queue.Queue()
        # A lock around whether or not the gtk idle function is running.
        self.idle_running_lock = threading.Lock()
        self.idle_running = 0
        self.main_thread = main_thread

    def call_nowait(self, callback, *args, **kargs):
        # put the action on the queue and then make sure the idle is running.
        self.queue.put((callback, args, kargs))
        self.idle_running_lock.acquire()
        if (self.idle_running == 0):
            gobject.idle_add(self._idle)
            self.idle_running = 1
        self.idle_running_lock.release()

    def call(self, callback, *args, **kargs):
        # If we're in the main thread, just call the function
        if self.main_thread == threading.currentThread():
            return callback (*args, **kargs)
        # Otherwise create a ReturnData and use call_nowait to signal it
        return_data = self.ReturnData(callback, *args, **kargs)
        self.call_nowait (return_data.main_thread)
        # And then wait for the return value.
        return return_data.get_retval()

    def _idle(self):
        gtk.threads_enter()
        self.idle_running_lock.acquire()
        try:
            (callback, args, kargs) = self.queue.get_nowait()
        except Queue.Empty:
            self.idle_running = 0
            self.idle_running_lock.release()
            gtk.threads_leave()
            return 0
        else:
            self.idle_running_lock.release()
            callback (*args, **kargs)
            gtk.threads_leave()
            return 1

queue = MainloopQueue()

def gtkAsyncMethod(func):
    """Decorator to make a methods run in the gtk main loop with no return value

    Suppose you have 2 methods, foo and bar

    @gtkAsyncMethod
    def foo():
        # gtk operations

    def bar():
        # same gtk operations as foo

    Then calling foo() is exactly the same as calling queue.call_nowait(bar).
    """

    def queuer(*args, **kargs):
        queue.call_nowait(func, *args, **kargs)
    return queuer


def gtkSyncMethod(func):
    """Decorator to make a methods run in the gtk main loop with a return value

    Suppose you have 2 methods, foo and bar

    @gtkSyncMethod
    def foo():
        # gtk operations

    def bar():
        # same gtk operations as foo

    Then calling foo() is exactly the same as calling queue.call(bar).
    """
    def locker(*args, **kargs):
        return queue.call(func, *args, **kargs)
    return locker
