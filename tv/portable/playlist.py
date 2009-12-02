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

"""``miro.playlist`` -- Miro playlist support.
"""

from miro.gtcache import gettext as _

from miro import dialogs
from miro import database
from miro import models
from miro.databasehelper import make_simple_get_set

class PlaylistItemMap(database.DDBObject):
    """Single row in the map that associates playlists with their child items.
    """

    def setup_new(self, playlist_id, item_id):
        self.playlist_id = playlist_id
        self.item_id = item_id
        rows = self.select('MAX(position+1)', 'playlist_id=?', (playlist_id,))
        self.position = rows[0][0]
        if self.position is None:
            self.position = 0

    @classmethod
    def playlist_view(cls, playlist_id):
        return cls.make_view("playlist_id=?", (playlist_id,))

    @classmethod
    def remove_item_from_playlists(cls, item):
        cls.delete('item_id=?', (item.id,))

    @classmethod
    def add_item_id(cls, playlist_id, item_id):
        cls(playlist_id, item_id)

    @classmethod
    def remove_item_id(cls, playlist_id, item_id):
        cls.delete('playlist_id=? AND item_id=?', (playlist_id, item_id))

class PlaylistMixin:
    """Class that handles basic playlist functionality.  PlaylistMixin is used
    by both SavedPlaylist and folder.PlaylistFolder.
    """

    MapClass = None # subclasses must override this

    def get_folder(self):
        return None

    def add_id(self, item_id):
        """Add a new item to end of the playlist.  """
        self.MapClass.add_item_id(self.id, item_id)
        item = models.Item.get_by_id(item_id)
        item.save()

        folder = self.get_folder()
        if folder is not None:
            folder.add_id(item_id)

    def remove_id(self, item_id, signal_change=True):
        """Remove an item from the playlist."""
        try:
            self.MapClass.remove_item_id(self.id, item_id)
        except database.ObjectNotFoundError:
            # if the item isn't in the playlist, then we move along
            # because there's nothing to change.
            return
        folder = self.get_folder()
        if folder is not None:
            folder.remove_id(item_id)
        if signal_change:
            item = models.Item.get_by_id(item_id)
            item.signal_change(needsSave=False)

    def add_item(self, item):
        """Add an item to the end of the playlist"""
        return self.add_id(item.id)

    def remove_item(self, item, signal_change=True):
        """remove an item from the playlist"""
        return self.remove_id(item.id, signal_change)

    def contains_id(self, item_id):
        view = self.MapClass.make_view('playlist_id=? AND item_id=?',
                (self.id, item_id))
        return view.count() > 0

    def reorder(self, new_order):
        """reorder items in the playlist.  new_order should contain a list of
        ids one for each item in the playlist.
        """
        for i, item_id in enumerate(new_order):
            map = self.MapClass.make_view('playlist_id=? AND item_id=?',
                    (self.id, item_id)).get_singleton()
            map.position = i
            map.signal_change()

class SavedPlaylist(database.DDBObject, PlaylistMixin):
    """An ordered list of videos that the user has saved.

    This class is called SavedPlaylist to distinguish it from app.Playlist,
    which is a temporary playlist that holds the videos we're playing right
    now.
    """
    MapClass = PlaylistItemMap

    def setup_new(self, title, item_ids=None):
        self.title = title
        self.folder_id = None
        if item_ids is not None:
            for id in item_ids:
                self.add_id(id)

    @classmethod
    def folder_view(cls, id):
        return cls.make_view('folder_id=?', (id,))

    @classmethod
    def get_by_title(cls, title):
        return cls.make_view('title=?', (title,)).get_singleton()

    def add_id(self, item_id):
        # Don't allow items to be added more than once.
        view = PlaylistItemMap.make_view('playlist_id=? AND item_id=?',
                (self.id, item_id))
        if view.count() == 0:
            PlaylistMixin.add_id(self, item_id)

    get_title, set_title = make_simple_get_set('title')

    def get_folder(self):
        self.confirm_db_thread()
        if self.folder_id is not None:
            return models.PlaylistFolder.get_by_id(self.folder_id)
        else:
            return None

    def _remove_ids_from_folder(self):
        folder = self.get_folder()
        if folder is not None:
            for map in PlaylistItemMap.playlist_view(self.id):
                try:
                    folder.remove_id(map.item_id)
                except database.ObjectNotFoundError:
                    continue

    def _add_ids_to_folder(self):
        folder = self.get_folder()
        if folder is not None:
            for map in PlaylistItemMap.playlist_view(self.id):
                folder.add_id(map.item_id)

    def set_folder(self, new_folder, update_trackers=True):
        self.confirm_db_thread()
        self._remove_ids_from_folder()
        if new_folder is not None:
            self.folder_id = new_folder.get_id()
        else:
            self.folder_id = None
        self.signal_change()
        self._add_ids_to_folder()
        if update_trackers:
            models.Item.update_folder_trackers()

    @staticmethod
    def bulk_set_folders(new_folders):
        for child, parent in new_folders:
            child.set_folder(parent, update_trackers=False)
        models.Item.update_folder_trackers()

    def rename(self):
        title = _("Rename Playlist")
        description = _("Enter a new name for the playlist %s" % self.get_title())

        def callback(dialog):
            if self.idExists() and dialog.choice == dialogs.BUTTON_OK:
                self.set_title(dialog.value)
        dialogs.TextEntryDialog(title, description, dialogs.BUTTON_OK,
                dialogs.BUTTON_CANCEL).run(callback)

    # Accepting moveItemsTo, but forcing it to be false allows playlists to be
    # used in the same context as folders in certain places, but still catches
    # logic problem. Maybe eventually, playlists and folders should derive
    # from the same parent --NN
    def remove(self, moveItemsTo=None):
        if moveItemsTo is not None:
            raise StandardError("Cannot 'move' a playlist to %s" % repr(moveItemsTo))
        self._remove_ids_from_folder()
        database.DDBObject.remove(self)
