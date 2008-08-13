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

"""messages.py -- Message passing between the frontend thread and the backend
thread.

The backend thread is the eventloop, which processes things like feed updates
and handles reading and writing to the database.  The frontend thread is the
thread of the UI toolkit we're using.  Communication between the two threads
is handled by passing messages between the two.  These messages are handled
asynchronously.

This module defines the messages that are passed between the two threads.
"""

import logging
import re
import urlparse

from miro import license
from miro.folder import ChannelFolder, PlaylistFolder
from miro.plat import resources
from miro import util

class MessageHandler(object):
    def __init__(self):
        self.message_map = {} # maps message classes to method names
        self.complained_about = set()

    def call_handler(self, method, message):
        """Arrange for a message handler method to be called in the correct
        thread.  Must be implemented by subclasses.
        """
        raise NotImplementedError()

    def handle(self, message):
        handler_name = self.get_message_handler_name(message)
        try:
            handler = getattr(self, handler_name)
        except AttributeError:
            if handler_name not in self.complained_about:
                logging.warn("MessageHandler doesn't have a %s method "
                        "to handle the %s message" % (handler_name,
                            message.__class__))
                self.complained_about.add(handler_name)
        else:
            self.call_handler(handler, message)

    def get_message_handler_name(self, message):
        try:
            return self.message_map[message.__class__]
        except KeyError:
            self.message_map[message.__class__] = \
                    self.calc_message_handler_name(message.__class__)
            return self.message_map[message.__class__]

    def calc_message_handler_name(self, message_class):
        def replace(match):
            return '%s_%s' % (match.group(1), match.group(2).lower())
        underscores = re.sub(r'([a-z])([A-Z])', replace,
                message_class.__name__)
        return 'handle_' + underscores.lower()


class Message(object):
    """Base class for all Messages."""

    @classmethod
    def install_handler(cls, handler):
        """Install a new message handler for this class.  When
        send_to_frontend() or send_to_backend() is called, this handler will
        be invoked.
        """
        cls.handler = handler

class BackendMessage(Message):
    """Base class for Messages that get sent to the backend."""

    def send_to_backend(self):
        try:
            handler = self.handler
        except AttributeError:
            logging.warn("No handler for backend messages")
        else:
            handler.handle(self)


class FrontendMessage(Message):
    """Base class for Messages that get sent to the frontend."""

    def send_to_frontend(self):
        try:
            handler = self.handler
        except AttributeError:
            logging.warn("No handler for frontend messages")
        else:
            handler.handle(self)

# Backend Messages

class TrackChannels(BackendMessage):
    """Begin tracking channels.

    After this message is sent, the backend will send back a ChannelList
    message, then it will send ChannelsChanged messages whenever the channel
    list changes.
    """
    pass

class StopTrackingChannels(BackendMessage):
    """Stop tracking channels."""
    pass

class TrackPlaylists(BackendMessage):
    """Begin tracking playlists.

    After this message is sent, the backend will send back a PlaylistList
    message, then it will send PlaylistsChanged messages whenever the list of
    playlists changes.
    """
    pass

class StopTrackingPlaylists(BackendMessage):
    """Stop tracking playlists."""
    pass

class TrackGuides(BackendMessage):
    """Begin tracking guides.

    After this message is sent, the backend will send back a GuideList
    message, then it will send GuidesChanged messages whenever the guide
    list changes.
    """
    pass

class StopTrackingGuides(BackendMessage):
    """Stop tracking guides."""
    pass

class TrackItems(BackendMessage):
    """Begin tracking items for a feed

    After this message is sent, the backend will send back a ItemList message,
    then it will send ItemsChanged messages for items in the feed.

    type is the type of object that we are tracking items for.  It can be one
    of the following:

    'feed' -- Items in a feed
    'playlist' - Items in a playlist
    'new' -- Items that haven't been watched
    'downloading' -- Items being downloaded
    'library' -- All items

    id should be the id of a feed/playlist. For new, downloading and library
    it is ignored.
    """

    def __init__(self, type, id):
        self.type = type
        self.id = id

