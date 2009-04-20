import shutil
import tempfile

from miro.feed import Feed
from miro.feedparser import FeedParserDict
from miro.item import Item
from miro.playlist import SavedPlaylist, PlaylistItemMap
from miro.folder import PlaylistFolder, PlaylistFolderItemMap
from miro import app
from miro import storedatabase
from miro import tabs
from miro.test.framework import EventLoopTest, MiroTestCase
from miro.plat import resources

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

    def checkList(self, playlist, correct_order):
        correct_ids = [item.id for item in correct_order]
        actual_ids = list(i.id for i in Item.playlist_view(playlist.id))
        self.assertEquals(actual_ids, correct_ids)

class PlaylistTestCase(PlaylistTestBase):
    def setUp(self):
        PlaylistTestBase.setUp(self)
        self.add_callbacks = []
        self.remove_callbacks = []

    def add_callback(self, tracker, obj):
        self.add_callbacks.append(obj)

    def remove_callback(self, tracker, obj):
        self.remove_callbacks.append(obj)

    def testBasicOperations(self):
        playlist = SavedPlaylist(u"rocketboom")
        self.assertEquals(playlist.get_title(), u'rocketboom')
        self.checkList(playlist, [])
        playlist.add_item(self.i4)
        playlist.add_item(self.i1)
        playlist.add_item(self.i3)
        playlist.add_item(self.i2)
        self.checkList(playlist, [self.i4, self.i1, self.i3, self.i2])
        playlist.add_item(self.i2)
        self.checkList(playlist, [self.i4, self.i1, self.i3, self.i2])
        self.assert_(self.i1.keep)
        self.assert_(self.i2.keep)
        self.assert_(self.i3.keep)
        self.assert_(self.i4.keep)
        playlist.remove_item(self.i2)
        self.checkList(playlist, [self.i4, self.i1, self.i3])
        playlist.reorder([self.i3.id, self.i4.id, self.i1.id])
        self.checkList(playlist, [self.i3, self.i4, self.i1])
        playlist.remove_item(self.i3)
        self.checkList(playlist, [self.i4, self.i1])

    def testInitialList(self):
        initialList = [self.i1, self.i2, self.i3]
        playlist = SavedPlaylist(u"rocketboom", [i.id for i in initialList])
        self.assertEquals(playlist.get_title(), u'rocketboom')
        self.checkList(playlist, initialList)

    def checkCallbacks(self, add_callbacks, remove_callbacks):
        self.assertEquals(self.add_callbacks, add_callbacks)
        self.assertEquals(self.remove_callbacks, remove_callbacks)

    def testCallbacks(self):
        initialList = [self.i1, self.i2, self.i3]
        playlist = SavedPlaylist(u"rocketboom", [i.id for i in initialList])
        tracker = Item.playlist_view(playlist.id).make_tracker()
        tracker.connect('added', self.add_callback)
        tracker.connect('removed', self.remove_callback)
        playlist.add_item(self.i4)
        self.checkCallbacks([self.i4], [])
        playlist.remove_item(self.i3)
        self.checkCallbacks([self.i4], [self.i3])

    def testExpireRemovesItem(self):
        checkList = [self.i1, self.i2, self.i3, self.i4]
        playlist = SavedPlaylist(u"rocketboom", [i.id for i in checkList])
        for i in [self.i1, self.i3, self.i4, self.i2]:
            i.expire()
            checkList.remove(i)
            self.checkList(playlist, checkList)

    def testRemovalRemovesItem(self):
        checkList = [self.i1, self.i2, self.i3, self.i4]
        playlist = SavedPlaylist(u"rocketboom", [i.id for i in checkList])
        for i in [self.i1, self.i3, self.i4, self.i2]:
            i.remove()
            checkList.remove(i)
            self.checkList(playlist, checkList)

