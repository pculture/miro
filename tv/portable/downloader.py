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

class RemoteDownloader(DDBObject):
    """Download a file using the downloader daemon."""

    def __init__(self, url, item, contentType):
        self.url = url
        self.itemList = [item]
        self.contentType = contentType
        self.dlid = "noid"
        self.status = {}
        self.thread = Thread(target=self.runDownloader, 
                             name="downloader -- %s" % self.url)
        self.thread.setDaemon(True)
        self.thread.start()
        DDBObject.__init__(self)

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

    ##
    # Removes downloader from the database
    def remove(self):
        self.stop()
        DDBObject.remove(self)

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
            return self.status['filename']
        finally:
            self.endRead()

    def onRestore(self):
        if self.dlid == 'noid' or len(self.status) == 0:
            thread = Thread(target=self.runDownloader, \
                            name="downloader -- %s" % self.url)
            thread.setDaemon(True)
            thread.start()
        elif self.getState() in ['downloading','uploading']:
            c = command.RestoreDownloaderCommand(RemoteDownloader.dldaemon, 
                    self.status)
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
        else:
            return RemoteDownloader(info['updated-url'],self.item, info['content-type'])
