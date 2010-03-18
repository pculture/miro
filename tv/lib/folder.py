# Miro - an RSS based video player application
# Copyright (C) 2005-2010 Participatory Culture Foundation
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

"""``miro.folder`` -- Holds ``Folder`` class and related things.
"""

import logging

from miro import feed
from miro import playlist
from miro.database import DDBObject, ObjectNotFoundError
from miro.databasehelper import make_simple_get_set

class FolderBase(DDBObject):
    """Base class for ChannelFolder and Playlist folder classes."""

    def setup_new(self, title):
        self.title = title
        self.expanded = True

    get_title, set_title = make_simple_get_set('title')

    def get_expanded(self):
        """Returns whether or not this folder is expanded in the ui.
        """
        self.confirm_db_thread()
        return self.expanded

    def set_expanded(self, new_expanded):
        """Changes the expanded status for this folder in the ui.
        """
        self.confirm_db_thread()
        self.expanded = new_expanded
        self.signal_change()
        for child in self.get_children_view():
            child.signal_change(needs_save=False)

    def remove(self, move_items_to=None):
        """Remove this folder and children.
        """
        raise NotImplementedError()

    # get_folder and set_folder are here so that channels/playlists
    # and folders have a consistent API.  They don't do much since we
    # don't allow nested folders.
    def get_folder(self):
        return None

    def set_folder(self, new_folder, signal_items=False):
        if new_folder is not None:
            raise TypeError("Nested folders not allowed")

    def get_children_view(self):
        """Return the children of this folder.
        """
        raise NotImplementedError()

class ChannelFolder(FolderBase):
    def setup_new(self, title, section=u'video'):
        self.section = section
        FolderBase.setup_new(self, title)

    def remove(self, move_items_to=None):
        """Removes this folder passing ``move_items_to`` to
        :func:miro.feed.Feed.remove.
        """
        children = list(self.get_children_view())
        for child in children:
            if child.is_watched_folder():
                child.set_visible(False) # just hide watched folders
                child.set_folder(None)
            else:
                child.remove(move_items_to)
        DDBObject.remove(self)

    @classmethod
    def video_view(cls):
        """Returns all 'video' folders.
        """
        return cls.make_view("section='video'")

    @classmethod
    def audio_view(cls):
        """Returns all 'audio' folders.
        """
        return cls.make_view("section='audio'")

    @classmethod
    def get_by_title(cls, title):
        """Returns folder by title.
        """
        return cls.make_view('title=?', (title,)).get_singleton()

    def get_children_view(self):
        """Returns all children of this folder.
        """
        return feed.Feed.folder_view(self.id)

    def has_downloaded_items(self):
        """True if this folder has feeds with downloaded items.
        """
        for mem in self.get_children_view():
            if mem.has_downloaded_items():
                return True
        return False

    def has_downloading_items(self):
        """True if this folder has feeds with downloading items.
        """
        for mem in self.get_children_view():
            if mem.has_downloading_items():
                return True
        return False

    def num_unwatched(self):
        """Returns number of unwatched items in feed.
        """
        unwatched = 0
        for child in self.get_children_view():
            unwatched += child.num_unwatched()
        return unwatched

    def num_available(self):
        """Returns number of available items in feed
        """
        available = 0
        for child in self.get_children_view():
            available += child.num_available()
        return available

    def mark_as_viewed(self):
        """Marks all children as viewed.
        """
        for child in self.get_children_view():
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
            map_ = view.get_singleton()
            map_.inc_count()
        except ObjectNotFoundError:
            cls(playlist_id, item_id)

    @classmethod
    def remove_item_id(cls, playlist_id, item_id):
        view = cls.make_view('playlist_id=? AND item_id=?',
                             (playlist_id, item_id))
        map_ = view.get_singleton()
        map_.dec_count()

class PlaylistFolder(FolderBase, playlist.PlaylistMixin):
    MapClass = PlaylistFolderItemMap

    def remove(self, move_items_to=None):
        children = list(self.get_children_view())
        for child in children:
            child.remove(move_items_to)
        DDBObject.remove(self)

    def get_children_view(self):
        return playlist.SavedPlaylist.folder_view(self.id)

def fix_playlist_missing_item_ids():
    for map in PlaylistFolderItemMap.make_view("item_id NOT IN "
            "(SELECT id FROM item)"):
        logging.warn("playlist folder item map %s refers to missing item (%s)",
                map.id, map.item_id)
        map.remove()
    for map in PlaylistFolderItemMap.make_view("playlist_id NOT IN "
            "(SELECT id FROM playlist_folder)"):
        logging.warn("playlist folder item map %s refers to missing folder (%s)",
                map.id, map.playlist_id)
        map.remove()
