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

from miro import app
from miro import messages
from miro import messagehandler
from miro import models
from miro import prefs
from miro import startup
from miro.data import mappings
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
        self.playlist_item_map = mappings.SharingItemPlaylistMap(
            self.share.db_info.db.connection)
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
                           ['sharing_item', 'dtv_variables'])

    def check_tracker_items(self, correct_items):
        # check the SharingItems in the database.  correct_items should be a
        # dictionary that maps item ids to item titles.
        item_view = models.SharingItem.make_view(db_info=self.share.db_info)
        data_from_db = dict((i.id, i.title) for i in item_view)
        # check that the IDs are correct
        self.assertSameSet(data_from_db.keys(), correct_items.keys())
        # check that the titles are correct
        self.assertEquals(data_from_db, correct_items)

    def check_playlist_items_map(self, correct_playlist_items):
        """Check the data in playlist_item_map 

        :param correct_playlist_items: dict mapping playlist ids to the items
        that should be in them.
        """
        self.assertEquals(self.playlist_item_map.get_map(),
                          correct_playlist_items)

    def make_daap_items(self, items_dict):
        """Given a dict mapping item ids to item titles, create a dict mapping
        those ids to DAAP items.
        """
        return [testobjects.make_mock_daap_item(item_id, title)
                for (item_id, title) in items_dict.items()]

    def check_client_connect(self):
        """Check the initial pass that creates items for
        SharingItemTrackerImpl """
        # simulate the inital pass
        client_connect_result = self.share.tracker.client_connect()
        # we shouldn't touch the DB in setup_items()
        self.check_tracker_items({})
        self.check_playlist_items_map({})
        # check the results of the initial pass
        self.share.tracker.client_connect_callback(client_connect_result)
        correct_items = dict((key, item['dmap.itemname'])
                             for key, item in
                             self.client.current_items().items())
        self.check_tracker_items(correct_items)
        correct_playlist_items = dict(
            (playlist_id, set(item_ids))
             for (playlist_id, item_ids) in
             self.client.current_playlist_item_map().items())
        self.check_playlist_items_map(correct_playlist_items)

    def check_client_update(self):
        """Check the an update run for SharingItemTrackerImpl """
        # calculate the what items are in the DB before the update
        item_view = models.SharingItem.make_view(db_info=self.share.db_info)
        items_before_update = dict((i.id, i.title) for i in item_view)
        playlist_items_before_update = self.playlist_item_map.get_map()
        # run the update
        client_update_result = self.share.tracker.client_update()
        # we shouldn't touch the DB in setup_items()
        self.check_tracker_items(items_before_update)
        self.check_playlist_items_map(playlist_items_before_update)
        # check the results of the update
        self.share.tracker.client_update_callback(client_update_result)
        correct_items = dict((key, item['dmap.itemname'])
                             for key, item in
                             self.client.current_items().items())
        self.check_tracker_items(correct_items)
        correct_playlist_items = dict(
            (playlist_id, set(item_ids))
             for (playlist_id, item_ids) in
             self.client.current_playlist_item_map().items())
        self.check_playlist_items_map(correct_playlist_items)

    def daap_playlist_tab_id(self, daap_id):
        return 'sharing-%s-%s' % (self.share.id, daap_id)

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
            testobjects.make_mock_daap_playlist(102, 'new-playlist-2',
                                                is_podcast=True)
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

