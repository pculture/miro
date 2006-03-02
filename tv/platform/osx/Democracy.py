import os
import sys

# Add extra stuff to the search path that will let us find our source
# directories when we have built a development bundle with py2app -A.
platform = 'osx'
root = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), '..', '..')
sys.path[0:0]=['%s/platform/%s' % (root, platform), '%s/platform' % root, '%s/portable' % root]

# Tee output off to a log file
class AutoflushingTeeStream:
    def __init__(self, streams):
        self.streams = streams
    def write(self, *args):
        for s in self.streams:
            s.write(*args)
            s.flush()

import config
logFile = config.get(config.LOG_PATHNAME)
if logFile:
    h = open(logFile, "wt")
    sys.stdout = AutoflushingTeeStream([h, sys.stdout])
    sys.stderr = AutoflushingTeeStream([h, sys.stderr])

# Kick off the application
import app
app.main()

