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

"""``miro.messagehandler``` -- Backend message handler
"""

from copy import copy
import logging
import time
import os

from miro import app
from miro import autoupdate
from miro import config
from miro import database
from miro import downloader
from miro import eventloop
from miro import feed
from miro.frontendstate import WidgetsFrontendState
from miro import guide
from miro import fileutil
from miro import commandline
from miro import item
from miro import messages
from miro import prefs
from miro import singleclick
from miro import subscription
from miro import tabs
from miro import opml
from miro import searchengines
from miro.feed import Feed, get_feed_by_url
from miro.gtcache import gettext as _
from miro.playlist import SavedPlaylist
from miro.folder import FolderBase, ChannelFolder, PlaylistFolder
from miro.xhtmltools import urlencode

from miro.plat.utils import makeURLSafe

import shutil

class ViewTracker(object):
    """Handles tracking views for TrackGuides, TrackChannels, TrackPlaylist and TrackItems."""

    def __init__(self):
        self.trackers = []
        self.add_callbacks()
        self.reset_changes()
        self.tabs_being_reordered = False
        self._last_sent_info = {}

    def reset_changes(self):
        self.changed = set()
        self.removed = set()
        self.added =  []
        # Need to use a list because added messages must be sent in the same
        # order they were received
        self.changes_pending = False

    def send_messages(self):
        # Try to reduce the number of messages we're sending out.
        self.changed -= self.removed
        self.changed -= set(self.added)

        for i in reversed(xrange(len(self.added))):
            if self.added[i] in self.removed:
                # Object was removed before we sent the add message, just
                # don't send any message
                self.removed.remove(self.added.pop(i))
        message = self.make_changed_message(
                self._make_added_list(self.added),
                self._make_changed_list(self.changed),
                self._make_removed_list(self.removed))
        if message.added or message.changed or message.removed:
            message.send_to_frontend()
        self.reset_changes()

    def _make_new_info(self, obj):
        info = self.InfoClass(obj)
        self._last_sent_info[obj.id] = copy(info)
        return info

    def _make_added_list(self, added):
        return [self._make_new_info(obj) for obj in added]

    def _make_changed_list(self, changed):
        retval = []
        for obj in changed:
            info = self.InfoClass(obj)
            if obj.id not in self._last_sent_info or info.__dict__ != self._last_sent_info[obj.id].__dict__:
                retval.append(info)
                self._last_sent_info[obj.id] = copy(info)
        return retval

    def _make_removed_list(self, removed):
        for obj in removed:
            del self._last_sent_info[obj.id]
        return [obj.id for obj in removed]


    def schedule_send_messages(self):
        # We don't send messages immediately so that if an object gets changed
        # multiple times, only one callback gets sent.
        if not self.changes_pending:
            eventloop.addUrgentCall(self.send_messages, 'view tracker update' )
            self.changes_pending = True

    def add_callbacks(self):
        for view in self.get_object_views():
            tracker = view.make_tracker()
            tracker.connect('added', self.on_object_added)
            tracker.connect('removed', self.on_object_removed)
            tracker.connect('changed', self.on_object_changed)
            self.trackers.append(tracker)

    def on_object_added(self, tracker, obj):
        if self.tabs_being_reordered:
            # even though we're not sending messages, call _make_new_info() to
            # update _last_sent_info
            self._make_new_info(obj)
            return
        if obj in self.changed:
            # object was already removed, we need to send that message out
            # before we send the add message.
            self.send_messages()
        self.added.append(obj)
        self.schedule_send_messages()

    def on_object_removed(self, tracker, obj):
        if self.tabs_being_reordered:
            # even though we're not sending messages, update _last_sent_info
            del self._last_sent_info[obj.id]
            return
        self.removed.add(obj)
        self.schedule_send_messages()

    def on_object_changed(self, tracker, obj):
        # Don't pay attention to tabs_being_reordered here.  This lets us
        # update the new/unwatched counts when channels are added/removed from
        # folders (#10988)
        self.changed.add(obj)
        self.schedule_send_messages()

    def old_on_object_added(self, obj, id):
        self.on_object_added(None, obj)
    def old_on_object_changed(self, obj, id):
        self.on_object_changed(None, obj)
    def old_on_object_removed(self, obj, id):
        self.on_object_removed(None, obj)

    def unlink(self):
        for tracker in self.trackers:
            tracker.unlink()

class TabTracker(ViewTracker):
    def __init__(self):
        ViewTracker.__init__(self)
        self.send_whole_list = False

    def make_changed_message(self, added, changed, removed):
        return messages.TabsChanged(self.type, added, changed, removed)

    def send_messages(self):
        if self.send_whole_list:
            self.send_initial_list()
            self.send_whole_list = False
            self.reset_changes()
        else:
            ViewTracker.send_messages(self)

    def send_initial_list(self):
        response = messages.TabList(self.type)
        current_folder_id = None
        for obj in self.get_tab_order().get_all_tabs():
            info = self._make_new_info(obj)
            if obj.get_folder() is None:
                response.append(info)
                if isinstance(obj, FolderBase):
                    current_folder_id = obj.id
                    if obj.getExpanded():
                        response.expand_folder(obj.id)
                else:
                    current_folder_id = None
            else:
                if (current_folder_id is None or
                        obj.get_folder().id != current_folder_id):
                    raise AssertionError("Tab ordering is wrong")
                response.append_child(current_folder_id, info)
        response.send_to_frontend()

