import os
import sys
import bsddb
import shutil
import types
from gettext import gettext as _
from os import remove
import re
from threading import RLock, Event, Thread
import traceback
from copy import copy

from clock import clock
from download_utils import cleanFilename, nextFreeFilename, shortenFilename
from download_utils import filenameFromURL
import eventloop
import httpclient

import config
import prefs
from sha import sha

from dl_daemon import command, daemon, bittorrent

import platformutils

# This pattern matches all possible strings.  I promise.
URIPattern = re.compile(r'^([^?]*/)?([^/?]*)/*(\?(.*))?$')

chatter = True

# a hash of download ids to downloaders
_downloads = {}

_lock = RLock()

def createDownloader(url, contentType, dlid):
    if contentType == 'application/x-bittorrent':
        return BTDownloader(url, dlid)
    else:
        return HTTPDownloader(url, dlid)

# Creates a new downloader object. Returns id on success, None on failure
def startNewDownload(url, dlid, contentType):
    dl = createDownloader(url, contentType, dlid)
    _downloads[dlid] = dl

def pauseDownload(dlid):
    try:
        download = _downloads[dlid]
    except: # There is no download with this id
        return True
    return download.pause()

def startDownload(dlid):
    try:
        download = _downloads[dlid]
    except KeyError:  # There is no download with this id
        err= "in startDownload(): no downloader with id %s" % dlid
        c = command.DownloaderErrorCommand(daemon.lastDaemon, err)
        c.send()
        return True
    return download.start()

def stopDownload(dlid, delete):
    try:
        _lock.acquire()
        try:
            download = _downloads[dlid]
            del _downloads[dlid]
        finally:
            _lock.release()
    except: # There is no download with this id
        return True
    return download.stop(delete)

def migrateDownload(dlid, directory):
    try:
        download = _downloads[dlid]
    except: # There is no download with this id
        pass
    else:
        if download.state in ("finished", "uploading"):
            download.moveToDirectory(directory)
            download.updateClient()

def getDownloadStatus(dlids = None):
    statuses = {}
    for key in _downloads.keys():
        if ((dlids is None)  or (dlids == key) or (key in dlids)):
            try:
                statuses[key] = _downloads[key].getStatus()
            except:
                pass
    return statuses

def shutDown():
    print "Shutting down downloaders..."
    for dlid in _downloads:
        _downloads[dlid].shutdown()

def restoreDownloader(downloader):
    downloader = copy(downloader)
    dlerType = downloader.get('dlerType')
    if dlerType == 'HTTP':
        dl = HTTPDownloader(restore = downloader)
    elif dlerType == 'BitTorrent':
        dl = BTDownloader(restore = downloader)
    else:
        err = "in restoreDownloader(): unknown dlerType: %s" % dlerType
        c = command.DownloaderErrorCommand(daemon.lastDaemon, err)
        c.send()
        return

    _downloads[downloader['dlid']] = dl

class DownloadStatusUpdater:
    """Handles updating status for all in progress downloaders.

    On OS X and gtk if the user is on the downloads page and has a bunch of
    downloads going, this can be a fairly CPU intensive task.
    DownloadStatusUpdaters mitigate this in 2 ways.

    1) DownloadStatusUpdater objects batch all status updates into one big
    update which takes much less CPU.  
    
    2) The update don't happen fairly infrequently (currently every 5 seconds).
    
    Becouse updates happen infrequently, DownloadStatusUpdaters should only be
    used for progress updates, not events like downloads starting/finishing.
    For those just call updateClient() since they are more urgent, and don't
    happen often enough to cause CPU problems.
    """

    UPDATE_CLIENT_INTERVAL = 5

    def __init__(self):
        self.toUpdate = set()

    def startUpdates(self):
        eventloop.addTimeout(self.UPDATE_CLIENT_INTERVAL, self.doUpdate,
                "Download status update")

    def doUpdate(self):
        try:
            statuses = []
            for downloader in self.toUpdate:
                statuses.append(downloader.getStatus())
            self.toUpdate = set()
            if statuses:
                command.BatchUpdateDownloadStatus(daemon.lastDaemon, 
                        statuses).send()
        finally:
            eventloop.addTimeout(self.UPDATE_CLIENT_INTERVAL, self.doUpdate,
                    "Download status update")

    def queueUpdate(self, downloader):
        self.toUpdate.add(downloader)

