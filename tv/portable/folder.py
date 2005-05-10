import feed
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
    # Removes a feed from the folder
    def removeFeed(self, theFeed):
	if isinstance(theFeed,feed.Feed):
	    theFeed = theFeed.getID()
	self.beginChange()
	try:
	    self.feeds.remove(theFeed)
	finally:
	    self.endChange()
	
