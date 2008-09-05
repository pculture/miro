from threading import Event, Lock
from miro import prefs
import miro.plat.config

_data = {}
_dataLock = Lock()

_ready = Event()

__callbacks = set()

def add_change_callback(callback):
    __callbacks.add(callback)

def remove_change_callback(callback):
    __callbacks.discard(callback)

def setDictionary(d):
    global _data
    #print "set initial remote config %s" % repr(d)
    _dataLock.acquire()
    try:
        _data = d
    finally:
        _dataLock.release()
    prefs.APP_SERIAL.key = 'appSerial-%s' % d[prefs.APP_PLATFORM.key]
    _ready.set()

def updateDictionary (key, value):
    _dataLock.acquire()
    try:
        _data[key] = value
    finally:
        _dataLock.release()
    for callback in __callbacks:
        callback(key, value)

def get(descriptor):
    _ready.wait()
    _dataLock.acquire()
    try:
        if descriptor.key in _data:
            return _data[descriptor.key]
        elif descriptor.platformSpecific:
            return miro.plat.config.get(descriptor)
        else:
            return descriptor.default
    finally:
        _dataLock.release()