downloadUpdater = DownloadStatusUpdater()

class BGDownloader:
    def __init__(self, url, dlid):
        self.dlid = dlid
        self.url = url
        self.startTime = clock()
        self.endTime = self.startTime
        self.shortFilename = filenameFromURL(url)
        self.pickInitialFilename()
        self.state = "downloading"
        self.currentSize = 0
        self.totalSize = -1
        self.blockTimes = []
        self.shortReasonFailed = self.reasonFailed = "No Error"

    def getURL(self):
        return self.url

    def getStatus(self):
        return {'dlid': self.dlid,
            'url': self.url,
            'state': self.state,
            'totalSize': self.totalSize,
            'currentSize': self.currentSize,
            'eta': self.getETA(),
            'rate': self.getRate(),
            'uploaded': 0,
            'filename': self.filename,
            'startTime': self.startTime,
            'endTime': self.endTime,
            'shortFilename': self.shortFilename,
            'reasonFailed': self.reasonFailed,
            'shortReasonFailed': self.shortReasonFailed,
            'dlerType': None }

    def updateClient(self):
        x = command.UpdateDownloadStatus(daemon.lastDaemon, self.getStatus())
        return x.send()
        
    ##
    def pickInitialFilename(self):
        """Pick a path to download to based on self.shortFilename.

        This method sets self.filename, as well as creates any leading paths
        needed to start downloading there.
        """

        downloadDir = os.path.join(config.get(prefs.MOVIES_DIRECTORY),
                'Incomplete Downloads')
        # Create the download directory if it doesn't already exist.
        try:
            os.makedirs(downloadDir)
        except:
            pass
        baseFilename = os.path.join(downloadDir, self.shortFilename+".part")
        baseFilename = shortenFilename(baseFilename)
        self.filename = nextFreeFilename(baseFilename)

    def moveToMoviesDirectory(self):
        """Move our downloaded file from the Incomplete Downloads directoy to
        the movies directory.
        """
        if chatter:
            print "moving to movies directory filename is ", self.filename
        self.moveToDirectory(config.get(prefs.MOVIES_DIRECTORY))

    def moveToDirectory (self, directory):
        newfilename = os.path.join(directory, self.shortFilename)
        newfilename = shortenFilename(newfilename)
        if newfilename == self.filename:
            return
        newfilename = nextFreeFilename(newfilename)
        try:
            shutil.move(self.filename, newfilename)
        except (IOError, OSError), e:
            print "WARNING: Error moving %s to %s (%s)" % (self.filename,
                                                           newfilename, e)
        else:
            self.filename = newfilename
            if chatter:
                print "new file name is ", self.filename

    ##
    # Returns a float with the estimated number of seconds left
    def getETA(self):
        if self.totalSize == -1:
            return -1
        rate = self.getRate()
        if rate > 0:
            return (self.totalSize - self.currentSize)/rate
        else:
            return 0

    ##
    # Returns a float with the download rate in bytes per second
    def getRate(self):
        now = clock()
        if self.endTime != self.startTime:
            rate = self.currentSize/(self.endTime-self.startTime)
        else:
            haltedSince = now
            for time, size in reversed(self.blockTimes):
                if size == self.currentSize:
                    haltedSince = time
                else:
                    break
            if now - haltedSince > self.HALTED_THRESHOLD:
                rate = 0
            else:
                try:
                    timespan = now - self.blockTimes[0][0]
                    if timespan != 0:
                        endSize = self.blockTimes[-1][1]
                        startSize = self.blockTimes[0][1]
                        rate = (endSize - startSize) / timespan
                    else:
                        rate = 0
                except IndexError:
                    rate = 0
        return rate

    def handleError(self, shortReason, reason):
        self.state = "failed"
        self.reasonFailed = reason
        self.shortReasonFailed = shortReason
        self.updateClient()

    def handleNetworkError(self, error):
        if isinstance(error, httpclient.NetworkError):
            self.handleError(error.getFriendlyDescription(),
                    error.getLongDescription())
        else:
            print "WARNING: grabURL errback not called with NetworkError"
            self.handleError(str(error), str(error))

    def handleGenericError(self, longDescription):
        self.handleError(_("Error"), longDescription)


