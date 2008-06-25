from miro import config
from miro import prefs

from miro.feed import Feed
from miro.guide import ChannelGuide
from miro.item import Item, getEntryForURL
from miro.playlist import SavedPlaylist
from miro.folder import PlaylistFolder, ChannelFolder
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

class BackendMessagesTest(EventLoopTest):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.test_handler = TestFrontendMessageHandler()
        messages.FrontendMessage.install_handler(self.test_handler)
        self.backend_message_handler = messagehandler.BackendMessageHandler()
        messages.BackendMessage.install_handler(self.backend_message_handler)
        self.channelTabOrder = TabOrder(u'channel')
        self.playlistTabOrder = TabOrder(u'playlist')
        # Adding a guide ensures that if we remove all our channel/playlist
        # tabs the selection code won't go crazy.
        ChannelGuide(config.get(prefs.CHANNEL_GUIDE_URL))

    def tearDown(self):
        messages.BackendMessage.install_handler(None)
        messages.FrontendMessage.install_handler(None)
        MiroTestCase.tearDown(self)

class FeedTrackTest(BackendMessagesTest):
    def setUp(self):
        BackendMessagesTest.setUp(self)
        self.feed1 = Feed(u'http://example.com/')
        self.feed2 = Feed(u'http://example.com/2')
        self.feed_folder = ChannelFolder('test channel folder')
        self.feed_folder.handleDNDAppend( set([self.feed2.id]))
        messages.TrackChannels().send_to_backend()
        self.runUrgentCalls()

    def testInitialList(self):
        self.assertEquals(len(self.test_handler.messages), 1)
        message = self.test_handler.messages[0]
        self.assert_(isinstance(message, messages.TabList))
        self.assertEquals(message.type, 'feed')
        self.checkChannelInfoList(message.toplevels, 
                [self.feed1, self.feed_folder])
        self.checkChannelInfoList(message.folder_children[self.feed_folder.id],
                [self.feed2])
        self.assertEquals(len(message.folder_children), 1)

    def checkChannelInfo(self, channelInfo, feed):
        self.assertEquals(channelInfo.name, feed.getTitle())
        self.assertEquals(channelInfo.id, feed.id)
        self.assertEquals(channelInfo.unwatched, feed.numUnwatched())
        self.assertEquals(channelInfo.available, feed.numAvailable())
        self.assertEquals(channelInfo.is_folder,
                isinstance(feed, ChannelFolder))

    def checkChannelInfoList(self, channelInfoList, objects):
        self.assertEquals(len(channelInfoList), len(objects))
        for info, object in zip(channelInfoList, objects):
            self.checkChannelInfo(info, object)

    def checkMessageCount(self, expected_count):
        self.assertEquals(len(self.test_handler.messages), expected_count)

    def checkChangedMessage(self, index, added=None, changed=None,
            removed=None):
        message = self.test_handler.messages[index]
        self.assertEquals(type(message), messages.TabsChanged)
        self.assertEquals(message.type, 'feed')
        if added:
            self.assertEquals(len(added), len(message.added))
            for channel, info in zip(added, message.added):
                self.checkChannelInfo(info, channel)
        else:
            self.assertEquals(len(message.added), 0)
        if changed:
            self.assertEquals(len(changed), len(message.changed))
            def find_changed_info(channel):
                for info in message.changed:
                    if info.id == channel.id:
                        return info
            for channel in changed:
                self.checkChannelInfo(find_changed_info(channel), channel)
        else:
            self.assertEquals(len(message.changed), 0)
        if removed:
            self.assertSameSet([c.id for c in removed], message.removed)
        else:
            self.assertEquals(len(message.removed), 0)

    def testAdded(self):
        f = Feed(u'http://example.com/3')
        self.runUrgentCalls()
        self.checkMessageCount(2)
        self.checkChangedMessage(1, added=[f])

    def testAddedOrder(self):
        f1 = Feed(u'http://example.com/3')
        f2 = Feed(u'http://example.com/4')
        f3 = Feed(u'http://example.com/5')
        f4 = Feed(u'http://example.com/6')
        f5 = Feed(u'http://example.com/7')
        self.runUrgentCalls()
        # We want the ChannelAdded messages to come in the same order the
        # feeds were added
        self.checkChangedMessage(1, added=[f1, f2, f3, f4, f5])

    def testRemoved(self):
        self.feed2.remove()
        self.runUrgentCalls()
        self.checkMessageCount(2)
        self.checkChangedMessage(1, removed=[self.feed2])

    def testChange(self):
        self.feed1.setTitle(u"Booya")
        self.runUrgentCalls()
        self.checkMessageCount(2)
        self.checkChangedMessage(1, changed=[self.feed1])

    def testReduceNumberOfMessages(self):
        f1 = Feed(u'http://example.com/3')
        f1.remove()
        f2 = Feed(u'http://example.com/4')
        f2.setTitle(u'New Title')
        self.runUrgentCalls()
        # We don't need to see that f1 was added because it got removed
        # immediately after.  We don't need to see that f2 was changed because
        # it will have the updated info in added.
        self.checkMessageCount(2)
        self.checkChangedMessage(1, added=[f2])

    def testStop(self):
        self.checkMessageCount(1)
        messages.StopTrackingChannels().send_to_backend()
        self.runUrgentCalls()
        self.feed1.setTitle(u"Booya")
        f = Feed(u'http://example.com/3')
        self.feed2.remove()
        self.checkMessageCount(1)

