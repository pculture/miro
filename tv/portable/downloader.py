# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
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

from base64 import b64encode
from miro.gtcache import gettext as _
import os

from miro.database import DDBObject, defaultDatabase
from miro.dl_daemon import daemon, command
from miro.download_utils import nextFreeFilename, getFileURLPath, filterDirectoryName
from miro.util import getTorrentInfoHash, returnsUnicode, checkU, returnsFilename, unicodify, checkF, toUni
# from miro import app
from miro import config
from miro import httpclient
from miro import indexes
from miro import prefs
import random
from miro import views
from miro.plat.utils import samefile, FilenameType, unicodeToFilename
from miro import flashscraper
import logging
import traceback
from miro import fileutil

# a hash of download ids that the server knows about.
_downloads = {}

# Returns an HTTP auth object corresponding to the given host, path or
# None if it doesn't exist
def findHTTPAuth(host, path, realm=None, scheme=None):
    checkU(host)
    checkU(path)
    if realm:
        checkU(realm)
    if scheme:
        checkU(scheme)
    #print "Trying to find HTTPAuth with host %s, path %s, realm %s, and scheme %s" %(host,path,realm,scheme)
    defaultDatabase.confirmDBThread()
    for obj in views.httpauths:
        if (obj.host == host and path.startswith(obj.path) and
                (realm is None or obj.realm == realm) and
                (scheme is None or obj.authScheme == scheme)):
            return obj
    return None


class HTTPAuthPassword(DDBObject):
    def __init__(self, username, password, host, realm, path, authScheme=u"Basic"):
        checkU(username)
        checkU(password)
        checkU(host)
        checkU(realm)
        checkU(path)
        checkU(authScheme)
        oldAuth = findHTTPAuth(host, path, realm, authScheme)
        while not oldAuth is None:
            oldAuth.remove()
            oldAuth = findHTTPAuth(host, path, realm, authScheme)
        self.username = username
        self.password = password
        self.host = host
        self.realm = realm
        self.path = os.path.dirname(path)
        self.authScheme = authScheme
        DDBObject.__init__(self)

    def getAuthToken(self):
        authString = u':'
        self.confirmDBThread()
        authString = self.username+u':'+self.password
        return b64encode(authString)

    def getAuthScheme(self):
        self.confirmDBThread()
        return self.authScheme

totalUpRate = 0
totalDownRate = 0

def _getDownloader(dlid):
    return views.remoteDownloads.getItemWithIndex(indexes.downloadsByDLID, dlid)

@returnsUnicode
def generateDownloadID():
    dlid = u"download%08d" % random.randint(0, 99999999)
    while _getDownloader (dlid=dlid):
        dlid = u"download%08d" % random.randint(0, 99999999)
    return dlid

