from feed import Feed
from feedparser import FeedParserDict
from item import Item
from playlist import SavedPlaylist
import app
import views
from test.framework import DemocracyTestCase

class PlaylistTestCase(DemocracyTestCase):
    def setUp(self):
        DemocracyTestCase.setUp(self)
        self.feed = Feed("http://feed.uk")
        self.i1 = Item(FeedParserDict({'title': 'item1'}), feed_id=self.feed.id)
        self.i2 = Item(FeedParserDict({'title': 'item2'}), feed_id=self.feed.id)
        self.i3 = Item(FeedParserDict({'title': 'item3'}), feed_id=self.feed.id)
        self.i4 = Item(FeedParserDict({'title': 'item4'}), feed_id=self.feed.id)
        self.addCallbacks = []
        self.removeCallbacks = []

    def addCallback(self, obj, id):
        self.addCallbacks.append((obj, id))

    def removeCallback(self, obj, id):
        self.removeCallbacks.append((obj, id))

    def checkList(self, playlist, correctOrder):
        realPositions = {}
        i = 0
        for listid, item in zip(playlist.trackedItems.list, correctOrder):
            self.assertEquals(listid, item.getID())
            realPositions[item.getID()] = i
            i += 1
        self.assertEquals(set(playlist.trackedItems.list), 
                playlist.trackedItems.trackedIDs)
        self.assertEquals(realPositions, playlist.trackedItems.positions)
        self.assertEquals(playlist.getItems(), correctOrder)

    def testBasicOperations(self):
        playlist = SavedPlaylist("rocketboom")
        self.assertEquals(playlist.getTitle(), 'rocketboom')
        self.assertEquals(playlist.getItems(), [])
        playlist.addItem(self.i4)
        playlist.addItem(self.i1)
        playlist.addItem(self.i3)
        playlist.addItem(self.i2)
        self.checkList(playlist, [self.i4, self.i1, self.i3, self.i2])
        playlist.addItem(self.i2)
        self.checkList(playlist, [self.i4, self.i1, self.i3, self.i2])
        self.assert_(self.i1.keep)
        self.assert_(self.i2.keep)
        self.assert_(self.i3.keep)
        self.assert_(self.i4.keep)
        playlist.moveItem(self.i2, 1)
        self.checkList(playlist, [self.i4, self.i2, self.i1, self.i3])
        playlist.moveItem(self.i3, 0)
        self.checkList(playlist, [self.i3, self.i4, self.i2, self.i1])
        playlist.moveItem(self.i3, 3)
        self.checkList(playlist, [self.i4, self.i2, self.i1, self.i3])
        playlist.removeItem(self.i2)
        self.checkList(playlist, [self.i4, self.i1, self.i3])
        playlist.removeItem(self.i3)
        self.checkList(playlist, [self.i4, self.i1])

    def testInitialList(self):
        initialList = [self.i1, self.i2, self.i3]
        playlist = SavedPlaylist("rocketboom", initialList)
        self.assertEquals(playlist.getTitle(), 'rocketboom')
        self.checkList(playlist, initialList)

    def checkCallbacks(self, movedItems):
        correctCallbackList = [(i, i.getID()) for i in movedItems]
        self.assertEquals(self.addCallbacks, correctCallbackList)
        self.assertEquals(self.removeCallbacks, correctCallbackList)

    def testCallbacks(self):
        initialList = [self.i1, self.i2, self.i3]
        playlist = SavedPlaylist("rocketboom", initialList)
        playlist.getView().addAddCallback(self.addCallback)
        playlist.getView().addRemoveCallback(self.removeCallback)
        playlist.moveItem(self.i2, 0)
        self.checkCallbacks([self.i2])
        playlist.moveItem(self.i3, 0)
        self.checkCallbacks([self.i2, self.i3])

    def testHandleDrop(self):
        playlist = SavedPlaylist("rocketboom")
        selection = app.controller.selection
        selection.selectItem('itemlist', views.items, self.i1.getID(),
                shiftSelect=False, controlSelect=False)
        playlist.handleDrop()
        self.checkList(playlist, [self.i1])
        selection.selectItem('itemlist', views.items, self.i3.getID(),
                shiftSelect=False, controlSelect=False)
        selection.selectItem('itemlist', views.items, self.i4.getID(),
                shiftSelect=False, controlSelect=True)
        playlist.handleDrop()
        self.checkList(playlist, [self.i1, self.i3, self.i4])

    def testMoveSelectionAboveItem(self):
        playlist = SavedPlaylist("rocketboom", [self.i1, self.i2, self.i3,
                self.i4])
        selection = app.controller.selection
        view = playlist.getView()
        selection.selectItem('itemlist', view, self.i1.getID(),
                shiftSelect=False, controlSelect=False)
        playlist.moveSelection(self.i3)
        self.checkList(playlist, [self.i2, self.i1, self.i3, self.i4])
        playlist.moveSelection(None)
        self.checkList(playlist, [self.i2, self.i3, self.i4, self.i1])
        playlist.moveSelection(self.i2)
        self.checkList(playlist, [self.i1, self.i2, self.i3, self.i4])
        selection.selectItem('itemlist', view, self.i2.getID(),
                shiftSelect=False, controlSelect=False)
        selection.selectItem('itemlist', view, self.i4.getID(),
                shiftSelect=True, controlSelect=False)
        playlist.moveSelection(self.i1)
        self.checkList(playlist, [self.i2, self.i3, self.i4, self.i1])
        selection.selectItem('itemlist', view, self.i1.getID(),
                shiftSelect=False, controlSelect=False)
        selection.selectItem('itemlist', view, self.i2.getID(),
                shiftSelect=False, controlSelect=True)
        playlist.moveSelection(self.i4)
        self.checkList(playlist, [self.i3, self.i2, self.i1, self.i4])
        selection.selectItem('itemlist', view, self.i1.getID(),
                shiftSelect=False, controlSelect=False)
        selection.selectItem('itemlist', view, self.i3.getID(),
                shiftSelect=False, controlSelect=True)
        playlist.moveSelection(None)
        self.checkList(playlist, [self.i2, self.i4, self.i3, self.i1])
        selection.selectItem('itemlist', view, self.i2.getID(),
                shiftSelect=False, controlSelect=False)
        selection.selectItem('itemlist', view, self.i3.getID(),
                shiftSelect=True, controlSelect=False)
        playlist.moveSelection(None)
        self.checkList(playlist, [self.i1, self.i2, self.i4, self.i3])
