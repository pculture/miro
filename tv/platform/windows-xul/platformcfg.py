import os
import util
import config
import _winreg
import cPickle
import string
import prefs
import tempfile
import ctypes

_specialFolderCSIDLs = {
    'AppData': 0x001a,
    "My Music": 0x000d,
    "My Pictures": 0x0027,
    "My Videos": 0x000e,
    "My Documents": 0x0005,
    "Desktop": 0x0000,
}

def getSpecialFolder(name):
    """Get the location of a special folder.  name should be one of the
    following: 'AppData', 'My Music', 'My Pictures', 'My Videos', 
    'My Documents', 'Desktop'.

    The path to the folder will be returned, or None if the lookup fails

    """

    buf = ctypes.create_unicode_buffer(260) 
    SHGetSpecialFolderPath = ctypes.windll.shell32.SHGetSpecialFolderPathW
    csidl = _specialFolderCSIDLs[name]
    if SHGetSpecialFolderPath(None, buf, csidl, False):
        return buf.value
    else:
        return None

_appDataDirectory = getSpecialFolder('AppData')
_baseMoviesDirectory = getSpecialFolder('My Videos')
_nonVideoDirectory = getSpecialFolder('Desktop')

def _getMoviesDirectory():
    path = os.path.join(_baseMoviesDirectory, config.get(prefs.SHORT_APP_NAME))
    try:
        os.makedirs(os.path.join(path, 'Incomplete Downloads'))
    except:
        pass
    return path

def _getSupportDirectory():
    path = os.path.join(_appDataDirectory,
                        config.get(prefs.PUBLISHER),
                        config.get(prefs.LONG_APP_NAME),
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
        if os.path.exists(file):
            return cPickle.load(open(file))
        else:
            return {}
    except:
        import traceback
        print "Error loading perferences. Resetting prefs."
        traceback.print_exc()
        return {}

def save(data):
    file = _getConfigFile()
    cPickle.dump(data,open(file,'w'))

def get(descriptor):
    if descriptor == prefs.MOVIES_DIRECTORY:
        return _getMoviesDirectory()

    elif descriptor == prefs.NON_VIDEO_DIRECTORY:
        return _nonVideoDirectory

    elif descriptor == prefs.SUPPORT_DIRECTORY:
        return _getSupportDirectory()

    elif descriptor == prefs.ICON_CACHE_DIRECTORY:
        return os.path.join(_getSupportDirectory(), 'icon-cache')
    
    elif descriptor == prefs.DB_PATHNAME:
        path = get(prefs.SUPPORT_DIRECTORY)
        return os.path.join(path, 'tvdump')

    elif descriptor == prefs.BSDDB_PATHNAME:
        path = get(prefs.SUPPORT_DIRECTORY)
        return os.path.join(path, 'database')

    elif descriptor == prefs.LOG_PATHNAME:
        return os.path.join(tempfile.gettempdir(), 'dtv-log')

    elif descriptor == prefs.DOWNLOADER_LOG_PATHNAME:
        return os.path.join(tempfile.gettempdir(), 'dtv-downloader-log')

    elif descriptor == prefs.RUN_AT_STARTUP:
        # We use the legacy startup registry key, so legacy versions
        # of Windows have a chance
        # http://support.microsoft.com/?kbid=270035

        folder = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER,"Software\Microsoft\Windows\CurrentVersion\Run")
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
