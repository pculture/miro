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

from download_utils import cleanFilename, nextFreeFilename, shortenFilename
import eventloop
import httpclient

import config
import prefs
from BitTornado import mapbase64, createPeerID
from BitTornado.RawServer import RawServer, autodetect_socket_style
from BitTornado.RateLimiter import RateLimiter
from BitTornado.ServerPortHandler import MultiHandler
from BitTornado.natpunch import UPnP_test
from BitTornado.bencode import bdecode, bencode
from BitTornado.launchmanycore import SingleDownload
from BitTornado.parseargs import defaultargs
from BitTornado.clock import clock
from sha import sha

from dl_daemon import command, daemon

import platformutils

# This pattern matches all possible strings.  I promise.
URIPattern = re.compile(r'^([^?]*/)?([^/?]*)/*(\?(.*))?$')

chatter = True

# a hash of download ids to downloaders
_downloads = {}

# BitTornado defaults
defaults = [
    ('max_uploads', 7,
        "the maximum number of uploads to allow at once."),
    ('keepalive_interval', 120.0,
        'number of seconds to pause between sending keepalives'),
    ('download_slice_size', 2 ** 14,
        "How many bytes to query for per request."),
    ('upload_unit_size', 1460,
        "when limiting upload rate, how many bytes to send at a time"),
    ('request_backlog', 10,
        "maximum number of requests to keep in a single pipe at once."),
    ('max_message_length', 2 ** 23,
        "maximum length prefix encoding you'll accept over the wire - larger values get the connection dropped."),
    ('ip', '',
        "ip to report you have to the tracker."),
    ('minport', 10000, 'minimum port to listen on, counts up if unavailable'),
    ('maxport', 60000, 'maximum port to listen on'),
    ('random_port', 1, 'whether to choose randomly inside the port range ' +
        'instead of counting up linearly'),
    ('responsefile', '',
        'file the server response was stored in, alternative to url'),
    ('url', '',
        'url to get file from, alternative to responsefile'),
    ('selector_enabled', 1,
        'whether to enable the file selector and fast resume function'),
    ('expire_cache_data', 10,
        'the number of days after which you wish to expire old cache data ' +
        '(0 = disabled)'),
    ('priority', '',
        'a list of file priorities separated by commas, must be one per file, ' +
        '0 = highest, 1 = normal, 2 = lowest, -1 = download disabled'),
    ('saveas', '',
        'local file name to save the file as, null indicates query user'),
    ('timeout', 300.0,
        'time to wait between closing sockets which nothing has been received on'),
    ('timeout_check_interval', 60.0,
        'time to wait between checking if any connections have timed out'),
    ('max_slice_length', 2 ** 17,
        "maximum length slice to send to peers, larger requests are ignored"),
    ('max_rate_period', 20.0,
        "maximum amount of time to guess the current rate estimate represents"),
    ('bind', '', 
        'comma-separated list of ips/hostnames to bind to locally'),
#    ('ipv6_enabled', autodetect_ipv6(),
    ('ipv6_enabled', 0,
         'allow the client to connect to peers via IPv6'),
    ('ipv6_binds_v4', autodetect_socket_style(),
        'set if an IPv6 server socket will also field IPv4 connections'),
    ('upnp_nat_access', 1,
        'attempt to autoconfigure a UPnP router to forward a server port ' +
        '(0 = disabled, 1 = mode 1 [fast], 2 = mode 2 [slow])'),
    ('upload_rate_fudge', 5.0, 
        'time equivalent of writing to kernel-level TCP buffer, for rate adjustment'),
    ('tcp_ack_fudge', 0.03,
        'how much TCP ACK download overhead to add to upload rate calculations ' +
        '(0 = disabled)'),
    ('display_interval', .5,
        'time between updates of displayed information'),
    ('rerequest_interval', 5 * 60,
        'time to wait between requesting more peers'),
    ('min_peers', 20, 
        'minimum number of peers to not do rerequesting'),
    ('http_timeout', 60, 
        'number of seconds to wait before assuming that an http connection has timed out'),
    ('max_initiate', 40,
        'number of peers at which to stop initiating new connections'),
    ('check_hashes', 1,
        'whether to check hashes on disk'),
    ('max_upload_rate', -1,
        'maximum kB/s to upload at (0 = no limit, -1 = automatic)'),
    ('max_download_rate', 0,
        'maximum kB/s to download at (0 = no limit)'),
    ('alloc_type', 'pre-allocate',
        'allocation type (may be normal, background, pre-allocate or sparse)'),
    ('alloc_rate', 2.0,
        'rate (in MiB/s) to allocate space at using background allocation'),
    ('buffer_reads', 1,
        'whether to buffer disk reads'),
    ('write_buffer_size', 4,
        'the maximum amount of space to use for buffering disk writes ' +
        '(in megabytes, 0 = disabled)'),
    ('snub_time', 30.0,
        "seconds to wait for data to come in over a connection before assuming it's semi-permanently choked"),
    ('spew', 0,
        "whether to display diagnostic info to stdout"),
    ('rarest_first_cutoff', 2,
        "number of downloads at which to switch from random to rarest first"),
    ('rarest_first_priority_cutoff', 5,
        'the number of peers which need to have a piece before other partials take priority over rarest first'),
    ('min_uploads', 4,
        "the number of uploads to fill out to with extra optimistic unchokes"),
    ('max_files_open', 50,
        'the maximum number of files to keep open at a time, 0 means no limit'),
    ('round_robin_period', 30,
        "the number of seconds between the client's switching upload targets"),
    ('super_seeder', 0,
        "whether to use special upload-efficiency-maximizing routines (only for dedicated seeds)"),
    ('security', 1,
        "whether to enable extra security features intended to prevent abuse"),
    ('max_connections', 0,
        "the absolute maximum number of peers to connect with (0 = no limit)"),
    ('auto_kick', 1,
        "whether to allow the client to automatically kick/ban peers that send bad data"),
    ('double_check', 1,
        "whether to double-check data being written to the disk for errors (may increase CPU load)"),
    ('triple_check', 0,
        "whether to thoroughly check data being written to the disk (may slow disk access)"),
    ('lock_files', 1,
        "whether to lock files the client is working with"),
    ('lock_while_reading', 0,
        "whether to lock access to files being read"),
    ('auto_flush', 0,
        "minutes between automatic flushes to disk (0 = disabled)"),
    ]

