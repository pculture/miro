import os

import config

def load():
    print "WARNING: loading config information is not supported on gtk"

def save(data):
    print "WARNING: saving config information is not supported on gtk"

def get(descriptor):
    value = None

    if descriptor.key == config.MOVIES_DIRECTORY.key:
        path = os.path.expanduser('~/Movies/DTV')
        try:
            os.makedirs(os.path.join(path,'Incomplete Downloads'))
        except:
            pass
        value = path

    elif descriptor.key == config.SUPPORT_DIRECTORY.key:
        path = os.path.expanduser('~/.dtv')
        os.environ['APPDATA'] = path # This is for the Bittorent module
        try:
            os.makedirs(path)
        except:
            pass
        value = path
    
    elif descriptor.key == config.DB_PATHNAME.key:
        path = get(config.SUPPORT_DIRECTORY)
        path = os.path.join(path, 'tvdump')
        value = path

    elif descriptor.key == config.DB_PATHNAME.key:
        path = get(config.SUPPORT_DIRECTORY)
        path = os.path.join(path, 'log')
        value = path
    
    return value
