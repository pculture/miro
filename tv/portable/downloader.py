from database import DDBObject
from threading import RLock, Thread, Event
from httplib import HTTPConnection
from scheduler import ScheduleEvent
import config

from time import sleep,time
from urlparse import urlparse
from os import remove, rename, access, F_OK
import re
import math
from copy import copy

from BitTorrent import configfile
from BitTorrent.download import Feedback, Multitorrent
from BitTorrent.defaultargs import get_defaults
from BitTorrent.parseargs import parseargs, printHelp
from BitTorrent.zurllib import urlopen
from BitTorrent.bencode import bdecode
from BitTorrent.ConvertedMetainfo import ConvertedMetainfo
from BitTorrent import configfile
from BitTorrent import BTFailure, CRITICAL
from BitTorrent import version

import sys
import os
import threading
from time import time, strftime
from signal import signal, SIGWINCH
from cStringIO import StringIO

defaults = get_defaults('btdownloadheadless')
defaults.extend((('donated', '', ''),
                 ))

#FIXME: check for free space and failed connection to tracker and fail
#on those cases

class DownloaderError(Exception):
    pass


class Downloader(DDBObject):
    def __init__(self, url,item):
        self.url = url
	self.item = item
        self.startTime = time()
        self.endTime = self.startTime
	self.shortFilename = self.filenameFromURL(url)
        self.filename = os.path.join(config.get('DataDirectory'),'Incomplete Downloads',self.shortFilename+".part")
	self.filename = self.nextFreeFilename(self.filename)
        self.state = "downloading"
        self.currentSize = 0
        self.totalSize = -1
        self.blockTimes = []
        self.headers = None
        self.lock = RLock()
        DDBObject.__init__(self)
        self.thread = Thread(target=self.runDownloader)
        self.thread.setDaemon(True)
        self.thread.start()

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


    ##
    # Returns the URL we're downloading
    def getURL(self):
        self.lock.acquire()
        ret = self.url
        self.lock.release()
        return ret
    ##    
    # Returns the state of the download: downloading, paused, stopped,
    # failed, or finished
    def getState(self):
        self.lock.acquire()
        ret = self.state
        self.lock.release()
        return ret

    ##
    # Returns the total size of the download in bytes
    def getTotalSize(self):
        self.lock.acquire()
        ret = self.totalSize
        self.lock.release()
        return ret

    ##
    # Returns the current amount downloaded in bytes
    def getCurrentSize(self):
        self.lock.acquire()
        ret = self.currentSize
        self.lock.release()
        return ret

    ##
    # Returns a float with the estimated number of seconds left
    def getETA(self):
        self.lock.acquire()
        try:
            rate = self.getRate()
            if rate != 0:
                eta = (self.totalSize - self.currentSize)/rate
                if eta < 0:
                    eta = 0
            else:
                eta = 0
        finally:
            self.lock.release()
        return eta

    ##
    # Returns a float with the download rate in bytes per second
    def getRate(self):
        now = time()
        self.lock.acquire()
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
            self.lock.release()
        return rate

    ##
    # Returns the filename that we're downloading to. Should not be
    # called until state is "finished."
    def getFilename(self):
        self.lock.acquire()
        ret = self.filename
        self.lock.release()
        return ret

    ##
    # Returns a reasonable filename for saving the given url
    def filenameFromURL(self,url):
        (scheme, host, path, params, query, fragment) = urlparse(url)
        if len(path):
            return re.compile("^.*?([^/]+)/?$").search(path).expand("\\1")
        else:
            return "unknown"

    def runDownloader(self):
        pass

    ##
    # Called by pickle during serialization
    def __getstate__(self):
	temp = copy(self.__dict__)
	temp["lock"] = None
	temp["thread"] = None
	return temp

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
	self.__dict__ = state
	self.lock = RLock()
        self.thread = Thread(target=lambda :self.runDownloader(retry = True))
        self.thread.setDaemon(True)
        self.thread.start()


