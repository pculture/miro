from Foundation import NSFileManager, NSAutoreleasePool, NSFileSystemFreeSize
import config

###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################

def getAvailableGBytesForMovies():
    pool = NSAutoreleasePool.alloc().init()
    fm = NSFileManager.defaultManager()
    info = fm.fileSystemAttributesAtPath_(config.get(config.MOVIES_DIRECTORY))
    bytesFree = info[NSFileSystemFreeSize]
    del pool
    return bytesFree / (1024 * 1024 * 1024)
