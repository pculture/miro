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

"""messagehandler.py -- Backend message handler"""

import logging

from miro import database
from miro import eventloop
from miro import feed
from miro import guide
from miro import httpclient
from miro import indexes
from miro import messages
from miro import singleclick
from miro import subscription
from miro import views
from miro import opml
from miro.feed import Feed, getFeedByURL
from miro.playlist import SavedPlaylist
from miro.folder import FolderBase, ChannelFolder, PlaylistFolder
from miro.util import getSingletonDDBObject

import shutil

class ViewTracker(object):
    """Handles tracking views for TrackGuides, TrackChannels, TrackPlaylist and TrackItems."""

    def __init__(self):
        self.add_callbacks()
        self.reset_changes()

    def reset_changes(self):
        self.changed = set()
        self.removed = set()
        self.added =  []
        # Need to use a list because added messages must be sent in the same
        # order they were receieved
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
                [self.InfoClass(obj) for obj in self.added],
                [self.InfoClass(obj) for obj in self.changed],
                [obj.id for obj in self.removed])
        message.send_to_frontend()
        self.reset_changes()

    def schedule_send_messages(self):
        # We don't send messages immediately so that if an object gets changed
        # multiple times, only one callback gets sent.
        if not self.changes_pending:
            eventloop.addUrgentCall(self.send_messages, 'view tracker update' )
            self.changes_pending = True

    def add_callbacks(self):
        for view in self.get_object_views():
            view.addAddCallback(self.on_object_added)
            view.addRemoveCallback(self.on_object_removed)
            view.addChangeCallback(self.on_object_changed)

    def remove_callbacks(self):
        for view in self.get_object_views():
            view.removeAddCallback(self.on_object_added)
            view.removeRemoveCallback(self.on_object_removed)
            view.removeChangeCallback(self.on_object_changed)

    def on_object_added(self, obj, id):
        if obj in self.removed:
            # object was already removed, we need to send that message out
            # before we send the add message.
            self.send_messages()
        self.added.append(obj)
        self.schedule_send_messages()

    def on_object_removed(self, obj, id):
        self.removed.add(obj)
        self.schedule_send_messages()

    def on_object_changed(self, obj, id):
        self.changed.add(obj)
        self.schedule_send_messages()

    def unlink(self):
        self.remove_callbacks()

class TabTracker(ViewTracker):
    def make_changed_message(self, added, changed, removed):
        return messages.TabsChanged(self.type, added, changed, removed)

    def add_callbacks(self):
        for view in self.get_object_views():
            view.addAddCallback(self.on_object_added)
            view.addRemoveCallback(self.on_object_removed)
            view.addChangeCallback(self.on_object_changed)

    def remove_callbacks(self):
        for view in self.get_object_views():
            view.removeAddCallback(self.on_object_added)
            view.removeRemoveCallback(self.on_object_removed)
            view.removeChangeCallback(self.on_object_changed)

    def send_initial_list(self):
        response = messages.TabList(self.type)
        current_folder_id = None
        for tab in self.get_tab_view():
            info = self.InfoClass(tab.obj)
            if tab.obj.getFolder() is None:
                response.append(info)
                if isinstance(tab.obj, FolderBase):
                    current_folder_id = tab.objID()
                    if tab.obj.getExpanded():
                        response.expand_folder(tab.objID())
                else:
                    current_folder_id = None
            else:
                if (current_folder_id is None or 
                        tab.obj.getFolder().id != current_folder_id):
                    raise AssertionError("Tab ordering is wrong")
                response.append_child(current_folder_id, info)
        response.send_to_frontend()

class ChannelTracker(TabTracker):
    type = 'feed'
    InfoClass = messages.ChannelInfo

    def get_object_views(self):
        return views.visibleFeeds, views.channelFolders

    def get_tab_view(self):
        return getSingletonDDBObject(views.channelTabOrder).getView()

class PlaylistTracker(TabTracker):
    type = 'playlist'
    InfoClass = messages.PlaylistInfo

    def get_object_views(self):
        return views.playlists, views.playlistFolders

    def get_tab_view(self):
        return getSingletonDDBObject(views.playlistTabOrder).getView()

class GuideTracker(ViewTracker):
    InfoClass = messages.GuideInfo

    def get_object_views(self):
        return [views.guides]

    def make_changed_message(self, added, changed, removed):
        return messages.TabsChanged('guide', added, changed, removed)

    def send_initial_list(self):
        info_list = [messages.GuideInfo(g) for g in views.guides]
        messages.GuideList(info_list).send_to_frontend()

