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

import os
try:
    import simplejson as json
except ImportError:
    import json

import datetime
import shutil
import sqlite3

from miro.gtcache import gettext as _
from miro.plat.utils import (PlatformFilenameType, unicode_to_filename,
                             utf8_to_filename)
from miro.test.framework import MiroTestCase, EventLoopTest
from miro.test import mock

from miro import app
from miro import database
from miro import devicedatabaseupgrade
from miro import devices
from miro import item
from miro import messages
from miro import metadata
from miro import models
from miro import schema
from miro import storedatabase
from miro.data.item import fetch_item_infos
from miro.plat import resources
from miro.test import testobjects

class DeviceManagerTest(MiroTestCase):
    def build_config_file(self, filename, data):
        fn = os.path.join(self.tempdir, filename)
        fp = open(fn, "w")
        fp.write(data)
        fp.close()

    def test_empty(self):
        dm = devices.DeviceManager()
        dm.load_devices(os.path.join(self.tempdir, "*.py"))
        self.assertRaises(KeyError, dm.get_device, "py")
        self.assertRaises(KeyError, dm.get_device_by_id, 0, 0)

    def test_parsing(self):
        self.build_config_file(
            "foo.py",
            """from miro.gtcache import gettext as _
from miro.devices import DeviceInfo, MultipleDeviceInfo
defaults = {
    "audio_conversion": "mp3",
    "container_types": "isom mp3".split(),
    "audio_types": "mp3 aac".split(),
    "video_types": ["h264"],
    "mount_instructions": _("Mount Instructions\\nOver multiple lines"),
    "video_path": u"Video",
    "audio_path": u"Audio",
    }
target1 = DeviceInfo("Target1",
                     vendor_id=0x890a,
                     product_id=0xbcde,
                     device_name="Bar",
                     video_conversion="mp4",
                     **defaults)
target2 = DeviceInfo('Target2',
                     video_conversion="mp4")
target3 = DeviceInfo('Target3',
                     video_conversion="mp4")
multiple = MultipleDeviceInfo('Foo', [target2, target3],
                              vendor_id=0x1234,
                              product_id=0x4567,
                              **defaults)
devices = [target1, multiple]
""")

        dm = devices.DeviceManager()
        dm.load_devices(os.path.join(self.tempdir, "*.py"))

        # a single device
        device = dm.get_device("Bar")
        self.assertEqual(repr(device),
                         "<DeviceInfo 'Target1' 'Bar' 890a bcde>")
        # this comes from the section name
        self.assertEqual(device.name, "Target1")
        # this comes from the default
        self.assertEqual(device.audio_conversion, "mp3")
        # this comes from the section
        self.assertEqual(device.device_name, 'Bar')
        self.assertEqual(device.video_conversion, "mp4")
        self.assertEqual(device.audio_path, 'Audio')
        self.assertTrue(isinstance(device.audio_path, PlatformFilenameType))
        self.assertEqual(device.video_path, 'Video')
        self.assertTrue(isinstance(device.video_path, PlatformFilenameType))
        # these are a special case
        self.assertFalse(device.has_multiple_devices)
        self.assertEqual(device.mount_instructions,
                         _('Mount Instructions\nOver multiple lines'))
        self.assertEqual(device.container_types, ['mp3', 'isom'])
        self.assertEqual(device.audio_types, ['mp3', 'aac'])
        self.assertEqual(device.video_types, ['h264'])

        # both devices have the same ID
        device = dm.get_device_by_id(0x1234, 0x4567)
        self.assertTrue(device.has_multiple_devices)
        self.assertEquals(device.name, 'Foo')
        self.assertEquals(device.device_name, 'Foo')
        self.assertEquals(device.vendor_id, 0x1234)
        self.assertEquals(device.product_id, 0x4567)
        self.assertEqual(device.mount_instructions,
                         _('Mount Instructions\nOver multiple lines'))

        single = device.get_device('Target2')
        self.assertFalse(single.has_multiple_devices)
        self.assertEqual(single.name, 'Target2')

    def test_invalid_device(self):
        self.build_config_file(
            "foo.py",
            """from miro.devices import DeviceInfo
target1 = DeviceInfo("Target1")
devices = [target1]
""")
        dm = devices.DeviceManager()
        with self.allow_warnings():
            dm.load_devices(os.path.join(self.tempdir, "*.py"))
        self.assertRaises(KeyError, dm.get_device, "Target1")
        self.assertRaises(KeyError, dm.get_device_by_id, 0, 0)

    def test_generic_device(self):
        self.build_config_file(
            "foo.py",
            """from miro.devices import DeviceInfo
target1 = DeviceInfo("Target1",
                     device_name='Foo*',
                     vendor_id=0x1234,
                     product_id=None,
                     video_conversion="hero",
                     audio_conversion="mp3",
                     container_types="isom mp3".split(),
                     audio_types="mp3 aac".split(),
                     video_types=["h264"],
                     mount_instructions=u"",
                     video_path=u"Video",
                     audio_path=u"Audio")
devices = [target1]
""")
        dm = devices.DeviceManager()
        dm.load_devices(os.path.join(self.tempdir, '*.py'))
        device = dm.get_device('Foo Bar')
        self.assertEqual(device.name, "Target1")
        device = dm.get_device_by_id(0x1234, 0x4567)
        self.assertEqual(device.name, "Target1")

    def test_multiple_device_gets_data_from_first_child(self):
        """
        If a MultipleDeviceInfo object is created without all the appropriate
        data, it will grab it from its first child.
        """
        self.build_config_file(
            "foo.py",
            """from miro.devices import DeviceInfo, MultipleDeviceInfo
defaults = {
    "audio_conversion": "mp3",
    "container_types": "mp3 isom".split(),
    "audio_types": "mp3 aac".split(),
    "video_types": ["h264"],
    "mount_instructions": "Mount Instructions\\nOver multiple lines",
    "video_path": u"Video",
    "audio_path": u"Audio",
    }
target1 = DeviceInfo("Target1",
                     vendor_id=0x890a,
                     product_id=0xbcde,
                     video_conversion="mp4",
                     **defaults)
target2 = DeviceInfo("Target2")
multiple = MultipleDeviceInfo('Foo', [target1, target2])
devices = [multiple]
""")
        dm = devices.DeviceManager()
        dm.load_devices(os.path.join(self.tempdir, '*.py'))
        device = dm.get_device('Foo')
        self.assertTrue(device.has_multiple_devices)
        self.assertEqual(device.video_conversion, "mp4")

    def test_multiple_device_info_single(self):
        """
        If a MultipleDeviceInfo has only one child, get_device() should just
        return the single child.
        """
        self.build_config_file(
            "foo.py",
            """from miro.devices import DeviceInfo, MultipleDeviceInfo
defaults = {
    "audio_conversion": "mp3",
    "container_types": "mp3 isom".split(),
    "audio_types": "mp3 aac".split(),
    "video_types": ["h264"],
    "mount_instructions": "Mount Instructions\\nOver multiple lines",
    "video_path": u"Video",
    "audio_path": u"Audio",
    }
target1 = DeviceInfo("Target1",
                     vendor_id=0x890a,
                     product_id=0xbcde,
                     video_conversion="mp4",
                     **defaults)
multiple = MultipleDeviceInfo('Foo', [target1])
devices = [multiple]
""")
        dm = devices.DeviceManager()
        dm.load_devices(os.path.join(self.tempdir, '*.py'))
        device = dm.get_device('Foo')
        self.assertFalse(device.has_multiple_devices)
        self.assertEqual(device.name, "Target1")
        self.assertEqual(device.device_name, "Foo")