btconfig = defaultargs(defaults)

#FIXME: check for free space and failed connection to tracker and fail
#on those cases

#FIXME: Trigger pending Manual Download in item when if we run out of disk space

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
    shutdownBTDownloader()

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

class BGDownloader:
    def __init__(self, url, dlid):
        self.dlid = dlid
        self.url = url
        self.startTime = clock()
        self.endTime = self.startTime
        self.shortFilename = self.filenameFromURL(url)
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
    # Returns a reasonable filename for saving the given url
    def filenameFromURL(self, url):
        try:
            match = URIPattern.match(url)
            if match is None:
                # This code path will never be executed.
                return cleanFilename(url)
            filename = match.group(2)
            query = match.group(4)
            if not filename:
                ret = query
            elif not query:
                ret = filename
            else:
                ret = "%s-%s" % (filename, query)
            if ret is None:
                ret = 'unknown'
            return cleanFilename(ret)
        except:
            return 'unknown'

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
    UPDATE_CLIENT_INTERVAL = 3
    UPDATE_CLIENT_WINDOW = 6
    HALTED_THRESHOLD = 3 # how many secs until we consider a download halted

    def __init__(self, url = None,dlid = None,restore = None):
        if restore is not None:
            self.__dict__ = copy(restore)
            self.blockTimes = []
            self.restartOnError = True
        else:
            BGDownloader.__init__(self, url, dlid)
            self.restartOnError = False
        self.lastUpdated = 0
        self.client = None
        self.filehandle = None
        self.timeout = None
        if self.state == 'downloading':
            if restore is not None:
                self.startDownload()
            else:
                self.startNewDownload()
        else:
            self.updateClient()

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
        self.blockTimes = [(clock(), self.currentSize)]
        self.updateClient()
        self.startTimeout()

    def startTimeout(self):
        self.cancelTimeout()
        self.timeout = eventloop.addTimeout(self.UPDATE_CLIENT_INTERVAL,
                lambda: self.updateRateAndETA(0), "update rate")

    def cancelTimeout(self):
        if self.timeout:
            self.timeout.cancel()
            self.timeout = None

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
                self.totalSize / (2 ** 20))
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
        self.cancelTimeout()
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
        try:
            self.filehandle.write(data)
        except IOError, e:
            self.handleWriteError(e)
        self.startTimeout()

    def onDownloadFinished(self, response):
        self.cancelTimeout()
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
        data['lastUpdated'] = self.lastUpdated
        data['dlerType'] = 'HTTP'
        return data

    ##
    # Update the download rate and eta based on recieving length bytes
    def updateRateAndETA(self,length):
        now = clock()
        self.currentSize = self.currentSize + length
        if self.lastUpdated <= now - self.UPDATE_CLIENT_INTERVAL:
            self.blockTimes.append((now,  self.currentSize))
            while (len(self.blockTimes) > 0 and 
                    now - self.blockTimes[0][0] > self.UPDATE_CLIENT_WINDOW):
                self.blockTimes.pop(0)
            self.lastUpdated = now
            self.updateClient()
        
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

