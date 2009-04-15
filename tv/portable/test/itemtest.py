import os
import tempfile
import shutil

from miro.feed import Feed
from miro.item import Item, FileItem
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
