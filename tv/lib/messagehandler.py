# Miro - an RSS based video player application
# Copyright (C) 2005, 2006, 2007, 2008, 2009, 2010, 2011
# Participatory Culture Foundation
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

import itertools
import logging
import time
import threading
import os

import libdaap

from miro import app
from miro import autoupdate
from miro import database
from miro import devices
from miro import downloader
from miro import eventloop
from miro import feed
from miro.displaystate import DisplayState
from miro import guide
from miro import fileutil
from miro import commandline
from miro import item
from miro import itemsource
from miro import messages
from miro import prefs
from miro import search
from miro import singleclick
from miro import subscription
from miro import tabs
from miro import opml
from miro.feed import Feed, lookup_feed
from miro.gtcache import gettext as _
from miro.playlist import SavedPlaylist
from miro.folder import FolderBase, ChannelFolder, PlaylistFolder

from miro.plat.utils import make_url_safe, thread_body

import shutil

class ViewTracker(object):
    """Handles tracking views for TrackGuides, TrackChannels, TrackPlaylist and
    TrackItems."""
    type = None
    info_factory = None

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

    def make_changed_message(self, added, changed, removed):
        raise NotImplementedError()

    def _make_new_info(self, obj):
        info = self.info_factory(obj)
        self._last_sent_info[obj.id] = info
        return info

    def _make_added_list(self, added):
        return [self._make_new_info(obj) for obj in added]

    def _make_changed_list(self, changed):
        retval = []
        for obj in changed:
            info = self.info_factory(obj)
            if (obj.id not in self._last_sent_info or
                info.__dict__ != self._last_sent_info[obj.id].__dict__):
                retval.append(info)
                self._last_sent_info[obj.id] = info
        return retval

    def _make_removed_list(self, removed):
        for obj in removed:
            del self._last_sent_info[obj.id]
        return [obj.id for obj in removed]

    def schedule_send_messages(self):
        # We don't send messages immediately so that if an object gets changed
        # multiple times, only one callback gets sent.
        if not self.changes_pending:
            eventloop.add_urgent_call(self.send_messages,
                                      'view tracker update' )
            self.changes_pending = True

    def add_callbacks(self):
        for view in self.get_object_views():
            tracker = view.make_tracker()
            tracker.set_bulk_mode(True)
            tracker.connect('added', self.on_object_added)
            tracker.connect('removed', self.on_object_removed)
            tracker.connect('changed', self.on_object_changed)
            tracker.connect('bulk-added', self.on_bulk_added)
            tracker.connect('bulk-removed', self.on_bulk_removed)
            tracker.connect('bulk-changed', self.on_bulk_changed)
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

    def on_bulk_added(self, emitter, objects):
        for obj in objects:
            self.on_object_added(emitter, obj)

    def on_bulk_removed(self, emitter, objects):
        for obj in objects:
            self.on_object_removed(emitter, obj)

    def on_bulk_changed(self, emitter, objects):
        for obj in objects:
            self.on_object_changed(emitter, obj)

    def unlink(self):
        for tracker in self.trackers:
            tracker.unlink()

class TabTracker(ViewTracker):
    def __init__(self):
        ViewTracker.__init__(self)
        self.send_whole_list = False

    def get_tab_order(self):
        raise NotImplementedError()

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
                    if obj.get_expanded():
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
    type = u'feed'
    info_factory = messages.ChannelInfo

    def get_object_views(self):
        return feed.Feed.visible_video_view(), ChannelFolder.video_view()

    def get_tab_order(self):
        return tabs.TabOrder.video_feed_order()

class AudioChannelTracker(TabTracker):
    type = u'audio-feed'
    info_factory = messages.ChannelInfo

    def get_object_views(self):
        return feed.Feed.visible_audio_view(), ChannelFolder.audio_view()

    def get_tab_order(self):
        return tabs.TabOrder.audio_feed_order()

class PlaylistTracker(TabTracker):
    type = u'playlist'
    info_factory = messages.PlaylistInfo

    def get_object_views(self):
        return SavedPlaylist.make_view(), PlaylistFolder.make_view()

    def get_tab_order(self):
        return tabs.TabOrder.playlist_order()

