import database
import feed
import downloader
import scheduler
import config

##
# Runs in the background and automatically triggers downloads
class AutoDownloader:
    ##
    # returns the number of downloads currently happening
    def downloads(self):
	count = 0
	for dl in self.downloaders:
	    count += 1
	return count

    ##
    # Returns true iff x is a feed and is automatically downloadable
    def eligibileFeedFilter(self,x):
	return isinstance(x,feed.Feed) and x.isAutoDownloadable()

    ##
    # This triggers items to be expired
    def expireItems(self):
	self.feeds.saveCursor()
	for feed in self.feeds:
	    feed.expireItems()
	self.feeds.restoreCursor()
	return 

    ##
    # This is the function that actually triggers the downloads It
    # loops through all of the available feeds round-robin style and
    # gets the next thing it can
    # 
    def spawnDownloads(self):
	database.defaultDatabase.recomputeFilters()
	attempts = 0
	target = config.get('DownloadsTarget')
	while self.downloads() < target and self.feeds.len() > attempts:
	    attempts += 1
	    thisFeed = self.feeds.getNext()
	    if thisFeed == None:
		self.feeds.resetCursor()
		thisFeed = self.feeds.getNext()
	    if thisFeed != None:
		thisFeed.downloadNext()
		database.defaultDatabase.recomputeFilters()

    def run(self):
	self.expireItems()
	self.spawnDownloads()
	    
    def __init__(self):
	self.feeds = database.defaultDatabase.filter(self.eligibileFeedFilter)
	self.downloaders = database.defaultDatabase.filter(lambda x:isinstance(x,downloader.Downloader) and x.getState() == 'downloading')
	self.run()
	self.event = scheduler.ScheduleEvent(30,self.run)
