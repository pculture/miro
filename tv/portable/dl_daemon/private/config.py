from threading import Event
import prefs

_data = {}

_ready = Event()

__callbacks = set()

def addChangeCallback(callback):
    __callbacks.add(callback)

def removeChangeCallback(callback):
    __callbacks.discard(callback)

def setDictionary(d):
    global _data
    #print "set initial remote config %s" % repr(d)
    _data = d
    prefs.APP_SERIAL.key = 'appSerial-%s' % d[prefs.APP_PLATFORM.key]
    _ready.set()

def updateDictionary (key, value):
    _data[key] = value
    for callback in __callbacks:
        callback(key, value)

def get(descriptor):
    _ready.wait()
    return _data[descriptor.key]
