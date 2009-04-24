from datetime import datetime, timedelta
import os
import tempfile
import shutil

from miro.feed import Feed
from miro.item import Item, FileItem, get_entry_for_url
from miro.downloader import RemoteDownloader
from miro.test.framework import MiroTestCase

class ItemSeenTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.feed = Feed(u'dtv:manualFeed', initiallyAutoDownloadable=False)
        self.tempdir = tempfile.mkdtemp()
        self._make_fake_video("pcf.mpeg")
        self._make_fake_video("dean.avi")
        self._make_fake_video("npr.mkv")
        self.container_item = FileItem(self.tempdir, self.feed.id)

    def tearDown(self):
        shutil.rmtree(self.tempdir, ignore_errors=True)
        MiroTestCase.tearDown(self)

    def _make_fake_video(self, filename):
        f = open(os.path.join(self.tempdir, filename), 'wb')
        f.write("FAKE DATA")
        f.close()

    def test_seen_attribute(self):
        children = list(self.container_item.getChildren())
        self.assertEquals(len(children), 3)
        self.assert_(not self.container_item.seen)
        children[0].markItemSeen()
        self.assert_(not self.container_item.seen)
        children[1].markItemSeen()
        self.assert_(not self.container_item.seen)
        children[2].markItemSeen()
        self.assert_(self.container_item.seen)
        children[1].markItemUnseen()
        self.assert_(not self.container_item.seen)
        children[1].markItemSeen()
        self.assert_(self.container_item.seen)

class ExpiredViewTest(MiroTestCase):
    def test_expired_view(self):
        f1 = Feed(u'http://example.com/1')
        f2 = Feed(u'http://example.com/2')
        f3 = Feed(u'http://example.com/3')
        f1.setExpiration(u'never', 0)
        f2.setExpiration(u'system', 0)
        f3.setExpiration(u'feed', 24)

        i1 = Item(entry=get_entry_for_url(u'http://example.com/1/item1'),
                feed_id=f1.id)
        i2 = Item(entry=get_entry_for_url(u'http://example.com/1/item2'),
                feed_id=f1.id)
        i3 = Item(entry=get_entry_for_url(u'http://example.com/2/item1'),
                feed_id=f2.id)
        i4 = Item(entry=get_entry_for_url(u'http://example.com/2/item2'),
                feed_id=f2.id)
        i5 = Item(entry=get_entry_for_url(u'http://example.com/3/item1'),
                feed_id=f3.id)
        i6 = Item(entry=get_entry_for_url(u'http://example.com/3/item2'),
                feed_id=f3.id)

        i1.watchedTime = i2.watchedTime = datetime.now()
        i3.watchedTime = datetime.now() - timedelta(days=12)
        i4.watchedTime = datetime.now() - timedelta(days=3)
        i5.watchedTime = datetime.now() - timedelta(days=3)
        i6.watchedTime = datetime.now() - timedelta(hours=12)

        for obj in (f1, f2, f3, i1, i2, i3, i4, i5, i6):
            obj.signal_change()

        self.assertEquals(list(f1.expiring_items()), [])
        self.assertEquals(list(f2.expiring_items()), [i3])
        self.assertEquals(list(f3.expiring_items()), [i5])

    def test_watched_time_reset(self):
        feed = Feed(u'http://example.com/1')
        item = Item(entry=get_entry_for_url(u'http://example.com/1/item1'),
                feed_id=feed.id)
        item.watchedTime = datetime.now()
        item.expire()
        self.assertEquals(item.watchedTime, None)

    def test_remove_before_downloader_referenced(self):
        # when items are restored from the DB, the downloader attribute is
        # loaded lazily.  Make sure that if we remove the item, the downloader
        # is still removed.
        feed = Feed(u'http://example.com/1')
        item = Item(entry=get_entry_for_url(u'http://example.com/1/item1'),
                feed_id=feed.id)
        item.set_downloader(RemoteDownloader(
            u'http://example.com/1/item1/movie.mpeg', item))
        downloader = item.downloader

        feed = self.reload_object(feed)
        item = self.reload_object(item)

        item.remove()
        self.assert_(not downloader.idExists())