##
# BitTorrent uses this class to display status information. We use
# it to update Downloader information
#
# We use the rate and ETA provided by BitTorrent rather than
# calculating our own.
class BTDisplay:
    ##
    # Takes in the downloader class associated with this display
    def __init__(self,dler):
        self.dler = dler
        self.lastUpTotal = 0
        self.lastUpdated = 0

    def finished(self):
        self.dler.updateClient()
        state = self.dler.state
        if not (state == "uploading" or
                state == "finished"):
            self.dler.moveToMoviesDirectory()
            self.dler.state = "uploading"
            self.dler.endTime = clock()
            if self.dler.endTime - self.dler.startTime != 0:
                self.dler.rate = self.dler.totalSize/(self.dler.endTime-self.dler.startTime)
            self.dler.currentSize =self.dler.totalSize
        self.lastUpdated = clock()
        self.dler.updateClient()

    def handleBitTorrentError(self, errorMessage):
        if "problem connecting to the tracker" in errorMessage.lower():
            shortReason = _("Can't connect")
        else:
            shortReason = _("Error")
        self.handleError(shortReason, errorMessage)
            
    def display(self, statistics):
        update = False
        now = clock()
        if statistics['errorTime'] != 0:
            self.handleBitTorrentError(statistics['errorMessage'])
        if statistics.get('upTotal') != None:
            if self.lastUpTotal > statistics.get('upTotal'):
                self.dler.uploaded += statistics.get('upTotal')
            else:
                self.dler.uploaded += statistics.get('upTotal') - self.lastUpTotal
            self.lastUpTotal = statistics.get('upTotal')
        if self.dler.state != "paused":
            self.dler.currentSize = int(self.dler.totalSize*statistics.get('fractionDone'))
        if self.dler.state != "finished" and self.dler.state != "uploading":
            self.dler.rate = statistics.get('downRate')
        if self.dler.rate == None:
            self.dler.rate = 0.0
        self.dler.eta = statistics.get('timeEst')
        if self.dler.eta == None:
            self.dler.eta = 0
        if (self.dler.state == "uploading" and
            self.dler.uploaded >= 1.5*self.dler.totalSize):
            self.dler.state = "finished"
            self.dler.torrent.shutdown()
        if self.dler.state == "downloading" and statistics.get('fractionDone') == 1.0:
            self.finished()
        else:
            if self.lastUpdated < now-3:
                update = True
                self.lastUpdated = now
            if update:
                self.dler.updateClient()

class BTDownloader(BGDownloader):
    def bt_failure(text):
        print "BitTornado error: %s" % text
    def bt_exception(text):
        print "BitTornado exception: %s" % text

    doneflag = Event()
    rawserver = RawServer(doneflag, btconfig['timeout_check_interval'],
                          btconfig['timeout'],
                          ipv6_enable = btconfig['ipv6_enabled'],
                          failfunc = bt_failure, errorfunc = bt_exception)
    upnp_type = UPnP_test(btconfig['upnp_nat_access'])
    #Spawn the download thread
    listen_port = rawserver.find_and_bind(
        btconfig['minport'], btconfig['maxport'], btconfig['bind'],
        ipv6_socket_style = btconfig['ipv6_binds_v4'],
        upnp = upnp_type, randomizer = btconfig['random_port'])
    ratelimiter = None
