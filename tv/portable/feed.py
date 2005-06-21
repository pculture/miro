from downloader import grabURL
from HTMLParser import HTMLParser,HTMLParseError
import xml
from urlparse import urlparse, urljoin
from urllib import urlopen
from datetime import datetime,timedelta
from database import defaultDatabase
from item import *
from scheduler import ScheduleEvent
from copy import copy
from xhtmltools import unescape,xhtmlify,fixXMLHeader, fixHTMLHeader, toUTF8Bytes
from cStringIO import StringIO
from threading import Thread, Semaphore
import traceback #FIXME get rid of this
import os
import config
import re

# Notes on character set encoding of feeds:
#
# The parsing libraries built into Python mostly use byte strings
# instead of unicode strings.  However, sometimes they get "smart" and
# try to convert the byte stream to a unicode stream automatically.
#
# What does what when isn't clearly documented
#
# We use the function toUTF8Bytes() to fix those smart conversions
#
# If you run into Unicode crashes, adding that function in the
# appropriate place should fix it.

# Universal Feed Parser http://feedparser.org/
# Licensed under Python license
import feedparser

# Pass in a connection to the frontend
def setDelegate(newDelegate):
    global delegate
    delegate = newDelegate

#
# Adds a new feed using USM
def addFeedFromFile(file):
    d = feedparser.parse(file)
    if d.feed.has_key('links'):
        for link in d.feed['links']:
            if link['rel'] == 'start':
                generateFeed(link['href'])
                return
    if d.feed.has_key('link'):
        addFeedFromWebPage(d.feed.link)

#
# Adds a new feed based on a link tag in a web page
def addFeedFromWebPage(url):
    feedURL = getFeedURLFromWebPage(url)
    if not feedURL is None:
        generateFeed(feedURL)

def getFeedURLFromWebPage(url):
    data = ''
    info = grabURL(url,"GET")
    if info is None:
        return None
    try:
        data = info['file-handle'].read()
        info['file-handle'].close()
    except:
        pass
    return HTMLFeedURLParser().getLink(info['updated-url'],data)

##
# Generates an appropriate feed for a URL
#
# @param url The URL of the feed
def generateFeed(url):
    thread = Thread(target=lambda: _generateFeed(url))
    thread.setDaemon(False)
    thread.start()