class PlaylistFolderTestCase(PlaylistTestBase):
    def setUp(self):
        PlaylistTestBase.setUp(self)
        self.playlistTabOrder = tabs.TabOrder(u'playlist')
        self.p1 = SavedPlaylist(u"rocketboom", [self.i1.id, self.i3.id])
        self.p2 = SavedPlaylist(u"telemusicvision", [self.i4.id, self.i3.id])
        self.p3 = SavedPlaylist(u"digg", [self.i1.id, self.i2.id, self.i3.id, self.i4.id])
        self.folder = PlaylistFolder(u"My Best Vids")
        self.p1.set_folder(self.folder)
        self.p2.set_folder(self.folder)
        self.p3.set_folder(self.folder)

    def check_list(self, correct_order):
        correct_ids = [item.id for item in correct_order]
        actual_ids = list(i.id for i in
                Item.playlist_folder_view(self.folder.id))
        self.assertEquals(actual_ids, correct_ids)

    def test_add_playlists(self):
        self.check_list([self.i1, self.i3, self.i4, self.i2])

    def test_change_folder(self):
        self.p3.set_folder(None)
        self.check_list([self.i1, self.i3, self.i4])
        self.p2.set_folder(None)
        self.check_list([self.i1, self.i3])
        self.p1.set_folder(None)
        self.check_list([])

    def test_remove_playlist(self):
        self.p3.remove()
        self.check_list([self.i1, self.i3, self.i4])
        self.p2.remove()
        self.check_list([self.i1, self.i3])
        self.p1.remove()
        self.check_list([])

    def test_remove_items_from_playlist(self):
        self.p3.remove_item(self.i2)
        self.check_list([self.i1, self.i3, self.i4])
        self.p3.remove_item(self.i3)
        # i3 is still in other children of self.folder, so it shouldn't be
        # removed
        self.check_list([self.i1, self.i3, self.i4])

    def test_order_independent(self):
        self.p3.reorder([self.i4.id, self.i2.id, self.i3.id, self.i1.id])
        self.check_list([self.i1, self.i3, self.i4, self.i2])
        self.folder.reorder([self.i4.id, self.i3.id, self.i2.id, self.i1.id])
        self.check_list([self.i4, self.i3, self.i2, self.i1])

    def test_remove_folder_removes_playlist(self):
        self.folder.remove()
        self.assertEquals(SavedPlaylist.make_view().count(), 0)

class Upgrade88TestCase(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.tmp_path = tempfile.mktemp()

    def tearDown(self):
        try:
            os.remove(self.tmp_path)
        except:
            pass
        MiroTestCase.tearDown(self)

    def test_live_storage_converts(self):
        # run upgrade 88
        old_db_path = resources.path("testdata/olddatabase.predbupgrade88")
        shutil.copyfile(old_db_path, self.tmp_path)
        live_storage = storedatabase.LiveStorage(self.tmp_path)
        live_storage.upgrade_database()
        # figure out which maps were created
        folder_maps = set()
        playlist_maps = set()
        playlists = {}
        items = {}
        for obj in live_storage.load_objects():
            if isinstance(obj, PlaylistFolderItemMap):
                folder_maps.add((obj.playlist_id, obj.item_id, obj.position,
                    obj.count))
                self.assert_(obj.id is not None)
            elif isinstance(obj, PlaylistItemMap):
                playlist_maps.add((obj.playlist_id, obj.item_id,
                    obj.position))
                self.assert_(obj.id is not None)
            elif (isinstance(obj, SavedPlaylist) or
                    isinstance(obj, PlaylistFolder)):
                playlists[obj.title] = obj
            elif isinstance(obj, Item):
                    items[obj.id] = obj
        # Double check that we have the right item ids
        self.assertEquals(items[242].get_title(),
                u"Berliner Brats n' Kraut")
        self.assertEquals(items[240].get_title(),
                u"White Bean & Basil Bruschetta")
        self.assertEquals(items[79].get_title(), u"Meet the GIMP!")
        self.assertEquals(items[69].get_title(),
                u"Delicious TV Vegetarian (video)")
        # check that folder contains playlist 1
        self.assertEquals(playlists['playlist1'].folder_id,
                playlists['folder1'].id)
        self.assertEquals(playlists['playlist2'].folder_id,
                playlists['folder1'].id)
        # Check that the playlist maps follow the following structure:
        #
        # folder1:
        #    - Berliner Brats n' Kraut (id: 242)
        #    - White Bean & Basil Bruschetta (id: 240)
        #    - Meet the GIMP! (id: 79)
        #    - Delicious TV Vegetarian (video) (id: 69)
        # playlist1
        #    - White Bean & Basil Bruschetta (id: 240)
        #    - Berliner Brats n' Kraut (id: 242)
        # playlist2
        #    - Meet the GIMP! (id: 79)
        #    - Delicious TV Vegetarian (video) (id: 69)
        #    - White Bean & Basil Bruschetta (id: 240)
        self.assertEquals(folder_maps, set([
            (playlists['folder1'].id, 242, 0, 1),
            (playlists['folder1'].id, 240, 1, 2),
            (playlists['folder1'].id, 79, 2, 1),
            (playlists['folder1'].id, 69, 3, 1),
        ]))
        self.assertEquals(playlist_maps, set([
            (playlists['playlist1'].id, 240, 0),
            (playlists['playlist1'].id, 242, 1),
            (playlists['playlist2'].id, 79, 0),
            (playlists['playlist2'].id, 69, 1),
            (playlists['playlist2'].id, 240, 2),
        ]))
