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

"""Miro playlist support."""

from miro.gtcache import gettext as _

from miro import app
from miro import dialogs
from miro import database
from miro import filters
from miro import item
from miro import views
from miro import sorts
from miro.databasehelper import makeSimpleGetSet, TrackedIDList

class PlaylistMixin:
    """Class that handles basic playlist functionality.  PlaylistMixin is used
    by both SavedPlaylist and folder.PlaylistFolder.
    """

    def setupTrackedItemView(self):
        self.trackedItems = TrackedIDList(views.items, self.item_ids)
        views.items.addRemoveCallback(self.onItemRemoved)

    def onItemRemoved(self, obj, id):
        if id in self.trackedItems:
            self.trackedItems.removeID(id)

    def getItems(self):
        """Get the items in this playlist."""
        self.confirmDBThread()
        return [i for i in self.getView()]

    def getView(self):
        return self.trackedItems.view

    def setSearch(self, searchTerms):
        """Set a search to limit the items in this playlist.  

        NOTE: When this is called by the template code, it will change the
        results of getView() and getItems().  I (BDK), feel like this is a
        kind of ugly design, but I don't want to change things right now,
        because that would involve extra sorts on the playlist view.  Right
        now the only time we use getView() is in the template code, so I
        didn't want to fix an issue that doesn't matter.
        """

        def searchFilter(obj):
            return filters.matchingItems(obj, searchTerms)
        self.trackedItems.setFilter(searchFilter)
    
    def getFolder(self):
        return None

    def addID(self, id):
        """Add a new item to end of the playlist.  """
        self.confirmDBThread()
        item = views.items.getObjectByID(id)
        item.save()
        if id not in self.trackedItems:
            self.trackedItems.appendID(id)

        folder = self.getFolder()
        if (folder is not None):
            folder.addID(id)

        self.signalChange()

    def removeID(self, id):
        """Remove an item from the playlist."""

        self.confirmDBThread()
        self.trackedItems.removeID(id)

        folder = self.getFolder()
        if (folder is not None):
            folder.addID(id)

        self.signalChange()

    def moveID(self, id, newPosition):
        """Change the position of an item in the playlist.

        This method works the same as list.insert().  The item will be
        inserted at the index newPosition, items that are currently at that
        index or after it will be moved back one position.  If new position is
        after the end of the list, the item will be added at the end, if it's
        less than 0 it will be added at the begining.
        """

        self.confirmDBThread()
        self.trackedItems.moveID(id, newPosition)
        self.signalChange()

    def addItem(self, item):
        return self.addID(item.getID())

    def removeItem(self, item):
        return self.removeID(item.getID())

    def moveItem(self, item, newPosition):
        return self.moveID(item.getID(), newPosition)

    def handleDNDAppend(self, draggedIDs):
        for id in draggedIDs:
            if not views.items.idExists(id):
                raise KeyError("%s is not an item id" % id)
            item = views.items.getObjectByID(id)
            if not item.isContainerItem:
                self.addID(id)
            else:
                for child in item.getChildren():
                    self.addID(child.getID())

    def handleDNDReorder(self, anchorItem, draggedItems):
        """Handle drag-and-drop reordering of the playlist."""
        for iid in draggedItems:
            if iid not in self.trackedItems:
                raise ValueError("id not in playlist folder: %s", iid)
        if anchorItem is not None:
            self.trackedItems.moveIDList(draggedItems, anchorItem.getID())
        else:
            self.trackedItems.moveIDList(draggedItems, None)
        self.signalChange()
        
    def recomputeSort(self):
        self.trackedItems.recomputeSort()

class SavedPlaylist(database.DDBObject, PlaylistMixin):
    """An ordered list of videos that the user has saved.

    This class is called SavedPlaylist to distinguish it from app.Playlist,
    which is a temporary playlist that holds the videos we're playing right
    now.
    """
    def __init__(self, title, item_ids=None):
        self.title = title
        if item_ids:
            self.item_ids = item_ids
        else:
            self.item_ids = []
        self.folder_id = None
        self.setupTrackedItemView()
        database.DDBObject.__init__(self)

    def onRestore(self):
        database.DDBObject.onRestore(self)
        self.setupTrackedItemView()

    getTitle, setTitle = makeSimpleGetSet('title')

    def getFolder(self):
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
        self.signalChange()
        if old_folder_id is not None:
            folder = views.playlistFolders.getObjectByID(old_folder_id)
            for id in self.item_ids:
                folder.checkItemIDRemoved(id)

    def handleRemove(self, ids):
        """Handle the user removing a set of IDs.  This method will also check
        the playlist folder we're in and remove the ID from there.
        """

        for id in ids:
            self.removeID(id)
        folder = self.getFolder()
        if folder:
            for id in ids:
                folder.checkItemIDRemoved(id)

    def getDragDestType(self):
        self.confirmDBThread()
        if self.folder_id is not None:
            return 'playlist'
        else:
            return 'playlist:playlistfolder'

    def rename(self):
        title = _("Rename Playlist")
        description = _("Enter a new name for the playlist %s" % self.getTitle())

        def callback(dialog):
            if self.idExists() and dialog.choice == dialogs.BUTTON_OK:
                self.setTitle(dialog.value)
        dialogs.TextEntryDialog(title, description, dialogs.BUTTON_OK,
                dialogs.BUTTON_CANCEL).run(callback)

    # This allows playlists to be used in the same context as folders
    # in certain places, but still catches logic problem. Maybe
    # eventually, playlists and folders should derive from the same
    # parent --NN
    def remove(self,moveItemsTo=None):
        if moveItemsTo is not None:
            raise StandardError("Cannot 'move' a playlist to %s" % repr(moveItemsTo))
        database.DDBObject.remove(self)

def createNewPlaylist(childIDs=None):
    """Start the new playlist creation process.  This should be called in
    response to the user clicking on the new playlist menu option.
    """

    title = _("Create Playlist")
    description = _("Enter a name for the new playlist")

    def callback(dialog):
        if dialog.choice == dialogs.BUTTON_CREATE:
            playlist = SavedPlaylist(dialog.value)
            app.selection.selectTabByObject(playlist)
            if childIDs:
                playlist.handleDNDAppend(childIDs)

    dialogs.TextEntryDialog(title, description, dialogs.BUTTON_CREATE,
            dialogs.BUTTON_CANCEL).run(callback)