class DeviceHelperTest(MiroTestCase):

    def test_load_database(self):
        data = {u'a': 2,
                u'b': {u'c': [5, 6]}}
        os.makedirs(os.path.join(self.tempdir, '.miro'))
        with open(os.path.join(self.tempdir, '.miro', 'json'), 'w') as f:
            json.dump(data, f)

        ddb = devices.load_database(self.tempdir)
        self.assertEqual(dict(ddb), data)
        self.assertEqual(len(ddb.get_callbacks('changed')), 1)

    def test_load_database_missing(self):
        ddb = devices.load_database(self.tempdir)
        self.assertEqual(dict(ddb), {})
        self.assertEqual(len(ddb.get_callbacks('changed')), 1)

    def test_load_database_error(self):
        os.makedirs(os.path.join(self.tempdir, '.miro'))
        with open(os.path.join(self.tempdir, '.miro', 'json'), 'w') as f:
            f.write('NOT JSON DATA')

        with self.allow_warnings():
            ddb = devices.load_database(self.tempdir)
        self.assertEqual(dict(ddb), {})
        self.assertEqual(len(ddb.get_callbacks('changed')), 1)

    def test_write_database(self):
        data = {u'a': 2,
                u'b': {u'c': [5, 6]}}
        devices.write_database(data, self.tempdir)
        with open(os.path.join(self.tempdir, '.miro', 'json')) as f:
            new_data = json.load(f)
        self.assertEqual(data, new_data)

class ScanDeviceForFilesTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.setup_device()
        self.add_fake_media_files_to_device()
        self.setup_fake_device_manager()

    def tearDown(self):
        del app.device_manager
        EventLoopTest.tearDown(self)

    def setup_device(self):
        self.device = testobjects.make_mock_device()

    def setup_fake_device_manager(self):
        app.device_manager = mock.Mock()
        app.device_manager.running = True
        app.device_manager._is_hidden.return_value = False

    def add_fake_media_files_to_device(self):
        self.device_item_filenames = [
            unicode_to_filename(f.decode('utf-8')) for f in
            ['foo.mp3', 'bar.mp3', 'foo.avi', 'bar.ogg']
        ]
        for filename in self.device_item_filenames:
            path = os.path.join(self.device.mount, filename)
            with open(path, 'w') as f:
                f.write("fake-data")

    def check_device_items(self, correct_paths):
        device_items = item.DeviceItem.make_view(db_info=self.device.db_info)
        device_item_paths = [di.filename for di in device_items]
        self.assertSameSet(device_item_paths, correct_paths)

    def run_scan_device_for_files(self):
        devices.scan_device_for_files(self.device)
        self.runPendingIdles()

    def test_scan_device_for_files(self):
        self.run_scan_device_for_files()
        self.check_device_items(self.device_item_filenames)

    def test_removed_files(self):
        self.run_scan_device_for_files()
        self.check_device_items(self.device_item_filenames)
        # remove a couple files
        for i in xrange(2):
            filename = self.device_item_filenames.pop()
            os.remove(os.path.join(self.device.mount, filename))
        # run scan_device_for_files again, it should remove the items that are
        # no longer present
        self.run_scan_device_for_files()
        self.check_device_items(self.device_item_filenames)

    def test_skip_read_only(self):
        self.device.read_only = True
        self.run_scan_device_for_files()
        self.check_device_items([])

class GlobSetTest(MiroTestCase):

    def test_globset_regular_match(self):
        gs = devices.GlobSet('abc')
        self.assertTrue('a' in gs)
        self.assertTrue('A' in gs)
        self.assertTrue('b' in gs)
        self.assertTrue('c' in gs)
        self.assertFalse('d' in gs)
        self.assertFalse('aa' in gs)

    def test_globset_glob_match(self):
        gs = devices.GlobSet(['a*', 'b*'])
        self.assertTrue('a' in gs)
        self.assertTrue('AB' in gs)
        self.assertTrue('b' in gs)
        self.assertTrue('ba' in gs)
        self.assertFalse('c' in gs)

    def test_globset_both_match(self):
        gs = devices.GlobSet(['a', 'b*'])
        self.assertTrue('a' in gs)
        self.assertTrue('b' in gs)
        self.assertTrue('ba' in gs)
        self.assertFalse('ab' in gs)
        self.assertFalse('c' in gs)

    def test_globset_and(self):
        gs = devices.GlobSet(['a', 'b*'])
        self.assertTrue(gs & set('a'))
        self.assertTrue(gs & set('b'))
        self.assertTrue(gs & set('bc'))
        self.assertTrue(gs & set(['bc', 'c']))
        self.assertFalse(gs & set('cd'))

    def test_globset_and_plain(self):
        gs = devices.GlobSet('ab')
        self.assertTrue(gs & set('a'))
        self.assertTrue(gs & set('b'))
        self.assertTrue(gs & set('ab'))
        self.assertTrue(gs & set('bc'))
        self.assertFalse(gs & set('cd'))

