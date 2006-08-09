"""Handle selection."""

import database
import item
import playlist
import feed

class SelectionHandler(object):
    """Class to handle selection.

    Attributes:

    currentSelection -- set of object ids that are currently selected
    currentView -- view that the selected ids are in
    """

    def __init__(self, db):
        self.db = db
        self.currentSelection = set()
        self.currentView = None
        self.lastSelected = None

    def _doSelect(self, id):
        obj = self.db.getObjectByID(id)
        obj.setSelected(True)
        self.currentSelection.add(id)

    def _doUnselect(self, id):
        obj = self.db.getObjectByID(id)
        obj.setSelected(False)
        self.currentSelection.remove(id)

    def _doMultiSelect(self, view, endpoint1, endpoint2):
        selecting = False
        if endpoint1 == endpoint2:
            self._doSelect(endpoint1)
            return
        for item in view:
            id = item.getID()
            if not selecting:
                if id in (endpoint1, endpoint2):
                    selecting = True
                    self._doSelect(id)
            else:
                self._doSelect(id)
                if id in (endpoint1, endpoint2):
                    break

    def clearSelection(self):
        for id in self.currentSelection:
            obj = self.db.getObjectByID(id)
            obj.setSelected(False)
        self.currentSelection = set()

    def selectItem(self, view, id, shiftSelect, controlSelect):
        if (controlSelect or shiftSelect) and view != self.currentView:
            return
        if controlSelect and shiftSelect:
            controlSelect = False

        if not controlSelect:
            self.clearSelection()

        if controlSelect and id in self.currentSelection:
            self._doUnselect(id)
        elif not shiftSelect or not self.lastSelected:
            self._doSelect(id)
        else:
            self._doMultiSelect(view, self.lastSelected, id)

        self.switchView(view)
        self.lastSelected = id

    def switchView(self, view):
        if self.currentView == view:
            return
        if self.currentView is not None:
            self.currentView.removeRemoveCallback(self.onRemove)
        self.currentView = view
        self.currentView.addRemoveCallback(self.onRemove)

    def onRemove(self, obj, id):
        if id in self.currentSelection:
            self._doUnselect(id)

    def getType(self):
        """Get the type of objects that are selected.  This will be one of
        "item", "playlist", "channel", or None if nothing is selected.
        """
        type = None
        for id in self.currentSelection:
            obj = self.currentView.getObjectByID(id)
            if isinstance(obj, item.Item):
                newType = 'item'
            elif obj.__class__ == playlist.SavedPlaylist:
                newType = 'playlist'
            elif obj.__class__ == feed.Feed:
                newType = 'channel'
            else:
                raise ValueError("Bad selected object type: %s" % obj)
            if type is None:
                type = newType
            elif type != newType:
                msg = "Multiple types selected: %s and %s" % (type, newType)
                raise ValueError(msg)
        return type
