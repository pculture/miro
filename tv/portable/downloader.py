from base64 import b64encode
from gettext import gettext as _
from threading import RLock
import os
import re
import shutil

from database import DDBObject, defaultDatabase
from dl_daemon import daemon, command
from download_utils import nextFreeFilename, parseURL
from util import getTorrentInfoHash
import app
import config
import httpclient
import indexes
import prefs
import random
import views

# a hash of download ids that the server knows about.
_downloads = {}

# Returns an HTTP auth object corresponding to the given host, path or
# None if it doesn't exist
def findHTTPAuth(host,path,realm = None,scheme = None):
    #print "Trying to find HTTPAuth with host %s, path %s, realm %s, and scheme %s" %(host,path,realm,scheme)
    defaultDatabase.confirmDBThread()
    for obj in views.httpauths:
        if (obj.host == host and path.startswith(obj.path) and
            (realm is None or obj.realm == realm) and
            (scheme is None or obj.authScheme == scheme)):
            return obj
    return None


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
        self.confirmDBThread()
        authString = self.username+':'+self.password
        return b64encode(authString)

    def getAuthScheme(self):
        self.confirmDBThread()
        return self.authScheme


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

    def signalChange (self, needsSave=True):
        for item in self.itemList:
            item.signalChange(needsSave=False)
        DDBObject.signalChange (self, needsSave=needsSave)

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
        self.signalChange()

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
            self.signalChange()

    ##
    # This is the actual download thread.
    def runDownloader(self):
        c = command.StartNewDownloadCommand(RemoteDownloader.dldaemon,
                                            self.url, self.dlid, self.contentType)
        c.send(block=False)
        _downloads[self.dlid] = self
        self.signalChange()

    ##
    # Pauses the download.
    def pause(self, block=False):
        if _downloads.has_key(self.dlid):
            c = command.PauseDownloadCommand(RemoteDownloader.dldaemon,
                                             self.dlid)
            c.send(block=block)
        else:
            self.status["state"] = "paused"
            self.signalChange()

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
                self.signalChange()

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
            self.signalChange()
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
                self.signalChange()

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
            self.signalChange()

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
        self.confirmDBThread()
        if self.contentType == 'application/x-bittorrent':
            return "bittorrent"
        else:
            return "http"

    ##
    # In case multiple downloaders are getting the same file, we can support
    # multiple items
    def addItem(self,item):
        self.itemList.append(item)

    def removeItem(self, item):
        self.itemList.remove(item)
        if len (self.itemList) == 0:
            self.remove()

    def getRate(self):
        self.confirmDBThread()
        return self.status.get('rate', 0)

    def getETA(self):
        self.confirmDBThread()
        return self.status.get('eta', 0)

    ##
    # Returns the reason for the failure of this download
    # This should only be called when the download is in the failed state
    def getReasonFailed(self):
        if not self.getState() == 'failed':
            msg = "getReasonFailed() called on a non-failed downloader"
            raise ValueError(msg)
        self.confirmDBThread()
        return self.status['reasonFailed']

    ##
    # Returns the URL we're downloading
    def getURL(self):
        self.confirmDBThread()
        return self.url

    ##    
    # Returns the state of the download: downloading, paused, stopped,
    # failed, or finished
    def getState(self):
        self.confirmDBThread()
        return self.status.get('state', 'downloading')

    ##
    # Returns the total size of the download in bytes
    def getTotalSize(self):
        self.confirmDBThread()
        return self.status.get('totalSize', -1)

    ##
    # Returns the current amount downloaded in bytes
    def getCurrentSize(self):
        self.confirmDBThread()
        return self.status.get('currentSize', 0)

    ##
    # Returns the filename that we're downloading to. Should not be
    # called until state is "finished."
    def getFilename(self):
        self.confirmDBThread()
        return self.status.get('filename', '')

    def onRestore(self):
        self.itemList = []
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
    views.remoteDownloads.confirmDBThread()
    for downloader in views.remoteDownloads:
        if downloader.getState() in ('downloading', 'paused'):
            filename = downloader.getFilename()
            if len(filename) > 0:
                if not os.path.isabs(filename):
                    filename = os.path.join(downloadDir, file)
                filesInUse.add(filename)

    for file in os.listdir(downloadDir):
        file = os.path.join(downloadDir, file)
        if file not in filesInUse:
            try:
                os.remove(file)
            except:
                pass # maybe a permissions error?  

def restartDownloads():
    views.remoteDownloads.confirmDBThread()
    for downloader in views.remoteDownloads:
        downloader.restartIfNeeded()

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
    def __init__(self,item):
        self.item = item

    def getDownloader(self, url, create=True):
        downloader = _getDownloader (url=url)
        if downloader:
            return downloader
        if not create:
            return None
        if url.startswith('file://'):
            scheme, host, port, path = parseURL(url)
            if re.match(r'/[a-zA-Z]:', path):
                path = path[1:]
            try:
                getTorrentInfoHash(path)
            except ValueError:
                raise ValueError("Don't know how to handle %s" % url)
            else:
                return RemoteDownloader(url, self.item,
                        'application/x-bittorrent')
        else:
            return RemoteDownloader(url, self.item)
