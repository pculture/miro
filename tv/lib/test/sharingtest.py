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

class ShareTest(MiroTestCase):
    # Test the backend Share object
    def setUp(self):
        MiroTestCase.setUp(self)
        # No need to have Share objects create real SharingItemTrackerImpl
        # instances
        self.MockSharingItemTrackerIpml = self.patch_for_test(
            'miro.sharing.SharingItemTrackerImpl')

    def test_database_paths(self):
        share1 = testobjects.make_share('TestShare')
        self.assertEquals(share1.db_path,
                          os.path.join(self.sandbox_support_directory,
                                       'sharing-db-0'))
        share2 = testobjects.make_share('TestShare2')
        self.assertEquals(share2.db_path,
                          os.path.join(self.sandbox_support_directory,
                                       'sharing-db-1'))

    def test_database_create_deletes_old_files(self):
        # test that if there's a file leftover from a previous miro run, we
        # delete it and then re-use it
        old_path = os.path.join(self.sandbox_support_directory,
                                'sharing-db-0')
        with open(old_path, 'wb') as f:
            f.write("old data")
        share = testobjects.make_share()
        self.assertEquals(share.db_path, old_path)
        # check that we opened a sqlite database on that path and overwrote
        # the old data
        if open(old_path).read() == 'old data':
            raise AssertionError("Didn't overwrite old path")

    def test_create_and_destroy(self):
        share = testobjects.make_share()
        self.assertNotEquals(share.db_path, None)
        self.assertNotEquals(share.db_info, None)
        old_path = share.db_path
        share.destroy()
        self.assertEquals(share.db_path, None)
        self.assertEquals(share.db_info, None)
        if os.path.exists(old_path):
            raise AssertionError("Calling Share.destroy() "
                                 "didn't delete database")

    def test_start_tracking(self):
        share = testobjects.make_share()
        self.assertEquals(share.tracker, None)
        # Calling start_tracking should create a SharingItemTrackerImpl
        share.start_tracking()
        self.assertNotEquals(share.tracker, None)
        tracker = share.tracker
        share.stop_tracking()
        self.assertEquals(share.tracker, None)
        # check that we call client_disconnect()
        self.assertEquals(tracker.client_disconnect.call_count, 1)
        # Calling start_tracking() again should re-create the tracker
        share.start_tracking()
        self.assertNotEquals(share.tracker, None)

    def test_start_tracking_twice(self):
        # Check that that calling start_tracking() twice in a row
        share = testobjects.make_share()
        share.start_tracking()
        first_tracker = share.tracker
        share.start_tracking()
        # second call should keep the same tracker
        self.assertEquals(share.tracker, first_tracker)

    def test_stop_tracking_twice(self):
        # Check that that calling stop_tracking() twice in a row
        share = testobjects.make_share()
        share.start_tracking()
        share.stop_tracking()
        self.assertEquals(share.tracker, None)
        # second call shouldn't cause an error
        share.stop_tracking()

class SharingTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.share = testobjects.make_share()
        # Replace threading.Thread() with a mock object so that
        # SharingItemTrackerImpl objects don't create real theads.
        self.patch_for_test('threading.Thread')
        # Replace update_started() and update_finished() with mock objects.
        # We want to ignore the TabsChanged messages that they send out.
        self.patch_for_test('miro.sharing.Share.update_started')
        self.patch_for_test('miro.sharing.Share.update_finished')
        # also use a Mock object for the daap client
        self.client = testobjects.MockDAAPClient()
        self.patch_for_test('miro.libdaap.make_daap_client',
                            self.client.returnself)
        self.MockTabsChanged = self.patch_for_test(
            'miro.messages.TabsChanged')

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

    def check_tracker_items(self, correct_items):
        # check the SharingItems in the database.  correct_items should be a
        # dictionary that maps item ids to item titles.
        item_view = models.SharingItem.make_view(db_info=self.share.db_info)
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

    def check_client_connect(self):
        """Check the initial pass that creates items for
        SharingItemTrackerImpl """
        # simulate the inital pass
        client_connect_result = self.share.tracker.client_connect()
        # we shouldn't touch the DB in setup_items()
        self.check_tracker_items({})
        # check the results of the initial pass
        self.share.tracker.client_connect_callback(client_connect_result)
        correct_items = dict((key, item['dmap.itemname'])
                             for key, item in
                             self.client.current_items().items())
        self.check_tracker_items(correct_items)

    def check_client_update(self):
        """Check the an update run for SharingItemTrackerImpl """
        # calculate the what items are in the DB before the update
        item_view = models.SharingItem.make_view(db_info=self.share.db_info)
        items_before_update = dict((i.id, i.title) for i in item_view)
        # run the update
        client_update_result = self.share.tracker.client_update()
        # we shouldn't touch the DB in setup_items()
        self.check_tracker_items(items_before_update)
        # check the results of the update
        self.share.tracker.client_update_callback(client_update_result)
        correct_items = dict((key, item['dmap.itemname'])
                             for key, item in
                             self.client.current_items().items())
        self.check_tracker_items(correct_items)

    def daap_playlist_tab_id(self, daap_id):
        return '%s-%s-%s-%s' % (self.share.name, self.share.host,
                                self.share.port, daap_id)

    def check_tabs_changed(self, correct_added_ids, correct_changed_ids,
                           correct_removed_ids):
        self.assertEquals(self.MockTabsChanged.call_count, 1)
        type_, added, changed, removed = self.MockTabsChanged.call_args[0]
        self.assertEquals(type_, 'connect')
        current_playlists = self.client.current_playlists()
        # check ids for added/removed/changed playlists
        self.assertEquals([info.id for info in added],
                          [self.daap_playlist_tab_id(daap_id)
                           for daap_id in correct_added_ids])
        self.assertEquals([info.id for info in changed],
                          [self.daap_playlist_tab_id(daap_id)
                           for daap_id in correct_changed_ids])
        self.assertSameSet(removed, correct_removed_ids)
        # check that the info for added/changed playlists is correct
        for info in added + changed:
            playlist_data = current_playlists[info.playlist_id]
            self.assertEquals(info.name, playlist_data['dmap.itemname'])
            podcast_key = 'com.apple.itunes.is-podcast-playlist'
            self.assertEquals(info.podcast,
                              playlist_data.get(podcast_key, False))

        self.MockTabsChanged.reset_mock()


    def test_sharing_items(self):
        # test sharing items created/update/delete

        # test initial item creation
        self.share.start_tracking()
        self.client.set_items(self.make_daap_items(
            {1: 'title-1', 2: 'title-2'}))
        self.check_client_connect()
        # test item update.
        # item 1 is updated, item 2 is deleted, and item 3 is added
        self.client.set_items(self.make_daap_items(
            {1: 'new-title-1', 3: 'new-title-3'}))
        self.check_client_update()

    def test_playlists(self):
        # test sending TabInfo updates for playlists

        # test initial item creation
        # only playlists with items should be created
        self.share.start_tracking()
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
        self.check_client_connect()
        self.check_tabs_changed([101, 102], [], [])

        # check updating playlists
        self.client.add_playlist(
            testobjects.make_mock_daap_playlist(104, 'playlist-4')
        )
        self.client.set_playlist_items(104, [1, 2])
        self.client.add_playlist(
            testobjects.make_mock_daap_playlist(102, 'new-playlist-2')
        )
        self.check_client_update()
        self.check_tabs_changed([104], [102], [])

        # check playlist deletion
        self.client.remove_playlist(101)
        # 102 gets removed because of no items
        self.client.set_playlist_items(102, [])
        # 103 is not removed because it never  contained items
        self.client.remove_playlist(103)
        self.check_client_update()
        self.check_tabs_changed([], [], [101, 102])

        # check that adding items to an empty playlist results in it being
        # added
        self.client.set_playlist_items(102, [1])
        self.check_client_update()
        self.check_tabs_changed([102], [], [])

    def test_disconnect_removes_playlists(self):
        # test that playlist tabs get after the client disconnects
        self.share.start_tracking()
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
        self.check_client_connect()
        self.check_tabs_changed([101], [], [])
        # run the code that happens after the tracker disconnects
        # playlist 1 should be removed.  playlist 2 was never added, so it
        # shouldn't be in the message.
        self.share.tracker.client_disconnect_callback_common()
        self.check_tabs_changed([], [], [101])

    def test_nul_in_playlist_data(self):
        # test that we remove NUL chars from playlist data (#17537)
        self.share.start_tracking()
        self.MockTabsChanged.reset_mock()
        self.client.set_items(self.make_daap_items({1: 'title-1'}))
        self.client.add_playlist(
            testobjects.make_mock_daap_playlist(101, 'playlist-\0\0one\0')
        )
        self.client.set_playlist_items(101, [1])
        self.share.tracker.client_connect_callback(
            self.share.tracker.client_connect())
        type_, added, changed, removed = self.MockTabsChanged.call_args[0]
        self.assertEquals(added[0].name, "playlist-one")

    def test_nul_in_item_data(self):
        # test that we remove NUL chars from item data (#17537)
        self.share.start_tracking()
        self.client.set_items(self.make_daap_items(
            {1: 'title-\0\0one\0'}))
        self.share.tracker.client_connect_callback(
            self.share.tracker.client_connect())
        db_item = models.SharingItem.get_by_daap_id(
            1, db_info=self.share.db_info)
        self.assertEquals(db_item.title, "title-one")
