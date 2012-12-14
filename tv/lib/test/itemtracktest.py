# Miro - an RSS based video player application
# Copyright (C) 2012
# Participatory Culture Foundation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA
#
# In addition, as a special exception, the copyright holders give
# permission to link the code of portions of this program with the OpenSSL
# library.
#
# You must obey the GNU General Public License in all respects for all of
# the code used other than OpenSSL. If you modify file(s) with this
# exception, you may extend this exception to your version of the file(s),
# but you are not obligated to do so. If you do not wish to do so, delete
# this exception statement from your version. If you delete this exception
# statement from all source files in the program, then also delete it here.

"""itemtracktest -- Test the miro.data.itemtrack module.  """

import datetime
import itertools

from miro import app
from miro import downloader
from miro import eventloop
from miro import messages
from miro import models
from miro import sharing
from miro.data import item
from miro.data import itemtrack
from miro.test import mock
from miro.data import connectionpool
from miro.test.framework import MiroTestCase, MatchAny
from miro.test import testobjects

class ItemTrackTestCase(MiroTestCase):
    """Base classes for all ItemTracker tests.

    This class doesn't define any tests, it simply provides a setUp/tearDown
    methond and some helper functions.
    """

    def setUp(self):
        MiroTestCase.setUp(self)
        self.idle_scheduler = mock.Mock()
        self.init_data_package()
        self.setup_items()
        self.setup_connection_pool()
        self.force_wal_mode()
        self.setup_mock_message_handler()
        self.setup_tracker()
        # make the change tracker start fresh for the unittests.  Since we
        # don't know which change tracker our item type will use, we go for
        # the sledge hammer approach here and reset them all.
        models.Item.change_tracker.reset()
        models.DeviceItem.change_tracker.reset()
        models.SharingItem.change_tracker.reset()

    def tearDown(self):
        self.tracker.destroy()
        MiroTestCase.tearDown(self)

    def force_wal_mode(self):
        """Force WAL mode to be a certain value.

        By default we set wal_mode to be True.  The NonWalMode versions of the
        test case overrides this method and sets wal_mode to False.
        """
        self.connection_pool.wal_mode = True

    def setup_mock_message_handler(self):
        """Install a mock object to handle frontend messages.

        We use this to intercept the ItemChanges message
        """
        self.mock_message_handler = mock.Mock()
        messages.FrontendMessage.install_handler(self.mock_message_handler)
        # move past the the SharingItemChanges method for our initial items.
        eventloop._eventloop.emit('event-finished', True)
        self.mock_message_handler.reset_mock()

    def process_items_changed_messages(self):
        """Simulate the eventloop finishing and sending the ItemChanges
        message to the frontend.  Also, intercept that message and pass it to
        our item tracker.
        """
        eventloop._eventloop.emit('event-finished', True)
        mock_handle = self.mock_message_handler.handle
        # filter through the TabsChanged messages and to find
        # ItemChanges messages.
        for args, kwargs in mock_handle.call_args_list:
            msg = args[0]
            if type(msg) in (messages.ItemChanges,
                             messages.DeviceItemChanges,
                             messages.SharingItemChanges):
                self.tracker.on_item_changes(msg)
        mock_handle.reset_mock()

    def run_tracker_idle(self):
        self.assertEqual(self.idle_scheduler.call_count, 1)
        args, kwargs = self.idle_scheduler.call_args
        self.idle_scheduler.reset_mock()
        callback = args[0]
        callback()

    def run_all_tracker_idles(self):
        loop_check = itertools.count()
        while self.idle_scheduler.call_count > 0:
            if loop_check.next() > 1000:
                raise AssertionError("idle callbacks never stopped")
            self.run_tracker_idle()

    # These next methods need to be implemented by subclasses
    def setup_items(self):
        """Setup the initial database items to track.
        """
        raise NotImplementedError()

    def setup_connection_pool(self):
        """Setup a connection pool to use with our tracker.
        """
        raise NotImplementedError()

    def setup_tracker(self):
        """Setup an item tracker to use."""
        raise NotImplementedError

