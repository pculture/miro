# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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
import time
from miro.feedparser import FeedParserDict

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
    """Checks to see if there's an item with this url already
    downloaded.

    In the case of the item existing in the manual feed, this pops up
    a dialog box with the status of the item.

    :param url: the url to check

    :returns: True if there is already an item for that url downloaded
        and False otherwise.
    """
    manual_feed = feed.Feed.get_manual_feed()
    for i in manual_feed.items:
        if i.get_url() == url:
            title = _("Download already exists")
            text1 = _("That URL is already an external download.")
            download_state = None
            if i.downloader is not None:
                download_state = i.downloader.get_state()
            if download_state in ('paused', 'stopped', 'failed'):
                i.download()
                text2 = _("%(appname)s will begin downloading it now.",
                          {"appname": config.get(prefs.SHORT_APP_NAME)})
            elif download_state == 'downloading':
                text2 = _("It is downloading now.")
            else:
                text2 = _("It has already been downloaded.")
            dialogs.MessageBoxDialog(title, "%s  %s" % (text1, text2)).run()
            return True
    existing_feed = feed.lookup_feed(url)
    if existing_feed is not None:
        return True
    return False

def _build_entry(url, content_type, additional=None):
    """Given a url, content type and additional metadata, builds and
    returns a FeedParserDict.
    """
    entry = {'updated_parsed': time.gmtime(time.time()),
             'enclosures': [{'url': url, 'type': unicode(content_type)}]}

    if additional is not None:
        for key in 'title', 'link', 'feed':
            if key in additional:
                entry[key] = additional[key]
        if 'description' in additional:
            entry['description'] = entry['summary'] = additional['description']
        if 'thumbnail' in additional:
            entry['thumbnail'] = {'href': additional['thumbnail']}
        if 'length' in additional:
            entry['enclosures'][0]['length'] = additional['length']

    if 'title' not in entry:
        dummy, dummy, urlpath, dummy, dummy, dummy = urlparse.urlparse(url)
        entry['title'] = os.path.basename(urlpath)

    return FeedParserDict(entry)

def download_unknown_mime_type(url):
    """Pops up a dialog box about how this is an unknown thing and
    asks the user what the user wants to do with it.

    :param url: the url to download
    """
    title = _('File Download')
    text = _(
        'This file at %(url)s does not appear to be audio, video, or '
        'an RSS feed.',
        {"url": url})
    dialog = dialogs.ThreeChoiceDialog(title, text,
                                       dialogs.BUTTON_DOWNLOAD_ANYWAY,
                                       dialogs.BUTTON_OPEN_IN_EXTERNAL_BROWSER,
                                       dialogs.BUTTON_CANCEL)
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
    """Given a url, this tries to figure out what it is (video, audio,
    torrent, rss feed, flash file that Miro can scrape) and handles it
    accordingly.

    If it can't figure out what it is, then it calls
    ``handle_unknown_callback`` with the url of the thing it can't
    identify and thus doesn't know what to do with.

    :param url: The url to download.

    :param handle_unknown_callback: The function to call if Miro can't
        figure out what kind of thing is at the url.  If this is None,
        then it uses the default ``download_unknown_mime_type``
        handler.

    :param metadata: dict holding additional metadata like title,
        description, ...
    """
    if handle_unknown_callback == None:
        handle_unknown_callback = download_unknown_mime_type

    if url.startswith('feed:') or url.startswith('feeds:'):
        # hack so feed(s): acts as http(s):
        url = "http" + url[4:]

    if check_url_exists(url):
        return

    def errback(error):
        title = _("Download Error")
        text = _(
            "%(appname)s is not able to download a file at this URL:\n"
            "\n"
            "URL: %(url)s\n"
            "\n"
            "Error: %(error)s (%(errordesc)s)",
            {"url": url,
             "appname": config.get(prefs.SHORT_APP_NAME),
             "error": error.getFriendlyDescription(),
             "errordesc": error.getLongDescription()}
        )
        logging.info("can't download '%s'", url)
        dialogs.MessageBoxDialog(title, text).run()

    def callback_peek(data):
        """Takes the data returned from a GET and peeks at it to see
        if it's a feed despite the fact that it has the wrong
        content-type.
        """
        if data["body"]:
            if filetypes.is_maybe_rss(data["body"]):
                # FIXME - this is silly since we just did a GET and we
                # do another one in add_feeds
                logging.info("%s is a feed--adding it." % url)
                add_feeds([url])
                return

        handle_unknown_callback(url)

    def callback(headers):
        """We need to figure out if the URL is a external video link,
        or a link to a feed.
        """
        if check_url_exists(url):
            return

        content_type = headers.get("content-type")
        if content_type:
            if filetypes.is_feed_content_type(content_type):
                add_feeds([url])
                return

            if  flashscraper.is_maybe_flashscrapable(url):
                entry = _build_entry(url, 'video/x-flv', additional=metadata)
                download_video(entry)
                return

            if filetypes.is_maybe_feed_content_type(content_type):
                logging.info("%s content type is %s.  "
                             "going to peek to see if it's a feed....",
                             url, content_type)
                httpclient.grab_url(url, callback_peek, errback)
                return

        entry = _build_entry(url, content_type)

        if filetypes.is_video_enclosure(entry['enclosures'][0]):
            download_video(entry)
        else:
            handle_unknown_callback(url)

    httpclient.grab_headers(url, callback, errback)

def download_video(fp_dict):
    """Takes a feedparser dict, generates an item.Item, adds the item
    to the manual feed, and sets the item to download.

    :param fp_dict: feedparser dict specifying metadata for the item
    """
    fp_values = item.FeedParserValues(fp_dict)
    manual_feed = feed.Feed.get_manual_feed()
    new_item = item.Item(fp_values, feed_id=manual_feed.get_id())
    new_item.download()

def filter_existing_feed_urls(urls):
    """Takes a list of feed urls and returns a list of urls that aren't
    already being managed by Miro.

    :param urls: list of urls to filter

    :returns: list of urls not already in Miro
    """
    return [u for u in urls if feed.lookup_feed(u) is None]

def add_feeds(urls, new_folder_name=None):
    """Adds a list of feeds that aren't already added to Miro to
    Miro.

    :param urls: list of urls to be added
    :param new_folder_name: if not None, the feeds will be added to
        this folder when created.
    """
    if not urls:
        return

    if new_folder_name is not None:
        new_folder = folder.ChannelFolder(new_folder_name)

    for url in filter_existing_feed_urls(urls):
        f = feed.Feed(url)
        if new_folder_name is not None:
            f.set_folder(new_folder)
