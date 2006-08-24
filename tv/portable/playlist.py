"""Democracy playlist support."""

from gtcache import gettext as _

import app
import dialogs
import database
import filters
import item
import views
from databasehelper import makeSimpleGetSet, TrackedIDList

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
        def searchFilter(obj):
            return filters.matchingItems(obj, searchTerms)
        self.trackedItems.setFilter(searchFilter)

    def addID(self, id):
        """Add a new item to end of the playlist.  """
        self.confirmDBThread()
        item = views.items.getObjectByID(id)
        item.save()
        if id not in self.trackedItems:
            self.trackedItems.appendID(id)
        self.signalChange()

    def removeID(self, id):
        """Remove an item from the playlist."""

        self.confirmDBThread()
        self.trackedItems.removeID(id)
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
            self.addID(id)

    def handleDNDReorder(self, anchorItem, draggedItems):
        """Handle drag-and-drop reordering of the playlist."""
        for id in draggedItems:
            if id not in self.trackedItems:
                raise ValueError("id not in playlist folder: %s", sourceID)
        if anchorItem is not None:
            self.trackedItems.moveIDList(draggedItems, anchorItem.getID())
        else:
            self.trackedItems.moveIDList(draggedItems, None)
        self.signalChange()

class SavedPlaylist(database.DDBObject, PlaylistMixin):
    """An ordered list of videos that the user has saved.

    This class is called SavedPlaylist to distinguish it from app.Playlist,
    which is a temporary playlist that holds the videos we're playing right
    now.
    """

    def __init__(self, title, items=None):
        self.title = title
        if items is not None:
            self.item_ids = [i.getID() for i in items]
        else:
            self.item_ids = []
        self.folder_id = None
        self.setupTrackedItemView()
        database.DDBObject.__init__(self)

    def onRestore(self):
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

def createNewPlaylist(childIDs=None):
    """Start the new playlist creation process.  This should be called in
    response to the user clicking on the new playlist menu option.
    """

    title = _("Create Playlist")
    description = _("Enter a name for the new playlist")

    def callback(dialog):
        if dialog.choice == dialogs.BUTTON_CREATE:
            playlist = SavedPlaylist(dialog.value)
            app.controller.selection.selectTabByObject(playlist)
            if childIDs:
                playlist.handleDNDAppend(childIDs)

    dialogs.TextEntryDialog(title, description, dialogs.BUTTON_CREATE,
            dialogs.BUTTON_CANCEL).run(callback)
