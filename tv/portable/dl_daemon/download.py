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

import os
import re
from threading import RLock
from copy import copy
import sys

from miro.gtcache import gettext as _

import libtorrent as lt
from miro.clock import clock
from miro.download_utils import cleanFilename, nextFreeFilename, checkFilenameExtension, filterDirectoryName
from miro.download_utils import filenameFromURL, getFileURLPath
from miro import eventloop
from miro import httpclient
import datetime
import logging
from miro import fileutil

from miro import config
from miro import prefs

from miro.dl_daemon import command, daemon
from miro.util import checkF, checkU, stringify
from miro.plat.utils import get_available_bytes_for_movies, utf8_to_filename

chatter = True

# a hash of download ids to downloaders
_downloads = {}

_lock = RLock()

def configReceived():
    torrentSession.startup()

def createDownloader(url, contentType, dlid):
    checkU(url)
    checkU(contentType)
    if contentType == u'application/x-bittorrent':
        return BTDownloader(url, dlid)
    else:
        return HTTPDownloader(url, dlid, expectedContentType=contentType)

# Creates a new downloader object. Returns id on success, None on failure
def startNewDownload(url, dlid, contentType, channelName):
    checkU(url)
    checkU(contentType)
    if channelName:
        checkF(channelName)
    dl = createDownloader(url, contentType, dlid)
    dl.channelName = channelName
    _downloads[dlid] = dl

def pauseDownload(dlid):
    try:
        download = _downloads[dlid]
    except (SystemExit, KeyboardInterrupt):
        raise
    except: # There is no download with this id
        return True
    return download.pause()

def info_hash_to_long(info_hash):
    # the info_hash() method from libtorrent returns a "big_number" object.
    # This doesn't hash very well: different instances with the same value
    # will have different hashes.  So we need to convert them to long objects,
    # though this weird process
    return long(str(info_hash), 16)

def startDownload(dlid):
    try:
        download = _downloads[dlid]
    except KeyError:  # There is no download with this id
        err= u"in startDownload(): no downloader with id %s" % dlid
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
    except (SystemExit, KeyboardInterrupt):
        raise
    except: # There is no download with this id
        return True
    return download.stop(delete)

def stopUpload(dlid):
    try:
        _lock.acquire()
        try:
            download = _downloads[dlid]
            if download.state not in (u"uploading", u"uploading-paused"):
                return
            del _downloads[dlid]
        finally:
            _lock.release()
    except (SystemExit, KeyboardInterrupt):
        raise
    except: # There is no download with this id
        return
    return download.stopUpload()

def pauseUpload(dlid):
    try:
        _lock.acquire()
        try:
            download = _downloads[dlid]
            if download.state != u"uploading":
                return
            del _downloads[dlid]
        finally:
            _lock.release()
    except (SystemExit, KeyboardInterrupt):
        raise
    except: # There is no download with this id
        return
    return download.pauseUpload()

def migrateDownload(dlid, directory):
    checkF(directory)
    try:
        download = _downloads[dlid]
    except (SystemExit, KeyboardInterrupt):
        raise
    except: # There is no download with this id
        pass
    else:
        if download.state in (u"finished", u"uploading", u"uploading-paused"):
            download.moveToDirectory(directory)

def getDownloadStatus(dlids = None):
    statuses = {}
    for key in _downloads.keys():
        if (dlids is None) or (dlids == key) or (key in dlids):
            try:
                statuses[key] = _downloads[key].getStatus()
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass
    return statuses

def shutDown():
    logging.info("Shutting down downloaders...")
    for dlid in _downloads:
        _downloads[dlid].shutdown()
    torrentSession.shutdown()

def restoreDownloader(downloader):
    downloader = copy(downloader)
    dlerType = downloader.get('dlerType')
    if dlerType == u'HTTP':
        dl = HTTPDownloader(restore = downloader)
    elif dlerType == u'BitTorrent':
        dl = BTDownloader(restore = downloader)
    else:
        err = u"in restoreDownloader(): unknown dlerType: %s" % dlerType
        c = command.DownloaderErrorCommand(daemon.lastDaemon, err)
        c.send()
        return

    _downloads[downloader['dlid']] = dl

