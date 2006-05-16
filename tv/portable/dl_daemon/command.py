import random
import socket

class Command:
    def __init__(self, daemon, *args, **kws):
        self.id = "cmd%08d" % random.randint(0,99999999)
        self.orig = True
        self.args = args
        self.kws = kws
        self.daemon = daemon

    def setDaemon(self, daemon):
        self.daemon = daemon

    def send(self, block = True, retry = True):
        if block:
            print "WARNING: blocking %s" % repr(self)
        try:
            return self.daemon.send(self, block)
        except socket.error, e:
            self.daemon.handleSocketError(e)
            raise

    def setReturnValue(self, ret):
        self.orig = False
        self.ret = ret

    def getReturnValue(self):
        return self.ret

    def action(self):
        print "WARNING: no action defined for command %s" % self.id
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
        import downloader
        return downloader.findHTTPAuth(*self.args, **self.kws)

class UpdateDownloadStatus(Command):
    def action(self):
        from downloader import RemoteDownloader
        return RemoteDownloader.updateStatus(*self.args, **self.kws)

class DownloaderErrorCommand(Command):
    def action(self):
        import util
        util.failed("In Downloader process", details=self.args[0])

#############################################################################
#  App to Downloader commands                                               #
#############################################################################
class InitialConfigCommand(Command):
    def action(self):
        from dl_daemon import remoteconfig
        remoteconfig.setDictionary(*self.args, **self.kws)
        from dl_daemon import download
        download.startBTDownloader()

class StartNewDownloadCommand(Command):
    def action(self):
        from dl_daemon import download
        return download.startNewDownload(*self.args, **self.kws)

class StartDownloadCommand(Command):
    def action(self):
        from dl_daemon import download
        return download.startDownload(*self.args, **self.kws)

class PauseDownloadCommand(Command):
    def action(self):
        from dl_daemon import download
        return download.pauseDownload(*self.args, **self.kws)

class StopDownloadCommand(Command):
    def action(self):
        from dl_daemon import download
        return download.stopDownload(*self.args, **self.kws)

class GetDownloadStatusCommand(Command):
    def action(self):
        from dl_daemon import download
        return download.getDownloadStatus(*self.args, **self.kws)

class RestoreDownloaderCommand(Command):
    def action(self):
        from dl_daemon import download
        return download.restoreDownloader(*self.args, **self.kws)

class MigrateDownloadCommand(Command):
    def action(self):
        from dl_daemon import download
        return download.migrateDownload(*self.args, **self.kws)

# This is a special command that's trapped by the daemon
class ShutDownCommand(Command):
    def action(self):
        import eventloop
        eventloop.quit()
        print "starting ShutDownCommand"
        from dl_daemon import download
        download.shutDown()
        import threading
        for thread in threading.enumerate():
            if thread != threading.currentThread():
                thread.join()
