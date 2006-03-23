from database import DDBObject, defaultDatabase
from threading import Thread, Event, RLock
from httplib import HTTPConnection, HTTPSConnection,HTTPException
from scheduler import ScheduleEvent
import threadpriority
import config
import traceback
import socket
import platformutils
from base64 import b64encode

from time import sleep,time
from urlparse import urlparse,urljoin
from os import remove, rename, access, F_OK
import re
import math
from copy import copy

from BitTorrent import configfile
from BitTorrent.download import Feedback, Multitorrent
from BitTorrent.defaultargs import get_defaults
from BitTorrent.parseargs import parseargs, printHelp
from BitTorrent.bencode import bdecode
from BitTorrent.ConvertedMetainfo import ConvertedMetainfo
from BitTorrent import configfile
from BitTorrent import BTFailure, CRITICAL
from BitTorrent import version

import sys
import os
import threading
from time import time, strftime
from cStringIO import StringIO

from dl_daemon import daemon, command

import app

from download_utils import grabURL, parseURL, cleanFilename

DOWNLOAD_DAEMON = False

defaults = get_defaults('btdownloadheadless')
defaults.extend((('donated', '', ''),))

# Pass in a connection to the frontend
def setDelegate(newDelegate):
    global delegate
    delegate = newDelegate

class DownloaderError(Exception):
    pass

# Returns an HTTP auth object corresponding to the given host, path or
# None if it doesn't exist
def findHTTPAuth(host,path,realm = None,scheme = None):
    #print "Trying to find HTTPAuth with host %s, path %s, realm %s, and scheme %s" %(host,path,realm,scheme)
    ret = None
    defaultDatabase.beginRead()
    try:
        for obj in app.globalViewList['httpauths']:
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

class Downloader(DDBObject):
    def __init__(self, url,item):
        self.url = url
        self.itemList = [item]
        self.startTime = time()
        self.endTime = self.startTime
        self.shortFilename = self.filenameFromURL(url)
        self.filename = os.path.join(config.get(config.MOVIES_DIRECTORY),'Incomplete Downloads',self.shortFilename+".part")
        self.filename = self.nextFreeFilename(self.filename)
        self.state = "downloading"
        self.currentSize = 0
        self.totalSize = -1
        self.blockTimes = []
        self.reasonFailed = "No Error"
        self.headers = None
        DDBObject.__init__(self)
        self.thread = Thread(target=self.runDownloader, \
                             name="downloader -- %s" % self.shortFilename)
        self.thread.setDaemon(True)
        self.thread.start()

    ##
    # In case multiple downloaders are getting the same file, we can support multiple items
    def addItem(self,item):
        self.itemList.append(item)

    ##
    # Returns the reason for the failure of this download
    # This should only be called when the download is in the failed state
    def getReasonFailed(self):
        ret = ""
        self.beginRead()
        try:
            ret = self.reasonFailed
        finally:
            self.endRead()
        return ret

    ##
    # Finds a filename that's unused and similar the the file we want
    # to download
    def nextFreeFilename(self, name):
        if not access(name,F_OK):
            return name
        parts = name.split('.')
        insertPoint = len(parts)-1
        count = 1
        parts[insertPoint:insertPoint] = [str(count)]
        newname = '.'.join(parts)
        while access(newname,F_OK):
            count += 1
            parts[insertPoint] = str(count)
            newname = '.'.join(parts)
        return newname

    def remove(self):
        DDBObject.remove(self)

    ##
    # Returns the URL we're downloading
    def getURL(self):
        self.beginRead()
        ret = self.url
        self.endRead()
        return ret
    ##    
    # Returns the state of the download: downloading, paused, stopped,
    # failed, or finished
    def getState(self):
        self.beginRead()
        ret = self.state
        self.endRead()
        return ret

    ##
    # Returns the total size of the download in bytes
    def getTotalSize(self):
        self.beginRead()
        ret = self.totalSize
        self.endRead()
        return ret

    ##
    # Returns the current amount downloaded in bytes
    def getCurrentSize(self):
        self.beginRead()
        ret = self.currentSize
        self.endRead()
        return ret

    ##
    # Returns a float with the estimated number of seconds left
    def getETA(self):
        self.beginRead()
        try:
            rate = self.getRate()
            if rate != 0:
                eta = (self.totalSize - self.currentSize)/rate
                if eta < 0:
                    eta = 0
            else:
                eta = 0
        finally:
            self.endRead()
        return eta

    ##
    # Returns a float with the download rate in bytes per second
    def getRate(self):
        now = time()
        self.beginRead()
        try:
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
        finally:
            self.endRead()
        return rate

    ##
    # Returns the filename that we're downloading to. Should not be
    # called until state is "finished."
    def getFilename(self):
        self.beginRead()
        ret = self.filename
        self.endRead()
        return ret

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

    def runDownloader(self):
        pass

    ##
    # Called by pickle during serialization
    def __getstate__(self):
        temp = copy(self.__dict__)
        temp["thread"] = None
        return (0,temp)

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
        (version, data) = state
        assert(version == 0)
        self.__dict__ = data
        self.filename = config.ensureMigratedMoviePath(self.filename)
        if self.getState() == "downloading":
            ScheduleEvent(0, lambda :self.runDownloader(retry = True),False)