class ChannelTracker(TabTracker):
    type = 'feed'
    InfoClass = messages.ChannelInfo

    def get_object_views(self):
        return feed.Feed.visible_video_view(), ChannelFolder.video_view()

    def get_tab_order(self):
        return tabs.TabOrder.video_feed_order()

class AudioChannelTracker(TabTracker):
    type = 'audio-feed'
    InfoClass = messages.ChannelInfo

    def get_object_views(self):
        return feed.Feed.visible_audio_view(), ChannelFolder.audio_view()

    def get_tab_order(self):
        return tabs.TabOrder.audio_feed_order()

class PlaylistTracker(TabTracker):
    type = 'playlist'
    InfoClass = messages.PlaylistInfo

    def get_object_views(self):
        return SavedPlaylist.make_view(), PlaylistFolder.make_view()

    def get_tab_order(self):
        return tabs.TabOrder.playlist_order()

class GuideTracker(ViewTracker):
    InfoClass = messages.GuideInfo

    def get_object_views(self):
        return [guide.ChannelGuide.make_view()]

    def make_changed_message(self, added, changed, removed):
        return messages.TabsChanged('guide', added, changed, removed)

    def send_initial_list(self):
        info_list = self._make_added_list(guide.ChannelGuide.make_view())
        messages.GuideList(info_list).send_to_frontend()

class WatchedFolderTracker(ViewTracker):
    InfoClass = messages.WatchedFolderInfo

    def get_object_views(self):
        return (feed.Feed.watched_folder_view(),)

    def make_changed_message(self, added, changed, removed):
        return messages.WatchedFoldersChanged(added, changed, removed)

    def send_initial_list(self):
        info_list = self._make_added_list(feed.Feed.watched_folder_view())
        messages.WatchedFolderList(info_list).send_to_frontend()

class ItemTrackerBase(ViewTracker):
    InfoClass = messages.ItemInfo

    def make_changed_message(self, added, changed, removed):
        return messages.ItemsChanged(self.type, self.id,
                added, changed, removed)

    def get_object_views(self):
        return [self.view]

    def send_initial_list(self):
        infos = self._make_added_list(self.view)
        messages.ItemList(self.type, self.id, infos).send_to_frontend()

class FeedItemTracker(ItemTrackerBase):
    type = 'feed'
    def __init__(self, feed):
        self.view = feed.visible_items
        self.id = feed.id
        ItemTrackerBase.__init__(self)

class FeedFolderItemTracker(ItemTrackerBase):
    type = 'feed'
    def __init__(self, folder):
        self.view = item.Item.visible_folder_view(folder.id)
        self.id = folder.id
        ItemTrackerBase.__init__(self)

class PlaylistItemTracker(ItemTrackerBase):
    type = 'playlist'
    def __init__(self, playlist):
        self.view = item.Item.playlist_view(playlist.id)
        self.id = playlist.id
        ItemTrackerBase.__init__(self)

class PlaylistFolderItemTracker(ItemTrackerBase):
    type = 'playlist'
    def __init__(self, playlist):
        self.view = item.Item.playlist_folder_view(playlist.id)
        self.id = playlist.id
        ItemTrackerBase.__init__(self)

class ManualItemTracker(ItemTrackerBase):
    type = 'manual'

    def __init__(self, id, id_list):
        self.id = id
        # SQLite can only handle 999 variables at once.  If there are more ids
        # than that, we need to split things up (#12020)
        self.views = []
        for pos in xrange(0, len(id_list), 950):
            bite_sized_list = id_list[pos:pos+950]
            place_holders = ', '.join('?' for i in xrange(len(bite_sized_list)))
            self.views.append(item.Item.make_view(
                'id in (%s)' % place_holders, tuple(bite_sized_list)))
        ItemTrackerBase.__init__(self)

    def get_object_views(self):
        return self.views

    def send_initial_list(self):
        infos = []
        for view in self.views:
            infos.extend(self._make_added_list(view))
        messages.ItemList(self.type, self.id, infos).send_to_frontend()

class DownloadingItemsTracker(ItemTrackerBase):
    type = 'downloads'
    id = None
    def __init__(self):
        self.view = item.Item.download_tab_view()
        ItemTrackerBase.__init__(self)

class VideoItemsTracker(ItemTrackerBase):
    type = 'videos'
    id = None
    def __init__(self):
        self.view = item.Item.watchable_video_view()
        ItemTrackerBase.__init__(self)

class AudioItemsTracker(ItemTrackerBase):
    type = 'audios'
    id = None
    def __init__(self):
        self.view = item.Item.watchable_audio_view()
        ItemTrackerBase.__init__(self)

class OtherItemsTracker(ItemTrackerBase):
    type = 'others'
    id = None
    def __init__(self):
        self.view = item.Item.watchable_other_view()
        ItemTrackerBase.__init__(self)

