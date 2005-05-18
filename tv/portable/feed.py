from formatter import AbstractFormatter, NullWriter
from httplib import HTTPConnection
from htmllib import HTMLParser
import xml
from urlparse import urlparse, urljoin
from urllib import urlopen
from datetime import datetime,timedelta
from database import defaultDatabase
from item import *
from scheduler import ScheduleEvent
from copy import copy
from xhtmltools import unescape,xhtmlify
import os
import config

# Universal Feed Parser http://feedparser.org/
# Licensed under Python license
import feedparser

##
# Generates an appropriate feed for a URL
#
# Eventually, we can use this to determine the type of feed automatically
class FeedFactory:
    def __init__(self, config = None):
        self.config = config
	
    ##
    # Returns an appropriate feed for the given URL
    #
    # @param url The URL of the feed
    def gen(self, url):
        if self.isRSSURL(url):
            return RSSFeed(url)
        else:
            return None

    ##
    # Determines the mime type of the URL
    # Returns true IFF url is RSS URL
    def isRSSURL(self,url):
        return True

##
# A feed contains a set of of downloadable items
class Feed(DDBObject):
    def __init__(self, url, title = None, visible = True):
        self.url = url
        self.items = []
	if title == None:
	    self.title = url
	else:
	    self.title = title
        self.created = datetime.now()
	self.autoDownloadable = False
	self.getEverything = False
	self.maxNew = -1
	self.fallBehind = -1
	self.expire = "system"
        self.updateFreq = 60*60
	self.startfrom = datetime.min
	self.visible = visible
        DDBObject.__init__(self)

    ##
    # Downloads the next available item taking into account maxNew,
    # fallbehind, and getEverything
    def downloadNext(self, dontUse = []):
	self.beginRead()
	try:
	    next = None

	    #The number of items downloading from this feed
	    dling = 0
	    #The number of items eligibile to download
	    eligibile = 0
	    #The number of unwatched, downloaded items
	    newitems = 0

	    #Find the next item we should get
	    for item in self.items:
		if (self.getEverything or item.getPubDateParsed() >= self.startfrom) and item.getState() == "stopped" and not item in dontUse:
		    eligibile += 1
		    if next == None:
			next = item
		    elif item.getPubDateParsed() < next.getPubDateParsed():
			next = item
		if item.getState() == "downloading":
		    dling += 1
		if item.getState() == "finished" or item.getState() == "uploading" and not item.getSeen():
		    newitems += 1

	finally:
	    self.endRead()

	if self.maxNew >= 0 and newItems >= self.maxNew:
	    return False
	elif self.fallBehind>=0 and eligibile > self.fallBehind:
	    dontUse.append(next)
	    return self.downloadNext(dontUse)
	elif next != None:
	    self.beginRead()
	    try:
		self.startfrom = next.getPubDateParsed()
	    finally:
		self.endRead()
	    next.download(autodl = True)
	    return True
	else:
	    return False

    ##
    # Returns marks expired items as expired
    def expireItems(self):
	if self.expire == "feed":
	    expireTime = self.expireTime
	elif self.expire == "system":
	    expireTime = config.get('DefaultTimeUntilExpiration')
	elif self.expire == "never":
	    return
	for item in self.items:
	    if item.getState() == "finished" and datetime.now() - item.getDownloadedTime() > expireTime:
		item.expire()

    ##
    # Returns true iff feed should be visible
    def isVisible(self):
	self.beginRead()
	try:
	    ret = self.visible
	finally:
	    self.endRead()
	return ret

    ##
    # Takes in parameters from the save settings page and saves them
    def saveSettings(self,automatic,maxnew,fallBehind,expire,expireDays,expireHours,getEverything):
	self.beginRead()
	try:
	    self.autoDownloadable = (automatic == "1")
	    self.getEverything = (getEverything == "1")
	    if maxnew == "unlimited":
		self.maxNew = -1
	    else:
		self.maxNew = int(maxnew)
	    if fallBehind == "unlimited":
		self.fallBehind = -1
	    else:
		self.fallBehind = int(fallBehind)
	    self.expire = expire
	    self.expireTime = timedelta(days=int(expireDays),hours=int(expireHours))
	finally:
	    self.endRead()

    ##
    # Returns "feed," "system," or "never"
    def getExpirationType(self):
	self.beginRead()
	ret = self.expire
	self.endRead()
	return ret

    ##
    # Returns"unlimited" or the maximum number of items this feed can fall behind
    def getMaxFallBehind(self):
	self.beginRead()
	if self.fallBehind < 0:
	    ret = "unlimited"
	else:
	    ret = self.fallBehind
	self.endRead()
	return ret

    ##
    # Returns "unlimited" or the maximum number of items this feed wants
    def getMaxNew(self):
	self.beginRead()
	if self.maxNew < 0:
	    ret = "unlimited"
	else:
	    ret = self.maxNew
	self.endRead()
	return ret

    ##
    # Returns the number of days until a video expires
    def getExpireDays(self):
	ret = 0
	self.beginRead()
	try:
	    try:
		ret = self.expireTime.days
	    except:
		ret = config.get('DefaultTimeUntilExpiration').days
	finally:
	    self.endRead()
	return ret

    ##
    # Returns the number of hours until a video expires
    def getExpireHours(self):
	ret = 0
	self.beginRead()
	try:
	    try:
		ret = int(self.expireTime.seconds/3600)
	    except:
		ret = int(config.get('DefaultTimeUntilExpiration').seconds/3600)
	finally:
	    self.endRead()
	return ret
	

    ##
    # Returns true iff item is autodownloadable
    def isAutoDownloadable(self):
        self.beginRead()
        ret = self.autoDownloadable
        self.endRead()
        return ret


    ##
    # Returns the title of the feed
    def getTitle(self):
        self.beginRead()
        ret = self.title
        self.endRead()
        return ret

    ##
    # Returns the URL of the feed
    def getURL(self):
        self.beginRead()
        ret = self.url
        self.endRead()
        return ret

    ##
    # Returns the description of the feed
    def getDescription(self):
        return "<span />"

    ##
    # Returns a link to a webpage associated with the feed
    def getLink(self):
        return ""

    ##
    # Returns the URL of the library associated with the feed
    def getLibraryLink(self):
        return ""

    ##
    # Returns the URL of a thumbnail associated with the feed
    def getThumbnail(self):
	return ""

    ##
    # Returns URL of license assocaited with the feed
    def getLicense(self):
	return ""

    ##
    # Returns the number of new items with the feed
    def getNewItems(self):
        self.beginRead()
	count = 0
	for item in self.items:
	    try:
		if item.getState() == 'finished' and not item.getSeen():
		    count += 1
	    except:
		pass
        self.endRead()
        return count

    ##
    # Removes a feed from the database
    def removeFeed(self,url):
        self.beginRead()
        try:
            for item in self.items:
                item.remove()
        finally:
            self.endRead()
        self.remove()

    ##
    # Called by pickle during serialization
    def __getstate__(self):
	temp = copy(self.__dict__)
	return temp

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
	self.__dict__ = state

