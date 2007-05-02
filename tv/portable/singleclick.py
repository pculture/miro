"""Helper functions for implement single click playback and single click
torrent downloading.

Frontends should call setCommandLineArgs() passing it a list of arguments that
the users gives.  This should just be suspected torrents/videos, not things
like '--help', '--version', etc.

Frontends should trap when a user opens a torrent/video with democracy while
democracy is already running.  They should arange for addVideo or addTorrent
to be called in the existing democracy process.
"""

from gtcache import gettext as _
import os

from util import getTorrentInfoHash
import app
import dialogs
import download_utils
import item
import feed
import folder
import httpclient
import views
import platformutils
import subscription
import util
import config
import prefs
from string import Template

_commandLineArgs = []
commandLineVideoIds = None
commandLineView = None 

def addVideo(path):
    path = os.path.abspath(path)
    views.items.confirmDBThread()
    for i in views.items:
        itemFilename = i.getFilename()
        if (itemFilename != '' and 
                os.path.exists(itemFilename) and
                platformutils.samefile(itemFilename, path)):
            print "Not adding duplicate video: %s" % path.decode('ascii', 'ignore')
            commandLineVideoIds.add(i.getID())
            return
    manualFeed = util.getSingletonDDBObject(views.manualFeed)
    fileItem = item.FileItem(path, feed_id=manualFeed.getID())
    fileItem.markItemSeen()
    commandLineVideoIds.add(fileItem.getID())

def addTorrent(path, torrentInfohash):
    manualFeed = util.getSingletonDDBObject(views.manualFeed)
    manualFeed.confirmDBThread()
    for i in manualFeed.items:
        if (i.downloader is not None and
                i.downloader.status.get('infohash') == torrentInfohash):
            print ("Not downloading %s, it's already a "
                    "download for %s" % (path, i))
            if i.downloader.getState() in ('paused', 'stopped'):
                i.download()
            return
    newItem = item.Item(item.getEntryForFile(path), feed_id=manualFeed.getID())
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
    urls = subscription.parseFile(path)
    if urls is not None:
        if len(urls) > 1:
            askForMultipleFeeds(urls)
        else:
            addFeeds(urls)

def filterExistingFeedURLs(urls):
    return [u for u in urls if feed.getFeedByURL(u) is None]

def addFeeds(urls, newFolderName=None):
    if len(urls) > 0:
        lastFeed = None
        if newFolderName is not None:
            newFolder = folder.ChannelFolder(newFolderName)
        for url in filterExistingFeedURLs(urls):
            f = feed.Feed(url)
            if newFolderName is not None:
                f.setFolder(newFolder)
            lastFeed = f
        if newFolderName is None:
            if lastFeed:
                for url in urls:
                    f = feed.getFeedByURL(url)
                    if f is lastFeed:
                        app.controller.selection.selectTabByObject(f)
                    else:
                        f.blink()
            else:
                for i in xrange (len(urls) - 1):
                    feed.getFeedByURL(urls[i]).blink()
                f = feed.getFeedByURL(urls[-1])
                app.controller.selection.selectTabByObject(f)
        else:
            app.controller.selection.selectTabByObject(newFolder)

def askForMultipleFeeds(urls):
    title = _("Subscribing to multiple channels") 
    description = _("Create %d channels?") % len(urls)
    d = dialogs.ThreeChoiceDialog(title, description, dialogs.BUTTON_ADD,
            dialogs.BUTTON_ADD_INTO_NEW_FOLDER, dialogs.BUTTON_CANCEL)
    def callback(d):
        if d.choice == dialogs.BUTTON_ADD:
            addFeeds(urls)
        elif d.choice == dialogs.BUTTON_ADD_INTO_NEW_FOLDER:
            askForNewFolderName(urls)
    d.run(callback)

def askForNewFolderName(urls):
    newURLCount = len(filterExistingFeedURLs(urls))
    existingURLCount = len(urls) - newURLCount
    title = _("Adding %d channels to a new folder") % newURLCount
    description = _("Enter a name for the new channel folder")
    if existingURLCount > 0:
        description += "\n\n"
        description += _("""\
NOTE: You are already subscribed to %d of these channels.  These channels \
will stay where they currently are.""" % existingURLCount)

    def callback(d):
        if d.choice == dialogs.BUTTON_CREATE:
            addFeeds(urls, d.value)
    dialogs.TextEntryDialog(title, description, dialogs.BUTTON_CREATE,
            dialogs.BUTTON_CANCEL).run(callback)

def complainAboutDemocracyURL(messageText):
    title = _("Subscription error")
    dialogs.MessageBoxDialog(title, messageText).run()

def addDemocracyURL(url):
    realURL = url[len('democracy:'):]
    def callback(info):
        if info.get('content-type') == 'application/x-democracy':
            urls = subscription.parseContent(info['body'])
            if urls is None:
                complainAboutDemocracyURL(
                    Template(_("This $shortAppName channel file has an invalid format: $url. Please notify the publisher of this file.")).substitute(url=realURL,shortAppName=config.get(prefs.SHORT_APP_NAME)))
            else:
                if len(urls) > 1:
                    askForMultipleFeeds(urls)
                else:
                    addFeeds(urls)
        else:
            complainAboutDemocracyURL(
                Template(_("This $shortAppName channel file has the wrong content type: $url. Please notify the publisher of this file.")).substitute(
                url=realURL,shortAppName=config.get(prefs.SHORT_APP_NAME)))
    def errback(error):
        complainAboutDemocracyURL(
                Template(_("Could not download the $shortAppName channel file: $url.")).substitute(url=realURL,shortAppName=config.get(prefs.SHORT_APP_NAME)))
    httpclient.grabURL(realURL, callback, errback)

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
        if arg.startswith('democracy:'):
            addDemocracyURL(arg)
        elif os.path.exists(arg):
            ext = os.path.splitext(arg)[1].lower()
            if ext in ('.torrent', '.tor'):
                try:
                    torrentInfohash = getTorrentInfoHash(arg)
                except ValueError:
                    title = _("Invalid Torrent")
                    msg = _("The torrent file %s appears to be corrupt and "
                            "cannot be opened. [OK]") % os.path.basename(arg)
                    dialogs.MessageBoxDialog(title, msg).run()
                    continue
                addTorrent(arg, torrentInfohash)
                addedTorrents = True
            elif ext in ('.rss', '.rdf', '.atom', '.ato'):
                addFeed(arg)
            elif ext in ('.democracy', '.dem', '.opml'):
                addSubscriptions(arg)
            else:
                addVideo(arg)
                addedVideos = True
        else:
            print "WARNING: %s doesn't exist" % arg

    if addedVideos:
        app.controller.selection.selectTabByTemplateBase('librarytab', False)
        playCommandLineView()
    elif addedTorrents:
        app.controller.selection.selectTabByTemplateBase('downloadtab')

def openFile(path):
    parseCommandLineArgs([path])