class TorrentSession:
    """Contains the bittorrent session and handles updating all running bittorrents"""

    def __init__(self):
        self.torrents = set()
        self.info_hash_to_downloader = {}
        self.session = None
        self.pnp_on = None
        self.pe_set = None
        self.enc_req = None

    def startup(self):
        fingerprint = lt.fingerprint("MR", 1, 1, 0, 0)
        self.session = lt.session(fingerprint)
        self.listen()
        self.setUpnp()
        self.setUploadLimit()
        self.setDownloadLimit()
        self.setEncryption()
        config.add_change_callback(self.configChanged)

    def listen(self):
        self.session.listen_on(config.get(prefs.BT_MIN_PORT), config.get(prefs.BT_MAX_PORT))

    def setUpnp(self):
        useUpnp = config.get(prefs.USE_UPNP)
        if useUpnp != self.pnp_on:
            self.pnp_on = useUpnp
            if useUpnp:
                self.session.start_upnp()
            else:
                self.session.stop_upnp()

    def setUploadLimit(self):
        limit = -1
        if config.get(prefs.LIMIT_UPSTREAM):
            limit = config.get(prefs.UPSTREAM_LIMIT_IN_KBS)
            limit = limit * (2 ** 10)
            if limit > sys.maxint:
                limit = sys.maxint # avoid OverflowErrors by keeping the value
                                   # an integer
        self.session.set_upload_rate_limit(limit)

    def setDownloadLimit(self):
        limit = -1
        if config.get(prefs.LIMIT_DOWNSTREAM_BT):
            limit = config.get(prefs.DOWNSTREAM_BT_LIMIT_IN_KBS)
            limit = limit * (2 ** 10)
            if limit > sys.maxint:
                limit = sys.maxint # avoid OverflowErrors by keeping the value
                                   # an integer
        self.session.set_download_rate_limit(limit)

    def setConnectionLimit(self):
        limit = -1
        if config.get(prefs.LIMIT_CONNECTIONS_BT):
            limit = config.get(prefs.CONNECTION_LIMIT_BT_NUM)
            if limit > 65536:
                limit = 65536 # there are only 2**16 TCP port numbers
        self.session.set_max_connections(limit)

    def setEncryption(self):
        if self.pe_set is None:
            self.pe_set = lt.pe_settings()
        enc_req = config.get(prefs.BT_ENC_REQ)
        if enc_req != self.enc_req:
            self.enc_req = enc_req
            if enc_req:
                self.pe_set.in_enc_policy = lt.enc_policy.forced
                self.pe_set.out_enc_policy = lt.enc_policy.forced
            else:
                self.pe_set.in_enc_policy = lt.enc_policy.enabled
                self.pe_set.out_enc_policy = lt.enc_policy.enabled
            self.session.set_pe_settings(self.pe_set)

    def shutdown(self):
        config.remove_change_callback(self.configChanged)

    def configChanged(self, key, value):
        if key == prefs.BT_MIN_PORT.key:
            if value > self.session.listen_port():
                self.listen()
        elif key == prefs.BT_MAX_PORT.key:
            if value < self.session.listen_port():
                self.listen()
        elif key == prefs.USE_UPNP.key:
            self.setUpnp()
        elif key in (prefs.LIMIT_UPSTREAM.key, prefs.UPSTREAM_LIMIT_IN_KBS.key):
            self.setUploadLimit()
        elif key in (prefs.LIMIT_DOWNSTREAM_BT.key, prefs.DOWNSTREAM_BT_LIMIT_IN_KBS.key):
            self.setDownloadLimit()
        elif key == prefs.BT_ENC_REQ.key:
            self.setEncryption()
        elif key in (prefs.LIMIT_CONNECTIONS_BT.key, prefs.CONNECTION_LIMIT_BT_NUM.key):
            self.setConnectionLimit()

    def find_duplicate_torrent(self, torrent_info):
        info_hash = info_hash_to_long(torrent_info.info_hash())
        return self.info_hash_to_downloader.get(info_hash)

    def add_torrent(self, downloader):
        self.torrents.add(downloader)
        info_hash = info_hash_to_long(downloader.torrent.info_hash())
        self.info_hash_to_downloader[info_hash] = downloader

    def remove_torrent(self, downloader):
        if downloader in self.torrents:
            self.torrents.remove(downloader)
            info_hash = info_hash_to_long(downloader.torrent.info_hash())
            del self.info_hash_to_downloader[info_hash]

    def updateTorrents(self):
        # Copy this set into a list in case any of the torrents gets removed during the iteration.
        for torrent in [x for x in self.torrents]:
            torrent.update_status()