class GuideTracker(ViewTracker):
    info_factory = messages.GuideInfo

    def get_object_views(self):
        return [guide.ChannelGuide.make_view()]

    def make_changed_message(self, added, changed, removed):
        return messages.TabsChanged('guide', added, changed, removed)

    def send_messages(self):
        message = messages.GuidesChanged(
            [self.info_factory(g) for g in self.added],
            [self.info_factory(g) for g in self.changed],
            [g.id for g in self.removed])
        message.send_to_frontend()

        # now that we've sent the GuidesChanged message, fix the changed
        # message for the hidden flag
        changed, self.changed = self.changed, set()
        for obj in changed:
            is_visible = obj.is_visible()
            if obj.id in self._last_sent_info:
                was_visible = self._last_sent_info[obj.id].visible
            else:
                was_visible = False
            if is_visible and not was_visible: # newly shown
                self.added.append(obj)
            elif not is_visible and was_visible: # newly hidden
                self.removed.add(obj)
            else:
                self.changed.add(obj)
        ViewTracker.send_messages(self)

    def send_initial_list(self):
        info_list = self._make_added_list(guide.ChannelGuide.make_view())
        messages.GuideList(info_list).send_to_frontend()

class WatchedFolderTracker(ViewTracker):
    info_factory = messages.WatchedFolderInfo

    def get_object_views(self):
        return (feed.Feed.watched_folder_view(),)

    def make_changed_message(self, added, changed, removed):
        return messages.WatchedFoldersChanged(added, changed, removed)

    def send_initial_list(self):
        info_list = self._make_added_list(feed.Feed.watched_folder_view())
        messages.WatchedFolderList(info_list).send_to_frontend()

class ItemSearchLimiter(itemsource.SourceLimiter):
    """ViewLimiter that filters out items that don't match a search query"""
    def __init__(self, query):
        self.query = query

    def filter_info(self, info):
        return not search.item_matches(info, self.query)

    def filter_list(self, info_list):
        return search.list_matches(info_list, self.query)

class SourceTrackerBase(ViewTracker):
    # we only deal with ItemInfo objects, so we don't need to create anything
    info_factory = lambda self, info: info

    def __init__(self, search_text):
        ViewTracker.__init__(self)
        self.current_search_text = self.last_search_text = search_text
        self.sent_initial_list = False
        if search_text:
            for source in self.trackers:
                source.set_limiter(ItemSearchLimiter(search_text))

    def get_sources(self):
        return [self.source]

    def add_callbacks(self):
        for source in self.get_sources():
            source.connect('added', self.on_object_added)
            source.connect('changed', self.on_object_changed)
            source.connect('removed', self.on_object_removed)
            source.connect('new-list', self.on_new_list)
            self.trackers.append(source)

    def on_new_list(self, source, infos):
        if not self.sent_initial_list:
            # don't send this until we send ItemList()
            return
        # XXX is it faster to just re-send the initial list?
        current_infos = {}
        for info in infos:
            if info.id not in self._last_sent_info:
                self.on_object_added(source, info)
            else:
                current_infos[info.id] = info
        for info in self._last_sent_info.values():
            if info.id in current_infos:
                self.on_object_changed(source, current_infos[info.id])
            else:
                self.on_object_removed(source, info)
        self.schedule_send_messages()

    def send_initial_list(self):
        infos = []
        for source in self.trackers:
            infos.extend(source.fetch())
        self._last_sent_info.update([(info.id, info) for info in infos])
        messages.ItemList(self.type, self.id, infos).send_to_frontend()
        self.sent_initial_list = True

    def make_changed_message(self, added, changed, removed):
        return messages.ItemsChanged(self.type, self.id, added, changed,
                                     removed)

    def send_messages(self):
        if self.current_search_text != self.last_search_text:
            self._update_search()

        ViewTracker.send_messages(self)

    def _update_search(self):
        if not self.current_search_text:
            limiter = None
        else:
            limiter = ItemSearchLimiter(self.current_search_text)
        for source in self.trackers:
            source.set_limiter(limiter)
        self.last_search_text = self.current_search_text

    def set_search_text(self, search_text):
        # don't change the search yet, schedule it in an urgent call.  That
        # way if we get tons of search changes at once, we can skip to the
        # last one.
        self.current_search_text = search_text
        self.schedule_send_messages()

