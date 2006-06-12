###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################
import os
import config
import prefs

# We need to define samefile for the portable code.  Lucky for us, this is
# very easy.
from os.path import samefile

def getAvailableBytesForMovies():
    statinfo = os.statvfs (config.get(prefs.MOVIES_DIRECTORY))
    return statinfo.f_frsize * statinfo.f_bavail