# Download an item using our separate download process
class RemoteDownloader(Downloader):
    def __init__(self, url,item,contentType):
        self.dlid = "noid"
        self.contentType = contentType
        self.eta = 0
        self.rate = 0
        Downloader.__init__(self,url,item)

    @classmethod
    def initializeDaemon(cls):
        if DOWNLOAD_DAEMON:
            RemoteDownloader.dldaemon = daemon.Daemon(server = False)

    @classmethod
    def updateStatus(cls, data):
        view = app.globalViewList['remoteDownloads'].filterWithIndex(
            app.globalIndexList['downloadsByDLID'],data['dlid'])
        try:
            view.resetCursor()
            self = view.getNext()
        finally:   
            app.globalViewList['remoteDownloads'].removeView(view)
        if not self is None:
            for key in data.keys():
                self.__dict__[key] = data[key]
            for item in self.itemList:
                item.beginChange()
                item.endChange()
        
    ##
    # This is the actual download thread.
    def runDownloader(self, retry = False):
        if not retry:
            c = command.StartNewDownloadCommand(RemoteDownloader.dldaemon,
                                                self.url, self.contentType)
            self.dlid = c.send()
            #FIXME: This is sooo slow...
            app.globalViewList['remoteDownloads'].recomputeIndex(app.globalIndexList['downloadsByDLID'])

    ##
    # Pauses the download.
    def pause(self):
        c = command.PauseDownloadCommand(RemoteDownloader.dldaemon,
                                            self.dlid)
        return c.send()

    ##
    # Stops the download and removes the partially downloaded
    # file.
    def stop(self):
        c = command.StopDownloadCommand(RemoteDownloader.dldaemon,
                                            self.dlid)
        return c.send()

    ##
    # Continues a paused or stopped download thread
    def start(self):
        c = command.StartDownloadCommand(RemoteDownloader.dldaemon,
                                            self.dlid)
        return c.send()

    def getRate(self):
        return self.rate

    def getETA(self):
        return self.eta

    ##
    # Removes downloader from the database
    def remove(self):
        self.stop()
        Downloader.remove(self)

    ##
    # Called by pickle during serialization
    def __getstate__(self):
        temp = copy(self.__dict__)
        temp["thread"] = None
        return (0,temp)

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
        (version, data) = state
        self.__dict__ = copy(data)
        del data['itemList']
        if data['dlid'] != 'noid':
            c = command.RestoreDownloaderCommand(RemoteDownloader.dldaemon, data)
            c.send(retry = True, block = False)
        else:
            self.thread = Thread(target=self.runDownloader, \
                                 name="downloader -- %s" % self.shortFilename)
            self.thread.setDaemon(True)
            self.thread.start()
            

