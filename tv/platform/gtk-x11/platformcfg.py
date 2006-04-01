import os

import config

def load():
    print "WARNING: loading config information is not supported on gtk"

def save(data):
    print "WARNING: saving config information is not supported on gtk"

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