class SearchItemsTracker(ItemTrackerBase):
    type = 'search'
    id = None
    def __init__(self):
        self.view = item.Item.search_item_view()
        ItemTrackerBase.__init__(self)

class FolderItemsTracker(ItemTrackerBase):
    type = 'folder-contents'
    def __init__(self, folder_id):
        self.view = item.Item.folder_contents_view(folder_id)
        self.id = folder_id
        ItemTrackerBase.__init__(self)

def make_item_tracker(message):
    if message.type == 'downloads':
        return DownloadingItemsTracker()
    elif message.type == 'videos':
        return VideoItemsTracker()
    elif message.type == 'audios':
        return AudioItemsTracker()
    elif message.type == 'others':
        return OtherItemsTracker()
    elif message.type == 'search':
        return SearchItemsTracker()
    elif message.type == 'folder-contents':
        return FolderItemsTracker(message.id)
    elif message.type == 'feed':
        try:
            feed_ = feed.Feed.get_by_id(message.id)
            return FeedItemTracker(feed_)
        except database.ObjectNotFoundError:
            folder = ChannelFolder.get_by_id(message.id)
            return FeedFolderItemTracker(folder)
    elif message.type == 'playlist':
        try:
            playlist = SavedPlaylist.get_by_id(message.id)
            return PlaylistItemTracker(playlist)
        except database.ObjectNotFoundError:
            playlist = PlaylistFolder.get_by_id(message.id)
            return PlaylistFolderItemTracker(playlist)
    elif message.type == 'manual':
        return ManualItemTracker(message.id, message.ids_to_track)
    else:
        logging.warn("Unknown TrackItems type: %s", message.type)

class CountTracker(object):
    """Tracks downloads count or new videos count"""
    def __init__(self):
        self.tracker = self.get_view().make_tracker()
        self.tracker.connect('added', self.on_count_changed)
        self.tracker.connect('removed', self.on_count_changed)

    def on_count_changed(self, tracker, obj):
        self.send_message()

    def send_message(self):
        self.make_message(len(self.tracker)).send_to_frontend()

    def stop_tracking(self):
        self.tracker.unlink()

class DownloadCountTracker(CountTracker):
    def get_view(self):
        return item.Item.only_downloading_view()

    def make_message(self, count):
        return messages.DownloadCountChanged(count)

class PausedCountTracker(CountTracker):
    def get_view(self):
        return item.Item.paused_view()

    def make_message(self, count):
        return messages.PausedCountChanged(count)

class NewVideoCountTracker(CountTracker):
    def get_view(self):
        return item.Item.unique_new_video_view()

    def make_message(self, count):
        return messages.NewVideoCountChanged(count)

class NewAudioCountTracker(CountTracker):
    def get_view(self):
        return item.Item.unique_new_audio_view()

    def make_message(self, count):
        return messages.NewAudioCountChanged(count)

class UnwatchedCountTracker(CountTracker):
    def get_view(self):
        return item.Item.newly_downloaded_view()

    def make_message(self, count):
        return messages.UnwatchedCountChanged(count)

