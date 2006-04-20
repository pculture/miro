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
        self.reasonFailed = "No Error"
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

    ##
    # Called by pickle during deserialization
    def onRestore(self):
        self.filename = config.ensureMigratedMoviePath(self.filename)

# Download an item using our separate download process
# Pass in url, item, and contentType to create
# Pass in localDownloadData to create from data found in local downloader
class RemoteDownloader(Downloader):
    def __init__(self, url = None, item = None, contentType = None):
        self.dlid = "noid"
        self.contentType = contentType
        self.eta = 0
        self.rate = 0
        Downloader.__init__(self,url,item)
            
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
            # Store the time the download finished
            if ((self.state in ['finished','uploading']) and
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
        app.globalViewList['remoteDownloads'].recomputeIndex(app.globalIndexList['downloadsByDLID'])

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
    # Called by pickle during deserialization
    def onRestore(self):
        if self.dlid == 'noid':
            thread = Thread(target=self.runDownloader, \
                            name="downloader -- %s" % self.shortFilename)
            thread.setDaemon(True)
            thread.start()
        elif self.state in ['downloading','uploading']:
            toSend = self.__dict__.copy()
            del toSend['itemList']
            c = command.RestoreDownloaderCommand(RemoteDownloader.dldaemon, 
                    toSend)
            c.send(retry = True, block = False)

##
# Kill the main BitTorrent thread
#
# This should be called before closing the app
def shutdownDownloader():
    c = command.ShutDownCommand(RemoteDownloader.dldaemon)
    c.send(block=False)    

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