torrentSession = TorrentSession()

class DownloadStatusUpdater:
    """Handles updating status for all in progress downloaders.

    On OS X and gtk if the user is on the downloads page and has a bunch of
    downloads going, this can be a fairly CPU intensive task.
    DownloadStatusUpdaters mitigate this in 2 ways.

    1) DownloadStatusUpdater objects batch all status updates into one big
    update which takes much less CPU.  
    
    2) The update don't happen fairly infrequently (currently every 5 seconds).
    
    Because updates happen infrequently, DownloadStatusUpdaters should only be
    used for progress updates, not events like downloads starting/finishing.
    For those just call updateClient() since they are more urgent, and don't
    happen often enough to cause CPU problems.
    """

    UPDATE_CLIENT_INTERVAL = 2

    def __init__(self):
        self.toUpdate = set()

    def startUpdates(self):
        eventloop.addTimeout(self.UPDATE_CLIENT_INTERVAL, self.doUpdate,
                "Download status update")

    def doUpdate(self):
        try:
            torrentSession.updateTorrents()
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

RETRY_TIMES = (
    60,
    5 * 60,
    10 * 60,
    30 * 60,
    60 * 60,
    2 * 60 * 60,
    6 * 60 * 60,
    24 * 60 * 60
    )

class BGDownloader:
    def __init__(self, url, dlid):
        self.dlid = dlid
        self.url = url
        self.startTime = clock()
        self.endTime = self.startTime
        self.shortFilename = filenameFromURL(url)
        self.pickInitialFilename()
        self.state = u"downloading"
        self.currentSize = 0
        self.totalSize = -1
        self.blockTimes = []
        self.shortReasonFailed = self.reasonFailed = u"No Error"
        self.retryTime = None
        self.retryCount = -1

    def get_url(self):
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
            'dlerType': None,
            'retryTime': self.retryTime,
            'retryCount': self.retryCount,
            'channelName': self.channelName}

    def updateClient(self):
        x = command.UpdateDownloadStatus(daemon.lastDaemon, self.getStatus())
        return x.send()
        
    def pickInitialFilename(self, suffix=".part", torrent=False):
        """Pick a path to download to based on self.shortFilename.

        This method sets self.filename, as well as creates any leading paths
        needed to start downloading there.

        If the torrent flag is true, then the filename we're working with
        is utf-8 and shouldn't be transformed in any way.

        If the torrent flag is false, then the filename we're working with
        is ascii and needs to be transformed into something sane.  (default)
        """

        downloadDir = os.path.join(config.get(prefs.MOVIES_DIRECTORY),
                'Incomplete Downloads')
        # Create the download directory if it doesn't already exist.
        if not os.path.exists(downloadDir):
            fileutil.makedirs(downloadDir)
        filename = self.shortFilename + suffix
        if not torrent:
            # this is an ascii filename and needs to be fixed
            filename = cleanFilename(filename)
        self.filename = nextFreeFilename(os.path.join(downloadDir, filename))

    def moveToMoviesDirectory(self):
        """Move our downloaded file from the Incomplete Downloads directory to
        the movies directory.
        """
        if chatter:
            logging.info("moveToMoviesDirectory: filename is %s", self.filename)
        self.moveToDirectory(config.get(prefs.MOVIES_DIRECTORY))

    def moveToDirectory(self, directory):
        checkF(directory)
        if self.channelName:
            channelName = filterDirectoryName(self.channelName)
            # bug 10769: shutil and windows has problems with long filenames, so we clip
            # the directory name.
            if len(channelName) > 80:
                channelName = channelName[:80]
            directory = os.path.join(directory, channelName)
            try:
                fileutil.makedirs(directory)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass
        newfilename = os.path.join(directory, self.shortFilename)
        if newfilename == self.filename:
            return
        newfilename = nextFreeFilename(newfilename)
        def callback():
            self.filename = newfilename
            self.updateClient()
        fileutil.migrate_file(self.filename, newfilename, callback)

    ##
    # Returns a float with the estimated number of seconds left
    def getETA(self):
        if self.totalSize == -1:
            return -1
        rate = self.getRate()
        if rate > 0:
            return (self.totalSize - self.currentSize) / rate
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

    def retryDownload(self):
        self.retryDC = None
        self.start()

    def handleTemporaryError(self, shortReason, reason):
        self.state = u"offline"
        self.reasonFailed = reason
        self.shortReasonFailed = shortReason
        self.retryCount = self.retryCount + 1
        if self.retryCount >= len(RETRY_TIMES):
            self.retryCount = len(RETRY_TIMES) - 1
        self.retryDC = eventloop.addTimeout(RETRY_TIMES[self.retryCount], self.retryDownload, "Logarithmic retry")
        self.retryTime = datetime.datetime.now() + datetime.timedelta(seconds = RETRY_TIMES[self.retryCount])
        self.updateClient()

    def handleError(self, shortReason, reason):
        self.state = u"failed"
        self.reasonFailed = reason
        self.shortReasonFailed = shortReason
        self.updateClient()

    def handleNetworkError(self, error):
        if isinstance(error, httpclient.NetworkError):
            if (isinstance(error, httpclient.MalformedURL) or 
                    isinstance(error, httpclient.UnexpectedStatusCode)):
                self.handleError(error.getFriendlyDescription(),
                                 error.getLongDescription())
            else:
                self.handleTemporaryError(error.getFriendlyDescription(),
                                          error.getLongDescription())
        else:
            logging.info("WARNING: grabURL errback not called with NetworkError")
            self.handleError(str(error), str(error))

    def handleGenericError(self, longDescription):
        self.handleError(_("Error"), longDescription)

    ##
    # Checks the download file size to see if we can accept it based on the 
    # user disk space preservation preference
    def acceptDownloadSize(self, size):
        accept = True
        if config.get(prefs.PRESERVE_DISK_SPACE):
            if size < 0:
                size = 0
            preserved = config.get(prefs.PRESERVE_X_GB_FREE) * 1024 * 1024 * 1024
            available = get_available_bytes_for_movies() - preserved
            accept = (size <= available)
        return accept


