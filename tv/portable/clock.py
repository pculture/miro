# Originally taken from BitTornado written by John Hoffman
# see portable/BitTorrent/LICENSE.txt for license information.
#
# Rewritten by Nick Nassar <nassar@pculture dotorg> to be thread safe.

from time import time
import sys
import threading

_MAXFORWARD = 100
_FUDGE = 1

class RelativeTime:
    def __init__(self):
        self.time = time()
        self.offset = 0
        self.lock = threading.Lock()

    def get_time(self):
        self.lock.acquire()
        try:
            t = time() + self.offset
            if t < self.time or t > self.time + _MAXFORWARD:
#                 print "FUDGE"
#                 print "t:           %s" % t
#                 print "self.time:   %s" % self.time
#                 print "self.offset: %s" % self.offset
                self.time += _FUDGE
                self.offset += self.time - t
                return self.time
            self.time = t
        finally:
            self.lock.release()
        return t

if sys.platform != 'win32':
    _RTIME = RelativeTime()
    def clock():
        return _RTIME.get_time()
