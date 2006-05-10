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
_scheduleHeap = []
_scheduleHeapLock = threading.Lock()
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

def addTimeout(delay, function, *args, **kwargs):
    """Schedule a function to be called at some point in the future.
    Returns a DelayedCall object that can be used to cancel the timeout.
    """

    scheduledTime = clock() + delay
    dc = DelayedCall(function, args, kwargs)
    _scheduleHeapLock.acquire()
    try:
        heapq.heappush(_scheduleHeap, (scheduledTime, dc))
    finally:
        _scheduleHeapLock.release()
    wakeup()
    return dc

def addIdle(function, *args, **kwargs):
    """Schedule a function to be called when we get some spare time.
    Returns a DelayedCall object that can be used to cancel the timeout.
    """
    return addTimeout(0, function, *args, **kwargs)

def processTimeouts():
    now = clock()
    _scheduleHeapLock.acquire()
    try:
        while len(_scheduleHeap) > 0 and _scheduleHeap[0][0] < now:
            time, dc = heapq.heappop(_scheduleHeap)
            _scheduleHeapLock.release()
            try:
                dc.dispatch()
            finally:
                _scheduleHeapLock.acquire()
    finally:
        _scheduleHeapLock.release()

def quit():
    global _quitFlag
    _quitFlag = True
    wakeup()

def nextTimeout():
    _scheduleHeapLock.acquire()
    try:
        if len(_scheduleHeap) == 0:
            return None
        else:
            return max(0, _scheduleHeap[0][0] - clock())
    finally:
        _scheduleHeapLock.release()

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
            print "calling %s" % self.__dict__
            self.function(*self.args, **self.kwargs)
        except:
            print "Exception in DelayedCall:"
            traceback.print_exc()

def loop():
    while not _quitFlag:
        timeout = nextTimeout()
        print "timout is ", timeout
        (inputReady, outputReady, exceptions) = select.select([_wakeeSocket], 
                [], [], timeout)
        if _wakeeSocket in inputReady:
            _wakeeSocket.recv(1024)
        processTimeouts()

if __name__ == '__main__':
    def foo():
        print "FOO"
    def bar(*args, **kwargs):
        print "BAR! %s %s" % (args, kwargs)

    def quitter():
        import time
        time.sleep(10)
        addIdle(bar, "thread")
        time.sleep(0.2)
        print "QUIT!"
        quit()

    addIdle(foo)
    addTimeout(5, bar, "chris", {"hula":"Hula"})
    addTimeout(1, bar, "ben", {"bula":"Hula"})
    fooDc = addTimeout(6, foo)
    def cancelFoo():
        print "cancling FOO"
        fooDc.cancel()
    addTimeout(5, cancelFoo)
    t = threading.Thread(target=quitter)
    t.start()
    loop()