class DeviceDatabaseTest(MiroTestCase):
    "Test sqlite databases on devices."""
    def setUp(self):
        MiroTestCase.setUp(self)
        self.device = testobjects.make_mock_device(no_database=True)

    def open_database(self):
        testobjects.setup_mock_device_database(self.device)

    def test_open(self):
        self.open_database()
        self.assertEquals(self.device.db_info.db.__class__,
                          storedatabase.LiveStorage)
        self.assertEquals(self.device.db_info.db.error_handler.__class__,
                          storedatabase.DeviceLiveStorageErrorHandler)

    def test_reload(self):
        self.open_database()
        testobjects.make_device_items(self.device, 'foo.mp3', 'bar.mp3')
        # close, then reopen the database
        self.device.db_info.db.finish_transaction()
        self.open_database()
        # test that the database is still intact by checking the
        # metadata_status table
        cursor = self.device.db_info.db.cursor
        cursor.execute("SELECT path FROM metadata_status")
        paths = [r[0] for r in cursor.fetchall()]
        self.assertSameSet(paths, ['foo.mp3', 'bar.mp3'])

    @mock.patch('miro.dialogs.MessageBoxDialog.run_blocking')
    def test_load_error(self, mock_dialog_run):
        # Test an error loading the device database
        def mock_get_last_id():
            if not self.faked_get_last_id_error:
                self.faked_get_last_id_error = True
                raise sqlite3.DatabaseError("Error")
            else:
                return 0
        self.faked_get_last_id_error = False
        self.patch_function('miro.storedatabase.LiveStorage._get_last_id',
                            mock_get_last_id)
        self.open_database()
        # check that we displayed an error dialog
        mock_dialog_run.assert_called_once_with()
        # check that our corrupt database logic ran
        dir_contents = os.listdir(os.path.join(self.device.mount, '.miro'))
        self.assert_('corrupt_database' in dir_contents)

    def test_save_error(self):
        # FIXME: what should we do if we have an error saving to the device?
        pass