class HTTPDownloader(BGDownloader):
    UPDATE_CLIENT_WINDOW = 12
    HALTED_THRESHOLD = 3 # how many secs until we consider a download halted

    def __init__(self, url = None, dlid = None, restore = None, expectedContentType = None):
        self.retryDC = None
        self.channelName = None
        self.expectedContentType = expectedContentType
        if restore is not None:
            if not isinstance(restore.get('totalSize', 0), int):
                # Sometimes restoring old downloaders caused errors because
                # their totalSize wasn't an int.  (see #3965)
                restore = None
        if restore is not None:
            self.__dict__.update(restore)
            self.blockTimes = []
            self.restartOnError = True
        else:
            BGDownloader.__init__(self, url, dlid)
            self.restartOnError = False
        self.client = None
        self.filehandle = None
        if self.state == 'downloading':
            self.startDownload()
        elif self.state == 'offline':
            self.start()
        else:
            self.updateClient()

    def resetBlockTimes(self):
        self.blockTimes = [(clock(), self.currentSize)]

    def startNewDownload(self):
        self.currentSize = 0
        self.totalSize = -1
        self.startDownload()

    def startDownload(self):
        if self.retryDC:
            self.retryDC.cancel()
            self.retryDC = None
        if self.currentSize == 0:
            headerCallback = self.onHeaders
        else:
            headerCallback = self.onHeadersRestart
        self.client = httpclient.grabURL(self.url,
                self.on_download_finished, self.onDownloadError,
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
        try:
            fileutil.remove(self.filename)
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            pass
        self.currentSize = 0
        self.totalSize = -1

    def handleTemporaryError(self, shortReason, reason):
        BGDownloader.handleTemporaryError(self, shortReason, reason)
        self.cancelRequest()

    def handleWriteError(self, error):
        text = (_("Could not write to %(filename)s") %
                {"filename": stringify(self.filename)})
        self.handleGenericError(text)
        if self.filehandle is not None:
            try:
                self.filehandle.close()
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass
        try:
            fileutil.remove(self.filename)
        except (SystemExit, KeyboardInterrupt):
            raise
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
                _("%(amount)s MB required to store this video") %
                  {"amount": self.totalSize / (2 ** 20)})
            return
        #We have a success
        self.retryCount = -1
        #Get the length of the file, then create it
        self.shortFilename = cleanFilename(info['filename'])
        if self.expectedContentType is not None:
            self.shortFilename = checkFilenameExtension(self.shortFilename, self.expectedContentType)
        else:
            self.shortFilename = checkFilenameExtension(self.shortFilename, info.get('content-type'))
        self.pickInitialFilename()
        try:
            self.filehandle = fileutil.open_file(self.filename,"w+b")
        except IOError:
            self.handleGenericError(_("Couldn't open %(filename)s for writing") % {"filename": stringify(self.filename)})
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
            if not self.client.gotBadStatusCode:
                self.onHeaders(info)
            else:
                self.cancelRequest()
                self.startNewDownload()
            return
        try:
            self.parseContentRange(info['content-range'])
        except ValueError:
            logging.info("WARNING, bad content-range: %r", info['content-range'])
            logging.info("currentSize: %d totalSize: %d", self.currentSize,
                          self.totalSize)
            self.cancelRequest()
            self.startNewDownload()
        else:
            try:
                self.filehandle = fileutil.open_file(self.filename,"r+b")
                self.filehandle.seek(self.currentSize)
            except IOError, e:
                self.handleWriteError(e)
            #We have a success
            self.retryCount = -1
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
            self.startDownload()
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

    def on_download_finished(self, response):
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
        self.resetBlockTimes()
        self.updateClient()

    def getStatus(self):
        data = BGDownloader.getStatus(self)
        data['dlerType'] = 'HTTP'
        return data

    ##
    # Update the download rate and eta based on receiving length bytes
    def updateRateAndETA(self, length):
        now = clock()
        self.currentSize = self.currentSize + length
        self.blockTimes.append((now,  self.currentSize))
        window_start = now - self.UPDATE_CLIENT_WINDOW
        i = 0
        for i in xrange(len(self.blockTimes)):
            if self.blockTimes[0][0] >= window_start:
                break
        self.blockTimes = self.blockTimes[i:]

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
                    fileutil.remove(self.filename)
                except (SystemExit, KeyboardInterrupt):
                    raise
                except:
                    pass
        if delete:
            try:
                if fileutil.isdir(self.filename):
                    fileutil.rmtree(self.filename)
                else:
                    fileutil.remove(self.filename)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass
        self.currentSize = 0
        self.cancelRequest()
        self.state = "stopped"
        self.updateClient()

    def stopUpload(self):
        # HTTP downloads never upload.
        pass

    ##
    # Continues a paused or stopped download thread
    def start(self):
        if self.state in ('paused', 'stopped', 'offline'):
            self.state = "downloading"
            self.startDownload()

    def shutdown(self):
        self.cancelRequest()
        self.updateClient()