class HTTPDownloader(BGDownloader):
    UPDATE_CLIENT_WINDOW = 12
    HALTED_THRESHOLD = 3 # how many secs until we consider a download halted

    def __init__(self, url = None,dlid = None,restore = None):
        if restore is not None:
            self.__dict__ = copy(restore)
            self.blockTimes = []
            self.restartOnError = True
        else:
            BGDownloader.__init__(self, url, dlid)
            self.restartOnError = False
        self.client = None
        self.filehandle = None
        if self.state == 'downloading':
            if restore is not None:
                self.startDownload()
            else:
                self.startNewDownload()
        else:
            self.updateClient()

    def resetBlockTimes(self):
        self.blockTimes = [(clock(), self.currentSize)]

    def startNewDownload(self):
        self.currentSize = 0
        self.totalSize = -1
        self.startDownload()

    def startDownload(self):
        if self.currentSize == 0:
            headerCallback = self.onHeaders
        else:
            headerCallback = self.onHeadersRestart
        self.client = httpclient.grabURL(self.url,
                self.onDownloadFinished, self.onDownloadError,
                headerCallback, self.onBodyData, start=self.currentSize)
        self.resetBlockTimes()
        self.updateClient()

    def cancelRequest(self):
        if self.client is not None:
            self.client.cancel()
            self.client = None

    def handleError(self, shortReason, reason):
        BGDownloader.handleError(self, shortReason, reason)
        self.cancelRequest()

    def handleWriteError(self, error):
        self.handleGenericError(_("Could not write to %s") % self.filename)
        if self.filehandle is not None:
            try:
                self.filehandle.close()
            except:
                pass
        try:
            os.remove(self.filename)
        except:
            pass

    def onHeaders(self, info):
        if info['contentLength'] != None:
            self.totalSize = info['contentLength']
        if self.client.gotBadStatusCode:
            error = httpclient.UnexpectedStatusCode(info['status'])
            self.handleNetworkError(error)
            return
        if not self.acceptDownloadSize(self.totalSize):
            self.handleError(_("Not enough disk space"),
                _("%s MB required to store this video") % 
                (self.totalSize / (2 ** 20)))
            return
        #Get the length of the file, then create it
        self.shortFilename = cleanFilename(info['filename'])
        self.pickInitialFilename()
        try:
            self.filehandle = file(self.filename,"w+b")
        except IOError:
            self.handleGenericError("Couldn't open %s for writing" % 
                self.filename)
            return
        if self.totalSize > 0:
            try:
                self.filehandle.seek(self.totalSize-1)
                self.filehandle.write(' ')
                self.filehandle.seek(0)
            except IOError, error:
                self.handleWriteError(error)
                return
        self.updateClient()

    def onHeadersRestart(self, info):
        self.restartOnError = False
        if info['status'] != 206 or 'content-range' not in info:
            self.currentSize = 0
            self.totalSize = -1
            self.resetBlockTimes()
            return self.onHeaders(info)
        try:
            self.parseContentRange(info['content-range'])
        except ValueError:
            if chatter:
                print "WARNING, bad content-range: %r" % info['content-range']
                print "currentSize: %d totalSize: %d" % (self.currentSize,
                        self.totalSize)
            self.cancelRequest()
            self.startNewDownload()
        else:
            try:
                self.filehandle = file(self.filename,"r+b")
                self.filehandle.seek(self.currentSize)
            except IOError, e:
                self.handleWriteError(e)
        self.updateClient()

    def parseContentRange(self, contentRange):
        """Parse the content-range header from an http response.  If it's
        badly formatted, or it's not what we were expecting based on the state
        we restored to, raise a ValueError.
        """

        m = re.search('bytes\s+(\d+)-(\d+)/(\d+)', contentRange)
        if m is None:
            raise ValueError()
        start = int(m.group(1))
        end = int(m.group(2))
        totalSize = int(m.group(3))
        if start > self.currentSize or (end + 1 != totalSize):
            # we only have the 1st <self.currentSize> bytes of the file, so
            # we cant handle these responses
            raise ValueError()
        self.currentSize = start
        self.totalSize = totalSize

    def onDownloadError(self, error):
        if self.restartOnError:
            self.restartOnError = False
            self.startNewDownload()
        else:
            self.client = None
            self.handleNetworkError(error)

    def onBodyData(self, data):
        if self.state != 'downloading':
            return
        self.updateRateAndETA(len(data))
        downloadUpdater.queueUpdate(self)
        try:
            self.filehandle.write(data)
        except IOError, e:
            self.handleWriteError(e)

    def onDownloadFinished(self, response):
        self.client = None
        try:
            self.filehandle.close()
        except Exception, e:
            self.handleWriteError(e)
            return
        self.state = "finished"
        if self.totalSize == -1:
            self.totalSize = self.currentSize
        self.endTime = clock()
        try:
            self.moveToMoviesDirectory()
        except IOError, e:
            self.handleWriteError(e)
        self.updateClient()

    def getStatus(self):
        data = BGDownloader.getStatus(self)
        data['dlerType'] = 'HTTP'
        return data

    ##
    # Update the download rate and eta based on recieving length bytes
    def updateRateAndETA(self, length):
        now = clock()
        self.currentSize = self.currentSize + length
        self.blockTimes.append((now,  self.currentSize))
        if (len(self.blockTimes) > 0 and 
                now - self.blockTimes[0][0] > self.UPDATE_CLIENT_WINDOW):
            self.blockTimes.pop(0)
        
    ##
    # Checks the download file size to see if we can accept it based on the 
    # user disk space preservation preference
    def acceptDownloadSize(self, size):
        accept = True
        if config.get(prefs.PRESERVE_DISK_SPACE):
            if size < 0:
                size = 0
            preserved = config.get(prefs.PRESERVE_X_GB_FREE) * 1024 * 1024 * 1024
            available = platformutils.getAvailableBytesForMovies() - preserved
            accept = (size <= available)
        return accept

    ##
    # Pauses the download.
    def pause(self):
        if self.state != "stopped":
            self.cancelRequest()
            self.state = "paused"
            self.updateClient()

    ##
    # Stops the download and removes the partially downloaded
    # file.
    def stop(self, delete):
        if self.state == "downloading":
            if self.filehandle is not None:
                try:
                    if not self.filehandle.closed:
                        self.filehandle.close()
                    remove(self.filename)
                except:
                    pass
        if delete:
            try:
                if os.path.isdir(self.filename):
                    shutil.rmtree(self.filename)
                else:
                    remove(self.filename)
            except:
                pass
        self.currentSize = 0
        self.cancelRequest()
        self.state = "stopped"
        self.updateClient()

    ##
    # Continues a paused or stopped download thread
    def start(self):
        if self.state == 'paused' or self.state == 'stopped':
            self.state = "downloading"
            self.startDownload()

    def shutdown(self):
        self.cancelRequest()
        self.updateClient()