class RemoteDownloader(DDBObject):
    """Download a file using the downloader daemon."""

    def __init__(self, url, item, contentType=None, channelName=None):
        checkU(url)
        if contentType:
            checkU(contentType)
        self.origURL = self.url = url
        self.itemList = [item]
        self.dlid = generateDownloadID()
        self.status = {}
        if contentType is None:
            # HACK:  Some servers report the wrong content-type for torrent
            # files.  We try to work around that by assuming if the enclosure
            # states that something is a torrent, it's a torrent.
            # Thanks to j@v2v.cc
            enclosureContentType = item.getFirstVideoEnclosureType()
            if enclosureContentType == u'application/x-bittorrent':
                contentType = enclosureContentType
        self.contentType = u""
        self.deleteFiles = True
        self.channelName = channelName
        self.manualUpload = False
        DDBObject.__init__(self)
        if contentType is None:
            self.contentType = u""
        else:
            self.contentType = contentType

        if self.contentType == u'':
            self.getContentType()
        else:
            self.runDownloader()

    def signalChange(self, needsSave=True, needsSignalItem=True):
        if needsSignalItem:
            for item in self.itemList:
                item.signalChange(needsSave=False)
        DDBObject.signalChange(self, needsSave=needsSave)

    def onContentType(self, info):
        if not self.idExists():
            return

        if info['status'] == 200:
            self.url = info['updated-url'].decode('ascii','replace')
            self.contentType = None
            try:
                self.contentType = info['content-type'].decode('ascii','replace')
            except:
                self.contentType = None
            self.runDownloader()
        else:
            error = httpclient.UnexpectedStatusCode(info['status'])
            self.onContentTypeError(error)

    def onContentTypeError(self, error):
        if not self.idExists():
            return

        self.status['state'] = u"failed"
        self.status['shortReasonFailed'] = error.getFriendlyDescription()
        self.status['reasonFailed'] = error.getLongDescription()
        self.signalChange()

    def getContentType(self):
        httpclient.grabHeaders(self.url, self.onContentType, self.onContentTypeError)
 
    @classmethod
    def initializeDaemon(cls):
        RemoteDownloader.dldaemon = daemon.ControllerDaemon()

    def _getRates(self):
        state = self.getState()
        if state == u'downloading':
            return (self.status.get('rate', 0), self.status.get('upRate', 0))
        if state == u'uploading':
            return (0, self.status.get('upRate', 0))
        return (0, 0)

    def beforeChangingStatus(self):
        global totalDownRate
        global totalUpRate
        rates = self._getRates()
        totalDownRate -= rates[0]
        totalUpRate -= rates[1]

    def afterChangingStatus(self):
        global totalDownRate
        global totalUpRate
        rates = self._getRates()
        totalDownRate += rates[0]
        totalUpRate += rates[1]

    @classmethod
    def updateStatus(cls, data):
        for field in data:
            if field not in ['filename', 'shortFilename', 'channelName', 'metainfo', 'fastResumeData']:
                data[field] = unicodify(data[field])
        self = _getDownloader(dlid=data['dlid'])
        # print data
        if self is not None:
            try:
                if self.status == data:
                    return
            except Exception, e:
                # This is a known bug with the way we used to save fast resume
                # data
                print "WARNING exception when comparing status: %s" % e

            wasFinished = self.isFinished()
            self.beforeChangingStatus()

            # FIXME: how do we get all of the possible bit torrent
            # activity strings into gettext? --NN
            if data.has_key('activity') and data['activity']:
                data['activity'] = _(data['activity'])

            self.status = data

            # Store the time the download finished
            finished = self.isFinished() and not wasFinished
            self.afterChangingStatus()

            if self.getState() == u'uploading' and not self.manualUpload and self.getUploadRatio() > 1.5:
                self.stopUpload()

            self.signalChange(needsSignalItem = not finished)
            if finished:
                for item in self.itemList:
                    item.onDownloadFinished()

    def runDownloader(self):
        """This is the actual download thread.
        """
        flashscraper.tryScrapingURL(self.url, self._runDownloader)

    def _runDownloader(self, url, contentType = None):
        if not self.idExists():
            return # we got deleted while we were doing the flash scraping
        if contentType is not None:
            self.contentType = contentType
        if url is not None:
            self.url = url
            c = command.StartNewDownloadCommand(RemoteDownloader.dldaemon,
                                                self.url, self.dlid, self.contentType, self.channelName)
            c.send()
            _downloads[self.dlid] = self
        else:
            self.status["state"] = u'failed'
            self.status["shortReasonFailed"] = _('File not found')
            self.status["reasonFailed"] = _('Flash URL Scraping Error')
        self.signalChange()

    def pause(self, block=False):
        """Pauses the download."""
        if _downloads.has_key(self.dlid):
            c = command.PauseDownloadCommand(RemoteDownloader.dldaemon, self.dlid)
            c.send()
        else:
            self.beforeChangingStatus()
            self.status["state"] = u"paused"
            self.afterChangingStatus()
            self.signalChange()

    def stop(self, delete):
        """Stops the download and removes the partially downloaded
        file.
        """
        if self.getState() in [u'downloading', u'uploading', u'paused']:
            if _downloads.has_key(self.dlid):
                c = command.StopDownloadCommand(RemoteDownloader.dldaemon,
                                                self.dlid, delete)
                c.send()
                del _downloads[self.dlid]
        else:
            if delete:
                self.delete()
            self.status["state"] = u"stopped"
            self.signalChange()

    def delete(self):
        try:
            filename = self.status['filename']
        except KeyError:
            return
        try:
            fileutil.delete(filename)
        except:
            logging.warn("Error deleting downloaded file: %s\n%s" % 
                    (toUni(filename), traceback.format_exc()))

        parent = os.path.join(fileutil.expand_filename(filename), os.path.pardir)
        parent = os.path.normpath(parent)
        moviesDir = fileutil.expand_filename(config.get(prefs.MOVIES_DIRECTORY))
        if (os.path.exists(parent) and os.path.exists(moviesDir) and
                not samefile(parent, moviesDir) and
                len(os.listdir(parent)) == 0):
            try:
                os.rmdir(parent)
            except:
                logging.warn("Error deleting empty download directory: %s\n%s" %
                        (toUni(parent), traceback.format_exc()))

    def start(self):
        """Continues a paused, stopped, or failed download thread
        """
        if self.getState() == u'failed':
            if _downloads.has_key (self.dlid):
                del _downloads[self.dlid]
            self.dlid = generateDownloadID()
            views.remoteDownloads.recomputeIndex(indexes.downloadsByDLID)
            self.beforeChangingStatus()
            self.status = {}
            self.afterChangingStatus()
            if self.contentType == u"":
                self.getContentType()
            else:
                self.runDownloader()
            self.signalChange()
        elif self.getState() in (u'stopped', u'paused', u'offline'):
            if _downloads.has_key(self.dlid):
                c = command.StartDownloadCommand(RemoteDownloader.dldaemon,
                                                 self.dlid)
                c.send()
            else:
                self.status['state'] = u'downloading'
                self.restart()
                self.signalChange()

    def migrate(self, directory):
        if _downloads.has_key(self.dlid):
            c = command.MigrateDownloadCommand(RemoteDownloader.dldaemon,
                                               self.dlid, directory)
            c.send()
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
            if fileutil.exists(filename):
                if 'channelName' in self.status and self.status['channelName'] is not None:
                    channelName = filterDirectoryName(self.status['channelName'])
                    directory = os.path.join (directory, channelName)
                try:
                    fileutil.makedirs(directory)
                except:
                    pass
                newfilename = os.path.join(directory, shortFilename)
                if newfilename == filename:
                    return
                newfilename = nextFreeFilename(newfilename)
                def callback():
                    self.status['filename'] = newfilename
                    self.signalChange()
                fileutil.migrate_file(filename, newfilename, callback)
        for i in self.itemList:
            i.migrate_children(directory)

    def setDeleteFiles(self, deleteFiles):
        self.deleteFiles = deleteFiles

    def setChannelName(self, channelName):
        if self.channelName is None:
            if channelName:
                checkF(channelName)
            self.channelName = channelName

    def remove(self):
        """Removes downloader from the database and deletes the file.
        """
        global totalDownRate
        global totalUpRate
        rates = self._getRates()
        totalDownRate -= rates[0]
        totalUpRate -= rates[1]
        self.stop(self.deleteFiles)
        DDBObject.remove(self)

    def getType(self):
        """Get the type of download.  Will return either "http" or
        "bittorrent".
        """
        self.confirmDBThread()
        if self.contentType == u'application/x-bittorrent':
            return u"bittorrent"
        else:
            return u"http"

    def addItem(self, item):
        """In case multiple downloaders are getting the same file, we can support
        multiple items
        """
        if item not in self.itemList:
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

    @returnsUnicode
    def getStartupActivity(self):
        self.confirmDBThread()
        activity = self.status.get('activity')
        if activity is None:
            return _("starting up")
        else:
            return activity

    @returnsUnicode
    def getReasonFailed(self):
        """Returns the reason for the failure of this download
        This should only be called when the download is in the failed state
        """
        if not self.getState() == u'failed':
            msg = u"getReasonFailed() called on a non-failed downloader"
            raise ValueError(msg)
        self.confirmDBThread()
        return self.status['reasonFailed']

    @returnsUnicode
    def getShortReasonFailed(self):
        if not self.getState() == u'failed':
            msg = u"getShortReasonFailed() called on a non-failed downloader"
            raise ValueError(msg)
        self.confirmDBThread()
        return self.status['shortReasonFailed']

    @returnsUnicode
    def getURL(self):
        """Returns the URL we're downloading
        """
        self.confirmDBThread()
        return self.url

    @returnsUnicode    
    def getState(self):
        """Returns the state of the download: downloading, paused, stopped,
        failed, or finished
        """
        self.confirmDBThread()
        return self.status.get('state', u'downloading')

    def isFinished(self):
        return self.getState() in (u'finished', u'uploading', u'uploading-paused')

    def getTotalSize(self):
        """Returns the total size of the download in bytes
        """
        self.confirmDBThread()
        return self.status.get(u'totalSize', -1)

    def getCurrentSize(self):
        """Returns the current amount downloaded in bytes
        """
        self.confirmDBThread()
        return self.status.get(u'currentSize', 0)

    @returnsFilename
    def getFilename(self):
        """Returns the filename that we're downloading to. Should not be
        called until state is "finished."
        """
        self.confirmDBThread()
        return self.status.get('filename', FilenameType(''))

    def onRestore(self):
        DDBObject.onRestore(self)
        self.deleteFiles = True
        self.itemList = []
        if self.dlid == 'noid':
            # this won't happen nowadays, but it can for old databases
            self.dlid = generateDownloadID()
        self.status['rate'] = 0
        self.status['upRate'] = 0
        self.status['eta'] = 0

    def getUploadRatio(self):
        size = self.getCurrentSize()
        if size == 0:
            return 0
        return self.status.get('uploaded', 0) / size
    
    def restartIfNeeded(self):
        if self.getState() in (u'downloading', u'offline'):
            self.restart()
        if self.getState() in (u'uploading'):
            if self.manualUpload or self.getUploadRatio() < 1.5:
                self.restart()
            else:
                self.stopUpload()

    def restart(self):
        if len(self.status) == 0 or self.status.get('dlerType') is None:
            if self.contentType == u"":
                self.getContentType()
            else:
                self.runDownloader()
        else:
            _downloads[self.dlid] = self
            c = command.RestoreDownloaderCommand(RemoteDownloader.dldaemon, 
                                                 self.status)
            c.send()

    def startUpload(self):
        if (self.getState() not in (u'finished', u'uploading-paused')
                or self.getType() != u'bittorrent'):
            return
        self.manualUpload = True
        if _downloads.has_key(self.dlid):
            c = command.StartDownloadCommand(RemoteDownloader.dldaemon,
                                             self.dlid)
            c.send()
        else:
            self.beforeChangingStatus()
            self.status['state'] = u'uploading'
            self.afterChangingStatus()
            self.restart()
            self.signalChange()

    def stopUpload(self):
        """
        Stop uploading/seeding and set status as "finished".
        """
        if _downloads.has_key(self.dlid):
            c = command.StopUploadCommand(RemoteDownloader.dldaemon,
                                          self.dlid)
            c.send()
            del _downloads[self.dlid]
        self.beforeChangingStatus()
        self.status["state"] = u"finished"
        self.afterChangingStatus()
        self.signalChange()

    def pauseUpload(self):
        """
        Stop uploading/seeding and set status as "uploading-paused".
        """
        if _downloads.has_key(self.dlid):
            c = command.PauseUploadCommand(RemoteDownloader.dldaemon,
                                           self.dlid)
            c.send()
            del _downloads[self.dlid]
        self.beforeChangingStatus()
        self.status["state"] = u"uploading-paused"
        self.afterChangingStatus()
        self.signalChange()


