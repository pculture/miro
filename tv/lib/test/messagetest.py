import logging
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
from miro import itemsource
from miro import messages
from miro import messagehandler

from miro.test import mock, testobjects
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
        if isinstance(message, messages.ItemChanges):
            # ItemChanges didn't exist when the unittests were written and
            # it's easier to ignore them then to fix the unittests
            return
        self.messages.append(message)

class TrackerTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        Feed(u'dtv:search')
        self.test_handler = TestFrontendMessageHandler()
        messages.FrontendMessage.install_handler(self.test_handler)
        self.backend_message_handler = messagehandler.BackendMessageHandler(
            None)
        messages.BackendMessage.install_handler(self.backend_message_handler)
        self.channelTabOrder = TabOrder(u'channel')
        self.playlistTabOrder = TabOrder(u'playlist')
        # Adding a guide ensures that if we remove all our
        # channel/playlist tabs the selection code won't go crazy.
        self.guide = ChannelGuide(app.config.get(prefs.CHANNEL_GUIDE_URL))

    def tearDown(self):
        EventLoopTest.tearDown(self)
        messages.BackendMessage.reset_handler()
        messages.FrontendMessage.reset_handler()

    def check_changed_message(self, index, added=None, changed=None,
                              removed=None, **kwargs):
        message = self.test_handler.messages[index]
        self.check_changed_message_type(message, **kwargs)
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

    def check_changed_message_type(self, message, **kwargs):
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
        self.store1 = ChannelGuide(u'http://amazon.com/')
        self.store1.store = ChannelGuide.STORE_VISIBLE
        self.store1.signal_change()
        self.store2 = ChannelGuide(u'http://not-amazon.com/')
        self.store2.store = ChannelGuide.STORE_INVISIBLE
        self.store2.signal_change()
        messages.TrackGuides().send_to_backend()
        self.runUrgentCalls()

    def check_info(self, guideInfo, guide):
        self.assertEquals(guideInfo.name, guide.get_title())
        self.assertEquals(guideInfo.id, guide.id)
        self.assertEquals(guideInfo.url, guide.get_url())
        self.assertEquals(guideInfo.default, guide.is_default())

    def test_initial_list(self):
        self.assertEquals(len(self.test_handler.messages), 2)
        guides, stores = self.test_handler.messages

        self.assert_(isinstance(guides, messages.GuideList))
        self.check_info(guides.default_guide, self.guide)
        self.check_info_list(guides.added_guides, [self.guide1])

        self.assert_(isinstance(stores, messages.StoreList))
        self.check_info_list(stores.visible_stores, [self.store1])
        self.check_info_list(stores.hidden_stores, [self.store2])

    def check_changed_message_type(self, message, type_='site'):
        self.assertEquals(type(message), messages.TabsChanged)
        self.assertEquals(message.type, type_)

    def check_stores_changed_message(self, index, added=None, changed=None,
                            removed=None):
        message = self.test_handler.messages[index]
        self.assertEquals(type(message), messages.StoresChanged)
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

    def test_added(self):
        g = ChannelGuide(u'http://example.com/3')
        self.runUrgentCalls()
        self.check_message_count(3) # GuideList, StoreList
        self.check_changed_message(2, added=[g])

    @uses_httpclient
    def test_removed(self):
        self.guide1.remove()
        self.runUrgentCalls()
        self.check_message_count(3) # GuideList, StoreList, TabsChanged
        self.check_changed_message(2, removed=[self.guide1])

    def test_change(self):
        self.guide1.set_title(u"Booya")
        self.runUrgentCalls()
        self.check_message_count(3) # GuideList, StoreList, TabsChanged
        self.check_changed_message(2, changed=[self.guide1])

    def test_change_invisible(self):
        self.store1.store = ChannelGuide.STORE_INVISIBLE
        self.store1.signal_change()
        self.runUrgentCalls()
        # GuideList, StoreList, StoresChanged, TabsChanged
        self.check_message_count(4)
        self.check_stores_changed_message(2, removed=[self.store1])
        self.check_changed_message(3, removed=[self.store1], type_='store')

    def test_change_visible(self):
        self.store2.store = self.guide1.STORE_VISIBLE
        self.store2.signal_change()
        self.runUrgentCalls()
        # GuideList, StoreList, StoresChanged, TabsChanged
        self.check_message_count(4)
        self.check_stores_changed_message(2, added=[self.store2])
        self.check_changed_message(3, added=[self.store2], type_='store')

    @uses_httpclient
    def test_stop(self):
        self.check_message_count(2) # GuideList, StoreList
        messages.StopTrackingGuides().send_to_backend()
        self.runUrgentCalls()
        self.guide.set_title(u"Booya")
        ChannelGuide(u'http://example.com/3')
        self.guide1.remove()
        self.check_message_count(2)

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
        Feed(u'http://example.com/3')
        self.playlist2.remove()
        self.check_message_count(1)

class FeedTrackTest(TrackerTest):
    def setUp(self):
        TrackerTest.setUp(self)
        self.feed1 = Feed(u'http://example.com/')
        self.feed2 = Feed(u'http://example.com/2')
        self.feed_folder = ChannelFolder(u'test channel folder')
        m = messages.TabsReordered()
        m.toplevels['feed'] = [messages.ChannelInfo(self.feed1),
                               messages.ChannelInfo(self.feed_folder)]
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
        self.assertEquals(message.type, 'feed')

    def test_initial_list(self):
        self.check_message_count(1)
        message1 = self.test_handler.messages[0]
        self.assert_(isinstance(message1, messages.TabList))
        self.assertEquals(message1.type, 'feed')
        self.check_info_list(message1.toplevels, [self.feed1,
                                                  self.feed_folder])
        self.check_info_list(message1.folder_children[self.feed_folder.id],
                             [self.feed2])
        self.assertEquals(len(message1.folder_children), 1)

    def test_added(self):
        f = Feed(u'http://example.com/3')
        self.runUrgentCalls()
        self.check_message_count(2)
        self.check_changed_message(1, added=[f])

    def test_added_order(self):
        f1 = Feed(u'http://example.com/3')
        f2 = Feed(u'http://example.com/4')
        f3 = Feed(u'http://example.com/5')
        f4 = Feed(u'http://example.com/6')
        f5 = Feed(u'http://example.com/7')
        self.runUrgentCalls()
        # We want the ChannelAdded messages to come in the same order
        # the feeds were added
        self.check_changed_message(1, added=[f1, f2, f3, f4, f5])

    @uses_httpclient
    def test_removed(self):
        self.feed2.remove()
        self.runUrgentCalls()
        self.check_message_count(2)
        self.check_changed_message(1, removed=[self.feed2])

    def test_change(self):
        self.feed1.set_title(u"Booya")
        self.runUrgentCalls()
        self.check_message_count(2)
        self.check_changed_message(1, changed=[self.feed1])

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
        self.check_message_count(2)
        self.check_changed_message(1, added=[f2])

    @uses_httpclient
    def test_stop(self):
        self.check_message_count(1)
        messages.StopTrackingChannels().send_to_backend()
        self.runUrgentCalls()
        self.feed1.set_title(u"Booya")
        Feed(u'http://example.com/3')
        self.feed2.remove()
        self.check_message_count(1)
