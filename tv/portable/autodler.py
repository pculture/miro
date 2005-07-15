import database
import feed
import item
import scheduler
import config
from random import randint

##
# Runs in the background and automatically triggers downloads
class AutoDownloader:
    ##
    # Returns true iff x is an autodownloader
    def isAutoDownloader(self,x):
        ret = False
        if x.getAutoDownloaded() and x.getState() == 'downloading':
            ret = True
        return ret

    ##
    # Returns true iff x is a manual downloader
    def isManualDownloader(self,x):
        ret = False
        if not x.getAutoDownloaded() and x.getState() == 'downloading':
            ret = True
        return ret

    ##
    # returns the number of automatic downloads currently happening
    def autoDownloads(self):
	count = 0
	for dl in self.autoDownloaders:
	    count += 1
	return count

    ##
    # returns the number of manual downloads currently happening
    def manualDownloads(self):
	count = 0
	for dl in self.manualDownloaders:
	    count += 1
	return count

    ##
    # Returns true iff x is a feed and is automatically downloadable
    def eligibileFeedFilter(self,x):
	return x.isAutoDownloadable()

    ##
    # Returns true iff x is a feed with a manual download item
    def manualFeedFilter(self,x):
        ret = False
        x.beginRead()
        try:
            for item in x.items:
                if item.getStateNoAuto() == 'manualpending':
                    ret = True
                    break
        finally:
            x.endRead()
        return ret
                
    ##
    # This triggers items to be expired
    def expireItems(self):
	for feed in self.allFeeds:
	    feed.expireItems()

    def recomputeFilters(self):
        # FIXME: For locking reasons, downloaders don't always
        #        call beginChange() and endChange(), so we have to
        #        recompute these filters
        self.allFeeds.recomputeFilter(self.autoFeeds)
	self.allFeeds.recomputeFilter(self.manualFeeds)
	self.allItems.recomputeFilter(self.autoDownloaders)
        self.allItems.recomputeFilter(self.manualDownloaders)


    ##
    # This is the function that actually triggers the downloads It
    # loops through all of the available feeds round-robin style and
    # gets the next thing it can
    # 
    def spawnDownloads(self):
        self.recomputeFilters()
	attempts = 0
        numFeeds = self.autoFeeds.len()
        numDownloads = self.autoDownloads()
	target = config.get('DownloadsTarget')
	while numDownloads < target and numFeeds > attempts:
	    attempts += 1
	    thisFeed = self.autoFeeds.getNext()
	    if thisFeed == None:
		self.autoFeeds.resetCursor()
		thisFeed = self.autoFeeds.getNext()
	    if thisFeed != None:
		thisFeed.downloadNextAuto()
                numDownloads += 1

	attempts = 0
        numFeeds = self.manualFeeds.len()
        numDownloads = self.manualDownloads()
	target = config.get('MaxManualDownloads')
        #print "I have %d manual downloads in %d feeds. I'm looking for %d" % (
        #    numDownloads,numFeeds,target)
        while (numDownloads < target and 
               numFeeds > attempts):
            #print "."
	    attempts += 1
	    thisFeed = self.manualFeeds.getNext()
	    if thisFeed == None:
		self.manualFeeds.resetCursor()
		thisFeed = self.manualFeeds.getNext()
	    if thisFeed != None:
		thisFeed.downloadNextManual()
		numDownloads += 1

    def run(self):
	self.expireItems()
	self.spawnDownloads()
	    
    def __init__(self):
        self.allFeeds = database.defaultDatabase.filter(lambda x:isinstance(x,feed.Feed))
        self.allItems = database.defaultDatabase.filter(lambda x:isinstance(x,item.Item
))
	self.autoFeeds =self.allFeeds.filter(self.eligibileFeedFilter)
        if self.autoFeeds.len() > 1:
            skip = randint(0,self.autoFeeds.len()-1)
            for x in range(0,skip):
                self.autoFeeds.getNext()

        self.manualFeeds = self.allFeeds.filter(self.manualFeedFilter)
        if self.manualFeeds.len() > 1:
            skip = randint(0,self.manualFeeds.len()-1)
            for x in range(0,skip):
                self.manualFeeds.getNext()

	self.autoDownloaders = self.allItems.filter(self.isAutoDownloader)
	self.manualDownloaders = self.allItems.filter(self.isManualDownloader)

	self.run()
	self.event = scheduler.ScheduleEvent(10,self.run)
