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

"""``miro.messages`` -- Message passing between the frontend thread and the
backend thread.

The backend thread is the eventloop, which processes things like feed
updates and handles reading and writing to the database.  The frontend
thread is the thread of the UI toolkit we're using.  Communication
between the two threads is handled by passing messages between the
two.  These messages are handled asynchronously.

This module defines the messages that are passed between the two threads.
"""

import copy
import logging

from miro.gtcache import gettext as _
from miro.messagetools import Message, MessageHandler
from miro.plat import resources
from miro import app
from miro import displaytext
from miro import models
from miro import guide
from miro import search
from miro import prefs
from miro import util

class BackendMessage(Message):
    """Base class for Messages that get sent to the backend.
    """
    def send_to_backend(self):
        try:
            handler = self.handler
        except AttributeError:
            logging.warn("No handler for backend messages")
        else:
            handler.handle(self)

class FrontendMessage(Message):
    """Base class for Messages that get sent to the frontend.
    """
    def send_to_frontend(self):
        try:
            handler = self.handler
        except AttributeError:
            logging.warn("No handler for frontend messages")
        else:
            handler.handle(self)

# Backend Messages

class FrontendStarted(BackendMessage):
    """Inform the backend that the frontend has finished starting up.
    """
    pass

class TrackChannels(BackendMessage):
    """Begin tracking channels.

    After this message is sent, the backend will send back a ChannelList
    message, then it will send ChannelsChanged messages whenever the channel
    list changes.
    """
    pass

class StopTrackingChannels(BackendMessage):
    """Stop tracking channels.
    """
    pass

class QuerySearchInfo(BackendMessage):
    """Ask the backend to send a CurrentSearchInfo message.
    """
    pass

class TrackPlaylists(BackendMessage):
    """Begin tracking playlists.

    After this message is sent, the backend will send back a PlaylistList
    message, then it will send PlaylistsChanged messages whenever the list of
    playlists changes.
    """
    pass

class StopTrackingPlaylists(BackendMessage):
    """Stop tracking playlists.
    """
    pass

class TrackGuides(BackendMessage):
    """Begin tracking guides.

    After this message is sent, the backend will send back a GuideList
    message, then it will send GuidesChanged messages whenever the guide
    list changes.
    """
    pass

class StopTrackingGuides(BackendMessage):
    """Stop tracking guides.
    """
    pass

class TrackDownloadCount(BackendMessage):
    """Start tracking the number of downloading items.  After this message is
    received the backend will send a corresponding DownloadCountChanged
    message.  It will also send DownloadCountChanged whenever the count
    changes.
    """
    pass

class StopTrackingDownloadCount(BackendMessage):
    """Stop tracking the download count.
    """
    pass

class TrackPausedCount(BackendMessage):
    """Start tracking the number of paused downloading items.  After
    this message is received, the backend will send a corresponding
    PausedCountChanged message.  It will also send PausedCountChanged
    whenever the count changes.
    """
    pass

class StopTrackingPausedCount(BackendMessage):
    """Stop tracking the paused count."""
    pass

class TrackOthersCount(BackendMessage):
    """Start tracking the number of 'other' items.  When this message is
    received the backend will send a corresponding
    OthersCountChanged message.  It will also send
    OthersCountChanged whenever the count changes.
    """
    pass

class StopTrackingOthersCount(BackendMessage):
    """Stop tracking the 'other' count.
    """
    pass

class TrackNewVideoCount(BackendMessage):
    """Start tracking the number of new videos.  When this message is
    received the backend will send a corresponding
    NewVideoCountChanged message.  It will also send
    NewVideoCountChanged whenever the count changes.
    """
    pass

class StopTrackingNewVideoCount(BackendMessage):
    """Stop tracking the new videos count.
    """
    pass

class TrackNewAudioCount(BackendMessage):
    """Start tracking the number of new audio items.  When this
    message is received the backend will send a corresponding
    NewAudioCountChanged message.  It will also send
    NewAudioCountChanged whenever the count changes.
    """
    pass

class StopTrackingNewAudioCount(BackendMessage):
    """Stop tracking the new audio items count.
    """
    pass

class TrackUnwatchedCount(BackendMessage):
    """Start tracking the number of unwatched items.  When this
    message is received, the backend will send a corresponding
    UnwatchedCountChanged message.  It will also send
    UnwatchedCountChanged whenever the count changes.
    """
    pass

class StopTrackingUnwatchedCount(BackendMessage):
    """Stop tracking the unwatched items count.
    """
    pass

class TrackWatchedFolders(BackendMessage):
    """Begin tracking watched folders

    After this message is sent, the backend will send back a
    WatchedFolderList message, then it will send WatchedFoldersChanged
    messages whenever the list changes.
    """
    pass

class StopTrackingWatchedFolders(BackendMessage):
    """Stop tracking watched folders.
    """
    pass

class TrackShare(BackendMessage):
    """Start tracking a media share
    """
    def __init__(self, share_id):
        self.share_id = share_id

class StopTrackingShare(BackendMessage):
    """Stop tracking a media share
    """
    def __init__(self, share_id):
        self.share_id = share_id

class SetFeedExpire(BackendMessage):
    """Sets the expiration for a feed.
    """
    def __init__(self, channel_info, expire_type, expire_time):
        self.channel_info = channel_info
        self.expire_type = expire_type
        self.expire_time = expire_time

class SetFeedMaxNew(BackendMessage):
    """Sets the feed's max new property.
    """
    def __init__(self, channel_info, max_new):
        self.channel_info = channel_info
        self.max_new = max_new

class SetFeedMaxOldItems(BackendMessage):
    """Sets the feed's max old items property.
    """
    def __init__(self, channel_info, max_old_items):
        self.channel_info = channel_info
        self.max_old_items = max_old_items

