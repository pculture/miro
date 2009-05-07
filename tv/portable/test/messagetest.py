from miro import config
from miro import prefs

from miro.feed import Feed
from miro.guide import ChannelGuide
from miro.item import Item
from miro.playlist import SavedPlaylist
from miro.folder import PlaylistFolder, ChannelFolder
from miro.singleclick import _build_entry
from miro.tabs import TabOrder
from miro import messages
from miro import messagehandler

from miro.test.framework import MiroTestCase, EventLoopTest

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
        messages.BackendMessage.install_handler(None)

    def testMessageMap(self):
        handler = messages.MessageHandler()
        self.assertEquals(handler.calc_message_handler_name(MessageOne),
                'handle_message_one')

    def testHandler(self):
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
        # Adding a guide ensures that if we remove all our channel/playlist
        # tabs the selection code won't go crazy.
        self.guide = ChannelGuide(config.get(prefs.CHANNEL_GUIDE_URL))

    def tearDown(self):
        EventLoopTest.tearDown(self)
        messages.BackendMessage.install_handler(None)
        messages.FrontendMessage.install_handler(None)

    def checkChangedMessage(self, index, added=None, changed=None,
            removed=None):
        message = self.test_handler.messages[index]
        self.checkChangedMessageType(message)
        if added:
            self.assertEquals(len(added), len(message.added))
            for object, info in zip(added, message.added):
                self.checkInfo(info, object)
        else:
            self.assertEquals(len(message.added), 0)
        if changed:
            self.assertEquals(len(changed), len(message.changed))
            def find_changed_info(object):
                for info in message.changed:
                    if info.id == object.id:
                        return info
            for object in changed:
                self.checkInfo(find_changed_info(object), object)
        else:
            self.assertEquals(len(message.changed), 0)
        if removed:
            self.assertSameSet([c.id for c in removed], message.removed)
        else:
            self.assertEquals(len(message.removed), 0)

    def checkMessageCount(self, expected_count):
        if len(self.test_handler.messages) != expected_count:
            raise AssertionError(
                    "checkMessageCount(%s) failed.  Messages:\n%s" %
                    (expected_count, self.test_handler.messages))

    def checkChangedMessageType(self, message):
        raise NotImplementedError()

    def checkInfoList(self, infoList, objects):
        self.assertEquals(len(infoList), len(objects))
        for info, object in zip(infoList, objects):
            self.checkInfo(info, object)

    def checkInfo(self, info, object):
        raise NotImplementedError()

class GuideTrackTest(TrackerTest):
    def setUp(self):
        TrackerTest.setUp(self)
        self.guide1 = ChannelGuide(u'http://example.com/')
        messages.TrackGuides().send_to_backend()
        self.runUrgentCalls()

    def checkInfo(self, guideInfo, guide):
        self.assertEquals(guideInfo.name, guide.get_title())
        self.assertEquals(guideInfo.id, guide.id)
        self.assertEquals(guideInfo.url, guide.get_url())
        self.assertEquals(guideInfo.default, guide.get_default())

    def testInitialList(self):
        self.assertEquals(len(self.test_handler.messages), 1)
        message = self.test_handler.messages[0]
        self.assert_(isinstance(message, messages.GuideList))
        self.checkInfo(message.default_guide, self.guide)
        self.checkInfoList(message.added_guides, [self.guide1])

    def checkChangedMessageType(self, message):
        self.assertEquals(type(message), messages.TabsChanged)
        self.assertEquals(message.type, 'guide')

    def testAdded(self):
        g = ChannelGuide(u'http://example.com/3')
        self.runUrgentCalls()
        self.checkMessageCount(2)
        self.checkChangedMessage(1, added=[g])

    def testRemoved(self):
        self.guide1.remove()
        self.runUrgentCalls()
        self.checkMessageCount(2)
        self.checkChangedMessage(1, removed=[self.guide1])

    def testChange(self):
        self.guide1.set_title(u"Booya")
        self.runUrgentCalls()
        self.checkMessageCount(2)
        self.checkChangedMessage(1, changed=[self.guide1])

    def testStop(self):
        self.checkMessageCount(1)
        messages.StopTrackingGuides().send_to_backend()
        self.runUrgentCalls()
        self.guide.set_title(u"Booya")
        g = ChannelGuide(u'http://example.com/3')
        self.guide1.remove()
        self.checkMessageCount(1)

