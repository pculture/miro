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

import copy
import logging
import time
import os

from miro import app
from miro import autoupdate
from miro import database
from miro import devices
from miro import conversions
from miro import downloader
from miro import eventloop
from miro import feed
from miro import guide
from miro import fileutil
from miro import commandline
from miro import item
from miro import itemsource
from miro import messages
from miro import filetypes
from miro import prefs
from miro import singleclick
from miro import subscription
from miro import tabs
from miro import opml
from miro.data.item import fetch_item_infos
from miro.widgetstate import DisplayState, ViewState, GlobalState
from miro.feed import Feed, lookup_feed
from miro.gtcache import gettext as _
from miro.playlist import SavedPlaylist
from miro.folder import HideableTab, FolderBase, ChannelFolder, PlaylistFolder

from miro.plat.utils import make_url_safe, filename_to_unicode

import shutil

class ViewTracker(object):
    """Handles tracking views for TrackGuides, TrackChannels, TrackPlaylists.
    """
    type = None
    info_factory = None

    def __init__(self):
        self.trackers = []
        self.add_callbacks()
        self.reset_changes()
        self.tabs_being_reordered = False
        self._last_sent_info = {}

    def reset_changes(self):
        self.changed = {}
        self.removed = set()
        self.added =  {}
        self.added_order = []
        # Need to use a list because added messages must be sent in the same
        # order they were received
        self.changes_pending = False

    def send_messages(self):
        message = self.make_changed_message(
                self._make_added_list(self._get_added_objects()),
                self._make_changed_list(self.changed.values()),
                self._make_removed_list(self.removed))
        if message.added or message.changed or message.removed:
            message.send_to_frontend()
        self.reset_changes()

    def _get_added_objects(self):
        """Get the objects in added in the order that we saw them."""
        return [obj for obj in self.added_order if obj.id in self.added]

    def make_changed_message(self, added, changed, removed):
        raise NotImplementedError()

    def _make_new_info(self, obj):
        info = self.info_factory(obj)
        self._last_sent_info[obj.id] = info
        return info

    def _make_added_list(self, *addeds):
        added_list = []
        for added in addeds:
            added_list.extend([self._make_new_info(obj) for obj in added])
        return added_list

    def _make_changed_list(self, changed):
        retval = []
        for obj in changed:
            info = self.info_factory(obj)
            if (obj.id not in self._last_sent_info or
                info.__dict__ != self._last_sent_info[obj.id].__dict__):
                retval.append(info)
                self._last_sent_info[obj.id] = info
        return retval

    def _make_removed_list(self, removed_set):
        for id_ in removed_set:
            del self._last_sent_info[id_]
        return list(removed_set)

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
        if obj.id in self.removed:
            # object was already removed, we need to send that message out
            # before we send the add message.
            self.send_messages()
        self.added[obj.id] = obj
        self.added_order.append(obj)
        self.schedule_send_messages()

    def on_object_removed(self, tracker, obj):
        self.on_object_id_removed(tracker, obj.id)

    def on_object_id_removed(self, tracker, id_):
        if self.tabs_being_reordered:
            # even though we're not sending messages, update _last_sent_info
            del self._last_sent_info[id_]
            return
        if id_ in self.added:
            # object added, then removed, just ignore it
            del self.added[id_]
        elif id_ in self.changed:
            # object changed, then removed, just send the removeal
            del self.changed[id_]
            self.removed.add(id_)
        else:
            self.removed.add(id_)
        self.schedule_send_messages()

    def on_object_changed(self, tracker, obj):
        # Don't pay attention to tabs_being_reordered here.  This lets us
        # update the new/unwatched counts when channels are added/removed from
        # folders (#10988)
        if obj.id in self.added:
            # object added, then changed, just send the addition
            self.added[obj.id] = obj
        else:
            self.changed[obj.id] = obj
        self.schedule_send_messages()

    def on_bulk_added(self, emitter, objects):
        for obj in objects:
            self.on_object_added(emitter, obj)

    def on_bulk_removed(self, emitter, objects):
        for obj in objects:
            self.on_object_id_removed(emitter, obj.id)

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
        root_view = HideableTab.make_view('type=?', (self.type,))
        try:
            root = root_view.get_singleton()
        except database.ObjectNotFoundError:
            root = HideableTab(self.type)
        response.root_expanded = root.get_expanded()
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
        return feed.Feed.visible_view(), ChannelFolder.make_view()

    def get_tab_order(self):
        return tabs.TabOrder.feed_order()

