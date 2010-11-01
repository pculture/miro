import cPickle
import functools

from miro import app
from miro import prefs

from miro.feed import Feed
from miro.guide import ChannelGuide
from miro.item import Item, FeedParserValues
from miro.playlist import SavedPlaylist
from miro.folder import PlaylistFolder, ChannelFolder
from miro.singleclick import _build_entry
from miro.tabs import TabOrder
from miro import iteminfocache
from miro import messages
from miro import messagehandler

from miro.test.framework import MiroTestCase, EventLoopTest, uses_httpclient

class MessageOne(messages.BackendMessage):
    pass

class MessageTwo(messages.BackendMessage):
    pass

class TestMessageHandler(messages.MessageHandler):
    def __init__(self, testcase):
        self.testcase = testcase
        messages.MessageHandler.__init__(self)

    def handle_message_one(self, message):
        self.testcase.message_one_count += 1

    def call_handler(self, method, message):
        method(message)

class MessageHandlerTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.message_one_count = 0
        messages.BackendMessage.install_handler(TestMessageHandler(self))

    def tearDown(self):
        MiroTestCase.tearDown(self)
        messages.BackendMessage.reset_handler()

    def test_message_map(self):
        handler = messages.MessageHandler()
        self.assertEquals(handler.calc_message_handler_name(MessageOne),
                'handle_message_one')

    def test_handler(self):
        self.assertEquals(self.message_one_count, 0)
        MessageOne().send_to_backend()
        self.assertEquals(self.message_one_count, 1)

class TestFrontendMessageHandler(object):
    def __init__(self):
        self.messages = []

    def handle(self, message):
        self.messages.append(message)

class TrackerTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        Feed(u'dtv:search')
        self.test_handler = TestFrontendMessageHandler()
        messages.FrontendMessage.install_handler(self.test_handler)
        self.backend_message_handler = messagehandler.BackendMessageHandler(None)
        messages.BackendMessage.install_handler(self.backend_message_handler)
        self.channelTabOrder = TabOrder(u'channel')
        self.audioChannelTabOrder = TabOrder(u'audio-channel')
        self.playlistTabOrder = TabOrder(u'playlist')
        # Adding a guide ensures that if we remove all our
        # channel/playlist tabs the selection code won't go crazy.
        self.guide = ChannelGuide(app.config.get(prefs.CHANNEL_GUIDE_URL))

    def tearDown(self):
        EventLoopTest.tearDown(self)
        messages.BackendMessage.reset_handler()
        messages.FrontendMessage.reset_handler()

    def check_changed_message(self, index, added=None, changed=None,
                              removed=None):
        message = self.test_handler.messages[index]
        self.check_changed_message_type(message)
        if added:
            self.assertEquals(len(added), len(message.added))
            for obj, info in zip(added, message.added):
                self.check_info(info, obj)
        else:
            self.assertEquals(len(message.added), 0)
        if changed:
            self.assertEquals(len(changed), len(message.changed))
            def find_changed_info(obj):
                for info in message.changed:
                    if info.id == obj.id:
                        return info
            for obj in changed:
                self.check_info(find_changed_info(obj), obj)
        else:
            self.assertEquals(len(message.changed), 0)
        if removed:
            self.assertSameSet([c.id for c in removed], message.removed)
        else:
            self.assertEquals(len(message.removed), 0)

    def check_message_count(self, expected_count):
        if len(self.test_handler.messages) != expected_count:
            raise AssertionError(
                "check_message_count(%s) failed.  Messages:\n%s" %
                (expected_count, self.test_handler.messages))

    def check_changed_message_type(self, message):
        raise NotImplementedError()

    def check_info_list(self, info_list, objs):
        self.assertEquals(len(info_list), len(objs))
        for info, obj in zip(info_list, objs):
            self.check_info(info, obj)

    def check_info(self, info, obj):
        raise NotImplementedError()

