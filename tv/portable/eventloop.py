"""Event loop handler.

This module handles the democracy event loop which is responsible for network
requests and scheduling.

TODO:
    handle user setting clock back
"""

import threading
import socket
import select
import heapq
import Queue
import util

from BitTornado.clock import clock

import util

class DelayedCall(object):
    def __init__(self, function, args, kwargs):
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.canceled = False

    def cancel(self):
        self.canceled = True

    def dispatch(self):
        if not self.canceled:
            try:
                self.function(*self.args, **self.kwargs)
            except:
                util.failedExn("While handling timeout")

class Scheduler(object):
    def __init__(self):
        self.heap = []

    def addTimeout(self, delay, function, args=None, kwargs=None):
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        scheduledTime = clock() + delay
        dc = DelayedCall(function, args, kwargs)
        heapq.heappush(self.heap, (scheduledTime, dc))
        return dc

    def nextTimeout(self):
        if len(self.heap) == 0:
            return None
        else:
            return max(0, self.heap[0][0] - clock())

    def processTimeouts(self):
        while len(self.heap) > 0 and self.heap[0][0] < clock():
            time, dc = heapq.heappop(self.heap)
            dc.dispatch()

class IdleQueue(object):
    def __init__(self):
        self.queue = Queue.Queue()

    def addIdle(self, function, args=None, kwargs=None):
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        self.queue.put((function, args, kwargs))

    def processIdles(self):
        while not self.queue.empty():
            function, args, kwargs = self.queue.get()
            try:
                function(*args, **kwargs)
            except:
                util.failedExn("While handling idle call")

class EventLoop(object):
    def __init__(self):
        self.scheduler = Scheduler()
        self.idleQueue = IdleQueue()
        self.readCallbacks = {}
        self.writeCallbacks = {}
        self.wakeSender, self.wakeReceiver = util.makeDummySocketPair()
        self.addReadCallback(self.wakeReceiver, self._slurpWakerData)
        self.quitFlag = False

    def _slurpWakerData(self):
        self.wakeReceiver.recv(1024)

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

    def doCallbacks(self, readyList, map):
        for fd in readyList:
            try:
                function = map[fd]
            except KeyError:
                util.failedExn("While talking to the network")
            else:
                try:
                    function()
                except:
                    util.failedExn("While talking to the network")
                    del map[fd] 
                    # remove the callback, since it's likely to fail forever

    def loop(self):
        while not self.quitFlag:
            timeout = self.scheduler.nextTimeout()
            readfds = self.readCallbacks.keys()
            writefds = self.writeCallbacks.keys()
            readables, writeables, _ = select.select(readfds, writefds, [],
                    timeout)
            self.doCallbacks(writeables, self.writeCallbacks)
            self.doCallbacks(readables, self.readCallbacks)
            if self.quitFlag:
                break
            self.scheduler.processTimeouts()
            if self.quitFlag:
                break
            self.idleQueue.processIdles()
            if self.quitFlag:
                break

_eventLoop = EventLoop()

def addReadCallback(socket, callback):
    _eventLoop.addReadCallback(socket, callback)

def removeReadCallback(socket):
    _eventLoop.removeReadCallback(socket)

def addWriteCallback(socket, callback):
    _eventLoop.addWriteCallback(socket, callback)

def removeWriteCallback(socket):
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

def addTimeout(delay, function, args=None, kwargs=None):
    """Schedule a function to be called at some point in the future.
    Returns a DelayedCall object that can be used to cancel the call.
    """

    dc = _eventLoop.scheduler.addTimeout(delay, function, args, kwargs)
    _eventLoop.wakeup()
    return dc

def addIdle(function, args=None, kwargs=None):
    """Schedule a function to be called when we get some spare time.
    Returns a DelayedCall object that can be used to cancel the call.
    """

    _eventLoop.idleQueue.addIdle(function, args, kwargs)
    _eventLoop.wakeup()

def startup():
    lt = threading.Thread(target=_eventLoop.loop, name="Event Loop")
    lt.setDaemon(False)
    lt.start()

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
        addIdle(func, args=args, kwargs=kwargs)
    return queuer
