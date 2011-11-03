# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

import time
import random
import threading
import logging

from miro import app
from miro import eventloop

# Amount of time to wait for daemonic threads to quit.  Right now, the
# only thing we use Daemonic threads for is to send HTTP requests to
# BitTorrent trackers.
DAEMONIC_THREAD_TIMEOUT = 2

class Command(object):
    spammy = False
    def __init__(self, daemon, *args, **kws):
        self.command_id = "cmd%08d" % random.randint(0, 99999999)
        self.orig = True
        self.args = args
        self.kws = kws
        self.daemon = daemon

    def set_daemon(self, daemon):
        self.daemon = daemon

    def send(self, callback=None):
        if self.daemon.shutdown:
            return
        eventloop.add_idle(lambda : self.daemon.send(self, callback),
                           "sending command %r" % self)

    def action(self):
        # for overriding
        logging.warning("no action defined for command %s", self.command_id)

    def __getstate__(self):
        out = {"id": self.command_id,
               "args": self.args,
               "kws": self.kws,
               "orig": self.orig}
        try:
            out["ret"] = self.ret
        except AttributeError:
            pass
        return out

    def __setstate__(self, data):
        self.command_id = data["id"]
        self.kws = data["kws"]
        self.args = data["args"]
        self.orig = data["orig"]
        try:
            self.ret = data["ret"]
        except KeyError:
            pass

#############################################################################
#  Downloader to App commands                                               #
#############################################################################
class FindHTTPAuthCommand(Command):
    def action(self):
        from miro import httpauth
        id_, args = self.args[0], self.args[1:]
        def callback(auth_header):
            c = GotHTTPAuthCommand(self.daemon, id_, auth_header)
            c.send()
        httpauth.find_http_auth(callback, *args)

class AskForHTTPAuthCommand(Command):
    def action(self):
        from miro import httpauth
        id_, args = self.args[0], self.args[1:]
        def callback(auth_header):
            c = GotHTTPAuthCommand(self.daemon, id_, auth_header)
            c.send()
        httpauth.ask_for_http_auth(callback, *args)

class RemoveHTTPAuthCommand(Command):
    def action(self):
        from miro import httpauth
        httpauth.remove_by_url_and_realm(*self.args)

class BatchUpdateDownloadStatus(Command):
    spammy = True
    def action(self):
        from miro.downloader import RemoteDownloader
        from miro.messages import DownloaderSyncCommandComplete

        cmd_done = self.args[1]
        fresh = all(RemoteDownloader.update_status(status, cmd_done=cmd_done)
                    for status in self.args[0])
        if cmd_done and fresh:
            DownloaderSyncCommandComplete().send_to_frontend()

class DownloaderErrorCommand(Command):
    def action(self):
        from miro import signals
        signals.system.failed("In Downloader process", details=self.args[0])

class DuplicateTorrent(Command):
    """The downloader daemon detected that one download was for the same
    torrent as another one.
    """
    def action(self):
        original_id, duplicate_id = self.args[0], self.args[1]
        from miro import downloader
        duplicate = downloader.get_downloader_by_dlid(duplicate_id)
        original = downloader.get_downloader_by_dlid(original_id)
        if duplicate is None:
            logging.warn("duplicate torrent doesn't exist anymore, "
                    "ignoring (dlid %s)", duplicate_id)
            return
        if original is None:
            logging.warn("original torrent doesn't exist anymore, "
                    "restarting (dlid %s)", original_id)
            duplicate.restart()
            return
        for item in duplicate.item_list:
            item.set_downloader(original)

class ShutDownResponseCommand(Command):
    def action(self):
        self.daemon.shutdown_response()

#############################################################################
#  App to Downloader commands                                               #
#############################################################################

# XXX why do we have so much junk here when we can multiplex this stuff with
# a cmd parameter? -gl
class InitialConfigCommand(Command):
    def action(self):
        app.config.set_dictionary(*self.args, **self.kws)
        from miro.dl_daemon import MiroDownloader
        MiroDownloader.finish_startup_after_config()

class UpdateConfigCommand(Command):
    def action(self):
        app.config.set_key(*self.args, **self.kws)

class UpdateHTTPPasswordsCommand(Command):
    def action(self):
        from miro.dl_daemon.private import httpauth
        httpauth.update_passwords(*self.args)

# Downloader Daemon start/stop/resume demux.
#
# This is the class that contains the action handler for commands which may
# be marshalled and sent to us via the DownloadStateManager().
#
# Here, they are demuxed, and then dispatched to the downloader.
class DownloaderBatchCommand(Command):
    STOP    = 0
    RESUME  = 1
    PAUSE   = 2
    RESTORE = 4

    def action(self):
        from miro.dl_daemon import download
        mark_reply = True
        for dlid, (cmd, args) in self.args[0].iteritems():
            if cmd == self.PAUSE:
                upload = args['upload']
                if upload:
                    download.pause_upload(dlid)
                else:
                    download.pause_download(dlid)
            elif cmd == self.STOP:
                upload = args['upload']
                if upload:
                    download.stop_upload(dlid)
                else:
                    download.stop_download(dlid, args['delete'])
            elif cmd == self.RESUME:
                channel_name = args['channel_name']
                url = args['url']
                content_type = args['content_type']
                download.start_download(url, dlid, content_type, channel_name)
            elif cmd == self.RESTORE:
                # Restoring a downloader doesn't actually change any state
                # so don't reply.
                mark_reply = False
                downloader = args['downloader']
                download.restore_downloader(downloader)
            else:
                raise ValueError('unknown downloader batch command %s' % cmd)
        # Mark this so that the next time we run through the periodic update
        # which will be after all the above have been processed because we
        # are in the same thread.
        if mark_reply:
            download.DOWNLOAD_UPDATER.set_cmds_done()
 
class MigrateDownloadCommand(Command):
    def action(self):
        from miro.dl_daemon import download
        return download.migrate_download(*self.args, **self.kws)

class GotHTTPAuthCommand(Command):
    def action(self):
        id_, auth_header = self.args
        from miro.dl_daemon.private import httpauth
        httpauth.handle_http_auth_response(id_, auth_header)

class ShutDownCommand(Command):
    def response_sent(self):
        eventloop.shutdown()
        logging.info("Shutdown complete")

    def action(self):
        starttime = time.time()
        from miro import httpclient
        from miro.dl_daemon import download
        download.shutdown()
        httpclient.stop_thread()
        eventloop.thread_pool_quit()
        for thread in threading.enumerate():
            if (thread != threading.currentThread()
                 and thread.getName() != "MainThread"
                 and not thread.isDaemon()):
                thread.join()
        endtime = starttime + DAEMONIC_THREAD_TIMEOUT
        for thread in threading.enumerate():
            if (thread != threading.currentThread() 
                and thread.getName() != "MainThread"):
                timeout = endtime - time.time()
                if timeout <= 0:
                    break
                thread.join(timeout)
        c = ShutDownResponseCommand(self.daemon)
        c.send(callback=self.response_sent)
        self.daemon.shutdown = True