class CleanFeed(BackendMessage):
    """Tells the backend to clean the old items from a feed.
    """
    def __init__(self, channel_id):
        self.channel_id = channel_id

class ImportFeeds(BackendMessage):
    """Tell the backend to import feeds from an .opml file.

    :param filename: file name that exists
    """
    def __init__(self, filename):
        self.filename = filename

class ExportSubscriptions(BackendMessage):
    """Tell the backend to export subscriptions to an .opml file.

    :param filename: file name to export to
    """
    def __init__(self, filename):
        self.filename = filename

class RenameObject(BackendMessage):
    """Tell the backend to rename a feed/playlist/folder.
    
    :param type: ``feed``, ``playlist``, ``feed-folder`` or
                 ``playlist-folder``
    :param id: id of the object to rename
    :param new_name: new name for the object
    """
    def __init__(self, typ, id_, new_name):
        self.type = typ
        self.id = id_
        self.new_name = util.to_uni(new_name)

class UpdateFeed(BackendMessage):
    """Updates a feed.
    """
    def __init__(self, id_):
        self.id = id_

class UpdateFeedFolder(BackendMessage):
    """Updates the feeds in a feed folder.
    """
    def __init__(self, id_):
        self.id = id_

class MarkFeedSeen(BackendMessage):
    """Mark a feed as seen.
    """
    def __init__(self, id_):
        self.id = id_

class MarkItemWatched(BackendMessage):
    """Mark an item as watched.
    """
    def __init__(self, info):
        self.info = info

class MarkItemUnwatched(BackendMessage):
    """Mark an item as unwatched.
    """
    def __init__(self, info):
        self.info = info

class SetItemsWatched(BackendMessage):
    """Set whether an iterable of items is watched.
    """
    def __init__(self, info_list, watched):
        self.info_list = info_list
        self.watched = watched

class MarkItemCompleted(BackendMessage):
    def __init__(self, info):
        self.info = info

class MarkItemSkipped(BackendMessage):
    def __init__(self, info):
        self.info = info

class SetItemIsPlaying(BackendMessage):
    """Set when an item begins playing; unset when it stops.
    """
    def __init__(self, info, is_playing):
        self.info = info
        self.is_playing = is_playing

class SetItemSubtitleEncoding(BackendMessage):
    """Mark an item as watched.
    """
    def __init__(self, info, encoding):
        self.info = info
        self.encoding = encoding

class SetItemResumeTime(BackendMessage):
    """Set an item resume time.
    """
    def __init__(self, info, time):
        self.info = info
        self.resume_time = time

class SetItemMediaType(BackendMessage):
    """Adds a list of videos to a playlist.
    """
    def __init__(self, media_type, video_ids):
        self.media_type = media_type
        self.video_ids = video_ids

class UpdateAllFeeds(BackendMessage):
    """Updates all feeds.
    """
    pass

class DeleteFeed(BackendMessage):
    """Delete a feed.
    """
    def __init__(self, id_, is_folder, keep_items):
        self.id = id_
        self.is_folder = is_folder
        self.keep_items = keep_items

class DeleteWatchedFolder(BackendMessage):
    """Delete a watched folder.

    .. Note::

       This separate from DeleteFeed since not all watched folders are
       visible.
    """
    def __init__(self, id_):
        self.id = id_

class DeletePlaylist(BackendMessage):
    """Delete a playlist.
    """
    def __init__(self, id_, is_folder):
        self.id = id_
        self.is_folder = is_folder

class DeleteSite(BackendMessage):
    """Delete an external channel guide.
    """
    def __init__(self, id_):
        self.id = id_

class NewGuide(BackendMessage):
    """Create a new channel guide.
    """
    def __init__(self, url):
        self.url = util.to_uni(url)

class NewFeed(BackendMessage):
    """Creates a new feed.
    """
    def __init__(self, url):
        self.url = util.to_uni(url)

class NewFeedSearchFeed(BackendMessage):
    """Creates a new feed based on a search through a feed.
    """
    def __init__(self, channel_info, search_term):
        self.channel_info = channel_info
        self.search_term = search_term

class NewFeedSearchEngine(BackendMessage):
    """Creates a new feed from a search engine.
    """
    def __init__(self, search_engine_info, search_term):
        self.search_engine_info = search_engine_info
        self.search_term = search_term

class NewFeedSearchURL(BackendMessage):
    """Creates a new feed from a url.
    """
    def __init__(self, url, search_term):
        self.url = url
        self.search_term = search_term

class NewWatchedFolder(BackendMessage):
    """Creates a new watched folder.
    """
    def __init__(self, path, visible=None):
        self.path = path
        self.visible = visible

class SetWatchedFolderVisible(BackendMessage):
    """Changes if a watched folder is visible in the tab list or not.
    """
    def __init__(self, id_, visible):
        self.id = id_
        self.visible = visible

class NewPlaylist(BackendMessage):
    """Create a new playlist.
    """
    def __init__(self, name, ids):
        self.name = util.to_uni(name)
        self.ids = ids

class NewFeedFolder(BackendMessage):
    """Create a new feed folder.
    """
    def __init__(self, name, child_feed_ids):
        self.name = util.to_uni(name)
        self.child_feed_ids = child_feed_ids

class NewPlaylistFolder(BackendMessage):
    """Create a new playlist folder.
    """
    def __init__(self, name, child_playlist_ids):
        self.name = util.to_uni(name)
        self.child_playlist_ids = child_playlist_ids

class ChangeMoviesDirectory(BackendMessage):
    """Change the current movies directory.

    If migrate is True, then the backend will send a series of
    ProgressDialog messages while the migration happens.
    """
    def __init__(self, path, migrate):
        self.path = path
        self.migrate = migrate

class AddVideosToPlaylist(BackendMessage):
    """Adds a list of videos to a playlist.
    """
    def __init__(self, playlist_id, video_ids):
        self.playlist_id = playlist_id
        self.video_ids = video_ids