class ItemTrackTestWALMode(ItemTrackTestCase):
    def setUp(self):
        ItemTrackTestCase.setUp(self)
        # setup mock objects to track when the items-changed and list-changed
        # signals get emitted
        self.signal_handlers = {}
        for signal in ("items-changed", "list-changed"):
            self.signal_handlers[signal] = mock.Mock()
            self.tracker.connect(signal, self.signal_handlers[signal])

    def setup_items(self):
        self.tracked_feed, self.tracked_items = \
                testobjects.make_feed_with_items(10)
        self.other_feed1, self.other_items1 = \
                testobjects.make_feed_with_items(12)
        self.other_feed2, self.other_items2 = \
                testobjects.make_feed_with_items(8)
        app.db.finish_transaction()

    def setup_connection_pool(self):
        self.connection_pool = app.connection_pools.get_main_pool()

    def setup_tracker(self):
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.tracked_feed.id)
        query.set_order_by(['release_date'])
        self.tracker = itemtrack.ItemTracker(self.idle_scheduler, query,
                                             item.ItemSource())

    def check_no_signals(self):
        """Check that our ItemTracker hasn't emitted any signals."""
        for handler in self.signal_handlers.values():
            self.assertEquals(handler.call_count, 0)

    def check_one_signal(self, should_have_fired):
        """Check that our ItemTracker has emitted a specific signal and no
        others.

        Reset the Mock object that handled the signal.

        :returns: argumunts passed to that signal
        """
        if should_have_fired not in self.signal_handlers.keys():
            raise ValueError("Unknown signal: %s", should_have_fired)
        for signal, handler in self.signal_handlers.items():
            if signal == should_have_fired:
                self.assertEquals(handler.call_count, 1)
                args = handler.call_args[0]
                handler.reset_mock()
            else:
                self.assertEquals(handler.call_count, 0)

        # do some sanity checks on the arguments passed
        # first argument should always be our tracker
        self.assertEquals(args[0], self.tracker)
        if should_have_fired in ('initial-list', 'items-changed'):
            # should be passed a list of ids
            self.assertEquals(len(args), 2)
        else:
            # shouldn't be passed anything
            self.assertEquals(len(args), 1)
        return args

    def check_tracker_items(self, correct_items=None):
        """Calculate which items should be in our ItemTracker and check if
        it's data agrees with this.

        :param correct_items: items that should be in our ItemTracker.  If
        None, we will use calc_items_in_tracker() to calculate this.
        """
        if correct_items is not None:
            item_list = correct_items
        else:
            item_list = self.calc_items_in_tracker()
        self.sort_item_list(item_list)
        self.assertEquals(len(item_list), len(self.tracker))
        # test the get_items() method
        tracker_items = self.tracker.get_items()
        self.assertEquals(len(tracker_items), len(item_list))
        for i, ti in zip(item_list, tracker_items):
            self.assertEquals(i.id, ti.id)
        # test the get_row() and get_item() methods
        for i, item in enumerate(item_list):
            self.assertEquals(self.tracker.get_row(i).id, item.id)
            self.assertEquals(self.tracker.get_item(item.id).id, item.id)

    def calc_items_in_tracker(self):
        item_list = []
        for i in models.Item.make_view():
            meets_conditions = True
            for condition in self.tracker.query.conditions:
                if len(condition.columns) > 1:
                    raise AssertionError("Don't know how to get value for %s"
                                         % condition.columns)
                table, column = condition.columns[0]
                if table == 'item':
                    item_value = getattr(i, column)
                elif table == 'remote_downloader':
                    dler = i.downloader
                    if dler is None:
                        item_value = None
                    else:
                        item_value = getattr(dler, column)
                elif table == 'feed':
                    item_value = getattr(i.get_feed(), column)
                else:
                    raise AssertionError("Don't know how to get value for %s"
                                         % condition.columns)
                full_column = "%s.%s" % (table, column)
                if condition.sql == '%s = ?' % full_column:
                    if item_value != condition.values[0]:
                        meets_conditions = False
                        break
                elif condition.sql == '%s < ?' % full_column:
                    if item_value >= condition.values[0]:
                        meets_conditions = False
                        break
                elif condition.sql == '<':
                    if item_value <= condition.values[0]:
                        meets_conditions = False
                        break
                elif condition.sql == '%s LIKE ?' % full_column:
                    value = condition.values[0]
                    if (value[0] != '%' or
                        value[-1] != '%'):
                        raise ValueError("Can't handle like without % on "
                                         "both ends")
                    inner_part = value[1:-1]
                    meets_conditions = inner_part in item_value
                    break
                else:
                    raise ValueError("Can't handle condition operator: %s" %
                                     condition.operater)
            if meets_conditions:
                item_list.append(i)
        return item_list

    def sort_item_list(self, item_list):
        def cmp_func(item1, item2):
            for ob in self.tracker.query.order_by:
                value1 = getattr(item1, ob.column)
                value2 = getattr(item2, ob.column)
                cmp_val = cmp(value1, value2)
                if ob.descending:
                    cmp_val *= -1
                if cmp_val != 0:
                    return cmp_val
            return 0
        item_list.sort(cmp=cmp_func)

    def test_initial_list(self):
        self.check_tracker_items()

    def test_background_fetch(self):
        # test that ItemTracker fetches its rows in the backend using
        # idle callbacks

        # initially we should just store None for our data as a placeholder
        # until we actually do the fetch.
        self.assertEquals(self.tracker.row_data, {})
        # we should have an idle callback to schedule fetching the row data.
        self.assertEqual(self.idle_scheduler.call_count, 1)
        self.run_all_tracker_idles()
        for row in self.tracker.row_data:
            self.assertNotEquals(row, None)
        self.check_tracker_items()

    def check_items_changed_after_message(self, changed_items):
        self.process_items_changed_messages()
        signal_args = self.check_one_signal('items-changed')
        self.assertSameSet([i.id for i in changed_items],
                           signal_args[1])

    def check_list_change_after_message(self):
        self.process_items_changed_messages()
        self.check_one_signal('list-changed')

    def test_item_changes(self):
        # test that simple changes result in a items-changed signal
        item1 = self.tracked_items[0]
        item2 = self.tracked_items[1]
        item1.title = u'new title'
        item1.signal_change()
        item2.title = u'new title2'
        item2.signal_change()
        self.check_items_changed_after_message([item1, item2])
        self.check_tracker_items()
        # test that changes to order by fields result in a list-changed
        item1.release_date += datetime.timedelta(days=400)
        item1.signal_change()
        item2.release_date += datetime.timedelta(days=400)
        item2.signal_change()
        self.check_list_change_after_message()
        self.check_tracker_items()
        # test that changes to conditions result in a list-changed
        item1.feed_id = self.other_feed2.id
        item1.signal_change()
        item2.feed_id = self.tracked_feed.id
        item2.signal_change()
        self.check_list_change_after_message()
        self.check_tracker_items()

    def test_item_changes_after_finished(self):
        # test item changes after we've finished fetching all rows
        while not self.tracker.idle_work_scheduled:
            self.tracker.do_idle_work()
        item1 = self.tracked_items[0]
        item2 = self.tracked_items[1]
        item1.title = u'new title'
        item1.signal_change()
        item2.title = u'new title2'
        item2.signal_change()
        self.check_items_changed_after_message([item1, item2])
        self.check_tracker_items()

    def test_add_remove(self):
        # adding items to our tracked feed should result in the list-changed
        # signal
        new_item = testobjects.make_item(self.tracked_feed, u'new-item')
        self.check_list_change_after_message()
        self.check_tracker_items()
        # removed items to our tracked feed should result in the list-changed
        # signal
        to_remove = self.tracked_items.pop(0)
        to_remove.remove()
        self.check_list_change_after_message()
        self.check_tracker_items()
        # adding/remove items from other feeds shouldn't result in any signals
        self.other_items1[0].remove()
        testobjects.make_item(self.other_feed2, u'new-item2')
        self.check_no_signals()
        self.check_tracker_items()

    def test_extra_conditions(self):
        # test adding more conditions
        titles = [i.title for i in self.tracked_items]
        titles.sort()
        middle_title = titles[len(titles) // 2]
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.tracked_feed.id)
        query.add_condition('title', '<', middle_title)
        query.set_order_by(['release_date'])
        self.tracker.change_query(query)
        # changing the query should emit list-changed
        self.check_one_signal('list-changed')
        self.check_tracker_items()

    def test_complex_conditions(self):
        # test adding more conditions
        query = itemtrack.ItemTrackerQuery()

        sql = "feed_id IN (SELECT id FROM feed WHERE id in (?, ?))"
        values = (self.tracked_feed.id, self.other_feed1.id)
        query.add_complex_condition(["feed_id"], sql, values)
        query.set_order_by(['release_date'])
        self.tracker.change_query(query)
        # changing the query should emit list-changed
        self.check_one_signal('list-changed')
        self.check_tracker_items(self.tracked_items + self.other_items1)

    def test_like(self):
        # test adding more conditions
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('title', 'LIKE', '%feed1%')
        self.tracker.change_query(query)
        # changing the query should emit list-changed
        self.check_one_signal('list-changed')
        self.check_tracker_items()

    def test_search(self):
        # test full-text search

        # manually set some titles so that we can test searching those
        item1, item2, item3 = self.tracked_items[:3]
        item1.title = u'foo bar'
        item1.signal_change()
        item2.title = u'bar baz'
        item2.signal_change()
        item3.title = u'foo bar baz'
        item3.signal_change()
        app.db.finish_transaction()
        self.check_items_changed_after_message([item1, item2, item3])
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.tracked_feed.id)
        query.set_search('foo')
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items([item1, item3])
        # test two terms
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.tracked_feed.id)
        query.set_search('foo baz')
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items([item3])
        # test that we do a prefix search for the last term
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.tracked_feed.id)
        query.set_search('fo')
        query.set_order_by(['release_date'])
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items([item1, item3])
        # But we should'nt do a prefix search for terms other than the last
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.tracked_feed.id)
        query.set_search('fo bar')
        query.set_order_by(['release_date'])
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items([])

    def test_search_for_torrent(self):
        # test searching for the string "torrent" in this case, we should 
        # match items that are torrents.

        item1 = self.tracked_items[0]
        # item1 will be a torrent download
        item1.download()
        downloader.RemoteDownloader.update_status({
            'current_size': 0,
            'total_size': None,
            'state': u'downloading',
            'rate': 0,
            'eta': None,
            'type': 'BitTorrent',
            'dlid': item1.downloader.dlid,
        })
        app.db.finish_transaction()
        self.check_items_changed_after_message([item1])
        # a search for torrent should match both of them
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.tracked_feed.id)
        query.set_search('torrent')
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items([item1])

    def test_feed_conditions(self):
        # change the query to something that involves downloader columns
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed.orig_url', '=', self.tracked_feed.orig_url)
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items()

    def test_downloader_conditions(self):
        # change the query to something that involves downloader columns
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('remote_downloader.state', '=', 'downloading')
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        # start downloading some items
        downloads = self.tracked_items[:4]
        for i in downloads:
            i.download()
        self.check_list_change_after_message()
        self.check_tracker_items()
        for i in downloads[2:]:
            i.expire()
        self.check_list_change_after_message()
        self.check_tracker_items()

    def test_playlist_conditions(self):
        # change the query to something that involves playlist columns
        playlist = models.SavedPlaylist(u'My playlist')
        for item in self.tracked_items:
            playlist.add_item(item)
        app.db.finish_transaction()
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('playlist_item_map.playlist_id', '=',
                            playlist.id)
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items(self.tracked_items)
        # add items to the playlist
        new_items = self.other_items1[:4]
        for item in new_items:
            playlist.add_item(item)
        self.check_list_change_after_message()
        self.check_tracker_items(self.tracked_items + new_items)
        # remove items from the playlist
        removed_items = self.tracked_items[:4]
        for item in removed_items:
            playlist.remove_item(item)
        self.check_list_change_after_message()
        self.check_tracker_items(self.tracked_items[4:] + new_items)

    def test_order(self):
        # test order by a different column
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.tracked_feed.id)
        query.set_order_by(['title'])
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items()
        # test reverse ordering
        query.set_order_by(['-title'])
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items()
        # test order by multiple column
        query.set_order_by(['title', '-release_date'])
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items()

    def test_limit(self):
        # test order by a different column
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.tracked_feed.id)
        query.set_order_by(['title'])
        query.set_limit(3)
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        sorted_items = sorted(self.tracked_items,
                              key=lambda item: item.title)
        self.check_tracker_items(sorted_items[:3])
        # test changes
        last_item = sorted_items[-1]
        last_item.title = u'aaaaaa'
        last_item.signal_change()
        self.check_list_change_after_message()
        self.check_tracker_items([last_item] + sorted_items[:2])

    def test_downloader_order(self):
        downloads = self.tracked_items[:4]
        for i, item_ in enumerate(downloads):
            # simulate a the download being in progress
            item_.download()
            # ensure that the downloads goes from slowest to fastest
            rate = i * 1024
            fake_status = {
                'current_size': 0,
                'total_size': None,
                'state': u'downloading',
                'rate': rate,
                'eta': None,
                'type': 'HTTP',
                'dlid': item_.downloader.dlid,
            }
            downloader.RemoteDownloader.update_status(fake_status)

        app.db.finish_transaction()
        self.check_items_changed_after_message(downloads)
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('remote_downloader.state', '=', 'downloading')
        query.set_order_by(['remote_downloader.rate'])
        self.tracker.change_query(query)
        # Need to manually fetch the items to compare to
        with self.connection_pool.context() as connection:
            id_list = [i.id for i in downloads]
            correct_items = item.fetch_item_infos(connection, id_list)
        self.check_tracker_items(correct_items)

    def test_change_while_loading_data(self):
        # test the backend writing to the DB before all data is loaded.
        item1 = self.tracked_items[0]
        item2 = self.tracked_items[1]
        old_title = item1.title
        item1.title = u'new title'
        item1.signal_change()
        # since these changes happened after our ItemTracker fetched its IDs,
        # when we load data from our ItemTracker it should have the old data
        self.assertEquals(self.tracker.get_item(item1.id).title,
                          old_title)
        item2.feed_id = self.other_feed1.id
        item2.signal_change()
        # For the same reason as above, item2 should still be in the tracker
        # and the next line should not throw an exception
        self.tracker.get_item(item2.id)
        # After ItemTracker gets the ItemChanges message, it should load the
        # new data
        self.process_items_changed_messages()
        self.assertEquals(self.tracker.get_item(item1.id).title,
                          u'new title')
        self.assertRaises(KeyError, self.tracker.get_item, item2.id)