class DatabaseSourceTrackerBase(SourceTrackerBase):

    def get_sources(self):
        return [itemsource.DatabaseItemSource(view) for view in
                self.get_object_views()]

    def get_object_views(self):
        return [self.view]

class FeedItemTracker(DatabaseSourceTrackerBase):
    type = u'feed'
    def __init__(self, feed, search_text):
        self.view = feed.visible_items
        self.id = feed.id
        DatabaseSourceTrackerBase.__init__(self, search_text)

class FeedFolderItemTracker(DatabaseSourceTrackerBase):
    type = u'feed'
    def __init__(self, folder, search_text):
        self.view = item.Item.visible_folder_view(folder.id)
        self.id = folder.id
        DatabaseSourceTrackerBase.__init__(self, search_text)

class PlaylistItemTracker(DatabaseSourceTrackerBase):
    type = u'playlist'
    def __init__(self, playlist, search_text):
        self.view = item.Item.playlist_view(playlist.id)
        self.id = playlist.id
        DatabaseSourceTrackerBase.__init__(self, search_text)

class PlaylistFolderItemTracker(DatabaseSourceTrackerBase):
    type = u'playlist'
    def __init__(self, playlist, search_text):
        self.view = item.Item.playlist_folder_view(playlist.id)
        self.id = playlist.id
        DatabaseSourceTrackerBase.__init__(self, search_text)

class ManualItemTracker(DatabaseSourceTrackerBase):
    type = u'manual'

    def __init__(self, id_, id_list, search_text):
        self.id = id_
        # SQLite can only handle 999 variables at once.  If there are more ids
        # than that, we need to split things up (#12020)
        self.views = []
        for pos in xrange(0, len(id_list), 950):
            bite_sized_list = id_list[pos:pos+950]
            place_holders = ', '.join('?' for i in xrange(
                    len(bite_sized_list)))
            self.views.append(item.Item.make_view(
                'id in (%s)' % place_holders, tuple(bite_sized_list)))
        DatabaseSourceTrackerBase.__init__(self, search_text)

    def get_object_views(self):
        return self.views

class DownloadingItemsTracker(DatabaseSourceTrackerBase):
    type = u'downloading'
    id = u'downloading'
    def __init__(self, search_text):
        self.view = item.Item.download_tab_view()
        DatabaseSourceTrackerBase.__init__(self, search_text)

class SharingBackendItemsTracker(DatabaseSourceTrackerBase):
    type = u'sharing-backend'
    id = u'sharing-backend'
    def __init__(self, search_text):
        self.view = item.Item.watchable_view()
        DatabaseSourceTrackerBase.__init__(self, search_text)

class VideoItemsTracker(DatabaseSourceTrackerBase):
    type = u'videos'
    id = u'videos'
    def __init__(self, search_text):
        self.view = item.Item.watchable_video_view()
        DatabaseSourceTrackerBase.__init__(self, search_text)

class AudioItemsTracker(DatabaseSourceTrackerBase):
    type = u'music'
    id = u'music'
    def __init__(self, search_text):
        self.view = item.Item.watchable_audio_view()
        DatabaseSourceTrackerBase.__init__(self, search_text)

class OtherItemsTracker(DatabaseSourceTrackerBase):
    type = u'others'
    id = u'others'
    def __init__(self, search_text):
        self.view = item.Item.watchable_other_view()
        DatabaseSourceTrackerBase.__init__(self, search_text)

class SearchItemsTracker(DatabaseSourceTrackerBase):
    type = u'search'
    id = u'search'
    def __init__(self, search_text):
        self.view = item.Item.search_item_view()
        DatabaseSourceTrackerBase.__init__(self, search_text)

