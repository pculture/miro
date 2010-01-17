# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

"""Miro download daemon - background process
"""

def override_modules():
    import miro
    import miro.dl_daemon.private.config
    import miro.dl_daemon.private.httpauth
    import miro.dl_daemon.private.resources
    miro.config = miro.dl_daemon.private.config
    miro.httpauth = miro.dl_daemon.private.httpauth
    miro.resources = miro.dl_daemon.private.resources

def launch():
    # Make all output flush immediately.
    # Don't add extra import statements here.  If there's a problem importing
    # something we want to see the error in the log.
    import sys
    import os
    from miro import util
    import logging
    logPath = os.environ.get('DEMOCRACY_DOWNLOADER_LOG')
    if logPath is not None:
        if os.environ.get('DEMOCRACY_DOWNLOADER_FIRST_LAUNCH') == '1':
            logMode = 'w'
        else:
            logMode = 'a'
        log = open(logPath, logMode)
        sys.stdout = sys.stderr = log

    sys.stdout = util.AutoFlushingStream(sys.stdout)
    sys.stderr = util.AutoFlushingStream(sys.stderr)

    override_modules()

    from miro.plat.utils import setup_logging, initialize_locale
    setup_logging(inDownloader=True)
    util.setup_logging()
    initialize_locale()

    if os.environ.get('DEMOCRACY_DOWNLOADER_FIRST_LAUNCH') != '1':
        logging.info ("*** Starting new downloader log ***")
    else:
        logging.info ("*** Launching Downloader Daemon ****")

    # Start of normal imports
    import threading

    from miro.dl_daemon import daemon
    from miro.dl_daemon import download
    from miro import eventloop
    from miro import httpclient

    port = int(os.environ['DEMOCRACY_DOWNLOADER_PORT'])
    short_app_name = os.environ['DEMOCRACY_SHORT_APP_NAME']
    server = daemon.DownloaderDaemon(port, short_app_name)

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
    from miro import gtcache
    gtcache.init()
    logging.info ("*** Daemon ready ***")

if __name__ == "__main__":
    launch()
