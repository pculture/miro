###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################

import ctypes
import config
import prefs

def samefile(path1, path2):
    buf1 = ctypes.create_string_buffer(260) 
    buf2 = ctypes.create_string_buffer(260) 
    GetLongPathName = ctypes.windll.kernel32.GetLongPathNameA
    rv1 = GetLongPathName(str(path1), buf1, 260)
    rv2 = GetLongPathName(str(path2), buf2, 260)
    if rv1 == 0 or rv1 > 260 or rv2 == 0 or rv2 > 260:
        return False
    else:
        return buf1.value == buf2.value

def getAvailableBytesForMovies():
    # TODO: windows implementation
    moviesDir = config.get(prefs.MOVIES_DIRECTORY)
    print "GETTING disk space for ", moviesDir
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
