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

"""Event loop handler.

This module handles the democracy event loop which is responsible for network
requests and scheduling.

TODO:
    handle user setting clock back
"""

import threading
import errno
import select
import heapq
import Queue
import logging
from miro import trapcall
from miro import signals
from miro import util

from miro.clock import clock

cumulative = {}

class DelayedCall(object):
    def __init__(self, function, name, args, kwargs):
        self.function = function
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self.canceled = False

    def _unlink(self):
        """Removes the references that this object has to the outside world,
        this eases the GC's work in finding cycles and fixes some memory leaks
        on windows.
        """
        self.function = self.args = self.kwargs = None

    def cancel(self):
        self.canceled = True
        self._unlink()

    def dispatch(self):
        if not self.canceled:
            when = "While handling %s" % self.name
            start = clock()
            trapcall.trap_call(when, self.function, *self.args, **self.kwargs)
            end = clock()
            if end-start > 0.5:
                logging.timing("%s too slow (%.3f secs)",
                               self.name, end-start)
            try:
                total = cumulative[self.name]
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                total = 0
            total += end - start
            cumulative[self.name] = total
            if total > 5.0:
                logging.timing("%s cumulative is too slow (%.3f secs)",
                               self.name, total)
                cumulative[self.name] = 0
        self._unlink()

class Scheduler(object):
    def __init__(self):
        self.heap = []

    def addTimeout(self, delay, function, name, args=None, kwargs=None):
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        scheduledTime = clock() + delay
        dc = DelayedCall(function,  "timeout (%s)" % (name,), args, kwargs)
        heapq.heappush(self.heap, (scheduledTime, dc))
        return dc

    def nextTimeout(self):
        if len(self.heap) == 0:
            return None
        else:
            return max(0, self.heap[0][0] - clock())

    def hasPendingTimeout(self):
        return len(self.heap) > 0 and self.heap[0][0] < clock()

    def processNextTimeout(self):
        time, dc = heapq.heappop(self.heap)
        dc.dispatch()

    def processTimeouts(self):
        while self.hasPendingTimeout():
            self.processNextTimeout()

class CallQueue(object):
    def __init__(self):
        self.queue = Queue.Queue()

    def addIdle(self, function, name, args=None, kwargs=None):
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        dc = DelayedCall(function, "idle (%s)" % (name,), args, kwargs)
        self.queue.put(dc)
        return dc

    def processNextIdle(self):
        dc = self.queue.get()
        dc.dispatch()

    def hasPendingIdle(self):
        return not self.queue.empty()

    def processIdles(self):
        while self.hasPendingIdle():
            self.processNextIdle()

class ThreadPool(object):
    """The thread pool is used to handle calls like gethostbyname() that block
    and there's no asynchronous workaround.  What we do instead is call them
    in a separate thread and return the result in a callback that executes in
    the event loop.
    """
    THREADS = 3

    def __init__(self, eventLoop):
        self.eventLoop = eventLoop
        self.queue = Queue.Queue()
        self.threads = []

    def initThreads(self):
        while len(self.threads) < ThreadPool.THREADS:
            t = threading.Thread(name='ThreadPool - %d' % len(self.threads),
                    target=self.threadLoop)
            t.setDaemon(True)
            t.start()
            self.threads.append(t)

    def threadLoop(self):
        while True:
            nextItem = self.queue.get()
            if nextItem == "QUIT":
                break
            else:
                callback, errback, func, name, args, kwargs, = nextItem
            try:
                result = func(*args, **kwargs)
            except KeyboardInterrupt:
                raise
            except Exception, e:
                func = errback
                name = 'Thread Pool Errback (%s)' % name
                args = (e,)
            else:
                func = callback
                name = 'Thread Pool Callback (%s)' % name
                args = (result,)
            if not self.eventLoop.quitFlag:
                self.eventLoop.idleQueue.addIdle(func, name, args=args)
                self.eventLoop.wakeup()

    def queueCall(self, callback, errback, function, name, *args, **kwargs):
        self.queue.put((callback, errback, function, name, args, kwargs))

    def closeThreads(self):
        for x in xrange(len(self.threads)):
            self.queue.put("QUIT")
        while len(self.threads) > 0:
            x = self.threads.pop()
            try:
                x.join()
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass
            