class HTTPDownloader(Downloader):
    def __init__(self, url,item, conn = None,download = None,redirURL = None):
	self.conn = conn
	self.download = download
	self.redirURL = redirURL
	self.lastUpdated = 0
	self.lastSize = 0
	Downloader.__init__(self,url,item)

    ##
    # Update the download rate and eta based on recieving length bytes
    def updateRateAndETA(self,length):
        now = math.floor(time())
	updated = False
        self.lock.acquire()
        try:
            self.currentSize = self.currentSize + length
	    if self.lastUpdated < now:
		self.blockTimes.append((now,  self.currentSize))
	        #Only keep the last 100 packets
		if len(self.blockTimes)>100:
		    self.blockTimes.pop(0)
	        updated = True
		self.lastUpdated = now
        finally:
            self.lock.release()
	if updated:
	    self.item.beginChange()
	    self.item.endChange()

    ##
    # Grabs the next block from the HTTP connection
    def getNextBlock(self,handle):
        self.lock.acquire()
        state = self.state
        self.lock.release()
        if (state == "paused") or (state == "stopped"):
            data = ""
	else:
	    try:
		data = handle.read(1024)
	    except:
		self.lock.acquire()
		self.state = "failed"
		self.lock.release()
		data = ""
        self.updateRateAndETA(len(data))
        return data

    ##
    # This is the actual download thread. Connects to the 
    def runDownloader(self, retry = False):
	self.item.beginChange()
	self.item.endChange()
        try:
            #Attempt to connect to the host and get header information
            (scheme, host, path, params, query, fragment) = urlparse(self.url)
            if len(params):
                path += ';'+params
            if len(query):
                path += '?'+query
	    if self.conn == None:
		conn = HTTPConnection(host)
		conn.request("HEAD",path)
		download = conn.getresponse()
		depth = 0
	    else:
		conn = self.conn
		download = self.download
		(scheme, host, path, params, query, fragment) = urlparse(self.redirURL)
		depth = 0
	    while download.status != 200 and depth < 10:
		depth += 1
		if download.status == 302 or download.status == 307 or download.status == 301:
		    info = download.msg
		    download.close()
		    conn.close()
		    if download.status == 301:
			self.url = info['Location']
		    (scheme, host, path, params, query, fragment) = urlparse(info['Location'])
		    if len(params):
			path += ';'+params
		    if len(query):
			path += '?'+query
		    conn = HTTPConnection(host)
		    conn.request("HEAD",path)
		    download = conn.getresponse()
		else:
		    raise DownloaderError, "File not found"
	    if depth == 10:
		raise DownloaderError, "Maximum redirect depth"
        except:
            self.lock.acquire()
            try:
                self.state = "failed"
            finally:
                self.lock.release()
            return False

	info = download.msg
	download.close()

        #Get the length of the file
        self.lock.acquire()
        try:
            try:
                totalSize = int(info['Content-Length'])
            except KeyError:
                totalSize = -1
            self.totalSize = totalSize
        finally:
            self.lock.release()

	if not retry:
	    try:
                #Get the filename, if an alternate one is given
		disposition = info['Content-Disposition']
		self.lock.acquire()
		try:
		    self.shortFilename = re.compile("^.*filename\s*=\s*\"(.*?)\"$").search(disposition).expand("\\1")
		    self.shortFilename.replace ("/","")
		    self.shortFilename.replace ("\\","")
		    self.filename = os.path.join(config.get('DataDirectory'),'Incomplete Downloads',self.shortFilename+".part")
		    self.filename = self.nextFreeFilename(self.filename)
		finally:
		    self.lock.release()
	    except KeyError:
		pass
	    filehandle = file(self.filename,"w+b")
	    pos = 0
	    if totalSize > 0:
		filehandle.seek(totalSize-1)
		filehandle.write(' ')
		filehandle.seek(0)
	else:
	    try:
		filehandle = file(self.filename,"r+b")
		self.lock.acquire()
		pos = self.currentSize
		self.lock.release()
		filehandle.seek(pos)
	    except:
		filehandle = file(self.filename,"w+b")
		self.lock.acquire()
		self.currentSize = 0
		self.lock.release()
		pos = 0
		if totalSize > 0:
		    filehandle.seek(totalSize-1)
		    filehandle.write(' ')
		    filehandle.seek(0)
        # If we're recovering a download give a range request
        if (pos > 0) and (pos != totalSize):
            conn.request("GET",path,headers = {"Range":"bytes="+str(pos)+"-"})
            download = conn.getresponse()
            if download.status != 206:
		download.close()
                #Range is not supported, start the download from 0
                self.lock.acquire()
                self.currentSize = 0
                self.lock.release()
                filehandle.close()
                filehandle = file(self.filename,"wb")
                conn.request("GET",path)
                download = conn.getresponse()
                if download.status != 200:
                    raise DownloaderError, "File not found"
        elif pos == 0:
            #If we're starting a download from the beginning, give a
            #plain old GET request
            conn.request("GET",path)
            download = conn.getresponse()
            if download.status != 200:
                raise DownloaderError, "Failed with "+str(download.status)
            
        #Download the file
        if pos != totalSize:
            data = self.getNextBlock(download)
            while len(data) > 0:
                filehandle.write(data)
                data = self.getNextBlock(download)
            filehandle.close()
            download.close()
        #Update the status
        self.lock.acquire()
        try:
            if self.state == "downloading":
                self.state = "finished"
		self.item.setDownloadedTime()
		newfilename = os.path.join(config.get('DataDirectory'),self.shortFilename)
		newfilename = self.nextFreeFilename(newfilename)
		rename(self.filename,newfilename)
		self.filename = newfilename
                if self.totalSize == -1:
                    self.totalSize = self.currentSize
                self.endTime = time()
        finally:
            self.lock.release()
	    self.item.beginChange()
	    self.item.endChange()
 

    ##
    # Pauses the download. Currently there's a flaw in the
    # implementation where this will block until the next packet is
    # received
    def pause(self):
        self.lock.acquire()
        self.state = "paused"
        self.lock.release()
	self.item.beginChange()
	self.item.endChange()
        self.thread.join()

    ##
    # Stops the download and removes the partially downloaded
    # file. Currently there's a flaw in the implementation where this
    # will block until the next packet is received
    def stop(self):
        self.lock.acquire()
        self.state = "stopped"
        self.lock.release()
	self.item.beginChange()
	self.item.endChange()
        self.thread.join()
        try:
            remove(self.filename)
        except:
            pass

    ##
    # Continues a paused or stopped download thread
    def start(self):
        self.pause() #Pause the download thread
        self.lock.acquire()
        self.state = "downloading"
        self.lock.release()
	self.item.beginChange()
	self.item.endChange()
	self.runDownloader(True)

    ##
    # Removes downloader from the database
    def remove(self):
        self.pause()
        DDBObject.remove(self)

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
	self.dler.item.setDownloadedTime()
        self.dler.lock.acquire()
	try:
	    if not self.dler.state == "finished":
		self.dler.state = "finished"
		newfilename = os.path.join(config.get('DataDirectory'),self.dler.shortFilename)
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
	    self.dler.lock.release()
	    self.dler.item.beginChange()
	    self.dler.item.endChange()
	    
    def error(self, errormsg):
	print errormsg
            
    def display(self, statistics):
	update = False
	now = math.floor(time())
	self.dler.lock.acquire()
	try:
	    if statistics.get('upTotal') != None:
		if self.lastUpTotal > statistics.get('upTotal'):
		    self.dler.uploaded += statistics.get('upTotal')
		else:
		    self.dler.uploaded += statistics.get('upTotal') - self.lastUpTotal
		self.lastUpTotal = statistics.get('upTotal')
	    if self.dler.state != "paused":
		self.dler.currentSize = int(self.dler.totalSize*statistics.get('fractionDone'))
	    if self.dler.state != "finished":
		self.dler.rate = statistics.get('downRate')
	    if self.dler.rate == None:
		self.dler.rate = 0.0
	    self.dler.eta = statistics.get('timeEst')
	    if self.dler.eta == None:
		self.dler.eta = 0
	    if self.lastUpdated < now:
		update = True
		self.lastUpdated = now
	finally:
	    self.dler.lock.release()
	    if update:
		self.dler.item.beginChange()
		self.dler.item.endChange()

    ##
    # Called by pickle during serialization
    def __getstate__(self):
	temp = copy(self.__dict__)
	temp["lock"] = None
	return temp

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
	self.__dict__ = state
	self.lock = RLock()

