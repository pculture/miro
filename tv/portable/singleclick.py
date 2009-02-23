# Miro - an RSS based video player application
# Copyright (C) 2005-2009 Participatory Culture Foundation
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
Miro is already running.  They should arrange for add_video or add_torrent
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
from miro import flashscraper
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
from miro import messages

_command_line_args = []
_command_line_videos = None
_command_line_view = None

def get_manual_feed():
    manual_feed = util.getSingletonDDBObject(views.manualFeed)
    manual_feed.confirmDBThread()
    return manual_feed

def add_video(path, single=False):
    path = os.path.abspath(path)
    views.items.confirmDBThread()
    for i in views.items:
        itemFilename = i.get_filename()
        if (itemFilename != '' and
                os.path.exists(itemFilename) and
                samefile(itemFilename, path)):
            logging.warn("Not adding duplicate video: %s" % path.decode('ascii', 'ignore'))
            _command_line_videos.add(i)
            return
    if single:
        correctFeed = util.getSingletonDDBObject(views.singleFeed)
        items = list(correctFeed.items)
        for i in items:
            i.expire()
    else:
        correctFeed = get_manual_feed()
    fileItem = item.FileItem(path, feed_id=correctFeed.getID())
    fileItem.markItemSeen()
    _command_line_videos.add(fileItem)

def check_url_exists(url):
    manualFeed = get_manual_feed()
    for i in manualFeed.items:
        if i.getURL() == url:
            title = _("Download already exists")
            text1 = _("That URL is already an external download.")
            downloadState = None
            if i.downloader is not None:
                downloadState = i.downloader.get_state()
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
        return True
    return False

def _build_entry(url, contentType, additional):
    entry = item.get_entry_for_url(url, contentType)
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

def download_unknown_mime_type(url):
    title = _('File Download')
    text = _('This file at %(url)s does not appear to be audio, video, or an RSS feed.',
             {"url": url})
    dialog = dialogs.ThreeChoiceDialog(title, text,
            dialogs.BUTTON_DOWNLOAD_ANYWAY, dialogs.BUTTON_OPEN_IN_EXTERNAL_BROWSER, dialogs.BUTTON_CANCEL)
    def callback(dialog):
        if check_url_exists(url):
            return
        if dialog.choice == dialogs.BUTTON_DOWNLOAD_ANYWAY:
            # Fake a video mime type, so we will download the item.
            download_video(item.get_entry_for_url(url, 'video/x-unknown'))
        elif dialog.choice == dialogs.BUTTON_OPEN_IN_EXTERNAL_BROWSER:
            messages.OpenInExternalBrowser(url).send_to_frontend()
    dialog.run(callback)

def add_download(url, additional=None, handle_unknown_callback=download_unknown_mime_type):
    """Given a url, this tries to figure out what it is (video, audio, torrent, rss feed,
    flash file that Miro can scrape) and handles it accordingly.

    If it can't figure out what it is, then it calls handle_unknown_callback with the url of
    the thing it can't identify and thus doesn't know what to do with.

    The additional parameter is a dict of metadata to toss in the entry Miro builds.
    """
    if check_url_exists(url):
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
            if filetypes.is_maybe_rss(data["body"]):
                # FIXME - this is silly since we just did a GET and we do
                # another one in add_feeds
                logging.info("%s is a feed--adding it." % url)
                add_feeds([url])
                return

        handle_unknown_callback(url)

    def callback_flash(old_url, additional=additional):
        def _callback(url, contentType="video/flv", additional=additional):
            if url:
                if additional == None:
                    additional = {"title": url}
                entry = _build_entry(url, contentType, additional)
                download_video(entry)
                return

            if url == None:
                handle_unknown_callback(old_url)
            else:
                handle_unknown_callback(url)

        flashscraper.try_scraping_url(url, _callback)

    def callback(headers, additional=additional):
        """We need to figure out if the URL is a external video link, or a link to
        a feed.
        """
        if check_url_exists(url):
            return

        contentType = headers.get("content-type")
        if contentType and filetypes.is_feed_content_type(contentType):
            add_feeds([url])
            return

        if contentType and flashscraper.is_maybe_flashscrapable(url):
            callback_flash(url)
            return

        if contentType and filetypes.is_maybe_feed_content_type(contentType):
            logging.info("%s content type is %s.  going to peek to see if it's a feed...." % (url, contentType))
            httpclient.grabURL(url, callback_peek, errback)
            return

        entry = _build_entry(url, contentType, additional)

        if filetypes.is_video_enclosure(entry['enclosures'][0]):
            download_video(entry)
        else:
            handle_unknown_callback(url)

    httpclient.grabHeaders(url, callback, errback)

def download_video(entry):
    manualFeed = get_manual_feed()
    newItem = item.Item(entry, feed_id=manualFeed.getID())
    newItem.download()

def download_video_url(url, additional=None):
    entry = _build_entry(url, None, additional)
    download_video(entry)

def add_torrent(path, torrentInfohash):
    manualFeed = get_manual_feed()
    for i in manualFeed.items:
        if (i.downloader is not None and
                i.downloader.status.get('infohash') == torrentInfohash):
            logging.info("not downloading %s, it's already a download for %s", path, i)
            if i.downloader.get_state() in ('paused', 'stopped'):
                i.download()
            return
    newItem = item.Item(item.get_entry_for_file(path), feed_id=manualFeed.getID())
    newItem.download()

def reset_command_line_view():
    global _command_line_view, _command_line_videos
    if _command_line_view is not None:
        _command_line_view.unlink()
        _command_line_view = None
    _command_line_videos = set()

def add_feed(path):
    feed.add_feed_from_file(path)

