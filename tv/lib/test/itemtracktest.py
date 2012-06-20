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
from miro import item
from miro import messages
from miro import models
from miro.data.item import ItemFetcher
from miro.data import itemtrack
from miro.test import mock
from miro.test.framework import MiroTestCase, MatchAny

class ItemTrackTest(MiroTestCase):
    def setUp(self):
        MiroTestCase.setUp(self)
        self.init_data_package()
        self.feed_counter = itertools.count()
        self.tracked_feed, self.tracked_items = self.make_feed_with_items(10)
        self.other_feed1, self.other_items1 = self.make_feed_with_items(12)
        self.other_feed2, self.other_items2 = self.make_feed_with_items(8)
        app.db.finish_transaction()
        self.mock_idle_scheduler = mock.Mock()
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.tracked_feed.id)
        query.set_order_by('release_date')
        self.tracker = itemtrack.ItemTracker(self.mock_idle_scheduler, query)
        self.signal_handlers = {}
        for signal in ("items-changed", "list-changed"):
            self.signal_handlers[signal] = mock.Mock()
            self.tracker.connect(signal, self.signal_handlers[signal])
        self.mock_message_handler = mock.Mock()
        messages.FrontendMessage.install_handler(self.mock_message_handler)
        # reset item chages that occured from setUp()
        item.Item.change_tracker.reset()

    def check_no_idles_scheduled(self):
        self.assertEqual(self.mock_idle_scheduler.call_count, 0)

    def run_tracker_idle(self):
        self.assertEqual(self.mock_idle_scheduler.call_count, 1)
        args, kwargs = self.mock_idle_scheduler.call_args
        self.mock_idle_scheduler.reset_mock()
        callback = args[0]
        callback()

    def run_all_tracker_idles(self):
        loop_check = itertools.count()
        while self.mock_idle_scheduler.call_count > 0:
            if loop_check.next() > 1000:
                raise AssertionError("idle callbacks never stopped")
            self.run_tracker_idle()

    def make_feed_with_items(self, item_count):
        feed_count = self.feed_counter.next()
        url = u'http://feed%d.com/feed.rss' % feed_count
        feed = models.Feed(url)
        items = []
        for i in xrange(item_count):
            name = u"feed%d-item%d" % (feed_count, i)
            items.append(self.make_item(feed, name))
        return feed, items

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
        for i in item.Item.make_view():
            meets_conditions = True
            for condition in self.tracker.query.conditions:
                if condition.table == 'item':
                    item_value = getattr(i, condition.column)
                elif condition.table == 'remote_downloader':
                    dler = i.downloader
                    if dler is None:
                        item_value = None
                    else:
                        item_value = getattr(dler, condition.column)
                elif condition.table == 'feed':
                    item_value = getattr(i.get_feed(), condition.column)
                else:
                    raise AssertionError("Don't know how to get value for %s"
                                         % condition.table)
                full_column = "%s.%s" % (condition.table, condition.column)
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
        self.assertEqual(self.mock_idle_scheduler.call_count, 1)
        self.run_all_tracker_idles()
        for row in self.tracker.row_data:
            self.assertNotEquals(row, None)
        self.check_tracker_items()

    def process_items_changed_message(self):
        """Simulate the eventloop finished and sending the ItemChanges
        message.

        Also, intercept that message and pass it to our item tracker
        """
        eventloop._eventloop.emit('event-finished', True)
        mock_handle = self.mock_message_handler.handle
        self.assertEquals(mock_handle.call_count, 1)
        message = mock_handle.call_args[0][0]
        self.assertEquals(type(message), messages.ItemChanges)
        self.tracker.on_item_changes(message)
        mock_handle.reset_mock()

    def check_items_changed_after_message(self, changed_items):
        self.process_items_changed_message()
        signal_args = self.check_one_signal('items-changed')
        self.assertSameSet([i.id for i in changed_items],
                           signal_args[1])

    def check_list_change_after_message(self):
        self.process_items_changed_message()
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

    def test_item_changes_after_connection_finished(self):
        # test that if we fetch an item, then it changes, we re-fetch it.
        while self.tracker.connection is not None:
            self.tracker.fetch_rows_during_idle()
        # at this point, our ItemTracker has fetched all its data, and it's
        # released its connection.
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
        new_item = self.make_item(self.tracked_feed, u'new-item')
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
        self.make_item(self.other_feed2, u'new-item2')
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
        query.set_order_by('release_date')
        self.tracker.change_query(query)
        # changing the query should emit list-changed
        self.check_one_signal('list-changed')
        self.check_tracker_items()

    def test_complex_conditions(self):
        # test adding more conditions
        query = itemtrack.ItemTrackerQuery()

        sql = "feed_id IN (SELECT id FROM feed WHERE id in (?, ?))"
        values = (self.tracked_feed.id, self.other_feed1.id)
        query.add_complex_condition("feed_id", sql, values)
        query.set_order_by('release_date')
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
        query.set_order_by('release_date')
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items([item1, item3])
        # But we should'nt do a prefix search for terms other than the last
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.tracked_feed.id)
        query.set_search('fo bar')
        query.set_order_by('release_date')
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

    def test_order(self):
        # test order by a different column
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('feed_id', '=', self.tracked_feed.id)
        query.set_order_by('title')
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items()
        # test reverse ordering
        query.set_order_by('-title')
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items()
        # test order by multiple column
        query.set_order_by('title', '-release_date')
        self.tracker.change_query(query)
        self.check_one_signal('list-changed')
        self.check_tracker_items()

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
        query = itemtrack.ItemTrackerQuery()
        query.add_condition('remote_downloader.state', '=', 'downloading')
        query.set_order_by('remote_downloader.rate')
        self.tracker.change_query(query)
        correct_items = ItemFetcher().fetch_many(self.tracker.connection,
                                                 [i.id for i in downloads])
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
        # After ItemTracker gets the ItemsChanged message, it should load the
        # new data
        self.process_items_changed_message()
        self.assertEquals(self.tracker.get_item(item1.id).title,
                          u'new title')
        self.assertRaises(KeyError, self.tracker.get_item, item2.id)