class RemoveVideosFromPlaylist(BackendMessage):
    """Removes a list of videos from a playlist.
    """
    def __init__(self, playlist_id, video_ids):
        self.playlist_id = playlist_id
        self.video_ids = video_ids

class DownloadURL(BackendMessage):
    """Downloads the item at a url.

    :param url: the url of the thing to download
    :handle_unknown_callback: if the thing at the url isn't something that
                              Miro knows what to do with, then it calls
                              this callback.  The handler should take a
                              single argument which is the url that
                              couldn't be handled.
    :param metadata: dict of name/value pairs to include in the item.
    """
    def __init__(self, url, handle_unknown_callback=None, metadata=None):
        self.url = util.to_uni(url)
        self.handle_unknown_callback = handle_unknown_callback
        self.metadata = metadata

class OpenIndividualFiles(BackendMessage):
    """Open a list of file items in Miro.
    """
    def __init__(self, filenames):
        self.filenames = filenames

class AddFiles(BackendMessage):
    """This is like OpenIndividualFiles, but is handled differently in
    that adding files doesn't cause videos that were added to be
    played.
    """
    def __init__(self, filenames):
        self.filenames = filenames

class CheckVersion(BackendMessage):
    """Checks whether Miro is the most recent version.
    """
    def __init__(self, up_to_date_callback):
        self.up_to_date_callback = up_to_date_callback

class Search(BackendMessage):
    """Search a search engine with a search term.
    
    The backend will send a SearchComplete message.
    """
    def __init__(self, searchengine_id, terms):
        self.id = searchengine_id
        self.terms = terms

class CancelAutoDownload(BackendMessage):
    """Cancels the autodownload for an item.
    """
    def __init__(self, id_):
        self.id = id_

class StartDownload(BackendMessage):
    """Start downloading an item.
    """
    def __init__(self, id_):
        self.id = id_
    def __repr__(self):
        return BackendMessage.__repr__(self) + (", id: %s" % self.id)

class CancelDownload(BackendMessage):
    """Cancel downloading an item.
    """
    def __init__(self, id_):
        self.id = id_

class CancelAllDownloads(BackendMessage):
    """Cancels all downloading items.
    """
    pass

class PauseAllDownloads(BackendMessage):
    """Pauses all downloading items.
    """
    pass

class PauseDownload(BackendMessage):
    """Pause downloading an item.
    """
    def __init__(self, id_):
        self.id = id_

class ResumeAllDownloads(BackendMessage):
    """Resumes all downloading items.
    """
    pass

class ResumeDownload(BackendMessage):
    """Resume downloading an item.
    """
    def __init__(self, id_):
        self.id = id_

class StartUpload(BackendMessage):
    """Start uploading a torrent.
    """
    def __init__(self, id_):
        self.id = id_

class StopUpload(BackendMessage):
    """Stop uploading a torrent.
    """
    def __init__(self, id_):
        self.id = id_

class KeepVideo(BackendMessage):
    """Cancel the auto-expiration of an item's video.
    """
    def __init__(self, id_):
        self.id = id_
    def __repr__(self):
        return BackendMessage.__repr__(self) + (", id: %s" % self.id)

class SetMediaKind(BackendMessage):
    """Set the media kind of the list of items to be the specified kind.
    """
    def __init__(self, item_infos, kind):
        self.item_infos = item_infos
        self.kind = kind

class SaveItemAs(BackendMessage):
    """Saves an item in the dark clutches of Miro to somewhere else.
    """
    def __init__(self, id_, filename):
        self.id = id_
        self.filename = filename

class RemoveVideoEntries(BackendMessage):
    """Remove the entry for list of external items.
    """
    def __init__(self, info_list):
        self.info_list = info_list

class DeleteVideos(BackendMessage):
    """Delete files for a list of items
    """
    def __init__(self, info_list):
        self.info_list = info_list

    def __repr__(self):
        return BackendMessage.__repr__(self) + (", infos: %s" % self.info_list)

class EditItems(BackendMessage):
    """Set properties for one or more items to user-defined values."""
    def __init__(self, item_ids, change_dict):
        self.item_ids = item_ids
        self.change_dict = change_dict

class RevertFeedTitle(BackendMessage):
    """Reverts the feed's title back to the original.
    """
    def __init__(self, id_):
        self.id = id_

class PlayAllUnwatched(BackendMessage):
    """Figures out all the unwatched items and plays them.
    """
    def __init__(self):
        pass

class TabExpandedChange(BackendMessage):
    """Inform the backend when a hideable tab gets expanded/collapsed.
    """
    def __init__(self, typ, expanded):
        self.type = typ
        self.expanded = expanded

class FolderExpandedChange(BackendMessage):
    """Inform the backend when a folder gets expanded/collapsed.
    """
    def __init__(self, typ, id_, expanded):
        self.type = typ
        self.id = id_
        self.expanded = expanded

class AutodownloadChange(BackendMessage):
    """Inform the backend that the user changed the auto-download
    setting for a feed.  The possible setting values are ``all``,
    ``new`` and ``off``.
    """
    def __init__(self, id_, setting):
        self.id = id_
        self.setting = setting

class TabsReordered(BackendMessage):
    """Inform the backend when the channel tabs are rearranged.  This
    includes simple position changes and also changes to which folders
    the channels are in.

    :param toplevels: a dict of {'type': [channelinfo1,
                      channelinfo2]}, where ``channelinfo`` is a
                      ChannelInfo object without parents
    :param folder_children: dict mapping channel folder ids to a list of
                            ChannelInfo objects for their children
    """
    def __init__(self):
        self.toplevels = {
            u'feed': [],
            u'playlist': []}
        self.folder_children = {}

    def append(self, info, typ):
        self.toplevels[typ].append(info)
        if info.is_folder:
            self.folder_children[info.id] = []

    def append_child(self, parent_id, info):
        self.folder_children[parent_id].append(info)

