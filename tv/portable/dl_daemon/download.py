import os
import sys
import bsddb
import random
import types
from os import remove, rename, access, F_OK
from threading import RLock, Event, Thread
from time import sleep, time
from copy import copy

from download_utils import grabURL, cleanFilename, parseURL

import config
from BitTorrent import configfile
from BitTorrent.download import Feedback, Multitorrent
from BitTorrent.defaultargs import get_defaults
from BitTorrent.parseargs import parseargs, printHelp
from BitTorrent.bencode import bdecode
from BitTorrent.ConvertedMetainfo import ConvertedMetainfo
from BitTorrent import configfile
from BitTorrent import BTFailure, CRITICAL
from BitTorrent import version

from dl_daemon import command, daemon

# a hash of download ids to downloaders
_downloads = {}
# a hash of URLs to downloaders
_downloads_by_url = {}

defaults = get_defaults('btdownloadheadless')
defaults.extend((('donated', '', ''),))

#FIXME: check for free space and failed connection to tracker and fail
#on those cases

#FIXME: Trigger pending Manual Download in item when if we run out of disk space

_lock = RLock()

def findHTTPAuth(*args, **kws):
    x = command.FindHTTPAuthCommand(daemon.lastDaemon, *args, **kws)
    return x.send(block = True, retry = True)

def generateDownloadID():
    _lock.acquire()
    try:
        dlid = "download%08d" % random.randint(0,99999999)
        while _downloads.has_key(dlid):
            dlid = "download%08d" % random.randint(0,99999999)
    finally:
        _lock.release()
    return dlid

def createDownloader(url, contentType, dlid):
    if contentType == 'application/x-bittorrent':
        return BTDownloader(url, dlid)
    else:
        return HTTPDownloader(url, dlid)

# Creates a new downloader object. Returns id on success, None on failure
def startNewDownload(url, contentType):
    _lock.acquire()
    try:
        if _downloads_by_url.has_key(url):
            dlid = _downloads_by_url[url].dlid
        else:
            dlid = generateDownloadID()
            dl = createDownloader(url, contentType, dlid)
            _downloads[dlid] = dl
            _downloads_by_url[url] = dl
    finally:
        _lock.release()
        return dlid

def pauseDownload(dlid):
    try:
        download = _downloads[dlid]
    except: # There is no download with this id
        return True
    return download.pause()

def startDownload(dlid):
    try:
        download = _downloads[dlid]
    except: # There is no download with this id
        return True
    return download.start()

def stopDownload(dlid):
    try:
        _lock.acquire()
        try:
            download = _downloads[dlid]
            del _downloads[dlid]
            # A download may be referred to by multiple ids
            if not download in _downloads:
                del _downloads_by_url[download.url]
        finally:
            _lock.release()
    except: # There is no download with this id
        return True
    return download.stop()

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
        _downloads[dlid].pause()
    shutdownBTDownloader()

def restoreDownloader(downloader):
    # changes to the downloader's dict shouldn't affect this
    downloader = copy(downloader)

    dlerType = downloader.get('dlerType')
    if dlerType == 'HTTP':
        dl = HTTPDownloader(restore = downloader)
    elif dlerType == 'BitTorrent':
        dl = BTDownloader(restore = downloader)
    else:
        print "WARNING dlerType %s not recognized" % dlerType
        dl = createDownloader(downloader['url'], downloader['contentType'],
                downloader['dlid'])
        print "created new downloader: %s" % dl

    _downloads[downloader['dlid']] = dl
    _downloads_by_url[downloader['url']] = dl

