"""Democracy playlist support."""

from gtcache import gettext as _

import app
import dialogs
import database
import views
from databasehelper import makeSimpleGetSet, TrackedIDList

class SavedPlaylist(database.DDBObject):
    """An ordered list of videos that the user has saved.

    This class is called SavedPlaylist to distinguish it from app.Playlist,
    which is a temporary playlist that holds the videos we're playing right
    now.
    """

    def __init__(self, title, items=None, expanded=False):
        self.title = title
        self.expanded = expanded
        if items is not None:
            self.item_ids = [i.getID() for i in items]
        else:
            self.item_ids = []
        self.trackedItems = TrackedIDList(views.items, self.item_ids)
        database.DDBObject.__init__(self)

    def onRestore(self):
        self.trackedItems = TrackedIDList(views.items, self.item_ids)

    getTitle, setTitle = makeSimpleGetSet('title')
    getExpanded, setExpanded = makeSimpleGetSet('expanded')

    def getItems(self):
        """Get the items in this playlist."""
        self.confirmDBThread()
        return [i for i in self.getView()]

    def getView(self):
        """Get a database view for this playlist."""
        return self.trackedItems.view

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

    def handleDrop(self):
        """Called when something gets dropped onto this playlist."""

        selection = app.controller.selection
        selectionType = selection.getType()
        if selectionType == 'item':
            for id in selection.currentSelection:
                self.addID(id)
        else:
            raise ValueError("can't drop type %s onto a playlist" %
                    selectionType)

def createNewPlaylist():
    """Start the new playlist creation process.  This should be called in
    response to the user clicking on the new playlist menu option.
    """

    title = _("Create Playlist")
    description = _("Enter a name for the new playlist")

    def callback(dialog):
        if dialog.choice == dialogs.BUTTON_CREATE:
            SavedPlaylist(dialog.value)

    dialogs.TextEntryDialog(title, description, dialogs.BUTTON_CREATE,
            dialogs.BUTTON_CANCEL).run(callback)