class BackendMessageHandler(messages.MessageHandler):
    def __init__(self, frontend_startup_callback):
        messages.MessageHandler.__init__(self)
        self.frontend_startup_callback = frontend_startup_callback
        self.channel_tracker = None
        self.audio_channel_tracker = None
        self.playlist_tracker = None
        self.guide_tracker = None
        self.watched_folder_tracker = None
        self.download_count_tracker = None
        self.paused_count_tracker = None
        self.new_video_count_tracker = None
        self.new_audio_count_tracker = None
        self.unwatched_count_tracker = None
        self.item_trackers = {}
        search_feed = get_feed_by_url('dtv:search')
        search_feed.connect('update-finished', self._search_update_finished)

    def call_handler(self, method, message):
        name = 'handling backend message: %s' % message
        logging.debug("handling backend %s", message)
        eventloop.addUrgentCall(method, name, args=(message,))

    def folder_class_for_type(self, type):
        if type in ('feed', 'audio-feed'):
            return ChannelFolder
        elif type == 'playlist':
            return PlaylistFolder
        else:
            raise ValueError("Unknown Type: %s" % type)

    def ddb_object_class_for_type(self, type):
        if type == 'feed':
            return feed.Feed
        elif type == 'audio-feed':
            return feed.Feed
        elif type == 'playlist':
            return SavedPlaylist
        elif type == 'feed-folder':
            return ChannelFolder
        elif type == 'playlist-folder':
            return PlaylistFolder
        elif type == 'site':
            return guide.ChannelGuide
        else:
            raise ValueError("Unknown Type: %s" % type)

    def handle_frontend_started(self, message):
        # add a little bit more delay to let things simmer down a bit.  The
        # calls here are low-priority, so we can afford to wait a bit.
        eventloop.addTimeout(2, self.frontend_startup_callback,
                'frontend startup callback')

    def handle_query_search_info(self, message):
        search_feed = get_feed_by_url('dtv:search')
        messages.CurrentSearchInfo(search_feed.lastEngine,
                search_feed.lastQuery).send_to_frontend()

    def handle_track_channels(self, message):
        if not self.channel_tracker:
            self.channel_tracker = ChannelTracker()
        if not self.audio_channel_tracker:
            self.audio_channel_tracker = AudioChannelTracker()
        self.channel_tracker.send_initial_list()
        self.audio_channel_tracker.send_initial_list()

    def handle_stop_tracking_channels(self, message):
        if self.channel_tracker:
            self.channel_tracker.unlink()
            self.channel_tracker = None

    def handle_track_guides(self, message):
        if not self.guide_tracker:
            self.guide_tracker = GuideTracker()
        self.guide_tracker.send_initial_list()

    def handle_stop_tracking_guides(self, message):
        if self.guide_tracker:
            self.guide_tracker.unlink()
            self.guide_tracker = None

    def handle_track_watched_folders(self, message):
        if not self.watched_folder_tracker:
            self.watched_folder_tracker = WatchedFolderTracker()
        self.watched_folder_tracker.send_initial_list()

    def handle_stop_tracking_watched_folders(self, message):
        if self.watched_folder_tracker:
            self.watched_folder_tracker.unlink()
            self.watched_folder_tracker = None

    def handle_track_playlists(self, message):
        if not self.playlist_tracker:
            self.playlist_tracker = PlaylistTracker()
        self.playlist_tracker.send_initial_list()

    def handle_stop_tracking_playlists(self, message):
        if self.playlist_tracker:
            self.playlist_tracker.unlink()
            self.playlist_tracker = None

    def handle_mark_feed_seen(self, message):
        try:
            try:
                feed_ = feed.Feed.get_by_id(message.id)
            except database.ObjectNotFoundError:
                feed_ = ChannelFolder.get_by_id(message.id)
            feed_.mark_as_viewed()
        except database.ObjectNotFoundError:
            logging.warning("handle_mark_feed_seen: can't find feed by id %s", message.id)

    def handle_mark_item_watched(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
            item_.mark_item_seen()
        except database.ObjectNotFoundError:
            logging.warning("handle_mark_item_seen: can't find item by id %s", message.id)

    def handle_mark_item_unwatched(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
            item_.mark_item_unseen()
        except database.ObjectNotFoundError:
            logging.warning("handle_mark_item_unwatched: can't find item by id %s", message.id)

    def handle_set_item_resume_time(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
            item_.set_resume_time(message.resume_time)
        except database.ObjectNotFoundError:
            logging.warning("handle_set_item_resume_time: can't find item by id %s", message.id)

    def handle_set_feed_expire(self, message):
        channel_info = message.channel_info
        expire_type = message.expire_type
        expire_time = message.expire_time

        try:
            channel = feed.Feed.get_by_id(channel_info.id)
            if expire_type == "never":
                channel.setExpiration(u"never", 0)
            elif expire_type == "system":
                channel.setExpiration(u"system", expire_time)
            else:
                channel.setExpiration(u"feed", expire_time)

        except database.ObjectNotFoundError:
            logging.warning("handle_set_feed_expire: can't find feed by id %s", channel_info.id)

    def handle_set_feed_max_new(self, message):
        channel_info = message.channel_info
        value = message.max_new

        try:
            channel = feed.Feed.get_by_id(channel_info.id)
            if value == u"unlimited":
                channel.set_max_new(-1)
            else:
                channel.set_max_new(value)

        except database.ObjectNotFoundError:
            logging.warning("handle_set_feed_max_new: can't find feed by id %s", channel_info.id)

    def handle_set_feed_max_old_items(self, message):
        channel_info = message.channel_info
        max_old_items = message.max_old_items

        try:
            channel = feed.Feed.get_by_id(channel_info.id)
            channel.setMaxOldItems(max_old_items)

        except database.ObjectNotFoundError:
            logging.warning("handle_set_feed_max_new: can't find feed by id %s", channel_info.id)

    def handle_clean_feed(self, message):
        channel_id = message.channel_id
        try:
            obj = feed.Feed.get_by_id(channel_id)
        except database.ObjectNotFoundError:
            logging.warn("handle_clean_feed: object not found id: %s" % channel_id)
        else:
            obj.clean_old_items()

    def handle_import_feeds(self, message):
        opml.Importer().import_subscriptions(message.filename)

    def handle_export_subscriptions(self, message):
        opml.Exporter().export_subscriptions(message.filename)

    def handle_rename_object(self, message):
        klass = self.ddb_object_class_for_type(message.type)
        try:
            obj = klass.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("object not found (type: %s, id: %s)" %
                    (message.type, message.id))
        else:
            obj.set_title(message.new_name)

    def handle_play_all_unwatched(self, message):
        item_infos = [messages.ItemInfo(i) for i in
                item.Item.newly_downloaded_view()]
        messages.PlayMovie(item_infos).send_to_frontend()

    def handle_folder_expanded_change(self, message):
        klass = self.folder_class_for_type(message.type)
        try:
            folder = klass.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("feed folder not found")
        else:
            folder.setExpanded(message.expanded)

    def handle_update_feed(self, message):
        try:
            feed_ = feed.Feed.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("feed not found: %s" % id)
        else:
            feed_.update()

    def handle_update_feed_folder(self, message):
        try:
            f = ChannelFolder.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("folder not found: %s" % id)
        else:
            for feed in f.getChildrenView():
                feed.update()

    def handle_update_all_feeds(self, message):
        for f in feed.Feed.make_view():
            f.scheduleUpdateEvents(0)

    def handle_delete_feed(self, message):
        if message.is_folder:
            klass = ChannelFolder
        else:
            klass = feed.Feed
        try:
            channel = klass.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("feed not found: %s" % message.id)
        else:
            if message.keep_items:
                move_to = feed.Feed.get_manual_feed()
            else:
                move_to = None
            channel.remove(move_to)

    def handle_delete_watched_folder(self, message):
        try:
            channel = feed.Feed.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("watched folder not found: %s" % message.id)
        else:
            if channel.is_watched_folder():
                channel.remove()
            else:
                logging.warn("%s is not a watched folder" % feed)

    def handle_delete_playlist(self, message):
        if message.is_folder:
            klass = PlaylistFolder
        else:
            klass = SavedPlaylist
        try:
            playlist = klass.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("playlist not found: %s" % message.id)
        else:
            playlist.remove()

    def handle_delete_site(self, message):
        try:
            site = guide.ChannelGuide.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("site not found: %s" % message.id)
        else:
            if site.get_default():
                raise ValueError("Can't delete default site")
            site.remove()

    def handle_tabs_reordered(self, message):
        # The frontend already has the channels in the correct order and with
        # the correct parents.  Don't send it updates based on the backend
        # re-aranging things
        if self.channel_tracker:
            self.channel_tracker.tabs_being_reordered = True
        if self.audio_channel_tracker:
            self.audio_channel_tracker.tabs_being_reordered = True
        try:
            self._do_handle_tabs_reordered(message)
        finally:
            if self.channel_tracker:
                self.channel_tracker.tabs_being_reordered = False
            if self.audio_channel_tracker:
                self.audio_channel_tracker.tabs_being_reordered = False

    def _do_handle_tabs_reordered(self, message):
        video_order = tabs.TabOrder.video_feed_order()
        audio_order = tabs.TabOrder.audio_feed_order()
        playlist_order = tabs.TabOrder.playlist_order()

        # make sure all the items are in the right places
        video_ids = set(info.id for info in message.toplevels['feed'])
        audio_ids = set(info.id for info in message.toplevels['audio-feed'])

        for obj in tabs.TabOrder.video_feed_order().get_all_tabs():
            if obj.id in audio_ids:
                obj.section = u'audio'
                obj.signal_change()
        for obj in tabs.TabOrder.audio_feed_order().get_all_tabs():
            if obj.id in video_ids:
                obj.section = u'video'
                obj.signal_change()

        for id_, feeds in message.folder_children.iteritems():
            try:
                feed_folder = ChannelFolder.get_by_id(id_)
            except database.ObjectNotFoundError:
                continue
            for mem in feeds:
                try:
                    mem = feed.Feed.get_by_id(mem.id)
                except database.ObjectNotFoundError:
                    continue
                if feed_folder.section != mem.section:
                    mem.section = feed_folder.section
                    mem.signal_change()

        for info_type, info_list in message.toplevels.iteritems():
            folder_class = self.folder_class_for_type(info_type)

            if info_type == 'feed':
                child_class = feed.Feed
                tab_order = video_order
            elif info_type == 'audio-feed':
                child_class = feed.Feed
                tab_order = audio_order
            elif info_type == 'playlist':
                child_class = SavedPlaylist
                tab_order = playlist_order
            else:
                raise ValueError("Unknown Type: %s" % message.type)

            order = []
            new_folders = []
            for info in info_list:
                order.append(info.id)
                if info.is_folder:
                    folder = folder_class.get_by_id(info.id)
                    for child_info in message.folder_children[info.id]:
                        child_id = child_info.id
                        order.append(child_id)
                        child = child_class.get_by_id(child_id)
                        new_folders.append((child, folder))
                else:
                    child = child_class.get_by_id(info.id)
                    new_folders.append((child, None))
            child_class.bulk_set_folders(new_folders)
            tab_order.reorder(order)
            tab_order.signal_change()

    def handle_playlist_reordered(self, message):
        try:
            playlist = SavedPlaylist.get_by_id(message.id)
        except database.ObjectNotFoundError:
            try:
                playlist = PlaylistFolder.get_by_id(message.id)
            except database.ObjectNotFoundError:
                logging.warn("PlaylistReordered: Playlist not found -- %s",
                        message.id)
                return

        if isinstance(playlist, PlaylistFolder):
            item_view = item.Item.playlist_folder_view(playlist.id)
        else:
            item_view = item.Item.playlist_view(playlist.id)
        playlist_item_ids = [i.id for i in item_view]
        if set(playlist_item_ids) != set(message.item_ids):
            logging.warn("PlaylistReordered: Not all ids present in the new order\nOriginal Ids: %s\nNew ids: %s", playlist_item_ids, message.item_ids)
            return
        playlist.reorder(message.item_ids)
        playlist.signal_change()

    def handle_new_guide(self, message):
        url = message.url
        if guide.get_guide_by_url(url) is None:
            guide.ChannelGuide(url, [u'*'])

    def handle_new_feed(self, message):
        url = message.url
        if not get_feed_by_url(url):
            Feed(url, section=message.section)

    def handle_new_feed_search_feed(self, message):
        term = message.search_term
        channel_info = message.channel_info
        section = message.section
        location = channel_info.base_href

        if isinstance(term, unicode):
            term = term.encode("utf-8")

        if isinstance(location, unicode):
            location = location.encode("utf-8")

        if channel_info.search_term:
            term = term + " " + channel_info.search_term

        url = u"dtv:searchTerm:%s?%s" % (urlencode(location), urlencode(term))
        if not get_feed_by_url(url):
            Feed(url, section=section)

    def handle_new_feed_search_engine(self, message):
        sei = message.search_engine_info
        term = message.search_term
        section = message.section

        url = searchengines.get_request_url(sei.name, term)

        if not url:
            return

        if not get_feed_by_url(url):
            f = Feed(url, section=section)

    def handle_new_feed_search_url(self, message):
        url = message.url
        term = message.search_term
        section = message.section

        if isinstance(term, unicode):
            term = term.encode("utf-8")

        normalized = feed.normalize_feed_url(url)

        if isinstance(url, unicode):
            url = url.encode("utf-8")

        url = u"dtv:searchTerm:%s?%s" % (urlencode(normalized), urlencode(term))
        if not get_feed_by_url(url):
            Feed(url, section=section)

    def handle_new_feed_folder(self, message):
        folder = ChannelFolder(message.name, message.section)

        if message.child_feed_ids is not None:
            section = message.section
            for id in message.child_feed_ids:
                feed_ = feed.Feed.get_by_id(id)
                feed_.set_folder(folder)
                if feed_.section != section:
                    feed_.section = section
                    feed_.signal_change()
            if section == u'video':
                tab_order = tabs.TabOrder.video_feed_order()
                tracker = self.channel_tracker
            else:
                tab_order = tabs.TabOrder.audio_feed_order()
                tracker = self.audio_channel_tracker
            tab_order.move_tabs_after(folder.id, message.child_feed_ids)
            tab_order.signal_change()
            tracker.send_whole_list = True

    def handle_new_watched_folder(self, message):
        url = u"dtv:directoryfeed:%s" % makeURLSafe(message.path)
        if not get_feed_by_url(url):
            feed.Feed(url)
        else:
            logging.info("Not adding duplicated watched folder: %s",
                    message.path)

    def handle_set_watched_folder_visible(self, message):
        try:
            feed_ = feed.Feed.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("watched folder not found: %s" % message.id)
        else:
            if not feed_.url.startswith("dtv:directoryfeed:"):
                raise ValueError("%s is not a watched folder" % feed_)
            feed_.setVisible(message.visible)

    def handle_new_playlist(self, message):
        name = message.name
        ids = message.ids
        if not ids:
            ids = None
        SavedPlaylist(name, ids)

    def handle_download_url(self, message):
        singleclick.add_download(message.url, message.handle_unknown_callback, message.metadata)

    def handle_open_individual_file(self, message):
        commandline.parse_command_line_args([message.filename])

    def handle_open_individual_files(self, message):
        commandline.parse_command_line_args(message.filenames)

    def handle_add_files(self, message):
        # add all files to Miro in the manualFeed
        for mem in message.filenames:
            if mem:
                commandline.add_video(mem, False)

    def handle_check_version(self, message):
        up_to_date_callback = message.up_to_date_callback
        autoupdate.check_for_updates(up_to_date_callback)

    def handle_new_playlist_folder(self, message):
        folder = PlaylistFolder(message.name)
        if message.child_playlist_ids is not None:
            for id in message.child_playlist_ids:
                playlist = SavedPlaylist.get_by_id(id)
                playlist.set_folder(folder)
            tab_order = tabs.TabOrder.playlist_order()
            tab_order.move_tabs_after(folder.id, message.child_playlist_ids)
            tab_order.signal_change()
            self.playlist_tracker.send_whole_list = True

    def handle_add_videos_to_playlist(self, message):
        try:
            playlist = SavedPlaylist.get_by_id(message.playlist_id)
        except database.ObjectNotFoundError:
            logging.warn("AddVideosToPlaylist: Playlist not found -- %s",
                    message.playlist_id)
            return
        for id in message.video_ids:
            try:
                item_ = item.Item.get_by_id(id)
            except database.ObjectNotFoundError:
                logging.warn("AddVideosToPlaylist: Item not found -- %s", id)
                continue
            if not item_.is_downloaded():
                logging.warn("AddVideosToPlaylist: Item not downloaded (%s)",
                        item_)
            else:
                playlist.add_item(item_)

    def handle_remove_videos_from_playlist(self, message):
        try:
            playlists = [SavedPlaylist.get_by_id(message.playlist_id)]
        except database.ObjectNotFoundError:
            # it's possible this playlist is really a playlist folder with
            # playlists in it.
            try:
                playlists = list(SavedPlaylist.folder_view(message.playlist_id))
            except database.ObjectNotFoundError:
                logging.warn("RemoveVideosFromPlaylist: playlist not found -- %s", message.playlist_id)
                return

        not_removed = []
        for id_ in message.video_ids:
            found = False
            for playlist in playlists:
                if playlist.contains_id(id_):
                    playlist.remove_id(id_)
                    found = True
            if not found:
                not_removed.append(id_)
        for id_ in not_removed:
            logging.warn("RemoveVideosFromPlaylist: Id not found -- %s", id_)

    def handle_search(self, message):
        searchengine_id = message.id
        terms = message.terms

        search_feed = get_feed_by_url('dtv:search')
        search_downloads_feed = get_feed_by_url('dtv:searchDownloads')

        search_feed.preserveDownloads(search_downloads_feed)
        if terms:
            search_feed.lookup(searchengine_id, terms)
        else:
            search_feed.set_info(searchengine_id, u'')
            search_feed.reset()

    def _search_update_finished(self, feed):
        messages.SearchComplete(feed.lastEngine, feed.lastQuery,
                feed.items.count()).send_to_frontend()

    def item_tracker_key(self, message):
        if message.type != 'manual':
            return (message.type, message.id)
        else:
            # make sure the item list is a tuple, so it can be hashed.
            return (message.type, tuple(message.id))

    def handle_track_items(self, message):
        key = self.item_tracker_key(message)
        if key not in self.item_trackers:
            try:
                item_tracker = make_item_tracker(message)
            except database.ObjectNotFoundError:
                logging.warn("TrackItems called for deleted object (%s %s)",
                        message.type, message.id)
                return
            if item_tracker is None:
                # message type was wrong
                return
            self.item_trackers[key] = item_tracker
        else:
            item_tracker = self.item_trackers[key]
        item_tracker.send_initial_list()

    def handle_track_items_manually(self, message):
        # handle_track_items can handle this message too
        self.handle_track_items(message)

    def handle_stop_tracking_items(self, message):
        key = self.item_tracker_key(message)
        try:
            item_tracker = self.item_trackers.pop(key)
        except KeyError:
            logging.warn("Item tracker not found (id: %s)", message.id)
        else:
            item_tracker.unlink()

    def handle_start_download(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("StartDownload: Item not found -- %s", message.id)
        else:
            item_.download()

    def handle_cancel_download(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("CancelDownload: Item not found -- %s", message.id)
        else:
            item_.expire()

    def handle_pause_all_downloads(self, message):
        """Pauses all downloading and uploading items"""
        for item_ in item.Item.downloading_view():
            if item_.is_uploading():
                item_.pauseUpload()
            else:
                item_.pause()

    def handle_pause_download(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("PauseDownload: Item not found -- %s", message.id)
        else:
            item_.pause()

    def handle_resume_all_downloads(self, message):
        """Resumes downloading and uploading items"""
        for item_ in item.Item.paused_view():
            if item_.is_uploading_paused():
                item_.startUpload()
            else:
                item_.resume()

    def handle_resume_download(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("ResumeDownload: Item not found -- %s", message.id)
        else:
            item_.resume()

    def handle_cancel_all_downloads(self, message):
        for item_ in item.Item.download_tab_view():
            if item_.is_uploading() or item_.is_uploading_paused():
                item_.stop_upload()
            else:
                item_.expire()

    def handle_start_upload(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("handle_start_upload: Item not found -- %s", message.id)
        else:
            if item_.parent_id is not None:
                # use the parent torrent file
                item_ = item_.get_parent()
            if item_.downloader.get_type() != 'bittorrent':
                logging.warn("%s is not a torrent", item_)
            elif item_.is_uploading():
                logging.warn("%s is already uploading", item_)
            else:
                item_.startUpload()

    def handle_stop_upload(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("handle_stop_upload: Item not found -- %s", message.id)
        else:
            if item_.parent_id is not None:
                # use the parent torrent file
                item_ = item_.get_parent()
            if item_.downloader.get_type() != 'bittorrent':
                logging.warn("%s is not a torrent", item_)
            elif not item_.is_uploading():
                logging.warn("%s is already stopped", item_)
            else:
                item_.stop_upload()

    def handle_keep_video(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("KeepVideo: Item not found -- %s", message.id)
        else:
            item_.save()

    def handle_save_item_as(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("SaveVideoAs: Item not found -- %s", message.id)
            return

        logging.info("saving video %s to %s" % (item_.get_filename(),
                                                message.filename))
        try:
            shutil.copyfile(item_.get_filename(), message.filename)
        except IOError:
            # FIXME - we should pass the error back to the frontend
            pass

    def handle_remove_video_entry(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("RemoveVideoEntry: Item not found -- %s", message.id)
        else:
            item_.expire()

    def handle_delete_video(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("DeleteVideo: Item not found -- %s", message.id)
        else:
            item_.delete_files()
            item_.expire()

    def handle_rename_video(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("RenameVideo: Item not found -- %s", message.id)
        else:
            item_.set_title(message.new_name)

    def handle_revert_feed_title(self, message):
        try:
            feed_object = feed.Feed.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("RevertFeedTitle: Feed not found -- %s", message.id)
        else:
            feed_object.revert_title()

    def handle_revert_item_title(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("RevertItemTitle: Item not found -- %s", message.id)
        else:
            item_.revert_title()

    def handle_autodownload_change(self, message):
        try:
            feed_ = feed.Feed.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("AutodownloadChange: Feed not found -- %s", message.id)
        else:
            feed_.set_auto_download_mode(message.setting)

    def handle_track_download_count(self, message):
        if self.download_count_tracker is None:
            self.download_count_tracker = DownloadCountTracker()
        self.download_count_tracker.send_message()

    def handle_stop_tracking_download_count(self, message):
        if self.download_count_tracker:
            self.download_count_tracker.stop_tracking()
            self.download_count_tracker = None

    def handle_track_paused_count(self, message):
        if self.paused_count_tracker is None:
            self.paused_count_tracker = PausedCountTracker()
        self.paused_count_tracker.send_message()

    def handle_stop_tracking_paused_count(self, message):
        if self.paused_count_tracker:
            self.paused_count_tracker.stop_tracking()
            self.paused_count_tracker = None

    def handle_track_new_video_count(self, message):
        if self.new_video_count_tracker is None:
            self.new_video_count_tracker = NewVideoCountTracker()
        self.new_video_count_tracker.send_message()

    def handle_stop_tracking_new_video_count(self, message):
        if self.new_video_count_tracker:
            self.new_video_count_tracker.stop_tracking()
            self.new_video_count_tracker = None

    def handle_track_new_audio_count(self, message):
        if self.new_audio_count_tracker is None:
            self.new_audio_count_tracker = NewAudioCountTracker()
        self.new_audio_count_tracker.send_message()

    def handle_stop_tracking_new_audio_count(self, message):
        if self.new_audio_count_tracker:
            self.new_audio_count_tracker.stop_tracking()
            self.new_audio_count_tracker = None

    def handle_track_unwatched_count(self, message):
        if self.unwatched_count_tracker is None:
            self.unwatched_count_tracker = UnwatchedCountTracker()
        self.unwatched_count_tracker.send_message()

    def handle_stop_tracking_unwatched_count(self, message):
        if self.unwatched_count_tracker:
            self.unwatched_count_tracker.stop_tracking()
            self.unwatched_count_tracker = None

    def handle_subscription_link_clicked(self, message):
        url = message.url
        subscriptions = subscription.find_subscribe_links(url)
        added, ignored = subscription.Subscriber().add_subscriptions(
            subscriptions)
        feeds = added.get('feed')
        # send a notification to the user
        if feeds:
            if len(feeds) == 1:
                title = _("Subscribed to new feed:")
                body = feeds[0].get('title', feeds[0]['url'])
            elif len(feeds) > 1:
                title = _('Subscribed to new feeds:')
                body = '\n'.join(
                    [' - %s' % feed.get('title', feed['url']) for feed in feeds])
            messages.NotifyUser(
                title, body, 'feed-subscribe').send_to_frontend()
        if 'download' in added or 'download' in ignored:
            messages.FeedlessDownloadStarted().send_to_frontend()

    def handle_change_movies_directory(self, message):
        old_path = config.get(prefs.MOVIES_DIRECTORY)
        config.set(prefs.MOVIES_DIRECTORY, message.path)
        if message.migrate:
            self._migrate(old_path, message.path)
        messages.UpdateFeed(feed.Feed.get_directory_feed().id).send_to_backend()

    def _migrate(self, old_path, new_path):
        to_migrate = list(downloader.RemoteDownloader.finished_view())
        migration_count = len(to_migrate)
        last_progress_time = 0
        for i, download in enumerate(to_migrate):
            current_time = time.time()
            if current_time > last_progress_time + 0.5:
                m = messages.MigrationProgress(i, migration_count, False)
                m.send_to_frontend()
                last_progress_time = current_time
            logging.info("migrating %s", download.get_filename())
            download.migrate(new_path)
        # Pass in case they don't exist or are not empty:
        # FIXME - these will never work since they're directory trees
        # and fileutil.rmdir calls os.rmdir which only removes non-empty
        # directories.
        try:
            fileutil.rmdir(os.path.join(old_path, 'Incomplete Downloads'))
        except OSError:
            pass
        try:
            fileutil.rmdir(old_path)
        except OSError:
            pass
        m = messages.MigrationProgress(migration_count, migration_count, True)
        m.send_to_frontend()

    def handle_report_crash(self, message):
        app.controller.send_bug_report(message.report, message.text,
                                       message.send_report)

    def _get_widgets_frontend_state(self):
        try:
            return WidgetsFrontendState.make_view().get_singleton()
        except database.ObjectNotFoundError:
            return WidgetsFrontendState()

    def handle_save_frontend_state(self, message):
        state = self._get_widgets_frontend_state()
        state.list_view_displays = message.list_view_displays
        state.sort_states = message.sort_states
        state.signal_change()

    def handle_query_frontend_state(self, message):
        state = self._get_widgets_frontend_state()
        messages.CurrentFrontendState(state.list_view_displays, state.sort_states).send_to_frontend()
