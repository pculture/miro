# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.0 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

# Written by Bram Cohen

from __future__ import division

from time import time


class DownloaderFeedback(object):

    def __init__(self, choker, upfunc, upfunc2, downfunc, uptotal, downtotal,
                 remainingfunc, leftfunc, file_length, finflag, downloader,
                 files):
        self.downloader = downloader
        self.picker = downloader.picker
        self.storage = downloader.storage
        self.choker = choker
        self.upfunc = upfunc
        self.upfunc2 = upfunc2
        self.downfunc = downfunc
        self.uptotal = uptotal
        self.downtotal = downtotal
        self.remainingfunc = remainingfunc
        self.leftfunc = leftfunc
        self.file_length = file_length
        self.finflag = finflag
        self.files = files
        self.lastids = []

    def _rotate(self):
        cs = self.choker.connections
        for peerid in self.lastids:
            for i in xrange(len(cs)):
                if cs[i].id == peerid:
                    return cs[i:] + cs[:i]
        return cs

    def collect_spew(self):
        l = [ ]
        cs = self._rotate()
        self.lastids = [c.id for c in cs]
        for c in cs:
            rec = {}
            rec['id'] = c.id
            rec["ip"] = c.ip
            rec["is_optimistic_unchoke"] = (c is self.choker.connections[0])
            if c.locally_initiated:
                rec["initiation"] = "L"
            else:
                rec["initiation"] = "R"
            u = c.upload
            rec["upload"] = (u.measure.get_total(), int(u.measure.get_rate()),
                             u.interested, u.choked)

            d = c.download
            rec["download"] = (d.measure.get_total(),int(d.measure.get_rate()),
                               d.interested, d.choked, d.is_snubbed())
            rec['completed'] = 1 - d.have.numfalse / len(d.have)
            rec['speed'] = d.connection.download.peermeasure.get_rate()
            l.append(rec)
        return l

    def get_statistics(self, spewflag = False, fileflag = False):
        status = {}
        numSeeds = 0
        numPeers = 0
        for d in self.downloader.downloads:
            if d.have.numfalse == 0:
                numSeeds += 1
            else:
                numPeers += 1
        status['numSeeds'] = numSeeds
        status['numPeers'] = numPeers
        status['upRate'] = self.upfunc()
        status['upRate2'] = self.upfunc2()
        status['upTotal'] = self.uptotal()
        missingPieces = 0
        numCopyList = []
        numCopies = 0
        for i in self.picker.crosscount:
            missingPieces += i
            if missingPieces == 0:
                numCopies += 1
            else:
                fraction = 1 - missingPieces / self.picker.numpieces
                numCopyList.append(fraction)
                if fraction == 0 or len(numCopyList) >= 3:
                    break
        numCopies -= numSeeds
        if self.picker.numgot == self.picker.numpieces:
            numCopies -= 1
        status['numCopies'] = numCopies
        status['numCopyList'] = numCopyList
        status['discarded'] = self.downloader.discarded_bytes
        status['storage_numcomplete'] = self.storage.stat_numfound + \
                                        self.storage.stat_numdownloaded
        status['storage_dirty'] = len(self.storage.stat_dirty)
        status['storage_active'] = len(self.storage.stat_active)
        status['storage_new'] = len(self.storage.stat_new)
        status['storage_numflunked'] = self.storage.stat_numflunked

        if spewflag:
            status['spew'] = self.collect_spew()
            status['bad_peers'] = self.downloader.bad_peers
        if fileflag:
            undl = self.storage.storage.undownloaded
            unal = self.storage.storage.unallocated
            status['files_left'] = [undl[fname] for fname in self.files]
            status['files_allocated'] = [not unal[fn] for fn in self.files]
        if self.finflag.isSet():
            status['downRate'] = 0
            status['downTotal'] = self.downtotal()
            status['fractionDone'] = 1
            return status
        timeEst = self.remainingfunc()
        status['timeEst'] = timeEst

        if self.file_length > 0:
            fractionDone = 1 - self.leftfunc() / self.file_length
        else:
            fractionDone = 1
        status.update({
            "fractionDone" : fractionDone,
            "downRate" : self.downfunc(),
            "downTotal" : self.downtotal()
            })
        return status
