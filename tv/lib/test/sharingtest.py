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

from miro.test import mock
from miro.test import testobjects
from miro.test.framework import MiroTestCase, EventLoopTest

class SharingDatabaseTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.share = mock.Mock()
        # sharing uses a separate thread to communicate with the client.
        # Patch it so that we can run the code in our own thread
        self.mock_thread_class = self.patch_for_test('threading.Thread')
        self.mock_add_idle = self.patch_for_test('miro.eventloop.add_idle')
        # also use a Mock object for the daap client
        self.patch_for_test('miro.libdaap.make_daap_client',
                            testobjects.make_mock_daap_client)

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
