"""Event loop handler.

This module handles the democracy event loop which is responsible for network
requests and scheduling.

TODO:
    handle user setting clock back
"""

import traceback
import threading
import socket
import select
import heapq

from BitTornado.clock import clock

import util

READ_WATCH = 1 << 0
WRITE_WATCH = 1 << 1

_quitFlag = False
_wakerSocket, _wakeeSocket = util.makeDummySocketPair()

def wakeup():
    _wakerSocket.send("B")

def watchSocket(socket, type, callback, errback):
    """Create a watch on a socket.  type must be a bitwise combination of
    READ_WATCH and WRITE_WATCH.  When the socket becomes available for
    readinrg/writing, callback will be called.  If we detect and error on the
    socket, errback will be called.

    It's okay to call watchSocket with a socket that already has a watch on
    it.  This can be used to change the type of watch.
    """
    pass

def removeWatch(socket):
    """Remove a watch on a socket."""
    pass

class DelayedCall(object):
    def __init__(self, function, args, kwargs):
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.canceled = False

    def cancel(self):
        self.canceled = True

    def dispatch(self):
        if self.canceled:
            return
        try:
            self.function(*self.args, **self.kwargs)
        except:
            print "Exception in DelayedCall:"
            traceback.print_exc()

class Scheduler(object):
    def __init__(self):
        self.heap = []
        self.lock = threading.Lock()

    def addTimeout(self, delay, function, args=(), kwargs={}):
        scheduledTime = clock() + delay
        dc = DelayedCall(function, args, kwargs)
        self.lock.acquire()
        try:
            heapq.heappush(self.heap, (scheduledTime, dc))
        finally:
            self.lock.release()
        return dc

    def nextTimeout(self):
        self.lock.acquire()
        try:
            if len(self.heap) == 0:
                return None
            else:
                return max(0, self.heap[0][0] - clock())
        finally:
            self.lock.release()

    def processTimeouts(self):
        while True:
            self.lock.acquire()
            try:
                if len(self.heap) > 0 and self.heap[0][0] < clock():
                    time, dc = heapq.heappop(self.heap)
                else:
                    break
            finally:
                self.lock.release()
            dc.dispatch()

_scheduler = Scheduler()

def addTimeout(delay, function, args=(), kwargs={}):
    """Schedule a function to be called at some point in the future.
    Returns a DelayedCall object that can be used to cancel the timeout.
    """

    dc = _scheduler.addTimeout(delay, function, args, kwargs)
    wakeup()
    return dc

def addIdle(function, *args, **kwargs):
    """Schedule a function to be called when we get some spare time.
    Returns a DelayedCall object that can be used to cancel the timeout.
    """
    return addTimeout(0, function, *args, **kwargs)

def quit():
    global _quitFlag
    _quitFlag = True
    wakeup()

def loop():
    while not _quitFlag:
        timeout = _scheduler.nextTimeout()
        (inputReady, outputReady, exceptions) = select.select([_wakeeSocket], 
                [], [], timeout)
        if _wakeeSocket in inputReady:
            _wakeeSocket.recv(1024)
        _scheduler.processTimeouts()