class DeviceUpgradeTest(MiroTestCase):
    """Test upgrading data from a JSON db from an old version of Miro."""

    def setUp(self):
        MiroTestCase.setUp(self)
        # setup a device object
        self.device = testobjects.make_mock_device(no_database=True)

    def setup_json_db(self, path):
        # setup a device database
        json_path = resources.path(path)
        self.device.db = devices.DeviceDatabase(json.load(open(json_path)))

    def test_upgrade_from_4x(self):
        # Test the upgrade from devices with just a JSON database
        self.setup_json_db('testdata/device-dbs/4.x-json')
        self.check_json_import(self.device.db[u'audio'])

    def check_json_import(self, device_data):
        """Check that we successfully imported the sqlite data."""
        sqlite_db = devices.load_sqlite_database(self.device.mount, 1024)
        sqlite_db.cursor.execute("SELECT album from metadata")
        db_info = database.DBInfo(sqlite_db)
        importer = devicedatabaseupgrade.OldItemImporter(sqlite_db,
                                                         self.device.mount,
                                                         self.device.db)
        importer.import_metadata()
        metadata_manager = devices.make_metadata_manager(self.device.mount,
                                                         db_info,
                                                         self.device.id)
        importer.import_device_items(metadata_manager)

        for path, item_data in device_data.items():
            # fill in data that's implicit with the dict
            item_data['file_type'] = u'audio'
            item_data['video_path'] = path
            filename = utf8_to_filename(path.encode('utf-8'))
            self.check_migrated_status(filename, db_info)
            self.check_migrated_entries(filename, item_data, db_info)
            self.check_migrated_device_item(filename, item_data, db_info)
            # check that the title tag was deleted
            self.assert_(not hasattr(item, 'title_tag'))

    def check_migrated_status(self, filename, device_db_info):
        # check the MetadataStatus.  For all items, we should be in the movie
        # data stage.
        status = metadata.MetadataStatus.get_by_path(filename, device_db_info)
        self.assertEquals(status.current_processor, u'movie-data')
        self.assertEquals(status.mutagen_status, status.STATUS_SKIP)
        self.assertEquals(status.moviedata_status, status.STATUS_NOT_RUN)
        self.assertEquals(status.echonest_status, status.STATUS_SKIP)
        self.assertEquals(status.net_lookup_enabled, False)

    def check_migrated_entries(self, filename, item_data, device_db_info):
        status = metadata.MetadataStatus.get_by_path(filename, device_db_info)
        entries = metadata.MetadataEntry.metadata_for_status(status,
                                                             device_db_info)
        entries = list(entries)
        self.assertEquals(len(entries), 1)
        entry = entries[0]
        self.assertEquals(entry.source, 'old-item')

        columns_to_check = entry.metadata_columns.copy()
        # handle drm specially
        self.assertEquals(entry.drm, False)
        columns_to_check.discard('drm')

        for name in columns_to_check:
            device_value = item_data.get(name)
            if device_value == '':
                device_value = None
            if getattr(entry, name) != device_value:
                raise AssertionError(
                    "Error migrating %s (old: %s new: %s)" %
                    (name, device_value, getattr(entry, name)))

    def check_migrated_device_item(self, filename, item_data, device_db_info):
        device_item = item.DeviceItem.get_by_path(filename, device_db_info)
        for name, field in schema.DeviceItemSchema.fields:
            if name == 'filename':
                # need to special-case this one, since filename is not stored
                # in the item_data dict
                self.assertEquals(device_item.filename, filename)
                continue
            elif name == 'id':
                continue # this column doesn't get migrated
            elif name == 'net_lookup_enabled':
                # this column should always be False.  It dosen't get migrated
                # from the old device item
                self.assertEquals(device_item.net_lookup_enabled, False)
                continue
            old_value = item_data.get(name)
            if (isinstance(field, schema.SchemaDateTime) and
                old_value is not None):
                old_value = datetime.datetime.fromtimestamp(old_value)
            new_value = getattr(device_item, name)
            if new_value != old_value:
                raise AssertionError("Error converting field %s "
                                     "(old: %r, new: %r)" % (name, old_value,
                                                             new_value))

    def test_upgrade_from_5x(self):
        # Test the upgrade from devices from Miro 5.x.  These have an sqlite
        # database, but only metadata on it, not the device_item table
        self.setup_json_db('testdata/device-dbs/5.x-json')
        device_sqlite = os.path.join(self.device.mount, '.miro', 'sqlite')
        shutil.copyfile(resources.path('testdata/5.x-device-database.sqlite'),
                        device_sqlite)
        self.check_json_import(self.device.db[u'audio'])

    def test_upgrade_from_5x_with_new_data(self):
        # Test a tricky case, we upgraded a device database for miro 5.x then
        # added new data to it.  When the data in the sqlite database doesn't
        # match the data in the JSON database we should prefer the data from
        # sqlite.
        self.setup_json_db('testdata/device-dbs/5.x-json')
        new_album = u'New Album Title'
        path = os.path.join(self.device.mount, '.miro', 'sqlite')
        shutil.copyfile(resources.path('testdata/5.x-device-database.sqlite'),
                        path)
        # tweak the sqlite database to simulate new data in it
        connection = sqlite3.connect(path)
        connection.execute("UPDATE metadata SET album=? ", (new_album,))
        connection.commit()
        connection.close()
        # do the same thing to the data that we are use to check the migrated
        # items
        device_data = self.device.db[u'audio'].copy()
        for dct in device_data.values():
            dct['album'] = new_album
        # check that the import code gets the value from the sqlite database,
        # not the JSON one
        self.check_json_import(device_data)


