###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################
import os
import config
import prefs

def getAvailableGBytesForMovies():
    statinfo = os.statvfs (config.get(prefs.MOVIES_DIRECTORY))
    return statinfo.f_frsize * statinfo.f_bavail / float(1024 * 1024 * 1024)
