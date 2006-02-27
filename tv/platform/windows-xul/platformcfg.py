import os
import util
import config
import _winreg
import cPickle

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
    return os.path.join(_getSupportDirectory(), "preferences.bin")

def load():
    try:
        file = _getConfigFile()
        return cPickle.load(open(file))
    except:
        print "Error loading perferences. Resetting prefs."
        return {}

def save(data):
    file = _getConfigFile()
    cPickle.dump(data,open(file,'w'))

def get(descriptor):
    if descriptor == config.MOVIES_DIRECTORY:
        return _getMoviesDirectory()

    elif descriptor == config.SUPPORT_DIRECTORY:
        return _getSupportDirectory()
    
    elif descriptor == config.DB_PATHNAME:
        path = get(config.SUPPORT_DIRECTORY)
        return os.path.join(path, 'tvdump')
    elif descriptor == config.RUN_AT_STARTUP:
        # We use the legacy startup registry key, so legacy versions
        # of Windows have a chance
        # http://support.microsoft.com/?kbid=270035

        folder = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,"Software\Microsoft\Windows\CurrentVersion\Run")
        count = 0
        while True:
            try:
                (name, val, type) = _winreg.EnumValue(folder,count)
                count += 1
                if (name == "Democracy Player"):
                    return True                    
            except:
                return False
        return False
    return None