class DeviceSyncManagerTest(EventLoopTest):
    def setUp(self):
        EventLoopTest.setUp(self)
        self.setup_feed()
        self.setup_playlist()
        self.setup_device()

    def setup_device(self):
        self.device = testobjects.make_mock_device()
        self.sync = self.device.database[u'sync'] = devices.DeviceDatabase()
        self.sync[u'podcasts'] = devices.DeviceDatabase()
        self.sync[u'playlists'] = devices.DeviceDatabase()
        self.sync[u'podcasts'][u'all'] = True
        self.sync[u'podcasts'][u'enabled'] = True
        self.sync[u'podcasts'][u'expire'] = True
        self.sync[u'podcasts'][u'items'] = [self.feed.url]
        self.sync[u'playlists'][u'enabled'] = True
        self.sync[u'playlists'][u'items'] = [self.playlist.title]

    def setup_feed(self):
        self.feed, items = testobjects.make_feed_with_items(
            10, file_items=True, prefix='feed')
        for i in items[:5]:
            i.mark_watched()
            i.signal_change()
        self.feed_items = items
        self.feed_unwatched_items = items[5:]

    def setup_playlist(self):
        self.manual_feed = testobjects.make_manual_feed()
        items = testobjects.add_items_to_feed(self.manual_feed,
                                              10,
                                              file_items=True,
                                              prefix='playlist-')
        self.playlist = models.SavedPlaylist(u'playlist',
                                             [i.id for i in items])
        self.playlist_items = items

    def check_get_sync_items(self, correct_items, correct_expired=None):
        dsm = app.device_manager.get_sync_for_device(self.device)
        items, expired = dsm.get_sync_items()
        self.assertSameSet([i.id for i in items],
                           [i.id for i in correct_items])
        if correct_expired is None:
            correct_expired = []
        # correct_expired are Item objects and the get_sync_items() returns
        # DeviceItems objects.  To compare, we use the URL.
        self.assertSameSet([i.url for i in expired],
                           [i.url for i in correct_expired])

    def check_device_items(self, correct_items):
        # check which DeviceItems we've created
        view = models.DeviceItem.make_view(db_info=self.device.db_info)
        self.assertSameSet([i.url for i in view],
                           [i.url for i in correct_items])

    def test_get_sync_items(self):
        # Test that get_sync_items() items to sync correctly
        self.check_get_sync_items(self.feed_items + self.playlist_items)

        self.sync[u'podcasts'][u'all'] = False
        self.check_get_sync_items(self.feed_unwatched_items +
                                  self.playlist_items)
        self.sync[u'podcasts'][u'enabled'] = False
        self.check_get_sync_items(self.playlist_items)
        self.sync[u'playlists'][u'enabled'] = False
        self.check_get_sync_items([])

    def add_sync_items(self):
        """Call get_sync_items() and feed the results to add_items().

        This will sync all potential items to the device.

        :returns: list of ItemInfos synced
        """

        dsm = app.device_manager.get_sync_for_device(self.device)
        infos, expired = dsm.get_sync_items()
        dsm.start()
        dsm.add_items(infos)
        self.runPendingIdles()
        return infos

    def test_add_items(self):
        # Test add_items()
        self.check_device_items([])
        infos = self.add_sync_items()
        self.check_device_items(infos)

    def test_get_sync_items_expired(self):
        # Test that get_sync_items() calculates expired items correctly
        self.add_sync_items()
        for i in self.feed_items:
            os.remove(i.filename)
            i.expire()
        self.check_get_sync_items(self.playlist_items, self.feed_items)

    def test_expire_items(self):
        # Test expiring items

        infos = self.add_sync_items()
        self.check_device_items(infos)
        # remove all items in our feed
        for i in self.feed_items:
            os.remove(i.filename)
            i.expire()
        dsm = app.device_manager.get_sync_for_device(self.device)
        # get_sync_items() should return the corresponding items in our device
        # for the expired items
        infos, expired = dsm.get_sync_items()
        self.assertSameSet([i.url for i in self.feed_items],
                           [i.url for i in expired])
        # test sending the items through expire_items()
        dsm.expire_items(expired)
        self.check_device_items(self.playlist_items)

    def set_feed_item_file_sizes(self, size):
        for i in self.feed_items:
            with open(i.filename, "w") as f:
                f.write(" " * size)

    def set_playlist_item_file_size(self, size):
        for i in self.playlist_items:
            with open(i.filename, "w") as f:
                f.write(" " * size)

    def setup_auto_fill_settings(self, feed_space, playlist_space):
        self.sync[u'auto_fill'] = True
        self.sync[u'auto_fill_settings'] = {
            u'recent_music': 0.0,
            u'random_music': 0.0,
            u'most_played_music': 0.0,
            u'new_playlists': playlist_space,
            u'recent_podcasts': feed_space,
        }

    def check_get_auto_items(self, dsm, size, correct_feed_count,
                             correct_playlist_count):
        feed_item_count = 0
        playlist_item_count = 0
        for item_info in dsm.get_auto_items(size):
            if item_info.feed_id == self.feed.id:
                feed_item_count += 1
            elif item_info.feed_id == self.manual_feed.id:
                playlist_item_count += 1
        self.assertEquals(feed_item_count, correct_feed_count)
        self.assertEquals(playlist_item_count, correct_playlist_count)

    def test_get_auto_items_auto_fill_off(self):
        # With auto_fill off, we shouldn't get any items
        self.set_feed_item_file_sizes(10)
        self.set_playlist_item_file_size(10)
        self.sync[u'auto_fill'] = False
        dsm = app.device_manager.get_sync_for_device(self.device)
        self.check_get_auto_items(dsm, 1000000000, 0, 0)

    def test_get_auto_items(self):
        # Test get_auto_items()
        self.set_feed_item_file_sizes(20)
        self.set_playlist_item_file_size(10)
        # Allocate 100 bytes to both our playlist items and our feed items.
        # This should be enough for the entire playlist and 1/2 of the feed
        # items
        self.setup_auto_fill_settings(feed_space=0.5, playlist_space=0.5)
        dsm = app.device_manager.get_sync_for_device(self.device)
        self.check_get_auto_items(dsm, 200, 5, 10)

    def test_get_auto_items_doesnt_half_fill_playlist(self):
        # Test that get_auto_items() only will return items for a playlist if
        # it can fill the entire playlist
        self.set_feed_item_file_sizes(10)
        self.set_playlist_item_file_size(10)
        # When we allocate 50 bytes to each', we can only sync the feed items
        self.setup_auto_fill_settings(feed_space=0.5, playlist_space=0.5)
        dsm = app.device_manager.get_sync_for_device(self.device)
        self.check_get_auto_items(dsm, 100, 5, 0)
        # When we allocate 100, we can sync both
        self.setup_auto_fill_settings(feed_space=0.5, playlist_space=0.5)
        dsm = app.device_manager.get_sync_for_device(self.device)
        self.check_get_auto_items(dsm, 200, 10, 10)

    def test_auto_sync(self):
        # Test that add_items() sets the auto_sync flag correctly

        # setup some auto-sync settings
        self.set_feed_item_file_sizes(10)
        self.set_playlist_item_file_size(10)
        self.setup_auto_fill_settings(feed_space=1.0, playlist_space=0.0)
        dsm = app.device_manager.get_sync_for_device(self.device)
        # get our sync items, they should all be from our feed
        auto_sync_items = dsm.get_auto_items(10000)
        for item in auto_sync_items:
            self.assertEquals(item.feed_id, self.feed.id)
        # call sync some items
        playlist_items = fetch_item_infos(app.db.connection,
                                          [i.id for i in self.playlist_items])
        dsm.start()
        dsm.add_items(playlist_items)
        dsm.add_items(auto_sync_items, auto_sync=True)
        self.runPendingIdles()
        # check that the device items got created and that auto_sync is set
        # correctly
        db_info=self.device.db_info
        for item in self.playlist_items:
            device_item = models.DeviceItem.get_by_url(item.url,
                                                       db_info=db_info)
            self.assertEquals(device_item.auto_sync, False)
        for item in self.feed_items:
            device_item = models.DeviceItem.get_by_url(item.url,
                                                       db_info=db_info)
            self.assertEquals(device_item.auto_sync, True)
        # check auto_sync_view()
        auto_sync_items = models.DeviceItem.auto_sync_view(db_info=db_info)
        self.assertSameSet(set(i.title for i in self.feed_items),
                           set(i.title for i in auto_sync_items))

    def test_run_conversion(self):
        # FIXME: Should write this one
        pass