class StopTrackingItems(BackendMessage):
    """Stop tracking items for a feed."""

    def __init__(self, type, id):
        self.type = type
        self.id = id

class TrackDownloadCount(BackendMessage):
    """Start tracking the number of downloading items.  After this message is
    recieved the backend will send a corresponding DownloadCountChanged
    message.  It will also send DownloadCountChanged whenever the count
    changes.
    """
    pass

class StopTrackingDownloadCount(BackendMessage):
    """Stop tracking the download count."""
    pass

class TrackNewCount(BackendMessage):
    """Start tracking the number of new videos.  When this message is recieved
    the backend will send a corresponding NewCountChanged message.  It will
    also send NewCountChanged.
    """
    pass

class StopTrackingNewCount(BackendMessage):
    """Stop tracking the new videos count."""
    pass

class ImportChannels(BackendMessage):
    """Tell the backend to import channels from an .opml file.

    Attributes:
    filename -- file name that exists
    """
    def __init__(self, filename):
        self.filename = filename

class ExportChannels(BackendMessage):
    """Tell the backend to export channels to an .opml file.

    Attributes:
    filename -- file name to export to
    """
    def __init__(self, filename):
        self.filename = filename

class RenameObject(BackendMessage):
    """Tell the backend to rename a channel/playlist/folder.
    
    Attributes:
    type -- 'feed', 'playlist', 'feed-folder' or 'playlist-folder'
    id  -- id of the object to rename
    new_name -- new name for the object
    """
    def __init__(self, type, id, new_name):
        self.type = type
        self.id = id
        self.new_name = util.toUni(new_name)

class UpdateChannel(BackendMessage):
    """Updates a channel."""
    def __init__(self, id):
        self.id = id

class MarkChannelSeen(BackendMessage):
    """Mark a channel as seen"""
    def __init__(self, id):
        self.id = id

class MarkItemWatched(BackendMessage):
    """Mark an item as watched"""
    def __init__(self, id):
        self.id = id

class MarkItemUnwatched(BackendMessage):
    """Mark an item as unwatched"""
    def __init__(self, id):
        self.id = id

class UpdateAllChannels(BackendMessage):
    """Updates all channels."""
    pass

class DeleteChannel(BackendMessage):
    """Delete a channel."""
    def __init__(self, id, is_folder, keep_items):
        self.id = id
        self.is_folder = is_folder
        self.keep_items = keep_items

class DeletePlaylist(BackendMessage):
    """Delete a playlist."""
    def __init__(self, id, is_folder):
        self.id = id
        self.is_folder = is_folder

class DeleteSite(BackendMessage):
    """Delete an external channel guide."""
    def __init__(self, id):
        self.id = id

class NewGuide(BackendMessage):
    """Create a new channel guide.
    """
    def __init__(self, url):
        self.url = util.toUni(url)

class NewChannel(BackendMessage):
    """Create a new channel."""
    def __init__(self, url, trackback=None):
        self.url = util.toUni(url)
        self.trackback = trackback

class NewChannelSearchChannel(BackendMessage):
    """Creates a new channel based on a search through a channel."""
    def __init__(self, channel_info, search_term):
        self.channel_info = channel_info
        self.search_term = search_term

class NewChannelSearchEngine(BackendMessage):
    """Creates a new channel from a search engine."""
    def __init__(self, search_engine_info, search_term):
        self.search_engine_info = search_engine_info
        self.search_term = search_term

class NewChannelSearchURL(BackendMessage):
    """Creates a new channel from a url."""
    def __init__(self, url, search_term):
        self.url = url
        self.search_term = search_term

class NewPlaylist(BackendMessage):
    """Create a new playlist."""
    def __init__(self, name, ids):
        self.name = util.toUni(name)
        self.ids = ids

class NewChannelFolder(BackendMessage):
    """Create a new channel folder."""
    def __init__(self, name):
        self.name = util.toUni(name)

class NewPlaylistFolder(BackendMessage):
    """Create a new channel folder."""
    def __init__(self, name):
        self.name = util.toUni(name)

class AddVideosToPlaylist(BackendMessage):
    def __init__(self, playlist_id, video_ids):
        self.playlist_id = playlist_id
        self.video_ids = video_ids

