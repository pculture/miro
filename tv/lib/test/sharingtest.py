# Miro - an RSS based video player application
# Copyright (C) 2010, 2011
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

from miro import sharing
import os

import sqlite3

from miro import models
from miro.test import mock
from miro.test import testobjects
from miro.test.framework import MiroTestCase, EventLoopTest

class SharingTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.share = mock.Mock()
        self.share.name = 'MockShare'
        self.share.host = '127.0.0.1'
        self.share.port = 1234
        # sharing uses a separate thread to communicate with the client.
        # Patch it so that we can run the code in our own thread
        self.mock_thread_class = self.patch_for_test('threading.Thread')
        self.mock_add_idle = self.patch_for_test('miro.eventloop.add_idle')
        # also use a Mock object for the daap client
        self.client = testobjects.MockDAAPClient()
        self.patch_for_test('miro.libdaap.make_daap_client',
                            self.client.returnself)
        self.MockTabsChanged = self.patch_for_test(
            'miro.messages.TabsChanged')

    def run_sharing_item_tracker_impl(self, share, database_filename):
        correct_database_path = os.path.join(self.sandbox_support_directory,
                                             database_filename)
        tracker_impl = sharing.SharingItemTrackerImpl(share)
        self.assertEquals(tracker_impl.db_path, correct_database_path)
        self.check_sharing_item_tracker_db(tracker_impl.db_path)
        # creating the SharingItemTrackerImpl should result in an attempt to
        # farm the work off into another thread.  This won't happen because
        # we've replaced threading.Thread with a mock object.
        thread_obj = self.mock_thread_class.return_value
        self.assertEquals(self.mock_thread_class.call_args[1]['target'],
                          tracker_impl.runloop)
        # go through the runloop one step at a time.  While
        # SharingItemTrackerImpl is running, db_path should be set
        success = tracker_impl.run_client_connect()
        if not success:
            raise AssertionError("client_connect failed.  Messages:\n\n%s" %
                                 self.log_messages())
        self.assertEquals(tracker_impl.db_path, correct_database_path)
        success = tracker_impl.run_client_update()
        if not success:
            raise AssertionError("client_update failed.  Messages:\n\n%s" %
                                 self.log_messages())
        self.assertEquals(tracker_impl.db_path, correct_database_path)
        # delete the client attribute to stop the run loop.  After
        # SharingItemTrackerImpl finishes, db_path should be unset
        del tracker_impl.client
        success = tracker_impl.run_client_update()
        if success:
            raise AssertionError("client_connect didn't fail "
                                 "when client=None.")
        tracker_impl.destroy_database()
        self.assertEquals(tracker_impl.db_path, None)
        if os.path.exists(correct_database_path):
            raise AssertionError("SharingItemTrackerImpl didn't delete "
                                 "its database")

    def check_sharing_item_tracker_db(self, db_path):
        if not os.path.exists(db_path):
            raise AssertionError("SharingItemTrackerImpl didn't create "
                                 "its database")
        # do a quick check on the DB schema
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [r[0] for r in cursor]
        conn.close()
        self.assertSameSet(table_names,
                           ['sharing_item', 'item_info_cache',
                            'dtv_variables'])

    def test_database_create(self):
        # test that SharingItemTrackerImpl creates an database
        self.run_sharing_item_tracker_impl(self.share, 'sharing-db-0')

    def test_database_create_second(self):
        # test that SharingItemTrackerImpl creates a database for the second
        # share correctly
        first_share = mock.Mock()
        first_tracker_impl = sharing.SharingItemTrackerImpl(first_share)
        first_tracker_impl.run_client_connect()
        # first_tracker_impl is now taking up the first database name.  Test
        # that the next one uses sharing-db-1 instead of sharing-db-0
        self.run_sharing_item_tracker_impl(self.share, 'sharing-db-1')

    def test_database_create_deletes_old_files(self):
        # test that if there's a file leftover from a previous miro run, we
        # delete it and then re-use it
        old_path = os.path.join(self.sandbox_support_directory,
                                'sharing-db-0')
        with open(old_path, 'wb') as f:
            f.write("old data")
        self.run_sharing_item_tracker_impl(self.share, 'sharing-db-0')

    def test_error_deleting_old_files(self):
        # test what happens when we get an error deleting an old file
        old_path = os.path.join(self.sandbox_support_directory,
                                'sharing-db-0')
        with open(old_path, 'wb') as f:
            f.write("old data")

        def mock_remove(path):
            if path == old_path:
                raise OSError("Permission Error")
            else:
                os.unlink(path)
        self.patch_function('os.remove', mock_remove)
        with self.allow_warnings():
            self.run_sharing_item_tracker_impl(self.share, 'sharing-db-1')

    def test_error_opening_database(self):
        # test errors when opening a database file
        old_sqlite_open = sqlite3.connect
        def mock_sqlite_connect(path, *args, **kwargs):
            if (path == os.path.join(self.sandbox_support_directory,
                                     'sharing-db-0')):
                raise sqlite3.Error("Error")
            else:
                return old_sqlite_open(path, *args, **kwargs)
        self.patch_function('sqlite3.connect', mock_sqlite_connect)
        with self.allow_warnings():
            self.run_sharing_item_tracker_impl(self.share, 'sharing-db-1')

    def check_tracker_items(self, tracker_impl, correct_items):
        # check the SharingItems in the database.  correct_items should be a
        # dictionary that maps item ids to item titles.
        item_view = models.SharingItem.make_view(db_info=tracker_impl.db_info)
        data_from_db = dict((i.id, i.title) for i in item_view)
        # check that the IDs are correct
        self.assertSameSet(data_from_db.keys(), correct_items.keys())
        # check that the titles are correct
        self.assertEquals(data_from_db, correct_items)

    def make_daap_items(self, items_dict):
        """Given a dict mapping item ids to item titles, create a dict mapping
        those ids to DAAP items.
        """
        client_items = {}
        for item_id, title in items_dict.items():
            daap_item = testobjects.make_mock_daap_item(item_id, title)
            client_items[item_id] = daap_item
        return client_items

    def check_client_connect(self, tracker_impl):
        """Check the initial pass that creates items for
        SharingItemTrackerImpl

        :param tracker_impl: SharingItemTrackerImpl to test
        """
        # simulate the inital pass
        client_connect_result = tracker_impl.client_connect()
        # we shouldn't touch the DB in setup_items()
        self.check_tracker_items(tracker_impl, {})
        # check the results of the initial pass
        tracker_impl.client_connect_callback(client_connect_result)
        correct_items = dict((key, item['dmap.itemname'])
                             for key, item in
                             self.client.current_items().items())
        self.check_tracker_items(tracker_impl, correct_items)

    def check_client_update(self, tracker_impl):
        """Check the an update run for SharingItemTrackerImpl

        :param tracker_impl: SharingItemTrackerImpl to test
        :param current_items: dictionary mapping item_ids to item titles.  We
        will simulate those items being returned by the daap client
        :param deleted_ids: dictionary maaping item ids to item titles for
        deleted items
        """
        # calculate the what items are in the DB before the update
        item_view = models.SharingItem.make_view(db_info=tracker_impl.db_info)
        items_before_update = dict((i.id, i.title) for i in item_view)
        # run the update
        client_update_result = tracker_impl.client_update()
        # we shouldn't touch the DB in setup_items()
        self.check_tracker_items(tracker_impl, items_before_update)
        # check the results of the update
        tracker_impl.client_update_callback(client_update_result)
        correct_items = dict((key, item['dmap.itemname'])
                             for key, item in
                             self.client.current_items().items())
        self.check_tracker_items(tracker_impl, correct_items)

    def daap_playlist_tab_id(self, daap_id):
        return '%s-%s-%s-%s' % (self.share.name, self.share.host,
                                self.share.port, daap_id)

    def check_tabs_changed(self, correct_added_ids, correct_changed_ids,
                           correct_removed_ids):
        self.assertEquals(self.MockTabsChanged.call_count, 1)
        type_, added, changed, removed = self.MockTabsChanged.call_args[0]
        self.assertEquals(type_, 'connect')
        current_playlists = self.client.current_playlists()
        # check added playlists
        self.assertEquals([info.id for info in added],
                          [self.daap_playlist_tab_id(daap_id)
                           for daap_id in correct_added_ids])
        for info in added:
            playlist_data = current_playlists[info.playlist_id]
            self.assertEquals(info.name, playlist_data['dmap.itemname'])
            podcast_key = 'com.apple.itunes.is-podcast-playlist'
            self.assertEquals(info.podcast,
                              playlist_data.get(podcast_key, False))

        # check changed playlists
        self.assertEquals(changed[0], self.share)

        # check removed playlists
        self.assertSameSet(removed, correct_removed_ids)
        self.MockTabsChanged.reset_mock()


    def test_sharing_items(self):
        # test sharing items created/update/delete

        # test initial item creation
        tracker_impl = sharing.SharingItemTrackerImpl(self.share)
        self.client.set_items(self.make_daap_items(
            {1: 'title-1', 2: 'title-2'}))
        self.check_client_connect(tracker_impl)
        # test item update.
        # item 1 is updated, item 2 is deleted, and item 3 is added
        self.client.set_items(self.make_daap_items(
            {1: 'new-title-1', 3: 'new-title-3'}))
        self.check_client_update(tracker_impl)

    def test_playlists(self):
        # test sending TabInfo updates for playlists

        # test initial item creation
        # only playlists with items should be created
        tracker_impl = sharing.SharingItemTrackerImpl(self.share)
        self.MockTabsChanged.reset_mock()
        self.client.set_items(self.make_daap_items(
            {1: 'title-1', 2: 'title-2'}))
        self.client.add_playlist(
            testobjects.make_mock_daap_playlist(101, 'playlist-1')
        )
        self.client.add_playlist(
            testobjects.make_mock_daap_playlist(102, 'playlist-2')
        )
        self.client.add_playlist(
            testobjects.make_mock_daap_playlist(103, 'playlist-3')
        )
        self.client.set_playlist_items(101, [1])
        self.client.set_playlist_items(102, [1, 2])
        self.check_client_connect(tracker_impl)
        self.check_tabs_changed([101, 102], [], [])

        # check updating playlists
        self.client.add_playlist(
            testobjects.make_mock_daap_playlist(104, 'playlist-4')
        )
        self.client.set_playlist_items(104, [1, 2])
        self.client.add_playlist(
            testobjects.make_mock_daap_playlist(102, 'new-playlist-2')
        )
        self.check_client_update(tracker_impl)
        self.check_tabs_changed([104], [102], [])

        # check playlist deletion
        self.client.remove_playlist(101)
        # 102 gets removed because of no items
        self.client.set_playlist_items(102, [])
        # 103 is not removed because it never  contained items
        self.client.remove_playlist(103)
        self.check_client_update(tracker_impl)
        self.check_tabs_changed([], [], [101, 102])

        # check that adding items to an empty playlist results in it being
        # added
        self.client.set_playlist_items(102, [1])
        self.check_client_update(tracker_impl)
        self.check_tabs_changed([102], [], [])

    def test_disconnect_removes_playlists(self):
        # test that playlist tabs get after the client disconnects
        tracker_impl = sharing.SharingItemTrackerImpl(self.share)
        self.MockTabsChanged.reset_mock()
        self.client.set_items(self.make_daap_items(
            {1: 'title-1', 2: 'title-2'}))
        self.client.add_playlist(
            testobjects.make_mock_daap_playlist(101, 'playlist-1')
        )
        self.client.add_playlist(
            testobjects.make_mock_daap_playlist(102, 'playlist-2')
        )
        self.client.set_playlist_items(101, [1])
        self.check_client_connect(tracker_impl)
        self.check_tabs_changed([101], [], [])
        # run the code that happens after the tracker disconnects
        # playlist 1 should be removed.  playlist 2 was never added, so it
        # shouldn't be in the message.
        tracker_impl.client_disconnect_callback_common()
        self.check_tabs_changed([], [], [101])

    def test_nul_in_playlist_data(self):
        # test that we remove NUL chars from playlist data (#17537)
        tracker_impl = sharing.SharingItemTrackerImpl(self.share)
        self.MockTabsChanged.reset_mock()
        self.client.set_items(self.make_daap_items({1: 'title-1'}))
        self.client.add_playlist(
            testobjects.make_mock_daap_playlist(101, 'playlist-\0\0one\0')
        )
        self.client.set_playlist_items(101, [1])
        tracker_impl.client_connect_callback(tracker_impl.client_connect())
        type_, added, changed, removed = self.MockTabsChanged.call_args[0]
        self.assertEquals(added[0].name, "playlist-one")

    def test_nul_in_item_data(self):
        # test that we remove NUL chars from item data (#17537)
        tracker_impl = sharing.SharingItemTrackerImpl(self.share)
        self.client.set_items(self.make_daap_items(
            {1: 'title-\0\0one\0'}))
        tracker_impl.client_connect_callback(tracker_impl.client_connect())
        db_item = models.SharingItem.get_by_daap_id(
            1, db_info=tracker_impl.db_info)
        self.assertEquals(db_item.title, "title-one")
