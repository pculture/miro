import os
import prefs
import gconf
import threading

client = gconf.client_get_default()
gconf_lock = threading.RLock()

class gconfDict:
    def get(self, key, default = None):
        gconf_lock.acquire()
        try:
            if (type(key) != str):
                raise TypeError()
            fullkey = '/apps/democracy/player/' + key
            value = client.get (fullkey)
            if (value != None):
                if (value.type == gconf.VALUE_STRING):
                    return value.get_string()
                if (value.type == gconf.VALUE_INT):
                    return value.get_int()
                if (value.type == gconf.VALUE_BOOL):
                    return value.get_bool()
                if (value.type == gconf.VALUE_FLOAT):
                    return value.get_float()
            return default
        finally:
            gconf_lock.release()

    def __contains__(self, key):
        gconf_lock.acquire()
        try:
            fullkey = '/apps/democracy/player/' + key
            return client.get(fullkey) is not None
        finally:
            gconf_lock.release()

    def __getitem__(self, key):
        rv = self.get(key)
        if rv is None:
            raise KeyError
        else:
            return rv

    def __setitem__(self, key, value):
        gconf_lock.acquire()
        try:
            if (type(key) != str):
                raise TypeError()
            fullkey = '/apps/democracy/player/' + key
            if (type(value) == str):
                client.set_string(fullkey, value)
            elif (type(value) == int):
                client.set_int(fullkey, value)
            elif (type(value) == bool):
                client.set_bool(fullkey, value)
            elif (type(value) == float):
                client.set_float(fullkey, value)
            else:
                raise TypeError()
        finally:
            gconf_lock.release()

def load():
    return gconfDict()

def save(data):
    pass

def get(descriptor):
    path = None

    if descriptor == prefs.MOVIES_DIRECTORY:
        path = os.path.expanduser('~/Movies/Democracy')

    elif descriptor == prefs.SUPPORT_DIRECTORY:
        path = os.path.expanduser('~/.democracy')

    elif descriptor == prefs.ICON_CACHE_DIRECTORY:
        path = os.path.expanduser('~/.democracy/icon-cache')
    
    elif descriptor == prefs.DB_PATHNAME:
        path = get(prefs.SUPPORT_DIRECTORY)
        path = os.path.join(path, 'tvdump')

    elif descriptor == prefs.BSDDB_PATHNAME:
        path = get(prefs.SUPPORT_DIRECTORY)
        path = os.path.join(path, 'database')

    elif descriptor == prefs.LOG_PATHNAME:
        path = get(prefs.SUPPORT_DIRECTORY)
        path = os.path.join(path, 'log')
    
    elif descriptor == prefs.DOWNLOADER_LOG_PATHNAME:
        path = get(prefs.SUPPORT_DIRECTORY)
        return os.path.join(path, 'dtv-downloader-log')

    return path
