from feed import Feed
from feedparser import FeedParserDict
from item import Item
from playlist import SavedPlaylist
from test.framework import DemocracyTestCase

class PlaylistTestCase(DemocracyTestCase):
    def setUp(self):
        DemocracyTestCase.setUp(self)
        self.feed = Feed("http://feed.uk")
        self.i1 = Item(self.feed.id, FeedParserDict({'title': 'item1'}))
        self.i2 = Item(self.feed.id, FeedParserDict({'title': 'item2'}))
        self.i3 = Item(self.feed.id, FeedParserDict({'title': 'item3'}))
        self.i4 = Item(self.feed.id, FeedParserDict({'title': 'item4'}))

    def testBasicOperations(self):
        playlist = SavedPlaylist("rocketboom")
        self.assertEquals(playlist.getTitle(), 'rocketboom')
        self.assertEquals(playlist.getItems(), [])
        self.assertEquals(playlist.getExpanded(), False)
        playlist.addItem(self.i4)
        playlist.addItem(self.i1)
        playlist.addItem(self.i3)
        playlist.addItem(self.i2)
        self.assertEquals(playlist.getItems(), 
                [self.i4, self.i1, self.i3, self.i2])
        playlist.changeItemPosition(self.i2, 1)
        self.assertEquals(playlist.getItems(), 
                [self.i4, self.i2, self.i1, self.i3])
        playlist.changeItemPosition(self.i3, 0)
        self.assertEquals(playlist.getItems(), 
                [self.i3, self.i4, self.i2, self.i1])
        playlist.changeItemPosition(self.i3, 4)
        self.assertEquals(playlist.getItems(), 
                [self.i4, self.i2, self.i1, self.i3])
        playlist.removeItem(self.i2)
        self.assertEquals(playlist.getItems(), [self.i4, self.i1, self.i3])
        playlist.removeItem(self.i3)
        self.assertEquals(playlist.getItems(), [self.i4, self.i1])
