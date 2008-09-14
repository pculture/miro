# Miro - an RSS based video player application
# Copyright (C) 2005-2008 Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

"""Helper functions for implement single click playback and single click
torrent downloading.

Frontends should call setCommandLineArgs() passing it a list of arguments that
the users gives.  This should just be suspected torrents/videos, not things
like '--help', '--version', etc.

Frontends should trap when a user opens a torrent/video with Miro while
Miro is already running.  They should arrange for addVideo or addTorrent
to be called in the existing Miro process.
"""

from miro.gtcache import gettext as _
from miro.gtcache import ngettext
import os
import logging

from miro.util import get_torrent_info_hash
from miro import dialogs
from miro import download_utils
from miro import item
from miro import feed
from miro import filetypes
from miro import folder
from miro import guide
from miro import httpclient
from miro import views
from miro import signals
from miro import subscription
from miro import util
from miro import config
from miro import prefs
from miro.plat.utils import samefile, filenameToUnicode, unicodeToFilename

_commandLineArgs = []
commandLineVideoIds = None
commandLineView = None 

def getManualFeed():
    manualFeed = util.getSingletonDDBObject(views.manualFeed)
    manualFeed.confirmDBThread()
    return manualFeed

def addVideo(path, single=False):
    path = os.path.abspath(path)
    views.items.confirmDBThread()
    for i in views.items:
        itemFilename = i.getFilename()
        if (itemFilename != '' and 
                os.path.exists(itemFilename) and
                samefile(itemFilename, path)):
            print "Not adding duplicate video: %s" % path.decode('ascii', 'ignore')
            commandLineVideoIds.add(i.getID())
            return
    if single:
        correctFeed = util.getSingletonDDBObject(views.singleFeed)
        items = [i for i in correctFeed.items]
        for i in items:
            i.expire()
    else:
        correctFeed = getManualFeed()
    fileItem = item.FileItem(path, feed_id=correctFeed.getID())
    fileItem.markItemSeen()
    commandLineVideoIds.add(fileItem.getID())

def checkURLExists(url):
    manualFeed = getManualFeed()
    for i in manualFeed.items:
        if i.getURL() == url:
            title = _("Download already exists")
            text1 = _("That URL is already an external download.")
            downloadState = None
            if i.downloader is not None:
                downloadState = i.downloader.getState()
            if downloadState in ('paused', 'stopped'):
                i.download()
                text2 = _("Miro will begin downloading it now.")
            elif downloadState == 'downloading':
                text2 = _("It is downloading now.")
            else:
                text2 = _("It has already been downloaded.")
            dialogs.MessageBoxDialog(title, "%s  %s" % (text1, text2)).run()
            return True
    existingFeed = feed.get_feed_by_url(url)
    if existingFeed is not None:
        existingFeed.blink()
        return True
    return False

def __buildEntry(url, contentType, additional):
    entry = item.getEntryForURL(url, contentType)
    if additional is not None:
        for key in 'title', 'link', 'feed':
            if key in additional:
                entry[key] = additional[key]
        if 'description' in additional:
            entry['description'] = entry['summary'] = additional[
                'description']
        if 'thumbnail' in additional:
            entry['thumbnail'] = {'href': additional['thumbnail']}
        if 'length' in additional:
            entry['enclosures'][0]['length'] = additional['length']
        if 'type' in additional:
            entry['enclosures'][0]['type'] = additional['type']

    return entry

