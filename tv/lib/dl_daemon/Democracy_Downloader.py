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

import logging

config_loaded = False
from miro import app
from miro import config

def override_modules():
    import miro
    import miro.dl_daemon.private.httpauth
    import miro.dl_daemon.private.resources
    miro.httpauth = miro.dl_daemon.private.httpauth
    miro.resources = miro.dl_daemon.private.resources

def launch():
    # Make all output flush immediately.
    # Don't add extra import statements here.  If there's a problem importing
    # something we want to see the error in the log.
    import logging
    import sys
    import os
    from miro import util

    sys.stdout = util.AutoFlushingStream(sys.stdout)
    sys.stderr = sys.stdout

    override_modules()

    from miro.plat.utils import setup_logging, initialize_locale
    setup_logging(in_downloader=True)
    util.setup_logging()
    initialize_locale()

    if os.environ.get('DEMOCRACY_DOWNLOADER_FIRST_LAUNCH') != '1':
        logging.info("Starting new downloader log")
    else:
        logging.info("Launching Downloader Daemon")
    log_versions()

    # Start of normal imports
    import threading

    from miro.dl_daemon import daemon
    from miro import httpclient

    addr = os.environ['DEMOCRACY_DOWNLOADER_ADDR']
    port = int(os.environ['DEMOCRACY_DOWNLOADER_PORT'])
    short_app_name = os.environ['DEMOCRACY_SHORT_APP_NAME']
    httpclient.start_thread()
    server = daemon.DownloaderDaemon(addr, port, short_app_name)
    # setup config for the downloader
    from miro import eventloop
    config.load(config.DownloaderConfig())
    app.downloader_config_watcher = config.ConfigWatcher(
            lambda foo, *args: eventloop.add_idle(foo, "config watcher",
                args=args))
    # start things up
    eventloop.startup()

def finish_startup_after_config():
    """Finish startup tasks once we have config setup.

    Called from command.InitialConfigCommand.
    """

    from miro import gtcache
    gtcache.init()

    from miro import httpclient
    from miro.dl_daemon import download
    download.startup()
    httpclient.init_libcurl()

    logging.info("Daemon ready")

def log_versions():
    import libtorrent
    logging.info("libtorrent: %s", libtorrent.version)

    import pycurl
    logging.info("pycurl:     %s", pycurl.version)

if __name__ == "__main__":
    launch()