#     ratelimiter = RateLimiter(rawserver.add_task,
#                               btconfig['upload_unit_size'])
#     ratelimiter.set_upload_rate(btconfig['max_upload_rate'])
    handler = MultiHandler(rawserver, doneflag)
    counter = 0

    def __init__(self, url = None, item = None, restore = None):
        if restore is not None:
            self.restoreState(restore)
        else:            
            self.metainfo = None
            self.infohash = None
            self.rate = 0
            self.eta = 0
            self.d = BTDisplay(self)
            self.uploaded = 0
            self.torrent = None
            BGDownloader.__init__(self,url,item)
            self.runDownloader()

    def _shutdownTorrent(self):
        try:
            self.torrent.shutdown()
        except:
            print "DTV: Warning: Shutting down non-existent torrent"

    def _startTorrent(self):
        # Get a number and convert it to base64, then make a peerid from that
        c = BTDownloader.counter
        BTDownloader.counter += 1
        x = ''
        for i in xrange(3):
            x = mapbase64[c & 0x3F]+x
            c >>= 6
        peer_id = createPeerID(x)

        self.torrent = SingleDownload(self, self.infohash, self.metainfo, btconfig, peer_id)
        self.torrent.start()
        self.rawserver.add_task(self.get_status,0)
        self.rawserver.wakeup()

    def _getTorrentStatus(self):
        downRate = 0.0
        timeEst = 0
        fractionDone = 0.0
        upTotal = 0
        errorTime = 0
        errorMessage = ""
        
        if not (self.torrent.is_dead() or self.torrent.waiting or
                self.torrent.checking):
            errorTime = self.torrent.status_errtime
            try:
                errorMessage = self.torrent.status_err[-1]
            except IndexError:
                pass
            # BitTornado keeps status all over the place. Joy!
            stats = self.torrent.statsfunc()
            s = stats['stats']
            upRate = stats['up']
            if self.torrent.seed:
                fractionDone = 1.0
                upTotal = s.upTotal
            else:
                fractionDone = stats['frac']
                downRate = stats['down']
                timeEst = stats['time']
                upTotal = s.upTotal
                   
        return {'downRate':downRate, 'timeEst':timeEst,
                'fractionDone': fractionDone, 'upTotal': upTotal, 
                'errorTime': errorTime, 'errorMessage': errorMessage}

    def moveToDirectory(self, directory):
        if self.state in ('uploading', 'downloading'):
            self._shutdownTorrent()
            BGDownloader.moveToDirectory(self, directory)
            self._startTorrent()
        else:
            BGDownloader.moveToDirectory(self, directory)

    def restoreState(self, data):
        self.__dict__ = data
        self.blockTimes = []
        self.d = BTDisplay(self)
        if self.state == 'downloading' or (
            self.state not in ['paused','stopped'] and
            self.uploaded < 1.5*self.totalSize):
            self.restartDL ()

    def getStatus(self):
        data = BGDownloader.getStatus(self)
        data['metainfo'] = self.metainfo
        data['infohash'] = self.infohash
        data['dlerType'] = 'BitTorrent'
        return data

    def getRate(self):
        return self.rate

    def getETA(self):
        return self.eta
        
    def pause(self):
        self.state = "paused"
        self.updateClient()
        try:
            self._shutdownTorrent()
        except KeyError:
            pass
        except AttributeError:
            pass

    def stop(self, delete):
        self.state = "stopped"
        self.updateClient()
        self._shutdownTorrent()
        if delete:
            try:
                if os.path.isdir(self.filename):
                    shutil.rmtree(self.filename)
                else:
                    remove(self.filename)
            except:
                pass

    def start(self):
        self.pause()
        metainfo = self.metainfo
        if metainfo is None:
            msg = _("Could not read BitTorrent metadata")
            self.handleGenericError(msg)
            self.state = "failed"
        else:
            self.state = "downloading"
        self.updateClient()
        if metainfo is not None:
            self._startTorrent()

    def shutdown(self):
        try:
            self._shutdownTorrent()
        except KeyError:
            pass
        except AttributeError:
            pass
        self.updateClient()

    def readMetainfo (self, metainfo):
        # FIXME: BitTorrent did lots of checking here for
        # invalid torrents. We should do the same
        self.metainfo = bdecode(metainfo)
        info = self.metainfo['info']
        self.infohash = sha(bencode(info)).digest()
        self.shortFilename = cleanFilename(self.metainfo['info']['name'])
        
        try:
            totalSize = self.metainfo['info']['length']
        except KeyError: # There are multiple files in this here torrent
            totalSize = 0
            for f in self.metainfo['info']['files']:
                totalSize += f['length']
        self.totalSize = totalSize

    def gotMetainfo(self):
        # FIXME: If the client is stopped before a BT download gets
        #        its metadata, we never run this. It's not a huge deal
        #        because it only affects the incomplete filename
        if not self.restarting:
            self.pickInitialFilename()
        self.updateClient()
        self._startTorrent()

    def handleMetainfo (self, metainfo):
        try:
            self.readMetainfo(metainfo)
        except ValueError:
            self.handleGenericError(_("Invalid BitTorrent metadata"))
            self.state = "failed"
            self.updateClient()
        else:
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

    def restartDL(self):
        self.runDownloader(done = True)
            
    def get_status(self):
        """run by the bittorrent server"""
        #print str(self.getID()) + ": "+str(self.metainfo.infohash).encode('hex')
        if not self.torrent.is_dead():
            self.rawserver.add_task(self.get_status,
                                    btconfig['display_interval'])
        status = self._getTorrentStatus()
        self.d.display(status)

    # Functions below this point are BitTornado SingleDownload
    # controller functions

    # These provide a queue for scheduling hash checks
    def hashchecksched(self, hash = None):
        if hash:
            try:
                self.hashcheck_queue.append(hash)
            except:
                self.hashcheck_queue = [hash]
        if not (hasattr(self,'hashcheck_current') and self.hashcheck_current):
            self._hashcheck_start()
    def _hashcheck_start(self):
        self.hashcheck_current = self.hashcheck_queue.pop(0)
        self.torrent.hashcheck_start(self.hashcheck_callback)
    def hashcheck_callback(self):
        self.torrent.hashcheck_callback()
        if (hasattr(self,'hashcheck_queue') and self.hashcheck_queue):
            self._hashcheck_start()
        else:
            self.hashcheck_current = None

    def saveAs(self, hash, name, saveas, isdir):
        if isdir and not os.path.isdir(self.filename):
            try:
                os.mkdir(self.filename)
            except:
                raise OSError("couldn't create directory for "+self.filename)
        return self.filename

    def was_stopped(self, hash):
        pass
        #print "DTV: Got 'was_stopped()' for %s" % self.shortFilename
    def died(self, hash):
        pass
        #print "DTV: Got 'died' for %s" % self.shortFilename
    def exchandler(self, error):
        print "DTV: BitTornado error %s" % error

