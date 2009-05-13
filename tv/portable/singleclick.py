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
"""

from miro.gtcache import gettext as _
import logging
import urlparse
import os.path
from feedparser import FeedParserDict

from miro import dialogs
from miro import item
from miro import feed
from miro import filetypes
from miro import flashscraper
from miro import folder
from miro import httpclient
from miro import config
from miro import prefs
from miro import messages

def check_url_exists(url):
    manualFeed = feed.Feed.get_manual_feed()
    for i in manualFeed.items:
        if i.get_url() == url:
            title = _("Download already exists")
            text1 = _("That URL is already an external download.")
            downloadState = None
            if i.downloader is not None:
                downloadState = i.downloader.get_state()
            if downloadState in ('paused', 'stopped'):
                i.download()
                text2 = _("%(appname)s will begin downloading it now.",
                          {"appname": config.get(prefs.SHORT_APP_NAME)})
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

def _build_entry(url, contentType, additional=None):
    entry = {'enclosures':[{'url' : url, 'type' : unicode(contentType)}]}

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

    if 'title' not in entry:
        _, _, urlpath, _, _, _ = urlparse.urlparse(url)
        entry['title'] = os.path.basename(urlpath)

    return FeedParserDict(entry)

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
            download_video(_build_entry(url, 'video/x-unknown'))
        elif dialog.choice == dialogs.BUTTON_OPEN_IN_EXTERNAL_BROWSER:
            messages.OpenInExternalBrowser(url).send_to_frontend()
    dialog.run(callback)

def add_download(url, handle_unknown_callback=None, metadata=None):
    """Given a url, this tries to figure out what it is (video, audio, torrent, rss feed,
    flash file that Miro can scrape) and handles it accordingly.

    If it can't figure out what it is, then it calls handle_unknown_callback with the url of
    the thing it can't identify and thus doesn't know what to do with.

    If ``handle_unknown_callback`` is None, then it uses the default handler which is
    ``download_unknown_mime_type``.
    """
    if handle_unknown_callback == None:
        handle_unknown_callback = download_unknown_mime_type

    if url.startswith('feed:'):
        # hack so feed: acts as http:
        url = "http:" + url[5:]
    elif url.startswith('feeds:'):
        # hack so feeds: acts as https:
        url = "https:" + url[6:]

    if check_url_exists(url):
        return

    def errback(error):
        title = _("Download Error")
        text = _(
            "%(appname)s is not able to download a file at this URL:\n"
            "\n"
            "URL: %(url)s",
            {"url": url, "appname": config.get(prefs.SHORT_APP_NAME)}
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

    def callback_flash(old_url):
        def _callback(url, contentType="video/flv"):
            if url:
                entry = _build_entry(url, contentType, additional=metadata)
                download_video(entry)
                return

            if url == None:
                handle_unknown_callback(old_url)
            else:
                handle_unknown_callback(url)

        flashscraper.try_scraping_url(url, _callback)

    def callback(headers):
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

        entry = _build_entry(url, contentType)

        if filetypes.is_video_enclosure(entry['enclosures'][0]):
            download_video(entry)
        else:
            handle_unknown_callback(url)

    httpclient.grabHeaders(url, callback, errback)

def download_video(entry):
    manualFeed = feed.Feed.get_manual_feed()
    newItem = item.Item(entry, feed_id=manualFeed.getID())
    newItem.download()

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
                f.set_folder(newFolder)
            lastFeed = f