class BTDownloader(Downloader):
    def global_error(self, level, text):
        self.d.error(text)
    doneflag = threading.Event()
    torrentConfig = configfile.parse_configuration_and_args(defaults,'btdownloadheadless', [], 0, None)
    torrentConfig = torrentConfig[0]
    multitorrent = Multitorrent(torrentConfig, doneflag, global_error)

    def __init__(self, url, item, metainfo = None):
	self.metainfo = metainfo
        self.rate = 0
        self.eta = 0
        self.d = BTDisplay(self)
        self.uploaded = 0
        Downloader.__init__(self,url,item)

    def getRate(self):
        self.lock.acquire()
        ret = self.rate
        self.lock.release()
        return ret

    def getETA(self):
        self.lock.acquire()
        ret = self.eta
        self.lock.release()
        return ret
        
    def pause(self):
        self.lock.acquire()
        self.state = "paused"
        self.lock.release()
	self.item.beginChange()
	self.item.endChange()
	try:
	    self.torrent.shutdown()
	except KeyError:
	    pass

    def stop(self):
        self.lock.acquire()
        self.state = "stopped"
        self.lock.release()
	self.item.beginChange()
	self.item.endChange()
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
        self.lock.acquire()
	metainfo = self.metainfo
	if metainfo == None:
	    self.state = "failed"
	else:
	    self.state = "downloading"
        self.lock.release()
	self.item.beginChange()
	self.item.endChange()
	if metainfo != None:
	    self.torrent = self.multitorrent.start_torrent(metainfo,
                                self.torrentConfig, self, self.filename)

    ##
    # Removes downloader from the database
    def remove(self):
        self.pause()
        DDBObject.remove(self)

    def runDownloader(self,done=False):
	print "Starting BT Downloader"
	self.item.beginChange()
	self.item.endChange()
	if self.metainfo == None:
	    h = urlopen(self.getURL())
	    metainfo = h.read()
	    h.close()
	    print "Getting new metainfo"
        try:
            # raises BTFailure if bad
	    if self.metainfo == None:
		metainfo = ConvertedMetainfo(bdecode(metainfo))
	    else:
		metainfo = self.metainfo
            self.shortFilename = metainfo.name_fs
	    if not done:
		self.filename = os.path.join(config.get('DataDirectory'),'Incomplete Downloads',self.shortFilename+".part")
		self.filename = self.nextFreeFilename(self.filename)
	    if self.metainfo == None:
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
        self.lock.acquire()
        try:
            self.totalSize = size
        finally:
            self.lock.release()

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
	if self.metainfo != None:
	    self.torrent = self.multitorrent.start_torrent(self.metainfo,
				      self.torrentConfig, self, self.filename)

	    self.get_status()
	else:
	    self.state = "paused"


    def __getstate__(self):
	temp = copy(self.__dict__)
	temp["lock"] = None
	temp["thread"] = None
	try:
	    temp["torrent"] = None
	except:
	    pass
	return temp

    def __setstate__(self,state):
	self.__dict__ = state
	self.lock = RLock()
        self.thread = Thread(target=self.restartDL)
        self.thread.setDaemon(True)
        self.thread.start()

