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

"""Handle selection."""

from copy import copy

from miro import app
from miro import database
from miro import eventloop
from miro import folder
from miro import config
from miro import prefs
from miro import guide
from miro import item
from miro import tabs
from miro import playlist
from miro import signals
from miro import feed
from miro import views
from miro import indexes
from miro import util
from miro.gtcache import gettext as _

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
        self.currentView.addViewUnlinkCallback(self.onViewUnlinked)

    def selectItem(self, view, id):
        self.switchView(view)
        obj = view.getObjectByID(id)
        self.currentSelection.add(id)
        obj.setSelected(True)

    def deselectItem(self, view, id):
        if view != self.currentView:
            raise ValueError("view != current view in deselectItem()")
        obj = view.getObjectByID(id)
        self.currentSelection.remove(id)
        obj.setSelected(False)

    def isSelected(self, view, id):
        return self.currentView == view and id in self.currentSelection

    def toggleItemSelect(self, view, id):
        self.switchView(view)
        if id in self.currentSelection:
            self.deselectItem(view, id)
        else:
            self.selectItem(view, id)

    def clearSelection(self):
        """Clears the current selection."""

        for obj in self.getObjects():
            obj.setSelected(False)
        self.currentSelection = set()
        if self.currentView is not None:
            self.currentView.removeRemoveCallback(self.onRemove)
            self.currentView.removeAddCallback(self.onAdd)
            self.currentView = None

    def selectAll(self):
        """Select all objects in the current View."""
        
        view = self.currentView
        if view:
            for obj in view:
                if obj.getID not in self.currentSelection:
                    self.selectItem(view, obj.getID())

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
        toSelect = []
        for obj in view:
            id = getID(obj)
            if selecting and id not in self.currentSelection:
                toSelect.append(id)
            if id == firstID:
                selecting = True
                if id not in self.currentSelection:
                    toSelect.append(id)
            if id == lastID:
                break
        for id in toSelect:
            self.selectItem(view, id)

    def onRemove(self, obj, id):
        if id in self.currentSelection:
            self.currentSelection.remove(id)
            if obj.idExists():
                obj.setSelected(False)

    def setObjectsActive(self, newValue):
        """Iterate through all selected objects and call setActive on them,
        passing in newValue.
        """

        for obj in self.getObjects():
            obj.setActive(newValue)

    def onAdd(self, obj, id):
        if obj.getSelected() and id not in self.currentSelection:
            # this happens when we remove/add the object to reorder it in a
            # playlist
            self.currentSelection.add(id)

    def onViewUnlinked(self):
        self.clearSelection()

    def getTypesDetailed(self):
        """Get the type of objects that are selected.  

        Returns a set, containing all the type of objects selected.  The
        members will be one of the following:

        'item', 'downloadeditem' 'playlisttab', playlistfoldertab,
        'channeltab', 'channelfoldertab', 'guidetab', 'addedguidetab',
        'statictab'.

        """

        types = set()
        for obj in self.getObjects():
            if isinstance(obj, item.Item):
                if obj.isDownloaded():
                    newType = 'downloadeditem'
                else:
                    newType = 'item'
            elif isinstance(obj, tabs.Tab):
                objClass = obj.obj.__class__
                if objClass == playlist.SavedPlaylist:
                    newType = 'playlisttab'
                elif objClass == folder.PlaylistFolder:
                    newType = 'playlistfoldertab'
                elif objClass == feed.Feed:
                    newType = 'channeltab'
                elif objClass == folder.ChannelFolder:
                    newType = 'channelfoldertab'
                elif objClass == guide.ChannelGuide:
                    if obj.obj.getDefault():
                        newType = 'guidetab'
                    else:
                        newType = 'addedguidetab'
                elif objClass == tabs.StaticTab:
                    newType = 'statictab'
                else:
                    raise ValueError("Bad selected tab type: %s" % obj.obj)
            else:
                raise ValueError("Bad selected object type: %s" % obj)
            types.add(newType)
        self.simplifyTypes(types) 
        # we don't care about the result of simplifyTypes, but the error
        # checking is useful
        return types

    def simplifyTypes(self, types):
        if len(types) == 0:
            return None
        elif types.issubset(set(["item", "downloadeditem"])):
                return "item"
        elif types.issubset(set(["playlistfoldertab", "playlisttab"])):
                return "playlisttab"
        elif types.issubset(set(["channelfoldertab", "channeltab"])):
                return "channeltab"
        elif len(types) == 1:
            for type in types:
                return type
        else:
            raise ValueError("Multiple types selected: %s" % types)

    def getType(self):
        """Get the simplified version of the type of objects that are
        selected.  getType() works like getTypesDetailed(), but it just
        returns one value.  It doesn't differentiate between playlists and
        playlist folders, and items and downloaded items for example.

        The return value will be one of

        "item", "playlisttab", "channeltab", 'guidetab', 'addedguidetab',
        'statictab', or None if nothing is selected.  

        """

        return self.simplifyTypes(self.getTypesDetailed())

    def getObjects(self):
        view = self.currentView
        objects = [view.getObjectByID(id) for id in self.currentSelection]
        # Don't return items that have been deleted from the DB (#9399)
        return [obj for obj in objects if obj.idExists()]

    def firstBeforeSelection(self, iterator):
        """Go through iterator and find the first item that is selected.
        Returns the item immediately before that one.

        Returns None if the first item in iterator is selected, or no items
        are selected.
        """

        lastItem = None
        for item in iterator:
            if item.getID() in self.currentSelection:
                return lastItem
            lastItem = item
        return None

    def firstAfterSelection(self, iterator):
        """Like firstBeforeSelection, but returns the first item following the
        last selected item in iterator.
        """

        retval = None
        lastSelected = False
        for item in iterator:
            if item.getID() in self.currentSelection:
                lastSelected = True
            elif lastSelected:
                lastSelected = False
                retval = item
        return retval

