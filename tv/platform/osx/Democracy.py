import os
import sys
import Foundation

# If the bundle is an alias bundle, we need to tweak the search path
bundle = Foundation.NSBundle.mainBundle()
bundleInfo = bundle.infoDictionary()
if bundleInfo['PyOptions']['alias']:
    root = os.path.dirname(bundle.bundlePath())
    root = os.path.join(root, '..', '..')
    root = os.path.normpath(root)
    sys.path[0:0] = ['%s/portable' % root]

# We can now import our stuff
import app
import prefs
import config

# Tee output off to a log file
class AutoflushingTeeStream:
    def __init__(self, streams):
        self.streams = streams
    def write(self, *args):
        for s in self.streams:
            s.write(*args)
            s.flush()

logFile = config.get(prefs.LOG_PATHNAME)
if logFile:
    h = open(logFile, "wt")
    sys.stdout = AutoflushingTeeStream([h, sys.stdout])
    sys.stderr = AutoflushingTeeStream([h, sys.stderr])

# Kick off the application
app.main()

