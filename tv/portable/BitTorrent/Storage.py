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

import os
from bisect import bisect_right
from array import array

from BitTorrent.obsoletepythonsupport import *

from BitTorrent import BTFailure


class FilePool(object):

    def __init__(self, max_files_open):
        self.max_files_open = max_files_open
        self.allfiles = {}
        self.handlebuffer = None
        self.handles = {}
        self.whandles = {}

    def close_all(self):
        failures = {}
        for filename, handle in self.handles.iteritems():
            try:
                handle.close()
            except Exception, e:
                failures[self.allfiles[filename]] = e
        self.handles.clear()
        self.whandles.clear()
        if self.handlebuffer is not None:
            del self.handlebuffer[:]
        for torrent, e in failures.iteritems():
            torrent.got_exception(e)

    def set_max_files_open(self, max_files_open):
        self.max_files_open = max_files_open
        self.close_all()
        if len(self.allfiles) > self.max_files_open:
            self.handlebuffer = []
        else:
            self.handlebuffer = None

    def add_files(self, files, torrent):
        for filename in files:
            if filename in self.allfiles:
                raise BTFailure('File '+filename+' belongs to another running '
                                'torrent')
        for filename in files:
            self.allfiles[filename] = torrent
        if self.handlebuffer is None and \
               len(self.allfiles) > self.max_files_open:
            self.handlebuffer = self.handles.keys()

    def remove_files(self, files):
        for filename in files:
            del self.allfiles[filename]
        if self.handlebuffer is not None and \
               len(self.allfiles) <= self.max_files_open:
            self.handlebuffer = None


# Make this a separate function because having this code in Storage.__init__()
# would make python print a SyntaxWarning (uses builtin 'file' before 'global')

def bad_libc_workaround():
    global file
    def file(name, mode = 'r', buffering = None):
        return open(name, mode)

