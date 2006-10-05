###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################

import ctypes
import config
import prefs

localeInitialized = False

def samefile(path1, path2):
    return getLongPathName(path1) == getLongPathName(path2)

def getLongPathName(path):
    buf = ctypes.create_unicode_buffer(260) 
    GetLongPathName = ctypes.windll.kernel32.GetLongPathNameW
    rv = GetLongPathName(path, buf, 260)
    if rv == 0 or rv > 260:
        return path
    else:
        return buf.value

def getAvailableBytesForMovies():
    # TODO: windows implementation
    moviesDir = config.get(prefs.MOVIES_DIRECTORY)
    freeSpace = ctypes.c_ulonglong(0)
    availableSpace = ctypes.c_ulonglong(0)
    totalSpace = ctypes.c_ulonglong(0)
    rv = ctypes.windll.kernel32.GetDiskFreeSpaceExW(unicode(moviesDir),
            ctypes.byref(availableSpace), ctypes.byref(totalSpace),
            ctypes.byref(freeSpace)) 
    if rv == 0:
        print "GetDiskFreeSpaceExW failed, returning bogus value!"
        return 100 * 1024 * 1024 * 1024
    return availableSpace.value

def initializeLocale():
    global localeInitialized

    localeInitialized = True
