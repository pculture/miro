#!/usr/bin/env python

# Written by Henry 'Pi' James and Bram Cohen
# see LICENSE.txt for license information

from sys import argv
from BitTorrent.bencode import bencode, bdecode

if len(argv) < 3:
    print '%s http://new.uri:port/announce file1.torrent file2.torrent' % argv[0]
    print
    exit(2) # common exit code for syntax error

for f in argv[2:]:
    h = open(f, 'rb')
    metainfo = bdecode(h.read())
    h.close()
    if metainfo['announce'] != argv[1]:
        print 'old announce for %s: %s' % (f, metainfo['announce'])
        metainfo['announce'] = argv[1]
        h = open(f, 'wb')
        h.write(bencode(metainfo))
        h.close()
