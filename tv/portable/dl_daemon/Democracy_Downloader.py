# Democracy download daemon Copyright (c) 2006 Participatory Culture Foundation
# Background process

# Make all output flush immediately.
import sys
import util
util.inDownloader = True
import os
import threading

from dl_daemon import daemon
# This isn't used here, we just want to load it sooner.
from dl_daemon import download
import eventloop

logPath = os.environ.get('DEMOCRACY_DOWNLOADER_LOG')
if logPath is not None:
    if os.environ.get('DEMOCRACY_DOWNLOADER_FIRST_LAUNCH') == '1':
        logMode = 'w'
    else:
        logMode = 'a'
    log = open(logPath, logMode)
    sys.stdout = sys.stderr = log

sys.stdout = util.AutoflushingStream(sys.stdout)
sys.stderr = util.AutoflushingStream(sys.stderr)
if os.environ.get('DEMOCRACY_DOWNLOADER_FIRST_LAUNCH') != '1':
    print
    print "*** Starting new downloader log ***"
    print

port = int(os.environ['DEMOCRACY_DOWNLOADER_PORT'])
server = daemon.DownloaderDaemon(port)

eventloop.startup()