class HTTPDownloader(Downloader):
    def __init__(self, url,item):
        self.lastUpdated = 0
        self.lastSize = 0
        Downloader.__init__(self,url,item)

    ##
    # Update the download rate and eta based on recieving length bytes
    def updateRateAndETA(self,length):
        now = time()
        updated = False
        self.beginRead()
        try:
            self.currentSize = self.currentSize + length
            if self.lastUpdated < now-3:
                self.blockTimes.append((now,  self.currentSize))
                #Only keep the last 100 packets
                if len(self.blockTimes)>100:
                    self.blockTimes.pop(0)
                updated = True
                self.lastUpdated = now
        finally:
            self.endRead()
        if updated:
            for item in self.itemList:
                item.beginChange()
                item.endChange()

    ##
    # Grabs the next block from the HTTP connection
    def getNextBlock(self,handle):
        self.beginRead()
        state = self.state
        self.endRead()
        if (state == "paused") or (state == "stopped"):
            data = ""
        else:
            try:
                data = handle.read(1024)
            except:
                self.beginRead()
                self.state = "failed"
                self.reasonFailed = "Lost connection to server"
                self.endRead()
                data = ""
        self.updateRateAndETA(len(data))
        return data

    ##
    # This is the actual download thread.
    def runDownloader(self, retry = False):
        threadpriority.setBackgroundPriority()

        if retry:
            self.beginRead()
            pos = self.currentSize
            self.endRead()
            try:
                filehandle = file(self.filename,"r+b")
                filehandle.seek(pos)
            except:
                filehandle = file(self.filename,"w+b")
                self.beginRead()
                self.currentSize = 0
                totalSize = self.totalSize
                self.endRead()
                pos = 0
                if totalSize > 0:
                    filehandle.seek(totalSize-1)
                    filehandle.write(' ')
                    filehandle.seek(0)

            info = grabURL(self.url,"GET",pos)
            if info is None and pos > 0:
                pos = 0
                self.beginRead()
                self.currentSize = 0
                self.endRead()
                info = grabURL(self.url,"GET")       
            if info is None:
                self.beginRead()
                try:
                    self.state = "failed"
                    self.reasonFailed = "Could not connect to server"
                finally:
                    self.endRead()
                return False
        else:
            #print "We don't have any INFO..."
            info = grabURL(self.url,"GET")
            if info is None:
                self.beginRead()
                try:
                    self.state = "failed"
                    self.reasonFailed = "Could not connect to server"
                finally:
                    self.endRead()
                return False

        if not retry:
            #get the filename to save to
            self.beginRead()
            try:
                self.shortFilename = info['filename']
                self.filename = os.path.join(config.get(config.MOVIES_DIRECTORY),'Incomplete Downloads',self.shortFilename+".part")
                self.filename = self.nextFreeFilename(self.filename)
            finally:
                self.endRead()

            #Get the length of the file, then create it
            self.beginRead()
            try:
                try:
                    totalSize = int(info['content-length'])
                except KeyError:
                    totalSize = -1
                self.totalSize = totalSize
            finally:
                self.endRead()
            try:
                filehandle = file(self.filename,"w+b")
            except IOError:
                self.beginRead()
                try:
                    self.state = "failed"
                    self.reasonFailed = "Could not write file to disk"
                finally:
                    self.endRead()
                return False
            self.beginRead()
            self.currentSize = 0
            self.endRead()
            if not self.acceptDownloadSize(totalSize):
                print "file is too big"
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
        self.beginRead()
        try:
            if self.state == "downloading":
                self.state = "finished"
                for item in self.itemList:
                    item.setDownloadedTime()
                newfilename = os.path.join(config.get(config.MOVIES_DIRECTORY),self.shortFilename)
                newfilename = self.nextFreeFilename(newfilename)
                rename(self.filename,newfilename)
                self.filename = newfilename
                if self.totalSize == -1:
                    self.totalSize = self.currentSize
                self.endTime = time()
            elif self.state == "stopped":
                try:
                    remove(self.filename)
                except:
                    pass
        finally:
            self.endRead()
            #FIXME: Really, this change should trigger a change in the item,
            #so we don't have to manually change each item
            self.beginChange()
            self.endChange()
            for item in self.itemList:
                item.beginChange()
                item.endChange()
 
    ##
    # Checks the download file size to see if we can accept it based on the 
    # user disk space preservation preference
    def acceptDownloadSize(self, size):
        if config.get(config.PRESERVE_DISK_SPACE):
            sizeInGB = size / 1024 / 1024 / 1024
            if sizeInGB > platformutils.getAvailableGBytesForMovies() - config.get(config.PRESERVE_X_GB_FREE):
                self.beginRead()
                try:
                    self.state = "failed"
                    self.reasonFailed = "File is too big"
                finally:
                    self.endRead()
                return False
        return True
        

    ##
    # Pauses the download.
    def pause(self):
        self.beginRead()
        try:
            if self.state != "stopped":
                self.state = "paused"
        finally:
            self.endRead()
        for item in self.itemList:
            item.beginChange()
            item.endChange()

    ##
    # Stops the download and removes the partially downloaded
    # file.
    def stop(self):
        self.beginRead()
        try:
            if self.state != "downloading":
                try:
                    remove(self.filename)
                except:
                    pass
            self.state = "stopped"
        finally:
            self.endRead()
        for item in self.itemList:
            item.beginChange()
            item.endChange()

    ##
    # Continues a paused or stopped download thread
    def start(self):
        self.pause() #Pause the download thread
        self.beginRead()
        self.state = "downloading"
        self.endRead()
        for item in self.itemList:
            item.beginChange()
            item.endChange()
        self.runDownloader(True)

    ##
    # Removes downloader from the database
    def remove(self):
        self.pause()
        Downloader.remove(self)

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
        for item in self.dler.itemList:
            item.setDownloadedTime()
        self.dler.beginRead()
        try:
            if not (self.dler.state == "uploading" or
                    self.dler.state == "finished"):
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

        finally:
            self.dler.endRead()
            #FIXME: Really, this change should trigger a change in the item,
            #so we don't have to manually change each item
            self.dler.beginChange()
            self.dler.endChange()
            for item in self.dler.itemList:
                item.beginChange()
                item.endChange()

    def error(self, errormsg):
        print errormsg
            
    def display(self, statistics):
        update = False
        now = time()
        self.dler.beginRead()
        try:
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
        finally:
            self.dler.endRead()
            if update:
                for item in self.dler.itemList:
                    item.beginChange()
                    item.endChange()

    ##
    # Called by pickle during serialization
    def __getstate__(self):
        temp = copy(self.__dict__)
        return (0,temp)

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
        (version, data) = state
        self.__dict__ = data