def addDownload(url, additional=None):
    if checkURLExists(url):
        return

    def errback(error):
        title = _("Download Error")
        text = _(
            "Miro is not able to download a file at this URL:\n"
            "\n"
            "URL: %(url)s",
            {"url": url}
        )
        logging.info("can't download '%s'", url)
        dialogs.MessageBoxDialog(title, text).run()

    def callback_peek(data):
        """Takes the data returned from a GET and peeks at it to see if it's a
        feed despite the fact that it has the wrong content-type.
        """
        if data["body"]:
            if filetypes.isMaybeRSS(data["body"]):
                # FIXME - this is silly since we just did a GET and we do 
                # another one in addFeeds
                logging.info("%s is a feed--adding it." % url)
                addFeeds([url])
                return
        
        downloadUnknownMimeType(url)

    def callback(headers):
        """We need to figure out if the URL is a external video link, or a link to
        a channel.
        """
        if checkURLExists(url):
            return

        contentType = headers.get("content-type")
        if contentType and filetypes.isFeedContentType(contentType):
            addFeeds([url])
            return

        if contentType and filetypes.isMaybeFeedContentType(contentType):
            logging.info("%s content type is %s.  going to peek to see if it's a feed...." % (url, contentType))
            httpclient.grabURL(url, callback_peek, errback)
            return

        entry = __buildEntry(url, contentType, additional)

        if filetypes.isVideoEnclosure(entry['enclosures'][0]):
            downloadVideo(entry)
        else:
            downloadUnknownMimeType(url)

    httpclient.grabHeaders(url, callback, errback)

def downloadUnknownMimeType(url):
    title = _('File Download')
    text = _('This file at %(url)s does not appear to be audio, video, or an RSS feed.',
             {"url": url})
    dialog = dialogs.ChoiceDialog(title, text, 
            dialogs.BUTTON_DOWNLOAD_ANYWAY, dialogs.BUTTON_CANCEL)
    def callback(dialog):
        if checkURLExists(url):
            return
        if dialog.choice == dialogs.BUTTON_DOWNLOAD_ANYWAY:
            # Fake a viedo mime type, so we will download the item.
            downloadVideo(item.getEntryForURL(url, 'video/x-unknown'))
    dialog.run(callback)

def downloadVideo(entry):
    manualFeed = getManualFeed()
    newItem = item.Item(entry, feed_id=manualFeed.getID())
    newItem.download()

def addTorrent(path, torrentInfohash):
    manualFeed = getManualFeed()
    for i in manualFeed.items:
        if (i.downloader is not None and
                i.downloader.status.get('infohash') == torrentInfohash):
            logging.info("not downloading %s, it's already a download for %s", path, i)
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

def inCommandLineVideoIDs(item_):
    return item_.getID() in commandLineVideoIds

def playCommandLineView():
    global commandLineView
    if len(commandLineVideoIds) == 0:
        return
    commandLineView = views.items.filter(inCommandLineVideoIDs)
    signals.system.videosAdded(commandLineView)

def addFeed(path):
    feed.add_feed_from_file(path)

def addSubscriptions(type_, urls):
    if urls is not None:
        if type_ == 'rss':
            if len(urls) > 1:
                askForMultipleFeeds(urls)
            else:
                addFeeds(urls)
        elif type_ == 'download':
            [addDownload(url, additional) for url, additional in urls]
        elif type_ == 'guide':
            for url in urls:
                if guide.getGuideByURL(url) is None:
                    guide.ChannelGuide(url, [u'*'])
                    
def filterExistingFeedURLs(urls):
    return [u for u in urls if feed.get_feed_by_url(u) is None]

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

def askForMultipleFeeds(urls):
    title = _("Subscribing to multiple channels") 
    description = ngettext("Create channel?",
                           "Create %(count)d channels?",
                           len(urls),
                           {"count": len(urls)})
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
    title = ngettext("Adding channel to a new folder"
                     "Adding %(count)d channels to a new folder",
                     newURLCount,
                     {"count": newURLCount})
    description = _("Enter a name for the new channel folder")
    if existingURLCount > 0:
        description += "\n\n"
        description += ngettext(
            "NOTE: You are already subscribed to one of these channels.  These "
            "channels will stay where they currently are.",
            "NOTE: You are already subscribed to %(count)d of these channels.  These "
            "channels will stay where they currently are.",
            existingURLCount,
            {"count": existingURLCount}
        )

    def callback(d):
        if d.choice == dialogs.BUTTON_CREATE:
            addFeeds(urls, d.value)
    dialogs.TextEntryDialog(title, description, dialogs.BUTTON_CREATE,
            dialogs.BUTTON_CANCEL).run(callback)