def _generateFeed(url):
    info = grabURL(url,"GET")
    if info is None:
        return None
    try:
        modified = info['last-modified']
    except KeyError:
        modified = None
    try:
        etag = info['etag']
    except KeyError:
        etag = None
    #Definitely an HTML feed
    if (info['content-type'].startswith('text/html') or 
        info['content-type'].startswith('application/xhtml+xml')):
        #print "Scraping HTML"
        html = info['file-handle'].read()
        if info.has_key('charset'):
            html = fixHTMLHeader(html,info['charset'])
            charset = info['charset']
        else:
            charset = None
        info['file-handle'].close()
        if delegate.isScrapeAllowed(url):
            return ScraperFeed(info['updated-url'],initialHTML=html,etag=etag,modified=modified, charset=charset)
        else:
            return None

    #It's some sort of feed we don't know how to scrape
    elif (info['content-type'].startswith('application/rdf+xml') or
          info['content-type'].startswith('application/atom+xml')):
        #print "ATOM or RDF"
        html = info['file-handle'].read()
        info['file-handle'].close()
        if info.has_key('charset'):
            xmldata = fixXMLHeader(html,info['charset'])
        else:
            xmldata = html
        return RSSFeed(info['updated-url'],initialHTML=xmldata,etag=etag,modified=modified)
    # If it's not HTML, we can't be sure what it is.
    #
    # If we get generic XML, it's probably RSS, but it still could be
    # XHTML.
    #
    # application/rss+xml links are definitely feeds. However, they
    # might be pre-enclosure RSS, so we still have to download them
    # and parse them before we can deal with them correctly.
    elif (info['content-type'].startswith('application/rss+xml') or
          info['content-type'].startswith('text/xml') or 
          info['content-type'].startswith('application/xml')):
        #print " It's doesn't look like HTML..."
        html = info["file-handle"].read()
        info["file-handle"].close()
        if info.has_key('charset'):
            xmldata = fixXMLHeader(html,info['charset'])
            html = fixHTMLHeader(html,info['charset'])
            charset = info['charset']
        else:
            xmldata = html
            charset = None
        try:
            parser = xml.sax.make_parser()
            parser.setFeature(xml.sax.handler.feature_namespaces, 1)
            handler = RSSLinkGrabber(info['redirected-url'],charset)
            parser.setContentHandler(handler)
            parser.parse(StringIO(xmldata))
        except xml.sax.SAXException: #it doesn't parse as RSS, so it must be HTML
            #print " Nevermind! it's HTML"
            if delegate.isScrapeAllowed(url):
                 return ScraperFeed(info['updated-url'],initialHTML=html,etag=etag,modified=modified, charset=charset)
            else:
                 return None
        except UnicodeDecodeError:
            print "Unicode issue parsing... %s" % xmldata[0:300]
	    traceback.print_exc()
            return None
        if handler.enclosureCount > 0 or handler.itemCount == 0:
            #print " It's RSS with enclosures"
            return RSSFeed(info['updated-url'],initialHTML=xmldata,etag=etag,modified=modified)
        else:
            #print " It's pre-enclosure RSS"
            if delegate.isScrapeAllowed(url):
                return ScraperFeed(info['updated-url'],initialHTML=xmldata,etag=etag,modified=modified, charset=charset)
            else:
                return None
    else:  #What the fuck kinda feed is this, asshole?
        print "DTV doesn't know how to deal with "+info['content-type']+" feeds"
        return None


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
        self.updating = False
        DDBObject.__init__(self)

    ##
    # Downloads the next available item taking into account maxNew,
    # fallbehind, and getEverything
    def downloadNextAuto(self, dontUse = []):
        print "Downloading next auto"
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
		if (item.getState() == "autopending") and not item in dontUse:
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

    def downloadNextManual(self):
        next = None
        for item in self.items:
            if item.getState() == "manualpending":
                if next is None:
                    next = item
                elif item.getPubDateParsed() < next.getPubDateParsed():
                    next = item
        if not next is None:
            next.download(autodl = False)


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
	    if (not item.getKeep()) and item.getState() == "finished" and datetime.now() - item.getDownloadedTime() > expireTime:
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
    def remove(self):
        self.beginRead()
        try:
            items = []
            self.itemlist.resetCursor()
            for item in self.itemlist:
                items.append(item)
            for item in items:
                item.remove()
        finally:
            self.endRead()
        del self.itemlist
        DDBObject.remove(self)

    ##
    # Called by pickle during serialization
    def __getstate__(self):
	temp = copy(self.__dict__)
	return (0,temp)

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
        (version, data) = state
        assert(version == 0)
        data['updating'] = False
	self.__dict__ = data