class Storage(object):

    def __init__(self, config, filepool, files, check_only=False):
        self.filepool = filepool
        self.config = config
        self.ranges = []
        self.myfiles = {}
        self.tops = {}
        self.undownloaded = {}
        self.unallocated = {}
        total = 0
        for filename, length in files:
	    # Was self.unallocated[filename] = 0
	    # Changed to deal with pre-allocated space
            self.unallocated[filename] = 0
            self.undownloaded[filename] = length
            if length > 0:
                self.ranges.append((total, total + length, filename))
                self.myfiles[filename] = None
            total += length
            if os.path.exists(filename):
                if not os.path.isfile(filename):
                    raise BTFailure('File '+filename+' already exists, but '
                                    'is not a regular file')
                l = os.path.getsize(filename)
                if l > length and not check_only:
                    h = file(filename, 'rb+')
                    h.truncate(length)
                    h.close()
                    l = length
		# Changed to pre-allocate space
		if l < length:
		    h = file(filename, 'rb+')
		    h.seek(length-1)
		    h.write('.')
		    h.close()
                self.tops[filename] = length
            elif not check_only:
                f = os.path.split(filename)[0]
                if f != '' and not os.path.exists(f):
                    os.makedirs(f)
		# Changed to pre-allocate space
		h = file(filename, 'wb')
		h.seek(length-1)
		h.write('.')
		h.close()
        self.begins = [i[0] for i in self.ranges]
        self.total_length = total
        if check_only:
            return
        self.handles = filepool.handles
        self.whandles = filepool.whandles

        # Rather implement this as an ugly hack here than change all the
        # individual calls. Affects all torrent instances using this module.
        if config['enable_bad_libc_workaround']:
            bad_libc_workaround()

    def was_preallocated(self, pos, length):
        for filename, begin, end in self._intervals(pos, length):
            if self.tops.get(filename, 0) < end:
                return False
        return True

    def get_total_length(self):
        return self.total_length

    def _intervals(self, pos, amount):
        r = []
        stop = pos + amount
        p = bisect_right(self.begins, pos) - 1
        while p < len(self.ranges) and self.ranges[p][0] < stop:
            begin, end, filename = self.ranges[p]
            r.append((filename, max(pos, begin) - begin, min(end, stop) - begin))
            p += 1
        return r

    def _get_file_handle(self, filename, for_write):
        handlebuffer = self.filepool.handlebuffer
        if filename in self.handles:
            if for_write and filename not in self.whandles:
                self.handles[filename].close()
                self.handles[filename] = file(filename, 'rb+', 0)
                self.whandles[filename] = None
            if handlebuffer is not None and handlebuffer[-1] != filename:
                handlebuffer.remove(filename)
                handlebuffer.append(filename)
        else:
            if for_write:
                self.handles[filename] = file(filename, 'rb+', 0)
                self.whandles[filename] = None
            else:
                self.handles[filename] = file(filename, 'rb', 0)
            if handlebuffer is not None:
                if len(handlebuffer) >= self.filepool.max_files_open:
                    oldfile = handlebuffer.pop(0)
                    if oldfile in self.whandles:   # .pop() in python 2.3
                        del self.whandles[oldfile]
                    self.handles[oldfile].close()
                    del self.handles[oldfile]
                handlebuffer.append(filename)
        return self.handles[filename]

    def read(self, pos, amount):
        r = []
        for filename, pos, end in self._intervals(pos, amount):
            h = self._get_file_handle(filename, False)
            h.seek(pos)
            r.append(h.read(end - pos))
        r = ''.join(r)
        if len(r) != amount:
            raise BTFailure('Short read - something truncated files?')
        return r

    def write(self, pos, s):
        # might raise an IOError
        total = 0
        for filename, begin, end in self._intervals(pos, len(s)):
            h = self._get_file_handle(filename, True)
            h.seek(begin)
            h.write(s[total: total + end - begin])
            total += end - begin

    def close(self):
        error = None
        for filename in self.handles.keys():
            if filename in self.myfiles:
                try:
                    self.handles[filename].close()
                except Exception, e:
                    error = e
                del self.handles[filename]
                if filename in self.whandles:
                    del self.whandles[filename]
        handlebuffer = self.filepool.handlebuffer
        if handlebuffer is not None:
            handlebuffer = [f for f in handlebuffer if f not in self.myfiles]
            self.filepool.handlebuffer = handlebuffer
        if error is not None:
            raise error

    def write_fastresume(self, resumefile, amount_done):
        resumefile.write('BitTorrent resume state file, version 1\n')
        resumefile.write(str(amount_done) + '\n')
        for _, _, filename in self.ranges:
            resumefile.write(str(os.path.getsize(filename)) + ' ' +
                             str(os.path.getmtime(filename)) + '\n')

    def check_fastresume(self, resumefile, return_filelist=False,
                         piece_size=None, numpieces=None, allfiles=None):
        filenames = [name for _, _, name in self.ranges]
        if resumefile is not None:
            version = resumefile.readline()
            if version != 'BitTorrent resume state file, version 1\n':
                raise BTFailure('Unsupported fastresume file format, '
                      'maybe from another client version')
            amount_done = int(resumefile.readline())
        else:
            amount_done = size = mtime = 0
        for filename in filenames:
            if resumefile is not None:
                line = resumefile.readline()
                size, mtime = line.split()[:2] # allow adding extra fields
                size = int(size)
                mtime = int(mtime)
            if os.path.exists(filename):
                fsize = os.path.getsize(filename)
            else:
                fsize = 0
            if fsize > 0 and mtime != os.path.getmtime(filename):
                raise BTFailure("Fastresume info doesn't match file "
                                "modification time")
            if size != fsize:
                raise BTFailure("Fastresume data doesn't match actual "
                                "filesize")
        if not return_filelist:
            return amount_done
        if resumefile is None:
            return None
        if numpieces < 32768:
            typecode = 'h'
        else:
            typecode = 'l'
        try:
            r = array(typecode)
            r.fromfile(resumefile, numpieces)
        except Exception, e:
            raise BTFailure("Couldn't read fastresume data: " + str(e))
        for i in range(numpieces):
            if r[i] >= 0:
                # last piece goes "past the end", doesn't matter
                self.downloaded(r[i] * piece_size, piece_size)
            if r[i] != -2:
                self.allocated(i * piece_size, piece_size)
        undl = self.undownloaded
        unal = self.unallocated
        return amount_done, [undl[x] for x in allfiles], \
               [not unal[x] for x in allfiles]

    def allocated(self, pos, length):
        for filename, begin, end in self._intervals(pos, length):
            self.unallocated[filename] -= end - begin

    def downloaded(self, pos, length):
        for filename, begin, end in self._intervals(pos, length):
            self.undownloaded[filename] -= end - begin