class EventLoop(signals.SignalEmitter):
    def __init__(self):
        signals.SignalEmitter.__init__(self, 'thread-started', 'begin-loop', 'end-loop')
        self.scheduler = Scheduler()
        self.idleQueue = CallQueue()
        self.urgentQueue = CallQueue()
        self.threadPool = ThreadPool(self)
        self.readCallbacks = {}
        self.writeCallbacks = {}
        self.wakeSender, self.wakeReceiver = util.make_dummy_socket_pair()
        self.addReadCallback(self.wakeReceiver, self._slurpWakerData)
        self.quitFlag = False
        self.clearRemovedCallbacks()
        self.loop_ready = threading.Event()

    def clearRemovedCallbacks(self):
        self.removedReadCallbacks = set()
        self.removedWriteCallbacks = set()

    def _slurpWakerData(self):
        self.wakeReceiver.recv(1024)

    def addReadCallback(self, socket, callback):
        self.readCallbacks[socket.fileno()] = callback

    def removeReadCallback(self, socket):
        del self.readCallbacks[socket.fileno()]
        self.removedReadCallbacks.add(socket.fileno())

    def addWriteCallback(self, socket, callback):
        self.writeCallbacks[socket.fileno()] = callback

    def removeWriteCallback(self, socket):
        del self.writeCallbacks[socket.fileno()]
        self.removedWriteCallbacks.add(socket.fileno())

    def wakeup(self):
        self.wakeSender.send("b")

    def callInThread(self, callback, errback, function, name, *args, **kwargs):
        self.threadPool.queueCall(callback, errback, function, name, *args, **kwargs)

    def loop(self):
        self.emit('thread-started', threading.currentThread())
        self.loop_ready.set()
        while not self.quitFlag:
            self.emit('begin-loop')
            self.clearRemovedCallbacks()
            timeout = self.scheduler.nextTimeout()
            readfds = self.readCallbacks.keys()
            writefds = self.writeCallbacks.keys()
            try:
                readables, writeables, _ = select.select(readfds, writefds, [],
                                                         timeout)
            except select.error, (err, detail):
                if err == errno.EINTR:
                    logging.warning ("eventloop: %s", detail)
                else:
                    raise
            if self.quitFlag:
                break
            self.urgentQueue.processIdles()
            for event in self.generateEvents(readables, writeables):
                event()
                if self.quitFlag:
                    break
                self.urgentQueue.processIdles()
                if self.quitFlag:
                    break
            self.emit('end-loop')

    def generateEvents(self, readables, writeables):
        """Generator that creates the list of events that should be dealt with
        on this iteration of the event loop.  This includes all socket
        read/write callbacks, timeouts and idle calls.  "events" are
        implemented as functions that should be called with no arguments.
        """

        for callback in self.generateCallbacks(writeables,
                self.writeCallbacks, self.removedWriteCallbacks):
            yield callback
        for callback in self.generateCallbacks(readables,
                self.readCallbacks, self.removedReadCallbacks):
            yield callback
        while self.scheduler.hasPendingTimeout():
            yield self.scheduler.processNextTimeout
        while self.idleQueue.hasPendingIdle():
            yield self.idleQueue.processNextIdle

    def generateCallbacks(self, readyList, map, removed):
        for fd in readyList:
            try:
                function = map[fd]
            except KeyError:
                # this can happen the write callback removes the read callback
                # or vise versa
                pass
            else:
                if fd in removed:
                    continue
                when = "While talking to the network"
                def callbackEvent():
                    if not trapcall.trap_call(when, function):
                        del map[fd] 
                yield callbackEvent

_eventLoop = EventLoop()

def addReadCallback(socket, callback):
    """Add a read callback.  When socket is ready for reading, callback will
    be called.  If there is already a read callback installed, it will be
    replaced.
    """
    _eventLoop.addReadCallback(socket, callback)

def removeReadCallback(socket):
    """Remove a read callback.  If there is not a read callback installed for
    socket, a KeyError will be thrown.
    """
    _eventLoop.removeReadCallback(socket)

def addWriteCallback(socket, callback):
    """Add a write callback.  When socket is ready for writing, callback will
    be called.  If there is already a write callback installed, it will be
    replaced.
    """
    _eventLoop.addWriteCallback(socket, callback)

def removeWriteCallback(socket):
    """Remove a write callback.  If there is not a write callback installed for
    socket, a KeyError will be thrown.
    """
    _eventLoop.removeWriteCallback(socket)

def stopHandlingSocket(socket):
    """Convience function to that removes both the read and write callback for
    a socket if they exist."""
    try:
        removeReadCallback(socket)
    except KeyError:
        pass
    try:
        removeWriteCallback(socket)
    except KeyError:
        pass

