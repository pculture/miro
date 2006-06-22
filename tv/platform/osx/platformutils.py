import threading
import Foundation

import config
import prefs

###############################################################################
#### THREADING UTILITIES                                                   ####
###############################################################################

def warnIfNotOnMainThread(name="(unknown)"):
    """Displays a warning message if a function is not called on the main GUI 
    thread.
    """
    if threading.currentThread().getName() != 'MainThread':
        print "WARNING: function %s not on main thread" % name

def isOnMainThread():
    return (threading.currentThread().getName() == 'MainThread')

###############################################################################

def callOnMainThread(func, *args, **kwargs):
    """Schedules func to be called on the main thread and returns immediately.
    """
    _call((func, args, kwargs), waitUntilDone=False)

def callOnMainThreadAndWaitUntilDone(func, *args, **kwargs):
    """Schedules func to be called on the main thread and wait until the calls 
    has been effectively performed.
    """
    _call((func, args, kwargs), waitUntilDone=True)

def callOnMainThreadAfterDelay(delay, func, *args, **kwargs):
    """Schedules func to be called on the main thread after the specified delay 
    (in seconds)
    """
    _call((func, args, kwargs), delay=delay)

def callOnMainThreadAndWaitReturnValue(func, *args, **kwargs):
    """Schedules func to be called on the main thread and wait for its result.
    """
    return _call((func, args, kwargs), waitForResult=True)

###############################################################################

def onMainThread(method):
    """Decorator which specifies that a method should always be called on the 
    main GUI thread.
    """
    def scheduled(self, *args, **kwargs):
        callOnMainThread(method, self, *args, **kwargs)
    return scheduled

def onMainThreadWaitingUntilDone(method):
    """Decorator which specifies that a method should always be called on the 
    main GUI thread and that the called must wait for it to be done.
    """
    def scheduled(self, *args, **kwargs):
        callOnMainThreadAndWaitUntilDone(method, self, *args, **kwargs)
    return scheduled

def onMainThreadWithReturn(method):
    """Decorator which specifies that a method should always be called on the 
    main GUI thread and that the called must wait for its result.
    """
    def scheduled(self, *args, **kwargs):
        return callOnMainThreadAndWaitReturnValue(method, self, *args, **kwargs)
    return scheduled

###############################################################################
#### THREADING UTILITIES SUPPORT                                           ####
###############################################################################

callLock = threading.Lock()
callEvent = threading.Event()
callResult = None

def _call(args, delay=0.0, waitUntilDone=False, waitForResult=False):
    if isOnMainThread():
        (func, fargs, fkwargs) = args
        return func(*fargs, **fkwargs)
    else:
        obj = CallerObject.alloc().initWithArgs_(args)
        try:
            if waitForResult:
                return obj.performCallAndWaitReturn()
            elif delay == 0.0:
                obj.performCall(waitUntilDone)
            else:
                obj.performCallLater(delay)
        finally:
            del obj

class CallerObject (Foundation.NSObject):
    
    def initWithArgs_(self, args):
        self = self.init()
        self.args = args
        return self
        
    def performCall(self, waitUntilDone):
        self.performSelectorOnMainThread_withObject_waitUntilDone_(self.perform_, self.args, waitUntilDone)

    def performCallLater(self, delay):
        self.performSelector_withObject_afterDelay_(self.performCall, None, delay)
        
    def performCallAndWaitReturn(self):
        global callLock
        global callEvent
        global callResult
        
        callLock.acquire()
        r = None
        try:
            callEvent.clear()
            self.performSelectorOnMainThread_withObject_waitUntilDone_(self.performAndNotify_, self.args, False)
            callEvent.wait()
            r = callResult
        finally:
            callResult = None
            callLock.release()
        return r
        
    def perform_(self, (func, args, kwargs)):
        return func(*args, **kwargs)

    def performAndNotify_(self, (func, args, kwargs)):
        global callResult
        callResult = func(*args, **kwargs)
        callEvent.set()

###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################

def getAvailableBytesForMovies():
    pool = Foundation.NSAutoreleasePool.alloc().init()
    fm = Foundation.NSFileManager.defaultManager()
    info = fm.fileSystemAttributesAtPath_(config.get(prefs.MOVIES_DIRECTORY))
    available = info[Foundation.NSFileSystemFreeSize]
    del pool
    return available
