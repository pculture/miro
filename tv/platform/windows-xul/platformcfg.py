import os

import config

def load():
    print "WARNING: preference loading not implemented" # NEEDS
    return {}

def save(data):
    print "WARNING: preference saving not implemented" # NEEDS

# NEEDS: the correct way to do this is to call SHGetFolderPath and
# ship the appropriate dll, not to hardcode paths. But that isn't
# working for me right now, so cheat.

def get(descriptor):
    value = None

    if descriptor == config.MOVIES_DIRECTORY:
        path = os.path.expandvars('C:\\Documents and Settings\\${USERNAME}\\My Documents\\My Videos\\DTV')
        try:
            os.makedirs(os.path.join(path,'Incomplete Downloads'))
        except:
            pass
        value = path

    elif descriptor == config.SUPPORT_DIRECTORY:
        path = os.path.expandvars('C:\\Documents and Settings\\${USERNAME}\\Application Data\\DTV')
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