class BTDownloader(BGDownloader):
    def __init__(self, url = None, item = None, restore = None):
        self.metainfo = None
        self.torrent = None
        self.rate = self.eta = 0
        self.upRate = self.uploaded = 0
        self.activity = None
        self.fastResumeData = None
        self.retryDC = None
        self.channelName = None
        self.uploadedStart = 0
        self.restarting = False
        self.seeders = -1
        self.leechers = -1
        if restore is not None:
            self.firstTime = False
            self.restoreState(restore)
        else:
            self.firstTime = True
            BGDownloader.__init__(self,url,item)
            self.run_downloader()

    def _startTorrent(self):
        try:
            torrent_info = lt.torrent_info(lt.bdecode(self.metainfo))
            duplicate = torrentSession.find_duplicate_torrent(torrent_info)
            if duplicate is not None:
                c = command.DuplicateTorrent(daemon.lastDaemon,
                        duplicate.dlid, self.dlid)
                c.send()
                return
            self.totalSize = torrent_info.total_size()

            if self.firstTime and not self.acceptDownloadSize(self.totalSize):
                self.handleError(_("Not enough disk space"),
                                 _("%(amount)s MB required to store this video") % {"amount": self.totalSize / (2 ** 20)})
                return

            save_path = os.path.dirname(fileutil.expand_filename(self.filename))
            if self.fastResumeData:
                self.torrent = torrentSession.session.add_torrent(torrent_info, save_path, lt.bdecode(self.fastResumeData), lt.storage_mode_t.storage_mode_allocate)
                self.torrent.resume()
            else:
                self.torrent = torrentSession.session.add_torrent(torrent_info, save_path, None, lt.storage_mode_t.storage_mode_allocate)
            try:
                if (lt.version_major, lt.version_minor) > (0, 13):
                    logging.debug("libtorrent version is (%d, %d), setting auto_managed to False", lt.version_major, lt.version_minor)
                    self.torrent.auto_managed(False)
            except AttributeError:
                logging.warning("libtorrent module doesn't have version_major or version_minor")
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            self.handleError(_('BitTorrent failure'), _('BitTorrent failed to startup'))
            logging.exception("Exception thrown in _startTorrent")
        else:
            torrentSession.add_torrent(self)

    def _shutdownTorrent(self):
        try:
            torrentSession.remove_torrent(self)
            if self.torrent is not None:
                self.torrent.pause()
                self.fastResumeData = lt.bencode(self.torrent.write_resume_data())
                torrentSession.session.remove_torrent(self.torrent, 0)
                self.torrent = None
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("Error shutting down torrent")

    def _pauseTorrent(self):
        try:
            torrentSession.remove_torrent(self)
            if self.torrent is not None:
                self.torrent.pause()
        except (SystemExit, KeyboardInterrupt):
            raise
        except:
            logging.exception("Error pausing torrent")

    def _resumeTorrent(self):
        if self.torrent is not None:
            try:
                self.torrent.resume()
                torrentSession.add_torrent(self)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                logging.exception("Error resuming torrent")
        else:
            self._startTorrent()

    def update_status(self):
        """
        activity -- string specifying what's currently happening or None for
                normal operations.  
        upRate -- upload rate in B/s
        downRate -- download rate in B/s
        upTotal -- total MB uploaded
        downTotal -- total MB downloaded
        fractionDone -- what portion of the download is completed.
        timeEst -- estimated completion time, in seconds.
        totalSize -- total size of the torrent in bytes
        """

        status = self.torrent.status()
        self.totalSize = status.total_wanted
        self.rate = status.download_payload_rate
        self.upRate = status.upload_payload_rate
        self.uploaded = status.total_payload_upload + self.uploadedStart
        self.seeders = status.num_complete
        self.leechers = status.num_incomplete
        try:
            self.eta = (status.total_wanted - status.total_wanted_done) / float(status.download_payload_rate)
        except ZeroDivisionError:
            self.eta = 0
        if status.state == lt.torrent_status.states.queued_for_checking:
            self.activity = "waiting to check existing files"
        elif status.state == lt.torrent_status.states.checking_files:
            self.activity = "checking existing files"
        elif status.state == lt.torrent_status.states.allocating:
            self.activity = "allocating disk space"
        else:
            self.activity = None
        self.currentSize = status.total_wanted_done
        if self.state == "downloading" and status.state == lt.torrent_status.states.seeding:
            self.moveToMoviesDirectory()
            self.state = "uploading"
            self.endTime = clock()
            self.updateClient()
        else:
            downloadUpdater.queueUpdate(self)

        if config.get(prefs.LIMIT_UPLOAD_RATIO):
            if status.state == lt.torrent_status.states.seeding:
                if float(self.uploaded)/self.totalSize > config.get(prefs.UPLOAD_RATIO):
                    self.stopUpload()

    def handleError(self, shortReason, reason):
        self._shutdownTorrent()
        BGDownloader.handleError(self, shortReason, reason)

    def handleTemporaryError(self, shortReason, reason):
        self._shutdownTorrent()
        BGDownloader.handleTemporaryError(self, shortReason, reason)

    def moveToDirectory(self, directory):
        if self.state in ('uploading', 'downloading'):
            self._shutdownTorrent()
            BGDownloader.moveToDirectory(self, directory)
            self._resumeTorrent()
        else:
            BGDownloader.moveToDirectory(self, directory)

    def restoreState(self, data):
        self.__dict__.update(data)
        self.rate = self.eta = 0
        self.upRate = 0
        self.uploadedStart = self.uploaded
        if self.state in ('downloading', 'uploading'):
            self.run_downloader(done=True)
        elif self.state == 'offline':
            self.start()

    def getStatus(self):
        data = BGDownloader.getStatus(self)
        data['upRate'] = self.upRate
        data['uploaded'] = self.uploaded
        data['metainfo'] = self.metainfo
        data['fastResumeData'] = self.fastResumeData
        data['activity'] = self.activity
        data['dlerType'] = 'BitTorrent'
        data['seeders'] = self.seeders
        data['leechers'] = self.leechers
        return data

    def getRate(self):
        return self.rate

    def getETA(self):
        return self.eta
        
    def pause(self):
        self.state = "paused"
        self.restarting = True
        self._pauseTorrent()
        self.updateClient()

    def stop(self, delete):
        self.state = "stopped"
        self._shutdownTorrent()
        self.updateClient()
        if delete:
            try:
                if fileutil.isdir(self.filename):
                    fileutil.rmtree(self.filename)
                else:
                    fileutil.remove(self.filename)
            except (SystemExit, KeyboardInterrupt):
                raise
            except:
                pass

    def stopUpload(self):
        self.state = "finished"
        self._shutdownTorrent()
        self.updateClient()

    def pauseUpload(self):
        self.state = "uploading-paused"
        self._shutdownTorrent()
        self.updateClient()

    def start(self):
        if self.state not in ('paused', 'stopped', 'offline'):
            return

        self.state = "downloading"
        if self.retryDC:
            self.retryDC.cancel()
            self.retryDC = None
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
            try:
                metainfo = lt.bdecode(self.metainfo)
                # if we don't get valid torrent metadata back, then the
                # metainfo is None.  treat that like a runtime error.
                if not metainfo:
                    raise RuntimeError()
                name = metainfo['info']['name']
            except RuntimeError:
                self.handleError(_("Corrupt Torrent"),
                                 _("The torrent file at %(url)s was not valid") % {"url": stringify(self.url)})
                return
            self.shortFilename = utf8_to_filename(name)
            self.pickInitialFilename(suffix="", torrent=True)
        self.updateClient()
        self._resumeTorrent()

    def handleMetainfo(self, metainfo):
        self.metainfo = metainfo
        self.gotMetainfo()

    def onDescriptionDownload(self, info):
        self.handleMetainfo(info['body'])

    def onDescriptionDownloadFailed(self, exception):
        self.handleNetworkError(exception)

    def getMetainfo(self):
        if self.metainfo is None:
            if self.url.startswith('file://'):
                path = getFileURLPath(self.url)
                try:
                    metainfoFile = open(path, 'rb')
                except IOError:
                    self.handleError(_("Torrent file deleted"),
                                     _("The torrent file for this item was deleted "
                                       "outside of %(appname)s.",
                                       {"appname": config.get(prefs.SHORT_APP_NAME)}
                                       ))

                    return
                try:
                    metainfo = metainfoFile.read()
                finally:
                    metainfoFile.close()

                self.handleMetainfo(metainfo)
            else:
                httpclient.grabURL(self.get_url(), self.onDescriptionDownload,
                        self.onDescriptionDownloadFailed)
        else:
            self.gotMetainfo()
                
    def run_downloader(self, done=False):
        self.restarting = done
        self.updateClient()
        self.getMetainfo()