class RemoveVideosFromPlaylist(BackendMessage):
    def __init__(self, playlist_id, video_ids):
        self.playlist_id = playlist_id
        self.video_ids = video_ids

class DownloadURL(BackendMessage):
    def __init__(self, url):
        self.url = util.toUni(url)

class Search(BackendMessage):
    """Search a search engine with a search term."""
    def __init__(self, searchengine_id, terms):
        self.id = searchengine_id
        self.terms = terms

class StartDownload(BackendMessage):
    """Start downloading an item."""
    def __init__(self, id):
        self.id = id

class CancelDownload(BackendMessage):
    """Cancel downloading an item."""
    def __init__(self, id):
        self.id = id

class PauseAllDownloads(BackendMessage):
    """Pauses all downloading items."""
    pass

class PauseDownload(BackendMessage):
    """Pause downloading an item."""
    def __init__(self, id):
        self.id = id

class ResumeAllDownloads(BackendMessage):
    """Resumes all downloading items."""
    pass

class ResumeDownload(BackendMessage):
    """Resume downloading an item."""
    def __init__(self, id):
        self.id = id

class RestartUpload(BackendMessage):
    """Start uploading a torrent again."""
    def __init__(self, id):
        self.id = id

class KeepVideo(BackendMessage):
    """Cancel the auto-expiration of an item's video"""
    def __init__(self, id):
        self.id = id

class SaveItemAs(BackendMessage):
    """Saves an item in the dark clutches of Miro to somewhere else."""
    def __init__(self, id, filename):
        self.id = id
        self.filename = filename

class RemoveVideoEntry(BackendMessage):
    """Remove the entry for an external video"""
    def __init__(self, id):
        self.id = id

class DeleteVideo(BackendMessage):
    """Delete the video for an item's video"""
    def __init__(self, id):
        self.id = id

class RenameVideo(BackendMessage):
    """Renames the video"""
    def __init__(self, id, new_name):
        self.id = id
        self.new_name = new_name

class FolderExpandedChange(BackendMessage):
    """Inform the backend when a folder gets expanded/collapsed
    """
    def __init__(self, type, id, expanded):
        self.type = type
        self.id = id
        self.expanded = expanded

class AutodownloadChange(BackendMessage):
    """Inform the backend that the user changed the auto-download setting for
    a feed.  The possible setting values are "all", "new" and "off"
    """
    def __init__(self, id, setting):
        self.id = id
        self.setting = setting

class TabsReordered(BackendMessage):
    """Inform the backend when the channel tabs are rearanged.  This includes
    simple position changes and also changes to which folders the channels are
    in.

    Attributes:
    type -- 'playlist' or feed'
    toplevels -- the list of ChannelInfo objects without parents
    folder_children -- dict mapping channel folder ids to a list of
        ChannelInfo objects for their children
    """
    def __init__(self, type):
        self.type = type
        self.toplevels = []
        self.folder_children = {}

    def append(self, info):
        self.toplevels.append(info)
        if info.is_folder:
            self.folder_children[info.id] = []

    def append_child(self, parent_id, info):
        self.folder_children[parent_id].append(info)

class PlaylistReordered(BackendMessage):
    """Inform the backend when the items in a playlist are re-ordered.

    Attributes:
    id -- playlist that was re-ordered
    item_ids -- List of ids for item in the playlist, in their new order.
    """
    def __init__(self, id, item_ids):
        self.id = id
        self.item_ids = item_ids

class SubscriptionLinkClicked(BackendMessage):
    """Inform the backend that the user clicked on a subscription link in a
    web browser.
    """

    def __init__(self, url):
        self.url = url