class RSSFeed(Feed):
    def __init__(self,url,title = None):
        Feed.__init__(self,url,title)
        self.scheduler = ScheduleEvent(self.updateFreq, self.update)
	self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.feed is self)
        self.scheduler = ScheduleEvent(0, self.update,False)

    ##
    # Returns the description of the feed
    def getDescription(self):
	self.beginRead()
	try:
	    ret = xhtmlify('<span>'+unescape(self.parsed.summary)+'</span>')
	except:
	    ret = "<span />"
	self.endRead()
        return ret

    ##
    # Returns a link to a webpage associated with the feed
    def getLink(self):
	self.beginRead()
	try:
	    ret = self.parsed.link
	except:
	    ret = ""
	self.endRead()
        return ret

    ##
    # Returns the URL of the library associated with the feed
    def getLibraryLink(self):
        self.beginRead()
	try:
	    ret = self.parsed.libraryLink
	except:
	    ret = ""
        self.endRead()
        return ret

    ##
    # Returns the URL of a thumbnail associated with the feed
    def getThumbnail(self):
        self.beginRead()
	try:
	    ret = self.parsed.image.url
	except:
	    ret = ""
        self.endRead()
        return ret
	

    ##
    # Updates a feed
    def update(self):
	try:
	    d = feedparser.parse(self.url,etag=self.parsed.etag,modified=self.parsed.modified)
	    if d.status == 304:
		return ""
	    else:
		self.parsed = d
	except:
	    self.parsed = feedparser.parse(self.url)
        self.beginRead()
        try:
	    try:
		if self.parsed.status == 301: #permanent redirect
                    self.url = self.parsed.url
	    except:
		pass
            try:
                self.title = self.parsed["feed"]["title"]
            except KeyError:
                try:
                    self.title = self.parsed["channel"]["title"]
                except KeyError:
                    pass
            for entry in self.parsed.entries:
                new = True
                for item in self.items:
                    try:
                        if item.getRSSID() == entry["id"]:
                            item.update(entry)
                            new = False
                    except KeyError:
                        # If the item changes at all, it results in a
                        # new entry
                        if (item.getRSSEntry() == entry):
                            item.update(entry)
                            new = False
                if new:
                    self.items.append(Item(self,entry))
            try:
                self.updateFreq = min(15*60,self.parsed["feed"]["ttl"]*60)
            except KeyError:
                self.updateFreq = 60*60
        finally:
            self.endRead()
	    self.beginChange()
	    self.endChange()
    ##
    # Overrides the DDBObject remove()
    def remove(self):
        self.scheduler.remove()
        Feed.remove(self)

    ##
    # Returns the URL of the license associated with the feed
    def getLicense(self):
	try:
	    ret = self.parsed.license
	except:
	    ret = ""
	return ret

    ##
    # Called by pickle during serialization
    def __getstate__(self):
	temp = copy(self.__dict__)
	temp["itemlist"] = None
	temp["scheduler"] = None
	return temp

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
	self.__dict__ = state
	self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.feed is self)
        self.scheduler = ScheduleEvent(self.updateFreq, self.update)

	#FIXME: the update dies if all of the items aren't restored, so we 
        # wait a little while before we start the update
        self.scheduler = ScheduleEvent(5, self.update,False)

