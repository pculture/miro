import os
import util
import config

# NEEDS: the correct way to do these is to call SHGetFolderPath and
# ship the appropriate dll, not to hardcode paths. But that isn't
# working for me right now, so cheat.

def _getMoviesDirectory():
    path = os.path.expandvars('C:\\Documents and Settings\\${USERNAME}\\My Documents\\My Videos\\%s' % config.get(config.SHORT_APP_NAME))
    try:
        os.makedirs(os.path.join(path, 'Incomplete Downloads'))
    except:
        pass
    return path

def _getSupportDirectory():
    path = 'C:\\Documents and Settings\\${USERNAME}\\Application Data\\%s\\%s\\Support' % \
        (config.get(config.PUBLISHER),
         config.get(config.LONG_APP_NAME))
    path = os.path.expandvars(path)

    try:
        os.makedirs(path)
    except:
        pass
    return path

def _getConfigFile():
    return os.path.join(_getSupportDirectory(), "preferences")

def load():
    file = _getConfigFile()
    if os.access(file, os.F_OK):
        return util.readSimpleConfigFile(_getConfigFile())
    else:
        # First time running program
        return {}

def save(data):
    util.writeSimpleConfigFile(_getConfigFile(), data)

def get(descriptor):
    if descriptor == config.MOVIES_DIRECTORY:
        return _getMoviesDirectory()

    elif descriptor == config.SUPPORT_DIRECTORY:
        return _getSupportDirectory()
    
    elif descriptor == config.DB_PATHNAME:
        path = get(config.SUPPORT_DIRECTORY)
        return os.path.join(path, 'tvdump')
    
    return None
