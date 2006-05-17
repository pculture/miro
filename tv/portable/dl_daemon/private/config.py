from threading import Event
import prefs

_data = {}

_ready = Event()

def setDictionary(d):
    global _data
    #print "set initial remote config %s" % repr(d)
    _data = d
    _ready.set()

def get(descriptor):
    _ready.wait()
    return _data[descriptor.key]
