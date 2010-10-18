from datetime import datetime, timedelta
import os
import shutil
import tempfile

from miro import app
from miro import prefs
from miro.feed import Feed
from miro.item import Item, FileItem, FeedParserValues
from miro.downloader import RemoteDownloader
from miro.test.framework import MiroTestCase
from miro.singleclick import _build_entry
from miro.plat.utils import FilenameType

def fp_values_for_url(url):
    return FeedParserValues(_build_entry(url, 'video/x-unknown'))

class ContainerItemTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.feed = Feed(u'dtv:manualFeed', initiallyAutoDownloadable=False)
        self.mytempdir = FilenameType(tempfile.mkdtemp(dir=self.tempdir))
        self._make_fake_item("pcf.avi")
        self._make_fake_item("dean.avi")
        self._make_fake_item("npr.txt")
        self.container_item = FileItem(self.mytempdir, self.feed.id)
        for child in self.container_item.get_children():
            if child.filename.endswith("avi"):
                child.file_type = u'video'
            else:
                child.file_type = u'other'
            child.media_type_checked = True
            child.signal_change()

    def tearDown(self):
        shutil.rmtree(self.mytempdir, ignore_errors=True)
        MiroTestCase.tearDown(self)

    def _make_fake_item(self, filename):
        f = open(os.path.join(self.mytempdir, filename), 'wb')
        f.write("FAKE DATA")
        f.close()

class ItemSeenTest(ContainerItemTest):
    def test_seen_attribute(self):
        # parents should be consider "seen" when all of their
        # audio/video children are marked seen.
        children = list(self.container_item.get_children())
        media_children = [i for i in children if i.is_playable()]
        other_children = [i for i in children if not i.is_playable()]
        self.assertEquals(len(media_children), 2)
        self.assertEquals(len(other_children), 1)
        self.assert_(not self.container_item.seen)
        media_children[0].mark_item_seen()
        self.assert_(not self.container_item.seen)
        media_children[1].mark_item_seen()
        self.assert_(self.container_item.seen)
        media_children[1].mark_item_unseen()
        self.assert_(not self.container_item.seen)
        media_children[1].mark_item_seen()
        self.assert_(self.container_item.seen)

class ChildRemoveTest(ContainerItemTest):
    def test_expire_all_children(self):
        children = list(self.container_item.get_children())
        for child in children[1:]:
            child.expire()
            self.assert_(self.container_item.id_exists())
        children[0].expire()
        self.assert_(not self.container_item.id_exists())

    def test_remove_parent(self):
        # test for the conditions that caused #11941
        self.container_item.remove()

    def test_parent_delete_files(self):
        # test for the conditions that caused #11941
        self.container_item.delete_files()
        self.container_item.remove()

class ExpiredViewTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self._expire_after_x_days_value = app.config.get(prefs.EXPIRE_AFTER_X_DAYS)
        app.config.set(prefs.EXPIRE_AFTER_X_DAYS, 6)

    def tearDown(self):
        MiroTestCase.tearDown(self)
        app.config.set(prefs.EXPIRE_AFTER_X_DAYS, self._expire_after_x_days_value)

    def test_expired_view_1(self):
        f1 = Feed(u'http://example.com/1')

        i1 = Item(fp_values_for_url(u'http://example.com/1/item1'),
                feed_id=f1.id)
        i2 = Item(fp_values_for_url(u'http://example.com/1/item2'),
                feed_id=f1.id)

        f1.set_expiration(u'never', 0)
        i1.watchedTime = i2.watchedTime = datetime.now()

        for obj in (f1, i1, i2):
            obj.signal_change()

        self.assertEquals(list(f1.expiring_items()), [])

    def test_expired_view_2(self):
        f2 = Feed(u'http://example.com/2')

        i3 = Item(fp_values_for_url(u'http://example.com/2/item1'),
                feed_id=f2.id)
        i4 = Item(fp_values_for_url(u'http://example.com/2/item2'),
                feed_id=f2.id)

        f2.set_expiration(u'system', 0)
        # system default is 6 days as set in setUp, so i3 should expire,
        # but i4 should not.
        i3.watchedTime = datetime.now() - timedelta(days=12)
        i4.watchedTime = datetime.now() - timedelta(days=3)

        for obj in (f2, i3, i4):
            obj.signal_change()

        self.assertEquals(list(f2.expiring_items()), [i3])

    def test_expired_view_3(self):
        f3 = Feed(u'http://example.com/3')

        i5 = Item(fp_values_for_url(u'http://example.com/3/item1'),
                feed_id=f3.id)
        i6 = Item(fp_values_for_url(u'http://example.com/3/item2'),
                feed_id=f3.id)

        f3.set_expiration(u'feed', 24)
        i5.watchedTime = datetime.now() - timedelta(days=3)
        i6.watchedTime = datetime.now() - timedelta(hours=12)

        for obj in (f3, i5, i6):
            obj.signal_change()

        self.assertEquals(list(f3.expiring_items()), [i5])

class ItemRemoveTest(MiroTestCase):
    def test_watched_time_reset(self):
        feed = Feed(u'http://example.com/1')
        item = Item(fp_values_for_url(u'http://example.com/1/item1'),
                feed_id=feed.id)
        item.watchedTime = datetime.now()
        item.expire()
        self.assertEquals(item.watchedTime, None)

    def test_remove_before_downloader_referenced(self):
        # when items are restored from the DB, the downloader
        # attribute is loaded lazily.  Make sure that if we remove the
        # item, the downloader is still removed.
        feed = Feed(u'http://example.com/1')
        item = Item(fp_values_for_url(u'http://example.com/1/item1'),
                feed_id=feed.id)
        item.set_downloader(RemoteDownloader(
            u'http://example.com/1/item1/movie.mpeg', item))
        downloader = item.downloader

        feed = self.reload_object(feed)
        downloader = self.reload_object(downloader)
        item = self.reload_object(item)

        item.remove()
        self.assert_(not downloader.id_exists())

class SubtitleEncodingTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.feed = Feed(u'http://example.com/1')
        self.item1 = Item(fp_values_for_url(u'http://example.com/1/item1'),
                feed_id=self.feed.id)
        self.item2 = Item(fp_values_for_url(u'http://example.com/1/item2'),
                feed_id=self.feed.id)

    def test_default(self):
        self.assertEquals(self.item1.subtitle_encoding, None)

    def test_set(self):
        self.item1.set_subtitle_encoding('latin-1')
        self.assertEquals(self.item1.subtitle_encoding, 'latin-1')

    def test_set_on_watched(self):
        # The 1st time an item is marked watched, we should remember the
        # subtitle encoding.
        self.item1.set_subtitle_encoding('latin-9')
        self.assertEquals(self.item2.subtitle_encoding, None)
        self.item2.mark_item_seen()
        self.assertEquals(self.item2.subtitle_encoding, 'latin-9')
        # Test the value isn't re-set the next time it's marked watched
        self.item1.set_subtitle_encoding('latin-5')
        self.item2.mark_item_seen()
        self.assertEquals(self.item2.subtitle_encoding, 'latin-9')

    def test_set_none(self):
        # Test an item is marked seen when the subtitle encoding is None)
        self.item1.mark_item_seen()
        self.assertEquals(self.item2.subtitle_encoding, None)
        self.item2.set_subtitle_encoding('latin-7')
        self.item2.mark_item_seen()
        self.item1.mark_item_seen()
        self.assertEquals(self.item1.subtitle_encoding, None)