class ItemTrackerBase(ViewTracker):
    InfoClass = messages.ItemInfo

    def make_changed_message(self, added, changed, removed):
        return messages.ItemsChanged(self.feed_id, added, changed, removed)

    def get_object_views(self):
        return [self.view]

    def send_initial_list(self):
        messages.ItemList(self.feed_id, self.view).send_to_frontend()

class FeedItemTracker(ItemTrackerBase):
    def __init__(self, feed):
        self.view = feed.items
        self.feed_id = feed.id
        ItemTrackerBase.__init__(self)

class FolderItemTracker(ItemTrackerBase):
    def __init__(self, folder):
        self.view = views.items.filterWithIndex(indexes.itemsByChannelFolder, 
                folder)
        self.feed_id = folder.id
        ItemTrackerBase.__init__(self)

    def unlink(self):
        ItemTrackerBase.unlink(self)
        self.view.unlink()

class DownloadingItemsTracker(ItemTrackerBase):
    def __init__(self):
        self.view = views.downloadingItems
        self.feed_id = messages.TrackItemsForFeed.DOWNLOADING
        ItemTrackerBase.__init__(self)

class NewItemsTracker(ItemTrackerBase):
    def __init__(self):
        self.view = views.uniqueNewWatchableItems
        self.feed_id = messages.TrackItemsForFeed.NEW
        ItemTrackerBase.__init__(self)

class LibraryItemsTracker(ItemTrackerBase):
    def __init__(self):
        self.view = views.uniqueWatchableItems
        self.feed_id = messages.TrackItemsForFeed.LIBRARY
        ItemTrackerBase.__init__(self)

def make_item_tracker(message):
    if message.feed_id == messages.TrackItemsForFeed.DOWNLOADING:
        return DownloadingItemsTracker()
    elif message.feed_id == messages.TrackItemsForFeed.NEW:
        return NewItemsTracker()
    elif message.feed_id == messages.TrackItemsForFeed.LIBRARY:
        return LibraryItemsTracker()
    try:
        feed = views.feeds.getObjectByID(message.feed_id)
        return FeedItemTracker(feed)
    except database.ObjectNotFoundError:
        folder = views.channelFolders.getObjectByID(message.feed_id)
        return FolderItemTracker(folder)

class CountTracker(object):
    """Tracks downloads count or new videos count"""
    def __init__(self):
        self.view = self.get_view()
        self.view.addAddCallback(self.on_count_changed)
        self.view.addRemoveCallback(self.on_count_changed)

    def on_count_changed(self, obj, id):
        self.send_message()

    def send_message(self):
        self.make_message(len(self.view)).send_to_frontend()

    def stop_tracking(self):
        self.view.removeAddCallback(self.on_count_changed)
        self.view.removeRemoveCallback(self.on_count_changed)

class DownloadCountTracker(CountTracker):
    def get_view(self):
        return views.downloadingItems

    def make_message(self, count):
        return messages.DownloadCountChanged(count)

class NewCountTracker(CountTracker):
    def get_view(self):
        return views.uniqueNewWatchableItems

    def make_message(self, count):
        return messages.NewCountChanged(count)