def cleanupIncompleteDownloads():
    downloadDir = os.path.join(config.get(prefs.MOVIES_DIRECTORY),
                                          'Incomplete Downloads')
    if not fileutil.exists(downloadDir):
        return

    filesInUse = set()
    views.remoteDownloads.confirmDBThread()
    for downloader in views.remoteDownloads:
        if downloader.getState() in ('downloading', 'paused',
                                     'offline', 'uploading', 'finished',
                                     'uploading-paused'):
            filename = downloader.getFilename()
            if len(filename) > 0:
                if not fileutil.isabs(filename):
                    filename = os.path.join(downloadDir, filename)
                filesInUse.add(filename)

    for f in fileutil.listdir(downloadDir):
        f = os.path.join(downloadDir, f)
        if f not in filesInUse:
            try:
                if fileutil.isfile(f):
                    fileutil.remove (f)
                elif fileutil.isdir(f):
                    fileutil.rmtree (f)
            except:
                # FIXME - maybe a permissions error?
                pass

def restartDownloads():
    views.remoteDownloads.confirmDBThread()
    for downloader in views.remoteDownloads:
        downloader.restartIfNeeded()

def killUploaders(*args):
    torrent_limit = config.get(prefs.UPSTREAM_TORRENT_LIMIT)
    while (views.autoUploads.len() > torrent_limit):
        views.autoUploads[0].stopUpload()