class RSSFeed(Feed):
    firstImageRE = re.compile('\<\s*img\s+[^>]*src\s*=\s*"(.*?)"[^>]*\>',re.I|re.M)
    
    def __init__(self,url,title = None,initialHTML = None, etag = None, modified = None):
        Feed.__init__(self,url,title)
        self.initialHTML = initialHTML
        self.etag = etag
        self.modified = modified
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
        info = {}
        self.beginRead()
        try:
            if self.updating:
                return
            else:
                self.updating = True
        finally:
            self.endRead()
        if not self.initialHTML is None:
            html = self.initialHTML
            self.initialHTML = None
        else:
            info = grabURL(self.url,etag=self.etag,modified=self.modified)
            if info is None:
                self.beginRead()
                try:
                    self.updating = False
                finally:
                    self.endRead()
                return None
            
            html = info['file-handle'].read()
            info['file-handle'].close()
            if info.has_key('charset'):
                html = fixXMLHeader(html,info['charset'])
            if info['status'] == 304:
                self.beginRead()
                try:
                    self.updating = False
                finally:
                    self.endRead()
                return
            self.url = info['updated-url']
        d = feedparser.parse(html)
        self.parsed = d

        self.beginRead()
        try:
            try:
                self.title = self.parsed["feed"]["title"]
            except KeyError:
                try:
                    self.title = self.parsed["channel"]["title"]
                except KeyError:
                    pass
            for entry in self.parsed.entries:
                entry = self.addScrapedThumbnail(entry)
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
            self.updating = False
        finally:
            if info.has_key('etag'):
                self.etag = info['etag']
            if info.has_key('last-modified'):
                self.modified = info['last-modified']
            self.endRead()
	    self.beginChange()
	    self.endChange()

    def addScrapedThumbnail(self,entry):
        if (len(entry['enclosures'])>0 and
            entry.has_key('description') and 
            not entry['enclosures'][0].has_key('thumbnail')):
                desc = RSSFeed.firstImageRE.search(unescape(entry['description']))
                if not desc is None:
                    entry['enclosures'][0]['thumbnail'] = FeedParserDict({'url': desc.expand("\\1")})
        return entry

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
	temp["scheduler"] = None
        temp["itemlist"] = None
	return (0,temp)

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
        (version, data) = state
        assert(version == 0)
        data['updating'] = False
	self.__dict__ = data
	self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.feed is self)
	#FIXME: the update dies if all of the items aren't restored, so we 
        # wait a little while before we start the update
        self.scheduler = ScheduleEvent(5, self.update,False)

        self.scheduler = ScheduleEvent(self.updateFreq, self.update)


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
class ScraperFeed(Feed):
    #FIXME: change this to a higher number once we optimize shit a bit
    maxThreads = 2

    def __init__(self,url,title = None, visible = True, initialHTML = None,etag=None,modified = None,charset = None):
	Feed.__init__(self,url,title,visible)
        self.initialHTML = initialHTML
        self.initialCharset = charset
	self.scheduler = ScheduleEvent(self.updateFreq, self.update)
	self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.feed is self)
	self.scheduler = ScheduleEvent(0, self.update,False)
        self.linkHistory = {}
        self.linkHistory[url] = {}
        self.tempHistory = {}
        if not etag is None:
            self.linkHistory[url]['etag'] = etag
        if not modified is None:
            self.linkHistory[url]['modified'] = modified
        self.semaphore = Semaphore(ScraperFeed.maxThreads)

    def getMimeType(self,link):
        info = grabURL(link,"HEAD")
        if info is None:
            return ''
        else:
            return info['content-type']

    ##
    # This puts all of the caching information in tempHistory into the
    # linkHistory. This should be called at the end of an updated so that
    # the next time we update we don't unnecessarily follow old links
    def saveCacheHistory(self):
        self.beginRead()
        try:
            for url in self.tempHistory.keys():
                self.linkHistory[url] = self.tempHistory[url]
            self.tempHistory = {}
        finally:
            self.endRead()
    ##
    # returns a tuple containing the text of the URL, the url (in case
    # of a permanent redirect), a redirected URL (in case of
    # temporary redirect)m and the download status
    def getHTML(self, url, useActualHistory = True):
        etag = None
        modified = None
        if self.linkHistory.has_key(url):
            if self.linkHistory[url].has_key('etag'):
                etag = self.linkHistory[url]['etag']
            if self.linkHistory[url].has_key('modified'):
                modified = self.linkHistory[url]['modified']
        info = grabURL(url, etag=etag, modified=modified)
        if info is None:
            return (None, url, url,404, None)
        else:
            if not self.tempHistory.has_key(info['updated-url']):
                self.tempHistory[info['updated-url']] = {}
            if info.has_key('etag'):
                self.tempHistory[info['updated-url']]['etag'] = info['etag']
            if info.has_key('last-modified'):
                self.tempHistory[info['updated-url']]['modified'] = info['last-modified']

            html = info['file-handle'].read()
            #print "Scraper got HTML of length "+str(len(html))
            info['file-handle'].close()
            #print "Closed"
            if info.has_key('charset'):
                return (html, info['updated-url'],info['redirected-url'],info['status'],info['charset'])
            else:
                return (html, info['updated-url'],info['redirected-url'],info['status'],None)

    def addVideoItem(self,link,dict,linkNumber):
	link = link.strip()
        if dict.has_key('title'):
            title = dict['title']
        else:
            title = link
	for item in self.items:
	    if item.getURL() == link:
		return
	if dict.has_key('thumbnail') > 0:
	    i=Item(self, FeedParserDict({'title':title,'enclosures':[FeedParserDict({'url':link,'thumbnail':FeedParserDict({'url':dict['thumbnail']})})]}),linkNumber = linkNumber)
	else:
	    i=Item(self, FeedParserDict({'title':title,'enclosures':[FeedParserDict({'url':link})]}),linkNumber = linkNumber)
	self.items.append(i)
	self.beginChange()
	self.endChange()

    def makeProcessLinkFunc(self,subLinks,depth,linkNumber):
        return lambda: self.processLinksThenFreeSem(subLinks,depth,linkNumber)

    def processLinksThenFreeSem(self,subLinks,depth,linkNumber):
        try:
            self.processLinks(subLinks, depth,linkNumber)
        finally:
            #print "Releasing semaphore"
            self.semaphore.release()

    #FIXME: compound names for titles at each depth??
    def processLinks(self,links, depth = 0,linkNumber = 0):
        maxDepth = 2
        urls = links[0]
        links = links[1]
        if depth<maxDepth:
            for link in urls:
                if depth == 0:
                    linkNumber += 1
                print "Processing %s (%d)" % (link,linkNumber)
                #FIXME keep the connection open
                mimetype = self.getMimeType(link)
                #print " mimetype is "+mimetype
                if mimetype != None:
                    #This is text of some sort: HTML, XML, etc.
                    if (mimetype.startswith('text/html') or
                        mimetype.startswith('application/xhtml+xml') or 
                        mimetype.startswith('text/xml')  or
                        mimetype.startswith('application/xml') or
                        mimetype.startswith('application/rss+xml') or
                        mimetype.startswith('application/atom+xml') or
                        mimetype.startswith('application/rdf+xml') ):
                        (html, url, redirURL,status,charset) = self.getHTML(link)
                        if status == 304: #It's cached
                            pass
                        elif not html is None:
                            subLinks = self.scrapeLinks(html, redirURL,charset=charset)
                            if depth == 0:
                                self.semaphore.acquire()
                                #print "Acquiring semaphore"
                                thread = Thread(target = self.makeProcessLinkFunc(subLinks,depth+1,linkNumber))
                                thread.setDaemon(False)
                                thread.start()
                            else:
                                self.processLinks(subLinks,depth+1,linkNumber)
                        else:
                            pass
                            #print link+" seems to be bogus..."
                    #This is a video
                    elif mimetype.startswith('video/'):
                        self.addVideoItem(link, links[link],linkNumber)

    #FIXME: go through and add error handling
    def update(self):
        self.beginRead()
        try:
            if self.updating:
                return
            else:
                self.updating = True
        finally:
            self.endRead()
        if not self.initialHTML is None:
            html = self.initialHTML
            self.initialHTML = None
            redirURL=self.url
            status = 200
            charset = self.initialCharset
            self.initialCharset = None
        else:
            (html,url, redirURL, status,charset) = self.getHTML(self.url)
        if not status == 304:
            if not html is None:
                links = self.scrapeLinks(html, redirURL, setTitle=True,charset=charset)
                self.processLinks(links)
            #Download the HTML associated with each page
        self.beginRead()
        try:
            self.saveCacheHistory()
            self.updating = False
        finally:
            self.endRead()

    def scrapeLinks(self,html,baseurl,setTitle = False,charset = None):
	try:
            if not charset is None:
                xmldata = fixXMLHeader(html,charset)
                html = fixHTMLHeader(html,charset)
            else:
                xmldata = html
            parser = xml.sax.make_parser()
            parser.setFeature(xml.sax.handler.feature_namespaces, 1)
            if not charset is None:
                handler = RSSLinkGrabber(baseurl,charset)
            else:
                handler = RSSLinkGrabber(baseurl)
            parser.setContentHandler(handler)
            try:
                parser.parse(StringIO(xmldata))
            except IOError, e:
                pass
	    links = handler.links
            linkDict = {}
            for link in links:
                if link[0].startswith('http://') or link[0].startswith('https://'):
                    if not linkDict.has_key(toUTF8Bytes(link[0],charset)):
                        linkDict[toUTF8Bytes(link[0])] = {}
                    if not link[1] is None:
                        linkDict[toUTF8Bytes(link[0])]['title'] = toUTF8Bytes(link[1],charset).strip()
                    if not link[2] is None:
                        linkDict[toUTF8Bytes(link[0])]['thumbnail'] = toUTF8Bytes(link[2],charset)
            if setTitle and not handler.title is None:
                self.beginChange()
                try:
                    self.title = handler.title
                finally:
                    self.endChange()
            return ([x[0] for x in links if x[0].startswith('http://') or x[0].startswith('https://')], linkDict)
	except (xml.sax.SAXException, IOError):
	    (links, linkDict) = self.scrapeHTMLLinks(html,baseurl,setTitle=setTitle, charset=charset)
            return (links, linkDict)

    ##
    # Given a string containing an HTML file, return a dictionary of
    # links to titles and thumbnails
    def scrapeHTMLLinks(self,html, baseurl,setTitle=False, charset = None):
        #print "Scraping "+baseurl+" as HTML"
	lg = HTMLLinkGrabber()
	links = lg.getLinks(html, baseurl)
        if setTitle and not lg.title is None:
            self.beginChange()
            try:
                self.title = lg.title
            finally:
                self.endChange()
            
        linkDict = {}
	for link in links:
	    if link[0].startswith('http://') or link[0].startswith('https://'):
                if not linkDict.has_key(toUTF8Bytes(link[0],charset)):
                    linkDict[toUTF8Bytes(link[0])] = {}
                if not link[1] is None:
                    linkDict[toUTF8Bytes(link[0])]['title'] = toUTF8Bytes(link[1],charset).strip()
                if not link[2] is None:
                    linkDict[toUTF8Bytes(link[0])]['thumbnail'] = toUTF8Bytes(link[2],charset)
	return ([x[0] for x in links if x[0].startswith('http://') or x[0].startswith('https://')],linkDict)
	
    ##
    # Called by pickle during serialization
    def __getstate__(self):
	temp = copy(self.__dict__)
        temp['semaphore'] = None
	temp["scheduler"] = None
        temp["itemlist"] = None
	return (0,temp)

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
        (version, data) = state
        assert(version == 0)
        data['updating'] = False
        data['tempHistory'] = {}
	self.__dict__ = data
	self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.feed is self)
	#FIXME: the update dies if all of the items aren't restored, so we 
        # wait a little while before we start the update
        ScheduleEvent(5, self.update,False)

        self.scheduler = ScheduleEvent(self.updateFreq, self.update)
        self.semaphore = Semaphore(ScraperFeed.maxThreads)

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
        self.beginRead()
        try:
            if self.updating:
                return
            else:
                self.updating = True
        finally:
            self.endRead()
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
            self.updating = False
	finally:
	    self.endRead()

    ##
    # Called by pickle during serialization
    def __getstate__(self):
	temp = copy(self.__dict__)
	temp["scheduler"] = None
        temp['itemlist'] = None
        temp['RSSFilenames'] = None
	return (0,temp)

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
        (version, data) = state
        assert(version == 0)
        data['updating'] = False
	self.__dict__ = data
	self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.feed is self)
	self.RSSFilenames = defaultDatabase.filter(lambda x:isinstance(x,Item) and isinstance(x.feed,RSSFeed)).map(lambda x:x.getFilenames())
	#FIXME: the update dies if all of the items aren't restored, so we 
        # wait a little while before we start the update
        self.scheduler = ScheduleEvent(5, self.update,False)

        self.scheduler = ScheduleEvent(self.updateFreq, self.update)

