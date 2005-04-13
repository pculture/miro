from datetime import datetime
from database import DDBObject
from threading import RLock
from downloader import DownloaderFactory
from copy import copy

##
# An item corresponds to a single entry in a feed. Generally, it has
# a single url associated with ti
#
# Item data is accessed by using the item as a dict. We use the same
# structure as the universal feed parser entry structure.
class Item(DDBObject):
    def __init__(self, feed, entry, autodl = True):
        self.feed = feed
        self.seen = False
        self.state =  'unselected'
	self.downloadTime = datetime.now()
        self.exirpiration = datetime.now()
        self.downloaders = []
        self.vidinfo = None
        self.autoDownloadable = autodl
        self.autoDownloaded = False
        self.entry = entry
        self.lock = RLock()
	self.dlFactory = DownloaderFactory(self)
        DDBObject.__init__(self)

    ##
    # Returns the feed this item came from
    def getFeed(self):
        self.lock.acquire()
        ret = self.feed
        self.lock.release()
        return ret

    ##
    # returns true iff item has been seen
    def getSeen(self):
        self.lock.acquire()
        ret = self.seen
        self.lock.release()
        return ret

    ##
    # Marks the item as seen
    def markItemSeen(self):
        self.lock.acquire()
        self.seen = True
        self.lock.release()

    ##
    # Gets the state of this item
    def getState(self):
        ret = None
        self.lock.acquire()
        try:
            if self.state in ['unselected','unwatched','expirable','saved','expired','deleted']:
                ret = self.state
        finally:
            self.lock.release()
        return ret

    ##
    # Sets the state of this item
    def setState(self,state):
        if not state in ['unselected','unwatched','expirable','saved','expired','deleted']:
            raise TypeError
        else:
            self.lock.acquire()
            self.state = state
            self.lock.release()

    ##
    # Gets the expiration time for this item
    def getExpiration(self):
        self.lock.acquire()
        ret = self.expiration
        self.lock.release()
        return ret

    ##
    # Sets the expiration time for this item
    def setExpiration(self, exp):
        if exp.__class__.__name__ != 'datetime':
            raise TypeError
        else:
            self.lock.acquire()
            self.expiration = exp
            self.lock.release()

    ##
    # Returns the item data associated with n
    def __getitem__(self,n):
        ret = None
        self.lock.acquire()
        try:
            ret = self.entry[n]
        finally:
            self.lock.release()
        return ret

    ##
    # Returns the item data associated with n
    def __getattr__(self,n):
        ret = None
	if not (self.lock == None):
	    self.lock.acquire()
        try:
	    try:
		ret = self.entry[n]
	    except KeyError:
		raise AttributeError
        finally:
	    if not (self.lock == None):
		self.lock.release()
        return ret

    ##
    # Returns a list of downloaders associated with this object
    def getDownloaders(self):
        self.lock.acquire()
        ret = self.downloaders
        self.lock.release()
        return ret

    ##
    # Returns the vidinfo object associated with this item
    def getVidInfo(self):
        self.lock.acquire()
        ret = self.vidinfo
        self.lock.release()
        return ret

    ##
    # Returns true iff item is autodownloadable
    def isAutoDownloadable(self):
        self.lock.acquire()
        ret = self.autoDownloadable
        self.lock.release()
        return ret

    ##
    # Returns true iff item was auto downloaded
    def autoDownloaded(self):
        self.lock.acquire()
        ret = self.autoDownloaded
        self.lock.release()
        return ret

    ##
    # Starts downloading the item
    def download(self):
        self.lock.acquire()
        try:
            downloadURLs = map(lambda x:x.getURL(),self.downloaders)
	    try:
		for enclosure in self.entry["enclosures"]:
		    try:
			if not enclosure["url"] in downloadURLs:
			    dler = self.dlFactory.getDownloader(enclosure["url"])
			    if dler != None:
				self.downloaders.append(dler)
		    except KeyError:
			pass
	    except KeyError:
		pass
        finally:
            self.lock.release()

    ##
    # Stops downloading the item
    def stopDownload(self):
        self.lock.acquire()
        try:
	    for dler in self.downloaders:
		dler.stop()
	    self.downloaders = []
        finally:
            self.lock.release()
    
    ##
    # returns status of the download in plain text
    def downloadState(self):
	if len(self.downloaders) == 0:
	    state = "stopped"
	else:
	    state = "finished"
	    for dler in self.downloaders:
		newState = dler.getState()
		if newState == "failed":
		    return "failed"
		elif newState != "finished":
		    state = newState
	return state

    ##
    # returns status of the download in plain text
    def downloadState(self):
	if len(self.downloaders) == 0:
	    state = "stopped"
	else:
	    state = "finished"
	    for dler in self.downloaders:
		newState = dler.getState()
		if newState == "failed":
		    return "failed"
		elif newState != "finished":
		    state = newState
	return state

    ##
    # returns status of the download in plain text
    def downloadTotalSize(self):
	size = 0
	for dler in self.downloaders:
	    size += dler.getTotalSize()
	return size

    ##
    # returns status of the download in plain text
    def downloadCurrentSize(self):
	size = 0
	for dler in self.downloaders:
	    size += dler.getCurrentSize()
	return size

    ##
    # returns string with estimate time until download completes
    def downloadETA(self):
	secs = 0
	for dler in self.downloaders:
	    secs += dler.getETA()
	if (secs < 120):
	    return "~"+'%1.1f' % secs+" secs"
	elif (secs < 6000):
	    return "~"+'%1.1f' % (secs/60)+" mins"
	else:
	    return "~"+'%1.1f' % (secs/3600)+" hours"

    ##
    # Updates an item with new data
    #
    # @param entry a dict object containing the new data
    def update(self, entry):
        self.beginChange()
        try:
            self.entry = entry
        finally:
            self.endChange()

    def getFilenameHack(self):
	return self.downloaders[0].getFilename()

    ##
    # Called by pickle during serialization
    def __getstate__(self):
	temp = copy(self.__dict__)
	temp["lock"] = None
	return temp

    ##
    # Called by pickle during serialization
    def __setstate__(self,state):
	self.__dict__ = state
	self.lock = RLock()