class PlaylistTracker(TabTracker):
    type = u'playlist'
    info_factory = messages.PlaylistInfo

    def get_object_views(self):
        return SavedPlaylist.make_view(), PlaylistFolder.make_view()

    def get_tab_order(self):
        return tabs.TabOrder.playlist_order()

class SimpleHideableTracker(ViewTracker):
    """Tracker for guides and stores - hideable tabs that aren't nestable."""
    info_factory = messages.GuideInfo

    def get_initial_views(self):
        return self.get_object_views()

    def make_changed_message(self, added, changed, removed):
        return messages.TabsChanged(self.type, added, changed, removed)

    def send_initial_list(self):
        info_list = self._make_added_list(*self.get_initial_views())
        message = self.list_message(info_list)
        root_view = HideableTab.make_view('type=?', (self.type,))
        try:
            root = root_view.get_singleton()
        except database.ObjectNotFoundError:
            root = HideableTab(self.type)
        message.root_expanded = root.get_expanded()
        message.send_to_frontend()
        self.reset_changes()

class GuideTracker(SimpleHideableTracker):
    type = 'site'
    list_message = messages.GuideList

    def get_object_views(self):
        return (guide.ChannelGuide.site_view(),)

    def get_initial_views(self):
        return (guide.ChannelGuide.site_view(), guide.ChannelGuide.guide_view())

class StoreTracker(SimpleHideableTracker):
    type = 'store'
    list_message = messages.StoreList

    def get_object_views(self):
        return (guide.ChannelGuide.visible_store_view(),)

    def get_initial_views(self):
        return (guide.ChannelGuide.store_view(),)

    def send_messages(self):
        message = messages.StoresChanged(
            [self.info_factory(g) for g in self._get_added_objects()],
            [self.info_factory(g) for g in self.changed.values()],
            frozenset(self.removed))
        message.send_to_frontend()

        ViewTracker.send_messages(self)

class WatchedFolderTracker(ViewTracker):
    info_factory = messages.WatchedFolderInfo

    def get_object_views(self):
        return (feed.Feed.watched_folder_view(),)

    def make_changed_message(self, added, changed, removed):
        return messages.WatchedFoldersChanged(added, changed, removed)

    def send_initial_list(self):
        info_list = self._make_added_list(feed.Feed.watched_folder_view())
        messages.WatchedFolderList(info_list).send_to_frontend()

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
        # XXX this had a TypeError for a while, so it seems unused
        CountTracker.stop_tracking(self)
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

class PreferencedCountTracker(CountTracker):
    def __init__(self):
        CountTracker.__init__(self)
        self.signal_handler = app.backend_config_watcher.connect(
            'changed', self.on_config_changed)

    def get_view(self):
        return self.view_func(app.config.get(self.pref))

    def stop_tracking(self):
        app.backend_config_watcher.disconnect(self.signal_handler)

    def on_config_changed(self, obj, key, value):
        if key == self.pref.key:
            CountTracker.stop_tracking(self)
            CountTracker.__init__(self)
            self.send_message()

class NewVideoCountTracker(PreferencedCountTracker):
    view_func = item.Item.unique_new_video_view
    pref = prefs.SHOW_PODCASTS_IN_VIDEO

    def make_message(self, count):
        return messages.NewVideoCountChanged(count)