##
# Parse HTML document and grab all of the links and their title
# FIXME: Grab link title from ALT tags in images
class HTMLLinkGrabber(HTMLParser):
    def getLinks(self,data, baseurl):
	self.links = []
	self.lastLink = None
	self.inLink = False
	self.inObject = False
	self.baseurl = baseurl
        self.inTitle = False
        self.title = None
        self.thumbnailUrl = None
        try:
            self.feed(data)
        except HTMLParseError:
            print "DTV: error parsing "+str(baseurl)
        try:
            self.close()
        except HTMLParseError:
            print "DTV: error closing "+str(baseurl)
	return self.links

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'title':
            self.inTitle = True
        elif tag.lower() == 'base':
            for attr in attrs:
                if attr[0].lower() == 'href':
                    self.baseurl = attr[1]
	elif tag.lower() == 'object':
	    self.inObject = True
        elif self.inLink and tag.lower() == 'img':
            for attr in attrs:
                if attr[0].lower() == 'src':
                    self.links[-1] = (self.links[-1][0],self.links[-1][1],urljoin(self.baseurl,attr[1]))
	elif tag.lower() == 'a':
	    for attr in attrs:
		if attr[0].lower() == 'href':
		    self.links.append( (urljoin(self.baseurl,attr[1]),None,None))
		    self.inLink = True
		    break
	elif tag.lower() == 'embed':
		for attr in attrs:
		    if attr[0].lower() == 'src':
			self.links.append( (urljoin(self.baseurl,attr[1]),None,None))
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
			self.links.append( (urljoin(self.baseurl,attr[1]),None,None))
			break
		
    def handle_endtag(self, tag):
	if tag.lower() == 'a':
	    if self.inLink:
		if self.links[-1][1] is None:
		    self.links[-1] = (self.links[-1][0], self.links[-1][0],self.links[-1][2])
		    self.inLink = False
	elif tag.lower() == 'object':
	    self.inObject = False
        elif tag.lower() == 'title':
            self.inTitle = False
    def handle_data(self, data):
        if self.inLink:
            if self.links[-1][1] is None:
                self.links[-1] = (self.links[-1][0], '',self.links[-1][2])
            self.links[-1] = (self.links[-1][0],self.links[-1][1]+data,self.links[-1][2])
        elif self.inTitle:
            if self.title is None:
                self.title = data
            else:
                self.title += data

