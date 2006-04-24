import feed
from copy import copy
from database import DDBObject,defaultDatabase

##
# Implements a folder, which contains a list of feeds
class Folder(DDBObject):
    def __init__(self, title):
	self.feeds = []
	self.title = title
	self.feedlist = defaultDatabase.filter(lambda x:isinstance(x,feed.Feed) and x.getID() in self.feeds)
	DDBObject.__init__(self)

    #FIXME: lock
    def getTitle(self):
	ret = self.title
	return ret

    ##
    # Adds a feed to the folder
    def addFeed(self, theFeed):
	if isinstance(theFeed,feed.Feed):
	    theFeed = theFeed.getID()
	self.beginChange()
	try:
	    self.feeds.append(theFeed)
	finally:
	    self.endChange()

    ##
    # Called by pickle during serialization
    def __getstate__(self):
	temp = copy(self.__dict__)
	temp["feedlist"] = None
	return temp

    ##
    # Called by pickle during deserialization
    def __setstate__(self,state):
	self.__dict__ = state
	self.feedlist = defaultDatabase.filter(lambda x:isinstance(x,feed.Feed) and x.getID() in self.feeds)

    ##
    # Removes a feed from the folder
    def removeFeed(self, theFeed):
	if isinstance(theFeed,feed.Feed):
	    theFeed = theFeed.getID()
	self.beginChange()
	try:
	    self.feeds.remove(theFeed)
	finally:
	    self.endChange()
	