class PlaylistTrackTest(BackendMessagesTest):
    def setUp(self):
        BackendMessagesTest.setUp(self)
        self.playlist1 = SavedPlaylist(u'Playlist 1')
        self.playlist2 = SavedPlaylist(u'Playlist 2')
        self.folder = PlaylistFolder('Playlist Folder')
        self.folder.handleDNDAppend( set([self.playlist2.id]))
        self.runUrgentCalls()
        messages.TrackPlaylists().send_to_backend()
        self.runUrgentCalls()

    def testInitialList(self):
        self.assertEquals(len(self.test_handler.messages), 1)
        message = self.test_handler.messages[0]
        self.assert_(isinstance(message, messages.TabList))
        self.assertEquals(message.type, 'playlist')
        self.checkPlaylistInfoList(message.toplevels, 
                [self.playlist1, self.folder])
        self.checkPlaylistInfoList(message.folder_children[self.folder.id],
                [self.playlist2])
        self.assertEquals(len(message.folder_children), 1)

    def checkPlaylistInfo(self, playlistInfo, playlist):
        self.assertEquals(playlistInfo.name, playlist.getTitle())
        self.assertEquals(playlistInfo.id, playlist.id)
        self.assertEquals(playlistInfo.is_folder,
                isinstance(playlist, PlaylistFolder))

    def checkPlaylistInfoList(self, playlistInfoList, objects):
        self.assertEquals(len(playlistInfoList), len(objects))
        for info, object in zip(playlistInfoList, objects):
            self.checkPlaylistInfo(info, object)

    def checkChangedMessage(self, index, added=None, changed=None,
            removed=None):
        message = self.test_handler.messages[index]
        self.assertEquals(type(message), messages.TabsChanged)
        self.assertEquals(message.type, 'playlist')
        if added:
            self.assertEquals(len(added), len(message.added))
            for playlist, info in zip(added, message.added):
                self.checkPlaylistInfo(info, playlist)
        else:
            self.assertEquals(len(message.added), 0)
        if changed:
            self.assertEquals(len(changed), len(message.changed))
            def find_changed_info(playlist):
                for info in message.changed:
                    if info.id == playlist.id:
                        return info
            for playlist in changed:
                self.checkPlaylistInfo(find_changed_info(playlist), playlist)
        else:
            self.assertEquals(len(message.changed), 0)
        if removed:
            self.assertSameSet([c.id for c in removed], message.removed)
        else:
            self.assertEquals(len(message.removed), 0)

    def checkMessageCount(self, expected_count):
        self.assertEquals(len(self.test_handler.messages), expected_count)

    def testAdded(self):
        p = SavedPlaylist(u'http://example.com/3')
        self.runUrgentCalls()
        self.checkMessageCount(2)
        self.checkChangedMessage(1, added=[p])

    def testAddedOrder(self):
        p1 = SavedPlaylist('Playlist 2')
        p2 = SavedPlaylist('Playlist 3')
        p3 = SavedPlaylist('Playlist 4')
        p4 = SavedPlaylist('Playlist 5')
        p5 = SavedPlaylist('Playlist 6')
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
        self.playlist1.setTitle(u"Booya")
        self.runUrgentCalls()
        self.checkMessageCount(2)
        self.checkChangedMessage(1, changed=[self.playlist1])

    def testReduceNumberOfMessages(self):
        p1 = SavedPlaylist(u'Playlist')
        p1.remove()
        p2 = SavedPlaylist(u'Playlist 2')
        p2.setTitle(u'New Title')
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
        self.playlist1.setTitle(u"Booya")
        f = Feed(u'http://example.com/3')
        self.playlist2.remove()
        self.checkMessageCount(1)

