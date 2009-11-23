# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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
from miro import eventloop
import logging

DAEMONIC_THREAD_TIMEOUT = 2
# amount of time to wait for daemonic threads to quit.  Right now, the only
# thing we use Daemonic threads for is to send HTTP requests to BitTorrent
# trackers.

class Command:
    def __init__(self, daemon, *args, **kws):
        self.id = "cmd%08d" % random.randint(0,99999999)
        self.orig = True
        self.args = args
        self.kws = kws
        self.daemon = daemon

    def setDaemon(self, daemon):
        self.daemon = daemon

    def send(self, callback=None):
        if self.daemon.shutdown:
            return
        eventloop.addIdle(lambda : self.daemon.send(self, callback), "sending command %s" % repr(self))

    def setReturnValue(self, ret):
        self.orig = False
        self.ret = ret

    def getReturnValue(self):
        return self.ret

    def action(self):
        logging.warning ("no action defined for command %s", self.id)
        #for overriding

    def __getstate__(self):
        out = {"id":self.id, "args":self.args, "kws":self.kws, "orig":self.orig}
        try:
            out["ret"] = self.ret
        except AttributeError:
            pass
        return out

    def __setstate__(self, data):
        self.id = data["id"]
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
        id, args = self.args[0], self.args[1:]
        def callback(authHeader):
            c = GotHTTPAuthCommand(self.daemon, id, authHeader)
            c.send()
        httpauth.find_http_auth(callback, *args)

class AskForHTTPAuthCommand(Command):
    def action(self):
        from miro import httpauth
        id, args = self.args[0], self.args[1:]
        def callback(authHeader):
            c = GotHTTPAuthCommand(self.daemon, id, authHeader)
            c.send()
        httpauth.askForHTTPAuth(callback, *args)

class UpdateDownloadStatus(Command):
    def action(self):
        from miro.downloader import RemoteDownloader
        return RemoteDownloader.update_status(*self.args, **self.kws)

class BatchUpdateDownloadStatus(Command):
    def action(self):
        from miro.downloader import RemoteDownloader
        for status in self.args[0]:
            RemoteDownloader.update_status(status)

class DownloaderErrorCommand(Command):
    def action(self):
        from miro import signals
        signals.system.failed("In Downloader process", details=self.args[0])

class DuplicateTorrent(Command):
    # The downloader daemon detected that one download was for the same
    # torrent as another one.
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
        for item in duplicate.itemList:
            item.set_downloader(original)

class ShutDownResponseCommand(Command):
    def action(self):
        self.daemon.shutdownResponse()

#############################################################################
#  App to Downloader commands                                               #
#############################################################################
class InitialConfigCommand(Command):
    def action(self):
        from miro import config
        from miro.dl_daemon import download
        config.setDictionary(*self.args, **self.kws)
        download.configReceived()

class UpdateConfigCommand(Command):
    def action(self):
        from miro import config
        config.updateDictionary(*self.args, **self.kws)

class StartNewDownloadCommand(Command):
    def action(self):
        from miro.dl_daemon import download
        return download.startNewDownload(*self.args, **self.kws)

class StartDownloadCommand(Command):
    def action(self):
        from miro.dl_daemon import download
        return download.startDownload(*self.args, **self.kws)

class PauseDownloadCommand(Command):
    def action(self):
        from miro.dl_daemon import download
        return download.pauseDownload(*self.args, **self.kws)

class StopDownloadCommand(Command):
    def action(self):
        from miro.dl_daemon import download
        return download.stopDownload(*self.args, **self.kws)

class StopUploadCommand(Command):
    def action(self):
        from miro.dl_daemon import download
        return download.stop_upload(*self.args, **self.kws)

class PauseUploadCommand(Command):
    def action(self):
        from miro.dl_daemon import download
        return download.pauseUpload(*self.args, **self.kws)

class GetDownloadStatusCommand(Command):
    def action(self):
        from miro.dl_daemon import download
        return download.getDownloadStatus(*self.args, **self.kws)

class RestoreDownloaderCommand(Command):
    def action(self):
        from miro.dl_daemon import download
        return download.restoreDownloader(*self.args, **self.kws)

class MigrateDownloadCommand(Command):
    def action(self):
        from miro.dl_daemon import download
        return download.migrateDownload(*self.args, **self.kws)

class GotHTTPAuthCommand(Command):
    def action(self):
        id, authHeader = self.args
        from miro import httpauth 
        # note since we're in the downloader process here, httpauth is
        # dl_daemon/private/httpauth.py
        httpauth.handleHTTPAuthResponse(id, authHeader)

class ShutDownCommand(Command):
    def response_sent(self):
        from miro import eventloop
        eventloop.quit()
        logging.info ("Shutdown complete")

    def action(self):
        starttime = time.time()
        from miro.dl_daemon import download
        download.shutDown()
        import threading
        eventloop.threadPoolQuit()
        for thread in threading.enumerate():
            if thread != threading.currentThread() and thread.getName() != "MainThread" and not thread.isDaemon():
                thread.join()
        endtime = starttime + DAEMONIC_THREAD_TIMEOUT
        for thread in threading.enumerate():
            if thread != threading.currentThread():
                timeout = endtime - time.time()
                if timeout <= 0:
                    break
                thread.join(timeout)
        c = ShutDownResponseCommand(self.daemon)
        c.send(callback=self.response_sent)
        self.daemon.shutdown = True