class SharingServerTest(EventLoopTest):
    """Test the sharing server."""
    def setUp(self):
        EventLoopTest.setUp(self)
        # need to call setup_tabs for PlaylistTracker() and
        # ChannelTracker()
        startup.setup_tabs()
        self.setup_config()
        self.setup_data()

    def setup_config(self):
        app.config.set(prefs.SHARE_AUDIO, True)
        app.config.set(prefs.SHARE_VIDEO, False)
        app.config.set(prefs.SHARE_FEED, True)

    def setup_data(self):
        self.manual_feed = testobjects.make_manual_feed()
        self.feed_with_downloads = testobjects.make_feed()
        self.feed_without_downloads = testobjects.make_feed()
        self.audio_items = []
        self.video_items = []
        self.undownloaded_items = []
        for i in xrange(10):
            self.audio_items.append(testobjects.make_file_item(
                self.feed_with_downloads, u'audio-item-%s' % i, ext='.mp3'))
            self.video_items.append(testobjects.make_file_item(
                self.manual_feed, u'video-item-%s' % i, ext='.avi'))
            self.undownloaded_items.append(testobjects.make_item(
                self.feed_without_downloads, u'feed-item-%s' % i))

        self.audio_playlist = models.SavedPlaylist(u'My music',
                [i.id for i in self.audio_items])
        # put some videos in the videos playlist.  These will be sent back by
        # the server, even if SHARE_VIDEO is not set
        self.video_playlist_items = self.video_items[:5]
        self.video_playlist = models.SavedPlaylist(u'My best videos',
                [i.id for i in self.video_playlist_items])
        app.db.finish_transaction()
        models.Item.change_tracker.reset()

    def setup_sharing_manager_backend(self):
        self.backend = sharing.SharingManagerBackend()
        self.backend.start_tracking()

    def check_daap_list(self, daap_list, ddb_objects):
        """Check data in our SharingManagerBackend

        :param daap_list: The return value of get_items() or get_playlists()
        :param ddb_objects: list of Item or Playlist objects to check against
        """
        daap_ids_and_names = []
        for daap_id, daap_data in daap_list.items():
            if daap_data['valid']:
                # do a quick check that the key for the dictionary is the same
                # as dmap.itemid
                self.assertEquals(daap_id, daap_data['dmap.itemid'])
                daap_ids_and_names.append(
                        (daap_id, daap_data['dmap.itemname']))
        correct_ids_and_names = [(obj.id, obj.get_title())
                                 for obj in ddb_objects]
        self.assertSameSet(daap_ids_and_names, correct_ids_and_names)

    def check_daap_item_deleted(self, item_list, ddb_object):
        self.assertEquals(item_list[ddb_object.id]['valid'], False)

    def check_get_revision_will_block(self, old_revision):
        self.assertEquals(self.backend.data_set.revision, old_revision)

    def send_changes_from_trackers(self):
        app.db.finish_transaction()
        models.Item.change_tracker.send_changes()
        self.backend.data_set.after_event_finished(mock.Mock(), True)

    def test_initial_list(self):
        self.setup_sharing_manager_backend()
        # test getting all items
        self.check_daap_list(self.backend.get_items(), 
                             self.audio_items + self.video_playlist_items)
        # test getting playlists
        self.check_daap_list(self.backend.get_playlists(),
                [self.audio_playlist, self.video_playlist,
                 self.feed_with_downloads, self.feed_without_downloads])
        # test getting items for a playlist
        self.check_daap_list(self.backend.get_items(self.audio_playlist.id),
                self.audio_items)
        self.check_daap_list(
            self.backend.get_items(self.video_playlist.id),
            self.video_playlist_items)
        self.check_daap_list(
            self.backend.get_items(self.feed_with_downloads.id),
            self.audio_items)
        self.check_daap_list(
            self.backend.get_items(self.feed_without_downloads.id), [])

    def test_initial_list_no_feeds(self):
        app.config.set(prefs.SHARE_FEED, False)
        self.setup_sharing_manager_backend()
        self.check_daap_list(self.backend.get_playlists(),
                [self.audio_playlist, self.video_playlist])

    def test_item_changes(self):
        self.setup_sharing_manager_backend()
        initial_revision = self.backend.data_set.revision
        added = self.video_items[0]
        added.set_user_metadata({'file_type': u'audio'})
        added.signal_change()
        changed = self.audio_items[0]
        changed.set_user_metadata({'title': u'New title'})
        changed.signal_change()
        removed = self.audio_items[-1]
        removed.remove()
        self.check_get_revision_will_block(initial_revision)
        self.send_changes_from_trackers()
        self.assertNotEquals(self.backend.data_set.revision, initial_revision)
        # get_items() should reflect the changes
        new_item_list = ([added] + self.audio_items[:-1] +
                         self.video_playlist_items)
        self.check_daap_list(self.backend.get_items(), new_item_list)
        self.check_daap_item_deleted(self.backend.get_items(), removed)

    def test_feed_changes(self):
        self.setup_sharing_manager_backend()
        initial_revision = self.backend.data_set.revision
        new_feed = testobjects.make_feed()
        self.feed_with_downloads.set_title(u'New Title')
        self.feed_without_downloads.remove()
        self.send_changes_from_trackers()
        self.assertNotEquals(self.backend.data_set.revision, initial_revision)
        self.check_daap_list(self.backend.get_playlists(),
                [new_feed, self.feed_with_downloads, self.audio_playlist,
                    self.video_playlist])
        self.check_daap_item_deleted(self.backend.get_playlists(),
                self.feed_without_downloads)
        # test adding items
        second_revision = self.backend.data_set.revision
        for item in self.video_items:
            item.set_feed(new_feed.id)
        self.send_changes_from_trackers()
        self.assertNotEquals(self.backend.data_set.revision, second_revision)
        self.check_daap_list(self.backend.get_items(new_feed.id),
                             self.video_items)
        # test removing items
        third_revision = self.backend.data_set.revision
        for item in self.video_items[4:]:
            item.remove()
        self.send_changes_from_trackers()
        self.assertNotEquals(self.backend.data_set.revision, third_revision)
        self.check_daap_list(self.backend.get_items(new_feed.id),
                             self.video_items[:4])

    def test_playlist_changes(self):
        self.setup_sharing_manager_backend()
        initial_revision = self.backend.data_set.revision
        new_playlist = models.SavedPlaylist(u'My Playlist')
        self.audio_playlist.set_title(u'My Audio Files')
        self.video_playlist.remove()
        self.send_changes_from_trackers()
        self.assertNotEquals(self.backend.data_set.revision, initial_revision)
        self.check_daap_list(self.backend.get_playlists(),
                [self.feed_with_downloads, self.feed_without_downloads,
                    self.audio_playlist, new_playlist])
        self.check_daap_item_deleted(self.backend.get_playlists(),
                self.video_playlist)
        # test adding items
        second_revision = self.backend.data_set.revision
        for item in self.video_items:
            new_playlist.add_item(item)
        self.send_changes_from_trackers()
        self.assertNotEquals(self.backend.data_set.revision, second_revision)
        self.check_daap_list(self.backend.get_items(new_playlist.id),
                             self.video_items)
        # test removing items
        third_revision = self.backend.data_set.revision
        for item in self.video_items[4:]:
            new_playlist.remove_item(item)
        self.send_changes_from_trackers()
        self.assertNotEquals(self.backend.data_set.revision, third_revision)
        self.check_daap_list(self.backend.get_items(new_playlist.id),
                             self.video_items[:4])

    def test_change_share_feed(self):
        self.setup_sharing_manager_backend()
        initial_revision = self.backend.data_set.revision
        app.config.set(prefs.SHARE_FEED, False)
        self.assertNotEquals(self.backend.data_set.revision, initial_revision)
        self.check_daap_list(self.backend.get_items(),
                self.audio_items + self.video_playlist_items)
        self.check_daap_list(self.backend.get_playlists(),
                [self.audio_playlist, self.video_playlist])
        self.check_daap_item_deleted(self.backend.get_playlists(),
                self.feed_with_downloads)
        self.check_daap_item_deleted(self.backend.get_playlists(),
                self.feed_without_downloads)

    def test_change_share_video(self):
        self.setup_sharing_manager_backend()
        initial_revision = self.backend.data_set.revision
        app.config.set(prefs.SHARE_VIDEO, True)
        self.assertNotEquals(self.backend.data_set.revision, initial_revision)

        self.check_daap_list(self.backend.get_items(),
                self.audio_items + self.video_items)
        app.config.set(prefs.SHARE_VIDEO, False)
        self.check_daap_list(self.backend.get_items(),
                self.audio_items + self.video_playlist_items)
        for item in self.video_items:
            if item not in self.video_playlist_items:
                self.check_daap_item_deleted(self.backend.get_items(), item)

    def test_client_disconnects_in_get_revision(self):
        # get_revision() blocks waiting for chainges, but it should return if
        # the client disconnects.  Test that this happens
        self.setup_sharing_manager_backend()
        mock_socket = mock.Mock()
        # We use a threading.Condition object to wait for changes.
        self.wait_count = 0
        def mock_wait(timeout=None):
            # we must use a timeout since we want to poll the socket
            self.assertNotEquals(timeout, None)
            if self.wait_count > 2:
                raise AssertionError("wait called too many times")
            self.wait_count += 1
        self.backend.data_set.condition.wait = mock_wait

        # We use select() to check if the socket is closed.
        self.select_count = 0
        def mock_select(rlist, wlist, xlist, timeout=None):
            self.assertEquals(timeout, 0)
            self.assertEquals(rlist, [mock_socket])
            if self.select_count == 0:
                # first time around, return nothing
                rv = [], [], []
            elif self.select_count == 1:
                # second time around, return the socket as available for
                # reading.  This happens when the socket gets closed
                rv = [mock_socket], [], []
            else:
                raise AssertionError("select called too much")
            self.select_count += 1
            return rv
        self.patch_for_test('select.select', mock_select)
        # calling get_revision() should set all the wheels in motion
        initial_revision = self.backend.data_set.revision
        new_revision = self.backend.get_revision(mock.Mock(),
                                                 initial_revision,
                                                 mock_socket)
        # get_revision() should have returned before any changes happened.
        self.assertEquals(initial_revision, new_revision)

    # FIXME: implement this
    # def test_get_file(self):
        # pass