class BGDownloader:
    def __init__(self, url, dlid):
        self.dlid = dlid
        self.url = url
        self.startTime = time()
        self.endTime = self.startTime
        self.shortFilename = self.filenameFromURL(url)
        self.pickInitialFilename()
        self.state = "downloading"
        self.currentSize = 0
        self.totalSize = -1
        self.blockTimes = []
        self.reasonFailed = "No Error"
        self.headers = None
        self.thread = Thread(target=self.runDownloader, \
                             name="downloader -- %s" % self.shortFilename)
        self.thread.setDaemon(False)
        self.thread.start()

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
            'shortFilename': self.shortFilename,
            'reasonFailed': self.reasonFailed,
            'dlerType': None }

    def updateClient(self):
        x = command.UpdateDownloadStatus(daemon.lastDaemon, self.getStatus())
        return x.send(block = False, retry = False)
        
    ##
    # Returns a reasonable filename for saving the given url
    def filenameFromURL(self,url):
        (scheme, host, path, params, query, fragment) = parseURL(url)
        if len(path):
            try:
                ret = re.compile("^.*?([^/]+)/?$").search(path).expand("\\1")
                return cleanFilename(ret)

            except:
                return 'unknown'
        else:
            return "unknown"

    ##
    # Finds a filename that's unused and similar the the file we want
    # to download
    def nextFreeFilename(self, name):
        if not access(name,F_OK):
            return name
        parts = name.split('.')
        count = 1
        if len(parts) == 1:
            newname = "%s.%s" % (name, count)
            while access(newname,F_OK):
                count += 1
                newname = "%s.%s" % (name, count)
        else:
            insertPoint = len(parts)-1
            parts[insertPoint:insertPoint] = [str(count)]
            newname = '.'.join(parts)
            while access(newname,F_OK):
                count += 1
                parts[insertPoint] = str(count)
                newname = '.'.join(parts)
        return newname

    def pickInitialFilename(self):
        """Pick a path to download to based on self.shortFilename.

        This method sets self.filename, as well as creates any leading paths
        needed to start downloading there.
        """

        downloadDir = os.path.join(config.get(config.MOVIES_DIRECTORY),
                'Incomplete Downloads')
        # Create the download directory if it doesn't already exist.
        try:
            os.makedirs(downloadDir)
        except:
            pass
        baseFilename = os.path.join(downloadDir, self.shortFilename+".part")
        self.filename = self.nextFreeFilename(baseFilename)

    ##
    # Returns a float with the estimated number of seconds left
    def getETA(self):
        rate = self.getRate()
        if rate > 0:
            return (self.totalSize - self.currentSize)/rate
        else:
            return 0

    ##
    # Returns a float with the download rate in bytes per second
    def getRate(self):
        now = time()
        if self.endTime != self.startTime:
            rate = self.currentSize/(self.endTime-self.startTime)
        else:
            try:
                if (now-self.blockTimes[0][0]) != 0:
                    rate=(self.blockTimes[-1][1]-self.blockTimes[0][1])/(now-self.blockTimes[0][0])
                else:
                    rate = 0
            except IndexError:
                rate = 0
        return rate

