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

from util import getTorrentInfoHash
import app
import item
import feed
import views
import platformutils
import subscription

_commandLineArgs = []
commandLineVideoIds = None
commandLineView = None 

def addVideo(path):
    path = os.path.abspath(path)
    views.items.confirmDBThread()
    for i in views.items:
        itemFilename = i.getFilename()
        if (itemFilename != '' and 
                platformutils.samefile(itemFilename, path)):
            print "Not adding duplicate video: %s" % path
            commandLineVideoIds.add(i.getID())
            return
    manualFeed = app.getSingletonDDBObject(views.manualFeed)
    fileItem = item.FileItem(manualFeed.getID(), path)
    commandLineVideoIds.add(fileItem.getID())

def addTorrent(path, torrentInfohash):
    manualFeed = app.getSingletonDDBObject(views.manualFeed)
    manualFeed.confirmDBThread()
    for i in manualFeed.items:
        if (i.downloader is not None and
                i.downloader.status.get('infohash') == torrentInfohash):
            print ("Not downloading %s, it's already a "
                    "download for %s" % (path, i))
            if i.downloader.getState() in ('paused', 'stopped'):
                i.download()
            return
    newItem = item.Item(manualFeed.getID(), item.getEntryForFile(path))
    newItem.download()

def resetCommandLineView():
    global commandLineView, commandLineVideoIds
    if commandLineView is not None:
        commandLineView.unlink()
        commandLineView = None
    commandLineVideoIds = set()

def inCommandLineVideoIDs(item):
    return item.getID() in commandLineVideoIds
def playCommandLineView():
    global commandLineView, commandLineVideoIds
    if len(commandLineVideoIds) == 0:
        return
    commandLineView = views.items.filter(inCommandLineVideoIDs)
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