class RSSLinkGrabber(xml.sax.handler.ContentHandler):
    def __init__(self,baseurl,charset=None):
	self.baseurl = baseurl
        self.charset = charset
    def startDocument(self):
        #print "Got start document"
        self.enclosureCount = 0
        self.itemCount = 0
	self.links = []
	self.inLink = False
	self.inDescription = False
        self.inTitle = False
        self.inItem = False
	self.descHTML = ''
	self.theLink = ''
        self.title = None
	self.firstTag = True

    def startElementNS(self, name, qname, attrs):
        (uri, tag) = name
	if self.firstTag:
	    self.firstTag = False
	    if tag != 'rss':
		raise xml.sax.SAXNotRecognizedException, "Not an RSS file"
        if tag.lower() == 'enclosure' or tag.lower() == 'content':
            self.enclosureCount += 1
	elif tag.lower() == 'link':
	    self.inLink = True
	    self.theLink = ''
	    return
	elif tag.lower() == 'description':
	    self.inDescription = True
	    self.descHTML = ''
        elif tag.lower() == 'item':
            self.itemCount += 1
            self.inItem = True
        elif tag.lower() == 'title' and not self.inItem:
            self.inTitle = True
    def endElementNS(self, name, qname):
        (uri, tag) = name
	if tag.lower() == 'description':
	    lg = HTMLLinkGrabber()
            try:
                html = xhtmlify(unescape(self.descHTML),addTopTags=True)
                if not self.charset is None:
                    html = fixHTMLHeader(html,self.charset)
                self.links[:0] = lg.getLinks(html,self.baseurl)
            except HTMLParseError: # Don't bother with bad HTML
                print "DTV: bad HTML in %s" % self.baseurl
	    self.inDescription = False
	elif tag.lower() == 'link':
	    self.links.append((self.theLink,None,None))
	    self.inLink = False
        elif tag.lower() == 'item':
            self.inItem == False
        elif tag.lower() == 'title' and not self.inItem:
            self.inTitle = False

    def characters(self, data):
	if self.inDescription:
	    self.descHTML += data
	elif self.inLink:
	    self.theLink += data
        elif self.inTitle:
            if self.title is None:
                self.title = data
            else:
                self.title += data

# Grabs the feed link from the given webpage
class HTMLFeedURLParser(HTMLParser):
    def getLink(self,baseurl,data):
        self.baseurl = baseurl
	self.link = None
        try:
            self.feed(data)
        except HTMLParseError:
            print "DTV: error parsing "+str(baseurl)
        try:
            self.close()
        except HTMLParseError:
            print "DTV: error closing "+str(baseurl)
	return self.link

    def handle_starttag(self, tag, attrs):
        attrdict = {}
        for (key, value) in attrs:
            attrdict[key.lower()] = value
        if (tag.lower() == 'link' and attrdict.has_key('rel') and 
            attrdict.has_key('type') and attrdict.has_key('href') and
            attrdict['rel'].lower() == 'alternate' and 
            attrdict['type'].lower() in ['application/rss+xml',
                                         'application/rdf+xml',
                                         'application/atom+xml',
                                         'text/xml',
                                         'application/xml']):
            print "Got Link %s" % attrdict['href']
            self.link = urljoin(self.baseurl,attrdict['href'])
