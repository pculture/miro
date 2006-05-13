# Democracy download daemon Copyright (c) 2006 Participatory Culture Foundation
# Background process

# Make all output flush immediately.
import sys
import util
import os
import eventloop
import threading

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

from dl_daemon import daemon

port = int(os.environ['DEMOCRACY_DOWNLOADER_PORT'])
server = daemon.DownloaderDaemon(port)
from dl_daemon import command
c = command.ReadyCommand(server)
from dl_daemon import download
download.startBTDownloader()
c = command.ReadyCommand(server)
c.send(block = False, retry = True)

eventloop.startup()
