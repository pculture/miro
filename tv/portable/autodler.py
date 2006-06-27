from BitTornado.clock import clock

import filters
import views
import config
import prefs
import eventloop
import httpclient

# filter functions we use to create views.

def eligibileFeedFilter(x):
    """Returns true iff x is a feed and is automatically downloadable"""
    return x.isAutoDownloadable()

def manualFeedFilter(x):
    """Returns true iff x is a feed with a manual download item"""
    x.confirmDBThread()
    for item in x.items:
        if item.isPendingManualDownload():
            return True
    return False

def isBitTorrentDownloader(item):
    """Returns true iff x is an item with a bit torrent download """
    return (item.downloader is not None and 
            item.downloader.getType() == 'bittorrent' and 
            item.getState() == 'downloading')


# downloadTimes maps feeds to the last time that we downloaded an item from
# that feed.
downloadTimes = {}

def downloadItem(item):
    """Download an item and update the downloadTimes dictionary"""
    item.download(autodl=True)
    downloadTimes[item.getFeed()] = clock()

def sortFeeds(feedList):
    """Sort feeds so that the least-recently downloaded are first in the list.
    """
    copy = [f for f in feedList]
    copy.sort(key=lambda(f): downloadTimes.get(f, 0))
    return copy


class AutoDownloadSpawner:
    """Class that actually spawn the auto-downloads.

    The goals are:
        * Never spawn more downloads than prefs.DOWNLOADS_TARGET
        * Never spawn bit torrent downloads than
            prefs.TORRENT_DOWNLOADS_TARGET
        * Prefer spawning HTTP downloads rather than starting a second
        torrent download.
        * Spawn downloads in a round-robin manner

    We do this by spawning autodownloads in 2 stages.  In the 1st stage, we
    refuse to spawn more than 1 bit torrent download while spawning as many
    HTTP downloads as possible.  In the 2nd stage we spawn BT downloads until
    we hit the TORRENT_DOWNLOADS_TARGET limit.
    """


    def __init__(self, callback, maxDownloads, maxTorrents, numDownloads,
            numTorrents, candidates):
        self.callback = callback
        self.maxDownloads = maxDownloads
        self.maxTorrents = maxTorrents
        self.numDownloads = numDownloads
        self.numTorrents = numTorrents
        self.candidates = candidates
        self.candidateIter = iter(self.candidates)
        self.stage = 1
        eventloop.addIdle(self.chooseNextDownload, "autodl iteration")


    def chooseNextDownload(self):
        if self.numDownloads >= self.maxDownloads:
            self.callback()
            return

        try:
            feed = self.candidateIter.next()
        except StopIteration:
            if self.stage == 1:
                self.stage = 2
                self.candidateIter = iter(self.candidates)
                eventloop.addIdle(self.chooseNextDownload, "autodl iteration")
            else:
                self.callback()
            return

        item = feed.getNextAutoDownload()
        if item is not None:
            self.handleCandidateItem(item)
        else:
            eventloop.addIdle(self.chooseNextDownload, "autodl iteration")

    def handleCandidateItem(self, item):
        """Handle an item that we may want to autodownload.  Depending if it's
        a torrent or not and what stage of the auto-download process we're at,
        we may or may not actually download it.
        """

        def onHeaders(info):
            if info.get('content-type') == 'application/x-bittorrent':
                self.handleTorrentCandidate(item)
            else:
                self.handleHTTPCandidate(item)
            eventloop.addIdle(self.chooseNextDownload, "autodl iteration")
        def errback(error):
            eventloop.addIdle(self.chooseNextDownload, "autodl iteration")

        httpclient.grabHeaders(item.getURL(), onHeaders, errback)

    def handleTorrentCandidate(self, item):
        # stage 1: Don't start more than 1 bit torrent downloads
        # stage 2: Download torrents until we reach our torrent limit
        if ((self.stage == 1 and self.numTorrents == 0) or 
            (self.stage == 2 and self.numTorrents < self.maxTorrents)):
            downloadItem(item)
            self.numDownloads += 1
            self.numTorrents += 1

    def handleHTTPCandidate(self, item):
        downloadItem(item)
        self.numDownloads += 1

##
# Runs in the background and automatically triggers downloads
class AutoDownloader:
    def spawnDownloads(self):
        """Goes through the feeds and starts up autodownloads and manual
        downloads as neccesary.  """
        self.spawnManualDownloads()
        self.spawnAutoDownloads()


    def spawnManualDownloads(self):
        maxDownloads = config.get(prefs.MAX_MANUAL_DOWNLOADS)
        if self.manualDownloads.len() >= maxDownloads:
            return
        candidates = sortFeeds(self.manualFeeds)
        for feed in candidates:
            if self.manualDownloads.len() < maxDownloads:
                feed.downloadNextManual()
                downloadTimes[feed] = clock()
            else:
                break

    def spawnAutoDownloads(self):
        # This used to be a loop, but now that we use asynchronous networking
        # that doesn't work.  I (ben) basically refactored the loop into an
        # object.
        AutoDownloadSpawner(self.spawnAutoDownloadsDone,
                config.get(prefs.DOWNLOADS_TARGET),
                config.get(prefs.TORRENT_DOWNLOADS_TARGET),
                self.autoDownloads.len(),
                self.btAutoDownloaders.len(),
                sortFeeds(self.autoFeeds))

    def spawnAutoDownloadsDone(self):
        eventloop.addTimeout(10, self.spawnDownloads, "Auto downloader")

    def __init__(self):
        self.autoFeeds = views.feeds.filter(eligibileFeedFilter)
        self.manualFeeds = views.feeds.filter(manualFeedFilter)
        self.autoDownloads = views.items.filter(filters.autoDownloads)
        self.btAutoDownloaders = views.items.filter(isBitTorrentDownloader)
        self.manualDownloads = views.items.filter(filters.manualDownloads)
        eventloop.addTimeout(10, self.spawnDownloads, "Auto downloader")