class PlaylistTrackTest(TrackerTest):
    def setUp(self):
        TrackerTest.setUp(self)
        self.playlist1 = SavedPlaylist(u'Playlist 1')
        self.playlist2 = SavedPlaylist(u'Playlist 2')
        self.folder = PlaylistFolder(u'Playlist Folder')
#        self.folder.handleDNDAppend( set([self.playlist2.id]))
        self.runUrgentCalls()
        messages.TrackPlaylists().send_to_backend()
        self.runUrgentCalls()

#    def testInitialList(self):
#        self.assertEquals(len(self.test_handler.messages), 1)
#        message = self.test_handler.messages[0]
#        self.assert_(isinstance(message, messages.TabList))
#        self.assertEquals(message.type, 'playlist')
#        self.checkInfoList(message.toplevels,
#                [self.playlist1, self.folder])
#        self.checkInfoList(message.folder_children[self.folder.id],
#                [self.playlist2])
#        self.assertEquals(len(message.folder_children), 1)

    def checkInfo(self, playlistInfo, playlist):
        self.assertEquals(playlistInfo.name, playlist.get_title())
        self.assertEquals(playlistInfo.id, playlist.id)
        self.assertEquals(playlistInfo.is_folder,
                isinstance(playlist, PlaylistFolder))

    def checkChangedMessageType(self, message):
        self.assertEquals(type(message), messages.TabsChanged)
        self.assertEquals(message.type, 'playlist')

    def testAdded(self):
        p = SavedPlaylist(u'http://example.com/3')
        self.runUrgentCalls()
        self.checkMessageCount(2)
        self.checkChangedMessage(1, added=[p])

    def testAddedOrder(self):
        p1 = SavedPlaylist(u'Playlist 2')
        p2 = SavedPlaylist(u'Playlist 3')
        p3 = SavedPlaylist(u'Playlist 4')
        p4 = SavedPlaylist(u'Playlist 5')
        p5 = SavedPlaylist(u'Playlist 6')
        self.runUrgentCalls()
        # We want the PlaylistAdded messages to come in the same order the
        # feeds were added.
        self.checkMessageCount(2)
        self.checkChangedMessage(1, added=[p1, p2, p3, p4, p5])

    def testRemoved(self):
        self.playlist2.remove()
        self.runUrgentCalls()
        self.checkMessageCount(2)
        self.checkChangedMessage(1, removed=[self.playlist2])

    def testChange(self):
        self.playlist1.set_title(u"Booya")
        self.runUrgentCalls()
        self.checkMessageCount(2)
        self.checkChangedMessage(1, changed=[self.playlist1])

    def testReduceNumberOfMessages(self):
        p1 = SavedPlaylist(u'Playlist')
        p1.remove()
        p2 = SavedPlaylist(u'Playlist 2')
        p2.set_title(u'New Title')
        self.runUrgentCalls()
        # We don't need to see that p1 was added because it got removed
        # immediately after.  We don't need to see that p2 was changed because
        # it will have the updated info in added.
        self.checkMessageCount(2)
        self.checkChangedMessage(1, added=[p2])

    def testStop(self):
        self.checkMessageCount(1)
        messages.StopTrackingPlaylists().send_to_backend()
        self.runUrgentCalls()
        self.playlist1.set_title(u"Booya")
        f = Feed(u'http://example.com/3')
        self.playlist2.remove()
        self.checkMessageCount(1)

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

    def checkInfo(self, channelInfo, feed):
        self.assertEquals(channelInfo.name, feed.get_title())
        self.assertEquals(channelInfo.id, feed.id)
        self.assertEquals(channelInfo.unwatched, feed.num_unwatched())
        self.assertEquals(channelInfo.available, feed.num_available())
        self.assertEquals(channelInfo.is_folder,
                isinstance(feed, ChannelFolder))

    def checkChangedMessageType(self, message):
        self.assertEquals(type(message), messages.TabsChanged)
        self.assert_(message.type in ('feed', 'audio-feed'))

    def testInitialList(self):
        self.checkMessageCount(2)
        message1 = self.test_handler.messages[0]
        self.assert_(isinstance(message1, messages.TabList))
        self.assertEquals(message1.type, 'feed')
        self.checkInfoList(message1.toplevels, [self.feed1])
        self.assertEquals(message1.folder_children, {})
        message2 = self.test_handler.messages[1]
        self.assertEquals(message2.type, 'audio-feed')
        self.checkInfoList(message2.toplevels, [self.feed_folder])
        self.checkInfoList(message2.folder_children[self.feed_folder.id],
                [self.feed2])
        self.assertEquals(len(message2.folder_children), 1)

    def testAdded(self):
        f = Feed(u'http://example.com/3')
        self.runUrgentCalls()
        self.checkMessageCount(3)
        self.checkChangedMessage(2, added=[f])

    def testAddedOrder(self):
        f1 = Feed(u'http://example.com/3')
        f2 = Feed(u'http://example.com/4')
        f3 = Feed(u'http://example.com/5')
        f4 = Feed(u'http://example.com/6')
        f5 = Feed(u'http://example.com/7')
        self.runUrgentCalls()
        # We want the ChannelAdded messages to come in the same order the
        # feeds were added
        self.checkChangedMessage(2, added=[f1, f2, f3, f4, f5])

    def testRemoved(self):
        self.feed2.remove()
        self.runUrgentCalls()
        self.checkMessageCount(3)
        self.checkChangedMessage(2, removed=[self.feed2])

    def testChange(self):
        self.feed1.set_title(u"Booya")
        self.runUrgentCalls()
        self.checkMessageCount(3)
        self.checkChangedMessage(2, changed=[self.feed1])

    def testReduceNumberOfMessages(self):
        f1 = Feed(u'http://example.com/3')
        f1.remove()
        f2 = Feed(u'http://example.com/4')
        f2.set_title(u'New Title')
        self.runUrgentCalls()
        # We don't need to see that f1 was added because it got removed
        # immediately after.  We don't need to see that f2 was changed because
        # it will have the updated info in added.
        self.checkMessageCount(3)
        self.checkChangedMessage(2, added=[f2])

    def testStop(self):
        self.checkMessageCount(2)
        messages.StopTrackingChannels().send_to_backend()
        self.runUrgentCalls()
        self.feed1.set_title(u"Booya")
        f = Feed(u'http://example.com/3')
        self.feed2.remove()
        self.checkMessageCount(2)