class FakeDownloader(object):
    def __init__(self):
        self.current_size = 0
        self.rate = 0
        self.state = 'downloading'

    def getCurrentSize(self):
        return self.current_size

    def getRate(self):
        return self.rate

    def getState(self):
        return self.state

class ItemTrackTest(BackendMessagesTest):
    def setUp(self):
        BackendMessagesTest.setUp(self)
        self.items = []
        self.feed = Feed(u'dtv:manualFeed')
        self.make_item(u'http://example.com/')
        self.make_item(u'http://example.com/2')
        self.runUrgentCalls()
        messages.TrackItemsForFeed(self.feed.id).send_to_backend()
        self.runUrgentCalls()

    def make_item(self, url):
        self.items.append(Item(entry=getEntryForURL(url), 
            feed_id=self.feed.id))

    def checkDownloadInfo(self, info, item):
        downloader = item.downloader
        self.assertEquals(info.current_size, downloader.getCurrentSize())
        self.assertEquals(info.rate, downloader.getRate())
        self.assertEquals(info.state, downlader.getState())

    def checkItemInfo(self, itemInfo, item):
        self.assertEquals(itemInfo.name, item.getTitle())
        self.assertEquals(itemInfo.description, item.getDescription())
        self.assertEquals(itemInfo.release_date, item.getReleaseDateObj())
        self.assertEquals(itemInfo.size, item.getSize())
        self.assertEquals(itemInfo.permalink, item.getLink())
        self.assertEquals(itemInfo.id, item.id)
        self.assertEquals(itemInfo.expiration_date, item.getExpirationTime())
        self.assertEquals(itemInfo.thumbnail, item.getThumbnail())
        self.assertEquals(itemInfo.thumbnail_large, item.getThumbnailLarge())
        if item.downloader:
            self.checkDownloadInfo(itemInfo.download_info)
        else:
            self.assertEquals(itemInfo.download_info, None)

    def checkChangedMessage(self, index, added=None, changed=None,
            removed=None):
        message = self.test_handler.messages[index]
        self.assertEquals(type(message), messages.ItemsChanged)
        if added:
            self.assertEquals(len(added), len(message.added))
            for item, info in zip(added, message.added):
                self.checkItemInfo(info, item)
        else:
            self.assertEquals(len(message.added), 0)
        if changed:
            self.assertEquals(len(changed), len(message.changed))
            def find_changed_info(item):
                for info in message.changed:
                    if info.id == item.id:
                        return info
            for item in changed:
                self.checkItemInfo(find_changed_info(item), item)
        else:
            self.assertEquals(len(message.changed), 0)
        if removed:
            self.assertSameSet([c.id for c in removed], message.removed)
        else:
            self.assertEquals(len(message.removed), 0)

    def testInitialList(self):
        self.assertEquals(len(self.test_handler.messages), 1)
        message = self.test_handler.messages[0]
        self.assert_(isinstance(message, messages.ItemList))
        self.assertEquals(message.feed_id, self.feed.id)

        self.assertEquals(len(message.items), len(self.items))
        message.items.sort(key=lambda i: i.id)
        for info, item in zip(message.items, self.items):
            self.checkItemInfo(info, item)

    def testUpdate(self):
        self.items[0].entry.title = u'new name'
        self.items[0].signalChange()
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
        messages.StopTrackingItemsForFeed(self.feed.id).send_to_backend()
        self.runUrgentCalls()
        self.items[0].entry.title = u'new name'
        self.items[0].signalChange()
        self.items[1].remove()
        self.make_item(u'http://example.com/4')
        self.runUrgentCalls()
        self.assertEquals(len(self.test_handler.messages), 1)