def configChangeUploaders(key, value):
    if key == prefs.UPSTREAM_TORRENT_LIMIT.key:
        killUploaders()

def limitUploaders():
    views.autoUploads.addAddCallback(killUploaders)
    config.add_change_callback(configChangeUploaders)
    killUploaders()
        

def startupDownloader():
    """Initialize the downloaders.

    This method currently does 2 things.  It deletes any stale files self in
    Incomplete Downloads, then it restarts downloads that have been restored
    from the database.  It must be called before any RemoteDownloader objects
    get created.
    """

    cleanupIncompleteDownloads()
    RemoteDownloader.initializeDaemon()
    limitUploaders()
    restartDownloads()

def shutdownDownloader(callback=None):
    if hasattr(RemoteDownloader, 'dldaemon') and RemoteDownloader.dldaemon is not None:
        RemoteDownloader.dldaemon.shutdownDownloaderDaemon(callback=callback)
    else:
        callback()

def lookupDownloader(url):
    return views.remoteDownloads.getItemWithIndex(indexes.downloadsByURL, url)

def getExistingDownloaderByURL(url):
    downloader = lookupDownloader(url)
    return downloader

def getExistingDownloader(item):
    downloader = lookupDownloader(item.getURL())
    if downloader:
        downloader.addItem(item)
    return downloader

def getDownloader(item):
    existing = getExistingDownloader(item)
    if existing:
        return existing
    url = item.getURL()
    channelName = unicodeToFilename(item.getChannelTitle(True))
    if not channelName:
        channelName = None
    if url.startswith(u'file://'):
        path = getFileURLPath(url)
        try:
            getTorrentInfoHash(path)
        except ValueError:
            raise ValueError("Don't know how to handle %s" % url)
        except IOError:
            return None
        else:
            return RemoteDownloader(url, item, u'application/x-bittorrent', channelName=channelName)
    else:
        return RemoteDownloader(url, item, channelName=channelName)
