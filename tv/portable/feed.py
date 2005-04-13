from urllib import urlopen
from datetime import datetime
from threading import RLock
from database import defaultDatabase
from item import *
from scheduler import ScheduleEvent
from copy import copy

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
    # Returns the title of the feed
    def getURL(self):
        self.lock.acquire()
        ret = self.url
        self.lock.release()
        return ret

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
    # Updates a feed
    def update(self):
        parsed = feedparser.parse(self.url)
        self.lock.acquire()
        self.beginChange()
        try:
            try:
                self.title = parsed["feed"]["title"]
            except KeyError:
                try:
                    self.title = parsed["channel"]["title"]
                except KeyError:
                    pass
            for entry in parsed.entries:
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
                self.updateFreq = min(15*60,parsed["feed"]["ttl"]*60)
            except KeyError:
                self.updateFreq = 60*60
        finally:
            self.endChange()
            self.lock.release()

    def remove(self):
        self.scheduler.remove()
        Feed.remove(self)

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