class HTTPDownloader(BGDownloader):
    def __init__(self, url = None,dlid = None,restore = None):
        if restore is not None:
            self.restoreState(restore)
        else:
            self.lastUpdated = 0
            BGDownloader.__init__(self,url, dlid)

    def getStatus(self):
        data = BGDownloader.getStatus(self)
        data['lastUpdated'] = self.lastUpdated
        data['dlerType'] = 'HTTP'
        return data

    ##
    # Update the download rate and eta based on recieving length bytes
    def updateRateAndETA(self,length):
        now = time()
        updated = False
        self.currentSize = self.currentSize + length
        if self.lastUpdated < now-3:
            self.blockTimes.append((now,  self.currentSize))
            #Only keep the last 100 packets
            if len(self.blockTimes)>100:
                self.blockTimes.pop(0)
            updated = True
            self.lastUpdated = now
        if updated:
            self.updateClient()
        
    ##
    # Grabs the next block from the HTTP connection
    def getNextBlock(self,handle):
        state = self.state
        if (state == "paused") or (state == "stopped"):
            data = ""
        else:
            try:
                data = handle.read(1024)
            except:
                self.state = "failed"
                self.reasonFailed = "Lost connection to server"
                data = ""
        self.updateRateAndETA(len(data))
        return data

    ##
    # This is the actual download thread.
    def runDownloader(self, retry = False):
        if retry:
            pos = self.currentSize
            info = grabURL(self.url,"GET",pos, findHTTPAuth = findHTTPAuth)
            if info is None and pos > 0:
                pos = 0
                self.currentSize = 0
                info = grabURL(self.url,"GET", findHTTPAuth = findHTTPAuth)
            if info is None:
                self.state = "failed"
                self.reasonFailed = "Could not connect to server"
                return False
            try:
                filehandle = file(self.filename,"r+b")
                filehandle.seek(pos)
            except:
                #the file doesn't exist. Get the right filename and restart dl
                self.shortFilename = cleanFilename(info['filename'])
                self.pickInitialFilename()
                filehandle = file(self.filename,"w+b")
                self.currentSize = 0
                totalSize = self.totalSize
                pos = 0
                if totalSize > 0:
                    filehandle.seek(totalSize-1)
                    filehandle.write(' ')
                    filehandle.seek(0)            
        else:
            #print "We don't have any INFO..."
            info = grabURL(self.url,"GET", findHTTPAuth = findHTTPAuth)
            if info is None:
                self.state = "failed"
                self.reasonFailed = "Could not connect to server"
                return False

        if not retry:
            #get the filename to save to
            self.shortFilename = cleanFilename(info['filename'])
            self.pickInitialFilename()

            #Get the length of the file, then create it
            try:
                totalSize = int(info['content-length'])
            except KeyError:
                totalSize = -1
            self.totalSize = totalSize
            try:
                filehandle = file(self.filename,"w+b")
            except IOError:
                self.state = "failed"
                self.reasonFailed = "Could not write file to disk"
                return False
            self.currentSize = 0
            if not self.acceptDownloadSize(totalSize):
                self.state = "failed"
                self.reasonFailed = "Not enough free space"
                return False
            pos = 0
            if totalSize > 0:
                filehandle.seek(totalSize-1)
                filehandle.write(' ')
                filehandle.seek(0)

        #Download the file
        if pos != self.totalSize:
            data = self.getNextBlock(info['file-handle'])
            while len(data) > 0:
                filehandle.write(data)
                data = self.getNextBlock(info['file-handle'])
            filehandle.close()
            info['file-handle'].kill()

        #Update the status
        if self.state == "downloading":
            self.state = "finished"
            newfilename = os.path.join(config.get(config.MOVIES_DIRECTORY),self.shortFilename)
            newfilename = self.nextFreeFilename(newfilename)
            try:
                rename(self.filename,newfilename)
                self.filename = newfilename
            except:
                # Eventually we should make this bring up an error
                # dialog in the app
                print "Democracy: Warning: Couldn't rename \"%s\" to \"%s\"" %(
                    self.filename, newfilename)
            if self.totalSize == -1:
                self.totalSize = self.currentSize
            self.endTime = time()
            self.state = "finished"
        elif self.state == "stopped":
            try:
                remove(self.filename)
            except:
                pass
        self.updateClient()
 
    ##
    # Checks the download file size to see if we can accept it based on the 
    # user disk space preservation preference
    def acceptDownloadSize(self, size):
        print "WARNING: acceptDownloadSize is a stub"
        return True
        if config.get(config.PRESERVE_DISK_SPACE):
            sizeInGB = size / 1024 / 1024 / 1024
            if sizeInGB > platformutils.getAvailableGBytesForMovies() - config.get(config.PRESERVE_X_GB_FREE):
                self.state = "failed"
                self.reasonFailed = "File is too big"
                return False
        return True

    ##
    # Pauses the download.
    def pause(self):
        if self.state != "stopped":
            self.state = "paused"
            self.updateClient()

    ##
    # Stops the download and removes the partially downloaded
    # file.
    def stop(self):
        if self.state != "downloading":
            try:
                remove(self.filename)
            except:
                pass
        self.state = "stopped"
        self.updateClient()
        #FIXME: remove downloader from memory

    ##
    # Continues a paused or stopped download thread
    def start(self):
        self.state = "downloading"
        self.updateClient()
        print "Warning starting downloader in thread"
        self.runDownloader(True)

    def restoreState(self, data):
        self.__dict__ = copy(data)
        if self.state == "downloading":
            self.thread = Thread(target=lambda:self.runDownloader(retry = True), \
                                 name="downloader -- %s" % self.shortFilename)
            self.thread.setDaemon(False)
            self.thread.start()


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
            self.dler.state = "uploading"
            newfilename = os.path.join(config.get(config.MOVIES_DIRECTORY),self.dler.shortFilename)
            newfilename = self.dler.nextFreeFilename(newfilename)
            rename(self.dler.filename,newfilename)
            self.dler.filename = newfilename
            self.dler.endTime = time()
            if self.dler.endTime - self.dler.startTime != 0:
                self.dler.rate = self.dler.totalSize/(self.dler.endTime-self.dler.startTime)
            self.dler.currentSize =self.dler.totalSize
            self.dler.multitorrent.singleport_listener.remove_torrent(self.dler.metainfo.infohash)
            self.dler.torrent = self.dler.multitorrent.start_torrent(self.dler.metainfo,self.dler.torrentConfig, self.dler, self.dler.filename)

        self.dler.updateClient()

    def error(self, errormsg):
        print errormsg
            
    def display(self, statistics):
        update = False
        now = time()
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
        if self.lastUpdated < now-3:
            update = True
            self.lastUpdated = now
        if update:
            self.dler.updateClient()

