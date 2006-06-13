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
import httpclient

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
else:
    print "*** Launching Democracy Downloader Daemon ****"

port = int(os.environ['DEMOCRACY_DOWNLOADER_PORT'])
server = daemon.DownloaderDaemon(port)

# remove the limits for the connection pool, we limit them ourselves in the
# downloader code.
httpclient.HTTPConnectionPool.MAX_CONNECTIONS_PER_SERVER = sys.maxint
httpclient.HTTPConnectionPool.MAX_CONNECTIONS = sys.maxint

eventloop.startup()

print "*** Daemon ready ***"