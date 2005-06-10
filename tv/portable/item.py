from datetime import datetime
from database import DDBObject
from downloader import DownloaderFactory
from copy import copy
from xhtmltools import unescape,xhtmlify
from scheduler import ScheduleEvent
from feedparser import FeedParserDict

##
# An item corresponds to a single entry in a feed. Generally, it has
# a single url associated with ti
#
# Item data is accessed by using the item as a dict. We use the same
# structure as the universal feed parser entry structure.
class Item(DDBObject):
    def __init__(self, feed, entry):
        self.feed = feed
        self.seen = False
        self.exirpiration = datetime.now()
        self.downloaders = []
        self.vidinfo = None
        self.autoDownloaded = False
	self.startingDownload = False
	self.lastDownloadFailed = False
        self.entry = entry
	self.dlFactory = DownloaderFactory(self)
	self.expired = False
        DDBObject.__init__(self)

    ##
    # Returns the URL associated with the first enclosure in the item
    def getURL(self):
	ret = ''
	self.beginRead()
	try:
	    ret = self.entry.enclosures[0].url
	finally:
	    self.endRead()
	return ret
    ##
    # Returns the feed this item came from
    def getFeed(self):
        self.beginRead()
        ret = self.feed
        self.endRead()
        return ret

    ##
    # Returns the number of videos associated with this item
    def getAvailableVideos(self):
	ret = 0
	self.beginRead()
	try:
	    ret = len(self.entry.enclosures)
	finally:
	    self.endRead()
	return ret

    ##
    # Marks this item as expired
    def expire(self):
        self.beginRead()
	try:
	    self.stopDownload()
	    self.markItemSeen()
	    self.expired = True
	finally:
	    self.endRead()	

    ##
    # returns true iff item has been seen
    def getSeen(self):
        self.beginRead()
        ret = self.seen
        self.endRead()
        return ret

    ##
    # Marks the item as seen
    def markItemSeen(self):
        self.beginRead()
        self.seen = True
        self.endRead()

    ##
    # Returns a list of downloaders associated with this object
    def getDownloaders(self):
        self.beginRead()
        ret = self.downloaders
        self.endRead()
        return ret

    def getRSSID(self):
	self.beginRead()
	try:
	    ret = self.entry["id"]
	finally:
	    self.endRead()
	return ret

    ##
    # Returns the vidinfo object associated with this item
    def getVidInfo(self):
        self.beginRead()
        ret = self.vidinfo
        self.endRead()
        return ret

    def setAutoDownloaded(self,autodl = True):
	self.beginRead()
	self.autoDownloaded = autodl
	self.endRead()

    ##
    # Returns true iff item was auto downloaded
    def autoDownloaded(self):
        self.beginRead()
        ret = self.autoDownloaded
        self.endRead()
        return ret

    def download(self,autodl=False):
	ScheduleEvent(0,lambda:self.actualDownload(autodl),False)

    ##
    # Starts downloading the item
    def actualDownload(self,autodl=False):
        self.beginRead()
        try:
	    self.setAutoDownloaded(autodl)
	    self.lastDownloadFailed = False
            downloadURLs = map(lambda x:x.getURL(),self.downloaders)
	    self.startingDownload = True
	    try:
		enclosures = self.entry["enclosures"]
	    except:
		enclosures = []
        finally:
            self.endRead()
	self.beginChange()
	self.endChange()
	try:
	    for enclosure in enclosures:
		try:
		    if not enclosure["url"] in downloadURLs:
			dler = self.dlFactory.getDownloader(enclosure["url"])
			if dler != None:
			    self.beginRead()
			    try:
				self.downloaders.append(dler)
			    finally:
				self.endRead()
			else:
			    self.beginRead()
			    try:
				self.lastDownloadFailed = True
			    finally:
				self.endRead()
		except KeyError:
		    pass
	except KeyError:
	    pass
        self.beginRead()
        try:
	    self.startingDownload = False
        finally:
            self.endRead()
	self.beginChange()
	self.endChange()

    ##
    # Returns a link to the thumbnail of the video
    def getThumbnail(self):
	ret = "resource:images/thumb.gif"	
        self.beginRead()
	try:
	    try:
		for enc in self.entry.enclosures:
		    try:
			ret = enc["thumbnail"]["url"]
			break
		    except:
			pass
	    except:
		try:
		    ret =  self.entry["thumbnail"]["url"]
		except:
		    pass
	    return ret
	finally:
	    self.endRead()

    ##
    # returns the title of the item
    def getTitle(self):
	self.beginRead()
	try:
	    ret = self.entry.title
	except:
	    try:
		ret = self.entry.enclosures[0]["url"]
	    except:
		ret = ""
	self.endRead()
	return ret

    ##
    # Returns valid XHTML containing a description of the video
    def getDescription(self):
	self.beginRead()
	try:
	    ret = xhtmlify('<span>'+unescape(self.entry.enclosures[0]["text"])+'</span>')
	except:
	    try:
		ret = xhtmlify('<span>'+unescape(self.entry.description)+'</span>')
	    except:
		ret = '<span />'
	self.endRead()
	return ret

    ##
    # Stops downloading the item
    def stopDownload(self):
	for dler in self.downloaders:
	    dler.stop()
	    dler.remove()
        self.beginRead()
        try:
	    self.downloaders = []
        finally:
            self.endRead()

    ##
    # returns status of the download in plain text
    def getState(self):
	self.beginRead()
	try:
	    if self.expired:
		state = "expired"
	    elif self.startingDownload:
		state = "downloading"
	    elif len(self.downloaders) == 0:
		if self.lastDownloadFailed:
		    state = "failed"
		else:
		    state = "stopped"
	    else:
		state = "finished"
		for dler in self.downloaders:
		    newState = dler.getState()
		    if newState != "finished":
			state = newState
		    if state == "failed":
			break
	finally:
	    self.endRead()
	return state

    ##
    # returns status of the download in plain text
    def getTotalSize(self):
	size = 0
	for dler in self.downloaders:
	    try:
		size += dler.getTotalSize()
	    except:
		pass
	if size == 0:
	    return ""
	mb = size / 1000000
	if mb <  100:
	    return '%1.1f' % mb + " MB"
	elif mb < 1000:
	    return '%1.0f' % mb + " MB"
	else:
	    return '%1.1f' % (mb/1000) + " GB"
	return size

    ##
    # returns status of the download in plain text
    def getCurrentSize(self):
	size = 0
	for dler in self.downloaders:
	    size += dler.getCurrentSize()
	if size == 0:
	    return ""
	mb = size / 1000000
	if mb <  100:
	    return '%1.1f' % mb + " MB"
	elif mb < 1000:
	    return '%1.0f' % mb + " MB"
	else:
	    return '%1.1f' % (mb/1000) + " GB"
	return size

    ##
    # returns string with estimate time until download completes
    def downloadETA(self):
	secs = 0
	for dler in self.downloaders:
	    secs += dler.getETA()
	if (secs < 120):
	    return '%1.0f' % secs+" secs"
	elif (secs < 6000):
	    return '%1.0f' % (secs/60)+" mins"
	else:
	    return '%1.1f' % (secs/3600)+" hours"

    ##
    # Returns the published date of the item
    def getPubDate(self):
	self.beginRead()
	try:
	    try:
		ret = datetime(*self.entry.modified_parsed[0:7]).strftime("%b %d %Y")
	    except:
		ret = ""
        finally:
	    self.endRead()
	return ret
    
    ##
    # Returns the published date of the item as a datetime object
    def getPubDateParsed(self):
	self.beginRead()
	try:
	    try:
		ret = datetime(*self.entry.modified_parsed[0:7])
	    except:
		ret = ""
        finally:
	    self.endRead()
	return ret

    ##
    # returns the date this video was released or when it was published
    def getReleaseDate(self):
        if hasattr(self,'releaseDate'):
            return self.releaseDate            
	self.beginRead()
	try:
	    try:
		self.releaseDate = datetime(*self.entry.enclosures[0].modified_parsed[0:7]).strftime("%b %d %Y")
	    except:
		try:
		    self.releaseDate = datetime(*self.entry.modified_parsed[0:7]).strftime("%b %d %Y")
		except:
		    self.releaseDate = ""
	finally:
	    self.endRead()
	return self.releaseDate

    ##
    # returns string with the play length of the video
    def getDuration(self):
	secs = 0
	#FIXME get this from VideoInfo
	if secs == 0:
	    return ""
	if (secs < 120):
	    return '%1.0f' % secs+" secs"
	elif (secs < 6000):
	    return '%1.0f' % (secs/60)+" mins"
	else:
	    return '%1.1f' % (secs/3600)+" hours"

    ##
    # return keyword tags associated with the video separated by commas
    def getTags(self):
	self.beginRead()
	try:
	    try:
		ret = self.entry.categories.join(", ")
	    except:
		ret = ""
	finally:
	    self.endRead()
	return ret

    ##
    # return the license associated with the video
    def getLicence(self):
	self.beginRead()
	try:
	    try:
		ret = self.entry.license
	    except:
		try:
		    ret = self.feed.getLicense()
		except:
		    ret = ""
	finally:
	    self.endRead()
	return ret

    ##
    # return the people associated with the video, separated by commas
    def getPeople(self):
	ret = []
	self.beginRead()
	try:
	    try:
		for role in self.entry.enclosures[0].roles:
		    for person in self.entry.enclosures[0].roles[role]:
			ret.append(person)
		for role in self.entry.roles:
		    for person in self.entry.roles[role]:
			ret.append(person)
	    except:
		pass
	finally:
	    self.endRead()
	return ret.join(', ')

    ##
    # returns the URL of the webpage associated with the item
    def getLink(self):
	self.beginRead()
	try:
	    try:
		ret = self.entry.link
	    except:
		ret = ""
	finally:
	    self.endRead()
	return ret

    ##
    # returns the URL of the payment page associated with the item
    def getPaymentLink(self):
	self.beginRead()
	try:
	    try:
		ret = self.entry.enclosures[0].payment_url
	    except:
		try:
		    ret = self.entry.payment_url
		except:
		    ret = ""
	finally:
	    self.endRead()
	return ret

    ##
    # returns a snippet of HTML containing a link to the payment page
    # HTML has already been sanitized by feedparser
    def getPaymentHTML(self):
	self.beginRead()
	try:
	    try:
		ret = self.entry.enclosures[0].payment_html
	    except:
		try:
		    ret = self.entry.payment_html
		except:
		    ret = ""
	finally:
	    self.endRead()
	return '<span>'+ret+'</span>'

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

    ##
    # marks the item as having been downloaded now
    def setDownloadedTime(self):
	self.beginRead()
	try:
	    self.downloadedTime = datetime.now()
	finally:
	    self.endRead()

    ##
    # gets the time the video was downloaded
    # Only valid if the state of this item is "finished"
    def getDownloadedTime(self):
	self.beginRead()
	try:
	    try:
		ret = self.downloadedTime
	    except:
		ret = datetime.min
	finally:
	    self.endRead()
	return ret

    ##
    # gets the time the video started downloading
    def getDLStartTime(self):
	self.beginRead()
	try:
	    try:
		ret = self.DLStartTime
	    except:
		ret = None
	finally:
	    self.endRead()
	return ret

    ##
    # Returns the filename of the first downloaded video or the empty string
    def getFilename(self):
	self.beginRead()
	try:
	    try:
		ret = self.downloaders[0].getFilename()
	    except:
		ret = ""
	finally:
	    self.endRead()
	return ret

    ##
    # Returns a list with the filenames of all of the videos in the item
    def getFilenames(self):
	ret = []
	self.beginRead()
	try:
	    try:
		for dl in self.downloaders:
		    ret.append(dl.getFilename())
	    except:
		pass
	finally:
	    self.endRead()
	return ret

    def getRSSEntry(self):
	self.beginRead()
	try:
	    ret = self.entry
	finally:
	    self.endRead()
	return ret

    ##
    # Called by pickle during serialization
    def __getstate__(self):
	temp = copy(self.__dict__)
	return (0,temp)

    ##
    # Called by pickle during serialization
    def __setstate__(self,state):
        (version, data) = state
        assert(version == 0)
	self.__dict__ = data

##
# An Item that exists as a file, but not as a download
class FileItem(Item):
    def getEntry(self,filename):
	return FeedParserDict({'title':filename,'enclosures':[{'url':filename}]})

    def __init__(self,feed,filename):
	Item.__init__(self,feed,self.getEntry(filename))
	self.filename = filename

    def getState(self):
	return "finished"

    def getDownloadedTime(self):
	self.beginRead()
	try:
	    try:
		time = datetime.fromtimestamp(os.getctime(self.filename))
	    except:
		return datetime.min
	finally:
	    self.endRead()

    def getFilename(self):
	return self.filename

    def getFilenames(self):
	return [self.filename]
