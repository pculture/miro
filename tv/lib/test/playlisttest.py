import shutil
import os

from miro.feed import Feed
from miro.item import Item, FeedParserValues
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
        self.i1 = Item(FeedParserValues({'title': u'item1'}),
                       feed_id=self.feed.id)
        self.i2 = Item(FeedParserValues({'title': u'item2'}),
                       feed_id=self.feed.id)
        self.i3 = Item(FeedParserValues({'title': u'item3'}),
                       feed_id=self.feed.id)
        self.i4 = Item(FeedParserValues({'title': u'item4'}),
                       feed_id=self.feed.id)

    def check_list(self, playlist, correct_order):
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

    def test_basic_operations(self):
        playlist = SavedPlaylist(u"rocketboom")
        self.assertEquals(playlist.get_title(), u'rocketboom')
        self.check_list(playlist, [])
        playlist.add_item(self.i4)
        playlist.add_item(self.i1)
        playlist.add_item(self.i3)
        playlist.add_item(self.i2)
        self.check_list(playlist, [self.i4, self.i1, self.i3, self.i2])
        playlist.add_item(self.i2)
        self.check_list(playlist, [self.i4, self.i1, self.i3, self.i2])
        self.assert_(self.i1.keep)
        self.assert_(self.i2.keep)
        self.assert_(self.i3.keep)
        self.assert_(self.i4.keep)
        playlist.remove_item(self.i2)
        self.check_list(playlist, [self.i4, self.i1, self.i3])
        playlist.reorder([self.i3.id, self.i4.id, self.i1.id])
        self.check_list(playlist, [self.i3, self.i4, self.i1])
        playlist.remove_item(self.i3)
        self.check_list(playlist, [self.i4, self.i1])

    def test_initial_list(self):
        initialList = [self.i1, self.i2, self.i3]
        playlist = SavedPlaylist(u"rocketboom", [i.id for i in initialList])
        self.assertEquals(playlist.get_title(), u'rocketboom')
        self.check_list(playlist, initialList)

    def check_callbacks(self, add_callbacks, remove_callbacks):
        self.assertEquals(self.add_callbacks, add_callbacks)
        self.assertEquals(self.remove_callbacks, remove_callbacks)

    def test_callbacks(self):
        initialList = [self.i1, self.i2, self.i3]
        playlist = SavedPlaylist(u"rocketboom", [i.id for i in initialList])
        tracker = Item.playlist_view(playlist.id).make_tracker()
        tracker.connect('added', self.add_callback)
        tracker.connect('removed', self.remove_callback)
        playlist.add_item(self.i4)
        self.check_callbacks([self.i4], [])
        playlist.remove_item(self.i3)
        self.check_callbacks([self.i4], [self.i3])

    def test_expire_removes_item(self):
        check_list = [self.i1, self.i2, self.i3, self.i4]
        playlist = SavedPlaylist(u"rocketboom", [i.id for i in check_list])
        for i in [self.i1, self.i3, self.i4, self.i2]:
            i.expire()
            check_list.remove(i)
            self.check_list(playlist, check_list)

    def test_removal_removes_item(self):
        check_list = [self.i1, self.i2, self.i3, self.i4]
        playlist = SavedPlaylist(u"rocketboom", [i.id for i in check_list])
        self.check_list(playlist, check_list)
        for i in [self.i1, self.i3, self.i4, self.i2]:
            i.remove()
            check_list.remove(i)
            self.check_list(playlist, check_list)

class PlaylistFolderTestCase(PlaylistTestBase):
    def setUp(self):
        PlaylistTestBase.setUp(self)
        self.playlistTabOrder = tabs.TabOrder(u'playlist')
        self.p1 = SavedPlaylist(u"rocketboom", [self.i1.id, self.i3.id])
        self.p2 = SavedPlaylist(u"telemusicvision", [self.i4.id, self.i3.id])
        self.p3 = SavedPlaylist(u"digg", [self.i1.id, self.i2.id,
                                          self.i3.id, self.i4.id])
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
        # i3 is still in other children of self.folder, so it
        # shouldn't be removed
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
        self.tmp_path = self.make_temp_path()

    def tearDown(self):
        try:
            os.remove(self.tmp_path)
        except StandardError:
            pass
        MiroTestCase.tearDown(self)

    def test_live_storage_converts(self):
        # FIXME - this test fails on Windows.  I'm pretty sure we need
        # a Windows-specific predbupgrade88 because the databases are
        # platform specific.
        if self.on_windows():
            self.assert_(False, "test_live_storage_converts fails on windows")
        # run upgrade 88
        old_db_path = resources.path("testdata/olddatabase.predbupgrade88")
        shutil.copyfile(old_db_path, self.tmp_path)
        self.reload_database(self.tmp_path)
        app.db.upgrade_database()
        # figure out which maps were created
        folder_maps = set()
        playlist_maps = set()
        for map in PlaylistFolderItemMap.make_view():
            folder_maps.add((map.playlist_id, map.item_id, map.position,
                map.count))
            self.assert_(map.id is not None)

        for map in PlaylistItemMap.make_view():
            playlist_maps.add((map.playlist_id, map.item_id, map.position))
            self.assert_(map.id is not None)

        playlist1 = SavedPlaylist.make_view("title='playlist1'").get_singleton()
        playlist2 = SavedPlaylist.make_view("title='playlist2'").get_singleton()
        folder = PlaylistFolder.make_view().get_singleton()

        # Double check that we have the right item ids
        self.assertEquals(Item.get_by_id(242).get_title(),
                u"Berliner Brats n' Kraut")
        self.assertEquals(Item.get_by_id(240).get_title(),
                u"White Bean & Basil Bruschetta")
        self.assertEquals(Item.get_by_id(79).get_title(), u"Meet the GIMP!")
        self.assertEquals(Item.get_by_id(69).get_title(),
                u"Delicious TV Vegetarian (video)")
        # check that folder contains playlist 1
        self.assertEquals(playlist1.folder_id, folder.id)
        self.assertEquals(playlist2.folder_id, folder.id)
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
            (folder.id, 242, 0, 1),
            (folder.id, 240, 1, 2),
            (folder.id, 79, 2, 1),
            (folder.id, 69, 3, 1),
        ]))
        self.assertEquals(playlist_maps, set([
            (playlist1.id, 240, 0),
            (playlist1.id, 242, 1),
            (playlist2.id, 79, 0),
            (playlist2.id, 69, 1),
            (playlist2.id, 240, 2),
        ]))
