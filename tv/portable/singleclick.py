"""Helper functions for implement single click playback and single click
torrent downloading.

Frontends should call setCommandLineArgs() passing it a list of arguments that
the users gives.  This should just be suspected torrents/videos, not things
like '--help', '--version', etc.

Frontends should trap when a user opens a torrent/video with democracy while
democracy is already running.  They should arange for addVideo or addTorrent
to be called in the existing democracy process.
"""

import os
from sha import sha

from BitTornado.bencode import bdecode, bencode

import app
import item
import feed

ADDED_NOTHING = 0
ADDED_TORRENTS = 1
ADDED_VIDEOS = 2
ADDED_BOTH = 3

_commandLineArgs = []

def initialize():
    try:
        app.getSingletonDDBObject('manualFeed')
    except LookupError:
        feed.Feed("dtv:manualFeed", useThread=False,
                initiallyAutoDownloadable=False)

def addVideo(path):
    manualFeed = app.getSingletonDDBObject('manualFeed')
    fileItem = item.FileItem(manualFeed, path)
    manualFeed.actualFeed.addItem(fileItem)

def getTorrentInfoHash(path):
    f = open(path)
    try:
        data = f.read()
        metainfo = bdecode(data)
        infohash = sha(bencode(metainfo['info'])).digest()
        return infohash
    finally:
        f.close()

def addTorrent(path, torrentInfohash):
    manualFeed = app.getSingletonDDBObject('manualFeed')
    manualFeed.beginRead()
    try:
        for i in manualFeed.items:
            i.beginRead()
            try:
                infohash = i.downloaders[0].status.get('infohash')
                if infohash == torrentInfohash:
                    print ("Not downloading %s, it's already a "
                            "download for %s" % (path, i))
                    return
            finally:
                i.endRead()
    finally:
        manualFeed.endRead()
    newItem = item.Item(manualFeed, item.getEntryForFile(path))
    manualFeed.actualFeed.addItem(newItem)
    newItem.download()

def addFile(path):
    if path.endswith('.torrent'):
        try:
            torrentInfohash = getTorrentInfoHash(path)
        except ValueError:
            print "WARNING: %s doesn't seem to be a torrent file"
            return ADDED_NOTHING
        addTorrent(path, torrentInfohash)
        return ADDED_TORRENTS
    else:
        addVideo(path)
        return ADDED_VIDEOS

def setCommandLineArgs(args):
    global _commandLineArgs
    _commandLineArgs = args

def parseCommandLineArgs():
    """Will return ADDED_VIDEOS, ADDED_TORRENTS, ADDED_BOTH, or ADDED_NOTHING
    depending on what it finds.  
    """

    global _commandLineArgs

    addFileResults = set()

    for arg in _commandLineArgs:
        if os.path.exists(arg):
            addFileResults.add(addFile(arg))

    if ADDED_VIDEOS in addFileResults and ADDED_TORRENTS in addFileResults:
        return ADDED_BOTH
    elif ADDED_VIDEOS in addFileResults:
        return ADDED_VIDEOS
    elif ADDED_TORRENTS in addFileResults:
        return ADDED_TORRENTS
    else:
        return ADDED_NOTHING
