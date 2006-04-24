import os

import config
import gconf

client = gconf.client_get_default()

class gconfDict:
    def get(self, key, default = None):
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
    def __setitem__(self, key, value):
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

def load():
    return gconfDict()

def save(data):
    pass

def get(descriptor):
    path = None

    if descriptor.key == config.MOVIES_DIRECTORY.key:
        path = os.path.expanduser('~/Movies/Democracy')

    elif descriptor.key == config.SUPPORT_DIRECTORY.key:
        path = os.path.expanduser('~/.democracy')
    
    elif descriptor.key == config.DB_PATHNAME.key:
        path = get(config.SUPPORT_DIRECTORY)
        path = os.path.join(path, 'tvdump')

    elif descriptor.key == config.DB_PATHNAME.key:
        path = get(config.SUPPORT_DIRECTORY)
        path = os.path.join(path, 'log')
    
    return path
