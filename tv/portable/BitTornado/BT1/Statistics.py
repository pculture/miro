# Written by Edward Keyes
# see LICENSE.txt for license information

from copy import copy
try:
    True
except:
    True = 1
    False = 0

class Statistics:
    def __init__(self, upmeasure, downmeasure, connecter, httpdl,
                 ratelimiter, rerequest_lastfailed, fdatflag):
        self.upmeasure = upmeasure
        self.downmeasure = downmeasure
        self.connecter = connecter
        self.httpdl = httpdl
        self.ratelimiter = ratelimiter
        self.downloader = connecter.downloader
        self.picker = connecter.downloader.picker
        self.storage = connecter.downloader.storage
        self.torrentmeasure = connecter.downloader.totalmeasure
        self.rerequest_lastfailed = rerequest_lastfailed
        self.fdatflag = fdatflag
        self.fdatactive = False
        self.upTotal = 0.0
        self.downTotal = 0.0
        self.shareRating = 0.0
        self.numSeeds = 0
        self.numOldSeeds = 0
        self.numCopies = 0.0
        self.numCopies2 = 0.0
        self.numPeers = 0
        self.last_failed = 1
        self.external_connection_made = 0
        self.piecescomplete = None
        self.backgroundallocating = False
        self.storage_totalpieces = len(self.storage.hashes)
        self.upRate = 0
        self.upSlots = 0


    def set_dirstats(self, files, numpieces, piece_length):
        self.piecescomplete = 0
        self.filelistupdated = True
        self.bgalloc_wasactive = False
#        self.filenames = {}
        self.filepieces = {}
        self.filepieces2 = {}
        self.filecomplete = {}
        self.fileinplace = {}
        start = 0L
        for i in range(len(files)):
#            self.filenames[i] = files[i][0]
            self.filepieces[i] = []
            self.filepieces2[i] = []
            l = files[i][1]
            if l == 0:
                self.filecomplete[i] = True
                self.fileinplace[i] = True
            else:
                self.filecomplete[i] = False
                self.fileinplace[i] = False
                for piece in range(int(start/piece_length),
                                   int((start+l-1)/piece_length)+1):
                    self.filepieces[i].append(piece)
                    self.filepieces2[i].append(piece)
                start += l


    def update(self):
        self.upTotal = self.upmeasure.get_total()
        self.downTotal = self.downmeasure.get_total()
        self.last_failed = self.rerequest_lastfailed()
        if self.connecter.external_connection_made:
            self.external_connection_made = 1
        if self.downTotal > 0:
            self.shareRating = float(self.upTotal)/self.downTotal
        else:
            if self.upTotal == 0:
               self.shareRating = 0.0
            else:
               self.shareRating = -1.0
        self.downloader = self.connecter.downloader
        self.picker = self.downloader.picker
        self.torrentmeasure = self.downloader.totalmeasure
        self.torrentRate = self.torrentmeasure.get_rate()
        self.torrentTotal = self.torrentmeasure.get_total()
        self.numSeeds = self.picker.seeds_connected
        self.numOldSeeds = self.downloader.num_disconnected_seeds()
        self.numPeers = len(self.downloader.downloads)-self.numSeeds
        self.numCopies = 0.0
        for i in self.picker.crosscount:
            if i==0:
                self.numCopies+=1
            else:
                self.numCopies+=1-float(i)/self.picker.numpieces
                break
        self.numCopies2 = 0.0
        if self.picker.done:
            self.numCopies2 = self.numCopies + 1
        else:
            for i in self.picker.crosscount2:
                if i==0:
                    self.numCopies2+=1
                else:
                    self.numCopies2+=1-float(i)/self.picker.numpieces
                    break
        self.discarded = self.downloader.discarded
        self.numSeeds += self.httpdl.seedsfound
        self.numOldSeeds += self.httpdl.seedsfound
        if self.numPeers == 0 or self.picker.numpieces == 0:
            self.percentDone = 0.0
        else:
            self.percentDone = 100.0*(float(self.picker.totalcount)/self.picker.numpieces)/self.numPeers

        self.backgroundallocating = self.storage.bgalloc_active
        self.storage_active = len(self.storage.stat_active)
        self.storage_new = len(self.storage.stat_new)
        self.storage_dirty = len(self.storage.dirty)
        numdownloaded = self.storage.stat_numdownloaded
        self.storage_justdownloaded = numdownloaded
        self.storage_numcomplete = self.storage.stat_numfound + numdownloaded
        self.storage_numflunked = self.storage.stat_numflunked
        self.storage_isendgame = self.downloader.endgamemode

        self.peers_kicked = self.downloader.kicked.items()
        self.peers_banned = self.downloader.banned.items()

        try:
            self.upRate = int(self.ratelimiter.upload_rate/1000)
            assert self.upRate < 5000
        except:
            self.upRate = 0
        self.upSlots = self.ratelimiter.slots

        if self.fdatflag.isSet():
            if not self.fdatactive:
                self.fdatactive = True
                if self.piecescomplete is not None:
                    self.piecescomplete = 0
        else:
            self.fdatactive = False

        if self.fdatflag.isSet() and self.piecescomplete is not None:
            if ( self.piecescomplete != self.picker.numgot
                 or self.bgalloc_wasactive or self.storage.bgalloc_active ) :
                    self.piecescomplete = self.picker.numgot
                    self.bgalloc_wasactive = self.storage.bgalloc_active
                    self.filelistupdated = True
                    for i in range(len(self.filecomplete)):
                        if not self.filecomplete[i]:
                            newlist = []
                            for piece in self.filepieces[i]:
                                if not self.storage.have[piece]:
                                    newlist.append(piece)
                            self.filepieces[i] = newlist
                            if not newlist:
                                self.filecomplete[i] = True
                        if self.filecomplete[i] and not self.fileinplace[i]:
                            while self.filepieces2[i]:
                                piece = self.filepieces2[i][-1]
                                if self.storage.places[piece] != piece:
                                    break
                                del self.filepieces2[i][-1]
                            if not self.filepieces2[i]:
                                self.fileinplace[i] = True
                                self.storage.storage.set_readonly(i)