class GuideTrackTest(TrackerTest):
    def setUp(self):
        TrackerTest.setUp(self)
        self.guide1 = ChannelGuide(u'http://example.com/')
        messages.TrackGuides().send_to_backend()
        self.runUrgentCalls()

    def check_info(self, guideInfo, guide):
        self.assertEquals(guideInfo.name, guide.get_title())
        self.assertEquals(guideInfo.id, guide.id)
        self.assertEquals(guideInfo.url, guide.get_url())
        self.assertEquals(guideInfo.default, guide.is_default())

    def test_initial_list(self):
        self.assertEquals(len(self.test_handler.messages), 1)
        message = self.test_handler.messages[0]
        self.assert_(isinstance(message, messages.GuideList))
        self.check_info(message.default_guide, self.guide)
        self.check_info_list(message.added_guides, [self.guide1])

    def check_changed_message_type(self, message):
        self.assertEquals(type(message), messages.TabsChanged)
        self.assertEquals(message.type, 'guide')

    def test_added(self):
        g = ChannelGuide(u'http://example.com/3')
        self.runUrgentCalls()
        self.check_message_count(2)
        self.check_changed_message(1, added=[g])

    @uses_httpclient
    def test_removed(self):
        self.guide1.remove()
        self.runUrgentCalls()
        self.check_message_count(2)
        self.check_changed_message(1, removed=[self.guide1])

    def test_change(self):
        self.guide1.set_title(u"Booya")
        self.runUrgentCalls()
        self.check_message_count(2)
        self.check_changed_message(1, changed=[self.guide1])

    @uses_httpclient
    def test_stop(self):
        self.check_message_count(1)
        messages.StopTrackingGuides().send_to_backend()
        self.runUrgentCalls()
        self.guide.set_title(u"Booya")
        g = ChannelGuide(u'http://example.com/3')
        self.guide1.remove()
        self.check_message_count(1)

class PlaylistTrackTest(TrackerTest):
    def setUp(self):
        TrackerTest.setUp(self)
        self.playlist1 = SavedPlaylist(u'Playlist 1')
        self.playlist2 = SavedPlaylist(u'Playlist 2')
        self.folder = PlaylistFolder(u'Playlist Folder')
        self.runUrgentCalls()
        messages.TrackPlaylists().send_to_backend()
        self.runUrgentCalls()

    def test_initial_list(self):
        self.assertEquals(len(self.test_handler.messages), 1)
        message = self.test_handler.messages[0]
        self.assert_(isinstance(message, messages.TabList))
        self.assertEquals(message.type, 'playlist')
        self.check_info_list(message.toplevels,
                             [self.playlist1, self.playlist2, self.folder])
        self.check_info_list(message.folder_children[self.folder.id], [])
        self.assertEquals(len(message.folder_children), 1)

    def check_info(self, playlistInfo, playlist):
        self.assertEquals(playlistInfo.name, playlist.get_title())
        self.assertEquals(playlistInfo.id, playlist.id)
        self.assertEquals(playlistInfo.is_folder,
                isinstance(playlist, PlaylistFolder))

    def check_changed_message_type(self, message):
        self.assertEquals(type(message), messages.TabsChanged)
        self.assertEquals(message.type, 'playlist')

    def test_added(self):
        p = SavedPlaylist(u'http://example.com/3')
        self.runUrgentCalls()
        self.check_message_count(2)
        self.check_changed_message(1, added=[p])

    def test_added_order(self):
        p1 = SavedPlaylist(u'Playlist 2')
        p2 = SavedPlaylist(u'Playlist 3')
        p3 = SavedPlaylist(u'Playlist 4')
        p4 = SavedPlaylist(u'Playlist 5')
        p5 = SavedPlaylist(u'Playlist 6')
        self.runUrgentCalls()
        # We want the PlaylistAdded messages to come in the same order
        # the feeds were added.
        self.check_message_count(2)
        self.check_changed_message(1, added=[p1, p2, p3, p4, p5])

    def test_removed(self):
        self.playlist2.remove()
        self.runUrgentCalls()
        self.check_message_count(2)
        self.check_changed_message(1, removed=[self.playlist2])

    def test_change(self):
        self.playlist1.set_title(u"Booya")
        self.runUrgentCalls()
        self.check_message_count(2)
        self.check_changed_message(1, changed=[self.playlist1])

    def test_reduce_number_of_messages(self):
        p1 = SavedPlaylist(u'Playlist')
        p1.remove()
        p2 = SavedPlaylist(u'Playlist 2')
        p2.set_title(u'New Title')
        self.runUrgentCalls()
        # We don't need to see that p1 was added because it got
        # removed immediately after.  We don't need to see that p2 was
        # changed because it will have the updated info in added.
        self.check_message_count(2)
        self.check_changed_message(1, added=[p2])

    def test_stop(self):
        self.check_message_count(1)
        messages.StopTrackingPlaylists().send_to_backend()
        self.runUrgentCalls()
        self.playlist1.set_title(u"Booya")
        f = Feed(u'http://example.com/3')
        self.playlist2.remove()
        self.check_message_count(1)

