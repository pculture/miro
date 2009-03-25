from miro import database
from miro import iconcache
from miro import item
from miro import feed
from miro import guide

from miro.test.framework import EventLoopTest

class IconCacheTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        database.resetDefaultDatabase()
        self.feed = feed.Feed(u'http://example.com/')
        self.item = item.Item({}, feed_id=self.feed.id)
        self.guide = guide.ChannelGuide(u'http://example.com/guide/')

    def tearDown(self):
        database.resetDefaultDatabase()
        EventLoopTest.tearDown(self)

    def test_ddbobject_created(self):
        """Test that we create a new DDBObject for each IconCache object."""
        self.assert_(self.feed.icon_cache in database.defaultDatabase)
        self.assert_(self.item.icon_cache in database.defaultDatabase)
        self.assert_(self.guide.icon_cache in database.defaultDatabase)

    def test_ddbobject_removed(self):
        """Test that we remove our IconCache DDBObject when it's container is
        removed.
        """
        feed_icon_cache = self.feed.icon_cache
        item_icon_cache = self.item.icon_cache
        guide_icon_cache = self.guide.icon_cache
        self.feed.remove()
        self.item.remove()
        self.guide.remove()

        self.assert_(feed_icon_cache not in database.defaultDatabase)
        self.assert_(item_icon_cache not in database.defaultDatabase)
        self.assert_(guide_icon_cache not in database.defaultDatabase)
