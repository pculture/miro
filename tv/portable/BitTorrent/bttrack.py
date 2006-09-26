#!/usr/bin/env python

# Written by Bram Cohen
# see LICENSE.txt for license information

from sys import argv
from BitTorrent.track import track

if __name__ == '__main__':
    track(argv[1:])
