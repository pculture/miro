from miro import database
from miro import iconcache
from miro import item
from miro import feed
from miro import guide

from miro.test.framework import EventLoopTest

class IconCacheTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.feed = feed.Feed(u'http://example.com/')
        self.item = item.Item({}, feed_id=self.feed.id)
        self.guide = guide.ChannelGuide(u'http://example.com/guide/')

    def test_ddbobject_removed(self):
        """Test that we remove our IconCache DDBObject when it's container is
        removed.
        """
        feed_icon_cache = self.feed.icon_cache
        item_icon_cache = self.item.icon_cache
        guide_icon_cache = self.guide.icon_cache
        self.item.remove()
        self.feed.remove()
        self.guide.remove()

        self.assert_(not feed_icon_cache.idExists())
        self.assert_(not item_icon_cache.idExists())
        self.assert_(not guide_icon_cache.idExists())
