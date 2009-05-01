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

from miro import feed
from miro import playlist
from miro import sorts
from miro import util
from miro.database import DDBObject, ObjectNotFoundError
from miro.databasehelper import make_simple_get_set

class FolderBase(DDBObject):
    """Base class for ChannelFolder and Playlist folder classes."""

    def setup_new(self, title):
        self.title = title
        self.expanded = True

    get_title, set_title = make_simple_get_set('title')

    def getExpanded(self):
        self.confirm_db_thread()
        return self.expanded

    def setExpanded(self, newExpanded):
        self.confirm_db_thread()
        self.expanded = newExpanded
        self.signal_change()
        for child in self.getChildrenView():
            child.signal_change(needsSave=False)

    def remove(self, moveItemsTo=None):
        children = list(self.getChildrenView())
        for child in children:
            child.remove(moveItemsTo)
        DDBObject.remove(self)

    # get_folder and set_folder are here so that channels/playlists and folders
    # have a consistent API.  They don't do much since we don't allow nested
    # folders.
    def get_folder(self):
        return None

    def set_folder(self, newFolder):
        if newFolder is not None:
            raise TypeError("Nested folders not allowed")

    def getChildrenView(self):
        """Return the children of this folder."""
        raise NotImplementedError()

class ChannelFolder(FolderBase):
    def setup_new(self, title, section=u'video'):
        self.section = section
        FolderBase.setup_new(self, title)
        self.setup_common()

    def setup_restored(self):
        self.setup_common()

    def setup_common(self):
        self.itemSort = sorts.ItemSort()
        self.itemSortDownloading = sorts.ItemSort()
        self.itemSortWatchable = sorts.ItemSortUnwatchedFirst()

    @classmethod
    def video_view(cls):
        return cls.make_view("section='video'")

    @classmethod
    def audio_view(cls):
        return cls.make_view("section='audio'")

    def getChildrenView(self):
        return feed.Feed.folder_view(self.id)

    def hasDownloadedItems(self):
        for feed in self.getChildrenView():
            if feed.hasDownloadedItems():
                return True
        return False

    def hasDownloadingItems(self):
        for feed in self.getChildrenView():
            if feed.hasDownloadingItems():
                return True
        return False

    # Returns string with number of unwatched videos in feed
    def num_unwatched(self):
        unwatched = 0
        for child in self.getChildrenView():
            unwatched += child.num_unwatched()
        return unwatched

    # Returns string with number of available videos in feed
    def num_available(self):
        available = 0
        for child in self.getChildrenView():
            available += child.num_available()
        return available

    def mark_as_viewed(self):
        for child in self.getChildrenView():
            child.mark_as_viewed()

class PlaylistFolderItemMap(playlist.PlaylistItemMap):
    """Single row in the map that associates playlist folders with their 
    child items.
    """
    def setup_new(self, playlist_id, item_id):
        playlist.PlaylistItemMap.setup_new(self, playlist_id, item_id)
        self.count = 1

    def inc_count(self):
        self.count += 1
        self.signal_change()

    def dec_count(self):
        if self.count > 1:
            self.count -= 1
            self.signal_change()
        else:
            self.remove()

    @classmethod
    def add_item_id(cls, playlist_id, item_id):
        view = cls.make_view('playlist_id=? AND item_id=?',
                (playlist_id, item_id))
        try:
            map = view.get_singleton()
            map.inc_count()
        except ObjectNotFoundError:
            cls(playlist_id, item_id)

    @classmethod
    def remove_item_id(cls, playlist_id, item_id):
        view = cls.make_view('playlist_id=? AND item_id=?',
                (playlist_id, item_id))
        map = view.get_singleton()
        map.dec_count()

class PlaylistFolder(FolderBase, playlist.PlaylistMixin):
    MapClass = PlaylistFolderItemMap

    def getChildrenView(self):
        return playlist.SavedPlaylist.folder_view(self.id)
