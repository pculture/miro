from miro.frontends.widgets import playback
from miro import signals
from miro.test import mock
from miro.test.framework import MiroTestCase

class MockItemList(signals.SignalEmitter):
    def __init__(self, items):
        signals.SignalEmitter.__init__(self, 'items-changed', 'list-changed')
        self.items = items

    def _get_child_mock(self, **kwargs):
        return mock.Mock(**kwargs)

    def __len__(self):
        return len(self.items)

    def get_first_item(self):
        return self.items[0]

    def get_item(self, id):
        return self.items[self.get_index(id)]

    def item_in_list(self, id):
        for item in self.items:
            if item.id == id:
                return True
        return False

    def get_index(self, id):
        for i, item in enumerate(self.items):
            if item.id == id:
                return i
        raise KeyError(id)

    def get_row(self, index):
        return self.items[index]

    def get_playable_ids(self):
        return [item.id for item in self.items if item.is_playable]

class PlaybackPlaylistTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.mock_item_list_pool = self.patch_for_test(
            'miro.app.item_list_pool')
        self.items = [
            mock.Mock(id=0, title='one', is_playable=True),
            mock.Mock(id=1, title='two', is_playable=True),
            mock.Mock(id=2, title='three', is_playable=False),
            mock.Mock(id=3, title='four', is_playable=True),
        ]
        self.item_list = MockItemList(self.items)

    def check_currently_playing(self, playlist, correct_index):
        if playlist.currently_playing != self.items[correct_index]:
            raise AssertionError("Item %s != Item %s" %
                                 (playlist.currently_playing.title,
                                  self.items[correct_index].title))

    def test_normal(self):
        playlist = playback.PlaybackPlaylist(self.item_list, 1, False, False)
        self.check_currently_playing(playlist, 1)
        playlist.select_next_item()
        self.check_currently_playing(playlist, 3)
        playlist.select_next_item()
        self.assertEquals(playlist.currently_playing, None)

    def test_repeat(self):
        playlist = playback.PlaybackPlaylist(self.item_list, 1, False, True)
        self.check_currently_playing(playlist, 1)
        playlist.select_next_item()
        self.check_currently_playing(playlist, 3)
        playlist.select_next_item()
        # after the end of the list, we should wrap around and continue
        # playing
        self.check_currently_playing(playlist, 0)
        playlist.select_next_item()
        self.check_currently_playing(playlist, 1)

    def test_shuffle(self):
        mock_choice = self.patch_for_test('random.choice')
        playlist = playback.PlaybackPlaylist(self.item_list, 1, True, False)
        # playback starts on the first item
        self.check_currently_playing(playlist, 1)
        # the next item should use random.choice.  We should pick between the
        # 2 remaining playable items
        mock_choice.return_value = 3
        playlist.select_next_item()
        self.assertEquals(mock_choice.call_args[0][0], [0, 3])
        self.check_currently_playing(playlist, 3)
        # the next item should use random.choice() with the last playable item
        mock_choice.return_value = 0
        playlist.select_next_item()
        self.assertEquals(mock_choice.call_args[0][0], [0])
        self.check_currently_playing(playlist, 0)
        # the next time, we should stop playback without calling choice()
        mock_choice.reset_mock()
        playlist.select_next_item()
        self.assertEquals(playlist.currently_playing, None)
        self.assertEquals(mock_choice.call_count, 0)

    def test_shuffle_repeat(self):
        mock_choice = self.patch_for_test('random.choice')
        playlist = playback.PlaybackPlaylist(self.item_list, 1, True, True)
        # playback starts on the first item
        self.check_currently_playing(playlist, 1)
        # the next item should use random.choice.  We should pick between the
        # 3 playable items in the list
        mock_choice.return_value = 3
        playlist.select_next_item()
        self.assertEquals(mock_choice.call_args[0][0], [0, 1, 3])
        self.check_currently_playing(playlist, 3)
        # the next item should do the same
        mock_choice.return_value = 0
        playlist.select_next_item()
        self.assertEquals(mock_choice.call_args[0][0], [0, 1, 3])
        self.check_currently_playing(playlist, 0)

    def test_forward_back(self):
        playlist = playback.PlaybackPlaylist(self.item_list, 0, False, False)
        self.check_currently_playing(playlist, 0)
        playlist.select_next_item()
        self.check_currently_playing(playlist, 1)
        playlist.select_previous_item()
        self.check_currently_playing(playlist, 0)
        playlist.select_next_item()
        self.check_currently_playing(playlist, 1)

    def test_shuffle_forward_back(self):
        mock_choice = self.patch_for_test('random.choice')
        playlist = playback.PlaybackPlaylist(self.item_list, 1, True, True)
        # playback starts on the first item
        self.check_currently_playing(playlist, 1)
        # the next item should use random.choice.  We should pick between the
        # 2 remaining playable items
        mock_choice.return_value = 3
        playlist.select_next_item()
        self.assertEquals(mock_choice.call_args[0][0], [0, 1, 3])
        self.check_currently_playing(playlist, 3)
        # going back should return us to the item #1, without calling choice()
        mock_choice.reset_mock()
        playlist.select_previous_item()
        self.assertEquals(mock_choice.call_count, 0)
        self.check_currently_playing(playlist, 1)
        # going forward should return us to item #3, again without calling
        # choice()
        playlist.select_next_item()
        self.assertEquals(mock_choice.call_count, 0)
        self.check_currently_playing(playlist, 3)
        # going forward again should return to the normal shuffle logic
        mock_choice.return_value = 0
        playlist.select_next_item()
        self.assertEquals(mock_choice.call_args[0][0], [0, 1, 3])
        self.check_currently_playing(playlist, 0)

    def test_item_change(self):
        playlist = playback.PlaybackPlaylist(self.item_list, 0, False, False)
        mock_handler = mock.Mock()
        playlist.connect("playing-info-changed", mock_handler)
        self.check_currently_playing(playlist, 0)
        # simulate an item changing titles
        new_item = mock.Mock(id=0, title='New item one', is_playable=True)
        self.item_list.items[0] = new_item
        self.item_list.emit('items-changed', set([new_item.id]))
        self.assertEquals(mock_handler.call_count, 1)
        self.assertEquals(playlist.currently_playing, new_item)
        # simulate an item that's not playing changing
        mock_handler.reset_mock()
        new_item2 = mock.Mock(id=2, title='New item three', is_playable=True)
        self.item_list.items[2] = new_item2
        self.item_list.emit('items-changed', set([new_item2.id]))
        self.assertEquals(mock_handler.call_count, 0)
        # simulate an item changing to not playable
        new_item3 = mock.Mock(id=0, title='New item one', is_playable=False)
        self.item_list.items[0] = new_item3
        self.item_list.emit('items-changed', set([new_item3.id]))
        self.assertEquals(mock_handler.call_count, 1)
        self.assertEquals(playlist.currently_playing, None)

    def test_delete(self):
        playlist = playback.PlaybackPlaylist(self.item_list, 0, False, False)
        mock_handler = mock.Mock()
        playlist.connect("playing-info-changed", mock_handler)
        self.check_currently_playing(playlist, 0)
        # simulate an item getting deleted
        del self.item_list.items[0]
        self.item_list.emit('list-changed')
        self.assertEquals(mock_handler.call_count, 1)
        self.assertEquals(playlist.currently_playing, None)

    def test_empty_item_list(self):
        empty_list = MockItemList([])
        playlist = playback.PlaybackPlaylist(empty_list, 0, False, False)
        self.assertEquals(playlist.currently_playing, None)

    def test_add_ref_and_release(self):
        self.assertEquals(self.mock_item_list_pool.add_ref.call_count, 0)
        self.assertEquals(self.mock_item_list_pool.release.call_count, 0)
        playlist = playback.PlaybackPlaylist(self.item_list, 0, False, False)
        self.assertEquals(self.mock_item_list_pool.add_ref.call_count, 1)
        self.assertEquals(self.mock_item_list_pool.release.call_count, 0)
        playlist.finished()
        self.assertEquals(self.mock_item_list_pool.add_ref.call_count, 1)
        self.assertEquals(self.mock_item_list_pool.release.call_count, 1)
