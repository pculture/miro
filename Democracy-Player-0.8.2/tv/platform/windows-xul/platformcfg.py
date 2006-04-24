import os
import util
import config
import _winreg
import cPickle
import string
import tempfile
import ctypes

_appDataDirectory = None
_baseMoviesDirectory = None

def _getRegString(key, subkey):
    def doExpand(val):
        out = ctypes.create_string_buffer(4096)
        indata = ctypes.create_string_buffer(val)
        bytes = ctypes.windll.kernel32.ExpandEnvironmentStringsA(indata,out,4093)
        return out.value

    (val, t) = _winreg.QueryValueEx(key, subkey)
    if t == _winreg.REG_SZ:
        return val
    elif t == _winreg.REG_EXPAND_SZ:
        return doExpand(val)
    else:
        raise TypeError, "Got bad type %s for registry subkey %s" % (t, subkey)

def _findDirectories():
    global _appDataDirectory
    global _baseMoviesDirectory

    keyName = r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
    key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, keyName)

    try:
        _appDataDirectory = _getRegString(key, 'AppData')
    except:
        # Older versions of Windows didn't have per user Application Data
        keyName2 = r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
        key2 = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, keyName2)
        _appDataDirectory = _getRegString(key2, 'AppData')
    try:
        _baseMoviesDirectory = _getRegString(key, 'My Video')
    except:
        _baseMoviesDirectory = None
    if type(_baseMoviesDirectory) is not str or len(_baseMoviesDirectory) < 1:
        # Apparently some machines have the key present, but blank
        documentsDirectory = _getRegString(key, 'Personal')
        # 'Help' the user
        _baseMoviesDirectory = os.path.join(documentsDirectory, 'My Videos')

_findDirectories()

def _getMoviesDirectory():
    path = os.path.join(_baseMoviesDirectory, config.get(config.SHORT_APP_NAME))
    try:
        os.makedirs(os.path.join(path, 'Incomplete Downloads'))
    except:
        pass
    return path

def _getSupportDirectory():
    path = os.path.join(_appDataDirectory,
                        config.get(config.PUBLISHER),
                        config.get(config.LONG_APP_NAME),
                        'Support')
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

    elif descriptor == config.LOG_PATHNAME:
        return os.path.join(tempfile.gettempdir(), 'dtv-log')

    elif descriptor == config.DOWNLOADER_LOG_PATHNAME:
        return os.path.join(tempfile.gettempdir(), 'dtv-downloader-log')

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
