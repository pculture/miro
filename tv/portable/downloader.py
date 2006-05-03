import os
import threading
from threading import Thread, RLock
from base64 import b64encode

import app
import config
from download_utils import grabURL
from database import DDBObject, defaultDatabase
from dl_daemon import daemon, command

import views
import indexes

from download_utils import grabURL, parseURL, cleanFilename

# Returns an HTTP auth object corresponding to the given host, path or
# None if it doesn't exist
def findHTTPAuth(host,path,realm = None,scheme = None):
    #print "Trying to find HTTPAuth with host %s, path %s, realm %s, and scheme %s" %(host,path,realm,scheme)
    ret = None
    defaultDatabase.beginRead()
    try:
        for obj in views.httpauths:
            if (obj.host == host and path.startswith(obj.path) and
                (realm is None or obj.realm == realm) and
                (scheme is None or obj.authScheme == scheme)):
                ret = obj
                break
    finally:
        defaultDatabase.endRead()
    return ret


class HTTPAuthPassword(DDBObject):
    def __init__(self,username,password,host, realm, path, authScheme="Basic"):
        oldAuth = findHTTPAuth(host,path,realm,authScheme)
        while not oldAuth is None:
            oldAuth.remove()
            oldAuth = findHTTPAuth(host,path,realm,authScheme)
        self.username = username
        self.password = password
        self.host = host
        self.realm = realm
        self.path = os.path.dirname(path)
        self.authScheme = authScheme
        DDBObject.__init__(self)

    def getAuthToken(self):
        authString = ':'
        self.beginRead()
        try:
            authString = self.username+':'+self.password
        finally:
            self.endRead()
        return b64encode(authString)

    def getAuthScheme(self):
        ret = ""
        self.beginRead()
        try:
            ret = self.authScheme
        finally:
            self.endRead()
        return ret

class RemoteDownloader(DDBObject):
    """Download a file using the downloader daemon."""

    def __init__(self, url, item, contentType):
        self.url = url
        self.itemList = [item]
        self.contentType = contentType
        self.dlid = "noid"
        self.status = {}
        self.thread = Thread(target=self.runDownloader, 
                             name="downloader -- %s" % self.url)
        self.thread.setDaemon(True)
        self.thread.start()
        DDBObject.__init__(self)

    @classmethod
    def initializeDaemon(cls):
        RemoteDownloader.dldaemon = daemon.ControllerDaemon()

    @classmethod
    def updateStatus(cls, data):
        view = views.remoteDownloads.filterWithIndex(
            indexes.downloadsByDLID,data['dlid'])
        try:
            view.resetCursor()
            self = view.getNext()
        finally:   
            views.remoteDownloads.removeView(view)
        if not self is None:
            oldState = self.getState()
            self.status = data
            # Store the time the download finished
            if ((self.getState() in ['finished','uploading']) and
                (oldState not in ['finished', 'uploading'])):
                for item in self.itemList:
                    item.setDownloadedTime()
            for item in self.itemList:
                item.beginChange()
                item.endChange()

    ##
    # This is the actual download thread.
    def runDownloader(self):
        c = command.StartNewDownloadCommand(RemoteDownloader.dldaemon,
                                            self.url, self.contentType)
        self.dlid = c.send()
        #FIXME: This is sooo slow...
        views.remoteDownloads.recomputeIndex(indexes.downloadsByDLID)

    ##
    # Pauses the download.
    def pause(self, block=False):
        c = command.PauseDownloadCommand(RemoteDownloader.dldaemon,
                                            self.dlid)
        c.send(block=block)

    ##
    # Stops the download and removes the partially downloaded
    # file.
    def stop(self):
        c = command.StopDownloadCommand(RemoteDownloader.dldaemon,
                                            self.dlid)
        c.send(block=False)

    ##
    # Continues a paused or stopped download thread
    def start(self):
        c = command.StartDownloadCommand(RemoteDownloader.dldaemon,
                                            self.dlid)
        c.send(block=False)

    ##
    # Removes downloader from the database
    def remove(self):
        self.stop()
        DDBObject.remove(self)

    def getType(self):
        """Get the type of download.  Will return either "http" or
        "bittorrent".
        """
        self.beginRead()
        try:
            if self.contentType == 'application/x-bittorrent':
                return "bittorrent"
            else:
                return "http"
        finally:
            self.endRead()

    ##
    # In case multiple downloaders are getting the same file, we can support
    # multiple items
    def addItem(self,item):
        self.itemList.append(item)

    def getRate(self):
        self.beginRead()
        try:
            return self.status.get('rate', 0)
        finally:
            self.endRead()

    def getETA(self):
        self.beginRead()
        try:
            return self.status.get('eta', 0)
        finally:
            self.endRead()

    ##
    # Returns the reason for the failure of this download
    # This should only be called when the download is in the failed state
    def getReasonFailed(self):
        if not self.getState() == 'failed':
            msg = "getReasonFailed() called on a non-failed downloader"
            raise ValueError(msg)
        self.beginRead()
        try:
            return self.status['reasonFailed']
        finally:
            self.endRead()

    ##
    # Returns the URL we're downloading
    def getURL(self):
        self.beginRead()
        try:
            return self.url
        finally:
            self.endRead()

    ##    
    # Returns the state of the download: downloading, paused, stopped,
    # failed, or finished
    def getState(self):
        self.beginRead()
        try:
            return self.status.get('state', 'downloading')
        finally:
            self.endRead()

    ##
    # Returns the total size of the download in bytes
    def getTotalSize(self):
        self.beginRead()
        try:
            return self.status.get('totalSize', -1)
        finally:
            self.endRead()

    ##
    # Returns the current amount downloaded in bytes
    def getCurrentSize(self):
        self.beginRead()
        try:
            return self.status.get('currentSize', 0)
        finally:
            self.endRead()

    ##
    # Returns the filename that we're downloading to. Should not be
    # called until state is "finished."
    def getFilename(self):
        self.beginRead()
        try:
            return self.status['filename']
        finally:
            self.endRead()

    def restartIfNeeded(self):
        if self.dlid == 'noid' or len(self.status) == 0:
            thread = Thread(target=self.runDownloader, \
                            name="downloader -- %s" % self.url)
            thread.setDaemon(True)
            thread.start()
        elif self.getState() in ['downloading','uploading']:
            c = command.RestoreDownloaderCommand(RemoteDownloader.dldaemon, 
                    self.status)
            c.send(retry = True, block = False)