class PlaylistReordered(BackendMessage):
    """Inform the backend when the items in a playlist are re-ordered.

    :param id: playlist that was re-ordered.
    :param item_ids: List of ids for item in the playlist, in their new
                     order.
    """
    def __init__(self, id_, item_ids):
        self.id = id_
        self.item_ids = item_ids

class SubscriptionLinkClicked(BackendMessage):
    """Inform the backend that the user clicked on a subscription link
    in a web browser.
    """
    def __init__(self, url):
        self.url = url

class ReportCrash(BackendMessage):
    """Sends a crash report.
    """
    def __init__(self, report, text, send_report):
        self.report = report
        self.text = text
        self.send_report = send_report

class SaveDisplayState(BackendMessage):
    """Save changes to one display for the frontend
    """
    def __init__(self, display_info):
        self.display_info = display_info

class QueryDisplayStates(BackendMessage):
    """Ask for a CurrentDisplayStates message to be sent back.
    """
    pass

class SaveViewState(BackendMessage):
    """Save changes to one tableview for the frontend
    """
    def __init__(self, view_info):
        self.view_info = view_info

class QueryViewStates(BackendMessage):
    """Ask for a CurrentViewStates message to be sent back.
    """
    pass

class SaveGlobalState(BackendMessage):
    """Save changes to the global widgets frontend state for the frontend
    """
    def __init__(self, global_state_info):
        self.info = global_state_info

class QueryGlobalState(BackendMessage):
    """Ask for a CurrentGlobalState message to be sent back.
    """
    pass

class SetDeviceType(BackendMessage):
    """
    Tell the backend which specific type of device we're dealing with.
    """
    def __init__(self, device, name):
        self.device = device
        self.name = name

class SaveDeviceSort(BackendMessage):
    """
    Saves the current sort for a device's view.
    """
    def __init__(self, device, tab_type, key, ascending):
        self.device = device
        self.tab_type = tab_type
        self.key = key
        self.ascending = ascending

class SaveDeviceView(BackendMessage):
    """
    Saves the current view on a device.
    """
    def __init__(self, device, tab_type, view):
        self.device = device
        self.tab_type = tab_type
        self.view = view

class ChangeDeviceSyncSetting(BackendMessage):
    """
    Tell the backend to change a sync setting on the device.
    """
    def __init__(self, device, file_type, setting, value):
        self.device = device
        self.file_type = file_type
        self.setting = setting
        self.value = value

class ChangeDeviceSetting(BackendMessage):
    """
    Tell the backend to change a setting on the device.
    """
    def __init__(self, device, setting, value):
        self.device = device
        self.setting = setting
        self.value = value

class QuerySyncInformation(BackendMessage):
    """
    Ask for a CurrentSyncInformation to be sent back for the given device.
    """
    def __init__(self, device):
        self.device = device

class DeviceSyncFeeds(BackendMessage):
    """
    Ask the backend to sync feeds/playlists onto the device.
    """
    def __init__(self, device):
        self.device = device

class DeviceSyncMedia(BackendMessage):
    """Ask the backend to sync media to the given device.
    """
    def __init__(self, device, item_ids):
        self.device = device
        self.item_ids = item_ids

class CancelDeviceSync(BackendMessage):
    """Ask the backend to cancel any sync in progress.
    """
    def __init__(self, device):
        self.device = device

class DeviceEject(BackendMessage):
    """Ask the backend to eject the given device.
    """
    def __init__(self, device):
        self.device = device

class DownloadSharingItems(BackendMessage):
    """Ask the backend to download some items from a remote share into the
    main database. 
    """
    def __init__(self, item_infos):
        self.item_infos = item_infos

class DownloadDeviceItems(BackendMessage):
    """Ask the backend to copy some items from a device into the main database.
    """
    def __init__(self, item_infos):
        self.item_infos = item_infos

class RateItem(BackendMessage):
    """Assign a rating (1-5) to an item.
    """
    def __init__(self, info, rating):
        self.info = info
        self.rating = rating

class SetNetLookupEnabled(BackendMessage):
    """Enable/disable internet lookups for a set of items.  """
    def __init__(self, item_ids, enabled):
        """Create a new message

        :param item_ids: list of item ids or None for all current items
        :param boolean enabled: enable/disable flag
        """
        self.item_ids = item_ids
        self.enabled = enabled

class ClogBackend(BackendMessage):
    """Dev message: intentionally clog the backend for a specified number of 
    seconds.
    """
    def __init__(self, n=0):
        self.n = n

class ForceFeedparserProcessing(BackendMessage):
    """Force the backend to do a bunch of feedparser updates
    """
    pass

class ForceDBSaveError(BackendMessage):
    """Simulate an error running an INSERT/UPDATE statement on the main DB.
    """

class ForceDeviceDBSaveError(BackendMessage):
    """Simulate an error running an INSERT/UPDATE statement on a device DB.
    """
    def __init__(self, device_info):
        self.device_info = device_info

# Frontend Messages
class DownloaderSyncCommandComplete(FrontendMessage):
    """Tell the frontend that the pause/resume all command are complete,
    so that we only sort once.  This saves time sorting and also prevents
    UI clog when items are updated and gets sorted one by one.
    """
    pass

class JettisonTabs(FrontendMessage):
    """Tell the frontend to remove certain sidebar tabs from its model.  Done
    when selecting multiple items in the sidebar using the add to new folder
    button in the main display.  This is really a hack for bz:16780

    WARNING - the frontend only implements this for leaf nodes. See
    handle_jettison_tabs for details.
    """
    def __init__(self, typ, ids):
        self.type = typ
        self.ids = ids

