# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
# 
# The Software is provided "AS IS", without warranty of any kind,
# express or implied, including but not limited to the warranties of
# merchantability,  fitness for a particular purpose and
# noninfringement. In no event shall the  authors or copyright holders
# be liable for any claim, damages or other liability, whether in an
# action of contract, tort or otherwise, arising from, out of or in
# connection with the Software or the use or other dealings in the
# Software.
#
# Copyright (C) 2002 John Hoffman
#               2006 Participatory Culture Foundation

from time import time, clock
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