##
# Kill the main BitTornado thread
#
# This should be called before closing the app
def shutdownBTDownloader():
    BTDownloader.doneflag.set()
    BTDownloader.rawserver.wakeup()
    BTDownloader.dlthread.join()

def updateBTConfig(key, value):
    if key in [prefs.LIMIT_UPSTREAM.key, prefs.UPSTREAM_LIMIT_IN_KBS.key]:
        if config.get(prefs.LIMIT_UPSTREAM):
            btconfig['max_upload_rate'] = config.get(prefs.UPSTREAM_LIMIT_IN_KBS)
        else:
            btconfig['max_upload_rate'] = -1
    if key == prefs.BT_MIN_PORT.key:
        btconfig['minport'] = config.get(prefs.BT_MIN_PORT)
    if key == prefs.BT_MAX_PORT.key:
        btconfig['maxport'] = config.get(prefs.BT_MAX_PORT)

def startBTDownloader():
    if config.get(prefs.LIMIT_UPSTREAM):
        btconfig['max_upload_rate'] = config.get(prefs.UPSTREAM_LIMIT_IN_KBS)
    else:
        btconfig['max_upload_rate'] = -1
    btconfig['minport'] = config.get(prefs.BT_MIN_PORT)
    btconfig['maxport'] = config.get(prefs.BT_MAX_PORT)
    config.addChangeCallback (updateBTConfig)
    BTDownloader.dlthread = Thread(target=BTDownloader.handler.listen_forever)
    BTDownloader.dlthread.setName("bittornado downloader")
    BTDownloader.dlthread.start()
