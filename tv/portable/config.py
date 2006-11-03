from threading import RLock
import os
import traceback

import util
import prefs
import resources
import eventloop
import platformcfg
import urllib

__appConfig = None
__data = None
__lock = RLock()
__callbacks = set()

def addChangeCallback(callback):
    __callbacks.add(callback)

def removeChangeCallback(callback):
    __callbacks.discard(callback)

def load():
    global __appConfig
    global __data
    if __appConfig is None and __data is None:
        __lock.acquire()
        try:
            # There's some sleight-of-hand here. The Windows port needs to
            # look up config.LONG_APP_NAME and config.PUBLISHER to compute
            # the path to the data file that is read when load() is
            # called. Setting __appConfig to a true value (and populating
            # it with those keys) before calling load() ensures that (a)
            # the values will be available and (b) we won't get caught in
            # an infinite loop of load()s. But in general, you shouldn't
            # call config.get() or config.set() from platformcfg.load()
            # unless you know exactly what you are doing, and maybe not
            # even then.
            __appConfig = util.readSimpleConfigFile(resources.path('app.config'))

            # Load the preferences
            __data = platformcfg.load()
            if __data is None:
                __data = dict()

            # This is a bit of a hack to automagically get the serial
            # number for this platform
            prefs.APP_SERIAL.key = ('appSerial-%s' % get(prefs.APP_PLATFORM))

        finally:
            __lock.release()

def save():
    __lock.acquire()
    try:
        __checkValidity()
        platformcfg.save( __data )
    finally:
        __lock.release()

def get(descriptor):
    if 'ISAFAKE' in descriptor.__dict__:
        print ("WARNING: config.get called with config descriptor: %s" %
            descriptor.key)
        print "%s:%s" % traceback.extract_stack()[-2][:2]

    __lock.acquire()
    try:
        __checkValidity()

        if __data is not None and descriptor.key in __data:
            return __data[descriptor.key]
        elif descriptor.platformSpecific:
            return platformcfg.get(descriptor)
        elif descriptor.key in __appConfig:
            return __appConfig[descriptor.key]
        else:
            return descriptor.default
    finally:
        __lock.release()

def getList(descriptor):
    return [urllib.unquote(i) for i in get(descriptor).split(",") if i]

def getAppConfig():
    __lock.acquire()
    try:
        __checkValidity()
        return __appConfig.copy()
    finally:
        __lock.release()
    
def set(descriptor, value):
    if 'ISAFAKE' in descriptor.__dict__:
        print ("WARNING: config.set called with config descriptor: %s" %
            descriptor.key)
    __lock.acquire()
    print "Setting %s to %s" % (descriptor.key, value)
    try:
        __checkValidity()
        if descriptor.key not in __data or __data[ descriptor.key ] != value:
            __data[ descriptor.key ] = value
            __notifyListeners(descriptor.key, value)
    finally:
        __lock.release()

def setList(descriptor, value):
    set(descriptor, [quote(i) for i in value].join (','))

def __checkValidity():
    if __appConfig == None:
        load()

def __notifyListeners(key, value):
    for callback in __callbacks:
        eventloop.addIdle(callback, 'config callback: %s' % callback,
                args=(key,value))

def ensureMigratedMoviePath(pathname):
    if hasattr(platformcfg, 'ensureMigratedMoviePath'):
        pathname = platformcfg.ensureMigratedMoviePath(pathname)
    return pathname

# We should remove this hack once we change all config.get to use prefs
import copy
for name, object in prefs.__dict__.items():
    if isinstance(object, prefs.Pref):
        fakePref = copy.copy(object)
        fakePref.ISAFAKE = True
        globals()[name] = fakePref