class BTDownloader(BGDownloader):
    def global_error(level, text):
        print "Bittorrent error (%s): %s" % (level, text)
    doneflag = Event()
    torrentConfig = configfile.parse_configuration_and_args(defaults,'btdownloadheadless', [], 0, None)
    torrentConfig = torrentConfig[0]
    multitorrent = Multitorrent(torrentConfig, doneflag, global_error)

    def __init__(self, url = None, item = None, restore = None):
        self.metainfo = None
        self.rate = 0
        self.eta = 0
        self.d = BTDisplay(self)
        self.uploaded = 0
        self.torrent = None
        if restore is not None:
            self.restoreState(restore)
        else:            
            BGDownloader.__init__(self,url,item)

    def restoreState(self, data):
        self.__dict__ = data
        self.d = BTDisplay(self)
        if self.state in ("downloading","uploading"):
            self.thread = Thread(target=self.restartDL, \
                                 name="downloader -- %s" % self.shortFilename)
            self.thread.setDaemon(False)
            self.thread.start()

    def getStatus(self):
        data = BGDownloader.getStatus(self)
        data['metainfo'] = self.metainfo
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
            self.torrent.shutdown()
        except KeyError:
            pass
        except AttributeError:
            pass

    def stop(self):
        self.state = "stopped"
        self.updateClient()
        if self.torrent is not None:
            self.torrent.shutdown()
            try:
                self.torrent.shutdown()
            except KeyError:
                pass
        try:
            remove(self.filename)
        except:
            pass

    def start(self):
        self.pause()
        metainfo = self.metainfo
        if metainfo == None:
            self.reasonFailed = "Could not read BitTorrent metadata"
            self.state = "failed"
        else:
            self.state = "downloading"
        self.updateClient()
        if metainfo != None:
            self.torrent = self.multitorrent.start_torrent(metainfo,
                                self.torrentConfig, self, self.filename)

    def runDownloader(self,done=False):
        self.updateClient()
        if self.metainfo is None:
            h = grabURL(self.getURL(),"GET", findHTTPAuth = findHTTPAuth)
            if h is None:
                self.state = "failed"
                self.reasonFailed = "Could not connect to server"
                self.updateClient()
                return
            else:
                metainfo = h['file-handle'].read()
                h['file-handle'].close()
        try:
            # raises BTFailure if bad
            if self.metainfo is None:
                metainfo = ConvertedMetainfo(bdecode(metainfo))
            else:
                metainfo = self.metainfo
            self.shortFilename = metainfo.name_fs
            if not done:
                self.pickInitialFilename()
            if self.metainfo is None:
                self.metainfo = metainfo
            self.set_torrent_values(self.metainfo.name, self.filename,
                                self.metainfo.total_bytes, len(self.metainfo.hashes))
            self.torrent = self.multitorrent.start_torrent(self.metainfo,
                                self.torrentConfig, self, self.filename)
        except BTFailure, e:
            print str(e)
            return
        self.get_status()

    ##
    # Functions below this point are needed by BitTorrent
    def set_torrent_values(self, name, path, size, numpieces):
        self.totalSize = size

    def exception(self, torrent, text):
        self.error(torrent, CRITICAL, text)

    def started(self, torrent):
        pass


    def get_status(self):
        #print str(self.getID()) + ": "+str(self.metainfo.infohash).encode('hex')
        self.multitorrent.rawserver.add_task(self.get_status,
                                             self.torrentConfig['display_interval'])
        status = self.torrent.get_status(False)
        self.d.display(status)

    def error(self, torrent, level, text):
        self.d.error(text)

    def failed(self, torrent, is_external):
        pass

    def finished(self, torrent):
        self.d.finished()

    def restartDL(self):
        if self.metainfo != None and self.state != "finished":
            self.torrent = self.multitorrent.start_torrent(self.metainfo,
                                      self.torrentConfig, self, self.filename)

            self.get_status()
        elif self.state != "finished":
            self.state = "paused"

    @classmethod
    def wakeup(self):
        if sys.platform != 'win32':
            if BTDownloader.multitorrent.rawserver.wakeupfds[1] is not None:
                os.write(BTDownloader.multitorrent.rawserver.wakeupfds[1], 'X')

##
# Kill the main BitTorrent thread
#
# This should be called before closing the app
def shutdownBTDownloader():
    BTDownloader.doneflag.set()
    BTDownloader.wakeup()
    BTDownloader.dlthread.join()

def startBTDownloader():
    #Spawn the download thread
    BTDownloader.dlthread = Thread(target=BTDownloader.multitorrent.rawserver.listen_forever)
    BTDownloader.dlthread.setName("bittorrent downloader")
    BTDownloader.dlthread.start()