class BTDownloader(Downloader):
    def global_error(level, text):
        print "Bittorrent error (%s): %s" % (level, text)
    doneflag = threading.Event()
    torrentConfig = configfile.parse_configuration_and_args(defaults,'btdownloadheadless', [], 0, None)
    torrentConfig = torrentConfig[0]
    multitorrent = Multitorrent(torrentConfig, doneflag, global_error)

    def __init__(self, url, item):
        self.metainfo = None
        self.rate = 0
        self.eta = 0
        self.d = BTDisplay(self)
        self.uploaded = 0
        self.torrent = None
        Downloader.__init__(self,url,item)

    def getRate(self):
        self.beginRead()
        ret = self.rate
        self.endRead()
        return ret

    def getETA(self):
        self.beginRead()
        ret = self.eta
        self.endRead()
        return ret
        
    def pause(self):
        self.beginRead()
        self.state = "paused"
        self.endRead()
        for item in self.itemList:
            item.beginChange()
            item.endChange()
        try:
            self.torrent.shutdown()
        except KeyError:
            pass

    def stop(self):
        self.beginRead()
        self.state = "stopped"
        self.endRead()
        for item in self.itemList:
            item.beginChange()
            item.endChange()
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

        pass

    def start(self):
        self.pause()
        self.beginRead()
        metainfo = self.metainfo
        if metainfo == None:
            self.state = "failed"
            self.reasonFailed = "Could not read BitTorrent metadata"
        else:
            self.state = "downloading"
        self.endRead()
        for item in self.itemList:
            item.beginChange()
            item.endChange()
        if metainfo != None:
            self.torrent = self.multitorrent.start_torrent(metainfo,
                                self.torrentConfig, self, self.filename)

    ##
    # Removes downloader from the database
    def remove(self):
        ScheduleEvent(0,self.pause,False)
        Downloader.remove(self)

    def runDownloader(self,done=False):
        for item in self.itemList:
            item.beginChange()
            item.endChange()
        if self.metainfo is None:
            h = grabURL(self.getURL(),"GET")
            if h is None:
                self.beginChange()
                try:
                    self.state = "failed"
                    self.reasonFailed = "Could not connect to server"
                finally:
                    self.endChange()
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
                self.filename = os.path.join(config.get(config.MOVIES_DIRECTORY),'Incomplete Downloads',self.shortFilename+".part")
                self.filename = self.nextFreeFilename(self.filename)
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
        self.beginRead()
        try:
            self.totalSize = size
        finally:
            self.endRead()

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
        threadpriority.setBackgroundPriority()

        if self.metainfo != None and self.state != "finished":
            self.torrent = self.multitorrent.start_torrent(self.metainfo,
                                      self.torrentConfig, self, self.filename)

            self.get_status()
        elif self.state != "finished":
            self.state = "paused"

    def __getstate__(self):
        temp = copy(self.__dict__)
        temp["thread"] = None
        try:
            temp["torrent"] = None
        except:
            pass
        return (0,temp)

    def __setstate__(self,state):
        (version, data) = state
        self.__dict__ = data
        self.thread = Thread(target=self.restartDL, \
                             name="unpickled download -- %s" %\
                             (self.shortFilename, ))
        self.thread.setDaemon(True)
        self.thread.start()

    @classmethod
    def wakeup(self):
        if sys.platform != 'win32':
            if BTDownloader.multitorrent.rawserver.wakeupfds[1] is not None:
                os.write(BTDownloader.multitorrent.rawserver.wakeupfds[1], 'X')

