#!/usr/bin/env python

# Written by Bram Cohen
# see LICENSE.txt for license information

import sys
assert sys.version >= '2', "Install Python 2.0 or greater"
from distutils.core import setup, Extension
import BitTorrent

setup(
    name = "BitTorrent",
    version = BitTorrent.version,
    author = "Bram Cohen",
    author_email = "<bram@bitconjurer.org>",
    url = "http://www.bitconjurer.org/BitTorrent/",
    license = "MIT",
    
    packages = ["BitTorrent"],

    scripts = ["btdownloadgui.py", "btdownloadheadless.py", "btdownloadlibrary.py", 
        "bttrack.py", "btmakemetafile.py", "btlaunchmany.py", "btcompletedir.py",
        "btdownloadcurses.py", "btcompletedirgui.py", "btlaunchmanycurses.py", 
        "btmakemetafile.py", "btreannounce.py", "btrename.py", "btshowmetainfo.py",
        "bttest.py"]
    )