class FolderItemsTracker(DatabaseSourceTrackerBase):
    type = u'folder-contents'
    def __init__(self, folder_id, search_text):
        self.view = item.Item.folder_contents_view(folder_id)
        self.id = folder_id
        DatabaseSourceTrackerBase.__init__(self, search_text)

class SharingItemTracker(SourceTrackerBase):
    type = u'sharing'
    def __init__(self, share, search_text):
        share_id = share.parent_id if share.parent_id else share.id
        self.id = share
        self.tracker = app.sharing_tracker.get_tracker(share_id)
        self.source = itemsource.SharingItemSource(self.tracker,
                                                   share.playlist_id)

        SourceTrackerBase.__init__(self, search_text)

class DeviceItemTracker(SourceTrackerBase):
    type = u'device'
    def __init__(self, device, search_text):
        self.device = device
        self.id = device.id
        self.source = itemsource.DeviceItemSource(device)

        SourceTrackerBase.__init__(self, search_text)

def make_item_tracker(message):
    if message.type == 'downloading':
        return DownloadingItemsTracker(message.search_text)
    elif message.type == 'videos':
        return VideoItemsTracker(message.search_text)
    elif message.type == 'music':
        return AudioItemsTracker(message.search_text)
    elif message.type == 'others':
        return OtherItemsTracker(message.search_text)
    elif message.type == 'search':
        return SearchItemsTracker(message.search_text)
    elif message.type == 'folder-contents':
        return FolderItemsTracker(message.id, message.search_text)
    elif message.type == 'feed':
        try:
            feed_ = feed.Feed.get_by_id(message.id)
            return FeedItemTracker(feed_, message.search_text)
        except database.ObjectNotFoundError:
            folder = ChannelFolder.get_by_id(message.id)
            return FeedFolderItemTracker(folder, message.search_text)
    elif message.type == 'playlist':
        try:
            playlist = SavedPlaylist.get_by_id(message.id)
            return PlaylistItemTracker(playlist, message.search_text)
        except database.ObjectNotFoundError:
            playlist = PlaylistFolder.get_by_id(message.id)
            return PlaylistFolderItemTracker(playlist, message.search_text)
    elif message.type == 'manual':
        return ManualItemTracker(message.id, message.ids_to_track,
                message.search_text)
    elif message.type == 'device':
        return DeviceItemTracker(message.id, message.search_text)
    elif message.type == 'sharing':
        return SharingItemTracker(message.id, message.search_text)
    elif message.type == 'sharing-backend':
        return SharingBackendItemsTracker(message.search_text)
    else:
        logging.warn("Unknown TrackItems type: %s", message.type)

class CountTracker(object):
    """Tracks downloads count or new videos count"""
    def __init__(self):
        self.tracker = self.get_view().make_tracker()
        self.tracker.connect('added', self.on_count_changed)
        self.tracker.connect('removed', self.on_count_changed)

    def get_view(self):
        raise NotImplementedError()

    def make_message(self, count):
        raise NotImplementedError()

    def on_count_changed(self, tracker, obj):
        self.send_message()

    def send_message(self):
        self.make_message(len(self.tracker)).send_to_frontend()

    def stop_tracking(self):
        self.tracker.unlink()

class DownloadCountTracker(CountTracker):
    def __init__(self):
        CountTracker.__init__(self)
        # we need to also track the only_downloading_view since if something
        # gets added/removed from that the total count stays the same, but the
        # downloading count changes (#14677)
        self.other_tracker = item.Item.only_downloading_view().make_tracker()
        self.other_tracker.connect('added', self.on_count_changed)
        self.other_tracker.connect('removed', self.on_count_changed)

    def get_view(self):
        return item.Item.download_tab_view()

    def make_message(self, total_count):
        # total_count includes non-downloading items like seeding torrents.
        # We need to split this into separate counts for the frontend
        downloading_count = len(self.other_tracker)
        non_downloading_count = total_count - downloading_count
        return messages.DownloadCountChanged(downloading_count,
                non_downloading_count)

    def stop_tracking(self):
        CountTracker.stop_tracking()
        self.other_tracker.unlink()

