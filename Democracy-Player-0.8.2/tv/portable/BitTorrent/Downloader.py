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

from random import shuffle
from time import time

from BitTorrent.CurrentRateMeasure import Measure
from BitTorrent.bitfield import Bitfield


class PerIPStats(object):

    def __init__(self):
        self.numgood = 0
        self.bad = {}
        self.numconnections = 0
        self.lastdownload = None
        self.peerid = None


class BadDataGuard(object):

    def __init__(self, download):
        self.download = download
        self.ip = download.connection.ip
        self.downloader = download.downloader
        self.stats = self.downloader.perip[self.ip]
        self.lastindex = None

    def bad(self, index, bump = False):
        self.stats.bad.setdefault(index, 0)
        self.stats.bad[index] += 1
        if self.ip not in self.downloader.bad_peers:
            self.downloader.bad_peers[self.ip] = (False, self.stats)
        if self.download is not None:
            self.downloader.kick(self.download)
            self.download = None
        elif len(self.stats.bad) > 1 and self.stats.numconnections == 1 and \
             self.stats.lastdownload is not None:
            # kick new connection from same IP if previous one sent bad data,
            # mainly to give the algorithm time to find other bad pieces
            # in case the peer is sending a lot of bad data
            self.downloader.kick(self.stats.lastdownload)
        if len(self.stats.bad) >= 3 and len(self.stats.bad) > \
           self.stats.numgood // 30:
            self.downloader.ban(self.ip)
        elif bump:
            self.downloader.picker.bump(index)

    def good(self, index):
        # lastindex is a hack to only increase numgood for by one for each good
        # piece, however many chunks came from the connection(s) from this IP
        if index != self.lastindex:
            self.stats.numgood += 1
            self.lastindex = index


