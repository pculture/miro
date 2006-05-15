from random import randint

import feed
import item
import config
import database
import eventloop

def viewLooper(view):
    """Generator that continuously loops around a view.  When it gets to the
    end, it just calls resetCursor and starts over.  Before we begin returning
    elements we advance to a random position.  This is used to implement feed
    downloading in a nice round-robin fashon.
    """
    if view.len() > 1:
        skip = randint(0,view.len()-1)
        for x in range(skip):
            view.getNext()

    while 1:
        next = view.getNext()
        if next != None:
            yield next
        else:
            view.resetCursor()
            yield view.getNext()

# filter functions we use to create views.

def isAutoDownloader(x):
    """Returns true iff x is an autodownloader"""
    ret = False
    if x.getAutoDownloaded() and x.getState() == 'downloading':
        ret = True
    return ret

def isManualDownloader(x):
    """Returns true iff x is a manual downloader"""
    ret = False
    if not x.getAutoDownloaded() and x.getState() == 'downloading':
        ret = True
    return ret

def eligibileFeedFilter(x):
    """Returns true iff x is a feed and is automatically downloadable"""
    return x.isAutoDownloadable()

def manualFeedFilter(x):
    """Returns true iff x is a feed with a manual download item"""
    ret = False
    x.beginRead()
    try:
        for item in x.items:
            if item.getState() == 'manualpending':
                ret = True
                break
    finally:
        x.endRead()
    return ret

def isBitTorrentDownloader(item):
    """Returns true iff x is an item with a bit torrent download """
    downloaders = item.getDownloaders()
    return (len(downloaders) > 0 and 
            downloaders[0].getType() == 'bittorrent')


##
# Runs in the background and automatically triggers downloads
class AutoDownloader:
                
    ##
    # This triggers items to be expired
    def expireItems(self):
        for feed in self.allFeeds:
            feed.expireItems()

    def spawnAutoDownloads(self):
        """Spawns auto downloads.

        Our strategy is:
            * Never spawn more downloads than config.DOWNLOADS_TARGET
            * Never spawn bit torrent downloads than
                config.TORRENT_DOWNLOADS_TARGET
            * Prefer spawning HTTP downloads rather than starting a second
            torrent download.
            * Spawn downloads in a round-robin manner
        """

        numFeeds = self.autoFeeds.len()
        # NOTE: numFeeds can become invalid if we insert/delete a feed
        # into the autoFeed view.  It's not a big deal though since it's not
        # that bad if we check a feed twice or miss one.
        numDownloads = self.autoDownloaders.len()
        numTorrents = self.btAutoDownloaders.len()
        maxDownloads = config.get(config.DOWNLOADS_TARGET)
        maxTorrents = config.get(config.TORRENT_DOWNLOADS_TARGET)
        # step 1: Don't start 2 bit torrent downloads
        attempts = 0
        while attempts < numFeeds and numDownloads < maxDownloads:
            attempts += 1
            feed = self.autoFeedsLoop.next()
            if feed is None: # happens when len(self.autoFeeds) == 0
                return
            item = feed.getNextAutoDownload()
            if item is not None:
                if not item.isTorrent():
                    item.download(autodl=True)
                    numDownloads += 1
                else:
                    if numTorrents == 0:
                        item.download(autodl=True)
                        numTorrents += 1
                        numDownloads += 1
        # step 2: Download whatever
        attempts = 0
        while attempts < numFeeds and numDownloads < maxDownloads:
            attempts += 1
            feed = self.autoFeedsLoop.next()
            if feed is None: # happens when len(self.autoFeeds) == 0
                return
            item = feed.getNextAutoDownload()
            if item is not None:
                if item.isTorrent():
                    if numTorrents < maxTorrents:
                        item.download(autodl=True)
                        numTorrents += 1
                        numDownloads += 1
                else:
                    item.download(autodl=True)
                    numDownloads += 1

    def spawnManualDownloads(self):
        attempts = 0
        numFeeds = self.manualFeeds.len() # see note in spawnAutoDownloads
        numDownloads = self.manualDownloaders.len()
        maxDownloads = config.get(config.MAX_MANUAL_DOWNLOADS)
        while numDownloads < maxDownloads and attempts < numFeeds:
            attempts += 1
            feed = self.manualFeedsLoop.next()
            if feed is None: # happens when len(self.manualFeeds) == 0
                return
            feed.downloadNextManual()
            numDownloads += 1

    ##
    # This is the function that actually triggers the downloads It
    # loops through all of the available feeds round-robin style and
    # gets the next thing it can
    # 
    def spawnDownloads(self):
        """Goes through the feeds and starts up autodownloads and manual
        downloads as neccesary.  """

        self.spawnAutoDownloads()
        self.spawnManualDownloads()

    def run(self):
        try:
            self.expireItems()
            self.spawnDownloads()
        finally:
            eventloop.addTimeout(10, self.run, "Auto downloader")

    def __init__(self):
        db = database.defaultDatabase
        self.allFeeds = db.filter(lambda x:isinstance(x,feed.Feed))
        self.allItems = db.filter(lambda x:isinstance(x,item.Item))
        self.autoFeeds = self.allFeeds.filter(eligibileFeedFilter)
        self.autoFeedsLoop = viewLooper(self.autoFeeds)
        self.manualFeeds = self.allFeeds.filter(manualFeedFilter)
        self.manualFeedsLoop = viewLooper(self.manualFeeds)
        self.autoDownloaders = self.allItems.filter(isAutoDownloader)
        self.btAutoDownloaders = \
                self.allItems.filter(isBitTorrentDownloader)
        self.manualDownloaders = self.allItems.filter(isManualDownloader)
        
        eventloop.addTimeout(10, self.run, "Auto downloader")