class PausedCountTracker(CountTracker):
    def get_view(self):
        return item.Item.paused_view()

    def make_message(self, count):
        return messages.PausedCountChanged(count)

class OthersCountTracker(CountTracker):
    def get_view(self):
        return item.Item.unique_others_view()

    def make_message(self, count):
        return messages.OthersCountChanged(count)

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
        self.others_count_tracker = None
        self.new_video_count_tracker = None
        self.new_audio_count_tracker = None
        self.unwatched_count_tracker = None
        self.item_trackers = {}
        search_feed = Feed.get_search_feed()
        search_feed.connect('update-finished', self._search_update_finished)

    def call_handler(self, method, message):
        name = 'handling backend message: %s' % message
        logging.debug("handling backend %s", message)
        eventloop.add_urgent_call(method, name, args=(message,))

    def folder_class_for_type(self, typ):
        if typ in ('feed', 'audio-feed'):
            return ChannelFolder
        elif typ == 'playlist':
            return PlaylistFolder
        else:
            raise ValueError("Unknown Type: %s" % typ)

    def ddb_object_class_for_type(self, typ):
        if typ == 'feed':
            return feed.Feed
        elif typ == 'audio-feed':
            return feed.Feed
        elif typ == 'playlist':
            return SavedPlaylist
        elif typ == 'feed-folder':
            return ChannelFolder
        elif typ == 'playlist-folder':
            return PlaylistFolder
        elif typ == 'site':
            return guide.ChannelGuide
        else:
            raise ValueError("Unknown Type: %s" % typ)

    def handle_frontend_started(self, message):
        # add a little bit more delay to let things simmer down a bit.  The
        # calls here are low-priority, so we can afford to wait a bit.
        eventloop.add_timeout(2, self.frontend_startup_callback,
                'frontend startup callback')

    def handle_query_search_info(self, message):
        search_feed = Feed.get_search_feed()
        messages.CurrentSearchInfo(search_feed.engine,
                search_feed.query).send_to_frontend()

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

    def handle_track_sharing(self, message):
        app.sharing_tracker.start_tracking()

    def handle_stop_tracking_sharing(self, message):
        pass

    def handle_sharing_eject(self, message):
        app.sharing_tracker.eject(message.share.id)

    def handle_track_devices(self, message):
        app.device_tracker.start_tracking()

    def handle_mark_feed_seen(self, message):
        try:
            try:
                feed_ = feed.Feed.get_by_id(message.id)
            except database.ObjectNotFoundError:
                feed_ = ChannelFolder.get_by_id(message.id)
            feed_.mark_as_viewed()
        except database.ObjectNotFoundError:
            logging.warning("handle_mark_feed_seen: can't find feed by id %s",
                            message.id)

    def handle_mark_item_watched(self, message):
        message.info.source.mark_watched(message.info)

    def handle_mark_item_unwatched(self, message):
        message.info.source.mark_unwatched(message.info)

    def handle_mark_item_completed(self, message):
        message.info.source.mark_completed(message.info)

    def handle_mark_item_skipped(self, message):
        message.info.source.mark_skipped(message.info)

    def handle_set_item_is_playing(self, message):
        message.info.source.set_is_playing(message.info, message.is_playing)

    def handle_rate_item(self, message):
        message.info.source.set_rating(message.info, message.rating)

    def handle_set_item_subtitle_encoding(self, message):
        message.info.source.set_subtitle_encoding(message.info,
                                                  message.encoding)

    def handle_set_item_resume_time(self, message):
        message.info.source.set_resume_time(message.info, message.resume_time)

    def handle_set_item_media_type(self, message):
        for id_ in message.video_ids:
            try:
                item_ = item.Item.get_by_id(id_)
            except database.ObjectNotFoundError:
                logging.warn("SetItemMediaType: Item not found -- %s", id_)
                continue
            item_.set_file_type(message.media_type)

    def handle_set_feed_expire(self, message):
        channel_info = message.channel_info
        expire_type = message.expire_type
        expire_time = message.expire_time

        try:
            channel = feed.Feed.get_by_id(channel_info.id)
            if expire_type == "never":
                channel.set_expiration(u"never", 0)
            elif expire_type == "system":
                channel.set_expiration(u"system", expire_time)
            else:
                channel.set_expiration(u"feed", expire_time)

        except database.ObjectNotFoundError:
            logging.warning("handle_set_feed_expire: can't find feed by id %s",
                            channel_info.id)

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
            logging.warning(
                "handle_set_feed_max_new: can't find feed by id %s",
                channel_info.id)

    def handle_set_feed_max_old_items(self, message):
        channel_info = message.channel_info
        max_old_items = message.max_old_items

        try:
            channel = feed.Feed.get_by_id(channel_info.id)
            channel.set_max_old_items(max_old_items)

        except database.ObjectNotFoundError:
            logging.warning(
                "handle_set_feed_max_new: can't find feed by id %s",
                channel_info.id)

    def handle_clean_feed(self, message):
        channel_id = message.channel_id
        try:
            obj = feed.Feed.get_by_id(channel_id)
        except database.ObjectNotFoundError:
            logging.warn("handle_clean_feed: object not found id: %s",
                         channel_id)
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
        item_infos = itemsource.DatabaseSource(
            item.Item.newly_downloaded_view()).fetch()
        messages.PlayMovie(item_infos).send_to_frontend()

    def handle_folder_expanded_change(self, message):
        klass = self.folder_class_for_type(message.type)
        try:
            folder = klass.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("feed folder not found")
        else:
            folder.set_expanded(message.expanded)

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
            for feed in f.get_children_view():
                feed.schedule_update_events(0)

    def handle_update_all_feeds(self, message):
        for f in feed.Feed.make_view():
            f.schedule_update_events(0)

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
            if site.is_default():
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
            logging.warn(
                """PlaylistReordered: Not all ids present in the new order
Original Ids: %s
New ids: %s""", playlist_item_ids, message.item_ids)
            return
        playlist.reorder(message.item_ids)
        playlist.signal_change()

    def handle_new_guide(self, message):
        url = message.url
        if guide.get_guide_by_url(url) is None:
            guide.ChannelGuide(url, [u'*'])

    def handle_set_guide_visible(self, message):
        g = guide.ChannelGuide.get_by_id(message.id)
        if not g.store:
            return
        if message.visible:
            g.store = g.STORE_VISIBLE
        else:
            g.store = g.STORE_INVISIBLE
        g.signal_change()

    def handle_new_feed(self, message):
        url = message.url
        if not lookup_feed(url):
            Feed(url, section=message.section)

    def handle_new_feed_search_feed(self, message):
        search_term = message.search_term
        channel_info = message.channel_info
        section = message.section
        url = channel_info.base_href

        if channel_info.search_term:
            search_term = search_term + " " + channel_info.search_term

        if not lookup_feed(url, search_term):
            Feed(url, section=section, search_term=search_term,
                    title=channel_info.name)

    def handle_new_feed_search_engine(self, message):
        sei = message.search_engine_info
        term = message.search_term
        section = message.section

        url = feed.make_search_url(sei.name, term)

        if not lookup_feed(url):
            Feed(url, section=section)

    def handle_new_feed_search_url(self, message):
        url = message.url
        search_term = message.search_term
        section = message.section

        normalized = feed.normalize_feed_url(url)

        if not lookup_feed(url, search_term):
            Feed(normalized, section=section, search_term=search_term)

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
        url = u"dtv:directoryfeed:%s" % make_url_safe(message.path)
        if not lookup_feed(url):
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
            feed_.set_visible(message.visible)

    def handle_new_playlist(self, message):
        name = message.name
        ids = message.ids
        if not ids:
            ids = None
        SavedPlaylist(name, ids)

    def handle_download_url(self, message):
        singleclick.add_download(message.url, message.handle_unknown_callback,
                                 message.metadata)

    def handle_open_individual_file(self, message):
        commandline.parse_command_line_args([message.filename])

    def handle_open_individual_files(self, message):
        commandline.parse_command_line_args(message.filenames)

    def handle_add_files(self, message):
        # exclude blank or None values
        good_files = [f for f in message.filenames if f]
        # add all files to Miro in the manualFeed
        commandline.add_videos(good_files)

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
                playlists = list(SavedPlaylist.folder_view(
                        message.playlist_id))
            except database.ObjectNotFoundError:
                logging.warn(
                    "RemoveVideosFromPlaylist: playlist not found -- %s",
                    message.playlist_id)
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

        search_feed = Feed.get_search_feed()
        search_downloads_feed = Feed.get_search_downloads_feed()

        search_feed.preserve_downloads(search_downloads_feed)
        if terms:
            search_feed.lookup(searchengine_id, terms)
        else:
            search_feed.reset(searchengine_id)

    def _search_update_finished(self, feed):
        messages.SearchComplete(feed.engine, feed.query,
                feed.items.count()).send_to_frontend()

    def item_tracker_key(self, message):
        if message.type == 'device':
            return (message.type, message.id.id)
        elif message.type != 'manual':
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

    def handle_set_track_items_search(self, message):
        key = self.item_tracker_key(message)
        try:
            item_tracker = self.item_trackers[key]
        except KeyError:
            logging.warn("SetTrackItemsSearch key not being tracked: %s", key)
            return
        item_tracker.set_search_text(message.search_text)

    def handle_stop_tracking_items(self, message):
        key = self.item_tracker_key(message)
        try:
            item_tracker = self.item_trackers.pop(key)
        except KeyError:
            logging.warn("Item tracker not found (id: %s)", message.id)
        else:
            item_tracker.unlink()

    def handle_cancel_auto_download(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("CancelAutoDownload: Item not found -- %s",
                         message.id)
        else:
            item_.cancel_auto_download()

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
                item_.pause_upload()
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
                item_.start_upload()
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
            logging.warn("handle_start_upload: Item not found -- %s",
                         message.id)
        else:
            if item_.parent_id is not None:
                # use the parent torrent file
                item_ = item_.get_parent()
            if item_.downloader.get_type() != 'bittorrent':
                logging.warn("%s is not a torrent", item_)
            elif item_.is_uploading():
                logging.warn("%s is already uploading", item_)
            else:
                item_.start_upload()

    def handle_stop_upload(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("handle_stop_upload: Item not found -- %s",
                         message.id)
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
        message.info.source.delete(message.info)

    def handle_rename_video(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("RenameVideo: Item not found -- %s", message.id)
        else:
            item_.set_title(message.new_name)

    def handle_edit_item(self, message):
        try:
            item_ = item.Item.get_by_id(message.item_id)
        except database.ObjectNotFoundError:
            logging.warn("EditItem: Item not found -- %s", message.item_id)
            return
        change_dict = message.change_dict

        if "name" in change_dict:
            item_.set_title(change_dict["name"])

        if "description" in change_dict:
            item_.set_description(change_dict["description"])

        if "file_type" in change_dict:
            item_.set_file_type(change_dict["file_type"])

    def handle_revert_feed_title(self, message):
        try:
            feed_object = feed.Feed.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("RevertFeedTitle: Feed not found -- %s", message.id)
        else:
            feed_object.revert_title()

    def handle_autodownload_change(self, message):
        try:
            feed_ = feed.Feed.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("AutodownloadChange: Feed not found -- %s",
                         message.id)
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

    def handle_track_others_count(self, message):
        if self.others_count_tracker is None:
            self.others_count_tracker = OthersCountTracker()
        self.others_count_tracker.send_message()

    def handle_stop_tracking_others_count(self, message):
        if self.others_count_tracker:
            self.others_count_tracker.stop_tracking()
            self.others_count_tracker = None

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
                    [' - %s' % feed.get('title', feed['url'])
                     for feed in feeds])
            messages.NotifyUser(
                title, body, 'feed-subscribe').send_to_frontend()
        if 'download' in added or 'download' in ignored:
            messages.FeedlessDownloadStarted().send_to_frontend()

    def handle_change_movies_directory(self, message):
        old_path = app.config.get(prefs.MOVIES_DIRECTORY)
        app.config.set(prefs.MOVIES_DIRECTORY, message.path)
        if message.migrate:
            self._migrate(old_path, message.path)
        message = messages.UpdateFeed(feed.Feed.get_directory_feed().id)
        message.send_to_backend()

    def _migrate(self, old_path, new_path):
        to_migrate = list(downloader.RemoteDownloader.finished_view())
        migration_count = len(to_migrate)
        last_progress_time = 0
        title = _('Migrating Files')
        messages.ProgressDialogStart(title).send_to_frontend()
        for i, download in enumerate(to_migrate):
            current_time = time.time()
            if current_time > last_progress_time + 0.5:
                text = '%s (%s/%s)' % (title, i, migration_count)
                progress = float(i) / migration_count
                messages.ProgressDialog(text, progress).send_to_frontend()
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
        m = messages.ProgressDialogFinished()
        m.send_to_frontend()

    def handle_report_crash(self, message):
        app.controller.send_bug_report(message.report, message.text,
                                       message.send_report)

    def _get_display_state(self, key):
        try:
            return DisplayState.make_view("type=? AND id_=?",
                key).get_singleton()
        # XXX FIXME
        except database.ObjectNotFoundError:
            return DisplayState(key)

    def handle_save_display_state(self, message):
        info = message.display_info
        state = self._get_display_state(info.key)
        state.is_list_view = info.is_list_view
        state.active_filters = info.active_filters
        state.sort_state = info.sort_state
        state.columns_enabled = info.columns_enabled
        state.column_widths = info.column_widths
        state.signal_change()
        
    def _get_display_states(self):
        states = []
        for display in DisplayState.make_view():
            key = (display.type, display.id_)
            display_info = messages.DisplayInfo(key, display)
            states.append(display_info)
        return states

    def handle_query_display_states(self, message):
        states = self._get_display_states()
        m = messages.CurrentDisplayStates(states)
        m.send_to_frontend()

    def handle_set_device_type(self, message):
        message.device.database['device_name'] = message.name
        app.device_manager.device_changed(message.device.id,
                                          name=message.name,
                                          mount=message.device.mount,
                                          size=message.device.size,
                                          remaining=message.device.remaining)

    def handle_device_eject(self, message):
        devices.write_database(message.device.database, message.device.mount)
        app.device_tracker.eject(message.device)

    @staticmethod
    def _get_sync_items_for_message(message):
        views = []
        infos = set()
        for video_id in message.video_ids:
            feed_ = feed.Feed.get_by_id(video_id)
            if message.video_type == 'all':
                view = feed_.downloaded_items
            else:
                view = feed_.unwatched_items
            views.append(view)

        for audio_id in message.audio_ids:
            feed_ = feed.Feed.get_by_id(audio_id)
            if message.audio_type == 'all':
                view = feed_.downloaded_items
            else:
                view = feed_.unwatched_items
            views.append(view)

        for playlist_id in message.playlist_ids:
            views.append(item.Item.playlist_view(playlist_id))

        for view in views:
            source = itemsource.DatabaseItemSource(view)
            try:
                infos.update(source.fetch())
            finally:
                source.unlink()
        return infos

    def handle_query_sync_information(self, message):
        infos = self._get_sync_items_for_message(message)
        video_count = sum(1 for info in infos if info.file_type == 'video')
        audio_count = sum(1 for info in infos if info.file_type == 'audio')
        message = messages.CurrentSyncInformation(message.device,
                                                  video_count,
                                                  audio_count)
        message.send_to_frontend()

    def handle_device_sync_feeds(self, message):
        infos = self._get_sync_items_for_message(message)
        if infos:
            dsm = app.device_manager.get_sync_for_device(message.device)
            dsm.add_items(infos)

    def handle_device_sync_media(self, message):
        try:
            item_infos = [itemsource.DatabaseItemSource.get_by_id(id_)
                          for id_ in message.item_ids]
        except database.ObjectNotFoundError:
            logging.warn("HandleDeviceSyncMedia: Items not found -- %s",
                         message.item_ids)
            return

        dsm = app.device_manager.get_sync_for_device(message.device)
        dsm.add_items(item_infos)
