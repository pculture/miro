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

    def runDownloader(self, retry = False):
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
# Pass in url, item, and contentType to create
# Pass in localDownloadData to create from data found in local downloader
class RemoteDownloader(Downloader):
    def __init__(self, url = None,item = None,contentType = None,
                 localDownloadData = None):
        if localDownloadData is None:
            self.dlid = "noid"
            self.contentType = contentType
            self.eta = 0
            self.rate = 0
            Downloader.__init__(self,url,item)
        else:
            self.__dict__ = localDownloadData
            self.dlid = "noid"
            self.eta = 0
            self.rate = 0
            if self.dlerType == 'BitTorrent':
                self.contentType = 'application/x-bittorrent'
            else:
                self.contentType = 'video/x-unknown'
            self.thread = Thread(target=self.runDownloader, \
                                 name="downloader -- %s" % self.shortFilename)
            self.thread.setDaemon(True)
            self.thread.start()
            
    @classmethod
    def initializeDaemon(cls):
        RemoteDownloader.dldaemon = daemon.ControllerDaemon()

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
            oldState = self.state
            for key in data.keys():
                self.__dict__[key] = data[key]
            if self.state == 'finished' and oldState != 'finished':
                for item in self.itemList:
                    item.setDownloadedTime()
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
        if data['dlid'] != 'noid':
            del data['itemList']
            c = command.RestoreDownloaderCommand(RemoteDownloader.dldaemon, data)
            c.send(retry = True, block = False)
        else:
            self.thread = Thread(target=self.runDownloader, \
                                 name="downloader -- %s" % self.shortFilename)
            self.thread.setDaemon(True)
            self.thread.start()

##
# For upgrading from old versions of the database
class HTTPDownloader(Downloader):
    pass

##
# For upgrading from old versions of the database
class BTDisplay:
    def __setstate__(self,state):
        (version, data) = state
        self.__dict__ = data

##
# For upgrading from old versions of the database
class BTDownloader(Downloader):
    pass

##
# Kill the main BitTorrent thread
#
# This should be called before closing the app
def shutdownDownloader():
    c = command.ShutDownCommand(RemoteDownloader.dldaemon)
    c.send()    

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

        else:
            return RemoteDownloader(info['updated-url'],self.item, info['content-type'])

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