##
# A DTV Collection of items -- similar to a playlist
class Collection(Feed):
    def __init__(self,title = None):
        Feed.__init__(self,url = "dtv:collection",title = title,visible = False)

    ##
    # Adds an item to the collection
    def addItem(self,item):
	if isinstance(item,Item):
	    self.beginRead()
	    try:
		self.removeItem(item)
		self.items.append(item)
	    finally:
		self.endRead()
	    return True
	else:
	    return False

    ##
    # Moves an item to another spot in the collection
    def moveItem(self,item,pos):
	self.beginRead()
	try:
	    self.removeItem(item)
	    if pos < len(self.items):
		self.items[pos:pos] = [item]
	    else:
		self.items.append(item)
	finally:
	    self.endRead()

    ##
    # Removes an item from the collection
    def removeItem(self,item):
	self.beginRead()
	try:
	    for x in range(0,len(self.items)):
		if self.items[x] == item:
		    self.items[x:x+1] = []
		    break
	finally:
	    self.endRead()
	return True

##
# A feed based on un unformatted HTML or pre-enclosure RSS
#
# 
class ScraperFeed(Feed):
    def __init__(self,url,title = None, visible = True):
	Feed.__init__(self,url,title,visible)
	self.scheduler = ScheduleEvent(self.updateFreq, self.update)
	self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.feed is self)
	self.scheduler = ScheduleEvent(0, self.update,False)
	self.mainHTML = ''
	self.secondaryHTML = {}

    def getMimeType(self,link):
	(linkScheme, linkHost, linkPath, linkParams, linkQuery, linkFragment) = urlparse(link)
	if len(linkParams):
	    linkPath += ';'+linkParams
	if len(linkQuery):
	    linkPath += '?'+linkQuery
	linkConn = HTTPConnection(linkHost)
	linkConn.connect()
	try:
	    linkConn.request('HEAD',linkPath)
	    linkDownload = linkConn.getresponse()
	except:
	    linkConn.close()
	    return None
	depth = 0
	while linkDownload.status != 200 and depth < 10:
	    depth += 1
	    if linkDownload.status == 302 or linkDownload.status == 307 or linkDownload.status == 301:
		info = linkDownload.msg
		linkDownload.close()
		linkConn.close()
		redirURL = info['Location']
		if linkDownload.status == 301:
		    link = redirURL
		(linkScheme, linkHost, linkPath, linkParams, linkQuery, linkFragment) = urlparse(info['Location'])
		linkConn = HTTPConnection(linkHost)
		if len(linkParams):
		    linkPath += ';'+linkParams
		if len(linkQuery):
		    linkPath += '?'+linkQuery
		try:
		    linkConn.request('HEAD',linkPath)
		except:
		    linkConn.close()
		    return None
		linkDownload = linkConn.getresponse()
	    else:
		return None
	info = linkDownload.msg
	linkDownload.close()
	return info['Content-Type']

    ##
    # returns a tuple containing the text of the URL, the url (in case
    # of a permanent redirect), and a redirected URL (in case of
    # temporary redirect)
    def getHTML(self, url):
	redirURL = url
	(scheme, host, path, params, query, fragment) = urlparse(url)
	conn = HTTPConnection(host)
	conn.connect()
	if len(params):
	    path += ';'+params
	if len(query):
	    path += '?'+query
	conn.request('GET',path)
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
		conn.request("GET",path)
		download = conn.getresponse()
	    else:
		return (None, url, redirURL)
	html = download.read()
	download.close()
	conn.close()
	return (html, url, redirURL)

    def addVideoItem(self,link,title):
	link = link.strip()
	for item in self.items:
	    if item.getURL() == link:
		return
	if len(title) > 0:
	    i=Item(self, FeedParserDict({'title':title,'enclosures':[FeedParserDict({'url':link})]}))
	else:
	    i=Item(self, FeedParserDict({'title':link,'enclosures':[FeedParserDict({'url':link})]}))
	self.items.append(i)
	self.beginChange()
	self.endChange()

    #FIXME: compound names for titles at each depth
    def processLinks(self,links, depth = 0):
	if depth<2:
	    for (link, title) in links:
		#FIXME keep the connection open
		mimetype = self.getMimeType(link)
		if mimetype != None:
                     #This is text of some sort: HTML, XML, etc.
		    if mimetype[0:9] == 'text/html' or mimetype[0:21] == 'application/xhtml+xml' or mimetype[0:9] == 'text/xml' or mimetype[0:15] == 'application/xml':
			(html, url, redirURL) = self.getHTML(link)
			subLinks = self.scrapeLinks(html, redirURL)
			self.processLinks(subLinks, depth+1)
		    #This is probably a video
		    else:
			self.addVideoItem(link, title)


    #FIXME: go through and add error handling
    #FIXME: perform HTTP caching
    def update(self):
	(self.mainHTML,self.url, redirURL) = self.getHTML(self.url)
	links = self.scrapeLinks(self.mainHTML, redirURL)
	self.processLinks(links)
	#Download the HTML associated with each page

    def scrapeLinks(self,html,baseurl):
	try:
	    handler = RSSLinkGrabber(html,baseurl)
	    xml.sax.parseString(html,handler)
	    links = handler.links
	    links2 = []
	    for link in links:
		if link[0][0:7] == 'http://':
		    links2.append((link[0],link[1].strip()))
	    return links2
	except xml.sax.SAXNotRecognizedException:
	    return self.scrapeHTMLLinks(html,baseurl)
	except xml.sax.SAXParseException:	    
	    return self.scrapeHTMLLinks(html,baseurl)
    ##
    # Given a string containing an HTML file, return a list of tuples
    # of titles and links
    def scrapeHTMLLinks(self,html, baseurl):
	lg = HTMLLinkGrabber(AbstractFormatter(NullWriter))
	links = lg.getLinks(html, baseurl)
	links2 = []
	for link in links:
	    if link[0][0:7] == 'http://':
		links2.append((link[0],link[1].strip()))
	return links2
	
    ##
    # Called by pickle during serialization
    def __getstate__(self):
	temp = copy(self.__dict__)
	temp["itemlist"] = None
	temp["scheduler"] = None
	return temp

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
	self.__dict__ = state
	self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.feed is self)
        self.scheduler = ScheduleEvent(self.updateFreq, self.update)

	#FIXME: the update dies if all of the items aren't restored, so we 
        # wait a little while before we start the update
        self.scheduler = ScheduleEvent(5, self.update,False)