def cleanupIncompleteDownloads():
    downloadDir = os.path.join(config.get(config.MOVIES_DIRECTORY),
            'Incomplete Downloads')
    if not os.path.exists(downloadDir):
        return

    filesInUse = set()
    views.remoteDownloads.beginRead()
    try:
        for downloader in views.remoteDownloads:
            if downloader.status.get('state') in ('downloading', 'paused'):
                filename = downloader.status['filename']
                if not os.path.isabs(filename):
                    filename = os.path.join(downloadDir, file)
                filesInUse.add(filename)
    finally:
        views.remoteDownloads.endRead()

    for file in os.listdir(downloadDir):
        file = os.path.join(downloadDir, file)
        if file not in filesInUse:
            try:
                os.remove(file)
            except:
                pass # maybe a permissions error?  

def restartDownloads():
    views.remoteDownloads.beginRead()
    try:
        for downloader in views.remoteDownloads:
            downloader.restartIfNeeded()
    finally:
        views.remoteDownloads.endRead()


def startupDownloader():
    """Initialize the downloaders.

    This method currently does 2 things.  It deletes any stale files self in
    Incomplete Downloads, then it restarts downloads that have been restored
    from the database.  It must be called before any RemoteDownloader objects
    get created.
    """

    cleanupIncompleteDownloads()
    RemoteDownloader.initializeDaemon()
    restartDownloads()

def shutdownDownloader():
    RemoteDownloader.dldaemon.shutdownDownloaderDaemon()

class DownloaderFactory:
    lock = RLock()
    def __init__(self,item):
        self.item = item

    def getDownloader(self, url):
        if url.startswith('file://'):
            if url.endswith('.torrent'):
                return RemoteDownloader(url, self.item,
                        'application/x-bittorrent')
            else:
                raise ValueError("Don't know how to handle %s" % url)
        else:
            return self.getDownloaderFromWeb(url)

    def getDownloaderFromWeb(self, url):
        info = grabURL(url, 'HEAD')
        if info is None: # some websites don't support HEAD requests
            info = grabURL(url, 'GET')
            if info is None:
                # info is still None, we can't create a downloader
                return None
            else:
                info['file-handle'].close()
        return RemoteDownloader(info['updated-url'], self.item,
                info['content-type'])
