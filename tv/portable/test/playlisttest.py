from miro.feed import Feed
from miro.feedparser import FeedParserDict
from miro.item import Item
from miro.playlist import SavedPlaylist
from miro.folder import PlaylistFolder
from miro import app
from miro import views
from miro import tabs
from miro.test.framework import EventLoopTest

class PlaylistTestBase(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.feed = Feed(u"http://feed.uk")
        self.i1 = Item(FeedParserDict({'title': u'item1'}),
                       feed_id=self.feed.id)
        self.i2 = Item(FeedParserDict({'title': u'item2'}),
                       feed_id=self.feed.id)
        self.i3 = Item(FeedParserDict({'title': u'item3'}),
                       feed_id=self.feed.id)
        self.i4 = Item(FeedParserDict({'title': u'item4'}),
                       feed_id=self.feed.id)

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

#    def doAppend(self, playlist, objects):
#        [playlist.addId(i.getID()) for i in objects]

#     def doReorder(self, playlist, anchor, objects):
#         playlist.handleDNDReorder(anchor, set([i.getID() for i in objects]))

class PlaylistTestCase(PlaylistTestBase):
    def setUp(self):
        PlaylistTestBase.setUp(self)
        self.addCallbacks = []
        self.removeCallbacks = []

    def addCallback(self, obj, id):
        self.addCallbacks.append((obj, id))

    def removeCallback(self, obj, id):
        self.removeCallbacks.append((obj, id))

    def testBasicOperations(self):
        playlist = SavedPlaylist(u"rocketboom")
        self.assertEquals(playlist.get_title(), u'rocketboom')
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
        playlist = SavedPlaylist(u"rocketboom", [i.id for i in initialList])
        self.assertEquals(playlist.get_title(), u'rocketboom')
        self.checkList(playlist, initialList)

    def checkCallbacks(self, movedItems):
        correctCallbackList = [(i, i.getID()) for i in movedItems]
        self.assertEquals(self.addCallbacks, correctCallbackList)
        self.assertEquals(self.removeCallbacks, correctCallbackList)

    def testCallbacks(self):
        initialList = [self.i1, self.i2, self.i3]
        playlist = SavedPlaylist(u"rocketboom", [i.id for i in initialList])
        playlist.getView().addAddCallback(self.addCallback)
        playlist.getView().addRemoveCallback(self.removeCallback)
        playlist.moveItem(self.i2, 0)
        self.checkCallbacks([self.i2])
        playlist.moveItem(self.i3, 0)
        self.checkCallbacks([self.i2, self.i3])

    def testExpireRemovesItem(self):
        checkList = [self.i1, self.i2, self.i3, self.i4]
        playlist = SavedPlaylist(u"rocketboom", [i.id for i in checkList])
        for i in [self.i1, self.i3, self.i4, self.i2]:
            i.expire()
            checkList.remove(i)
            self.checkList(playlist, checkList)

class PlaylistFolderTestCase(PlaylistTestBase):
    def setUp(self):
        PlaylistTestBase.setUp(self)
        self.playlistTabOrder = tabs.TabOrder(u'playlist')
        self.p1 = SavedPlaylist(u"rocketboom", [self.i1.id, self.i3.id])
        self.p2 = SavedPlaylist(u"telemusicvision", [self.i4.id, self.i3.id])
        self.p3 = SavedPlaylist(u"digg", [self.i1.id, self.i2.id, self.i3.id, self.i4.id])
        self.folder = PlaylistFolder("My Best Vids")
        self.folder.setExpanded(True)
        self.runPendingIdles() # The TabOrder gets updated in an idle call

    def doTabReorder(self, anchorID, items):
        pass

    def doPlaylistRemove(self, playlist, items):
        playlist.handleRemove(set([i.getID() for i in items]))

#    def testExpireRemovesItem(self):
#        self.doAppend(self.folder, [self.p1])
#        self.checkList(self.folder, [self.i1, self.i3])
#        self.i1.expire()
#        self.checkList(self.folder, [self.i3])
#        self.i3.expire()
#        self.checkList(self.folder, [])

#    def testRemovePlaylistRemovesItem(self):
#        for pl in [self.p1, self.p2, self.p3]:
#            self.doAppend(self.folder, [pl])
#        self.checkList(self.folder, [self.i1, self.i3, self.i4, self.i2])
#        self.doTabReorder(None, [self.p3])
#        self.checkList(self.folder, [self.i1, self.i3, self.i4])
#        self.doTabReorder(None, [self.p2])
#        self.checkList(self.folder, [self.i1, self.i3])
#        self.doTabReorder(None, [self.p1])
#        self.checkList(self.folder, [])

#    def testRemoveItemFromPlaylist(self):
#        for pl in [self.p1, self.p2, self.p3]:
#            self.doAppend(self.folder, [pl])
#        self.checkList(self.folder, [self.i1, self.i3, self.i4, self.i2])
#        self.doPlaylistRemove(self.p1, [self.i1])
#        self.checkList(self.folder, [self.i1, self.i3, self.i4, self.i2])
#        self.doPlaylistRemove(self.p3, [self.i1])
#        self.checkList(self.folder, [self.i3, self.i4, self.i2])

#    def testRemoveFolderRemovesPlaylist(self):
#        self.doAppend(self.folder, [self.p1, self.p2, self.p3])
#        self.folder.remove()
#        self.assertEquals(len(views.playlists), 0)
