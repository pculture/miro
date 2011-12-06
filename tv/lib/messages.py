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

class TrackItems(BackendMessage):
    """Begin tracking items for a feed

    After this message is sent, the backend will send back a ItemList message,
    then it will send ItemsChanged messages for items in the feed.

    type is the type of object that we are tracking items for.  It can be one
    of the following:

    * feed -- Items in a feed
    * playlist -- Items in a playlist
    * new -- Items that haven't been watched
    * downloading -- Items being downloaded
    * library -- All items

    id should be the id of a feed/playlist. For new, downloading and library
    it is ignored.
    """
    def __init__(self, typ, id_):
        self.type = typ
        self.id = id_

class TrackItemsManually(BackendMessage):
    """Track a manually specified list of items.

    TrackItemsManually can only be used to track database items.

    No ItemList message will be sent, since the sender is providing the inital
    list of items.  Instead, if the infos_to_track is out of date of date,
    then an ItemsChanged message will be sent with the changes.

    ItemsChanged messages will have "manual" as the type and will use the id
    specified in the constructed.
    """
    def __init__(self, id_, infos_to_track):
        self.id = id_
        self.infos_to_track = infos_to_track
        self.type = 'manual'

class StopTrackingItems(BackendMessage):
    """Stop tracking items for a feed.
    """
    def __init__(self, typ, id_):
        self.type = typ
        self.id = id_

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

class TrackSharing(BackendMessage):
    """Start tracking media shares.
    """
    pass

class TrackDevices(BackendMessage):
    """Start tracking devices.
    """
    pass

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