##
# Kill the main BitTorrent thread
#
# This should be called before closing the app
def shutdownDownloader():
    if DOWNLOAD_DAEMON:
        c = command.ShutDownCommand(RemoteDownloader.dldaemon)
        c.send()
    else:
        BTDownloader.doneflag.set()
        BTDownloader.wakeup()
        BTDownloader.dlthread.join()
    

# Spawn the download thread
if not DOWNLOAD_DAEMON:
    BTDownloader.dlthread = Thread(target=BTDownloader.multitorrent.rawserver.listen_forever)
    BTDownloader.dlthread.setName("bittorrent downloader")
    BTDownloader.dlthread.start()

class DownloaderFactory:
    lock = RLock()
    def __init__(self,item):
        self.item = item

    def getDownloader(self,url):
        info = grabURL(url,'GET')
        if info is None:
            return None
        # FIXME: uncomment these 2 lines and comment the 3 above to
        # enable the download daemon

        elif DOWNLOAD_DAEMON:
            return RemoteDownloader(info['updated-url'],self.item, info['content-type'])
        self.lock.acquire()
        try:
            ret = None
            defaultDatabase.beginUpdate()
            defaultDatabase.saveCursor()
            try:
                defaultDatabase.resetCursor()
                for obj in defaultDatabase:
                    if isinstance(obj,Downloader) and obj.url == info['updated-url']:
                        ret = obj
                        break
            finally:
                defaultDatabase.restoreCursor()
                defaultDatabase.endUpdate()
            if not ret is None:
                ret.addItem(self.item)
            else:
                if info['content-type'] == 'application/x-bittorrent':
                    #print "Got BT Download"
                    ret = BTDownloader(info['updated-url'],self.item)
                else:
                    #print "Got HTTP download"
                    ret = HTTPDownloader(info['updated-url'],self.item)
        finally:
            self.lock.release()
        return ret


if __name__ == "__main__":
    def printsaved():
        print "Saved!"
    def displayDLStatus(dler):
        print dler.getState()
        print str(dler.getCurrentSize()) + " of " + str(dler.getTotalSize())
        print str(dler.getETA()) + " seconds remaining"
        print str(dler.getRate()) + " bytes/sec"
        print "Saving to " + dler.getFilename()
    factory = DownloaderFactory(DDBObject())
    x = factory.getDownloader("http://www.blogtorrent.com/demo/btdownload.php?type=torrent&file=SatisfactionWeb.mov.torrent")
    y = factory.getDownloader("http://www.vimeo.com/clips/2005/04/05/vimeo.thelastminute.613.mov")
    ScheduleEvent(2,lambda :displayDLStatus(x),True)
    ScheduleEvent(2,lambda :displayDLStatus(y),True)
    sleep(60)
    x.stop()