class FeedTrackTest(TrackerTest):
    def setUp(self):
        TrackerTest.setUp(self)
        self.feed1 = Feed(u'http://example.com/')
        self.feed2 = Feed(u'http://example.com/2')
        self.feed_folder = ChannelFolder(u'test channel folder')
        m = messages.TabsReordered()
        m.toplevels['feed'] = [messages.ChannelInfo(self.feed1)]
        m.toplevels['audio-feed'] = [messages.ChannelInfo(self.feed_folder)]
        m.folder_children[self.feed_folder.id] = \
                [messages.ChannelInfo(self.feed2)]
        m.send_to_backend()
        messages.TrackChannels().send_to_backend()
        self.runUrgentCalls()

    def check_info(self, channelInfo, feed):
        self.assertEquals(channelInfo.name, feed.get_title())
        self.assertEquals(channelInfo.id, feed.id)
        self.assertEquals(channelInfo.unwatched, feed.num_unwatched())
        self.assertEquals(channelInfo.available, feed.num_available())
        self.assertEquals(channelInfo.is_folder,
                          isinstance(feed, ChannelFolder))

    def check_changed_message_type(self, message):
        self.assertEquals(type(message), messages.TabsChanged)
        self.assert_(message.type in ('feed', 'audio-feed'))

    def test_initial_list(self):
        self.check_message_count(2)
        message1 = self.test_handler.messages[0]
        self.assert_(isinstance(message1, messages.TabList))
        self.assertEquals(message1.type, 'feed')
        self.check_info_list(message1.toplevels, [self.feed1])
        self.assertEquals(message1.folder_children, {})
        message2 = self.test_handler.messages[1]
        self.assertEquals(message2.type, 'audio-feed')
        self.check_info_list(message2.toplevels, [self.feed_folder])
        self.check_info_list(message2.folder_children[self.feed_folder.id],
                             [self.feed2])
        self.assertEquals(len(message2.folder_children), 1)

    def test_added(self):
        f = Feed(u'http://example.com/3')
        self.runUrgentCalls()
        self.check_message_count(3)
        self.check_changed_message(2, added=[f])

    def test_added_order(self):
        f1 = Feed(u'http://example.com/3')
        f2 = Feed(u'http://example.com/4')
        f3 = Feed(u'http://example.com/5')
        f4 = Feed(u'http://example.com/6')
        f5 = Feed(u'http://example.com/7')
        self.runUrgentCalls()
        # We want the ChannelAdded messages to come in the same order
        # the feeds were added
        self.check_changed_message(2, added=[f1, f2, f3, f4, f5])

    @uses_httpclient
    def test_removed(self):
        self.feed2.remove()
        self.runUrgentCalls()
        self.check_message_count(3)
        self.check_changed_message(2, removed=[self.feed2])

    def test_change(self):
        self.feed1.set_title(u"Booya")
        self.runUrgentCalls()
        self.check_message_count(3)
        self.check_changed_message(2, changed=[self.feed1])

    @uses_httpclient
    def test_reduce_number_of_messages(self):
        f1 = Feed(u'http://example.com/3')
        f1.remove()
        f2 = Feed(u'http://example.com/4')
        f2.set_title(u'New Title')
        self.runUrgentCalls()
        # We don't need to see that f1 was added because it got
        # removed immediately after.  We don't need to see that f2 was
        # changed because it will have the updated info in added.
        self.check_message_count(3)
        self.check_changed_message(2, added=[f2])

    @uses_httpclient
    def test_stop(self):
        self.check_message_count(2)
        messages.StopTrackingChannels().send_to_backend()
        self.runUrgentCalls()
        self.feed1.set_title(u"Booya")
        f = Feed(u'http://example.com/3')
        self.feed2.remove()
        self.check_message_count(2)

class FakeDownloader(object):
    def __init__(self):
        self.current_size = 0
        self.rate = 0
        self.state = 'downloading'

    def get_current_size(self):
        return self.current_size

    def get_rate(self):
        return self.rate

    def get_state(self):
        return self.state

