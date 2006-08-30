from gtcache import gettext as _

import app
import dialogs
import indexes
import playlist
import views
from database import DDBObject
from databasehelper import makeSimpleGetSet

class FolderBase(DDBObject):
    """Base class for ChannelFolder and Playlist folder classes."""

    def __init__(self, title):
	self.title = title
        self.expanded = True
	DDBObject.__init__(self)

    getTitle, setTitle = makeSimpleGetSet('title')

    def getExpanded(self):
        self.confirmDBThread()
        return self.expanded

    def setExpanded(self, newExpanded):
        self.confirmDBThread()
        self.expanded = newExpanded
        self.signalChange()
        for child in self.getChildrenView():
            child.signalChange(needsSave=False)

    def getNextTab(self):
        """Get the first tab that isn't in this folder our.  If there are no
        items afterwards, return None.
        """

        anchorItem = None
        seenSelf = False
        # Find the tab directly after this folder and move the tabs above
        # that one.
        for tab in self.getTabOrder().getView():
            if not seenSelf and tab.obj is self: 
                seenSelf = True
            elif seenSelf and tab.obj.getFolder() is not self:
                return tab.obj
        return None

    def handleDNDAppend(self, draggedIDs):
        tabOrder = self.getTabOrder()
        for id in draggedIDs:
            tab = tabOrder.tabView.getObjectByID(id)
            tab.obj.setFolder(self)
        tabOrder.moveTabs(self.getNextTab(), draggedIDs)
        selection = app.controller.selection.tabListSelection
        if len(selection.currentSelection) == 0:
            # we appended tabs to a non-expanded folder and now nothing is
            # selected.  Select that folder.
            app.controller.selection.selectItem('tablist', tabOrder.tabView,
                    self.getID(), False, False)
        self.signalChange()

    def rename(self):
        def callback(dialog):
            if self.idExists() and dialog.choice == dialogs.BUTTON_OK:
                self.setTitle(dialog.value)
        dialogs.TextEntryDialog(self.renameTitle(), self.renameText(), 
                dialogs.BUTTON_OK, dialogs.BUTTON_CANCEL).run(callback)

    def remove(self):
        children = [child for child in self.getChildrenView()]
        for child in children:
            child.remove()
        DDBObject.remove(self)

    # getFolder and setFolder are here so that channels/playlists and folders
    # have a consistent API.  They don't do much since we don't allow nested
    # folders.
    def getFolder(self):
        return None

    def setFolder(self, newFolder):
        if newFolder is not None:
            raise TypeError("Nested folders not allowed")

    def renameTitle(self):
        """Return the title to use for the rename dialog"""
        raise NotImplementedError()
    def renameText(self):
        """Return the description text to use for the rename dialog"""
        raise NotImplementedError()
    def getTabOrder(self):
        """Return the TabOrder object that this folder belongs to."""
        raise NotImplementedError()
    def getChildrenView(self):
        """Return the children of this folder."""
        raise NotImplementedError()

class ChannelFolder(FolderBase):
    def renameTitle(self):
        return _("Rename Channel Folder")
    def renameText(self):
        return _("Enter a new name for the channel folder %s" % 
                self.getTitle())
    def getTabOrder(self):
        return app.getSingletonDDBObject(views.channelTabOrder)
    def getChildrenView(self):
        return views.feeds.filterWithIndex(indexes.byFolder, self)

    def hasDownloadedItems(self):
        for feed in self.getChildrenView():
            if feed.hasDownloadedItems():
                return True
        return False

    # Returns true iff unwatched should be shown 
    def showU(self):
        return self.numUnwatched() > 0

    # Returns string with number of unwatched videos in feed
    def numUnwatched(self):
        unwatched = 0
        for child in self.getChildrenView():
            unwatched += child.unwatched
        return unwatched

    # Returns true iff unwatched should be shown 
    def showA(self):
        return self.numAvailable() > 0

    # Returns string with number of unwatched videos in feed
    def numAvailable(self):
        available = 0
        for child in self.getChildrenView():
            available += child.available
        return available
    
class PlaylistFolder(FolderBase, playlist.PlaylistMixin):
    def __init__(self, title):
        self.item_ids = []
        self.setupTrackedItemView()
        FolderBase.__init__(self, title)

    def onRestore(self):
        self.setupTrackedItemView()

    def handleDNDAppend(self, draggedIDs):
        FolderBase.handleDNDAppend(self, draggedIDs)
        for id in draggedIDs:
            tab = self.getTabOrder().tabView.getObjectByID(id)
            for item in tab.obj.getView():
                if item.getID() not in self.trackedItems:
                    self.trackedItems.appendID(item.getID())
        self.signalChange()

    def checkItemIDRemoved(self, id):
        index = indexes.playlistsByItemAndFolderID
        value = (id, self.getID())
        view = views.playlists.filterWithIndex(index, value)
        if view.len() == 0 and id in self.trackedItems:
            self.removeID(id)

    def renameTitle(self):
        return _("Rename Playlist Folder")
    def renameText(self):
        return _("Enter a new name for the playlist folder %s" % 
                self.getTitle())
    def getTabOrder(self):
        return app.getSingletonDDBObject(views.playlistTabOrder)
    def getChildrenView(self):
        return views.playlists.filterWithIndex(indexes.byFolder, self)

def createNewChannelFolder(childIDs=None):
    title = _("Create Channel Folder")
    description = _("Enter a name for the new channel folder")

    def callback(dialog):
        if dialog.choice == dialogs.BUTTON_CREATE:
            folder = ChannelFolder(dialog.value)
            app.controller.selection.selectTabByObject(folder)
            if childIDs:
                folder.handleDNDAppend(childIDs)

    dialogs.TextEntryDialog(title, description, dialogs.BUTTON_CREATE,
            dialogs.BUTTON_CANCEL).run(callback)

def createNewPlaylistFolder(childIDs=None):
    title = _("Create Playlist Folder")
    description = _("Enter a name for the new playlist folder")

    def callback(dialog):
        if dialog.choice == dialogs.BUTTON_CREATE:
            folder = PlaylistFolder(dialog.value)
            app.controller.selection.selectTabByObject(folder)
            if childIDs:
                folder.handleDNDAppend(childIDs)

    dialogs.TextEntryDialog(title, description, dialogs.BUTTON_CREATE,
            dialogs.BUTTON_CANCEL).run(callback)