def addTimeout(delay, function, name, args=None, kwargs=None):
    """Schedule a function to be called at some point in the future.
    Returns a DelayedCall object that can be used to cancel the call.
    """

    dc = _eventLoop.scheduler.addTimeout(delay, function, name, args, kwargs)
    return dc

def addIdle(function, name, args=None, kwargs=None):
    """Schedule a function to be called when we get some spare time.
    Returns a DelayedCall object that can be used to cancel the call.
    """

    dc = _eventLoop.idleQueue.addIdle(function, name, args, kwargs)
    _eventLoop.wakeup()
    return dc

def addUrgentCall(function, name, args=None, kwargs=None):
    """Schedule a function to be called as soon as possible.  This method
    should be used for things like GUI actions, where the user is waiting on
    us.
    """

    dc = _eventLoop.urgentQueue.addIdle(function, name, args, kwargs)
    _eventLoop.wakeup()
    return dc

def callInThread(callback, errback, function, name, *args, **kwargs):
    """Schedule a function to be called in a separate thread. Do not
    put code that accesses the database or the UI here!
    """
    _eventLoop.callInThread(callback, errback, function, name, *args, **kwargs)

lt = None

profile_file = None


def startup():
    threadPoolInit()

    def profile_startup():
        import profile
        def start_loop():
            _eventLoop.loop()
        profile.runctx('_eventLoop.loop()', globals(), locals(), profile_file + ".event_loop")

    global lt
    if profile_file:
        lt = threading.Thread(target=profile_startup, name="Event Loop")
    else:
        lt = threading.Thread(target=_eventLoop.loop, name="Event Loop")
    lt.setDaemon(False)
    lt.start()
    _eventLoop.loop_ready.wait()

def join():
    if lt is not None:
        lt.join()

def quit():
    threadPoolQuit()
    _eventLoop.quitFlag = True
    _eventLoop.wakeup()

def finished():
    """Returns True if the eventloop is done with it's work and has quit, or
    is about to quit.
    """

    if _eventLoop.quitFlag:
        # call wakeup() as a precaution to make sure we really are quitting.
        _eventLoop.wakeup() 
        return True
    else:
        return False

def connect(signal, callback):
    _eventLoop.connect(signal, callback)

def disconnect(signal, callback):
    _eventLoop.disconnect(signal, callback)

def resetEventLoop():
    global _eventLoop
    _eventLoop = EventLoop()

def threadPoolQuit():
    _eventLoop.threadPool.closeThreads()

def threadPoolInit():
    _eventLoop.threadPool.initThreads()

def asIdle(func):
    """Decorator to make a methods run as an idle function

    Suppose you have 2 methods, foo and bar

    @asIdle
    def foo():
        # database operations

    def bar():
        # same database operations as foo

    Then calling foo() is exactly the same as calling addIdle(bar).
    """

    def queuer(*args, **kwargs):
        return addIdle(func, "%s() (using asIdle)" % func.__name__, args=args, kwargs=kwargs)
    return queuer

def asUrgent(func):
    """Like asIdle, but uses addUrgentCall() instead of addIdle()."""

    def queuer(*args, **kwargs):
        return addUrgentCall(func, "%s() (using asUrgent)" % func.__name__, args=args, kwargs=kwargs)
    return queuer

def checkHeapSize():
    logging.info ("Heap size: %d.", len(_eventLoop.scheduler.heap))
    addTimeout(5, checkHeapSize, "Check Heap Size")

def idle_iterate(func, name, args=None, kwargs=None):
    """Iterate over a generator function using addIdle for each iteration.

    This allows long running functions to be split up into distinct steps,
    after each step other idle functions will have a chance to run.

    For example:

    def foo(x, y, z):
        # do some computation
        yield
        # more computation
        yield
        # more computation
        yield

    eventloop.idle_iterate(foo, 'Foo', args=(1, 2, 3))
    """

    if args is None:
        args = ()
    if kwargs is None:
        kwargs = {}
    iter = func(*args, **kwargs)
    addIdle(_idle_iterate_step, name, args=(iter, name))

def _idle_iterate_step(iter, name):
    try:
        rv = iter.next()
    except StopIteration:
        return
    else:
        if rv is not None:
            logging.warn("idle_iterate yield value ignored: %s (%s)", 
                    rv, name)
        addIdle(_idle_iterate_step, name, args=(iter, name))

def idle_iterator(func):
    """Decorator to wrap a generator function in a idle_iterate() call."""
    def queuer(*args, **kwargs):
        return idle_iterate(func, "%s() (using idle_iterator)" % func.__name__, args=args, kwargs=kwargs)
    return queuer