class TabSelectionArea(SelectionArea, signals.SignalEmitter):
    """Selection area for the tablist.  This has a couple special cases to
    ensure that we always have at least one tab selected.
    """

    def __init__(self):
        SelectionArea.__init__(self)
        signals.SignalEmitter.__init__(self, 'tab-selected')

    def selectItem(self, view, id):
        SelectionArea.selectItem(self, view, id)
        self.moveCursorToSelection()

    def deselectItem(self, view, id):
        SelectionArea.deselectItem(self, view, id)
        self.moveCursorToSelection()

    def moveCursorToSelection(self):
        for id in self.currentSelection:
            self.currentView.moveCursorToID(id)
            break

    def toggleItemSelect(self, view, id):
        # Don't let a control select deselect the last selected item in the
        # tab list.
        if self.currentSelection == set([id]):
            return
        else:
            return SelectionArea.toggleItemSelect(self, view, id)

    def onRemove(self, obj, id):
        SelectionArea.onRemove(self, obj, id)
        # We may be removing/adding tabs quickly to reorder them.  Use an idle
        # callback to check if none are selected so we do the Right Thing in
        # this case.
        eventloop.addUrgentCall(self.checkNoTabsSelected,
                "checkNoTabsSelected")

    def checkNoTabsSelected(self):
        if len(self.currentSelection) == 0:
            prevTab = self.currentView.cur()
            if prevTab is None:
                # we remove the 1st tab in the list, try to select the new 1st
                # tab
                prevTab = self.currentView.getNext()
            if prevTab is None:
                # That was the last tab in the list, select the guide
                self.selectFirstTab()
            else:
                self.selectItem(self.currentView, prevTab.objID())
            self.emit('tab-selected')

    def selectFirstTab(self):
        if config.get(prefs.OPEN_CHANNEL_ON_STARTUP) is not None:
            view = views.feeds.filterWithIndex(indexes.feedsByURL,
                          unicode(config.get(prefs.OPEN_CHANNEL_ON_STARTUP)))
            if len(view) > 0:
                self.selectItem(views.allTabs, view[0].getID())
                self.emit('tab-selected')
                view.unlink()
                return
            else:
                view.unlink()
        if config.get(prefs.OPEN_FOLDER_ON_STARTUP) is not None:
            view = views.channelFolders.filterWithIndex(indexes.foldersByTitle,
                          unicode(config.get(prefs.OPEN_FOLDER_ON_STARTUP)))
            if len(view) > 0:
                self.selectItem(views.allTabs, view[0].getID())
                self.emit('tab-selected')
                view.unlink()
                return
            else:
                view.unlink()

        views.guideTabs.resetCursor()
        guide = views.guideTabs.getNext()
        self.selectItem(views.guideTabs, guide.objID())
        self.emit('tab-selected')

    def isFolderSelected(self):
        """Returns if a channel/playlist folder is selected."""
        for tab in self.getObjects():
            if isinstance(tab.obj, folder.FolderBase):
                return True
        return False