class SharingConnectFailed(FrontendMessage):
    """Tell the frontend the request to connect a share failed."""
    def __init__(self, share):
        self.share = share

class SharingDisappeared(FrontendMessage):
    """Tell the frontend that the share has somehow disappeared."""
    def __init__(self, share):
        self.share = share

class ShowWarning(FrontendMessage):
    """Tell the frontend to show a warning."""
    def __init__(self, title, description):
        self.title = title
        self.description = description

class FrontendQuit(FrontendMessage):
    """The frontend should exit."""
    pass

class DatabaseUpgradeStart(FrontendMessage):
    """We're about to do a database upgrade.
    """
    def __init__(self, doing_db_upgrade):
        self.doing_db_upgrade = doing_db_upgrade

class DatabaseUpgradeProgress(FrontendMessage):
    """We're about to do a database upgrade.
    """
    def __init__(self, stage, stage_progress, total_progress):
        self.stage = stage
        self.stage_progress = stage_progress
        self.total_progress = total_progress

class DatabaseUpgradeEnd(FrontendMessage):
    """We're done with the database upgrade.
    """
    pass

class StartupSuccess(FrontendMessage):
    """The startup process is complete.  The frontend should wait for
    this signal to show the UI to the user.
    """
    pass

class StartupFailure(FrontendMessage):
    """The startup process failed.  The frontend should inform the
    user that this happened and quit.

    Attributes:
    :param summary: Short, user-friendly, summary of the problem.
    :param description: Longer explanation of the problem.
    """
    def __init__(self, summary, description):
        self.summary = summary
        self.description = description

class StartupDatabaseFailure(FrontendMessage):
    """The startup process failed due to a database error.  The
    frontend should inform the user that this happened and quit.

    Attributes:
    :param summary: Short, user-friendly, summary of the problem.
    :param description: Longer explanation of the problem.
    """
    def __init__(self, summary, description):
        self.summary = summary
        self.description = description

class ChannelInfo(object):
    """Tracks the state of a channel

    :param name: channel name
    :param url: channel url (None for channel folders)
    :param id: object id
    :param tab_icon: path to this channel's tab icon
    :param thumbnail: path to this channel's thumbnail
    :param num_downloaded: number of downloaded items in the feed
    :param unwatched: number of unwatched videos
    :param available: number of newly downloaded videos
    :param is_folder: is this a channel folder?
    :param is_directory_feed: is this channel is a watched directory?
    :param parent_id: id of parent folder or None
    :param is_updating: whether or not the feed is currently updating
    :param has_downloading: are videos currently being downloaded for
                            this channel?
    :param base_href: url to use for relative links for items in this
                      channel.  This will be None for ChannelFolders.
    :param autodownload_mode: current autodownload mode (``all``,
                              ``new`` or ``off``)
    :param search_term: the search term used for this feed or None
    :param expire: expire type (``system``, ``never``, or ``feed``)
    :param expire_time: expire time in hours
    :param max_new: maximum number of items this feed wants
    :param max_old_items: maximum number of old items to remember
    """
    def __init__(self, channel_obj):
        self.name = channel_obj.get_title()
        self.id = channel_obj.id
        self.unwatched = channel_obj.num_unwatched()
        self.available = channel_obj.num_available()
        self.has_downloading = channel_obj.has_downloading_items()
        if hasattr(channel_obj, "searchTerm"):
            self.search_term = channel_obj.searchTerm
        else:
            self.search_term = None
        if not isinstance(channel_obj, models.ChannelFolder):
            self.has_original_title = channel_obj.has_original_title()
            self.is_updating = channel_obj.is_updating()
            self.parent_id = channel_obj.folder_id
            self.url = channel_obj.get_url()
            self.thumbnail = channel_obj.get_thumbnail_path()
            self.base_href = channel_obj.get_base_href()
            self.autodownload_mode = channel_obj.get_autodownload_mode()
            self.is_folder = False
            self.is_directory_feed = (self.url is not None and
                    self.url.startswith('dtv:directoryfeed'))
            self.tab_icon = channel_obj.get_thumbnail_path()
            self.expire = channel_obj.get_expiration_type()
            self.expire_time = channel_obj.get_expiration_time()
            self.max_new = channel_obj.get_max_new()
            self.max_old_items = channel_obj.get_max_old_items()
            self.num_downloaded = channel_obj.num_downloaded()
        else:
            self.is_updating = False
            self.parent_id = None
            self.url = None
            self.thumbnail = resources.path('images/folder-icon.png')
            self.autodownload_mode = self.base_href = None
            self.is_folder = True
            self.tab_icon = resources.path('images/icon-folder.png')
            self.is_directory_feed = False
            self.expire = None
            self.expire_time = None
            self.max_new = None
            self.max_old_items = None
            self.num_downloaded = None

class PlaylistInfo(object):
    """Tracks the state of a playlist

    :param name: playlist name
    :param id: object id
    :param is_folder: is this a playlist folder?
    """
    def __init__(self, playlist_obj):
        self.name = playlist_obj.get_title()
        self.id = playlist_obj.id
        self.is_folder = isinstance(playlist_obj, models.PlaylistFolder)
        if self.is_folder:
            self.parent_id = None
        else:
            self.parent_id = playlist_obj.folder_id

class GuideInfo(object):
    """Tracks the state of a channel guide

    :param name: channel name
    :param id: object id
    :param url: URL for the guide
    :param allowed_urls: URLs that should be also considered part of the guide
    :param default: is this the default channel guide?
    :param favicon: the favicon for the guide
    :param faviconIsDefault: true if the guide is using the default site
                             icon and not a favicon from the web
    """
    def __init__(self, guide):
        self.name = guide.get_title()
        self.id = guide.id
        self.url = guide.get_url()
        self.default = guide.is_default()
        self.store = bool(guide.store)
        self.visible = guide.is_visible()
        self.allowed_urls = guide.allowedURLs
        self.favicon = guide.get_favicon_path()
        self.faviconIsDefault = not (guide.icon_cache and
                                     guide.icon_cache.get_filename())

    def __repr__(self):
        return '<miro.messages.GuideInfo(%i) "%s">' % (self.id, self.name)

