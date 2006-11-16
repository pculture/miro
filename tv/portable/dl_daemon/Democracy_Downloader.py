# Democracy download daemon Copyright (c) 2006 Participatory Culture Foundation
# Background process

def launch():
    # Make all output flush immediately.
    # Don't add extra import statements here.  If there's a problem importting
    # something we want to see the error in the log.
    import sys
    import os
    import util
    util.inDownloader = True
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

    import platformutils
    platformutils.initializeLocale()

    # Start of normal imports
    import threading

    from dl_daemon import daemon
    # This isn't used here, we just want to load it sooner.
    from dl_daemon import download
    import eventloop
    import httpclient

    port = int(os.environ['DEMOCRACY_DOWNLOADER_PORT'])
    server = daemon.DownloaderDaemon(port)

    # remove the limits for the connection pool, we limit them
    # ourselves in the downloader code.  Don't try to pipeline
    # requests, it doesn't make sense when the download size is so
    # large.
    httpclient.HTTPConnectionPool.MAX_CONNECTIONS_PER_SERVER = sys.maxint
    httpclient.HTTPConnectionPool.MAX_CONNECTIONS = sys.maxint
    httpclient.PIPELINING_ENABLED = False
    httpclient.SOCKET_READ_TIMEOUT = 300
    httpclient.SOCKET_INITIAL_READ_TIMEOUT = 30

    download.downloadUpdater.startUpdates()
    eventloop.startup()

    # Hack to init gettext after we can get config information
    #
    # See corresponding hack in gtcache.py
    import gtcache
    gtcache.init()
    print "*** Daemon ready ***"

if __name__ == "__main__":
    launch()
