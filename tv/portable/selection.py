"""Handle selection."""

import app
import database
import item
import tabs
import playlist
import feed
import views

def getID(obj):
    """Gets an ID to use for an object.  For tabs, this is the object ID that
    maps to the tab.  For other objects this is the actual DDBObject ID."""
    if isinstance(obj, tabs.Tab):
        return obj.objID()
    else:
        return obj.getID()

class SelectionArea(object):
    """Represents an area that holds a selection.  Currently we have 2
    SelectionAreas, the tab list and the item list.  SelectionAreas hold
    several database views, for instance the tab list contains
    views.guideTabs, views.staticTabs, views.feedTabs and views.playlistTabs.
    All the items selected in an area must be in a single view.

    Member variables:

    currentView -- The view that items are currently selected in, or None if
        there are no items selected.
    currentSelection -- set of object IDs that are currently selected.
    """

    def __init__(self):
        self.currentSelection = set()
        self.currentView = None

    def switchView(self, view):
        if self.currentView == view:
            return
        if self.currentView:
            self.clearSelection()
        self.currentView = view
        self.currentView.addRemoveCallback(self.onRemove)
        self.currentView.addAddCallback(self.onAdd)

    def selectItem(self, view, id):
        self.switchView(view)
        obj = view.getObjectByID(id)
        obj.setSelected(True)
        self.currentSelection.add(id)

    def deselectItem(self, view, id):
        if view != self.currentView:
            raise ValueError("view != current view in deselectItem()")
        obj = view.getObjectByID(id)
        obj.setSelected(False)
        self.currentSelection.remove(id)

    def toggleItemSelect(self, view, id):
        self.switchView(view)
        if id in self.currentSelection:
            self.deselectItem(view, id)
        else:
            self.selectItem(view, id)

    def clearSelection(self):
        """Clears the current selection."""

        for id in self.currentSelection:
            obj = self.currentView.getObjectByID(id)
            obj.setSelected(False)
        self.currentSelection = set()
        if self.currentView is not None:
            self.currentView.removeRemoveCallback(self.onRemove)
            self.currentView.removeAddCallback(self.onAdd)
            self.currentView = None

    def calcExtendRange(self, view, id):
        idIsBefore = False
        gotFirst = False
        firstID = lastID = None
        for obj in view:
            objID = getID(obj)
            if objID == id and not gotFirst:
                idIsBefore = True
            if objID in self.currentSelection:
                if not gotFirst:
                    firstID = objID
                    gotFirst = True
                lastID = objID
        if firstID is None or lastID is None:
            raise AssertionError("Couldn't find my selected IDs")
        if idIsBefore:
            return id, lastID
        else:
            return firstID, id

    def extendSelection(self, view, id):
        """Extends the selection in response to a shift-select.  If id is on
        top of the current selection, we will select everything between the id
        and the last selected item.  If id is below it or in the middle, we
        will select between the first selected item and id.  
        """

        self.switchView(view)
        if len(self.currentSelection) == 0:
            return self.selectItem(view, id)
        firstID, lastID = self.calcExtendRange(view, id)
        self.selectBetween(view, firstID, lastID)

    def selectBetween(self, view, firstID, lastID):
        """Select all items in view between firstID and lastID."""

        self.switchView(view)
        selecting = False
        for obj in view:
            id = getID(obj)
            if selecting and id not in self.currentSelection:
                self.selectItem(view, id)
            if id == firstID:
                selecting = True
                if id not in self.currentSelection:
                    self.selectItem(view, id)
            if id == lastID:
                break

    def onRemove(self, obj, id):
        if id in self.currentSelection:
            try:
                obj = self.currentView.getObjectByID(id)
                obj.setSelected(False)
            except database.ObjectNotFoundError:
                pass
            self.currentSelection.remove(id)

    def onAdd(self, obj, id):
        if obj.getSelected() and id not in self.currentSelection:
            # this happens when we remove/add the object to reorder it in a
            # playlist
            self.currentSelection.add(id)

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

class SelectionHandler(object):
    """Handles selection for Democracy.

    Attributes:

    tabListSelection -- SelectionArea for the tab list
    itemListSelection -- SelectionArea for the item list
    currentTab -- the currently selected tab
    """

    def __init__(self):
        self.tabListSelection = SelectionArea()
        self.itemListSelection = SelectionArea()
        self.currentTab = None

    def selectItem(self, area, view, id, shiftSelect, controlSelect):
        if area == 'tablist':
            selection = self.tabListSelection
        elif area == 'itemlist':
            selection = self.itemListSelection
        else:
            raise ValueError("Unknown area: %s" % area)

        selectedObj = view.getObjectByID(id)

        # ignore control and shift when selecting static tabs
        if isinstance(selectedObj, tabs.Tab) and selectedObj.isStatic():
            controlSelect = shiftSelect = False
        # Don't let a control select deselect the last selected item in the
        # tab list.
        if (controlSelect and area == 'tablist' and 
                selection.currentSelection == set([id])):
            return

        if controlSelect:
            selection.toggleItemSelect(view, id)
        elif shiftSelect:
            selection.extendSelection(view, id)
        else:
            selection.clearSelection()
            selection.selectItem(view, id)

        if area == 'itemlist':
            self.setTabListActive(False)
        else:
            self.setTabListActive(True)
            self.displayTabContents(id)

    def setTabListActive(self, value):
        for id in self.tabListSelection.currentSelection:
            tab = self.tabListSelection.currentView.getObjectByID(id)
            tab.setActive(value)

    def selectFirstGuide(self):
        views.guideTabs.resetCursor()
        guide = views.guideTabs.getNext()
        self.selectItem('tablist', views.guideTabs, guide.objID(),
                shiftSelect=False, controlSelect=False)

    def selectTabByTemplateBase(self, tabTemplateBase):
        tabViews = [ 
            views.guideTabs, 
            views.staticTabs, 
            views.feedTabs, 
            views.playlistTabs,
        ]
        for view in tabViews:
            for tab in view:
                if tab.tabTemplateBase == tabTemplateBase:
                    self.selectItem('tablist', view, tab.objID(),
                            shiftSelect=False, controlSelect=False)
                    return

    def displayTabContents(self, id):
        tab = self.tabListSelection.currentView.getObjectByID(id)
        if tab is self.currentTab:
            # Don't redisplay the current tab if it's being display.  The one
            # exception is the guide tab, where redisplaying it will open the
            # home page.
            mainFrame = app.controller.frame
            mainDisplay = mainFrame.getDisplay(mainFrame.mainDisplay) 
            if (not tab.tabTemplateBase == 'guidetab' and
                    self.currentTab.display is mainDisplay):
                return
        else:
            self.currentTab = tab
        self.displayCurrentTabContent()

    def selectTabByObject(self, obj):
        tabViews = [ 
            views.guideTabs, 
            views.staticTabs, 
            views.feedTabs, 
            views.playlistTabs,
        ]
        for view in tabViews:
            for tab in view:
                if tab.obj is obj:
                    self.selectItem('tablist', view, tab.objID(),
                            shiftSelect=False, controlSelect=False)
                    return

    def displayCurrentTabContent(self):
        self.itemListSelection.clearSelection()
        self.currentTab.start(app.controller.frame)

    def isTabSelected(self, tab):
        return tab.objID() in self.tabListSelection.currentSelection