class ItemTrackTestNonWALMode(ItemTrackTestWALMode):
    def force_wal_mode(self):
        self.connection_pool.wal_mode = False

class DeviceItemTrackTestWALMode(ItemTrackTestCase):
    def setup_items(self):
        self.device = testobjects.make_mock_device()
        device_items = testobjects.make_device_items(self.device, 'audio1.mp3',
                                                     'audio2.mp3', 'video1.avi')
        self.audio1, self.audio2, self.video1 = device_items
        self.device.db_info.db.finish_transaction()

    def setup_connection_pool(self):
        # simulate the device tab being sent to the frontend so that
        # app.connection_pools has a ConnectionPool for the device
        msg = messages.TabsChanged('connect', [self.device], [], [])
        app.connection_pools.on_tabs_changed(msg)
        self.connection_pool = app.connection_pools.get_device_pool(
            self.device.id)

    def setup_tracker(self):
        query = itemtrack.DeviceItemTrackerQuery()
        query.add_condition('file_type', '=', u'audio')
        query.set_order_by(['filename'])
        item_source = item.DeviceItemSource(self.device)
        self.tracker = itemtrack.ItemTracker(self.idle_scheduler, query,
                                             item_source)

    def check_list(self, *correct_items):
        tracker_items = self.tracker.get_items()
        self.assertEquals([i.id for i in tracker_items],
                          [i.id for i in correct_items])

    def test_list(self):
        self.check_list(self.audio1, self.audio2)

    def test_changes(self):
        self.audio2.update_from_metadata({u'file_type': u'video'})
        self.audio2.signal_change()
        self.video1.update_from_metadata({u'file_type': u'audio'})
        self.video1.signal_change()
        self.process_items_changed_messages()
        self.check_list(self.audio1, self.video1)