def add_subscriptions(type_, urls):
    if urls is not None:
        if type_ == 'rss':
            if len(urls) > 1:
                ask_for_multiple_feeds(urls)
            else:
                add_feeds(urls)
        elif type_ == 'download':
            [add_download(url, additional) for url, additional in urls]
        elif type_ in ('guide', 'site'):
            for url in urls:
                if guide.getGuideByURL(url) is None:
                    guide.ChannelGuide(url, [u'*'])

def filter_existing_feed_urls(urls):
    return [u for u in urls if feed.get_feed_by_url(u) is None]

def add_feeds(urls, newFolderName=None):
    if len(urls) > 0:
        lastFeed = None
        if newFolderName is not None:
            newFolder = folder.ChannelFolder(newFolderName)

        for url in filter_existing_feed_urls(urls):
            f = feed.Feed(url)
            if newFolderName is not None:
                f.setFolder(newFolder)
            lastFeed = f

def ask_for_multiple_feeds(urls):
    title = _("Subscribing to multiple feeds")
    description = ngettext("Create feed?",
                           "Create %(count)d feeds?",
                           len(urls),
                           {"count": len(urls)})
    d = dialogs.ThreeChoiceDialog(title, description, dialogs.BUTTON_ADD,
            dialogs.BUTTON_ADD_INTO_NEW_FOLDER, dialogs.BUTTON_CANCEL)
    def callback(d):
        if d.choice == dialogs.BUTTON_ADD:
            add_feeds(urls)
        elif d.choice == dialogs.BUTTON_ADD_INTO_NEW_FOLDER:
            ask_for_new_folder_name(urls)
    d.run(callback)

def ask_for_new_folder_name(urls):
    newURLCount = len(filter_existing_feed_urls(urls))
    existingURLCount = len(urls) - newURLCount
    title = ngettext("Adding feed to a new folder"
                     "Adding %(count)d feeds to a new folder",
                     newURLCount,
                     {"count": newURLCount})
    description = _("Enter a name for the new feed folder")
    if existingURLCount > 0:
        description += "\n\n"
        description += ngettext(
            "NOTE: You are already subscribed to one of these feeds.  These "
            "feeds will stay where they currently are.",
            "NOTE: You are already subscribed to %(count)d of these feeds.  These "
            "feeds will stay where they currently are.",
            existingURLCount,
            {"count": existingURLCount}
        )

    def callback(d):
        if d.choice == dialogs.BUTTON_CREATE:
            add_feeds(urls, d.value)
    dialogs.TextEntryDialog(title, description, dialogs.BUTTON_CREATE,
            dialogs.BUTTON_CANCEL).run(callback)

def complain_about_subscription_url(messageText):
    title = _("Subscription error")
    dialogs.MessageBoxDialog(title, messageText).run()

def add_subscription_url(prefix, expectedContentType, url):
    realURL = url[len(prefix):]
    def callback(info):
        if info.get('content-type') == expectedContentType:
            type_, urls = subscription.parse_content(info['body'])
            if urls is None:
                text = _(
                    "This %(appname)s feed file has an invalid format: "
                    "%(url)s.  Please notify the publisher of this file.",
                    {"appname": config.get(prefs.SHORT_APP_NAME), "url": realURL}
                )
                complain_about_subscription_url(text)
            else:
                add_subscriptions(type_, urls)
        else:
            text = _(
                "This %(appname)s feed file has the wrong content type: "
                "%(url)s. Please notify the publisher of this file.",
                {"appname": config.get(prefs.SHORT_APP_NAME), "url": realURL}
            )
            complain_about_subscription_url(text)

    def errback(error):
        text = _(
            "Could not download the %(appname)s feed file: %(url)s",
            {"appname": config.get(prefs.SHORT_APP_NAME), "url": realURL}
        )
        complain_about_subscription_url(text)

    httpclient.grabURL(realURL, callback, errback)

def set_command_line_args(args):
    _command_line_args.extend(args)

def download_url(url):
    if url.startswith('http:') or url.startswith('https:'):
        add_download(url)
    elif url.startswith('feed:'):
        # hack so feed: acts as http:
        url = "http:" + url[5:]
        add_download(url)
    elif url.startswith('feeds:'):
        # hack so feeds: acts as https:
        url = "https:" + url[6:]
        add_download(url)
    else:
        parse_command_line_args([unicodeToFilename(url)])

def parse_command_line_args(args=None):
    if args is None:
        global _command_line_args
        args = _command_line_args
        _command_line_args = []

    reset_command_line_view()

    added_videos = False
    added_downloads = False

    for arg in args:
        if arg.startswith('file://'):
            arg = download_utils.getFileURLPath(arg)
        if arg.startswith('miro:'):
            add_subscription_url('miro:', 'application/x-miro', arg)
        elif arg.startswith('democracy:'):
            add_subscription_url('democracy:', 'application/x-democracy', arg)
        elif arg.startswith('http:') or arg.startswith('https:') or arg.startswith('feed:') or arg.startswith('feeds:'):
            download_url(filenameToUnicode(arg))
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
                add_torrent(arg, torrentInfohash)
                added_downloads = True
            elif ext in ('.rss', '.rdf', '.atom', '.ato'):
                add_feed(arg)
            elif ext in ('.miro', '.democracy', '.dem', '.opml'):
                ret = subscription.parse_file(arg)
                if ret is not None:
                    add_subscriptions(ret[0], ret[1])
            else:
                add_video(arg, len(args) == 1)
                added_videos = True
        else:
            logging.warning("parse_command_line_args: %s doesn't exist", arg)

    if added_videos:
        item_infos = [messages.ItemInfo(i) for i in _command_line_videos]
        messages.PlayMovie(item_infos).send_to_frontend()

    if added_downloads:
        # FIXME - switch to downloads tab?
        pass