class SingleDownload(object):

    def __init__(self, downloader, connection):
        self.downloader = downloader
        self.connection = connection
        self.choked = True
        self.interested = False
        self.active_requests = []
        self.measure = Measure(downloader.config['max_rate_period'])
        self.peermeasure = Measure(max(downloader.storage.piece_size / 10000,
                                       20))
        self.have = Bitfield(downloader.numpieces)
        self.last = 0
        self.example_interest = None
        self.backlog = 2
        self.guard = BadDataGuard(self)

    def _backlog(self):
        backlog = 2 + int(4 * self.measure.get_rate() /
                          self.downloader.chunksize)
        if backlog > 50:
            backlog = max(50, int(.075 * backlog))
        self.backlog = backlog
        return backlog

    def disconnected(self):
        self.downloader.lost_peer(self)
        for i in xrange(len(self.have)):
            if self.have[i]:
                self.downloader.picker.lost_have(i)
        self._letgo()
        self.guard.download = None

    def _letgo(self):
        if not self.active_requests:
            return
        if self.downloader.storage.endgame:
            self.active_requests = []
            return
        lost = []
        for index, begin, length in self.active_requests:
            self.downloader.storage.request_lost(index, begin, length)
            if index not in lost:
                lost.append(index)
        self.active_requests = []
        ds = [d for d in self.downloader.downloads if not d.choked]
        shuffle(ds)
        for d in ds:
            d._request_more(lost)
        for d in self.downloader.downloads:
            if d.choked and not d.interested:
                for l in lost:
                    if d.have[l] and self.downloader.storage.do_I_have_requests(l):
                        d.interested = True
                        d.connection.send_interested()
                        break

    def got_choke(self):
        if not self.choked:
            self.choked = True
            self._letgo()

    def got_unchoke(self):
        if self.choked:
            self.choked = False
            if self.interested:
                self._request_more()

    def got_piece(self, index, begin, piece):
        try:
            self.active_requests.remove((index, begin, len(piece)))
        except ValueError:
            self.downloader.discarded_bytes += len(piece)
            return False
        if self.downloader.storage.endgame:
            self.downloader.all_requests.remove((index, begin, len(piece)))
        self.last = time()
        self.measure.update_rate(len(piece))
        self.downloader.measurefunc(len(piece))
        self.downloader.downmeasure.update_rate(len(piece))
        if not self.downloader.storage.piece_came_in(index, begin, piece,
                                                     self.guard):
            if self.downloader.storage.endgame:
                while self.downloader.storage.do_I_have_requests(index):
                    nb, nl = self.downloader.storage.new_request(index)
                    self.downloader.all_requests.append((index, nb, nl))
                for d in self.downloader.downloads:
                    d.fix_download_endgame()
                return False
            ds = [d for d in self.downloader.downloads if not d.choked]
            shuffle(ds)
            for d in ds:
                d._request_more([index])
            return False
        if self.downloader.storage.do_I_have(index):
            self.downloader.picker.complete(index)
        if self.downloader.storage.endgame:
            for d in self.downloader.downloads:
                if d is not self and d.interested:
                    if d.choked:
                        d.fix_download_endgame()
                    else:
                        try:
                            d.active_requests.remove((index, begin, len(piece)))
                        except ValueError:
                            continue
                        d.connection.send_cancel(index, begin, len(piece))
                        d.fix_download_endgame()
        self._request_more()
        if self.downloader.picker.am_I_complete():
            for d in [i for i in self.downloader.downloads if i.have.numfalse == 0]:
                d.connection.close()
        return self.downloader.storage.do_I_have(index)

    def _want(self, index):
        return self.have[index] and self.downloader.storage.do_I_have_requests(index)

    def _request_more(self, indices = None):
        assert not self.choked
        if len(self.active_requests) >= self._backlog():
            return
        if self.downloader.storage.endgame:
            self.fix_download_endgame()
            return
        lost_interests = []
        while len(self.active_requests) < self.backlog:
            if indices is None:
                interest = self.downloader.picker.next(self._want, self.have.numfalse == 0)
            else:
                interest = None
                for i in indices:
                    if self.have[i] and self.downloader.storage.do_I_have_requests(i):
                        interest = i
                        break
            if interest is None:
                break
            if not self.interested:
                self.interested = True
                self.connection.send_interested()
            self.example_interest = interest
            self.downloader.picker.requested(interest, self.have.numfalse == 0)
            while len(self.active_requests) < (self.backlog-2) * 5 + 2:
                begin, length = self.downloader.storage.new_request(interest)
                self.active_requests.append((interest, begin, length))
                self.connection.send_request(interest, begin, length)
                if not self.downloader.storage.do_I_have_requests(interest):
                    lost_interests.append(interest)
                    break
        if not self.active_requests and self.interested:
            self.interested = False
            self.connection.send_not_interested()
        if lost_interests:
            for d in self.downloader.downloads:
                if d.active_requests or not d.interested:
                    continue
                if d.example_interest is not None and self.downloader.storage.do_I_have_requests(d.example_interest):
                    continue
                for lost in lost_interests:
                    if d.have[lost]:
                        break
                else:
                    continue
                interest = self.downloader.picker.next(d._want, d.have.numfalse == 0)
                if interest is None:
                    d.interested = False
                    d.connection.send_not_interested()
                else:
                    d.example_interest = interest
        if self.downloader.storage.endgame:
            self.downloader.all_requests = []
            for d in self.downloader.downloads:
                self.downloader.all_requests.extend(d.active_requests)
            for d in self.downloader.downloads:
                d.fix_download_endgame()

    def fix_download_endgame(self):
        want = [a for a in self.downloader.all_requests if self.have[a[0]] and a not in self.active_requests]
        if self.interested and not self.active_requests and not want:
            self.interested = False
            self.connection.send_not_interested()
            return
        if not self.interested and want:
            self.interested = True
            self.connection.send_interested()
        if self.choked or len(self.active_requests) >= self._backlog():
            return
        shuffle(want)
        del want[self.backlog - len(self.active_requests):]
        self.active_requests.extend(want)
        for piece, begin, length in want:
            self.connection.send_request(piece, begin, length)

    def got_have(self, index):
        if self.have[index]:
            return
        if index == self.downloader.numpieces-1:
            self.peermeasure.update_rate(self.downloader.storage.total_length-
              (self.downloader.numpieces-1)*self.downloader.storage.piece_size)
        else:
            self.peermeasure.update_rate(self.downloader.storage.piece_size)
        self.have[index] = True
        self.downloader.picker.got_have(index)
        if self.downloader.picker.am_I_complete() and self.have.numfalse == 0:
            self.connection.close()
            return
        if self.downloader.storage.endgame:
            self.fix_download_endgame()
        elif self.downloader.storage.do_I_have_requests(index):
            if not self.choked:
                self._request_more([index])
            else:
                if not self.interested:
                    self.interested = True
                    self.connection.send_interested()

    def got_have_bitfield(self, have):
        if self.downloader.picker.am_I_complete() and have.numfalse == 0:
            self.connection.close()
            return
        self.have = have
        for i in xrange(len(self.have)):
            if self.have[i]:
                self.downloader.picker.got_have(i)
        if self.downloader.storage.endgame:
            for piece, begin, length in self.downloader.all_requests:
                if self.have[piece]:
                    self.interested = True
                    self.connection.send_interested()
                    return
        for i in xrange(len(self.have)):
            if self.have[i] and self.downloader.storage.do_I_have_requests(i):
                self.interested = True
                self.connection.send_interested()
                return

    def get_rate(self):
        return self.measure.get_rate()

    def is_snubbed(self):
        return time() - self.last > self.downloader.snub_time


class Downloader(object):

    def __init__(self, config, storage, picker, numpieces, downmeasure,
                 measurefunc, kickfunc, banfunc):
        self.config = config
        self.storage = storage
        self.picker = picker
        self.chunksize = config['download_slice_size']
        self.downmeasure = downmeasure
        self.numpieces = numpieces
        self.snub_time = config['snub_time']
        self.measurefunc = measurefunc
        self.kickfunc = kickfunc
        self.banfunc = banfunc
        self.downloads = []
        self.perip = {}
        self.bad_peers = {}
        self.discarded_bytes = 0

    def make_download(self, connection):
        ip = connection.ip
        perip = self.perip.get(ip)
        if perip is None:
            perip = PerIPStats()
            self.perip[ip] = perip
        perip.numconnections += 1
        d = SingleDownload(self, connection)
        perip.lastdownload = d
        perip.peerid = connection.id
        self.downloads.append(d)
        return d

    def lost_peer(self, download):
        self.downloads.remove(download)
        ip = download.connection.ip
        self.perip[ip].numconnections -= 1
        if self.perip[ip].lastdownload == download:
            self.perip[ip].lastdownload = None

    def kick(self, download):
        if not self.config['retaliate_to_garbled_data']:
            return
        ip = download.connection.ip
        peerid = download.connection.id
        # kickfunc will schedule connection.close() to be executed later; we
        # might now be inside RawServer event loop with events from that
        # connection already queued, and trying to handle them after doing
        # close() now could cause problems.
        self.kickfunc(download.connection)

    def ban(self, ip):
        if not self.config['retaliate_to_garbled_data']:
            return
        self.banfunc(ip)
        self.bad_peers[ip] = (True, self.perip[ip])
