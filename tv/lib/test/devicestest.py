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
import sqlite3

from miro.gtcache import gettext as _
from miro.plat.utils import (PlatformFilenameType, unicode_to_filename,
                             utf8_to_filename)
from miro.test.framework import MiroTestCase, EventLoopTest
from miro.test import mock

from miro import app
from miro import database
from miro import devices
from miro import item
from miro import metadata
from miro import schema
from miro import storedatabase
from miro.plat import resources

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
        self.device = mock.Mock()
        self.device.database = devices.DeviceDatabase()
        self.device.mount = self.make_temp_dir_path()
        self.device.id = 123
        self.device.name = 'Device'
        self.device.size = 1024000
        self.device.read_only = False
        os.makedirs(os.path.join(self.device.mount, '.miro'))
        sqlite_db = devices.load_sqlite_database(self.device.mount,
                                                 self.device.database,
                                                 self.device.size)
        db_info = database.DBInfo(sqlite_db)
        metadata_manager = devices.make_metadata_manager(self.device.mount,
                                                         db_info,
                                                         self.device.id)
        self.device.db_info = db_info
        self.device.metadata_manager = metadata_manager

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
        self.device = mock.Mock()
        self.device.database = devices.DeviceDatabase()
        self.device.mount = self.tempdir
        self.device.id = 123
        self.device.name = 'Device'
        self.device.size = 1024000
        os.makedirs(os.path.join(self.device.mount, '.miro'))

    def open_database(self):
        sqlite_db = devices.load_sqlite_database(self.device.mount,
                                                 self.device.database,
                                                 self.device.size)
        db_info = database.DBInfo(sqlite_db)
        metadata_manager = devices.make_metadata_manager(self.device.mount,
                                                         db_info,
                                                         self.device.id)
        self.device.db_info = db_info
        self.device.metadata_manager = metadata_manager

    def make_device_items(self, *filenames):
        for filename in filenames:
            # ensure that filename is the correct type for our platform
            filename = unicode_to_filename(unicode(filename))
            with open(os.path.join(self.device.mount, filename), 'w') as f:
                f.write("FAKE DATA")
                f.close()
            item.DeviceItem(self.device, filename)

    def test_open(self):
        self.open_database()
        self.assertEquals(self.device.db_info.db.__class__,
                          storedatabase.LiveStorage)
        self.assertEquals(self.device.db_info.db.error_handler.__class__,
                          storedatabase.DeviceLiveStorageErrorHandler)

    def test_reload(self):
        self.open_database()
        self.make_device_items('foo.mp3', 'bar.mp3')
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
        # setup a device database
        json_path = resources.path('testdata/pre-metadata-device-db')
        self.db = devices.DeviceDatabase(json.load(open(json_path)))
        # setup a device object
        self.device = mock.Mock()
        self.device.database = self.db
        self.device.mount = self.tempdir + "/"
        self.device.remaining = 0
        os.makedirs(os.path.join(self.device.mount, '.miro'))
        self.device.id = 123
        self.cover_art_dir = os.path.join(self.tempdir, 'cover-art')
        os.makedirs(self.cover_art_dir)

    def test_upgrade(self):
        # Test the upgrade from pre-metadata device databases
        sqlite_db = devices.load_sqlite_database(':memory:', self.db, 1024)
        db_info = database.DBInfo(sqlite_db)
        # load_sqlite_database should have converted the old data to metadata
        # entries
        metadata_manager = devices.make_metadata_manager(self.tempdir,
                                                         db_info,
                                                         self.device.id)
        for path, item_data in self.db[u'audio'].items():
            # fill in data that's implicit with the dict
            item_data['file_type'] = u'audio'
            item_data['video_path'] = path
            filename = utf8_to_filename(path.encode('utf-8'))
            self.check_migrated_status(filename, metadata_manager.db_info)
            self.check_migrated_entries(filename, item_data,
                                        metadata_manager.db_info)
            self.check_migrated_device_item(filename, item_data,
                                            metadata_manager.db_info)
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
            old_value = item_data.get(name)
            if (isinstance(field, schema.SchemaDateTime) and
                old_value is not None):
                old_value = datetime.datetime.fromtimestamp(old_value)
            new_value = getattr(device_item, name)
            if new_value != old_value:
                raise AssertionError("Error converting field %s "
                                     "(old: %r, new: %r)" % (name, old_value,
                                                             new_value))
