from miro import database

from miro import app
from miro import iconcache
from miro import item
from miro import feed
from miro import guide

from miro.test.framework import EventLoopTest

class IconCacheTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.feed = feed.Feed(u'http://example.com/')
        self.item = item.Item(item.FeedParserValues({}), feed_id=self.feed.id)
        self.guide = guide.ChannelGuide(u'http://example.com/guide/')

    def test_ddbobject_removed(self):
        """Test that we remove our IconCache DDBObject when it's
        container is removed.
        """
        feed_icon_cache = self.feed.icon_cache
        item_icon_cache = self.item.icon_cache
        guide_icon_cache = self.guide.icon_cache
        self.item.remove()
        self.feed.remove()
        self.guide.remove()

        self.assert_(not feed_icon_cache.id_exists())
        self.assert_(not item_icon_cache.id_exists())
        self.assert_(not guide_icon_cache.id_exists())

    def test_remove_before_icon_cache_referenced(self):
        # Items create the icon_cache attribute lazily when restored
        # from db.  Make sure that removing an item before it's
        # created is okay.

        # trick LiveStorage into restoring our feed, item and guide
        self.feed = self.reload_object(self.feed)
        self.item = self.reload_object(self.item)
        self.guide = self.reload_object(self.guide)

        feed_icon_cache_id = self.feed.icon_cache_id
        item_icon_cache_id = self.item.icon_cache_id
        guide_icon_cache_id = self.guide.icon_cache_id
        self.item.remove()
        self.feed.remove()
        self.guide.remove()

        self.assertRaises(database.ObjectNotFoundError,
                iconcache.IconCache.get_by_id, feed_icon_cache_id)
        self.assertRaises(database.ObjectNotFoundError,
                iconcache.IconCache.get_by_id, item_icon_cache_id)
        self.assertRaises(database.ObjectNotFoundError,
                iconcache.IconCache.get_by_id, guide_icon_cache_id)