class FeedItemTrackTest(TrackerTest):
    def setUp(self):
        TrackerTest.setUp(self)
        self.items = []
        self.feed = Feed(u'dtv:manualFeed')
        self.make_item(u'http://example.com/')
        self.make_item(u'http://example.com/2')
        self.runUrgentCalls()
        messages.TrackItems('feed', self.feed.id).send_to_backend()
        self.runUrgentCalls()

    def make_item(self, url):
        entry = _build_entry(url, 'video/x-unknown')
        item_ = Item(FeedParserValues(entry), feed_id=self.feed.id)
        self.items.append(item_)

    def checkDownloadInfo(self, info, item):
        downloader = item.downloader
        self.assertEquals(info.current_size, downloader.get_current_size())
        self.assertEquals(info.rate, downloader.get_rate())
        self.assertEquals(info.state, downloader.get_state())

    def check_info(self, itemInfo, item):
        self.assertEquals(itemInfo.name, item.get_title())
        self.assertEquals(itemInfo.description, item.get_description())
        self.assertEquals(itemInfo.release_date, item.get_release_date_obj())
        self.assertEquals(itemInfo.size, item.get_size())
        self.assertEquals(itemInfo.permalink, item.get_link())
        self.assertEquals(itemInfo.id, item.id)
        self.assertEquals(itemInfo.expiration_date, item.get_expiration_time())
        self.assertEquals(itemInfo.thumbnail, item.get_thumbnail())
        if item.downloader:
            self.checkDownloadInfo(itemInfo.download_info)
        else:
            self.assertEquals(itemInfo.download_info, None)

    def check_changed_message_type(self, message):
        self.assertEquals(type(message), messages.ItemsChanged)
        self.assertEquals(message.type, 'feed')

    def test_initial_list(self):
        self.assertEquals(len(self.test_handler.messages), 1)
        message = self.test_handler.messages[0]
        self.assert_(isinstance(message, messages.ItemList))
        self.assertEquals(message.type, 'feed')
        self.assertEquals(message.id, self.feed.id)

        self.assertEquals(len(message.items), len(self.items))
        message.items.sort(key=lambda i: i.id)
        self.check_info_list(message.items, self.items)

    def test_update(self):
        self.items[0].entry_title = u'new name'
        self.items[0].signal_change()
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 2)
        self.check_changed_message(1, changed=[self.items[0]])

    def test_add(self):
        self.make_item(u'http://example.com/3')
        self.make_item(u'http://example.com/4')
        self.make_item(u'http://example.com/5')
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 2)
        self.check_changed_message(1, added=self.items[2:])

    def test_remove(self):
        self.items[1].remove()
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 2)
        self.check_changed_message(1, removed=[self.items[1]])

    def test_stop(self):
        messages.StopTrackingItems('feed', self.feed.id).send_to_backend()
        self.runUrgentCalls()
        self.items[0].entry_title = u'new name'
        self.items[0].signal_change()
        self.items[1].remove()
        self.make_item(u'http://example.com/4')
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 1)

class PlaylistItemTrackTest(TrackerTest):
    def setUp(self):
        TrackerTest.setUp(self)
        self.items = []
        self.feed = Feed(u'dtv:manualFeed')
        self.playlist = SavedPlaylist(u'test playlist')
        self.make_item(u'http://example.com/')
        self.make_item(u'http://example.com/2')
        self.runUrgentCalls()
        messages.TrackItems('playlist', self.playlist.id).send_to_backend()
        self.runUrgentCalls()

    def make_item(self, url):
        entry = _build_entry(url, 'video/x-unknown')
        item_ = Item(FeedParserValues(entry), feed_id=self.feed.id)
        self.items.append(item_)
        self.playlist.add_item(item_)

    def checkDownloadInfo(self, info, item):
        downloader = item.downloader
        self.assertEquals(info.current_size, downloader.get_current_size())
        self.assertEquals(info.rate, downloader.get_rate())
        self.assertEquals(info.state, downloader.get_state())

    def check_info(self, itemInfo, item):
        self.assertEquals(itemInfo.name, item.get_title())
        self.assertEquals(itemInfo.description, item.get_description())
        self.assertEquals(itemInfo.release_date, item.get_release_date_obj())
        self.assertEquals(itemInfo.size, item.get_size())
        self.assertEquals(itemInfo.permalink, item.get_link())
        self.assertEquals(itemInfo.id, item.id)
        self.assertEquals(itemInfo.expiration_date, item.get_expiration_time())
        self.assertEquals(itemInfo.thumbnail, item.get_thumbnail())
        if item.downloader:
            self.checkDownloadInfo(itemInfo.download_info)
        else:
            self.assertEquals(itemInfo.download_info, None)

    def check_changed_message_type(self, message):
        self.assertEquals(type(message), messages.ItemsChanged)
        self.assertEquals(message.type, 'playlist')

    def test_initial_list(self):
        self.assertEquals(len(self.test_handler.messages), 1)
        message = self.test_handler.messages[0]
        self.assert_(isinstance(message, messages.ItemList))
        self.assertEquals(message.type, 'playlist')
        self.assertEquals(message.id, self.playlist.id)

        self.assertEquals(len(message.items), len(self.items))
        message.items.sort(key=lambda i: i.id)
        self.check_info_list(message.items, self.items)

    def test_update(self):
        self.items[0].entry_title = u'new name'
        self.items[0].signal_change()
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 2)
        self.check_changed_message(1, changed=[self.items[0]])

    def test_add(self):
        self.make_item(u'http://example.com/3')
        self.make_item(u'http://example.com/4')
        self.make_item(u'http://example.com/5')
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 2)
        self.check_changed_message(1, added=self.items[2:])

    def test_remove(self):
        self.items[1].remove()
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 2)
        self.check_changed_message(1, removed=[self.items[1]])

    def test_stop(self):
        messages.StopTrackingItems(
            'playlist', self.playlist.id).send_to_backend()
        self.runUrgentCalls()
        self.items[0].entry_title = u'new name'
        self.items[0].signal_change()
        self.items[1].remove()
        self.make_item(u'http://example.com/4')
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 1)


