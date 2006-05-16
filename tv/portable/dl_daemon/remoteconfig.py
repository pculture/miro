from threading import Event

def getConfigItems():
    import config
    return [config.LIMIT_UPSTREAM,
               config.UPSTREAM_LIMIT_IN_KBS,
               config.BT_MIN_PORT,
               config.BT_MAX_PORT,
               config.MOVIES_DIRECTORY,
               config.PRESERVE_DISK_SPACE,
               config.PRESERVE_X_GB_FREE,
               config.SUPPORT_DIRECTORY,
               config.SHORT_APP_NAME,
               config.LONG_APP_NAME,
               config.APP_PLATFORM,
               config.APP_VERSION,
               config.APP_SERIAL,
               config.APP_REVISION,
               config.PUBLISHER,
               config.PROJECT_URL,
               config.LOG_PATHNAME,
            ]
                    
                    
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
