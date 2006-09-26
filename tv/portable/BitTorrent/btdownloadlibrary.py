# Written by Bram Cohen
# see LICENSE.txt for license information

import BitTorrent.download
from threading import Event

def dummychoose(default, size, saveas, dir):
    return saveas

def dummydisplay(dict):
    pass

def dummyerror(message):
    pass

def download(url, file):
    ev = Event()
    def fin(ev = ev):
        ev.set()
    BitTorrent.download.download(['--url', url, '--saveas', file], 
        dummychoose, dummydisplay, fin, dummyerror, ev, 80)
