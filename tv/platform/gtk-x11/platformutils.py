###############################################################################
#### Helper method used to get the free space on the disk where downloaded ####
#### movies are stored                                                     ####
###############################################################################
import os

def getAvailableGBytesForMovies():
    # TODO: windows implementation
    stream = os.popen ('stat -f /home/clahey/Movies2/Democracy/ -c "%a"')
    free_blocks = int(stream.read())
    stream.close()
    stream = os.popen ('stat -f /home/clahey/Movies2/Democracy/ -c "%S"')
    block_size = int(stream.read())
    stream.close()
    return free_blocks * block_size / float(1024 * 1024 * 1024)
