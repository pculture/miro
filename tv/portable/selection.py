"""Handle selection."""

import app
import database
import folder
import guide
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

    def __init__(self, selectionHandler):
        self.currentSelection = set()
        self.currentView = None
        self.handler = selectionHandler

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
        "item", "playlisttab", "channeltab", 'guidetab', 'addedguidetab',
        'statictab', or None if nothing is selected.  
        """
        type = None
        for id in self.currentSelection:
            obj = self.currentView.getObjectByID(id)
            if isinstance(obj, item.Item):
                newType = 'item'
            elif isinstance(obj, tabs.Tab):
                if obj.obj.__class__ in (playlist.SavedPlaylist,
                        folder.PlaylistFolder):
                    newType = 'playlisttab'
                elif obj.obj.__class__ in (feed.Feed, folder.ChannelFolder):
                    newType = 'channeltab'
                elif obj.obj.__class__ == guide.ChannelGuide:
                    if obj.obj.getDefault():
                        newType = 'guidetab'
                    else:
                        newType = 'addedguidetab'
                elif obj.obj.__class__ == tabs.StaticTab:
                    newType = 'statictab'
                else:
                    raise ValueError("Bad selected tab type: %s" % obj.obj)
            else:
                raise ValueError("Bad selected object type: %s" % obj)
            if type is None:
                type = newType
            elif type != newType:
                msg = "Multiple types selected: %s and %s" % (type, newType)
                raise ValueError(msg)
        return type

class TabSelectionArea(SelectionArea):
    """Selection area for the tablist.  This has a couple special cases to
    ensure that we always have at least one tab selected.
    """

    def toggleItemSelect(self, view, id):
        # Don't let a control select deselect the last selected item in the
        # tab list.
        if len(self.currentSelection) == set([id]):
            return
        else:
            return SelectionArea.toggleItemSelect(self, view, id)

    def onRemove(self, obj, id):
        SelectionArea.onRemove(self, obj, id)
        if len(self.currentSelection) == 0:
            prevTab = self.currentView.cur()
            if prevTab is None:
                # we remove the 1st tab in the list, try to select the new 1st
                # tab
                prevTab = self.currentView.getNext()
            if prevTab is None:
                # That was the last tab in the list, select the guide
                self.selectFirstGuide()
            else:
                self.selectItem(self.currentView, prevTab.objID())
            self.handler.displayCurrentTabContent()

    def selectFirstGuide(self):
        views.guideTabs.resetCursor()
        guide = views.guideTabs.getNext()
        self.selectItem(views.guideTabs, guide.objID())
        self.handler.displayCurrentTabContent()

class SelectionHandler(object):
    """Handles selection for Democracy.

    Attributes:

    tabListSelection -- SelectionArea for the tab list
    itemListSelection -- SelectionArea for the item list
    """

    def __init__(self):
        self.tabListSelection = TabSelectionArea(self)
        self.itemListSelection = SelectionArea(self)
        self.lastDisplay = None

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
            self.displayCurrentTabContent()

    def setTabListActive(self, value):
        for id in self.tabListSelection.currentSelection:
            tab = self.tabListSelection.currentView.getObjectByID(id)
            tab.setActive(value)

    def selectFirstGuide(self):
        self.tabListSelection.selectFirstGuide()

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

    def _chooseDisplayForCurrentTab(self):
        tls = self.tabListSelection
        frame = app.controller.frame

        if len(tls.currentSelection) == 0:
            raise AssertionError("No tabs selected")
        elif len(tls.currentSelection) == 1:
            for id in tls.currentSelection:
                tab = tls.currentView.getObjectByID(id)
                return app.TemplateDisplay(tab.contentsTemplate, 
                        frameHint=frame, areaHint=frame.mainDisplay, 
                        id=tab.obj.getID())
        else:
            selectedType = tls.getType()
            if selectedType == 'channeltab':
                return app.TemplateDisplay('multi-channel', frameHint=frame,
                        areaHint=frame.mainDisplay)
            elif selectedType == 'playlisttab':
                return app.TemplateDisplay('multi-playlist', frameHint=frame,
                        areaHint=frame.mainDisplay)
            else:
                raise AssertionError("Multiple %s tabs selected" %
                        selectedType)

    def displayCurrentTabContent(self):
        newDisplay = self._chooseDisplayForCurrentTab()
        # Don't redisplay the current tab if it's being displayed.  It messes
        # up our database callbacks.  The one exception is the guide tab,
        # where redisplaying it will reopen the home page.
        frame = app.controller.frame
        mainDisplay = frame.getDisplay(frame.mainDisplay) 
        if (self.lastDisplay and newDisplay == self.lastDisplay and
                self.lastDisplay is mainDisplay and
                newDisplay.templateName != 'guide'):
            return

        self.itemListSelection.clearSelection()
        selectionType = self.tabListSelection.getType()
        if selectionType in ('guidetab', 'addedguidetab'):
            guideURL = self.getSelectedTabs()[0].obj.getURL()
        else:
            guideURL = None
        frame.onSelectedTabChange(selectionType,
                len(self.tabListSelection.currentSelection) > 1,
                guideURL)
        frame.selectDisplay(newDisplay, frame.mainDisplay)
        self.lastDisplay = newDisplay

    def isTabSelected(self, tab):
        return tab.objID() in self.tabListSelection.currentSelection

    def getSelectedTabs(self):
        """Return a list of the currently selected Tabs. """

        view = self.tabListSelection.currentView
        selection = self.tabListSelection.currentSelection
        return [view.getObjectByID(id) for id in selection]
