"""Democracy playlist support."""

from gtcache import gettext as _

import dialogs
import database
import indexes
import views
from databasehelper import makeSimpleGetSet

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
            self.items = items
        else:
            self.items = []
        database.DDBObject.__init__(self)

    getTitle, setTitle = makeSimpleGetSet('title')
    getExpanded, setExpanded = makeSimpleGetSet('expanded')

    def getItems(self):
        """Get a view containing all the items in this playlist."""
        self.confirmDBThread()
        return self.items

    def addItem(self, item):
        """Add a new item to end of the playlist.  
        """
        self.confirmDBThread()
        self.items.append(item)
        self.signalChange()

    def removeItem(self, item):
        """Remove an item from the playlist."""

        self.confirmDBThread()
        self.items.remove(item)
        self.signalChange()

    def changeItemPosition(self, item, newPosition):
        """Change the position of an item in the playlist.

        This method works the same as list.insert().  The item will be
        inserted at the index newPosition, items that are currently at that
        index or after it will be moved back one position.  If new position is
        after the end of the list, the item will be added at the end, if it's
        less than 0 it will be added at the begining.
        """

        self.confirmDBThread()
        self.items.remove(item)
        self.items.insert(newPosition, item)
        self.signalChange()

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