class NewAudioCountTracker(PreferencedCountTracker):
    view_func = item.Item.unique_new_audio_view
    pref = prefs.SHOW_PODCASTS_IN_MUSIC

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
        self.playlist_tracker = None
        self.guide_tracker = None
        self.store_tracker = None
        self.watched_folder_tracker = None
        self.download_count_tracker = None
        self.paused_count_tracker = None
        self.others_count_tracker = None
        self.new_video_count_tracker = None
        self.new_audio_count_tracker = None
        self.unwatched_count_tracker = None
        search_feed = Feed.get_search_feed()
        search_feed.connect('update-finished', self._search_update_finished)

    def call_handler(self, method, message):
        name = 'handling backend message: %s' % message
        logging.debug("handling backend %s", message)
        eventloop.add_urgent_call(method, name, args=(message,))

    def folder_class_for_type(self, typ):
        if typ == 'feed':
            return ChannelFolder
        elif typ == 'playlist':
            return PlaylistFolder
        else:
            raise ValueError("Unknown Type: %s" % typ)

    def ddb_object_class_for_type(self, typ):
        if typ == 'feed':
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
        self.channel_tracker.send_initial_list()

    def handle_stop_tracking_channels(self, message):
        if self.channel_tracker:
            self.channel_tracker.unlink()
            self.channel_tracker = None

    def handle_track_guides(self, message):
        if not self.guide_tracker:
            self.guide_tracker = GuideTracker()
            self.store_tracker = StoreTracker()
        self.guide_tracker.send_initial_list()
        self.store_tracker.send_initial_list()

    def handle_stop_tracking_guides(self, message):
        if self.guide_tracker:
            self.guide_tracker.unlink()
            self.guide_tracker = None
            self.store_tracker.unlink()
            self.store_tracker = None

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

    def handle_track_share(self, message):
        app.sharing_tracker.track_share(message.share_id)

    def handle_stop_tracking_share(self, message):
        app.sharing_tracker.stop_tracking_share(message.share_id)

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
        itemsource.get_handler(message.info).mark_watched(message.info)

    def handle_set_items_watched(self, message):
        for info in message.info_list:
            if message.watched:
                itemsource.get_handler(info).mark_watched(info)
            else:
                itemsource.get_handler(info).mark_unwatched(info)

    def handle_mark_item_unwatched(self, message):
        itemsource.get_handler(message.info).mark_unwatched(message.info)

    def handle_mark_item_completed(self, message):
        itemsource.get_handler(message.info).mark_completed(message.info)

    def handle_mark_item_skipped(self, message):
        itemsource.get_handler(message.info).mark_skipped(message.info)

    def handle_set_item_is_playing(self, message):
        itemsource.get_handler(message.info).set_is_playing(message.info,
                message.is_playing)

    def handle_rate_item(self, message):
        itemsource.get_handler(message.info).set_rating(message.info,
                message.rating)

    def handle_set_item_subtitle_encoding(self, message):
        itemsource.get_handler(message.info).set_subtitle_encoding(
                message.info, message.encoding)

    def handle_set_item_resume_time(self, message):
        itemsource.get_handler(message.info).set_resume_time(message.info,
                message.resume_time)

    def handle_set_item_media_type(self, message):
        for id_ in message.video_ids:
            try:
                item_ = item.Item.get_by_id(id_)
            except database.ObjectNotFoundError:
                logging.warn("SetItemMediaType: Item not found -- %s", id_)
                continue
            item_.set_user_metadata({'file_type': message.media_type})

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
        item_ids = [i.id for i in item.Item.newly_downloaded_view()]
        item_infos = app.db.fetch_item_infos(item_ids)
        messages.PlayMovies(item_infos).send_to_frontend()

    def handle_tab_expanded_change(self, message):
        tab_view = HideableTab.make_view('type=?', (message.type,))
        try:
            tab = tab_view.get_singleton()
        except database.ObjectNotFoundError:
            tab = HideableTab(message.type)
        else:
            tab.set_expanded(message.expanded)

    def handle_folder_expanded_change(self, message):
        klass = self.folder_class_for_type(message.type)
        try:
            folder = klass.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("feed folder not found: %s",
                    repr((message.type, message.id)))
        else:
            folder.set_expanded(message.expanded)

    def handle_update_feed(self, message):
        try:
            feed_ = feed.Feed.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("feed not found: %s" % message.id)
        else:
            feed_.update()

    def handle_update_feed_folder(self, message):
        try:
            f = ChannelFolder.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("folder not found: %s" % message.id)
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
        try:
            self._do_handle_tabs_reordered(message)
        finally:
            if self.channel_tracker:
                self.channel_tracker.tabs_being_reordered = False

    def _do_handle_tabs_reordered(self, message):
        feed_order = tabs.TabOrder.feed_order()
        playlist_order = tabs.TabOrder.playlist_order()

        for info_type, info_list in message.toplevels.iteritems():
            folder_class = self.folder_class_for_type(info_type)

            if info_type == 'feed':
                child_class = feed.Feed
                tab_order = feed_order
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
            # NB: signal_change() is implicit
            tab_order.reorder(order)

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
        # signal_change() implicit in reorder()
        playlist.reorder(message.item_ids)

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
            Feed(url)

    def handle_new_feed_search_feed(self, message):
        search_term = message.search_term
        channel_info = message.channel_info
        url = channel_info.base_href

        if channel_info.search_term:
            search_term = search_term + " " + channel_info.search_term

        if not lookup_feed(url, search_term):
            Feed(url, search_term=search_term,
                    title=channel_info.name)

    def handle_new_feed_search_engine(self, message):
        sei = message.search_engine_info
        term = message.search_term

        url = feed.make_search_url(sei.name, term)

        if not lookup_feed(url):
            Feed(url)

    def handle_new_feed_search_url(self, message):
        url = message.url
        search_term = message.search_term

        normalized = feed.normalize_feed_url(url)

        if not lookup_feed(url, search_term):
            Feed(normalized, search_term=search_term)

    def handle_new_feed_folder(self, message):
        folder = ChannelFolder(message.name)

        if message.child_feed_ids is not None:
            for id_ in message.child_feed_ids:
                feed_ = feed.Feed.get_by_id(id_)
                feed_.set_folder(folder)
            tab_order = tabs.TabOrder.feed_order()
            tracker = self.channel_tracker
            # NB: no need to call signal_change() as move_tabs_after() does it
            tab_order.move_tabs_after(folder.id, message.child_feed_ids)
            tracker.send_whole_list = True
            messages.JettisonTabs(u'feed',
                message.child_feed_ids).send_to_frontend()

    def handle_new_watched_folder(self, message):
        url = u"dtv:directoryfeed:%s" % make_url_safe(message.path)
        if not lookup_feed(url):
            feed_ = feed.Feed(url)
            if message.visible is not None:
                feed_.set_visible(message.visible)
        else:
            logging.warning("Not adding duplicated watched folder: %s",
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
            for id_ in message.child_playlist_ids:
                playlist = SavedPlaylist.get_by_id(id_)
                playlist.set_folder(folder)
            tab_order = tabs.TabOrder.playlist_order()
            # NB: no need to call signal_change() as move_tabs_after() does it.
            tab_order.move_tabs_after(folder.id, message.child_playlist_ids)
            self.playlist_tracker.send_whole_list = True
            messages.JettisonTabs(u'playlist',
                message.child_playlist_ids).send_to_frontend()

    def handle_add_videos_to_playlist(self, message):
        try:
            playlist = SavedPlaylist.get_by_id(message.playlist_id)
        except database.ObjectNotFoundError:
            logging.warn("AddVideosToPlaylist: Playlist not found -- %s",
                    message.playlist_id)
            return
        for id_ in message.video_ids:
            try:
                item_ = item.Item.get_by_id(id_)
            except database.ObjectNotFoundError:
                logging.warn("AddVideosToPlaylist: Item not found -- %s", id_)
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
        if message.type != 'manual':
            return (message.type, message.id)
        else:
            # make sure the item list is a tuple, so it can be hashed.
            return (message.type, tuple(message.id))

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
        app.download_state_manager.set_bulk_mode()
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
        app.download_state_manager.set_bulk_mode()
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
        app.download_state_manager.set_bulk_mode()
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

    def handle_set_media_kind(self, message):
        item_infos = message.item_infos
        kind = message.kind
        logging.debug('KIND = %s', kind)
        items = []
        for i in item_infos:
            try:
                items.append(item.Item.get_by_id(i.id))
            except database.ObjectNotFoundError:
                logging.warn("SetMediaKind: Item not found -- %s", i.id)
        app.bulk_sql_manager.start()
        try:
            for i in items:
                i.set_user_metadata({u'kind': kind})
        finally:
            app.bulk_sql_manager.finish()
        
    def handle_save_item_as(self, message):
        try:
            item_ = item.Item.get_by_id(message.id)
        except database.ObjectNotFoundError:
            logging.warn("SaveVideoAs: Item not found -- %s", message.id)
            return

        logging.debug("saving video %s to %s", item_.get_filename(),
                      message.filename)


        try:
            if fileutil.samefile(item_.get_filename(), message.filename):
                return # saving over the same file
        except EnvironmentError:
            # just try to write the file anyways
            pass

        try:
            shutil.copyfile(item_.get_filename(), message.filename)
        except EnvironmentError, e:
            # XXX is there a more useful error message we can show the user?
            messages.ShowWarning(
                _("Error saving file"),
                _("There was an error saving %(filename)s: %(error)s", {
                        'filename': message.filename,
                        'error': e.strerror})).send_to_frontend()

    def handle_remove_video_entries(self, message):
        items = []
        for info in message.info_list:
            try:
                items.append(item.Item.get_by_id(info.id))
            except database.ObjectNotFoundError:
                logging.warn("RemoveVideoEntries: Item not found -- %s",
                        info.id)
        app.bulk_sql_manager.start()
        try:
            for item_ in items:
                item_.expire()
        finally:
            app.bulk_sql_manager.finish()

    def handle_delete_videos(self, message):
        # group the ItemInfos by their handler
        infos_per_handler = {}
        for info in message.info_list:
            handler = itemsource.get_handler(info)
            infos_per_handler.setdefault(handler, []).append(info)
        # for each handler, call bulk_delete()
        for handler, info_list in infos_per_handler.iteritems():
            handler.bulk_delete(info_list)

    def handle_edit_items(self, message):
        changes = message.change_dict
        for id_ in message.item_ids:
            try:
                item_ = item.Item.get_by_id(id_)
            except database.ObjectNotFoundError:
                logging.warn("EditItems: Item not found -- %s", id_)
                continue
            # ItemInfo uses "name", but the metadata system uses "title" now
            if 'name' in changes:
                changes['title'] = changes.pop('name')
            item_.set_user_metadata(changes)

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
                title = _("Subscribed to new podcast:")
                body = feeds[0].get('title', feeds[0]['url'])
            elif len(feeds) > 1:
                title = _('Subscribed to new podcasts:')
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
        app.local_metadata_manager.will_move_files([d.get_filename() for d in
                                                    to_migrate])
        for i, download in enumerate(to_migrate):
            current_time = time.time()
            if current_time > last_progress_time + 0.5:
                text = '%s (%s/%s)' % (title, i, migration_count)
                progress = float(i) / migration_count
                messages.ProgressDialog(text, progress).send_to_frontend()
                last_progress_time = current_time
            logging.debug("migrating %s", download.get_filename())
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
        key_view = DisplayState.make_view("type=? AND id_=?", key)
        if key_view.count() == 1:
            return key_view.get_singleton()
        else:
            return DisplayState(key)

    def _get_view_state(self, key):
        key_view = ViewState.make_view(
                   "display_type=? AND display_id=? AND view_type=?", key)
        if key_view.count() == 1:
            return key_view.get_singleton()
        else:
            return ViewState(key)

    def handle_save_display_state(self, message):
        info = message.display_info
        state = self._get_display_state(info.key)
        state.selected_view = info.selected_view
        state.shuffle = info.shuffle
        state.repeat = info.repeat
        state.selection = info.selection
        state.sort_state = info.sort_state
        if isinstance(info.last_played_item_id, (int, long)):
            state.last_played_item_id = info.last_played_item_id
        else:
            # don't save device/share items, since they might not be there next
            # time
            state.last_played_item_id = None
        # shallow-copy attributes that store lists, dicts, and sets so
        # that changing the DisplayInfo doesn't change the database object
        state.active_filters = copy.copy(info.active_filters)
        state.signal_change()

    def handle_save_view_state(self, message):
        info = message.view_info
        state = self._get_view_state(info.key)
        state.scroll_position = info.scroll_position
        state.columns_enabled = copy.copy(info.columns_enabled)
        state.column_widths = copy.copy(info.column_widths)
        state.signal_change()

    def handle_save_global_state(self, message):
        info = message.info
        state = GlobalState.get_singleton()
        state.item_details_expanded = info.item_details_expanded
        state.guide_sidebar_expanded = info.guide_sidebar_expanded
        state.tabs_width = int(info.tabs_width)
        state.signal_change()

    def _get_display_states(self):
        states = []
        for display in DisplayState.make_view():
            key = (display.type, display.id_)
            display_info = messages.DisplayInfo(key, display)
            states.append(display_info)
        return states
        
    def _get_view_states(self):
        states = []
        for view in ViewState.make_view():
            key = (view.display_type, view.display_id, view.view_type)
            view_info = messages.ViewInfo(key, view)
            states.append(view_info)
        return states

    def handle_query_display_states(self, message):
        states = self._get_display_states()
        m = messages.CurrentDisplayStates(states)
        m.send_to_frontend()

    def handle_query_view_states(self, message):
        states = self._get_view_states()
        m = messages.CurrentViewStates(states)
        m.send_to_frontend()

    def handle_query_global_state(self, message):
        info = messages.GlobalInfo(GlobalState.get_singleton())
        m = messages.CurrentGlobalState(info)
        m.send_to_frontend()

    def handle_set_device_type(self, message):
        message.device.database[u'device_name'] = message.name
        app.device_manager.device_changed(message.device.id,
                                          name=message.device.name,
                                          device_name=message.name,
                                          mount=message.device.mount,
                                          size=message.device.size,
                                          remaining=message.device.remaining)

    def handle_save_device_sort(self, message):
        db_entry = u'%s_sort_state' % message.tab_type
        message.device.database[db_entry] = (message.key, message.ascending)

    def handle_save_device_view(self, message):
        message.device.database[u'%s_view' % message.tab_type] = message.view

    def handle_change_device_sync_setting(self, message):
        db = message.device.database
        if message.file_type:
            this_sync = db[u'sync'].setdefault(message.file_type, {})
        else:
            this_sync = db[u'sync']
        if not isinstance(message.setting, (tuple, list)):
            settings = [message.setting]
        else:
            settings = list(message.setting)
        while len(settings) > 1:
            this_sync = this_sync.setdefault(settings.pop(0), {})
        this_sync[settings[0]] = message.value

    def handle_change_device_setting(self, message):
        app.device_manager.change_setting(message.device, message.setting,
                                          message.value)

    def handle_device_eject(self, message):
        app.device_manager.eject_device(message.device)

    def handle_query_sync_information(self, message):
        dsm = app.device_manager.get_sync_for_device(message.device)
        dsm.query_sync_information()

    def handle_device_sync_feeds(self, message):
        dsm = app.device_manager.get_sync_for_device(message.device)
        if hasattr(dsm, 'last_sync_info'):
            infos, expired, count, size = dsm.last_sync_info
            del dsm.last_sync_info
        else:
            infos, expired = dsm.get_sync_items(dsm.max_sync_size())
            count, size = dsm.get_sync_size(infos, expired)

        if size > dsm.max_sync_size():
            return

        if infos or expired:
            if expired:
                dsm.expire_items(expired)
            without_auto = dsm.max_sync_size(include_auto=False)
            if size > without_auto:
                dsm.expire_auto_items(size - without_auto)
            if infos:
                dsm.start()
                dsm.add_items(infos)
                if size < without_auto:
                    remaining = dsm.max_sync_size() - size
                    auto_items = dsm.get_auto_items(remaining)
                    if auto_items:
                        dsm.add_items(auto_items, auto_sync=True)
            else:
                message = messages.CurrentSyncInformation(message.device,
                                                          0, 0)
                message.send_to_frontend()

    def handle_device_sync_media(self, message):
        try:
            item_infos = fetch_item_infos(app.db.connection,
                                          message.item_ids)
        except database.ObjectNotFoundError:
            logging.warn("HandleDeviceSyncMedia: Items not found -- %s",
                         message.item_ids)
            return

        dsm = app.device_manager.get_sync_for_device(message.device)
        count, size = dsm.get_sync_size(item_infos)

        if size > dsm.max_sync_size():
            return

        dsm.start()
        dsm.add_items(item_infos)

    def handle_cancel_device_sync(self, message):
        dsm = app.device_manager.get_sync_for_device(message.device,
                                                     create=False)
        if dsm:
            dsm.cancel()

    def handle_download_sharing_items(self, message):
        from miro.singleclick import _build_entry, download_video

        for item_info in message.item_infos:
            # notes:
            # For sharing item the URL is encoded directory into the path.
            url = item_info.filename.urlize().decode('utf-8', 'replace')
            file_format = '.' + item_info.file_format
            try:
                # So many to choose from ... let's just pick the first one.
                content_type = filetypes.EXT_MIMETYPES_MAP[file_format][0]
            except KeyError:
                content_type = 'audio/unknown'
            additional = {
                'title': item_info.title,
                'description': item_info.description,
            }
            entry = _build_entry(url, content_type, additional=additional)
            download_video(entry)

    def handle_download_device_items(self, message):
        manual_feed = Feed.get_manual_feed()
        video_directory = app.config.get(prefs.MOVIES_DIRECTORY)

        for item_info in message.item_infos:
            final_path = os.path.join(video_directory,
                                      os.path.basename(item_info.filename))
            view = item.Item.make_view('is_file_item AND filename=?',
                                       (filename_to_unicode(final_path),))
            if view.count(): # file already exists
                continue
            shutil.copyfile(item_info.filename, final_path)
            fp_values = item.fp_values_for_file(final_path,
                                                item_info.title,
                                                item_info.description)
            fi = item.FileItem(final_path, feed_id=manual_feed.id,
                               fp_values=fp_values)
            fi.release_date = item_info.release_date
            fi.duration = item_info.duration
            fi.permalink = item_info.permalink
            if item_info.comments_link:
                fi.comments_link = item_info.comments_link
            if item_info.payment_link:
                fi.payment_link = item_info.payment_link
            #fi.screenshot = item_info.thumbnail
            if item_info.thumbnail_url:
                fi.thumbnail_url = item_info.thumbnail_url
            fi.file_format = item_info.file_format
            fi.license = item_info.license
            fi.mime_type = item_info.mime_type
            fi.creation_time = item_info.date_added
            fi.artist = item_info.artist
            fi.album = item_info.album
            fi.track = item_info.track
            fi.year = item_info.year
            fi.genre = item_info.genre
            fi.signal_change()

    def handle_clog_backend(self, message):
        logging.debug('handle_clog_backend: Backend snoozing for %d seconds.  '
                      'ZZZZZZ.', message.n)
        time.sleep(message.n)
        logging.debug('handle_clog_backend: Backend out of snooze.  Yawn!')

    def handle_force_feedparser_processing(self, message):
        # For all our RSS feeds, force an update
        for f in feed.Feed.make_view():
            if isinstance(f.actualFeed, feed.RSSFeedImpl):
                f.actualFeed.etag = f.actualFeed.modified = None
                f.actualFeed.signal_change()
                f.update()
            elif isinstance(f.actualFeed, feed.RSSMultiFeedBase):
                f.actualFeed.etag = {}
                f.actualFeed.modified = {}
                f.actualFeed.signal_change()
                f.update()

    def handle_force_dbsave_error(self, message):
        app.db.simulate_db_save_error()

    def handle_force_device_dbsave_error(self, message):
        app.device_manager.force_db_save_error(message.device_info)

    def handle_set_net_lookup_enabled(self, message):
        paths = set()
        if message.item_ids is None:
            app.local_metadata_manager.set_net_lookup_enabled_for_all(
                message.enabled)
            return

        for item_id in message.item_ids:
            try:
                i = item.Item.get_by_id(item_id)
            except database.ObjectNotFoundError:
                logging.warn("handle_force_run_echonest: id not found: %s",
                             item_id)
            else:
                paths.add(i.get_filename())
        # Remove any None values in case an item didn't have a path
        paths.discard(None)
        app.local_metadata_manager.set_net_lookup_enabled(paths,
                                                          message.enabled)

    def handle_remove_echonest_data(self, message):
        paths = set()
        for item_id in message.item_ids:
            try:
                i = item.Item.get_by_id(item_id)
            except database.ObjectNotFoundError:
                logging.warn("handle_force_run_echonest: id not found: %s",
                             item_id)
            else:
                paths.append(i.get_filename())
        # Remove any None values in case an item didn't have a path
        paths.discard(None)
        app.local_metadata_manager.remove_echonest_data(paths)
