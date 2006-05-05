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
import views
import subscription

_commandLineArgs = []

def addVideo(path):
    manualFeed = app.getSingletonDDBObject(views.manualFeed)
    manualFeed.beginRead()
    try:
        for i in manualFeed.items:
            if i.getFilename() == path:
                print "Not adding duplicate video: %s" % path
                return
    finally:
        manualFeed.endRead()
    fileItem = item.FileItem(manualFeed, path)
    manualFeed.actualFeed.addItem(fileItem)

def getTorrentInfoHash(path):
    f = open(path, 'rb')
    try:
        data = f.read()
        metainfo = bdecode(data)
        infohash = sha(bencode(metainfo['info'])).digest()
        return infohash
    finally:
        f.close()

def addTorrent(path, torrentInfohash):
    manualFeed = app.getSingletonDDBObject(views.manualFeed)
    manualFeed.beginRead()
    try:
        for i in manualFeed.items:
            i.beginRead()
            try:
                for d in i.downloaders:
                    if d.status.get('infohash') == torrentInfohash:
                        print ("Not downloading %s, it's already a "
                                "download for %s" % (path, i))
                        if i.getState() in ('paused', 'stopped'):
                            i.download()
                        return
            finally:
                i.endRead()
    finally:
        manualFeed.endRead()
    newItem = item.Item(manualFeed, item.getEntryForFile(path))
    manualFeed.actualFeed.addItem(newItem)
    newItem.download()

def addFeed(path):
    feed.addFeedFromFile(path)

def addSubscriptions(path):
    handler = app.GUIActionHandler()
    urls = subscription.parseFile(path)
    if urls is not None:
        lastURL = urls.pop()
        for url in urls:
            handler.addFeed(url, selected=None)
        handler.addFeed(lastURL)


def setCommandLineArgs(args):
    global _commandLineArgs
    _commandLineArgs = args

def parseCommandLineArgs(args=None):
    if args is None:
        args = _commandLineArgs

    addedVideos = False
    addedTorrents = False

    for arg in args:
        print "parsing ", arg
        if os.path.exists(arg):
            ext = os.path.splitext(arg)[1].lower()
            if ext in ('.torrent', '.tor'):
                print "trying torrent"
                try:
                    torrentInfohash = getTorrentInfoHash(arg)
                except ValueError:
                    print "WARNING: %s doesn't seem to be a torrent file"
                    continue
                addTorrent(arg, torrentInfohash)
                addedTorrents = True
            elif ext in ('.rss', '.rdf', '.atom'):
                addFeed(arg)
            elif ext == '.democracy':
                addSubscriptions(arg)
            else:
                addVideo(arg)
                addedVideos = True
        else:
            print "WARNING: %s doesn't exist" % arg

    if addedVideos:
        app.controller.selectTabByTemplateBase('librarytab')
    elif addedTorrents:
        app.controller.selectTabByTemplateBase('downloadtab')


