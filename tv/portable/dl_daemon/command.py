import random
import cPickle
import traceback
from time import sleep

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
        while True:
            try:
                return self.daemon.send(self, block)
            except:
                #traceback.print_exc()
                if retry:
                    sleep(5)
                else:
                    break

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
        except:
            pass
        return out

    def __setstate__(self, data):
        self.id = data["id"]
        self.kws = data["kws"]
        self.args = data["args"]
        self.orig = data["orig"]
        try:
            self.ret = data["ret"]
        except:
            pass

#############################################################################
#  Downloader to App commands                                               #
#############################################################################
class GetConfigCommand(Command):
    def action(self):
        import config
        return config.get(*self.args, **self.kws)

class GetResourcePathCommand(Command):
    def action(self):
        import resource
        return resource.path(*self.args, **self.kws)

class GetResourceURLCommand(Command):
    def action(self):
        import resource
        return resource.url(*self.args, **self.kws)

class FindHTTPAuthCommand(Command):
    def action(self):
        import downloader
        return downloader.findHTTPAuth(*self.args, **self.kws)

class UpdateDownloadStatus(Command):
    def action(self):
        from downloader import RemoteDownloader
        return RemoteDownloader.updateStatus(*self.args, **self.kws)

#############################################################################
#  App to Downloader commands                                               #
#############################################################################
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

class ShutDownCommand(Command):
    def action(self):
        from dl_daemon import download
        return download.shutDown(*self.args, **self.kws)
