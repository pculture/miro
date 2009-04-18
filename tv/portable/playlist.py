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

"""Miro playlist support."""

from miro.gtcache import gettext as _

from miro import dialogs
from miro import database
from miro import views
from miro.databasehelper import makeSimpleGetSet, TrackedIDList

class PlaylistMixin:
    """Class that handles basic playlist functionality.  PlaylistMixin is used
    by both SavedPlaylist and folder.PlaylistFolder.
    """

    def setupTrackedItemView(self):
        self.trackedItems = TrackedIDList(views.items, self.item_ids)
        views.items.addRemoveCallback(self.onItemRemoved)
        for id in self.item_ids:
            _playlist_id_added(self, id)

    def onItemRemoved(self, obj, id):
        if id in self.trackedItems:
            self.trackedItems.removeID(id)
        self.signal_changed()

    def getItems(self):
        """Get the items in this playlist."""
        self.confirmDBThread()
        return [i for i in self.getView()]

    def getView(self):
        return self.trackedItems.view

    def get_folder(self):
        return None

    def addID(self, id):
        """Add a new item to end of the playlist.  """
        self.confirmDBThread()
        item = views.items.getObjectByID(id)
        item.save()
        if id not in self.trackedItems:
            self.trackedItems.appendID(id)

        folder = self.get_folder()
        if (folder is not None):
            folder.addID(id)

        _playlist_id_added(self, id)
        self.signal_change()

    def removeID(self, id):
        """Remove an item from the playlist."""

        self.confirmDBThread()
        self.trackedItems.removeID(id)

        folder = self.get_folder()
        if (folder is not None):
            folder.addID(id)

        _playlist_id_removed(self, id)
        self.signal_change()

    def moveID(self, id, newPosition):
        """Change the position of an item in the playlist.

        This method works the same as list.insert().  The item will be
        inserted at the index newPosition, items that are currently at that
        index or after it will be moved back one position.  If new position is
        after the end of the list, the item will be added at the end, if it's
        less than 0 it will be added at the beginning.
        """

        self.confirmDBThread()
        self.trackedItems.moveID(id, newPosition)
        self.signal_change()

    def idInPlaylist(self, id):
        return id in self.trackedItems

    def addItem(self, item):
        return self.addID(item.getID())

    def removeItem(self, item):
        return self.removeID(item.getID())

    def moveItem(self, item, newPosition):
        return self.moveID(item.getID(), newPosition)

    def reorder(self, newOrder):
        self.trackedItems.reorder(newOrder)

    def recomputeSort(self):
        self.trackedItems.recomputeSort()

class SavedPlaylist(database.DDBObject, PlaylistMixin):
    """An ordered list of videos that the user has saved.

    This class is called SavedPlaylist to distinguish it from app.Playlist,
    which is a temporary playlist that holds the videos we're playing right
    now.
    """
    def setup_new(self, title, item_ids=None):
        self.title = title
        if item_ids:
            self.item_ids = item_ids
        else:
            self.item_ids = []
        self.folder_id = None
        self.setup_common()

    def setup_restored(self):
        self.setup_common()

    def setup_common(self):
        self.setupTrackedItemView()

    @classmethod
    def folder_view(cls, id):
        return cls.make_view('folder_id=?', (id,))

    get_title, set_title = makeSimpleGetSet('title')

    def get_folder(self):
        self.confirmDBThread()
        if self.folder_id is not None:
            return self.dd.getObjectByID(self.folder_id)
        else:
            return None

    def setFolder(self, newFolder):
        self.confirmDBThread()
        old_folder_id = self.folder_id
        if newFolder is not None:
            self.folder_id = newFolder.getID()
        else:
            self.folder_id = None
        self.signal_change()
        if old_folder_id is not None:
            folder = views.playlistFolders.getObjectByID(old_folder_id)
            folder.check_for_removed_ids()
        if newFolder:
            for id in self.item_ids:
                newFolder.checkItemIDAdded(id)

    def handleRemove(self, ids):
        """Handle the user removing a set of IDs.  This method will also check
        the playlist folder we're in and remove the ID from there.
        """

        for id in ids:
            self.removeID(id)
        folder = self.get_folder()
        if folder:
            folder.check_for_removed_ids()

    def rename(self):
        title = _("Rename Playlist")
        description = _("Enter a new name for the playlist %s" % self.get_title())

        def callback(dialog):
            if self.idExists() and dialog.choice == dialogs.BUTTON_OK:
                self.set_title(dialog.value)
        dialogs.TextEntryDialog(title, description, dialogs.BUTTON_OK,
                dialogs.BUTTON_CANCEL).run(callback)

    # This allows playlists to be used in the same context as folders
    # in certain places, but still catches logic problem. Maybe
    # eventually, playlists and folders should derive from the same
    # parent --NN
    def remove(self, moveItemsTo=None):
        if moveItemsTo is not None:
            raise StandardError("Cannot 'move' a playlist to %s" % repr(moveItemsTo))
        database.DDBObject.remove(self)

_id_map = {} # map item ids to sets of playlists that contain them

def playlist_set_for_item_id(id):
    try:
        return _id_map[id]
    except KeyError:
        playlist_set = set()
        _id_map[id] = playlist_set
        return playlist_set

def _playlist_id_added(playlist, id):
    playlist_set_for_item_id(id).add(playlist)

def _playlist_id_removed(playlist, id):
    playlist_set_for_item_id(id).discard(playlist)