# Frontend Messages
class ChannelInfo(object):
    """Tracks the state of a channel

    Attributes:

    name -- channel name
    url -- channel url (None for channel folders)
    id -- object id
    tab_icon -- path to this channel's tab icon
    thumbnail -- path to this channel's thumbnail
    unwatched -- number of unwatched videos
    available -- number of newly downloaded videos
    is_folder -- is this a channel folder?
    is_directory_feed -- is this channel a watched directory?
    has_downloading -- are videos currently being downloaded for this channel?
    base_href -- url to use for relative links for items in this channel.
      This will be None for ChannelFolders.
    autodownload_mode -- current autodownload mode ('all', 'new' or 'off')
    search_term -- the search term used for this feed or None
    """
    def __init__(self, channel_obj):
        self.name = channel_obj.getTitle()
        self.id = channel_obj.id
        self.unwatched = channel_obj.numUnwatched()
        self.available = channel_obj.numAvailable()
        self.has_downloading = channel_obj.hasDownloadingItems()
        if hasattr(channel_obj, "searchTerm"):
            self.search_term = channel_obj.searchTerm
        else:
            self.search_term = None
        if not isinstance(channel_obj, ChannelFolder):
            self.url = channel_obj.getURL()
            self.thumbnail = channel_obj.getThumbnailPath()
            self.base_href = channel_obj.getBaseHref()
            self.autodownload_mode = channel_obj.getAutoDownloadMode()
            self.is_folder = False
            self.tab_icon = resources.path('wimages/icon-rss.png')
            self.is_directory_feed = False
        else:
            self.url = None
            self.thumbnail = resources.path('wimages/folder-icon.png')
            self.autodownload_mode = self.base_href = None
            self.is_folder = True
            self.tab_icon = resources.path('wimages/icon-folder.png')
            self.is_directory_feed = (self.url is not None and 
                    self.url.startswith('dtv:directoryfeed'))

class PlaylistInfo(object):
    """Tracks the state of a playlist

    Attributes:

    name -- playlist name
    id -- object id
    is_folder -- is this a playlist folder?
    """

    def __init__(self, playlist_obj):
        self.name = playlist_obj.getTitle()
        self.id = playlist_obj.id
        self.is_folder = isinstance(playlist_obj, PlaylistFolder)

class GuideInfo(object):
    """Tracks the state of a channel guide

    Attributes:

    name -- channel name
    id -- object id
    url -- URL for the guide
    allowed_urls -- URLs that should be also considered part of the guide
    default -- is this the default channel guide?
    """
    def __init__(self, guide):
        self.name = guide.getTitle()
        self.id = guide.id
        self.url = guide.getURL()
        self.default = guide.getDefault()
        self.allowed_urls = guide.allowedURLs

class ItemInfo(object):
    """Tracks the state of an item

    Attributes:

    name -- name of the item
    id -- object id
    feed_id -- id for the items feed
    description -- longer description for the item (HTML)
    release_date -- datetime object when the item was published
    size -- size of the item in bytes
    duration -- length of the video in seconds
    permalink -- URL to a permalink to the item (or None)
    downloaded -- has the item been downloaded?
    is_external -- is this item external (true) or from a channel (false)?
    expiration_date -- datetime object for when the item will expire (or None)
    item_viewed -- has the user ever seen the item?
    video_watched -- has the user watched the video for the item?
    video_path -- the file path to the video for this item (or None)
    thumbnail -- path to the thumbnail for this file
    file_format -- User-facing format description.  Possibly the file type,
      pulled from the mime_type, or more generic, like "audio"
    license -- this file's license, if known.
    license_name -- user-facing license name
    file_type -- filetype of the enclosure that would be downloaded
    file_url -- URL of the enclosure that would be downloaded
    download_info -- DownloadInfo object containing info about the download
        (or None)
    is_container_item -- whether or not this item is actually a
        collection of files as opposed to an individual item
    """
    def __init__(self, item):
        self.name = item.getTitle()
        self.id = item.id
        self.feed_id = item.feed_id
        self.description = item.getDescription()
        self.release_date = item.getReleaseDateObj()
        self.size = item.getSize()
        self.duration = item.getDurationValue()
        self.permalink = item.getLink()
        if not item.keep:
            self.expiration_date = item.getExpirationTime()
        else:
            self.expiration_date = None
        self.item_viewed = item.getViewed()
        self.downloaded = item.isDownloaded()
        self.is_external = item.isExternal()
        self.video_watched = item.getSeen()
        self.video_path = item.getVideoFilename()
        self.thumbnail = item.getThumbnail()
        self.file_format = item.getFormat()
        self.license = item.getLicence()
        self.file_url = item.getURL()
        self.is_container_item = item.isContainerItem
        if urlparse.urlparse(self.license)[0]:
            self.license_name = license.license_name(self.license)
        else:
            self.license_name = None

        enclosure = item.getFirstVideoEnclosure()
        if enclosure:
            self.file_type = enclosure.get('type')
            self.file_url = enclosure.get('url')
        else:
            self.file_type = None
            self.file_url = None

        if item.downloader:
            self.download_info = DownloadInfo(item.downloader)
        else:
            self.download_info = None