##
# Kill the main BitTorrent thread
#
# This should be called before closing the app
def shutdownBTDownloader():
    BTDownloader.doneflag.set()
    BTDownloader.dlthread.join()

#Spawn the download thread
BTDownloader.dlthread = Thread(target=BTDownloader.multitorrent.rawserver.listen_forever)
BTDownloader.dlthread.start()

class DownloaderFactory:
    def __init__(self,item):
	self.item = item
    def getDownloader(self,url):
	redirURL = url
	(scheme, host, path, params, query, fragment) = urlparse(url)
	conn = HTTPConnection(host)
	if len(params):
	    path += ';'+params
	if len(query):
	    path += '?'+query

	#FIXME: do something smarter on failure
	try:
	    conn.request("HEAD",path)
	except:
	    print "Couldn't connect"
	    return None
	download = conn.getresponse()
	depth = 0
	while download.status != 200 and depth < 10:
	    depth += 1
	    if download.status == 302 or download.status == 307 or download.status == 301:
		info = download.msg
		download.close()
		conn.close()
		redirURL = info['Location']
		if download.status == 301:
		    url = redirURL
		(scheme, host, path, params, query, fragment) = urlparse(info['Location'])
		conn = HTTPConnection(host)
		if len(params):
		    path += ';'+params
		if len(query):
		    path += '?'+query
	        #FIXME: catch exception here
		conn.request("HEAD",path)
		download = conn.getresponse()
	    else:
		print download.status
		return None
	if depth == 10:
	    return None
        info = download.msg
	download.close()
	if info['Content-Type'] == 'application/x-bittorrent':
	    print "Starting BT downloader"
            conn.request("GET",path)
            download = conn.getresponse()
	    metainfo = download.read()
	    conn.close()
	    try:
		metainfo = ConvertedMetainfo(bdecode(metainfo))
		return BTDownloader(url,self.item,metainfo)
	    except BTFailure, e:
		print str(e)
		return None
	else:
	    print "Starting http downloader"
	    return HTTPDownloader(url,self.item,conn,download,redirURL)

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