class ItemInfo(object):
    """Tracks the state of an item

    :param name: name of the item
    :param id: object id
    :param source: the ItemSource this ItemInfo was generated from
    :param feed_id: id for the items feed
    :param feed_name: name of the feed item is attached to
    :param feed_url: URL of the feed item is attached to 
    :param description: longer description for the item (HTML)
    :param state: see Item.get_state()
    :param release_date: datetime object when the item was published
    :param size: size of the item in bytes
    :param duration: length of the video in seconds
    :param resume_time: time at which playback should restart
    :param permalink: URL to a permalink to the item (or None)
    :param commentslink: URL to a comments page for the item (or None)
    :param payment_link: URL of the payment page associated with the item
                         (or empty string)
    :param has_shareable_url: does this item have a shareable URL?
    :param can_be_saved: is this an expiring downloaded item?
    :param downloaded: has the item been downloaded?
    :param is_external: is this item external (true) or from a channel
                        (false)?
    :param expiration_date: datetime object for when the item will expire
                            (or None)
    :param item_viewed: has the user ever seen the item?
    :param video_watched: has the user watched the video for the item?
    :param video_path: the file path to the video for this item (or None)
    :param file_type: type of the downloaded file (video/audio/other)
    :param subtitle_encoding: encoding for subtitle display
    :param media_type_checked: has the movie data util checked file_type?
    :param seeding_status: Torrent seeding status ('seeding', 'stopped',
                           or None)
    :param thumbnail: path to the thumbnail for this file
    :param thumbnail_url: URL for the item's thumbnail (or None)
    :param file_format: User-facing format description.  Possibly the
                        file type,  pulled from the mime_type, or more
                        generic, like "audio"
    :param remote: is this item from a media share or local?
    :param host: machine hosting the item, only valid if remote is set
    :param port: port to connect to for item, only valid if remote is set
    :param license: this file's license, if known.
    :param mime_type: mime-type of the enclosure that would be downloaded
    :param album_artist: the album artist of the album
    :param artist: the primary artist of the track
    :param album: the track's album of origin
    :param track: the track number within the album
    :param year: the track's year of release
    :param genre: the track's genre
    :param rating: the user's rating of the track
    :param date_added: when the item became part of the user's db
    :param last_played: the date/time the item was last played
    :param file_url: URL of the enclosure that would be downloaded
    :param download_info: DownloadInfo object containing info about the
                          download (or None)
    :param is_container_item: whether or not this item is actually a
                              collection of files as opposed to an
                              individual item
    :param children: for container items the children of the item.
    :param is_playable: is this item a audio/video file, or a container that
                        contains audio/video files inside.
    :param is_playing: Whether item is the currently playing (or paused) item
    :param leechers: (Torrent only) number of leeching clients
    :param seeders: (Torrent only) number of seeding clients
    :param up_rate: (Torrent only) how fast we're uploading data
    :param down_rate: (Torrent only) how fast we're downloading data
    :param up_total: (Torrent only) total amount we've uploaded
    :param down_total: (Torrent only) total amount we've downloaded
    :param up_down_ratio: (Torrent only) ratio of uploaded to downloaded
    :param has_drm: True/False if known; None if unknown (usually means no)
    """

    html_stripper = util.HTMLStripper()

    def __repr__(self):
        return "<ItemInfo %r>" % self.id

    def __getstate__(self):
        d = self.__dict__.copy()
        d['device'] = None
        del d['description_stripped']
        del d['search_terms']
        return d

    def __setstate__(self, d):
        self.__dict__.update(d)
        self.description_stripped = ItemInfo.html_stripper.strip(
                self.description)
        self.search_terms = search.calc_search_terms(self)

    def __init__(self, id_, **kwargs):
        self.id = id_

        self.__dict__.update(kwargs) # we're just a thin wrapper around some
                                     # data

        # stuff we can calculate from other attributes
        if not hasattr(self, 'description_stripped'):
            self.description_stripped = ItemInfo.html_stripper.strip(
                self.description)
        if not hasattr(self, 'search_terms'):
            self.search_terms = search.calc_search_terms(self)
        self.name_sort_key = util.name_sort_key(self.name)
        self.album_sort_key = util.name_sort_key(self.album)
        self.artist_sort_key = util.name_sort_key(self.artist)
        if self.album_artist:
            self.album_artist_sort_key = util.name_sort_key(self.album_artist)
        else:
            self.album_artist_sort_key = self.artist_sort_key
        # pre-calculate things that get displayed in list view
        self.description_oneline = (
                self.description_stripped[0].replace('\n', '$'))
        self.display_date = displaytext.date_slashes(self.release_date)
        self.display_duration = displaytext.duration(self.duration)
        self.display_duration_short = displaytext.short_time_string(
                self.duration)
        self.display_size = displaytext.size_string(self.size)
        self.display_date_added = displaytext.date_slashes(self.date_added)
        self.display_last_played = displaytext.date_slashes(self.last_played)
        self.display_track = displaytext.integer(self.track)
        self.display_year = displaytext.integer(self.year)
        self.display_torrent_details = self.calc_torrent_details()
        self.display_drm = self.has_drm and _("Locked") or u""
        # FIXME: display_kind changes here need also be applied in itemedit
        if self.kind == 'movie':
            self.display_kind = _("Movie")
        elif self.kind == 'show':
            self.display_kind = _("Show")
        elif self.kind == 'clip':
            self.display_kind = _("Clip")
        elif self.kind == 'podcast':
            self.display_kind = _("Podcast")
        else:
            self.display_kind = None

        if self.state == 'downloading':
            dl_info = self.download_info
            if dl_info.eta > 0:
                self.display_eta = displaytext.time_string(dl_info.eta)
            else:
                self.display_eta = ''
            self.display_rate = displaytext.download_rate(dl_info.rate)
        else:
            self.display_rate = self.display_eta = ''

    def calc_torrent_details(self):
        if not self.download_info or not self.download_info.torrent:
            return ''

        details = _(
            "S: %(seeders)s  |  "
            "L: %(leechers)s  |  "
            "UR: %(up_rate)s  |  "
            "UT: %(up_total)s  |  "
            "DR: %(down_rate)s  |  "
            "DT: %(down_total)s  |  "
            "R: %(ratio).2f",
            {"seeders": self.seeders,
             "leechers": self.leechers,
             "up_rate": self.up_rate,
             "up_total": self.up_total,
             "down_rate": self.down_rate,
             "down_total": self.down_total,
             "ratio": self.up_down_ratio})
        return details

class DownloadInfo(object):
    """Tracks the download state of an item.

    :param downloaded_size: bytes downloaded
    :param rate: current download rate, in bytes per second
    :param state: one of ``downloading``, ``uploading``, ``finished``,
                  ``failed`` or ``paused``.  ``uploading`` is for
                  torrents only.  It means that we've finished
                  downloading the torrent and are now seeding it.
    :param eta: Estimated seconds before the download is finished
    :param startup_activity: The current stage of starting up
    :param finished: True if the item has finished downloading
    :param torrent: Is this a Torrent download?
    """
    def __init__(self, downloader):
        self.downloaded_size = downloader.get_current_size()
        self.total_size = downloader.get_total_size()
        self.rate = downloader.get_rate()
        self.state = downloader.get_state()
        self.startup_activity = downloader.get_startup_activity()
        self.finished = downloader.is_finished()
        self.torrent = (downloader.get_type() == 'bittorrent')
        if self.state == 'failed':
            self.reason_failed = downloader.get_reason_failed()
            self.short_reason_failed = downloader.get_short_reason_failed()
        else:
            self.reason_failed = u""
            self.short_reason_failed = u""
        self.eta = downloader.get_eta()