class BackendMessageHandler(messages.MessageHandler):
    def __init__(self):
        messages.MessageHandler.__init__(self)
        self.channel_tracker = None
        self.playlist_tracker = None
        self.guide_tracker = None
        self.download_count_tracker = None
        self.new_count_tracker = None
        self.item_trackers = {}

    def call_handler(self, method, message):
        name = 'handling backend message: %s' % message
        eventloop.addUrgentCall(method, name, args=(message,))

    def folder_view_for_type(self, type):
        if type == 'feed':
            return views.channelFolders
        elif type == 'playlist':
            return views.playlistFolders
        else:
            raise ValueError("Unknown Type: %s" % type)

    def view_for_type(self, type):
        if type == 'feed':
            return views.visibleFeeds
        elif type == 'playlist':
            return views.playlists
        elif type == 'feed-folder':
            return views.channelFolders
        elif type == 'playlist-folder':
            return views.playlistFolders
        elif type == 'site':
            return views.guides
        else:
            raise ValueError("Unknown Type: %s" % type)

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
        self.guide_tracker.send_initial_list()

    def handle_stop_tracking_guides(self, message):
        if self.guide_tracker:
            self.guide_tracker.unlink()
            self.guide_tracker = None

    def handle_track_playlists(self, message):
        if not self.playlist_tracker:
            self.playlist_tracker = PlaylistTracker()
        self.playlist_tracker.send_initial_list()

    def handle_stop_tracking_playlists(self, message):
        if self.playlist_tracker:
            self.playlist_tracker.unlink()
            self.playlist_tracker = None

    def handle_mark_channel_seen(self, message):
        feed = database.defaultDatabase.getObjectByID(message.id)
        feed.markAsViewed()

    def handle_mark_item_watched(self, message):
        item = views.items.getObjectByID(message.id)
        item.markItemSeen()

    def handle_mark_item_unwatched(self, message):
        item = views.items.getObjectByID(message.id)
        item.markItemUnseen()

    def handle_import_channels(self, message):
        opml.Importer().importSubscriptionsFrom(message.filename)

    def handle_export_channels(self, message):
        opml.Exporter().exportSubscriptionsTo(message.filename)

    def handle_rename_object(self, message):
        view = self.view_for_type(message.type)
        try:
            obj = view.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("object not found (type: %s, id: %s)" % 
                    (message.type, message.id))
        else:
            obj.setTitle(message.new_name)

    def handle_folder_expanded_change(self, message):
        folder_view = self.folder_view_for_type(message.type)
        try:
            folder = folder_view.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("channel folder not found")
        else:
            folder.setExpanded(message.expanded)

    def handle_update_channel(self, message):
        view = views.visibleFeeds
        try:
            feed = view.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("feed not found: %s" % id)
        else:
            feed.update()

    def handle_update_all_channels(self, message):
        for f in views.feeds:
            f.scheduleUpdateEvents(0)

    def handle_delete_channel(self, message):
        if message.is_folder:
            view = views.channelFolders
        else:
            view = views.visibleFeeds
        try:
            channel = view.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("channel not found: %s" % id)
        else:
            if message.keep_items:
                move_to = getSingletonDDBObject(views.manualFeed)
            else:
                move_to = None
            channel.remove(move_to)

    def handle_delete_playlist(self, message):
        if message.is_folder:
            view = views.playlistFolders
        else:
            view = views.playlists
        try:
            playlist = view.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("playlist not found: %s" % message.id)
        else:
            playlist.remove()

    def handle_delete_site(self, message):
        site = views.guides.getObjectByID(message.id)
        if site.getDefault():
            raise ValueError("Can't delete default site")
        site.remove()

    def handle_tabs_reordered(self, message):
        folder_view = self.folder_view_for_type(message.type)
        if message.type == 'feed':
            item_view = views.visibleFeeds
            tab_order = getSingletonDDBObject(views.channelTabOrder)
        elif message.type == 'playlist':
            item_view = views.playlists
            tab_order = getSingletonDDBObject(views.playlistTabOrder)
        else:
            raise ValueError("Unknown Type: %s" % message.type)

        order = []
        for info in message.toplevels:
            order.append(info.id)
            if info.is_folder:
                folder = folder_view.getObjectByID(info.id)
                for child_info in message.folder_children[info.id]:
                    child_id = child_info.id
                    order.append(child_id)
                    feed = item_view.getObjectByID(child_id)
                    feed.setFolder(folder)
            else:
                feed = item_view.getObjectByID(info.id)
                feed.setFolder(None)
        tab_order.tab_ids = order
        tab_order.signalChange()

    def handle_new_guide(self, message):
        url = message.url
        if guide.getGuideByURL(url) is None:
            guide.ChannelGuide(url, [u'*'])

    def handle_new_channel(self, message):
        url = message.url
        if not getFeedByURL(url):
            Feed(url)
            if message.trackback:
                httpclient.grabURL(message.trackback, 
                        lambda x: None, lambda x: None)

    def handle_new_channel_folder(self, message):
        ChannelFolder(message.name)

    def handle_new_playlist(self, message):
        name = message.name
        ids = message.ids
        if not ids:
            ids = None
        SavedPlaylist(name, ids)

    def handle_download_url(self, message):
        singleclick.addDownload(message.url)

    def handle_new_playlist_folder(self, message):
        PlaylistFolder(message.name)

    def handle_track_items_for_feed(self, message):
        if message.feed_id not in self.item_trackers:
            item_tracker = make_item_tracker(message)
            self.item_trackers[message.feed_id] = item_tracker
        else:
            item_tracker = self.item_trackers[message.feed_id]
        item_tracker.send_initial_list()

    def handle_stop_tracking_items_for_feed(self, message):
        try:
            item_tracker = self.item_trackers.pop(message.feed_id)
        except KeyError:
            logging.warn("Item tracker not found (id: %s)", message.feed_id)
        else:
            item_tracker.unlink()

    def handle_start_download(self, message):
        try:
            item = views.items.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("StartDownload: Item not found -- %s", message.id)
        else:
            item.download()

    def handle_cancel_download(self, message):
        try:
            item = views.items.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("CancelDownload: Item not found -- %s", message.id)
        else:
            item.executeExpire()

    def handle_pause_download(self, message):
        try:
            item = views.downloadingItems.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("PauseDownload: Item not found -- %s", message.id)
        else:
            item.pause()

    def handle_resume_download(self, message):
        try:
            item = views.items.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("ResumeDownload: Item not found -- %s", message.id)
        else:
            item.resume()

    def handle_restart_upload(self, message):
        try:
            item = views.items.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("ResumeDownload: Item not found -- %s", message.id)
        else:
            if item.downloader.getType() != 'bittorrent':
                logging.warn("%s is not a torrent", item)
            elif item.downloader.state == 'uploading':
                logging.warn("%s is currently uploading", item)
            else:
                item.startUpload()

    def handle_keep_video(self, message):
        try:
            item = views.items.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("KeepVideo: Item not found -- %s", message.id)
        else:
            item.save()

    def handle_save_item_as(self, message):
        try:
            item = views.items.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("SaveVideoAs: Item not found -- %s", message.id)
        else:
            logging.info("saving video %s to %s" % (item.getVideoFilename(), 
                                                    message.filename))
            try:
                shutil.copyfile(item.getVideoFilename(), message.filename)
            except IOError:
                # FIXME - we should pass the error back to the frontend
                pass

    def handle_remove_video_entry(self, message):
        try:
            item = views.items.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("RemoveVideoEntry: Item not found -- %s", message.id)
        else:
            item.executeExpire()

    def handle_delete_video(self, message):
        try:
            item = views.items.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("DeleteVideo: Item not found -- %s", message.id)
        else:
            item.deleteFiles()
            item.executeExpire()

    def handle_rename_video(self, message):
        try:
            item = views.items.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("RenameVideo: Item not found -- %s", message.id)
        else:
            item.setTitle(message.new_name)

    def handle_autodownload_change(self, message):
        try:
            feed = views.feeds.getObjectByID(message.id)
        except database.ObjectNotFoundError:
            logging.warn("AutodownloadChange: Feed not found -- %s", message.id)
        else:
            feed.setAutoDownloadMode(message.setting)

    def handle_track_download_count(self, message):
        if self.download_count_tracker is None:
            self.download_count_tracker = DownloadCountTracker()
        self.download_count_tracker.send_message()

    def handle_stop_tracking_download_count(self, message):
        if self.download_count_tracker:
            self.download_count_tracker.stop_tracking()
            self.download_count_tracker = None

    def handle_track_new_count(self, message):
        if self.new_count_tracker is None:
            self.new_count_tracker = NewCountTracker()
        self.new_count_tracker.send_message()

    def handle_stop_tracking_new_count(self, message):
        if self.new_count_tracker:
            self.new_count_tracker.stop_tracking()
            self.new_count_tracker = None

    def handle_subscription_link_clicked(self, message):
        url = message.url
        type, subscribeURLs = subscription.findSubscribeLinks(url)
        normalizedURLs = []
        for url, additional in subscribeURLs:
            normalized = feed.normalizeFeedURL(url)
            if feed.validateFeedURL(normalized):
                normalizedURLs.append((normalized, additional))
        if normalizedURLs:
            if type == 'feed':
                for url, additional in normalizedURLs:
                    feed.Feed(url)
                    if 'trackback' in additional:
                        httpclient.grabURL(additional['trackback'],
                                           lambda x: None,
                                           lambda x: None)
            elif type == 'download':
                for url, additional in normalizedURLs:
                    singleclick.addDownload(url, additional)
            elif type == 'guide':
                for url, additional in normalizedURLs:
                    if guide.getGuideByURL (url) is None:
                        guide.ChannelGuide(url, [u'*'])
            else:
                raise AssertionError("Unknown subscribe type")