class SelectionHandler(signals.SignalEmitter):
    """Handles selection for Democracy.

    Attributes:

    tabListSelection -- SelectionArea for the tab list
    itemListSelection -- SelectionArea for the item list
    tabListActive -- does the tabListSelection the have the "active"
        selection?  In other words, is that the one that was clicked on last.

    SelectionHandlers emit a tab-selected signal and an item-selected signal.
    Frontends should connect to these signals and update the UI based on it.
    """

    def __init__(self):
        signals.SignalEmitter.__init__(self, 'tab-selected', 'item-selected')
        self.tabListSelection = TabSelectionArea()
        self.itemListSelection = SelectionArea()
        self.tabListActive = True
        self.tabListSelection.connect('tab-selected',
                self.propagateTabSelected)

    def propagateTabSelected(self, tabListSelection):
        self.emit('tab-selected')

    def getSelectionForArea(self, area):
        if area == 'tablist':
            return self.tabListSelection
        elif area == 'itemlist':
            return self.itemListSelection
        else:
            raise ValueError("Unknown area: %s" % area)

    def isSelected(self, area, view, id):
        return self.getSelectionForArea(area).isSelected(view, id)

    def selectItem(self, area, view, id, shiftSelect, controlSelect,
            sendSignal=True):
        selection = self.getSelectionForArea(area)
        try:
            selectedObj = view.getObjectByID(id)
        except database.ObjectNotFoundError:
            # Item got deleted before the select went through.
            return

        # ignore control and shift when selecting static tabs
        if (isinstance(selectedObj, tabs.Tab) and 
                selectedObj.type in ('statictab', 'guide')):
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
            if sendSignal:
                self.emit('item-selected')
        else:
            self.setTabListActive(True)
            if sendSignal:
                self.emit('tab-selected')

    def setTabListActive(self, value):
        self.tabListActive = value
        self.tabListSelection.setObjectsActive(value)
        self.itemListSelection.setObjectsActive(not value)

    def calcSelection(self, area, sourceID):
        """Calculate the selection, given the ID of an object that was clicked
        on.  If sourceID is in the current selection, this will all the
        objects in the current selection, otherwise it will be only the object
        that corresponds to sourceID.  
        """

        selection = self.getSelectionForArea(area)
        if sourceID in selection.currentSelection:
            return set(selection.currentSelection)
        else:
            return set([sourceID])

    def selectFirstTab(self):
        self.tabListSelection.selectFirstTab()

    def selectTabByTemplateBase(self, tabTemplateBase, sendSignal=True):
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
                            shiftSelect=False, controlSelect=False,
                            sendSignal=sendSignal)
                    return

    def selectTabByObject(self, obj, sendSignal=True):
        channelTabOrder = util.getSingletonDDBObject(views.channelTabOrder)
        playlistTabOrder = util.getSingletonDDBObject(views.playlistTabOrder)
        tabViews = [ 
            views.guideTabs, 
            views.staticTabs, 
            channelTabOrder.getView(), 
            playlistTabOrder.getView(), 
        ]
        for view in tabViews:
            for tab in view:
                if tab.obj is obj:
                    self.selectItem('tablist', view, tab.objID(),
                            shiftSelect=False, controlSelect=False,
                            sendSignal=sendSignal)
                    return

    def isTabSelected(self, tab):
        return tab.objID() in self.tabListSelection.currentSelection

    def getSelectedTabs(self):
        """Return a list of the currently selected Tabs. """

        return self.tabListSelection.getObjects()

    def getSelectedItems(self):
        """Return a list of the currently selected items. """

        return self.itemListSelection.getObjects()