class DeviceItemTrackTestNoWALMode(DeviceItemTrackTestWALMode):
    def force_wal_mode(self):
        self.connection_pool.wal_mode = False

class SharingItemTrackTestWalMode(ItemTrackTestCase):
    def setup_items(self):
        self.setup_client()
        self.setup_share()

    def setup_share(self):
        # make a share and that uses our mock client
        self.patch_function('miro.libdaap.make_daap_client',
                            lambda *args, **kwargs: self.client)
        # Make sure the SharingItemTrackerImpl doesn't actually create a
        # thread.  We want to manually call its methods and have them run in
        # the in the main thread.
        self.patch_for_test('miro.sharing.SharingItemTrackerImpl.start_thread')
        self.share = testobjects.make_share()
        self.share_info = messages.SharingInfo(self.share)
        self.share.set_info(self.share_info)
        self.share.start_tracking()
        self.run_client_connect()

    def setup_connection_pool(self):
        msg = messages.TabsChanged('connect', [self.share_info], [], [])
        app.connection_pools.on_tabs_changed(msg)
        self.connection_pool = app.connection_pools.get_sharing_pool(
            self.share.info.id)
        self.setup_tracker()

    def setup_client(self):
        self.client = testobjects.MockDAAPClient()
        self.video1 = testobjects.make_mock_daap_item(1001, 'video-item-1',
                                                      u'video')
        self.video2 = testobjects.make_mock_daap_item(1002, 'video-item-2',
                                                      u'video')
        self.audio1 = testobjects.make_mock_daap_item(2001, 'audio-item-1',
                                                      u'audio')
        self.audio2 = testobjects.make_mock_daap_item(2002, 'audio-item-2',
                                                      u'audio')
        self.client.set_items([self.video1, self.video2,
                               self.audio1, self.audio2])

    def setup_tracker(self):
        # Set up our item tracker
        query = itemtrack.SharingItemTrackerQuery()
        query.add_condition('file_type', '=', u'audio')
        query.set_order_by(['title'])
        item_source = item.SharingItemSource(self.share.info)
        self.tracker = itemtrack.ItemTracker(self.idle_scheduler, query,
                                             item_source)

    def setup_mock_message_handler(self):
        """Install a mock object to handle frontend messages.

        We use this to intercept the SharingItemChanges message
        """
        self.mock_message_handler = mock.Mock()
        messages.FrontendMessage.install_handler(self.mock_message_handler)
        # move past the the SharingItemChanges method for our initial items.
        eventloop._eventloop.emit('event-finished', True)
        self.mock_message_handler.reset_mock()

    def run_client_connect(self):
        result = self.share.tracker.client_connect()
        self.share.tracker.client_connect_callback(result)
        self.share.db_info.db.finish_transaction()

    def run_client_update(self):
        result = self.share.tracker.client_update()
        self.share.tracker.client_update_callback(result)
        self.share.db_info.db.finish_transaction()

    def check_list(self, *correct_items):
        tracker_items = self.tracker.get_items()
        correct_ids = [i['dmap.itemid'] for i in correct_items]
        self.assertEquals([i.daap_id for i in tracker_items], correct_ids)

    def test_list(self):
        self.check_list(self.audio1, self.audio2)

    def test_changes(self):
        new_video1 = self.video1.copy()
        new_video1 = testobjects.make_mock_daap_item(1001, 'video-item-1',
                                                     u'audio')
        audio3 = testobjects.make_mock_daap_item(2003, 'audio-item-3',
                                                 u'audio')
        self.client.set_items([new_video1, self.video2,
                               self.audio1, self.audio2, audio3])
        self.run_client_update()
        self.process_items_changed_messages()
        self.check_list(self.audio1, self.audio2, audio3, new_video1)

    def test_playlist_filter(self):
        self.client.add_playlist(
            testobjects.make_mock_daap_playlist(3001, 'playlist')
        )
        self.client.set_playlist_items(3001, [1001, 1002])
        self.run_client_update()
        query = itemtrack.SharingItemTrackerQuery()
        query.add_condition('sharing_item_playlist_map.playlist_id', '=',
                            3001)
        query.set_order_by(['title'])
        self.tracker.change_query(query)
        self.check_list(self.video1, self.video2)
        # test changes
        self.client.set_playlist_items(3001, [1001, 1002, 2001])
        self.run_client_update()
        self.process_items_changed_messages()
        self.check_list(self.audio1, self.video1, self.video2)

