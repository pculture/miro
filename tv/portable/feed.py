from urllib import urlopen
from datetime import datetime
from threading import RLock
from database import defaultDatabase
from item import *
from scheduler import ScheduleEvent
from copy import copy
from xhtmltools import unescape,xhtmlify

#FIXME: Add support for HTTP caching and redirects

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
    def __init__(self, url, title = 'unknown'):
        self.url = url
        self.items = []
        self.title = title
        self.created = datetime.now()
        self.lock = RLock()
        self.updateFreq = 60*60
        DDBObject.__init__(self)

    ##
    # Returns the title of the feed
    def getTitle(self):
        self.lock.acquire()
        ret = self.title
        self.lock.release()
        return ret

    ##
    # Returns the URL of the feed
    def getURL(self):
        self.lock.acquire()
        ret = self.url
        self.lock.release()
        return ret

    ##
    # Returns the description of the feed
    def getDescription(self):
        return ""

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
        self.lock.acquire()
	count = 0
	for item in self.items:
	    try:
		if item.getState() == 'finished' and not item.getSeen():
		    count += 1
	    except:
		pass
        self.lock.release()
        return count

    ##
    # Removes a feed from the database
    def removeFeed(self,url):
        self.lock.acquire()
        try:
            for item in self.items:
                item.remove()
        finally:
            self.lock.release()
        self.remove()

class RSSFeed(Feed):
    def __init__(self,url,title = 'unknown'):
        Feed.__init__(self,url,title)
        self.update()
        self.scheduler = ScheduleEvent(self.updateFreq, self.update)
	self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.feed is self)

    ##
    # Returns the description of the feed
    def getDescription(self):
	self.lock.acquire()
	try:
	    ret = xhtmlify('<span>'+unescape(self.parsed.summary)+'</span>')
	except:
	    ret = ""
	self.lock.release()
        return ret

    ##
    # Returns a link to a webpage associated with the feed
    def getLink(self):
	self.lock.acquire()
	try:
	    ret = self.parsed.link
	except:
	    ret = ""
	self.lock.release()
        return ret

    ##
    # Returns the URL of the library associated with the feed
    def getLibraryLink(self):
        self.lock.acquire()
	try:
	    ret = self.parsed.libraryLink
	except:
	    ret = ""
        self.lock.release()
        return ret

    ##
    # Returns the URL of a thumbnail associated with the feed
    def getThumbnail(self):
        self.lock.acquire()
	try:
	    ret = self.parsed.image.url
	except:
	    ret = ""
        self.lock.release()
        return ret
	

    ##
    # Updates a feed
    def update(self):
        self.parsed = feedparser.parse(self.url)
        self.lock.acquire()
        self.beginChange()
        try:
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
                        if item["id"] == entry["id"]:
                            item.update(entry)
                            new = False
                    except KeyError:
                        # If the item changes at all, it results in a
                        # new entry
                        if (item.entry == entry):
                            item.update(entry)
                            new = False
                if new:
                    self.items.append(Item(self,entry))
            try:
                self.updateFreq = min(15*60,self.parsed["feed"]["ttl"]*60)
            except KeyError:
                self.updateFreq = 60*60
        finally:
            self.endChange()
            self.lock.release()

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
	temp["lock"] = None
	temp["itemlist"] = None
	temp["scheduler"] = None
	return temp

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
	self.__dict__ = state
	self.lock = RLock()
	self.itemlist = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.feed is self)
        self.scheduler = ScheduleEvent(self.updateFreq, self.update)
        self.scheduler = ScheduleEvent(1, self.update,False)
