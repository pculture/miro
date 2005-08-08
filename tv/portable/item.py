from datetime import datetime, timedelta
from database import DDBObject, defaultDatabase
from downloader import DownloaderFactory
from copy import copy
from xhtmltools import unescape,xhtmlify
from scheduler import ScheduleEvent
from feedparser import FeedParserDict
from threading import Thread
import threadpriority
import config

##
# An item corresponds to a single entry in a feed. Generally, it has
# a single url associated with it
class Item(DDBObject):
    manualDownloads = defaultDatabase.filter(lambda x:isinstance(x,Item) and x.getState() == "downloading" and not x.getAutoDownloaded())

    def __init__(self, feed, entry, linkNumber = 0):
        self.feed = feed
        self.seen = False
        self.downloaders = []
        self.vidinfo = None
        self.autoDownloaded = False
        self.startingDownload = False
        self.lastDownloadFailed = False
        self.pendingManualDL = False
        self.pendingReason = ""
        self.entry = entry
        self.dlFactory = DownloaderFactory(self)
        self.expired = False
        self.keep = False
        # linkNumber is a hack to make sure that scraped items at the
        # top of a page show up before scraped items at the bottom of
        # a page. 0 is the topmost, 1 is the next, and so on
        self.linkNumber = linkNumber
        self.creationTime = datetime.now()
        DDBObject.__init__(self)

    # Unfortunately, our database does not scale well with many views,
    # so we have this hack to make sure that unwatched and available
    # get updated when an item changes
    def endChange(self):
        DDBObject.endChange(self)
        self.feed.updateUandA()

    ##
    # Returns the URL associated with the first enclosure in the item
    def getURL(self):
        ret = ''
        self.beginRead()
        try:
            ret = self.entry.enclosures[0].url
        finally:
            self.endRead()
        return ret
    ##
    # Returns the feed this item came from
    def getFeed(self):
        self.beginRead()
        ret = self.feed
        self.endRead()
        return ret

    ##
    # Returns the number of videos associated with this item
    def getAvailableVideos(self):
        ret = 0
        self.beginRead()
        try:
            ret = len(self.entry.enclosures)
        finally:
            self.endRead()
        return ret

    ##
    # Marks this item as expired
    def expire(self):
        self.beginRead()
        try:
            self.stopDownload()
            # FIXME: should expired items be marked as "seen?"
            # self.markItemSeen()
            self.expired = True
        finally:
            self.endRead()        
        self.beginChange()
        self.endChange()

    ##
    # Returns string with days or hours until this gets deleted
    def getExpirationTime(self):
        ret = "???"
        self.beginRead()
        self.feed.beginRead()
        try:
            if self.feed.expire == "never":
                ret = "never"
            else:
                if self.feed.expire == "feed":
                    expireTime = self.feed.expireTime
                elif self.feed.expire == "system":
                    expireTime = timedelta(days=config.get(config.EXPIRE_AFTER_X_DAYS))
                
                    exp = expireTime - (datetime.now() - self.getDownloadedTime())
                    if exp.days > 0:
                        ret = "%d days" % exp.days
                    elif exp.seconds > 3600:
                        ret = "%d hours" % (exp.seconds/3600)
                    else:
                        ret = "%d minutes" % (exp.seconds/60)
        finally:
            self.feed.endRead()
            self.endRead()
        return ret

    def getKeep(self):
        self.beginRead()
        ret = self.keep
        self.endRead()
        return ret

    def setKeep(self,val):
        self.beginRead()
        self.keep = val
        self.endRead()
        self.beginChange()
        self.endChange()

    ##
    # returns true iff item has been seen
    def getSeen(self):
        self.beginRead()
        ret = self.seen
        self.endRead()
        return ret

    ##
    # Marks the item as seen
    def markItemSeen(self):
        self.beginChange()
        try:
            self.seen = True
        finally:
            self.endChange()

    ##
    # Returns a list of downloaders associated with this object
    def getDownloaders(self):
        self.beginRead()
        ret = self.downloaders
        self.endRead()
        return ret

    def getRSSID(self):
        self.beginRead()
        try:
            ret = self.entry["id"]
        finally:
            self.endRead()
        return ret

    ##
    # Returns the vidinfo object associated with this item
    def getVidInfo(self):
        self.beginRead()
        ret = self.vidinfo
        self.endRead()
        return ret

    def setAutoDownloaded(self,autodl = True):
        self.beginRead()
        self.autoDownloaded = autodl
        self.endRead()

    def getPendingReason(self):
        ret = ""
        self.beginRead()
        ret = self.pendingReason
        self.endRead()
        return ret

    ##
    # Returns true iff item was auto downloaded
    def getAutoDownloaded(self):
        self.beginRead()
        ret = self.autoDownloaded
        self.endRead()
        return ret

    ##
    # Returns the linkNumber
    def getLinkNumber(self):
        self.beginRead()
        try:
            ret = self.linkNumber
        finally:
            self.endRead()
        return ret

    def download(self,autodl=False):
        thread = Thread(target = lambda:self.actualDownload(autodl))
        thread.setDaemon(False)
        thread.start()

    ##
    # Starts downloading the item
    def actualDownload(self,autodl=False):
        threadpriority.setNormalPriority()
        spawn = True
        self.beginRead()
        try:
            # FIXME: For locking reasons, downloaders don't always
            #        call beginChange() and endChange(), so we have to
            #        recompute this filter
            defaultDatabase.recomputeFilter(self.manualDownloads)
            if ((not autodl) and 
                self.manualDownloads.len() >= config.get(config.MAX_MANUAL_DOWNLOADS)):
                self.pendingManualDL = True
                self.pendingReason = "Too many manual downloads"
                spawn = False
                self.expired = False
            else:
                #Don't spawn two downloaders
                if self.startingDownload:
                    spawn = False
                else:
                    self.setAutoDownloaded(autodl)
                    self.expired = False
                    self.keep = False
                    self.pendingManualDL = False
                    self.lastDownloadFailed = False
                    downloadURLs = map(lambda x:x.getURL(),self.downloaders)
                    self.startingDownload = True
            try:
                enclosures = self.entry["enclosures"]
            except:
                enclosures = []
        finally:
            self.endRead()
        self.beginChange()
        self.endChange()

        if not spawn:
            return

        try:
            for enclosure in enclosures:
                try:
                    if not enclosure["url"] in downloadURLs:
                        dler = self.dlFactory.getDownloader(enclosure["url"])
                        if dler != None:
                            self.beginRead()
                            try:
                                self.downloaders.append(dler)
                            finally:
                                self.endRead()
                        else:
                            self.beginRead()
                            try:
                                self.lastDownloadFailed = True
                            finally:
                                self.endRead()
                except KeyError:
                    pass
        except KeyError:
            pass
        self.beginRead()
        try:
            self.startingDownload = False
        finally:
            self.endRead()
        self.beginChange()
        self.endChange()


    ##
    # Returns a link to the thumbnail of the video
    def getThumbnail(self):
        ret = None
        self.beginRead()
        try:
            if self.entry.has_key('enclosures'):
                for enc in self.entry.enclosures:
                    if enc.has_key('thumbnail') and enc['thumbnail'].has_key('url'):
                        ret = enc["thumbnail"]["url"]
                        break
            if (ret is None and self.entry.has_key('thumbnail') and
                self.entry['thumbnail'].has_key('url')):
                ret =  self.entry["thumbnail"]["url"]
        finally:
            self.endRead()
        if ret is None:
            ret = "resource:images/thumb.png"
        return ret
    ##
    # returns the title of the item
    def getTitle(self):
        self.beginRead()
        try:
            ret = self.entry.title
        except:
            try:
                ret = self.entry.enclosures[0]["url"]
            except:
                ret = ""
        self.endRead()
        return ret

    ##
    # Returns valid XHTML containing a description of the video
    def getDescription(self):
        self.beginRead()
        try:
            ret = xhtmlify('<span>'+unescape(self.entry.enclosures[0]["text"])+'</span>')
        except:
            try:
                ret = xhtmlify('<span>'+unescape(self.entry.description)+'</span>')
            except:
                ret = '<span />'
        self.endRead()
        return ret

    ##
    # Stops downloading the item
    def stopDownload(self):
        for dler in self.downloaders:
            dler.stop()
            dler.remove()
        self.beginRead()
        try:
            self.downloaders = []
            self.keep = False
            self.pendingManualDL = False
        finally:
            self.endRead()

    ##
    # returns status of the download in plain text
    def getState(self):
        self.beginRead()
        self.feed.beginRead()
        try:
            state = self.getStateNoAuto()
            if ((state == "stopped") and 
                self.feed.isAutoDownloadable() and 
                (self.feed.getEverything or 
                 self.getPubDateParsed() >= self.feed.startfrom)):
                state = "autopending"
        finally:
            self.feed.endRead()
            self.endRead()
            
        return state
    

    ##
    # returns the state of the download, without checking automatic dl
    # eligibility
    def getStateNoAuto(self):
        self.beginRead()
        try:
            if self.expired:
                state = "expired"
            elif self.startingDownload:
                state = "downloading"
            elif self.keep:
                state = "saved"
            elif self.pendingManualDL:
                state = "manualpending"
            elif len(self.downloaders) == 0:
                if self.lastDownloadFailed:
                    state = "failed"
                else:
                    state = "stopped"
            else:
                state = "finished"
                for dler in self.downloaders:
                    newState = dler.getState()
                    if newState != "finished":
                        state = newState
                    if state == "failed":
                        break
            if (state == "finished" or state=="uploading") and self.seen:
                state = "watched"
        finally:
            self.endRead()
        return state

    def getFailureReason(self):
        ret = ""
        self.beginRead()
        try:
            if self.lastDownloadFailed:
                ret = "Could not connect to server"
            else:
                for dler in self.downloaders:
                    if dler.getState() == "failed":
                        ret = dler.getReasonFailed()
                        break
        finally:
            self.endRead()
        return ret
                

    ##
    # returns status of the download in plain text
    def getTotalSize(self):
        size = 0
        for dler in self.downloaders:
            try:
                size += dler.getTotalSize()
            except:
                pass
        if size == 0:
            return ""
        mb = size / 1000000
        if mb <  100:
            return '%1.1f' % mb + " MB"
        elif mb < 1000:
            return '%1.0f' % mb + " MB"
        else:
            return '%1.1f' % (mb/1000) + " GB"
        return size

    ##
    # returns status of the download in plain text
    def getCurrentSize(self):
        size = 0
        for dler in self.downloaders:
            size += dler.getCurrentSize()
        if size == 0:
            return ""
        mb = size / 1000000
        if mb <  100:
            return '%1.1f' % mb + " MB"
        elif mb < 1000:
            return '%1.0f' % mb + " MB"
        else:
            return '%1.1f' % (mb/1000) + " GB"
        return size

    ##
    # Returns string containing three digit percent finished
    # "000" through "100" This is used to choose an image for the progress bar
    def threeDigitPercentDone(self):
        ret = "000"
        self.beginRead()
        try:
            size = 0
            dled = 0
            for dler in self.downloaders:
                try:
                    size += dler.getTotalSize()
                    dled += dler.getCurrentSize()
                except:
                    pass
            if size > 0:
                percent = (100*dled)/size
                ret = '%03d' % percent
        finally:
            self.endRead()
        return ret
    ##
    # returns string with estimate time until download completes
    def downloadETA(self):
        secs = 0
        for dler in self.downloaders:
            secs += dler.getETA()
        if secs == 0:
            return 'starting up...'
        elif (secs < 120):
            return '%1.0f' % secs+" secs left"
        elif (secs < 6000):
            return '%1.0f' % (secs/60)+" mins left"
        else:
            return '%1.1f' % (secs/3600)+" hours left"

    ##
    # Returns the published date of the item
    def getPubDate(self):
        self.beginRead()
        try:
            try:
                ret = datetime(*self.entry.modified_parsed[0:7]).strftime("%b %d %Y")
            except:
                ret = ""
        finally:
            self.endRead()
        return ret
    
    ##
    # Returns the published date of the item as a datetime object
    def getPubDateParsed(self):
        self.beginRead()
        try:
            try:
                ret = datetime(*self.entry.modified_parsed[0:7])
            except:
                ret = ""
        finally:
            self.endRead()
        return ret

    ##
    # returns the date this video was released or when it was published
    def getReleaseDate(self):
        if hasattr(self,'releaseDate'):
            return self.releaseDate            
        self.beginRead()
        try:
            try:
                self.releaseDate = datetime(*self.entry.enclosures[0].modified_parsed[0:7]).strftime("%b %d %Y")
            except:
                try:
                    self.releaseDate = datetime(*self.entry.modified_parsed[0:7]).strftime("%b %d %Y")
                except:
                    self.releaseDate = ""
        finally:
            self.endRead()
        return self.releaseDate

    ##
    # returns the date this video was released or when it was published
    def getReleaseDateObj(self):
        if hasattr(self,'releaseDateObj'):
            return self.releaseDateObj
        self.beginRead()
        try:
            try:
                self.releaseDateObj = datetime(*self.entry.enclosures[0].modified_parsed[0:7])
            except:
                try:
                    self.releaseDateObj = datetime(*self.entry.modified_parsed[0:7])
                except:
                    self.releaseDateObj = datetime.min
        finally:
            self.endRead()
        return self.releaseDateObj

    ##
    # returns string with the play length of the video
    def getDuration(self):
        secs = 0
        #FIXME get this from VideoInfo
        if secs == 0:
            return ""
        if (secs < 120):
            return '%1.0f' % secs+" secs"
        elif (secs < 6000):
            return '%1.0f' % (secs/60)+" mins"
        else:
            return '%1.1f' % (secs/3600)+" hours"

    ##
    # return keyword tags associated with the video separated by commas
    def getTags(self):
        self.beginRead()
        try:
            try:
                ret = self.entry.categories.join(", ")
            except:
                ret = ""
        finally:
            self.endRead()
        return ret

    ##
    # return the license associated with the video
    def getLicence(self):
        self.beginRead()
        try:
            try:
                ret = self.entry.license
            except:
                try:
                    ret = self.feed.getLicense()
                except:
                    ret = ""
        finally:
            self.endRead()
        return ret

    ##
    # return the people associated with the video, separated by commas
    def getPeople(self):
        ret = []
        self.beginRead()
        try:
            try:
                for role in self.entry.enclosures[0].roles:
                    for person in self.entry.enclosures[0].roles[role]:
                        ret.append(person)
                for role in self.entry.roles:
                    for person in self.entry.roles[role]:
                        ret.append(person)
            except:
                pass
        finally:
            self.endRead()
        return ret.join(', ')

    ##
    # returns the URL of the webpage associated with the item
    def getLink(self):
        self.beginRead()
        try:
            try:
                ret = self.entry.link
            except:
                ret = ""
        finally:
            self.endRead()
        return ret

    ##
    # returns the URL of the payment page associated with the item
    def getPaymentLink(self):
        self.beginRead()
        try:
            try:
                ret = self.entry.enclosures[0].payment_url
            except:
                try:
                    ret = self.entry.payment_url
                except:
                    ret = ""
        finally:
            self.endRead()
        return ret

    ##
    # returns a snippet of HTML containing a link to the payment page
    # HTML has already been sanitized by feedparser
    def getPaymentHTML(self):
        self.beginRead()
        try:
            try:
                ret = self.entry.enclosures[0].payment_html
            except:
                try:
                    ret = self.entry.payment_html
                except:
                    ret = ""
        finally:
            self.endRead()
        return '<span>'+ret+'</span>'

    ##
    # Updates an item with new data
    #
    # @param entry a dict object containing the new data
    def update(self, entry):
        self.beginChange()
        try:
            self.entry = entry
        finally:
            self.endChange()

    ##
    # marks the item as having been downloaded now
    def setDownloadedTime(self):
        self.beginRead()
        try:
            self.downloadedTime = datetime.now()
        finally:
            self.endRead()

    ##
    # gets the time the video was downloaded
    # Only valid if the state of this item is "finished"
    def getDownloadedTime(self):
        self.beginRead()
        try:
            try:
                ret = self.downloadedTime
            except:
                ret = datetime.min
        finally:
            self.endRead()
        return ret

    ##
    # gets the time the video started downloading
    def getDLStartTime(self):
        self.beginRead()
        try:
            try:
                ret = self.DLStartTime
            except:
                ret = None
        finally:
            self.endRead()
        return ret

    ##
    # Returns the filename of the first downloaded video or the empty string
    def getFilename(self):
        self.beginRead()
        try:
            try:
                ret = self.downloaders[0].getFilename()
            except:
                ret = ""
        finally:
            self.endRead()
        return ret

    ##
    # Returns a list with the filenames of all of the videos in the item
    def getFilenames(self):
        ret = []
        self.beginRead()
        try:
            try:
                for dl in self.downloaders:
                    ret.append(dl.getFilename())
            except:
                pass
        finally:
            self.endRead()
        return ret

    def getRSSEntry(self):
        self.beginRead()
        try:
            ret = self.entry
        finally:
            self.endRead()
        return ret

    def remove(self):
        for dler in self.downloaders:
            dler.remove()
        DDBObject.remove(self)

    ##
    # Called by pickle during serialization
    def __getstate__(self):
        temp = copy(self.__dict__)
        return (3,temp)

    ##
    # Called by pickle during serialization
    def __setstate__(self,state):
        (version, data) = state
        if version == 0:
            data['pendingManualDL'] = False
            if not data.has_key('linkNumber'):
                data['linkNumber'] = 0
            version += 1
        if version == 1:
            data['keep'] = False
            data['pendingReason'] = ""
            version += 1
        if version == 2:
            data['creationTime'] = datetime.now()
            version += 1
        assert(version == 3)
        data['startingDownload'] = False
        self.__dict__ = data

##
# An Item that exists as a file, but not as a download
class FileItem(Item):
    def getEntry(self,filename):
        return FeedParserDict({'title':filename,'enclosures':[{'url':filename}]})

    def __init__(self,feed,filename):
        Item.__init__(self,feed,self.getEntry(filename))
        self.filename = filename

    def getState(self):
        return "finished"

    def getDownloadedTime(self):
        self.beginRead()
        try:
            try:
                time = datetime.fromtimestamp(os.getctime(self.filename))
            except:
                return datetime.min
        finally:
            self.endRead()

    def getFilename(self):
        ret = ''
        try:
            ret = self.filename
        except:
            pass
        return ret

    def getFilenames(self):
        ret = []
        try:
            ret = [self.filename]
        except:
            pass
        return ret