class SharingItemTrackTestNOWalMode(SharingItemTrackTestWalMode):
    def force_wal_mode(self):
        self.connection_pool.wal_mode = False

class ItemInfoAttributeTest(MiroTestCase):
    # Test that DeviceItemInfo and SharingItemInfo to make sure that they
    # define the same attributes that ItemInfo does

    def test_device_item_info(self):
        self._check_class_against_item_info(item.DeviceItemInfo)

    def test_sharing_item_info(self):
        self._check_class_against_item_info(item.SharingItemInfo)

    def _check_class_against_item_info(self, klass):
        required_attrs = self._calc_required_attrs()
        # make sure the other class either has a SelectColumn or a class
        # property for each of the required SelectColumns
        klass_attrs = self._select_column_attrs(klass)
        klass_attrs.update(self._class_properties(klass))
        # special case, if ItemInfo only uses filename_unicode, to implement
        # the filename_property().  So if the class defines filename(), then
        # it doesn't need to define filename_unicode
        if 'filename' in klass_attrs:
            required_attrs.remove('filename_unicode')

        if not required_attrs.issubset(klass_attrs):
            msg = ("%s does not define required attributes: (%s)" %
                   (klass, required_attrs.difference(klass_attrs)))
            raise AssertionError(msg)

    def _select_column_attrs(self, klass):
        return set([col.attr_name for col in klass.select_info.select_columns])

    def _class_properties(self, klass):
        return set(name for name, obj in klass.__dict__.items()
                   if isinstance(obj, property))

    def _calc_required_attrs(self):
        item_attrs = self._select_column_attrs(item.ItemInfo)
        # remove default values defined in ItemInfoBase
        required_attrs = item_attrs.difference(
            item.ItemInfoBase.__dict__.keys())
        return required_attrs

    def test_db_error_item_attributes(self):
        # test that DBErrorItemInfo defines 
        required_attrs = self._calc_required_attrs()
        missing_attributes = set()
        db_error_item_info = item.DBErrorItemInfo(0)
        for attr_name in required_attrs:
            if not hasattr(db_error_item_info, attr_name):
                missing_attributes.add(attr_name)
        if missing_attributes:
            msg = ("DBErrorItemInfo does not define required "
                   "attributes: (%s)" % missing_attributes)
            raise AssertionError(msg)

class BackendItemTrackerTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.setup_data()
        self.setup_tracker()

    def tearDown(self):
        self.item_tracker.destroy()
        MiroTestCase.tearDown(self)

    def setup_data(self):
        self.feed, self.items = \
                testobjects.make_feed_with_items(10, file_items=True)
        self.other_feed, self.other_items = \
                testobjects.make_feed_with_items(10, file_items=True)
        self.process_item_changes()

    def setup_tracker(self):
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.feed.id)
        self.item_tracker = itemtrack.BackendItemTracker(query)
        self.items_changed_callback = mock.Mock()
        self.item_tracker.connect('items-changed', self.items_changed_callback)

    def fetch_item_infos(self, item_objects):
        if len(item_objects) == 0:
            return []
        return item.fetch_item_infos(app.db.connection,
                                     [i.id for i in item_objects])

    def test_initial_list(self):
        self.assertSameSet(self.item_tracker.get_items(),
                           self.fetch_item_infos(self.items))

    def check_callback(self, added, changed, removed):
        self.assertEquals(self.items_changed_callback.call_count, 1)
        call_args, call_kwargs = self.items_changed_callback.call_args
        self.assertEquals(call_args[0], self.item_tracker)
        self.assertSameSet(call_args[1], self.fetch_item_infos(added))
        self.assertSameSet(call_args[2], self.fetch_item_infos(changed))
        self.assertSameSet(call_args[3], [item.id for item in removed])
        self.assertEquals(call_kwargs, {})
        self.items_changed_callback.reset_mock()

    def process_item_changes(self):
        app.db.finish_transaction()
        models.Item.change_tracker.send_changes()

    def test_changes(self):
        self.assertEquals(self.items_changed_callback.call_count, 0)
        # make changes that don't add/remove items from the list
        self.items[0].set_user_metadata({'title': u'new title'})
        self.items[0].signal_change()
        self.items[1].set_user_metadata({'title': u'new title'})
        self.items[1].signal_change()
        self.process_item_changes()
        self.check_callback(added=[], changed=self.items[:2], removed=[])
        # make changes that add/remove items from the list.
        self.items[0].remove()
        new_items = testobjects.add_items_to_feed(self.feed, 5,
                                                  file_items=True)
        self.items[1].set_user_metadata({'title': u'newer title'})
        self.items[1].signal_change()
        self.other_items[0].set_feed(self.feed.id)
        self.process_item_changes()
        self.check_callback(added=new_items + [self.other_items[0]],
                            changed=[self.items[1]],
                            removed=[self.items[0]])

    def test_change_query(self):
        new_query = itemtrack.ItemTrackerQuery()
        new_query.add_condition('feed_id', '=', self.other_feed.id)
        self.item_tracker.change_query(new_query)
        self.assertSameSet(self.item_tracker.get_items(),
                           self.fetch_item_infos(self.other_items))
        # check that changing the query resulted in the items-changed signal
        self.process_item_changes()
        self.check_callback(added=self.other_items,
                            changed=[],
                            removed=self.items)

    def test_destroy(self):
        # test that after destroy() is called, we no longer track changes
        self.item_tracker.destroy()
        self.items[0].set_user_metadata({'title': u'new title'})
        self.items[0].signal_change()
        self.process_item_changes()
        self.assertEquals(self.items_changed_callback.call_count, 0)
