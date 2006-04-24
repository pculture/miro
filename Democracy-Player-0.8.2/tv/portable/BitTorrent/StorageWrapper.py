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

from sha import sha
from array import array
from binascii import b2a_hex

from BitTorrent.bitfield import Bitfield
from BitTorrent import BTFailure, INFO, WARNING, ERROR, CRITICAL

def toint(s):
    return int(b2a_hex(s), 16)

def tobinary(i):
    return (chr(i >> 24) + chr((i >> 16) & 0xFF) +
        chr((i >> 8) & 0xFF) + chr(i & 0xFF))

NO_PLACE = -1

ALLOCATED = -1
UNALLOCATED = -2
FASTRESUME_PARTIAL = -3

class StorageWrapper(object):

    def __init__(self, storage, config, hashes, piece_size, finished,
            statusfunc, flag, data_flunked, infohash, errorfunc, resumefile):
        self.numpieces = len(hashes)
        self.storage = storage
        self.config = config
        check_hashes = config['check_hashes']
        self.hashes = hashes
        self.piece_size = piece_size
        self.data_flunked = data_flunked
        self.errorfunc = errorfunc
        self.total_length = storage.get_total_length()
        self.amount_left = self.total_length
        self.partial_mark = "BitTorrent - this part has not been "+\
                            "downloaded yet."+infohash+\
                            tobinary(config['download_slice_size'])
        if self.total_length <= piece_size * (self.numpieces - 1):
            raise BTFailure, 'bad data in responsefile - total too small'
        if self.total_length > piece_size * self.numpieces:
            raise BTFailure, 'bad data in responsefile - total too big'
        self.finished = finished
        self.numactive = array('H', [0] * self.numpieces)
        self.inactive_requests = [1] * self.numpieces
        self.amount_inactive = self.total_length
        self.endgame = False
        self.have = Bitfield(self.numpieces)
        self.waschecked = Bitfield(self.numpieces)
        if self.numpieces < 32768:
            typecode = 'h'
        else:
            typecode = 'l'
        self.places = array(typecode, [NO_PLACE] * self.numpieces)
        if not check_hashes:
            self.rplaces = array(typecode, range(self.numpieces))
            fastresume = True
        else:
            self.rplaces = self._load_fastresume(resumefile, typecode)
            if self.rplaces is not None:
                fastresume = True
            else:
                self.rplaces = array(typecode, [UNALLOCATED] * self.numpieces)
                fastresume = False
        self.holepos = 0
        self.stat_numfound = 0
        self.stat_numflunked = 0
        self.stat_numdownloaded = 0
        self.stat_active = {}
        self.stat_new = {}
        self.stat_dirty = {}
        self.download_history = {}
        self.failed_pieces = {}

        if self.numpieces == 0:
            return
        targets = {}
        total = 0
        if not fastresume:
            for i in xrange(self.numpieces):
                if self._waspre(i):
                    self.rplaces[i] = ALLOCATED
                    total += 1
                else:
                    targets[hashes[i]] = i
        if total and check_hashes:
            statusfunc('checking existing file', 0)
        def markgot(piece, pos):
            if self.have[piece]:
                if piece != pos:
                    return
                self.rplaces[self.places[pos]] = ALLOCATED
                self.places[pos] = self.rplaces[pos] = pos
                return
            self.places[piece] = pos
            self.rplaces[pos] = piece
            self.have[piece] = True
            self.amount_left -= self._piecelen(piece)
            self.amount_inactive -= self._piecelen(piece)
            self.inactive_requests[piece] = None
            if not fastresume:
                self.waschecked[piece] = True
            self.stat_numfound += 1
        lastlen = self._piecelen(self.numpieces - 1)
        partials = {}
        for i in xrange(self.numpieces):
            if not self._waspre(i):
                if self.rplaces[i] != UNALLOCATED:
                    raise BTFailure("--check_hashes 0 or fastresume info "
                                    "doesn't match file state (missing data)")
                continue
            elif fastresume:
                t = self.rplaces[i]
                if t >= 0:
                    markgot(t, i)
                    continue
                if t == UNALLOCATED:
		    #Changed to accomodate pre-allocation
		    continue
                if t == ALLOCATED:
                    continue
                if t!= FASTRESUME_PARTIAL:
                    raise BTFailure("Bad fastresume info (illegal value)")
                data = self.storage.read(self.piece_size * i,
                                         self._piecelen(i))
                self._check_partial(i, partials, data)
                self.rplaces[i] = ALLOCATED
            else:
                data = self.storage.read(piece_size * i, self._piecelen(i))
                sh = sha(buffer(data, 0, lastlen))
                sp = sh.digest()
                sh.update(buffer(data, lastlen))
                s = sh.digest()
                if s == hashes[i]:
                    markgot(i, i)
                elif s in targets and self._piecelen(i) == self._piecelen(targets[s]):
                    markgot(targets[s], i)
                elif not self.have[self.numpieces - 1] and sp == hashes[-1] and (i == self.numpieces - 1 or not self._waspre(self.numpieces - 1)):
                    markgot(self.numpieces - 1, i)
                else:
                    self._check_partial(i, partials, data)
                statusfunc(fractionDone = 1 - self.amount_left /
                           self.total_length)
            if flag.isSet():
                return
        self.amount_left_with_partials = self.amount_left
        for piece in partials:
            if self.places[piece] < 0:
                pos = partials[piece][0]
                self.places[piece] = pos
                self.rplaces[pos] = piece
                self._make_partial(piece, partials[piece][1])
        for i in xrange(self.numpieces):
            if self.rplaces[i] != UNALLOCATED:
                self.storage.allocated(piece_size * i, self._piecelen(i))
            if self.have[i]:
                self.storage.downloaded(piece_size * i, self._piecelen(i))

    def _waspre(self, piece):
        return self.storage.was_preallocated(piece * self.piece_size, self._piecelen(piece))

    def _piecelen(self, piece):
        if piece < self.numpieces - 1:
            return self.piece_size
        else:
            return self.total_length - piece * self.piece_size

    def _check_partial(self, pos, partials, data):
        index = None
        missing = False
        marklen = len(self.partial_mark)+4
        for i in xrange(0, len(data) - marklen,
                        self.config['download_slice_size']):
            if data[i:i+marklen-4] == self.partial_mark:
                ind = toint(data[i+marklen-4:i+marklen])
                if index is None:
                    index = ind
                    parts = []
                if ind >= self.numpieces or ind != index:
                    return
                parts.append(i)
            else:
                missing = True
        if index is not None and missing:
            i += self.config['download_slice_size']
            if i < len(data):
                parts.append(i)
            partials[index] = (pos, parts)

    def _make_partial(self, index, parts):
        length = self._piecelen(index)
        l = []
        self.inactive_requests[index] = l
        x = 0
        self.amount_left_with_partials -= self._piecelen(index)
        self.download_history[index] = {}
        request_size = self.config['download_slice_size']
        for x in xrange(0, self._piecelen(index), request_size):
            partlen = min(request_size, length - x)
            if x in parts:
                l.append((x, partlen))
                self.amount_left_with_partials += partlen
            else:
                self.amount_inactive -= partlen
                self.download_history[index][x] = None
        self.stat_dirty[index] = 1

    def _initalloc(self, pos, piece):
        assert self.rplaces[pos] < 0
        assert self.places[piece] == NO_PLACE
        p = self.piece_size * pos
        length = self._piecelen(pos)
        if self.rplaces[pos] == UNALLOCATED:
            self.storage.allocated(p, length)
        self.places[piece] = pos
        self.rplaces[pos] = piece
        # "if self.rplaces[pos] != ALLOCATED:" to skip extra mark writes
        mark = self.partial_mark + tobinary(piece)
        mark += chr(0xff) * (self.config['download_slice_size'] - len(mark))
        mark *= (length - 1) // len(mark) + 1
        self.storage.write(p, buffer(mark, 0, length))

    def _move_piece(self, oldpos, newpos):
        assert self.rplaces[newpos] < 0
        assert self.rplaces[oldpos] >= 0
        data = self.storage.read(self.piece_size * oldpos,
                                 self._piecelen(newpos))
        self.storage.write(self.piece_size * newpos, data)
        if self.rplaces[newpos] == UNALLOCATED:
            self.storage.allocated(self.piece_size * newpos, len(data))
        piece = self.rplaces[oldpos]
        self.places[piece] = newpos
        self.rplaces[oldpos] = ALLOCATED
        self.rplaces[newpos] = piece
        if not self.have[piece]:
            return
        data = data[:self._piecelen(piece)]
        if sha(data).digest() != self.hashes[piece]:
            raise BTFailure('data corrupted on disk - '
                            'maybe you have two copies running?')

    def _get_free_place(self):
        while self.rplaces[self.holepos] >= 0:
            self.holepos += 1
        return self.holepos

    def get_amount_left(self):
        return self.amount_left

    def do_I_have_anything(self):
        return self.amount_left < self.total_length

    def _make_inactive(self, index):
        length = self._piecelen(index)
        l = []
        x = 0
        request_size = self.config['download_slice_size']
        while x + request_size < length:
            l.append((x, request_size))
            x += request_size
        l.append((x, length - x))
        self.inactive_requests[index] = l

    def _load_fastresume(self, resumefile, typecode):
        if resumefile is not None:
            try:
                r = array(typecode)
                r.fromfile(resumefile, self.numpieces)
                return r
            except Exception, e:
                self.errorfunc(WARNING, "Couldn't read fastresume data: " +
                               str(e))
        return None

    def write_fastresume(self, resumefile):
        for i in xrange(self.numpieces):
            if self.rplaces[i] >= 0 and not self.have[self.rplaces[i]]:
                self.rplaces[i] = FASTRESUME_PARTIAL
        self.rplaces.tofile(resumefile)

    def get_have_list(self):
        return self.have.tostring()

    def do_I_have(self, index):
        return self.have[index]

    def do_I_have_requests(self, index):
        return not not self.inactive_requests[index]

    def new_request(self, index):
        # returns (begin, length)
        if self.inactive_requests[index] == 1:
            self._make_inactive(index)
        self.numactive[index] += 1
        self.stat_active[index] = 1
        if index not in self.stat_dirty:
            self.stat_new[index] = 1
        rs = self.inactive_requests[index]
        r = min(rs)
        rs.remove(r)
        self.amount_inactive -= r[1]
        if self.amount_inactive == 0:
            self.endgame = True
        return r

    def piece_came_in(self, index, begin, piece, source = None):
        if self.places[index] < 0:
            if self.rplaces[index] == ALLOCATED:
                self._initalloc(index, index)
            else:
                n = self._get_free_place()
                if self.places[n] >= 0:
                    oldpos = self.places[n]
                    self._move_piece(oldpos, n)
                    n = oldpos
                if self.rplaces[index] < 0 or index == n:
                    self._initalloc(n, index)
                else:
                    self._move_piece(index, n)
                    self._initalloc(index, index)

        if index in self.failed_pieces:
            old = self.storage.read(self.places[index] * self.piece_size +
                                    begin, len(piece))
            if old != piece:
                self.failed_pieces[index][self.download_history[index][begin]]\
                    = None
        self.download_history.setdefault(index, {})
        self.download_history[index][begin] = source

        self.storage.write(self.places[index] * self.piece_size + begin, piece)
        self.stat_dirty[index] = 1
        self.numactive[index] -= 1
        if self.numactive[index] == 0:
            del self.stat_active[index]
        if index in self.stat_new:
            del self.stat_new[index]
        if not self.inactive_requests[index] and not self.numactive[index]:
            del self.stat_dirty[index]
            if sha(self.storage.read(self.piece_size * self.places[index], self._piecelen(index))).digest() == self.hashes[index]:
                self.have[index] = True
                self.storage.downloaded(index * self.piece_size,
                                        self._piecelen(index))
                self.inactive_requests[index] = None
                self.waschecked[index] = True
                self.amount_left -= self._piecelen(index)
                self.stat_numdownloaded += 1
                for d in self.download_history[index].itervalues():
                    if d is not None:
                        d.good(index)
                del self.download_history[index]
                if index in self.failed_pieces:
                    for d in self.failed_pieces[index]:
                        if d is not None:
                            d.bad(index)
                    del self.failed_pieces[index]
                if self.amount_left == 0:
                    self.finished()
            else:
                self.data_flunked(self._piecelen(index), index)
                self.inactive_requests[index] = 1
                self.amount_inactive += self._piecelen(index)
                self.stat_numflunked += 1

                self.failed_pieces[index] = {}
                allsenders = {}
                for d in self.download_history[index].itervalues():
                    allsenders[d] = None
                if len(allsenders) == 1:
                    culprit = allsenders.keys()[0]
                    if culprit is not None:
                        culprit.bad(index, bump = True)
                    del self.failed_pieces[index] # found the culprit already
                return False
        return True

    def request_lost(self, index, begin, length):
        self.inactive_requests[index].append((begin, length))
        self.amount_inactive += length
        self.numactive[index] -= 1
        if not self.numactive[index] and index in self.stat_active:
            del self.stat_active[index]
            if index in self.stat_new:
                del self.stat_new[index]

    def get_piece(self, index, begin, length):
        if not self.have[index]:
            return None
        if not self.waschecked[index]:
            if sha(self.storage.read(self.piece_size * self.places[index], self._piecelen(index))).digest() != self.hashes[index]:
                raise BTFailure, 'told file complete on start-up, but piece failed hash check'
            self.waschecked[index] = True
        if begin + length > self._piecelen(index):
            return None
        return self.storage.read(self.piece_size * self.places[index] + begin, length)