class WatchedFolderInfo(object):
    """Tracks the state of a watched folder.
    
    :param id: ID of the channel
    :param path: Path to the folder being watched
    :param visible: Is the watched folder shown on the tab list?
    """
    def __init__(self, channel):
        self.id = channel.id
        self.path = channel.dir
        self.visible = channel.visible

class GuideList(FrontendMessage):
    """Sends the frontend the initial list of channel guides

    :param default_guide: The Default channel guide
    :param added_guides: list added channel guides
    :param invisible_guides: list of guides which aren't visible (used by
                             StoreManager)
    """
    def __init__(self, guides):
        default_guides = [g for g in guides if g.default]
        if not default_guides:
            # The problem here is that Miro persists guides and it's possible
            # for it to have a default channel guide persisted, but when you
            # set the channel guide via the DTV_CHANNELGUIDE_URL, then there's
            # no default guide.  So we generate one here.  Bug #11027.
            logging.warning("Generating a new guide")
            cg = guide.ChannelGuide(util.to_uni(app.config.get(
                        prefs.CHANNEL_GUIDE_URL)))
            cg_info = GuideInfo(cg)
            default_guides = [cg_info]
        elif len(default_guides) > 1:
            logging.warning("Multiple default guides!  Picking the first one.")
            default_guides = [default_guides[0]]
        self.default_guide = default_guides[0]
        self.added_guides = [g for g in guides if not g.default]
        self.root_expanded = False

class StoreList(FrontendMessage):
    """Sends the frontend the initial list of stores"""
    def __init__(self, stores):
        self.hidden_stores = [s for s in stores if not s.visible]
        self.visible_stores = [s for s in stores if s.visible]
        self.root_expanded = False

class StoresChanged(FrontendMessage):
    """Informs the frontend that the visible store list has changed.

    :param added: GuideInfo object for each added store.
                  The list will be in the same order that they were added.
    :param changed: The list of GuideInfo for each changed store.
    :param removed: list of ids for each store that was hidden.
    """
    def __init__(self, added, changed, removed):
        self.added = added
        self.changed = changed
        self.removed = removed

class SetGuideVisible(BackendMessage):
    """Changes if a guide is visible in the tab list or not.
    """
    def __init__(self, id_, visible):
        self.id = id_
        self.visible = visible

class TabList(FrontendMessage):
    """Sends the frontend the current list of channels and playlists

    This is sent at startup and when the changes to the list of
    channels/playlists is too complex to describe with a TabsChanged message.

    :param type: ``feed`` or ``playlist``
    :param toplevels: the list of ChannelInfo/PlaylistInfo objects
                      without parents
    :param folder_children: dict mapping channel folder ids to a list of
                            ChannelInfo/PlaylistInfo objects for their
                            children
    :param expanded_folders: set containing ids of the folders that should
                             be initially expanded.
    """
    def __init__(self, typ):
        self.type = typ
        self.toplevels = []
        self.folder_children = {}
        self.expanded_folders = set()
        self.root_expanded = None

    def append(self, info):
        self.toplevels.append(info)
        if info.is_folder:
            self.folder_children[info.id] = []

    def append_child(self, parent_id, info):
        self.folder_children[parent_id].append(info)

    def expand_folder(self, folder_id):
        self.expanded_folders.add(folder_id)

class TabsChanged(FrontendMessage):
    """Informs the frontend that the channel list or playlist list has been 
    changed.

    :param type: ``feed``, ``playlist`` or ``guide``
    :param added: ChannelInfo/PlaylistInfo object for each added tab.  The
                  list will be in the same order that the tabs were added.
    :param changed: list of ChannelInfo/PlaylistInfos for each changed tab.
    :param removed: list of ids for each tab that was removed
    """
    def __init__(self, typ, added, changed, removed):
        self.type = typ
        self.added = added
        self.changed = changed
        self.removed = removed

    def __str__(self):
        return ('<miro.messages.TabsChanged %s '
    '(%d added, %d changed, %d removed)>') % (self.type,
    len(self.added), len(self.changed), len(self.removed))

class ItemChanges(FrontendMessage):
    """Sent to the frontend when items change

    :attribute added: set ids for added items
    :attribute changed: set ids for changed items
    :attribute removed: set ids for removed items
    :attribute changed_columns: set columns that were changed (the union of
    changes for all items)
    :attribute dlstats_changed: Did we get new download stats?
    :attribute playlists_changed: Did items get added/removed from playlists?
    """
    def __init__(self, added, changed, removed, changed_columns,
                 dlstats_changed, playlists_changed):
        self.added = frozenset(added)
        self.changed = frozenset(changed)
        self.removed = frozenset(removed)
        self.changed_columns = frozenset(changed_columns)
        self.dlstats_changed = dlstats_changed
        self.playlists_changed = playlists_changed

class DeviceItemChanges(FrontendMessage):
    """Sent to the frontend when items change on a device

    :attribute device_id: id for the device
    :attribute added: set ids for added items
    :attribute changed: set ids for changed items
    :attribute removed: set ids for removed items
    :attribute changed_columns: set columns that were changed (the union of
    changes for all items)
    """
    def __init__(self, device_id, added, changed, removed, changed_columns):
        self.device_id = device_id
        self.added = added
        self.changed = changed
        self.removed = removed
        self.changed_columns = changed_columns

