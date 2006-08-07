from feed import Feed
from feedparser import FeedParserDict
from item import Item
from playlist import SavedPlaylist
from test.framework import DemocracyTestCase

class PlaylistTestCase(DemocracyTestCase):
    def setUp(self):
        DemocracyTestCase.setUp(self)
        self.feed = Feed("http://feed.uk")
        self.i1 = Item(FeedParserDict({'title': 'item1'}), feed_id=self.feed.id)
        self.i2 = Item(FeedParserDict({'title': 'item2'}), feed_id=self.feed.id)
        self.i3 = Item(FeedParserDict({'title': 'item3'}), feed_id=self.feed.id)
        self.i4 = Item(FeedParserDict({'title': 'item4'}), feed_id=self.feed.id)

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
        self.assertEquals(playlist.getExpanded(), False)
        playlist.addItem(self.i4)
        playlist.addItem(self.i1)
        playlist.addItem(self.i3)
        playlist.addItem(self.i2)
        self.checkList(playlist, [self.i4, self.i1, self.i3, self.i2])
        playlist.changeItemPosition(self.i2, 1)
        self.checkList(playlist, [self.i4, self.i2, self.i1, self.i3])
        playlist.changeItemPosition(self.i3, 0)
        self.checkList(playlist, [self.i3, self.i4, self.i2, self.i1])
        playlist.changeItemPosition(self.i3, 3)
        self.checkList(playlist, [self.i4, self.i2, self.i1, self.i3])
        playlist.removeItem(self.i2)
        self.checkList(playlist, [self.i4, self.i1, self.i3])
        playlist.removeItem(self.i3)
        self.checkList(playlist, [self.i4, self.i1])
