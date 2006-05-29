"""Event loop handler.

This module handles the democracy event loop which is responsible for network
requests and scheduling.

TODO:
    handle user setting clock back
"""

import threading
import socket
import errno
import select
import heapq
import Queue
import util
import database

from BitTornado.clock import clock

import util

class DelayedCall(object):
    def __init__(self, function, name, args, kwargs):
        self.function = function
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self.canceled = False

    def cancel(self):
        self.canceled = True

    def dispatch(self):
        if not self.canceled:
            when = "While handling timeout (%s)" % self.name
            #start = clock()
            util.trapCall(when, self.function, *self.args, **self.kwargs)
            #end = clock()
            #if end-start > 0.05:
            #    print "WARNING: %s too slow (%.3f secs)" % (
            #        self.name, end-start)

class Scheduler(object):
    def __init__(self):
        self.heap = []

    def addTimeout(self, delay, function, name, args=None, kwargs=None):
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        scheduledTime = clock() + delay
        dc = DelayedCall(function, name, args, kwargs)
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
        self.queue.put((function, name, args, kwargs))

    def processNextIdle(self):
        function, name, args, kwargs = self.queue.get()
        #start = clock()
        util.trapCall("While handling idle call (%s)" % (name,),
                function, *args, **kwargs)
        #end = clock()
        #if end-start > 0.05:
        #    print "WARNING: %s too slow (%.3f secs)" % (
        #        name, end-start)

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
        for x in xrange(self.THREADS):
            t = threading.Thread(name='ThreadPool - %d' % x,
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
                callback, errback, func, args, kwargs, = nextItem
            try:
                result = func(*args, **kwargs)
            except Exception, e:
                self.eventLoop.idleQueue.addIdle(errback, 
                        'Thread Pool Errback', args=(e,))
            else:
                self.eventLoop.idleQueue.addIdle(callback, 
                    'Thread Pool Callback', args=(result,))
            self.eventLoop.wakeup()

    def queueCall(self, callback, errback, function, *args, **kwargs):
        self.queue.put((callback, errback, function, args, kwargs))

    def closeThreads(self):
        for x in xrange(self.THREADS):
            self.queue.put("QUIT")
        for t in self.threads:
            t.join()

class EventLoop(object):
    def __init__(self):
        self.scheduler = Scheduler()
        self.idleQueue = CallQueue()
        self.urgentQueue = CallQueue()
        self.threadPool = ThreadPool(self)
        self.readCallbacks = {}
        self.writeCallbacks = {}
        self.wakeSender, self.wakeReceiver = util.makeDummySocketPair()
        self.addReadCallback(self.wakeReceiver, self._slurpWakerData)
        self.quitFlag = False
        self.delegate = None

    def _slurpWakerData(self):
        self.wakeReceiver.recv(1024)

    def setDelegate(self, delegate):
        self.delegate = delegate

    def addReadCallback(self, socket, callback):
        self.readCallbacks[socket.fileno()] = callback

    def removeReadCallback(self, socket):
        del self.readCallbacks[socket.fileno()]

    def addWriteCallback(self, socket, callback):
        self.writeCallbacks[socket.fileno()] = callback

    def removeWriteCallback(self, socket):
        del self.writeCallbacks[socket.fileno()]

    def wakeup(self):
        self.wakeSender.send("b")

    def callInThread(self, callback, errback, function, *args, **kwargs):
        self.threadPool.queueCall(callback, errback, function, *args, **kwargs)

    def _beginLoop(self):
        if self.delegate is not None and hasattr(self.delegate, "beginLoop"):
            self.delegate.beginLoop(self)

    def _endLoop(self):
        if self.delegate is not None and hasattr(self.delegate, "endLoop"):
            self.delegate.endLoop(self)

    def loop(self):
        database.set_thread()
        while not self.quitFlag:
            self._beginLoop()
            timeout = self.scheduler.nextTimeout()
            readfds = self.readCallbacks.keys()
            writefds = self.writeCallbacks.keys()
            try:
                readables, writeables, _ = select.select(readfds, writefds, [],
                                                         timeout)
            except select.error, (err, detail):
                if err == errno.EINTR:
                    print "DTV: eventloop: %s" % detail
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
            self._endLoop()

    def generateEvents(self, readables, writeables):
        """Generator that creates the list of events that should be dealt with
        on this iteration of the event loop.  This includes all socket
        read/write callbacks, timeouts and idle calls.  "events" are
        implemented as functions that should be called with no arguments.
        """

        for callback in self.generateCallbacks(writeables,
                self.writeCallbacks):
            yield callback
        for callback in self.generateCallbacks(readables,
                self.readCallbacks):
            yield callback
        while self.scheduler.hasPendingTimeout():
            yield self.scheduler.processNextTimeout
        while self.idleQueue.hasPendingIdle():
            yield self.idleQueue.processNextIdle

    def generateCallbacks(self, readyList, map):
        for fd in readyList:
            try:
                function = map[fd]
            except KeyError:
                # this can happen the write callback removes the read callback
                # or vise versa
                pass
            else:
                when = "While talking to the network"
                def callbackEvent():
                    if not util.trapCall(when, function):
                        del map[fd] 
                yield callbackEvent

_eventLoop = EventLoop()

def setDelegate(delegate):
    _eventLoop.setDelegate(delegate)

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

    _eventLoop.idleQueue.addIdle(function, name, args, kwargs)
    _eventLoop.wakeup()

def addUrgentCall(function, name, args=None, kwargs=None):
    """Schedule a function to be called as soon as possible.  This method
    should be used for things like GUI actions, where the user is waiting on
    us.
    """

    _eventLoop.urgentQueue.addIdle(function, name, args, kwargs)
    _eventLoop.wakeup()

def callInThread(callback, errback, function, *args, **kwargs):
    """Get the numerical IP address for a IPv4 host, on success callback will
    be called with the adrress, on failure errback will be called with the
    exception.
    """
    _eventLoop.callInThread(callback, errback, function, *args, **kwargs)

lt = None

def startup():
    global lt
    lt = threading.Thread(target=_eventLoop.loop, name="Event Loop")
    lt.setDaemon(False)
    lt.start()

def join():
    global lt
    lt.join()
    database.set_thread()

def quit():
    _eventLoop.quitFlag = True
    _eventLoop.wakeup()

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