##
# A feed of all of the Movies we find in the movie folder that don't
# belong to a "real" feed
#
# FIXME: How do we trigger updates on this feed?
class DirectoryFeed(Feed):
    def __init__(self):
        Feed.__init__(self,url = "dtv:directoryfeed",title = "Feedless Videos",visible = False)

	#A database query of all of the filenames of all of the downloads
	self.RSSFilenames = defaultDatabase.filter(lambda x:isinstance(x,Item) and isinstance(x.feed,RSSFeed)).map(lambda x:x.getFilenames())
	self.updateFreq = 30
        self.scheduler = ScheduleEvent(self.updateFreq, self.update,True)
	self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,FileItem) and x.feed is self)
        self.scheduler = ScheduleEvent(0, self.update,False)
    ##
    # Returns a list of all of the files in a given directory
    def getFileList(self,dir):
	allthefiles = []
	for root, dirs, files in os.walk(dir,topdown=True):
	    if root == dir and 'Incomplete Downloads' in dirs:
		dirs.remove('Incomplete Downloads')
	    toRemove = []
	    for curdir in dirs:
		if curdir[0] == '.':
		    toRemove.append(curdir)
	    for curdir in toRemove:
		dirs.remove(curdir)
	    toRemove = []
	    for curfile in files:
		if curfile[0] == '.':
		    toRemove.append(curfile)
	    for curfile in toRemove:
		files.remove(curfile)
	    
	    allthefiles[:0] = map(lambda x:os.path.normcase(os.path.join(root,x)),files)
	return allthefiles

    def update(self):
	knownFiles = []
	self.beginRead()
	try:
	    #Files on the filesystem
	    existingFiles = self.getFileList(config.get('DataDirectory'))
	    #Files known about by real feeds
	    for item in self.RSSFilenames:
		knownFiles[:0] = item
	    knownFiles = map(os.path.normcase,knownFiles)

	    #Remove items that are in feeds, but we have in our list
	    for x in range(0,len(self.items)):
		try:
		    while (self.items[x].getFilename() in knownFiles) or (not self.items[x].getFilename() in existingFiles):
			self.items[x].remove()
			self.items[x:x+1] = []
		except IndexError:
		    pass

	    #Files on the filesystem that we known about
	    myFiles = map(lambda x:x.getFilename(),self.items)

	    #Adds any files we don't know about
	    for file in existingFiles:
		if not file in knownFiles and not file in myFiles:
		    self.items.append(FileItem(self,file))
		    
	finally:
	    self.endRead()

    ##
    # Called by pickle during serialization
    def __getstate__(self):
	temp = copy(self.__dict__)
	temp["itemlist"] = None
	temp["scheduler"] = None
	return temp

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
	self.__dict__ = state
	self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,FileItem) and x.feed is self)
        self.scheduler = ScheduleEvent(self.updateFreq, self.update)

	#FIXME: the update dies if all of the items aren't restored, so we 
        # wait a little while before we start the update
        self.scheduler = ScheduleEvent(5, self.update,False)