class SharingItemChanges(FrontendMessage):
    """Sent to the frontend when items change on a share

    :attribute share_id: id for the share
    :attribute added: set ids for added items
    :attribute changed: set ids for changed items
    :attribute removed: set ids for removed items
    :attribute changed_columns: set columns that were changed (the union of
    changes for all items)
    :attribute changed_playlists: True if the any playlists have been changed
    had their contents changed.
    """
    def __init__(self, share_id, added, changed, removed, changed_columns,
                 changed_playlists):
        self.share_id = share_id
        self.added = added
        self.changed = changed
        self.removed = removed
        self.changed_columns = changed_columns
        self.changed_playlists = changed_playlists

class WatchedFolderList(FrontendMessage):
    """Sends the frontend the initial list of watched folders.

    :param watched_folders: List of watched folders
    """
    def __init__(self, watched_folders):
        self.watched_folders = watched_folders

class WatchedFoldersChanged(FrontendMessage):
    """Informs the frontend that the watched folder list has changed.

    :param added: WatchedFolderInfo object for each added watched folder.
                  The list will be in the same order that they were added.
    :param changed: The list of WatchedFolderInfo for each changed watched
                    folder.
    :param removed: list of ids for each watched folder that was removed.
    """
    def __init__(self, added, changed, removed):
        self.added = added
        self.changed = changed
        self.removed = removed

class CurrentSearchInfo(FrontendMessage):
    """Informs the frontend of the current search settings.
    """
    def __init__(self, engine, text):
        self.engine = engine
        self.text = text

class DownloadCountChanged(FrontendMessage):
    """Informs the frontend that number of downloads has changed. Includes the
    number of non downloading items which should be displayed.
    """
    def __init__(self, count, non_downloading_count):
        self.count = count
        self.non_downloading_count = non_downloading_count

class PausedCountChanged(FrontendMessage):
    """Informs the frontend that number of paused downloading items
    has changed.
    """
    def __init__(self, count):
        self.count = count

class OthersCountChanged(FrontendMessage):
    """Informs the frontend that the number of 'other' items has changed.
    """
    def __init__(self, count):
        self.count = count

class NewVideoCountChanged(FrontendMessage):
    """Informs the frontend that number of new videos has changed.
    """
    def __init__(self, count):
        self.count = count

class NewAudioCountChanged(FrontendMessage):
    """Informs the frontend that number of new videos has changed.
    """
    def __init__(self, count):
        self.count = count

class UnwatchedCountChanged(FrontendMessage):
    """Informs the frontend that number of unwatched items has changed.
    """
    def __init__(self, count):
        self.count = count

class ConverterList(FrontendMessage):
    """Sends the list of converters to the frontend

    :attribute converters: list of converter groups.  Each group will contain
    a sublist of (identifier, name) tuples.
    """
    def __init__(self, converter_list):
        self.converters = []
        for name, converters in converter_list:
            self.converters.append([(info.identifier, info.name)
                                    for info in converters])

class ConversionTaskInfo(object):
    """Tracks the state of an conversion task.

    :param key: id for the conversion task
    :param state: current state of the conversion.  One of: "pending",
        "running", "failed", or "finished"
    :param progress: how far the conversion task is
    :param error: user-friendly string for describing conversion
                  errors (if any)
    :param output_path: path to the converted video (or None)
    :param log_path: path to the log file for the conversion
    :param item_name: name of the item being converted
    :param item_thumbnail: thumbnail for the item being converted
    """
    def __init__(self, task):
        self.id = self.key = task.key
        if task.is_finished():
            self.state = 'finished'
            self.output_path = task.final_output_path
        else:
            self.output_path = None
            if task.is_failed():
                self.state = 'failed'
            elif task.is_running():
                self.state = "running"
            else:
                self.state = "pending"
        self.log_path = task.log_path
        self.progress = task.progress
        self.error = task.error
        self.item_name = task.item_info.title
        self.item_thumbnail = task.item_info.thumbnail
        self.eta = task.get_eta()
        self.target = task.get_display_name()
        self.output_size_guess = task.get_output_size_guess()

class ConversionTasksList(FrontendMessage):
    """Send the current list of running and pending conversion tasks to the 
       frontend.
    """
    def __init__(self, running_tasks, pending_tasks, finished_tasks):
        self.running_tasks = running_tasks
        self.pending_tasks = pending_tasks
        self.finished_tasks = finished_tasks

class ConversionsCountChanged(FrontendMessage):
    """Informs the frontend that number of running conversions has changed.
    """
    def __init__(self, running_count, other_count):
        self.running_count = running_count
        self.other_count = other_count

class ConversionTaskCreated(FrontendMessage):
    """Informs the frontend that a conversion task has been created.
    """
    def __init__(self, task):
        self.task = task

class ConversionTaskRemoved(FrontendMessage):
    """Informs the frontend that a conversion task has been removed.
    """
    def __init__(self, task):
        self.task = task

class AllConversionTaskRemoved(FrontendMessage):
    """Informs the frontend that all conversion tasks have been removed.
    """
    pass

class ConversionTaskChanged(FrontendMessage):
    """Informs the frontend that a conversion task has changed.

    This is sent when a conversion task changes state, or when a running task
    changes it's progress.
    """
    def __init__(self, task):
        self.task = task

class SharingInfo(object):
    """Tracks the state of an extent share."""
    def __init__(self, share):
        self.id = 'sharing-%s' % (share.id,)
        self.share_id = share.id
        self.sqlite_path = share.db_path
        self.name = share.name
        self.host = share.host
        self.port = share.port
        self.share_available = False
        self.stale_callback = None
        self.mount = False
        self.is_updating = False

class SharingPlaylistInfo(object):
    """Tracks the state a playlist on a share."""
    def __init__(self, share_id, name, playlist_id, podcast):
        self.share_id = share_id
        self.id = u'sharing-%s-%s' % (share_id, playlist_id)
        self.name = name
        self.podcast = podcast
        self.playlist_id = playlist_id

