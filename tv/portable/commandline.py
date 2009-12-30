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

"""``miro.commandline`` -- This modules handles the parsing of
files/URLs passed to Miro on the command line.

Frontends should call ``set_ommand_line_args()`` passing it a list of
arguments that the users gives.  This should just be suspected
torrents/videos, not things like ``--help``, ``--version``, etc.

Frontends should trap when a user opens a torrent/video with Miro
while Miro is already running.  They should arrange for ``add_video``
or ``add_torrent`` to be called in the existing Miro process.
"""

from miro.gtcache import gettext as _

import os.path
import logging
from miro import app
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

_command_line_args = []
_command_line_videos = None
_command_line_view = None

def _item_exists_for_path(path):
    # in SQLite, LIKE is case insensitive, so we can use it to only look at
    # filenames that possibly will match
    for row in item.Item.select('filename',
            'filename IS NOT NULL AND filename LIKE ?', (path,)):
        if samefile(row[0], path):
            return True
    return False

def add_video(path, manual_feed=None):
    path = os.path.abspath(path)
    if _item_exists_for_path(path):
        logging.warn("Not adding duplicate video: %s",
                path.decode('ascii', 'ignore'))
        if _command_line_videos is not None:
            _command_line_videos.add(i)
        return
    if manual_feed is None:
        manual_feed = feed.Feed.get_manual_feed()
    file_item = item.FileItem(path, feed_id=manual_feed.get_id(),
            mark_seen=True)
    if _command_line_videos is not None:
        _command_line_videos.add(file_item)

def add_videos(paths):
    manual_feed = feed.Feed.get_manual_feed()
    app.bulk_sql_manager.start()
    try:
        for path in paths:
            add_video(path, manual_feed=manual_feed)
    finally:
        app.bulk_sql_manager.finish()

def add_torrent(path, torrent_info_hash):
    manual_feed = feed.Feed.get_manual_feed()
    for i in manual_feed.items:
        if ((i.downloader is not None
             and i.downloader.status.get('infohash') == torrent_info_hash)):
            logging.info("not downloading %s, it's already a download for %s",
                         path, i)
            if i.downloader.get_state() in ('paused', 'stopped'):
                i.download()
            return
    new_item = item.Item(item.fp_values_for_file(path),
                         feed_id=manual_feed.get_id())
    new_item.download()

def _complain_about_subscription_url(message_text):
    title = _("Subscription error")
    dialogs.MessageBoxDialog(title, message_text).run()

def add_subscription_url(prefix, expected_content_type, url):
    real_url = url[len(prefix):]
    def callback(info):
        if info.get('content-type') == expected_content_type:
            subscription_list = autodiscover.parse_content(info['body'])
            if subscription_list is None:
                text = _(
                    "This %(appname)s feed file has an invalid format: "
                    "%(url)s.  Please notify the publisher of this file.",
                    {"appname": config.get(prefs.SHORT_APP_NAME),
                     "url": real_url}
                    )
                _complain_about_subscription_url(text)
            else:
                subscription.SubscriptionHandler().add_subscriptions(
                    subscription_list)
        else:
            text = _(
                "This %(appname)s feed file has the wrong content type: "
                "%(url)s. Please notify the publisher of this file.",
                {"appname": config.get(prefs.SHORT_APP_NAME),
                 "url": real_url}
                )
            _complain_about_subscription_url(text)

    def errback(error):
        text = _(
            "Could not download the %(appname)s feed file: %(url)s",
            {"appname": config.get(prefs.SHORT_APP_NAME),
             "url": real_url}
            )
        _complain_about_subscription_url(text)

    httpclient.grabURL(real_url, callback, errback)

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
            arg = download_utils.get_file_url_path(arg)
        elif arg.startswith('miro:'):
            add_subscription_url('miro:', 'application/x-miro', arg)
        elif arg.startswith('democracy:'):
            add_subscription_url('democracy:', 'application/x-democracy', arg)
        elif (arg.startswith('http:')
              or arg.startswith('https:')
              or arg.startswith('feed:')
              or arg.startswith('feeds:')):
            singleclick.add_download(filenameToUnicode(arg))
        elif os.path.exists(arg):
            ext = os.path.splitext(arg)[1].lower()
            if ext in ('.torrent', '.tor'):
                try:
                    torrent_infohash = get_torrent_info_hash(arg)
                except ValueError:
                    title = _("Invalid Torrent")
                    msg = _(
                        "The torrent file %(filename)s appears to be corrupt "
                        "and cannot be opened.",
                        {"filename": os.path.basename(arg)}
                        )
                    dialogs.MessageBoxDialog(title, msg).run()
                    continue
                add_torrent(arg, torrent_infohash)
                added_downloads = True
            elif ext in ('.rss', '.rdf', '.atom', '.ato'):
                feed.add_feed_from_file(arg)
            elif ext in ('.miro', '.democracy', '.dem', '.opml'):
                opml.Importer().import_subscriptions(arg, show_summary=False)
            else:
                add_video(arg, len(args) == 1)
                added_videos = True
        else:
            logging.warning("parse_command_line_args: %s doesn't exist", arg)

    # if the user has Miro set up to play all videos externally, then
    # we don't want to play videos added by the command line.
    #
    # this fixes bug 12362 where if the user has his/her system set up
    # to use Miro to play videos and Miro goes to play a video
    # externally, then it causes an infinite loop and dies.
    if added_videos and config.get(prefs.PLAY_IN_MIRO):
        item_infos = [messages.ItemInfo(i) for i in _command_line_videos]
        messages.PlayMovie(item_infos).send_to_frontend()

    if added_downloads:
        # FIXME - switch to downloads tab?
        pass
