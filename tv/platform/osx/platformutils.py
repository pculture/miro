import threading
import os
import urllib
import statvfs
import logging
import sys

from objc import NO
import Foundation

from util import returnsUnicode, returnsBinary, checkU, checkB

FilenameType = str

# We need to define samefile for the portable code.  Lucky for us, this is
# very easy.
from os.path import samefile

localeInitialized = False

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
    if isOnMainThread() and delay == 0.0:
        (func, fargs, fkwargs) = args
        return func(*fargs, **fkwargs)
    else:
        obj = CallerObject.alloc().initWithArgs_(args)
        try:
            if waitForResult:
                return obj.performCallAndWaitReturn()
            elif delay == 0.0:
                obj.performCall_(waitUntilDone)
            else:
                obj.performCallLater_(delay)
        finally:
            del obj

class CallerObject (Foundation.NSObject):
    
    def initWithArgs_(self, args):
        self = self.init()
        self.args = args
        return self
        
    def performCall_(self, waitUntilDone):
        self.performSelectorOnMainThread_withObject_waitUntilDone_(self.perform_, self.args, waitUntilDone)

    def performCallLater_(self, delay):
        dontWait = Foundation.NSNumber.numberWithBool_(NO)
        self.performSelector_withObject_afterDelay_(self.performCall_, dontWait, delay)
        
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
    import config
    import prefs

    pool = Foundation.NSAutoreleasePool.alloc().init()
    fm = Foundation.NSFileManager.defaultManager()
    info = fm.fileSystemAttributesAtPath_(config.get(prefs.MOVIES_DIRECTORY))
    try:
        available = info[Foundation.NSFileSystemFreeSize]
    except:
        # We could not retrieve the available disk size for some reason, default
        # to something huge to allow downloads.
        available = 1024 * 1024 * 1024 * 1024
    del pool
    return available

def initializeLocale():
    global localeInitialized

    pool = Foundation.NSAutoreleasePool.alloc().init()
    languages = list(Foundation.NSUserDefaults.standardUserDefaults()["AppleLanguages"])
    try:
        pos = languages.index('en')
        languages = languages[:pos]
    except:
        pass

    print languages
    os.environ["LANGUAGE"] = ':'.join(languages)
    
    localeInitialized = True
    del pool

def setupLogging (inDownloader=False):
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        stream = sys.stdout)

# Takes in a unicode string representation of a filename and creates a
# valid byte representation of it attempting to preserve extensions
#
# This is not guaranteed to give the same results every time it is run,
# not is it garanteed to reverse the results of filenameToUnicode
@returnsBinary
def unicodeToFilename(filename, path = None):
    checkU(filename)
    if path:
        checkB(path)
    else:
        path = os.getcwd()

    # Keep this a little shorter than the max length, so we can run
    # nextFilename
    MAX_LEN = os.statvfs(path)[statvfs.F_NAMEMAX]-5
    
    filename.replace('/','_').replace("\000","_").replace("\\","_").replace(":","_").replace("*","_").replace("?","_").replace("\"","_").replace("<","_").replace(">","_").replace("|","_")

    newFilename = filename.encode('utf-8','replace')
    while len(newFilename) > MAX_LEN:
        filename = shortenFilename(filename)
        newFilename = filename.encode('utf-8','replace')

    return newFilename

@returnsUnicode
def shortenFilename(filename):
    checkU(filename)
    # Find the first part and the last part
    pieces = filename.split(u".")
    lastpart = pieces[-1]
    if len(pieces) > 1:
        firstpart = u".".join(pieces[:-1])
    else:
        firstpart = u""
    # If there's a first part, use that, otherwise shorten what we have
    if len(firstpart) > 0:
        return u"%s.%s" % (firstpart[:-1],lastpart)
    else:
        return filename[:-1]

# Given a filename in raw bytes, return the unicode representation
#
# Since this is not guaranteed to give the same results every time it is run,
# not is it garanteed to reverse the results of unicodeToFilename
@returnsUnicode
def filenameToUnicode(filename, path = None):
    if path:
        checkB(path)
    checkB(filename)
    return filename.decode('utf-8','replace')

# Takes in a byte string or a unicode string and does the right thing
# to make a URL
@returnsUnicode
def makeURLSafe(string, safe='/'):
    if type(string) == str:
        # quote the byte string
        return urllib.quote(string, safe=safe).decode('ascii')
    else:
        return urllib.quote(string.encode('utf-8','replace'), safe=safe).decode('ascii')

# Undoes makeURLSafe (assuming it was passed a filenameType)
@returnsBinary
def unmakeURLSafe(string):
    # unquote the byte string
    checkU (string)
    return urllib.unquote(string.encode('ascii'))

# Takes filename given by the PyObjC bridge and turn it into a FilenameType
@returnsBinary
def osFilenameToFilenameType(filename):
    return FilenameType(unicode(filename).encode('utf-8','replace'))

# Takes an array of filenames given by the OS and turn them into a FilenameTypes
def osFilenamesToFilenameTypes(filenames):
    return [osFilenameToFilenameType(filename) for filename in filenames]

# Takes a FilenameType and turn it into something the PyObjC bridge accepts.
def filenameTypeToOSFilename(filename):
    return filename.decode('utf-8')