class BTDownloader(BGDownloader):
    def __init__(self, url = None, item = None, restore = None):
        if restore is not None:
            self.restoreState(restore)
        else:            
            self.metainfo = None
            self.torrent = None
            self.rate = self.eta = 0
            self.fastResumeData = None
            BGDownloader.__init__(self,url,item)
            self.runDownloader()

    def _shutdownTorrent(self):
        try:
            if self.torrent is not None:
                self.fastResumeData = self.torrent.shutdown()
        except:
            print "DTV: Warning: Error shutting down torrent"
            traceback.print_exc()

    def _startTorrent(self):
        self.torrent = bittorrent.TorrentDownload(self.metainfo,
                self.filename, self.fastResumeData)
        self.torrent.set_status_callback(self.updateStatus)
        self.torrent.start()

    @eventloop.asIdle
    def updateStatus(self, newStatus):
        """
        activity -- string specifying what's currently happening or None for
                normal operations.  
        upRate -- upload rate
        downRate -- download rate in kb/s
        upTotal -- total kb uploaded
        downTotal -- total kb downloaded
        fractionDone -- what portion of the download is completed.
        timeEst -- estimated completion time, in seconds.
        totalSize -- total size of the torrent in bytes
        """

        self.totalSize = newStatus['totalSize']
        self.rate = newStatus['downRate']
        self.eta = newStatus['timeEst']
        self.currentSize = int(self.totalSize * newStatus['fractionDone'])
        if self.state == "downloading" and newStatus['fractionDone'] == 1.0:
            self.moveToMoviesDirectory()
            self.state = "uploading"
            self.endTime = clock()
            self.updateClient()
        else:
            downloadUpdater.queueUpdate(self)

    def handleError(self, shortReason, reason):
        self._shutdownTorrent()
        BGDownloader.handleError(self, shortReason, reason)

    def moveToDirectory(self, directory):
        if self.state in ('uploading', 'downloading'):
            self._shutdownTorrent()
            BGDownloader.moveToDirectory(self, directory)
            self._startTorrent()
        else:
            BGDownloader.moveToDirectory(self, directory)

    def restoreState(self, data):
        self.__dict__ = data
        if 'fastResumeData' not in data:
            self.fastResumeData = None
        self.rate = self.eta = 0
        if self.state == 'downloading' or (
            self.state == 'uploading' and self.uploaded < 1.5*self.totalSize):
            self.runDownloader(done=True)

    def getStatus(self):
        data = BGDownloader.getStatus(self)
        data['metainfo'] = self.metainfo
        data['fastResumeData'] = self.fastResumeData
        data['dlerType'] = 'BitTorrent'
        return data

    def getRate(self):
        return self.rate

    def getETA(self):
        return self.eta
        
    def pause(self):
        self.state = "paused"
        self._shutdownTorrent()
        self.updateClient()

    def stop(self, delete):
        self.state = "stopped"
        self._shutdownTorrent()
        self.updateClient()
        if delete:
            try:
                if os.path.isdir(self.filename):
                    shutil.rmtree(self.filename)
                else:
                    remove(self.filename)
            except:
                pass

    def start(self):
        if self.state not in ('paused', 'stopped'):
            return

        self.state = "downloading"
        self.updateClient()
        self.getMetainfo()

    def shutdown(self):
        self._shutdownTorrent()
        self.updateClient()

    def gotMetainfo(self):
        # FIXME: If the client is stopped before a BT download gets
        #        its metadata, we never run this. It's not a huge deal
        #        because it only affects the incomplete filename
        if not self.restarting:
            self.pickInitialFilename()
        self.updateClient()
        self._startTorrent()

    def handleMetainfo(self, metainfo):
        self.metainfo = metainfo
        self.gotMetainfo()

    def onDescriptionDownload(self, info):
        self.handleMetainfo (info['body'])

    def onDescriptionDownloadFailed(self, exception):
        self.handleNetworkError(exception)

    def getMetainfo(self):
        if self.metainfo is None:
            if self.url.startswith('file://'):
                path = self.url[len('file://'):]
                metainfoFile = open(path, 'rb')
                try:
                    metainfo = metainfoFile.read()
                finally:
                    metainfoFile.close()

                self.handleMetainfo(metainfo)
            else:
                httpclient.grabURL(self.getURL(), self.onDescriptionDownload,
                        self.onDescriptionDownloadFailed)
        else:
            self.gotMetainfo()
                

    def runDownloader(self,done=False):
        self.restarting = done
        self.updateClient()
        self.getMetainfo()
