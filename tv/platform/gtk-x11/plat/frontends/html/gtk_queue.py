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

"""Queue methods to be run later in the gtk main loop.

Background (skip if you don't care):

These methods are nessecary because we need to prevent different threads from
accessing gtk and gdk methods simultaniously.  Pygtk provides locking around
gtk, but using this is very tricky.  Instead, we use gobject.idle_add(), which
forces a methods to be run in the gtk main loop.  However, idle_add has a
problem as well.  It doesn't specify which order the methods added will be run
in.  In fact, the most straight-forward implementation of it would use a
priority queue which would allow methods to run out of order.  The
gtkSyncMethod and gtkAsyncMethod functions defined here doesn't have that
problem.

The short story is: use the gtkAsyncMethod to safely run methods that use
gtk objects if you don't care about the return value.  Use gtkSyncMethod if
you do.

"""

import gobject
import threading
import gtk
import Queue
import sys
import traceback
import logging

from miro.clock import clock

class ExceptionContainer:
    def __init__(self, exc_info):
        self.type, self.value, self.tb = exc_info

    def reraise(self):
        raise self.type, self.value, self.tb

class MainloopQueue:
    # Class to send data back to the other thread.
    class ReturnData:
        def __init__ (self, callback, args = None, kwargs = None):
            if args == None: args = []
            if kwargs == None: kwargs = {}

            # The action to take
            self.callback = callback
            self.args = args
            self.kwargs = kwargs
            # Condition to signal that the data is ready.
            self.cond = threading.Condition()
            # The return value
            self.retval = None
            # Whether retval is ready.
            self.done = False
        def main_thread (self):
            # Call the callback as requested, and then notify that the retval is calculated
            try:
                self.retval = self.callback (*self.args, **self.kwargs)
            except Exception, e:
                self.retval = ExceptionContainer(sys.exc_info())
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

    def call_nowait(self, callback, args = None, kwargs = None):
        if args == None: args = []
        if kwargs == None: kwargs = {}

        # put the action on the queue and then make sure the idle is running.
        self.queue.put((callback, args, kwargs))
        self.idle_running_lock.acquire()
        if (self.idle_running == 0):
            gobject.idle_add(self._idle)
            self.idle_running = 1
        self.idle_running_lock.release()

    def call(self, callback, args = None, kwargs = None):
        if args == None: args = []
        if kwargs == None: kwargs = {}

        # If we're in the main thread, just call the function
        if self.main_thread == threading.currentThread():
            return callback (*args, **kwargs)
        # Otherwise create a ReturnData and use call_nowait to signal it
        return_data = self.ReturnData(callback, args, kwargs)
        start = clock()
        self.call_nowait (return_data.main_thread)
        # And then wait for the return value.
        retval = return_data.get_retval()
        end = clock()
        if end - start > 1:
            logging.timing ("gtkSyncMethod: %s took too long: %.3f", callback, end - start)
        if isinstance(retval, ExceptionContainer):
            retval.reraise()
        else:
            return retval

    def _idle(self):
        gtk.gdk.threads_enter()
        self.idle_running_lock.acquire()
        try:
            (callback, args, kwargs) = self.queue.get_nowait()
        except Queue.Empty:
            self.idle_running = 0
            self.idle_running_lock.release()
            gtk.gdk.threads_leave()
            return 0
        else:
            self.idle_running_lock.release()
            try:
                start = clock()
                callback (*args, **kwargs)
                end = clock()
                if end - start > 1:
                    logging.timing ("gtkAsyncMethod: %s took too long: %.3f", callback, end - start)
            except:
                logging.exception ("Exception in a gtkAsyncMethod:")
            gtk.gdk.threads_leave()
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

    def queuer(*args, **kwargs):
        queue.call_nowait(func, args=args, kwargs=kwargs)
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
    def locker(*args, **kwargs):
        return queue.call(func, args=args, kwargs=kwargs)
    return locker