class PendingDownloadInfo(DownloadInfo):
    """DownloadInfo object for pending downloads (downloads queued,
    but not started because we've reached some limit)
    """
    def __init__(self):
        self.downloaded_size = 0
        self.rate = 0
        self.state = 'pending'
        self.startup_activity = _('queued for download')
        self.finished = False
        self.torrent = False
        self.reason_failed = u""
        self.short_reason_failed = u""
        self.eta = 0

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

class ItemList(FrontendMessage):
    """Sends the frontend the initial list of items for a feed

    :param type: type of object being tracked (same as in TrackItems)
    :param id: id of the object being tracked (same as in TrackItems)
    :param items: list of ItemInfo objects
    """
    def __init__(self, typ, id_, item_infos):
        self.type = typ
        self.id = id_
        self.items = item_infos

class ItemsChanged(FrontendMessage):
    """Informs the frontend that the items in a feed have changed.

    :param type: type of object being tracked (same as in TrackItems)
    :param id: id of the object being tracked (same as in TrackItems)
    :param added: list containing an ItemInfo object for each added item.
                  The order will be the order they were added.
    :param changed: set containing an ItemInfo for each changed item.
    :param removed: set containing ids for each item that was removed
    """
    def __init__(self, typ, id_, added, changed, removed):
        self.type = typ
        self.id = id_
        self.added = added
        self.changed = changed
        self.removed = removed

    def __str__(self):
        return ('<miro.messages.ItemsChanged %s:%s '
    '(%d added, %d changed, %d removed)>') % (self.type, self.id,
    len(self.added), len(self.changed), len(self.removed))

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
        self.item_name = task.item_info.name
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
    def __init__(self, share_id, tracker_id, name, host, port, parent_id=None,
                 playlist_id=None, podcast=False, has_children=False):
        # We need to create a unique identifier for indexing.  Fortunately
        # this may be non-numeric.  We just combine the name, host, port
        # as our index.
        self.id = share_id
        self.tracker_id = tracker_id
        self.name = name
        self.host = host
        self.port = port
        self.share_available = False
        self.stale_callback = None
        self.mount = False
        self.podcast = podcast
        self.is_updating = False
        self.playlist_id = playlist_id
        if parent_id is not None:
            self.is_folder = has_children
            self.parent_id = parent_id
        else:
            self.parent_id = None
            self.is_folder = True

class SharingEject(BackendMessage):
    """Tells the backend that the user has requested the share be disconnected.
    """
    def __init__(self, share):
        self.share = share

class DeviceInfo(object):
    """Tracks the state of an attached device.
    """
    def __init__(self, id_, device_info, mount, database, size, remaining):
        self.id = id_
        self.mount = mount
        self.database = database
        self.size = size
        self.remaining = remaining
        self.info = device_info
        self.name = database.get('settings', {}).get('name', device_info.name)

    def __repr__(self):
        return "<miro.messages.DeviceInfo %r %r>" % (self.id, self.info)

    def max_sync_size(self, include_auto=True):
        """
        Returns the largest sync (in bytes) that we can perform on this device.
        """
        if not self.mount:
            return 0
        sync = self.database.get(u'sync', {})
        if not sync.get(u'max_fill', False):
            return self.remaining + (self._auto_fill_size() if include_auto
                                     else 0)
        else:
            try:
                percent = int(sync.get(u'max_fill_percent', 90)) * 0.01
            except ValueError:
                return self.remaining + (self._auto_fill_size() if include_auto
                                         else 0)
            else:
                min_remaining = self.size * (1 - percent)
                return self.remaining - min_remaining + (
                    self._auto_fill_size() if include_auto else 0)

    def _auto_fill_size(self):
        """
        Returns the total size of auto-filled files.
        """
        sync = self.database.get(u'sync')
        if not sync:
            return 0
        if not sync.get(u'auto_fill', False):
            return 0
        return sum(item[u'size'] for file_type in (u'audio', u'video')
                   for item in self.database[file_type].values()
                   if item.get(u'auto_sync'))

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

class PlayMovie(FrontendMessage):
    """Starts playing a specific movie.
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
    def __init__(self, target, remaining, eta, total):
        self.target = target
        self.remaining = remaining
        self.eta = eta
        self.total = total