class SharingEject(BackendMessage):
    """Tells the backend that the user has requested the share be disconnected.
    """
    def __init__(self, share):
        self.share = share

class DeviceInfo(object):
    """Tracks the state of an attached device.
    """
    def __init__(self, id_, device_info, mount, sqlite_path, database, db_info,
                 metadata_manager, size, remaining, read_only):
        self.id = id_
        self.mount = mount
        self.sqlite_path = sqlite_path
        self.database = database
        self.db_info = db_info
        self.metadata_manager = metadata_manager
        self.size = size
        self.remaining = remaining
        self.info = device_info
        self.read_only = read_only
        self.name = database.get('settings', {}).get('name', device_info.name)

    def __repr__(self):
        return "<miro.messages.DeviceInfo %r %r>" % (self.id, self.info)

class DeviceChanged(FrontendMessage):
    """Informs the frontend that a device has changed state.
    """
    def __init__(self, device):
        self.device = device

class CurrentSyncInformation(FrontendMessage):
    """Informs the frontend of what the current sync would look like.
    """
    def __init__(self, device, count, size):
        self.device = device
        self.count = count
        self.size = size

class DeviceSyncChanged(FrontendMessage):
    """Informs the frontend that the status of a device sync has changed.  This
    includes starting and stopping.
    """
    def __init__(self, sync_manager):
        self.device = sync_manager.device
        self.finished = sync_manager.is_finished()
        self.progress = sync_manager.get_progress()
        self.eta = sync_manager.get_eta()

class MessageToUser(FrontendMessage):
    """Lets the backend send messages directly to the user.
    """
    def __init__(self, title, desc):
        self.title = title
        self.desc = desc

class PlayMovies(FrontendMessage):
    """Play a list of files
    """
    def __init__(self, item_infos):
        self.item_infos = item_infos

class StopPlaying(FrontendMessage):
    """Stops playback.
    """
    pass

class NotifyUser(FrontendMessage):
    """Sends a notification to the user.

    Can optionally give a notification type, so we can filter based on
    whether the user has selected that they are interested in
    receiving notifications of this type.
    """
    def __init__(self, title, body, notify_type=None):
        self.title = title
        self.body = body
        self.notify_type = notify_type
    
class SearchComplete(FrontendMessage):
    """Notifies the backend that the search was complete.
    """
    def __init__(self, engine, query, result_count):
        self.engine = engine
        self.query = query
        self.result_count = result_count

class CurrentDisplayStates(FrontendMessage):
    """Returns the states of all displays
    """
    def __init__(self, display_infos):
        self.displays = display_infos

class CurrentGlobalState(FrontendMessage):
    """Returns the global state for the widgets frontend
    """
    def __init__(self, global_info):
        self.info = global_info

class CurrentViewStates(FrontendMessage):
    """Returns the states of all Views
    """
    def __init__(self, view_infos):
        self.views = view_infos

class DisplayInfo(object):
    """Contains the properties that:
       -are shared across all TableViews for a Display or
       -apply to just one view in a display
    """
    def __init__(self, key, display=None):
        self.key = key
        if display is not None:
            self.selected_view = display.selected_view
            self.shuffle = display.shuffle
            self.repeat = display.repeat
            self.selection = display.selection
            self.sort_state = display.sort_state
            self.last_played_item_id = display.last_played_item_id
            # shallow-copy attributes that store lists, dicts, and sets so
            # that changing the database object doesn't change the DisplayInfo
            self.active_filters = copy.copy(display.active_filters)
        else:
            self.selected_view = None
            self.active_filters = None
            self.shuffle = None
            self.repeat = None
            self.selection = None
            self.sort_state = None
            self.last_played_item_id = None

class GlobalInfo(object):
    """Contains the properties that are global to the widgets frontend
    """
    def __init__(self, global_info):
        self.item_details_expanded = global_info.item_details_expanded
        self.guide_sidebar_expanded = global_info.guide_sidebar_expanded
        self.tabs_width = global_info.tabs_width

class ViewInfo(object):
    """Contains the properties that are unique to each View
    """
    def __init__(self, key, view=None):
        self.key = key
        if view is not None:
            self.scroll_position = view.scroll_position
            # shallow-copy attributes that store lists, dicts, and sets so
            # that changing the database object doesn't change the DisplayInfo
            self.columns_enabled = copy.copy(view.columns_enabled)
            self.column_widths = copy.copy(view.column_widths)
        else:
            self.scroll_position = None
            self.columns_enabled = None
            self.column_widths = None

class OpenInExternalBrowser(FrontendMessage):
    """Opens the specified url in an external browser.
    """
    def __init__(self, url):
        self.url = url

class ProgressDialogStart(FrontendMessage):
    def __init__(self, title):
        self.title = title

class ProgressDialog(FrontendMessage):
    """Inform the frontend of progress while we perform a long-running task.

    :param progress: current progress for the task [0.0 - 1.0] or -1 if we
        can't estimate the progress.  The frontend should show a throbber in
        this case)
    """
    def __init__(self, description, progress):
        self.description = description
        self.progress = progress

class ProgressDialogFinished(FrontendMessage):
    pass

class FeedlessDownloadStarted(FrontendMessage):
    """Inform the frontend that a new video started downloading because a
    subscribe link was clicked.
    """
    pass

class MetadataProgressUpdate(FrontendMessage):
    def __init__(self, target, finished, finished_local, eta, total):
        self.target = target
        self.finished = finished
        self.finished_local = finished_local
        self.eta = eta
        self.total = total

class SetNetLookupEnabledFinished(FrontendMessage):
    """The backend has processed the SetNetLookupEnabled message."""
    pass

class NetLookupCounts(FrontendMessage):
    """Update the frontend on how many items we're running net lookups for."""
    def __init__(self, net_lookup_count, total_count):
        self.net_lookup_count = net_lookup_count
        self.total_count = total_count