class ItemInfoCacheTest(FeedItemTrackTest):
    # this class runs the exact same tests as FeedItemTrackTest, but using
    # values read from the item_info_cache file.  Also, we check to make sure
    # that item_info_cache.save() after the test doesn't raise an exception.
    def __init__(self, testMethodName='runTest'):
        # little hack to call app.item_info_cache.save() at the end of our test
        # method
        FeedItemTrackTest.__init__(self, testMethodName)
        org_test_method = getattr(self, self._testMethodName)
        def wrapper():
            org_test_method()
            app.db.finish_transaction()
            app.item_info_cache.save()
        test_with_save_at_end = functools.update_wrapper(wrapper,
                org_test_method)
        setattr(self, self._testMethodName, test_with_save_at_end)

    def setUp(self):
        FeedItemTrackTest.setUp(self)
        app.db.finish_transaction()
        app.item_info_cache.save()
        app.item_info_cache = iteminfocache.ItemInfoCache()

class ItemInfoCacheErrorTest(MiroTestCase):
    # Test errors when loading the Item info cache
    def setUp(self):
        MiroTestCase.setUp(self)
        self.items = []
        self.feed = Feed(u'dtv:manualFeed')
        self.make_item(u'http://example.com/')
        self.make_item(u'http://example.com/2')

    def make_item(self, url):
        entry = _build_entry(url, 'video/x-unknown')
        item_ = Item(FeedParserValues(entry), feed_id=self.feed.id)
        self.items.append(item_)

    def test_failsafe_load(self):
        # Make sure current data is saved
        app.db.finish_transaction()
        app.item_info_cache.save()
        # insert bogus values into the db
        app.db.cursor.execute("UPDATE item_info_cache SET pickle='BOGUS'")
        # this should fallback to the failsafe values
        app.item_info_cache = iteminfocache.ItemInfoCache()
        for item in self.items:
            cache_info = app.item_info_cache.id_to_info[item.id]
            real_info = messages.ItemInfo(item)
            self.assertEquals(cache_info.__dict__, real_info.__dict__)
        # it should also delete all data from the item cache table
        app.db.cursor.execute("SELECT COUNT(*) FROM item_info_cache")
        self.assertEquals(app.db.cursor.fetchone()[0], 0)
        # Next call to save() should fix the data
        app.db.finish_transaction()
        app.item_info_cache.save()
        app.db.cursor.execute("SELECT COUNT(*) FROM item_info_cache")
        self.assertEquals(app.db.cursor.fetchone()[0], len(self.items))
        for item in self.items:
            app.db.cursor.execute("SELECT pickle FROM item_info_cache "
                    "WHERE id=%s" % item.id)
            db_info = cPickle.loads(str(app.db.cursor.fetchone()[0]))
            real_info = messages.ItemInfo(item)
            self.assertEquals(db_info.__dict__, real_info.__dict__)

    def test_item_info_version(self):
        app.db.finish_transaction()
        app.item_info_cache.save()
        messages.ItemInfo.VERSION += 1
        # We should delete the old cache data because ItemInfoCache.VERSION
        # has changed
        app.item_info_cache = iteminfocache.ItemInfoCache()
        app.db.cursor.execute("SELECT COUNT(*) FROM item_info_cache")
        self.assertEquals(app.db.cursor.fetchone()[0], 0)