def complainAboutSubscriptionURL(messageText):
    title = _("Subscription error")
    dialogs.MessageBoxDialog(title, messageText).run()

def addSubscriptionURL(prefix, expectedContentType, url):
    realURL = url[len(prefix):]
    def callback(info):
        if info.get('content-type') == expectedContentType:
            type_, urls = subscription.parseContent(info['body'])
            if urls is None:
                text = _(
                    "This %(appname)s channel file has an invalid format: "
                    "%(url)s.  Please notify the publisher of this file.",
                    {"appname": config.get(prefs.SHORT_APP_NAME), "url": realURL}
                )
                complainAboutSubscriptionURL(text)
            else:
                addSubscriptions(type_, urls)
        else:
            text = _(
                "This %(appname)s channel file has the wrong content type: "
                "%(url)s. Please notify the publisher of this file.",
                {"appname": config.get(prefs.SHORT_APP_NAME), "url": realURL}
            )
            complainAboutSubscriptionURL(text)

    def errback(error):
        text = _(
            "Could not download the %(appname)s channel file: %(url)s",
            {"appname": config.get(prefs.SHORT_APP_NAME), "url": realURL}
        )
        complainAboutSubscriptionURL(text)

    httpclient.grabURL(realURL, callback, errback)

def set_command_line_args(args):
    _commandLineArgs.extend(args)

def downloadURL(url):
    if url.startswith('http:') or url.startswith('https:'):
        addDownload(url)
    elif url.startswith('feed:'):
        # hack so feed: acts as http:
        url = "http:" + url[len("feed:"):]
        addDownload(url)
    elif url.startswith('feeds:'):
        # hack so feeds: acts as https:
        url = "https:" + url[len("feeds:"):]
        addDownload(url)
    else:
        parse_command_line_args([unicodeToFilename(url)])

def parse_command_line_args(args=None):
    if args is None:
        global _commandLineArgs
        args = _commandLineArgs
        _commandLineArgs = []

    resetCommandLineView()

    addedVideos = False
    addedDownloads = False

    for arg in args:
        if arg.startswith('file://'):
            arg = download_utils.getFileURLPath(arg)
        if arg.startswith('miro:'):
            addSubscriptionURL('miro:', 'application/x-miro', arg)
        elif arg.startswith('democracy:'):
            addSubscriptionURL('democracy:', 'application/x-democracy', arg)
        elif arg.startswith('http:') or arg.startswith('https:') or arg.startswith('feed:') or arg.startswith('feeds:'):
            downloadURL(filenameToUnicode(arg))
        elif os.path.exists(arg):
            ext = os.path.splitext(arg)[1].lower()
            if ext in ('.torrent', '.tor'):
                try:
                    torrentInfohash = get_torrent_info_hash(arg)
                except ValueError:
                    title = _("Invalid Torrent")
                    msg = _(
                        "The torrent file %(filename)s appears to be corrupt and cannot be opened. [OK]",
                        {"filename": os.path.basename(arg)}
                    )
                    dialogs.MessageBoxDialog(title, msg).run()
                    continue
                addTorrent(arg, torrentInfohash)
                addedDownloads = True
            elif ext in ('.rss', '.rdf', '.atom', '.ato'):
                addFeed(arg)
            elif ext in ('.miro', '.democracy', '.dem', '.opml'):
                ret = subscription.parseFile(arg)
                if ret is not None:
                    addSubscriptions(ret[0], ret[1])
            else:
                addVideo(arg, len(args) == 1)
                addedVideos = True
        else:
            logging.warning("parse_command_line_args: %s doesn't exist", arg)

def openFile(path):
    parse_command_line_args([path])
