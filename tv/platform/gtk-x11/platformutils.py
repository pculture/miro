###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################
import os
import config
import prefs

def getAvailableGBytesForMovies():
    # TODO: windows implementation
    stream = os.popen ('stat -f %s -c "%%a"' % (config.get(prefs.MOVIES_DIRECTORY),))
    free_blocks = int(stream.read())
    stream.close()
    stream = os.popen ('stat -f %s -c "%%S"' % (config.get(prefs.MOVIES_DIRECTORY),))
    block_size = int(stream.read())
    stream.close()
    return free_blocks * block_size / float(1024 * 1024 * 1024)
