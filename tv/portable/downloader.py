import os
import shutil
from threading import RLock
from base64 import b64encode

import app
import config
import prefs
from database import DDBObject, defaultDatabase
from dl_daemon import daemon, command

import views
import indexes
import random
import httpclient

from download_utils import nextFreeFilename
from gettext import gettext as _

# a hash of download ids that the server knows about.
_downloads = {}

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

def _getDownloader (dlid = None, url = None):
    if dlid is not None:
        view = views.remoteDownloads.filterWithIndex(
            indexes.downloadsByDLID,dlid)
        try:
            view.resetCursor()
            dler = view.getNext()
        finally:   
            views.remoteDownloads.removeView(view)
        return dler
    if url is not None:
        view = views.remoteDownloads.filterWithIndex(
            indexes.downloadsByURL,url)
        try:
            view.resetCursor()
            dler = view.getNext()
        finally:   
            views.remoteDownloads.removeView(view)
        return dler

def generateDownloadID():
    dlid = "download%08d" % random.randint(0,99999999)
    while _getDownloader (dlid=dlid):
        dlid = "download%08d" % random.randint(0,99999999)
    return dlid

class RemoteDownloader(DDBObject):
    """Download a file using the downloader daemon."""

    def __init__(self, url, item, contentType = None):
        self.url = url
        self.itemList = [item]
        self.contentType = contentType
        self.dlid = generateDownloadID()
        self.status = {}
        if contentType is None:
            self.contentType = ""
            self.getContentType()
        else:
            self.contentType = contentType
            self.runDownloader()
        DDBObject.__init__(self)

    def onContentType (self, info):
        if info['status'] == 200:
            self.url = info['updated-url']
            self.contentType = info.get('content-type',None)
            self.runDownloader()
        else:
            self.onContentTypeError(info['reason'])

    def onContentTypeError (self, error):
        self.status['state'] = "failed"
        self.status['reasonFailed'] = str(error)
        for item in self.itemList:
            item.beginChange()
            item.endChange()

    def getContentType(self):
        httpclient.grabHeaders(self.url, self.onContentType, self.onContentTypeError)
 
    @classmethod
    def initializeDaemon(cls):
        RemoteDownloader.dldaemon = daemon.ControllerDaemon()

    @classmethod
    def updateStatus(cls, data):
        self = _getDownloader (dlid=data['dlid'])
        # print data
        if self is not None:
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
                                            self.url, self.dlid, self.contentType)
        c.send(block=False)
        _downloads[self.dlid] = self
        for item in self.itemList:
            item.beginChange()
            item.endChange()

    ##
    # Pauses the download.
    def pause(self, block=False):
        if _downloads.has_key(self.dlid):
            c = command.PauseDownloadCommand(RemoteDownloader.dldaemon,
                                             self.dlid)
            c.send(block=block)
        else:
            self.status["state"] = "paused"

    ##
    # Stops the download and removes the partially downloaded
    # file.
    def stop(self):
        if ((self.getState() in ['downloading','uploading'])):
            if _downloads.has_key(self.dlid):
                c = command.StopDownloadCommand(RemoteDownloader.dldaemon,
                                                self.dlid)
                c.send(block=False)
                del _downloads[self.dlid]
            else:
                self.status["state"] = "stopped"

    ##
    # Continues a paused, stopped, or failed download thread
    def start(self):
        if self.getState() == 'failed':
            if _downloads.has_key (self.dlid):
                del _downloads[self.dlid]
            self.dlid = generateDownloadID()
            views.remoteDownloads.recomputeIndex(indexes.downloadsByDLID)
            self.status = {}
            if self.contentType == "":
                self.getContentType()
            else:
                self.runDownloader()
        elif self.getState() in ('stopped', 'paused'):
            if _downloads.has_key(self.dlid):
                c = command.StartDownloadCommand(RemoteDownloader.dldaemon,
                                                 self.dlid)
                c.send(block=False)
            else:
                _downloads[self.dlid] = self
                c = command.RestoreDownloaderCommand(RemoteDownloader.dldaemon, 
                                                     self.status)
                c.send(retry = True, block = False)

    def migrate(self):
        if _downloads.has_key(self.dlid):
            c = command.MigrateDownloadCommand(RemoteDownloader.dldaemon,
                                               self.dlid)
            c.send(block=False)
        else:
            # downloader doesn't have our dlid.  Move the file ourself.
            try:
                shortFilename = self.status['shortFilename']
            except KeyError:
                print """\
WARNING: can't migrate download because we don't have a shortFilename!
URL was %s""" % self.url
                return
            try:
                filename = self.status['filename']
            except KeyError:
                print """\
WARNING: can't migrate download because we don't have a filename!
URL was %s""" % self.url
                return
            if os.path.exists(filename):
                newfilename = os.path.join(config.get(prefs.MOVIES_DIRECTORY),
                        shortFilename)
                newfilename = nextFreeFilename(newfilename)
                try:
                    shutil.move(filename, newfilename)
                except IOError, error:
                    print "WARNING: Error moving %s to %s (%s)" % (self.status['filename'],
                            newfilename, error)
                else:
                    self.status['filename'] = newfilename

    ##
    # Removes downloader from the database and deletes the file.
    def remove(self):
        self.stop()
        try:
            filename = self.status['filename']
            os.remove (filename)
        except:
            pass
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
            return self.status.get('filename', '')
        finally:
            self.endRead()

    def onRestore(self):
        if self.dlid == 'noid':
            # this won't happen nowadays, but it can for old databases
            self.dlid = generateDownloadID()
        self.status['rate'] = 0
        self.status['eta'] = 0

    def restartIfNeeded(self):
        if self.getState() in ('downloading','uploading'):
            if len(self.status) == 0 or self.status.get('dlerType') is None:
                if self.contentType == "":
                    self.getContentType()
                else:
                    self.runDownloader()
            else:
                _downloads[self.dlid] = self
                c = command.RestoreDownloaderCommand(RemoteDownloader.dldaemon, 
                                                     self.status)
                c.send(retry = True, block = False)

def cleanupIncompleteDownloads():
    downloadDir = os.path.join(config.get(prefs.MOVIES_DIRECTORY),
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

def shutdownDownloader(callback = None):
    RemoteDownloader.dldaemon.shutdownDownloaderDaemon(callback=callback)

class DownloaderFactory:
    lock = RLock()
    def __init__(self,item):
        self.item = item

    def getDownloader(self, url):
        downloader = _getDownloader (url=url)
        if downloader:
            return downloader
        if url.startswith('file://'):
            if url.endswith('.torrent'):
                return RemoteDownloader(url, self.item,
                        'application/x-bittorrent')
            else:
                raise ValueError("Don't know how to handle %s" % url)
        else:
            return RemoteDownloader(url, self.item)