class FakeDownloader(object):
    def __init__(self):
        self.current_size = 0
        self.rate = 0
        self.state = 'downloading'

    def get_current_size(self):
        return self.current_size

    def getRate(self):
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
        self.items.append(Item(entry=_build_entry(url, 'video/x-unknown'),
            feed_id=self.feed.id))

    def checkDownloadInfo(self, info, item):
        downloader = item.downloader
        self.assertEquals(info.current_size, downloader.get_current_size())
        self.assertEquals(info.rate, downloader.getRate())
        self.assertEquals(info.state, downloader.get_state())

    def checkInfo(self, itemInfo, item):
        self.assertEquals(itemInfo.name, item.get_title())
        self.assertEquals(itemInfo.description, item.get_description())
        self.assertEquals(itemInfo.release_date, item.get_release_date_obj())
        self.assertEquals(itemInfo.size, item.get_size())
        self.assertEquals(itemInfo.permalink, item.get_link())
        self.assertEquals(itemInfo.id, item.id)
        self.assertEquals(itemInfo.expiration_date, item.get_expiration_time())
        self.assertEquals(itemInfo.thumbnail, item.getThumbnail())
        if item.downloader:
            self.checkDownloadInfo(itemInfo.download_info)
        else:
            self.assertEquals(itemInfo.download_info, None)

    def checkChangedMessageType(self, message):
        self.assertEquals(type(message), messages.ItemsChanged)
        self.assertEquals(message.type, 'feed')

    def testInitialList(self):
        self.assertEquals(len(self.test_handler.messages), 1)
        message = self.test_handler.messages[0]
        self.assert_(isinstance(message, messages.ItemList))
        self.assertEquals(message.type, 'feed')
        self.assertEquals(message.id, self.feed.id)

        self.assertEquals(len(message.items), len(self.items))
        message.items.sort(key=lambda i: i.id)
        self.checkInfoList(message.items, self.items)

    def testUpdate(self):
        self.items[0].entry_title = u'new name'
        self.items[0].signal_change()
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 2)
        self.checkChangedMessage(1, changed=[self.items[0]])

    def testAdd(self):
        self.make_item(u'http://example.com/3')
        self.make_item(u'http://example.com/4')
        self.make_item(u'http://example.com/5')
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 2)
        self.checkChangedMessage(1, added=self.items[2:])

    def testRemove(self):
        self.items[1].remove()
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 2)
        self.checkChangedMessage(1, removed=[self.items[1]])

    def testStop(self):
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
        item = Item(entry=_build_entry(url, 'video/x-unknown'),
                    feed_id=self.feed.id)
        self.items.append(item)
        self.playlist.add_item(item)

    def checkDownloadInfo(self, info, item):
        downloader = item.downloader
        self.assertEquals(info.current_size, downloader.get_current_size())
        self.assertEquals(info.rate, downloader.getRate())
        self.assertEquals(info.state, downloader.get_state())

    def checkInfo(self, itemInfo, item):
        self.assertEquals(itemInfo.name, item.get_title())
        self.assertEquals(itemInfo.description, item.get_description())
        self.assertEquals(itemInfo.release_date, item.get_release_date_obj())
        self.assertEquals(itemInfo.size, item.get_size())
        self.assertEquals(itemInfo.permalink, item.get_link())
        self.assertEquals(itemInfo.id, item.id)
        self.assertEquals(itemInfo.expiration_date, item.get_expiration_time())
        self.assertEquals(itemInfo.thumbnail, item.getThumbnail())
        if item.downloader:
            self.checkDownloadInfo(itemInfo.download_info)
        else:
            self.assertEquals(itemInfo.download_info, None)

    def checkChangedMessageType(self, message):
        self.assertEquals(type(message), messages.ItemsChanged)
        self.assertEquals(message.type, 'playlist')

    def testInitialList(self):
        self.assertEquals(len(self.test_handler.messages), 1)
        message = self.test_handler.messages[0]
        self.assert_(isinstance(message, messages.ItemList))
        self.assertEquals(message.type, 'playlist')
        self.assertEquals(message.id, self.playlist.id)

        self.assertEquals(len(message.items), len(self.items))
        message.items.sort(key=lambda i: i.id)
        self.checkInfoList(message.items, self.items)

    def testUpdate(self):
        self.items[0].entry_title = u'new name'
        self.items[0].signal_change()
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 2)
        self.checkChangedMessage(1, changed=[self.items[0]])

    def testAdd(self):
        self.make_item(u'http://example.com/3')
        self.make_item(u'http://example.com/4')
        self.make_item(u'http://example.com/5')
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 2)
        self.checkChangedMessage(1, added=self.items[2:])

    def testRemove(self):
        self.items[1].remove()
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 2)
        self.checkChangedMessage(1, removed=[self.items[1]])

    def testStop(self):
        messages.StopTrackingItems('playlist', self.playlist.id).send_to_backend()
        self.runUrgentCalls()
        self.items[0].entry_title = u'new name'
        self.items[0].signal_change()
        self.items[1].remove()
        self.make_item(u'http://example.com/4')
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 1)
