#!/usr/bin/env python

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

import os
import sys
from sha import sha
from time import time
from threading import Event

from BitTorrent.bencode import bencode
from BitTorrent.btformats import check_info
from BitTorrent.parseargs import parseargs, printHelp
from BitTorrent.obsoletepythonsupport import *
from BitTorrent import BTFailure

ignore = ['core', 'CVS', 'Thumbs.db']

noncharacter_translate = {}
for i in range(0xD800, 0xE000):
    noncharacter_translate[i] = None
for i in range(0xFDD0, 0xFDF0):
    noncharacter_translate[i] = None
for i in (0xFFFE, 0xFFFF):
    noncharacter_translate[i] = None

del i

def dummy(v):
    pass

def make_meta_files(url, files, flag=Event(), progressfunc=dummy,
                    filefunc=dummy, piece_len_pow2=None, target=None,
                    comment=None, filesystem_encoding=None):
    if len(files) > 1 and target:
        raise BTFailure("You can't specify the name of the .torrent file when "
                        "generating multiple torrents at once")

    if not filesystem_encoding:
        try:
            sys.getfilesystemencoding
        except AttributeError:
            pass
        else:
            filesystem_encoding = sys.getfilesystemencoding()
        if not filesystem_encoding:
            filesystem_encoding = 'ascii'
    try:
        'a1'.decode(filesystem_encoding)
    except:
        raise BTFailure('Filesystem encoding "'+filesystem_encoding+
                        '" is not supported in this version')
    files.sort()
    ext = '.torrent'

    togen = []
    for f in files:
        if not f.endswith(ext):
            togen.append(f)

    total = 0
    for f in togen:
        total += calcsize(f)

    subtotal = [0]
    def callback(x):
        subtotal[0] += x
        progressfunc(subtotal[0] / total)
    for f in togen:
        if flag.isSet():
            break
        t = os.path.split(f)
        if t[1] == '':
            f = t[0]
        filefunc(f)
        make_meta_file(f, url, flag=flag, progress=callback,
                       piece_len_exp=piece_len_pow2, target=target,
                       comment=comment, encoding=filesystem_encoding)

def make_meta_file(path, url, piece_len_exp, flag=Event(), progress=dummy,
                   comment=None, target=None, encoding='ascii'):
    piece_length = 2 ** piece_len_exp
    a, b = os.path.split(path)
    if not target:
        if b == '':
            f = a + '.torrent'
        else:
            f = os.path.join(a, b + '.torrent')
    else:
        f = target
    info = makeinfo(path, piece_length, flag, progress, encoding)
    if flag.isSet():
        return
    check_info(info)
    h = file(f, 'wb')
    data = {'info': info, 'announce': url.strip(),'creation date': int(time())}
    if comment:
        data['comment'] = comment
    h.write(bencode(data))
    h.close()

def calcsize(path):
    total = 0
    for s in subfiles(os.path.abspath(path)):
        total += os.path.getsize(s[1])
    return total

def makeinfo(path, piece_length, flag, progress, encoding):
    def to_utf8(name):
        try:
            u = name.decode(encoding)
        except Exception, e:
            raise BTFailure('Could not convert file/directory name "'+name+
                            '" to utf-8 ('+str(e)+'). Either the assumed '
                            'filesystem encoding "'+encoding+'" is wrong or '
                            'the filename contains illegal bytes.')
        if u.translate(noncharacter_translate) != u:
            raise BTFailure('File/directory name "'+name+'" contains reserved '
                            'unicode values that do not correspond to '
                            'characters.')
        return u.encode('utf-8')
    path = os.path.abspath(path)
    if os.path.isdir(path):
        subs = subfiles(path)
        subs.sort()
        pieces = []
        sh = sha()
        done = 0
        fs = []
        totalsize = 0.0
        totalhashed = 0
        for p, f in subs:
            totalsize += os.path.getsize(f)

        for p, f in subs:
            pos = 0
            size = os.path.getsize(f)
            p2 = [to_utf8(name) for name in p]
            fs.append({'length': size, 'path': p2})
            h = file(f, 'rb')
            while pos < size:
                a = min(size - pos, piece_length - done)
                sh.update(h.read(a))
                if flag.isSet():
                    return
                done += a
                pos += a
                totalhashed += a

                if done == piece_length:
                    pieces.append(sh.digest())
                    done = 0
                    sh = sha()
                progress(a)
            h.close()
        if done > 0:
            pieces.append(sh.digest())
        return {'pieces': ''.join(pieces),
            'piece length': piece_length, 'files': fs,
            'name': to_utf8(os.path.split(path)[1])}
    else:
        size = os.path.getsize(path)
        pieces = []
        p = 0
        h = file(path, 'rb')
        while p < size:
            x = h.read(min(piece_length, size - p))
            if flag.isSet():
                return
            pieces.append(sha(x).digest())
            p += piece_length
            if p > size:
                p = size
            progress(min(piece_length, size - p))
        h.close()
        return {'pieces': ''.join(pieces),
            'piece length': piece_length, 'length': size,
            'name': to_utf8(os.path.split(path)[1])}

def subfiles(d):
    r = []
    stack = [([], d)]
    while stack:
        p, n = stack.pop()
        if os.path.isdir(n):
            for s in os.listdir(n):
                if s not in ignore and not s.startswith('.'):
                    stack.append((p + [s], os.path.join(n, s)))
        else:
            r.append((p, n))
    return r
