import database
import feed
import downloader
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
        if isinstance(x,downloader.Downloader) and x.getState() == 'downloading':
            for item in x.itemList:
                if item.getAutoDownloaded():
                    ret = True
                    break
        return ret

    ##
    # Returns true iff x is a manual downloader
    def isManualDownloader(self,x):
        ret = False
        if isinstance(x,downloader.Downloader) and x.getState() == 'downloading':
            for item in x.itemList:
                if not item.getAutoDownloaded():
                    ret = True
                    break
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
	return isinstance(x,feed.Feed) and x.isAutoDownloadable()

    ##
    # Returns true iff x is a feed with a manual download item
    def manualFeedFilter(self,x):
        ret = False
        if isinstance(x, feed.Feed):
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

    ##
    # This is the function that actually triggers the downloads It
    # loops through all of the available feeds round-robin style and
    # gets the next thing it can
    # 
    def spawnDownloads(self):
	print "Spawning auto downloader..."
	database.defaultDatabase.recomputeFilters()
	attempts = 0
	target = config.get('DownloadsTarget')
	while self.autoDownloads() < target and self.autoFeeds.len() > attempts:
	    attempts += 1
	    thisFeed = self.autoFeeds.getNext()
	    if thisFeed == None:
		self.autoFeeds.resetCursor()
		thisFeed = self.autoFeeds.getNext()
	    if thisFeed != None:
		thisFeed.downloadNextAuto()
		database.defaultDatabase.recomputeFilters()

	attempts = 0
	target = config.get('MaxManualDownloads')
        while (self.manualDownloads() < target and 
               self.manualFeeds.len() > attempts):
	    attempts += 1
	    thisFeed = self.manualFeeds.getNext()
	    if thisFeed == None:
		self.manualFeeds.resetCursor()
		thisFeed = self.manualFeeds.getNext()
	    if thisFeed != None:
		thisFeed.downloadNextManual()
		database.defaultDatabase.recomputeFilters()
	print "done autodownloading..."

    def run(self):
	self.expireItems()
	self.spawnDownloads()
	    
    def __init__(self):
	self.autoFeeds = database.defaultDatabase.filter(self.eligibileFeedFilter)
        if self.autoFeeds.len() > 1:
            skip = randint(0,self.autoFeeds.len()-1)
            for x in range(0,skip):
                self.autoFeeds.getNext()

        self.manualFeeds = database.defaultDatabase.filter(self.manualFeedFilter)
        if self.manualFeeds.len() > 1:
            skip = randint(0,self.manualFeeds.len()-1)
            for x in range(0,skip):
                self.manualFeeds.getNext()
        
        self.allFeeds = database.defaultDatabase.filter(lambda x:isinstance(x,feed.Feed))

	self.autoDownloaders = database.defaultDatabase.filter(self.isAutoDownloader)
	self.manualDownloaders = database.defaultDatabase.filter(self.isManualDownloader)

	self.run()
	self.event = scheduler.ScheduleEvent(30,self.run)