class DownloadInfo(object):
    """Tracks the download state of an item.

    Attributes:

    downloaded_size -- bytes downloaded
    rate -- current download rate, in bytes per second
    state -- one of 'downloading', 'uploading', 'finished', 'failed' or 
        'paused'.  'uploading' is for torrents only.  It means that we've
        finished downloding the torrent and are now seeding it.
    startup_activity -- The current stage of starting up
    finished -- True if the item has finished downloading
    torrent -- Is this a Torrent download?
    """
    def __init__(self, downloader):
        self.downloaded_size = downloader.getCurrentSize()
        self.rate = downloader.getRate()
        self.state = downloader.getState()
        self.startup_activity = downloader.getStartupActivity()
        self.finished = downloader.isFinished()
        self.torrent = (downloader.getType() == 'bittorrent')

class GuideList(FrontendMessage):
    """Sends the frontend the initial list of channel guides

    Attributes:
    default_guide -- The Default channel guide
    guides -- list added channel guides
    """

    def __init__(self, guides):
        self.default_guide = None
        self.added_guides = []
        for guide in guides:
            if guide.default:
                if self.default_guide is not None:
                    raise ValueError("Multiple Default guides")
                self.default_guide = guide
            else:
                self.added_guides.append(guide)

class TabList(FrontendMessage):
    """Sends the frontend the initial list of channels and playlists

    Attributes:
    type -- 'feed' or 'playlist'
    toplevels -- the list of ChannelInfo/PlaylistInfo objects without parents
    folder_children -- dict mapping channel folder ids to a list of
        ChannelInfo/PlaylistInfo objects for their children
    expanded_folders -- set containing ids of the folders that should
        be initially expanded.
    """

    def __init__(self, type):
        self.type = type
        self.toplevels = []
        self.folder_children = {}
        self.expanded_folders = set()

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

    Attributes:
    type -- 'feed', playlist' or 'guide'
    added -- ChannelInfo/PlaylistInfo object for each added tab.  The list 
        will be in the same order that the tabs were added.
    changed -- list of ChannelInfo/PlaylistInfos for each changed tab.
    removed -- list of ids for each tab that was removed
    """

    def __init__(self, type, added, changed, removed):
        self.type = type
        self.added = added
        self.changed = changed
        self.removed = removed

class ItemList(FrontendMessage):
    """Sends the frontend the initial list of items for a feed

    Attributes:
    type -- type of object being tracked (same as in TrackItems)
    id -- id of the object being tracked (same as in TrackItems)
    items -- list of ItemInfo objects
    """
    def __init__(self, type, id, items):
        self.type = type
        self.id = id
        self.items = [ItemInfo(item) for item in items]

class ItemsChanged(FrontendMessage):
    """Informs the frontend that the items in a feed have changed.

    Attributes:
    type -- type of object being tracked (same as in TrackItems)
    id -- id of the object being tracked (same as in TrackItems)
    added -- list containing an ItemInfo object for each added item.  The
        order will be the order they were added.
    changed -- set containing an ItemInfo for each changed item.
    removed -- set containing ids for each item that was removed
    """

    def __init__(self, type, id, added, changed, removed):
        self.type = type
        self.id = id
        self.added = added
        self.changed = changed
        self.removed = removed

class DownloadCountChanged(FrontendMessage):
    """Informs the frontend that number of downloads has changed """

    def __init__(self, count):
        self.count = count

class NewCountChanged(FrontendMessage):
    """Informs the frontend that number of new videos has changed """

    def __init__(self, count):
        self.count = count
