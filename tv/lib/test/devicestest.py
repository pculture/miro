# Miro - an RSS based video player application
# Copyright (C) 2010 Participatory Culture Foundation
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
import json

from miro.test.framework import MiroTestCase

from miro import devices

class DeviceManagerTest(MiroTestCase):
    def build_config_file(self, filename, data):
        fn = os.path.join(self.tempdir, filename)
        fp = open(fn, "w")
        fp.write(data)
        fp.close()

    def test_empty(self):
        dm = devices.DeviceManager()
        dm.load_devices(os.path.join(self.tempdir, "*.dev"))
        self.assertRaises(KeyError, dm.get_device, "abc")
        self.assertRaises(KeyError, dm.get_device_by_id, 0, 0)

    def test_parsing(self):
        self.build_config_file(
            "foo.dev",
            "[DEFAULT]\n"
            "vendor_id: 0x1234\n"
            "product_id: 0x4567\n"
            "name: Foo\n"
            "audio_conversion: mp3\n"
            "audio_types: .mp3 .aac\n"
            "mount_instructions: Mount Instructions\\nOver multiple lines\n"
            "video_path: Video\n"
            "audio_path: Audio\n"
            "\n"
            "[Target1]\n"
            "vendor_id: 0x890a\n"
            "product_id: 0xbcde\n"
            "name: Bar\n"
            "video_conversion: mp4\n"
            "\n"
            "[Target2]\n"
            "video_conversion: mp4\n"
            "\n"
            "[Target3]\n"
            "video_conversion: mp4\n"
            "\n"
            )

        dm = devices.DeviceManager()
        dm.load_devices(os.path.join(self.tempdir, "*.dev"))

        # a single device
        device = dm.get_device("Bar")
        # this comes from the section name
        self.assertEqual(device.name, "Target1")
        # this comes from the default
        self.assertEqual(device.audio_conversion, "mp3")
        # this comes from the section
        self.assertEqual(device.device_name, 'Bar')
        self.assertEqual(device.video_conversion, "mp4")
        self.assertEqual(device.audio_path, 'Audio')
        self.assertEqual(device.video_path, 'Video')
        # these are a special case
        self.assertFalse(device.has_multiple_devices)
        self.assertEqual(device.mount_instructions,
                         'Mount Instructions\nOver multiple lines')
        self.assertEqual(device.audio_types, ['.mp3', '.aac'])

        # both devices have the same ID
        device = dm.get_device_by_id(0x1234, 0x4567)
        self.assertTrue(device.has_multiple_devices)
        self.assertEquals(device.name, 'Foo')
        self.assertEquals(device.device_name, 'Foo')
        self.assertEquals(device.vendor_id, 0x1234)
        self.assertEquals(device.product_id, 0x4567)
        self.assertEqual(device.mount_instructions,
                         'Mount Instructions\nOver multiple lines')

        single = device.get_device('Target2')
        self.assertFalse(single.has_multiple_devices)
        self.assertEqual(single.name, 'Target2')

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

        ddb = devices.load_database(self.tempdir)
        self.assertEqual(dict(ddb), {})
        self.assertEqual(len(ddb.get_callbacks('changed')), 1)


    def test_write_database(self):
        data = {u'a': 2,
                u'b': {u'c': [5, 6]}}
        devices.write_database(self.tempdir, data)
        with open(os.path.join(self.tempdir, '.miro', 'json')) as f:
            new_data = json.load(f)
        self.assertEqual(data, new_data)
