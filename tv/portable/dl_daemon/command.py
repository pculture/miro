import time

import random
import socket
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
        #for overrriding

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
        httpauth.findHTTPAuth(callback, *args)

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
        return RemoteDownloader.updateStatus(*self.args, **self.kws)

class BatchUpdateDownloadStatus(Command):
    def action(self):
        from miro.downloader import RemoteDownloader
        for status in self.args[0]:
            RemoteDownloader.updateStatus(status)

class DownloaderErrorCommand(Command):
    def action(self):
        from miro import signals
        signals.system.failed("In Downloader process", details=self.args[0])

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
        return download.stopUpload(*self.args, **self.kws)

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
            if thread != threading.currentThread() and not thread.isDaemon():
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
