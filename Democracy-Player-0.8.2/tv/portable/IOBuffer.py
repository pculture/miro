# IOBuffer.py Copyright (c) 2006 Participatory Culture Foundation
#
# Implements a file-like object similar to stringIO, except that it
# provides the data as a continuous read-only stream instead of a
# string. Made for use in a multithreaded environment where a producer
# writes and a consumer reads.  There's currently no limit on the
# buffer size, so this could consume lots of memory if the write
# function gets ahead of the read
#
# Only supports one consumer.
#
# read() blocks until there's some data left to return

from Queue import Queue

class IOBuffer:
    def __init__(self):
        # Force self.buf to be a string or unicode
        self.bufs = Queue()
        self.curBuf = ''
        self.pos = 0
        self.softspace = 0
        
    def read(self, size = None):
        remaining = len(self.curBuf) - self.pos
        if size is None:  # Grab everything
            output = []
            if remaining > 0:
                output.append(self.curBuf[self.pos:])
                self.pos = 0
                self.curBuf = ''
            data = self.bufs.get()
            while len(data) > 0:
                output.append(data)
                data = self.bufs.get()
            return ''.join(output)
        
        elif remaining > 0: # There's leftover data outside the queue
                            # and a size limit

            if remaining <= size: # The leftover data fits in size bytes
                ret = self.curBuf[self.pos:]
                self.pos = len(self.curBuf)
                return ret
            else:                 # The leftover data won't fit in size bytes
                ret = self.curBuf[self.pos:self.pos+size]
                self.pos += size
                return ret
        else:
            newBuf = self.bufs.get()
            if len(newBuf) <= size: # Send the string through now
                return newBuf
            else:
                self.pos = size
                self.curBuf = newBuf
                return newBuf[0:size]

    # FIXME: deprecated --used to allow an IOBuffer as the output of a template
    def getOutput(self):
        return self.read()

    def write(self, string):
        if len(string) > 0:
            self.bufs.put(string)

    def close(self):
        self.bufs.put('')
