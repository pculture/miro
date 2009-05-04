# Miro - an RSS based video player application
# Copyright (C) 2009 Participatory Culture Foundation
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

from miro.gtcache import gettext as _

import os.path
import logging
from miro import config
from miro import prefs
from miro import messages
from miro import dialogs
from miro import autodiscover
from miro import subscription
from miro import feed
from miro import item
from miro import httpclient
from miro import download_utils
from miro.util import get_torrent_info_hash
from miro.plat.utils import samefile, filenameToUnicode
from miro import singleclick
from miro import opml

"""
This modules handles the parsing of files/URLs passed to Miro on the command line.

Frontends should call set_ommand_line_args() passing it a list of arguments that
the users gives.  This should just be suspected torrents/videos, not things
like '--help', '--version', etc.

Frontends should trap when a user opens a torrent/video with Miro while
Miro is already running.  They should arrange for add_video or add_torrent
to be called in the existing Miro process.

"""

_command_line_args = []
_command_line_videos = None
_command_line_view = None


def add_video(path, single=False):
    path = os.path.abspath(path)
    for i in item.Item.make_view():
        itemFilename = i.get_filename()
        if (itemFilename != '' and
                os.path.exists(itemFilename) and
                samefile(itemFilename, path)):
            logging.warn("Not adding duplicate video: %s" % path.decode('ascii', 'ignore'))
            if _command_line_videos is not None:
                _command_line_videos.add(i)
            return
    if single:
        correctFeed = feed.Feed.get_single_feed()
        items = list(correctFeed.items)
        for i in items:
            i.expire()
    else:
        correctFeed = feed.Feed.get_manual_feed()
    fileItem = item.FileItem(path, feed_id=correctFeed.getID())
    fileItem.markItemSeen()
    if _command_line_videos is not None:
        _command_line_videos.add(fileItem)


def add_torrent(path, torrentInfohash):
    manualFeed = feed.Feed.get_manual_feed()
    for i in manualFeed.items:
        if (i.downloader is not None and
                i.downloader.status.get('infohash') == torrentInfohash):
            logging.info("not downloading %s, it's already a download for %s", path, i)
            if i.downloader.get_state() in ('paused', 'stopped'):
                i.download()
            return
    newItem = item.Item(item.get_entry_for_file(path), feed_id=manualFeed.getID())
    newItem.download()


def complain_about_subscription_url(messageText):
    title = _("Subscription error")
    dialogs.MessageBoxDialog(title, messageText).run()

def add_subscription_url(prefix, expectedContentType, url):
    realURL = url[len(prefix):]
    def callback(info):
        if info.get('content-type') == expectedContentType:
            subscription_list = autodiscover.parse_content(info['body'])
            if subscription_list is None:
                text = _(
                    "This %(appname)s feed file has an invalid format: "
                    "%(url)s.  Please notify the publisher of this file.",
                    {"appname": config.get(prefs.SHORT_APP_NAME), "url": realURL}
                )
                complain_about_subscription_url(text)
            else:
                subscription.SubscriptionHandler().add_subscriptions(
                    subscription_list)
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


def reset_command_line_view():
    global _command_line_view, _command_line_videos
    if _command_line_view is not None:
        _command_line_view.unlink()
        _command_line_view = None
    _command_line_videos = set()


def parse_command_line_args(args=None):
    """
    This goes through a list of files which could be arguments passed
    in on the command line or a list of files from other source.

    If the args list is None, then this pulls from the internal
    _command_line_args list which is populated by set_command_line_args.
    """
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
        elif arg.startswith('miro:'):
            add_subscription_url('miro:', 'application/x-miro', arg)
        elif arg.startswith('democracy:'):
            add_subscription_url('democracy:', 'application/x-democracy', arg)
        elif arg.startswith('http:') or arg.startswith('https:') or arg.startswith('feed:') or arg.startswith('feeds:'):
            singleclick.add_download(filenameToUnicode(arg))
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
                singleclick.add_torrent(arg, torrentInfohash)
                added_downloads = True
            elif ext in ('.rss', '.rdf', '.atom', '.ato'):
                feed.add_feed_from_file(arg)
            elif ext in ('.miro', '.democracy', '.dem', '.opml'):
                opml.Importer().import_subscriptions(arg, showSummary=False)
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