##
# Parse HTML document and grab all of the links and their title
# FIXME: get titles from a tag, then title. Get thumbnail from img
#        inside a tag
class HTMLLinkGrabber(HTMLParser):
    def getLinks(self,data, baseurl):
	self.links = []
	self.lastLink = None
	self.inLink = False
	self.inObject = False
	self.baseurl = baseurl
	self.feed(data)
	self.close()
	return self.links

    #FIXME Handle title and baseurl
    def handle_starttag(self, tag, method, attrs):
	if tag.lower() == 'object':
	    self.inObject = True
	elif tag.lower() == 'a':
	    for attr in attrs:
		if attr[0].lower() == 'href':
		    self.links.append( (urljoin(self.baseurl,attr[1]),''))
		    self.inLink = True
		    break
	elif tag.lower() == 'embed':
		for attr in attrs:
		    if attr[0].lower() == 'src':
			self.links.append( (urljoin(self.baseurl,attr[1]),''))
			break
	elif tag.lower() == 'param' and self.inObject:
	    srcParam = False
	    for attr in attrs:
		if attr[0].lower() == 'name' and attr[1].lower() == 'src':
		    srcParam = True
		    break
	    if srcParam:
		for attr in attrs:
		    if attr[0].lower() == 'value':
			self.links.append( (urljoin(self.baseurl,attr[1]),''))
			break
		
    def handle_endtag(self, tag, method):
	if tag.lower() == 'a':
	    if self.inLink:
		if len(self.links[-1][1]) == 0:
		    self.links[-1] = (self.links[-1][0], self.links[-1][0])
		    self.inLink = False
	if tag.lower() == 'object':
	    self.inObject = False
    def handle_data(self, data):
	if self.inLink:
	    self.links[-1] = (self.links[-1][0],self.links[-1][1]+data)

##
# Get title from item title
class RSSLinkGrabber(xml.sax.handler.ContentHandler):
    def __init__(self,html,baseurl):
	self.html = html
	self.baseurl = baseurl
    def startDocument(self):
	self.links = []
	self.inLink = False
	self.inDescription = True
	self.descHTML = ''
	self.theLink = ''
	self.firstTag = True

    def startElement(self, tag, attrs):
	if self.firstTag:
	    self.firstTag = False
	    if tag != 'rss':
		raise xml.sax.SAXNotRecognizedException, "Not an RSS file"
	if tag.lower() == 'link':
	    self.inLink = True
	    self.theLink = ''
	    return
	elif tag.lower() == 'description':
	    self.inDescription = True
	    self.descHTML = ''
		
    def endElement(self, tag):
	if tag.lower() == 'description':
	    lg = HTMLLinkGrabber(self.html,self.baseurl)
	    self.links[:0] = lg.getLinks(unescape(self.descHTML),self.baseurl)
	    self.inDescription = False
	elif tag.lower() == 'link':
	    self.links.append((self.theLink,self.theLink))
	    self.inLink = False
    def characters(self, data):
	if self.inDescription:
	    self.descHTML += data
	elif self.inLink:
	    self.theLink += data
