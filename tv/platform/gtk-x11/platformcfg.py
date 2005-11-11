import os

import config

def load():
    pass

def save(data):
    pass

def get(descriptor):
    value = None

    if descriptor == config.MOVIES_DIRECTORY:
        path = os.path.expanduser('~/Movies/DTV')
        try:
            os.makedirs(os.path.join(path,'Incomplete Downloads'))
        except:
            pass
        value = path

    elif descriptor == config.SUPPORT_DIRECTORY:
        path = os.path.expanduser('~/.dtv')
        os.environ['APPDATA'] = path # This is for the Bittorent module
        try:
            os.makedirs(path)
        except:
            pass
        value = path
    
    elif descriptor == config.DB_PATHNAME:
        path = get(config.SUPPORT_DIRECTORY)
        path = os.path.join(path, 'tvdump')
        value = path
    
    return value
