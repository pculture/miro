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
commandLineVideoIds = None
commandLineView = None 

def addVideo(path):
    views.items.beginRead()
    try:
        for i in views.items:
            # FIXME: we should handle case-insensitivity on OS X and 8.3
            # pathnames on windows.  This probably means adding a
            # platformutils.samefile function, which I don't want to do for
            # the 0.8.4 release.  (BTW: This will be supor easy on linux and
            # OS X: from os.path import samefile).
            if i.getFilename() == os.path.abspath(path):
                print "Not adding duplicate video: %s" % path
                commandLineVideoIds.add(i.getID())
                return
    finally:
        views.items.endRead()
    manualFeed = app.getSingletonDDBObject(views.manualFeed)
    fileItem = item.FileItem(manualFeed, path)
    manualFeed.actualFeed.addItem(fileItem)
    commandLineVideoIds.add(fileItem.getID())

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

def resetCommandLineView():
    global commandLineView, commandLineVideoIds
    if commandLineView is not None:
        commandLineView.unlink()
        commandLineView = None
    commandLineVideoIds = set()

def playCommandLineView():
    global commandLineView, commandLineVideoIds
    if len(commandLineVideoIds) == 0:
        return
    def inCommandLineVideoIDs(item):
        return item.getID() in commandLineVideoIds
    commandLineView = views.fileItems.filter(inCommandLineVideoIDs)
    firstItemId = commandLineVideoIds.__iter__().next()
    app.controller.playbackController.configure(commandLineView, firstItemId)
    app.controller.playbackController.enterPlayback()

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

    resetCommandLineView()

    addedVideos = False
    addedTorrents = False

    for arg in args:
        if os.path.exists(arg):
            ext = os.path.splitext(arg)[1].lower()
            if ext in ('.torrent', '.tor'):
                try:
                    torrentInfohash = getTorrentInfoHash(arg)
                except ValueError:
                    print "WARNING: %s doesn't seem to be a torrent file" % arg
                    continue
                addTorrent(arg, torrentInfohash)
                addedTorrents = True
            elif ext in ('.rss', '.rdf', '.atom', '.ato'):
                addFeed(arg)
            elif ext in ('.democracy', '.dem'):
                addSubscriptions(arg)
            else:
                addVideo(arg)
                addedVideos = True
        else:
            print "WARNING: %s doesn't exist" % arg

    if addedVideos:
        app.controller.selectTabByTemplateBase('librarytab')
        playCommandLineView()
    elif addedTorrents:
        app.controller.selectTabByTemplateBase('downloadtab')

def openFile(path):
    parseCommandLineArgs([path])
