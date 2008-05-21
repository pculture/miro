from miro.feed import Feed
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

    def testNoMethod(self):
        # Our test handle doesn't define a method to handle MessageTwo.  Make
        # sure we don't throw an exception in this case.
        MessageTwo().send_to_backend()

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
        messages.BackendMessage.install_handler(
                messagehandler.BackendMessageHandler())
        self.channelTabOrder = TabOrder(u'channel')
        self.playlistTabOrder = TabOrder(u'playlist')

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
        self.runPendingIdles()
        messages.TrackChannels().send_to_backend()
        self.runPendingIdles()

    def testInitialList(self):
        self.assertEquals(len(self.test_handler.messages), 1)
        message = self.test_handler.messages[0]
        self.assert_(isinstance(message, messages.ChannelList))
        self.assertEquals(len(message.channels), 2)
        self.checkChannelInfo(message.channels[0], self.feed1)
        self.checkChannelInfo(message.channels[1], self.feed_folder)

    def checkChannelInfo(self, channelInfo, feed):
        self.assertEquals(channelInfo.name, feed.getTitle())
        self.assertEquals(channelInfo.id, feed.id)
        self.assertEquals(channelInfo.unwatched, feed.numUnwatched())
        self.assertEquals(channelInfo.available, feed.numAvailable())
        if isinstance(feed, ChannelFolder):
            self.assertEquals(len(channelInfo.children),
                    len(feed.getChildrenView()))
            for info, child in zip(channelInfo.children,
                    feed.getChildrenView()):
                self.checkChannelInfo(info, child)
        else:
            self.assertEquals(channelInfo.children, None)

    def checkMessageCount(self, expected_count):
        self.assertEquals(len(self.test_handler.messages), expected_count)

    def checkMessage(self, index, message_type, channel):
        message = self.test_handler.messages[index]
        self.assertEquals(type(message), message_type)
        self.checkChannelInfo(message.channel, channel)

    def testAdded(self):
        f = Feed(u'http://example.com/3')
        self.runPendingIdles()
        self.checkMessage(1, messages.ChannelAdded, f)
        # there will actually be a ChannelChanged message afterwards, but we
        # don't need to care about that.

    def testRemoved(self):
        self.feed2.remove()
        self.runPendingIdles()
        self.checkMessageCount(2)
        self.checkMessage(1, messages.ChannelRemoved, self.feed2)

    def testChange(self):
        self.feed1.setTitle(u"Booya")
        self.runPendingIdles()
        self.checkMessageCount(2)
        self.checkMessage(1, messages.ChannelChanged, self.feed1)

    def testReorder(self):
        self.channelTabOrder.handleDNDReorder(self.feed1,
                set([self.feed2.id]))
        self.runPendingIdles()
        self.checkMessageCount(4)
        self.checkMessage(1, messages.ChannelRemoved, self.feed2)
        self.checkMessage(2, messages.ChannelChanged, self.feed_folder)
        self.checkMessage(3, messages.ChannelAdded, self.feed2)

    def testStop(self):
        self.checkMessageCount(1)
        messages.StopTrackingChannels().send_to_backend()
        self.runPendingIdles()
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
        self.runPendingIdles()
        messages.TrackPlaylists().send_to_backend()
        self.runPendingIdles()

    def testInitialList(self):
        self.assertEquals(len(self.test_handler.messages), 1)
        message = self.test_handler.messages[0]
        self.assert_(isinstance(message, messages.PlaylistList))
        self.assertEquals(len(message.playlists), 2)
        self.checkPlaylistInfo(message.playlists[0], self.playlist1)
        self.checkPlaylistInfo(message.playlists[1], self.folder)

    def checkPlaylistInfo(self, playlistInfo, playlist):
        self.assertEquals(playlistInfo.name, playlist.getTitle())
        self.assertEquals(playlistInfo.id, playlist.id)
        if isinstance(playlist, PlaylistFolder):
            self.assertEquals(len(playlistInfo.children),
                    len(playlist.getChildrenView()))
            for info, child in zip(playlistInfo.children,
                    playlist.getChildrenView()):
                self.checkPlaylistInfo(info, child)
        else:
            self.assertEquals(playlistInfo.children, None)

    def checkMessageCount(self, expected_count):
        self.assertEquals(len(self.test_handler.messages), expected_count)

    def checkMessage(self, index, message_type, playlist):
        message = self.test_handler.messages[index]
        self.assertEquals(type(message), message_type)
        self.checkPlaylistInfo(message.playlist, playlist)

    def testAdded(self):
        p = SavedPlaylist(u'http://example.com/3')
        self.runPendingIdles()
        self.checkMessage(1, messages.PlaylistAdded, p)
        # there will actually be a PlaylistChanged message afterwards, but we
        # don't need to care about that.

    def testRemoved(self):
        self.playlist2.remove()
        self.runPendingIdles()
        self.checkMessageCount(2)
        self.checkMessage(1, messages.PlaylistRemoved, self.playlist2)

    def testChange(self):
        self.playlist1.setTitle(u"Booya")
        self.runPendingIdles()
        self.checkMessageCount(2)
        self.checkMessage(1, messages.PlaylistChanged, self.playlist1)

    def testReorder(self):
        self.playlistTabOrder.handleDNDReorder(self.playlist1,
                set([self.playlist2.id]))
        self.runPendingIdles()
        self.checkMessageCount(3)
        self.checkMessage(1, messages.PlaylistRemoved, self.playlist2)
        self.checkMessage(2, messages.PlaylistAdded, self.playlist2)

    def testStop(self):
        self.checkMessageCount(1)
        messages.StopTrackingPlaylists().send_to_backend()
        self.runPendingIdles()
        self.playlist1.setTitle(u"Booya")
        f = Feed(u'http://example.com/3')
        self.playlist2.remove()
        self.checkMessageCount(1)
