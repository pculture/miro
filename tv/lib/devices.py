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

from glob import glob
import json
import logging
import os, os.path
import shutil
import time
from ConfigParser import SafeConfigParser

from miro import app
from miro import item
from miro import fileutil
from miro import filetypes
from miro import messages
from miro import signals
from miro import videoconversion

from miro.plat import resources
from miro.plat.utils import filename_to_unicode

class DeviceInfo(object):
    """
    Object which contains various information about a specific supported
    device.

    name: User-visible name of the device
    device_name: the name of the device as reported through USB
    vendor_id: integer version of the device's USB vendor ID
    product_id: integer version of the device's USB product ID
    video_conversion: the Miro conversion name for video to this device
    video_path: mount-relative path to where the videos should be placed
    audio_conversion: the Miro conversion name for audio to this device
    audio_path: mount-relative path to where audio files should be placed
    audio_types: audio MIME types this device supports
    mount_instructions: text to show the user about how to mount their device
    """
    has_multiple_devices = False

    def __init__(self, section, parser):
        self.name = section.decode('utf8')
        self.device_name = self._get(section, parser, 'name')
        self.vendor_id = int(self._get(section, parser, 'vendor_id'), 16)
        self.product_id = int(self._get(section, parser, 'product_id'), 16)
        self.video_conversion = self._get(section, parser, 'video_conversion')
        self.video_path = self._get(section, parser, 'video_path')
        self.audio_conversion = self._get(section, parser, 'audio_conversion')
        self.audio_path = self._get(section, parser, 'audio_path')
        self.audio_types = self._get(section, parser, 'audio_types').split()
        self.mount_instructions = self._get(
            section, parser, 'mount_instructions').decode('utf8').replace(
            '\\n', '\n')

    def _get(self, section, parser, name):
        try:
            return parser.get(section, name)
        except KeyError:
            pass
        try:
            return parser.get('DEFAULT', name)
        except KeyError:
            return None

class MultipleDeviceInfo(object):
    """
    Like DeviceInfo, but represents a device we can't figure out just from the
    USB information.
    """
    has_multiple_devices = True

    def __init__(self, *args):
        self.device_name = self.name = args[0].device_name
        self.vendor_id = args[0].vendor_id
        self.product_id = args[0].product_id
        self.mount_instructions = args[0].mount_instructions
        self.devices = {}
        for info in args:
            self.add_device(info)

    def add_device(self, info):
        self.devices[info.name] = info

    def get_device(self, name):
        """
        Get a given device by the user-visible name.

        Returns a DeviceInfo object.
        """
        return self.devices[name]

class DeviceManager(object):
    """
    Manages the list of devices that Miro knows about, as well as managing the
    current syncs for devices.
    """
    def __init__(self):
        self.device_by_name = {}
        self.device_by_id = {}
        self.syncs_in_progress = {}
        self.startup()

    def _add_device(self, info):
        device_name = info.device_name
        if device_name in self.device_by_name:
            existing = self.device_by_name[device_name]
            if isinstance(existing, MultipleDeviceInfo):
                existing.add_device(info)
                return
            else:
                info = MultipleDeviceInfo(existing, info)
        self.device_by_name[device_name] = info
        self.device_by_id[(info.vendor_id, info.product_id)] = info

    def startup(self):
        # load devices
        devices = glob(resources.path('devices/*.dev'))
        for device_desc in devices:
            parser = SafeConfigParser()
            parser.readfp(open(device_desc))
            for section in parser.sections():
                info = DeviceInfo(section, parser)
                self._add_device(info)

    @staticmethod
    def _get_device_from_info(info, device_type):
        if not info.has_multiple_devices:
            return info
        if device_type is not None and device_type in info.devices:
            return info.devices[device_type]
        return info

    def get_device(self, device_name, device_type=None):
        """
        Get a DeviceInfo (or MultipleDeviceInfo) object given the device's USB
        name.
        """
        info = self.device_by_name[device_name]
        return self._get_device_from_info(info, device_type)

    def get_device_by_id(self, vendor_id, product_id, device_type=None):
        """
        Get a DeviceInfo (or MultipleDeviceInfo) object give the device's USB
        vendor and product IDs.
        """
        info = self.device_by_id[(vendor_id, product_id)]
        return self._get_device_from_info(info, device_type)

    def get_sync_for_device(self, device, create=True):
        """
        Returns a DeviceSyncManager for the given device.  If one exists,
        return that one, otherwise build a new one and return that.

        If create is False, return None instead of creating a new sync manager.
        """
        if device.id not in self.syncs_in_progress:
            if not create:
                return None
            dsm = DeviceSyncManager(device)
            self.syncs_in_progress[device.id] = dsm

        return self.syncs_in_progress[device.id]


class DeviceSyncManager(object):
    """
    Represents a sync in progress to a given device.
    """
    def __init__(self, device):
        self.device = device
        self.start_time = time.time()
        self.etas = {}
        self.signal_handles = []
        self.waiting = set()

        self.device.is_updating = True # start the spinner
        messages.TabsChanged('devices', [], [self.device],
                             []).send_to_frontend()

        self.audio_target_folder = os.path.join(device.mount,
                                                device.info.audio_path)
        if not os.path.exists(self.audio_target_folder):
            os.makedirs(self.audio_target_folder)

        self.video_target_folder = os.path.join(device.mount,
                                                device.info.video_path)
        if not os.path.exists(self.video_target_folder):
            os.makedirs(self.video_target_folder)

    def add_items(self, item_infos):
        device_info = self.device.info
        for info in item_infos:
            if self._exists(info):
                continue # don't recopy stuff
            if info.file_type == 'audio':
                if (info.file_format and
                    info.file_format.split()[0] in device_info.audio_types):
                    final_path = os.path.join(self.audio_target_folder,
                                              os.path.basename(
                            info.video_path))
                    try:
                        shutil.copy(info.video_path, final_path)
                    except IOError:
                        # FIXME - we should pass the error back to the frontend
                        pass
                    else:
                        self._add_item(final_path, info)
                else:
                    logging.debug('unable to detect format of %r: %s' % (
                            info.video_path, info.file_format))
                    self.start_conversion(device_info.audio_conversion,
                                          info,
                                          self.audio_target_folder)
            elif info.file_type == 'video':
                self.start_conversion(device_info.video_conversion,
                                      info,
                                      self.video_target_folder)

        self._check_finished()

    def start_conversion(self, conversion, info, target):
        conversion_manager = videoconversion.conversion_manager
        start_conversion = conversion_manager.start_conversion

        if not self.waiting:
            for signal, callback in (
                ('task-changed', self._conversion_changed_callback),
                ('task-staged', self._conversion_staged_callback),
                ('task-removed', self._conversion_removed_callback),
                ('all-tasks-removed', self._conversion_removed_callback)):
                self.signal_handles.append(conversion_manager.connect(
                        signal, callback))

        self.waiting.add(info)
        start_conversion(conversion, info, target,
                         create_item=False)

    def _exists(self, item_info):
        if item_info.file_type not in self.device.database:
            return False
        for existing in self.device.database[item_info.file_type].values():
            if (item_info.file_url and
                existing.get('url') == item_info.file_url):
                return True
            elif ((item_info.name, item_info.description, item_info.size,
                   item_info.duration) ==
                  (existing.get('name'), existing.get('description'),
                   existing.get('size'), existing.get('duration'))):
                # if a bunch of qualities are the same, we'll call it close
                # enough
                return True
        return False

    def _conversion_changed_callback(self, conversion_manager, task):
        self.etas[task.key] = task.get_eta()
        self._send_sync_changed()

    def _conversion_removed_callback(self, conversion_manager, task=None):
        if task is not None:
            try:
                self.waiting.remove(task.item_info)
                del self.etas[task.key]
            except KeyError:
                pass
        else: # remove all tasks
            self.etas = {}
            self.waiting = set()
        self._check_finished()

    def _conversion_staged_callback(self, conversion_manager, task):
        try:
            self.waiting.remove(task.item_info)
            del self.etas[task.key]
        except KeyError:
            pass # missing for some reason
        else:
            if not task.error: # successful!
                self._add_item(task.final_output_path, task.item_info)
        self._check_finished()

    def _add_item(self, final_path, item_info):
        device_item = item.DeviceItem(
            device=self.device,
            file_type=item_info.file_type,
            video_path=final_path[len(self.device.mount):],
            name=item_info.name,
            feed_name=item_info.feed_name,
            feed_url=item_info.feed_url,
            description=item_info.description,
            release_date=time.mktime(item_info.release_date.timetuple()),
            duration=item_info.duration * 1000,
            permalink=item_info.permalink,
            commentslink=item_info.commentslink,
            payment_link=item_info.payment_link,
            screenshot=item_info.thumbnail,
            thumbnail_url=item_info.thumbnail_url,
            file_format=item_info.file_format,
            license=item_info.license,
            url=item_info.file_url,
            media_type_checked=item_info.media_type_checked,
            mime_type=item_info.mime_type)
        device_item._migrate_thumbnail()
        database = self.device.database
        database.setdefault(device_item.file_type, [])
        database[device_item.file_type][device_item.video_path] = \
            device_item.to_dict()
        messages.ItemsChanged('device', '%s-%s' % (self.device.id,
                                                   device_item.file_type),
                              [messages.ItemInfo(device_item)], # added
                              [], []).send_to_frontend() # changed, removed

    def _check_finished(self):
        if not self.waiting:
            # finished!
            for handle in self.signal_handles:
                videoconversion.conversion_manager.disconnect(handle)
            self.signal_handles = None
            self.device.is_updating = False # stop the spinner
            messages.TabsChanged('devices', [], [self.device],
                                 []).send_to_frontend()
            del app.device_manager.syncs_in_progress[self.device.id]
        self._send_sync_changed()

    def _send_sync_changed(self):
        message = messages.DeviceSyncChanged(self)
        message.send_to_frontend()

    def is_finished(self):
        if self.waiting:
            return False
        return self.device.id not in app.device_manager.syncs_in_progress

    def get_eta(self):
        etas = [eta for eta in self.etas.values() if eta is not None]
        if not etas:
            return
        longest_eta = max(etas)
        return longest_eta

    def get_progress(self):
        eta = self.get_eta()
        if eta is None:
            return 0.0 # no progress
        total_time = time.time() - self.start_time
        total_eta = total_time + eta
        return total_time / total_eta


class DeviceDatabase(dict, signals.SignalEmitter):

    def __init__(self, data=None, parent=None):
        if data:
            dict.__init__(self, data)
        else:
            dict.__init__(self)
        signals.SignalEmitter.__init__(self, 'changed')
        self.parent = parent
        self.bulk_mode = False

    def __getitem__(self, key):
        value = super(DeviceDatabase, self).__getitem__(key)
        if isinstance(value, dict) and not isinstance(value, DeviceDatabase):
            value = self[key] = DeviceDatabase(value, self.parent or self)
        return value

    def __setitem__(self, key, value):
        super(DeviceDatabase, self).__setitem__(key, value)
        if self.parent:
            self.parent.notify_changed()
        else:
            self.notify_changed()

    def notify_changed(self):
        if not self.bulk_mode:
            self.emit('changed')

    def set_bulk_mode(self, bulk):
        self.bulk_mode = bulk
        if not bulk:
            self.notify_changed()


class DatabaseSaveManager(object):
    def __init__(self, mount, database):
        self.mount = mount
        database.connect('changed', self.database_changed)

    def database_changed(self, database):
        write_database(self.mount, database)


def load_database(mount):
    """
    Returns a dictionary of the JSON database that lives on the given device.

    The database lives at [MOUNT]/.miro/json
    """
    file_name = os.path.join(mount, '.miro', 'json')
    if not os.path.exists(file_name):
        return {}
    try:
        db = json.load(file(file_name, 'rb'))
    except ValueError:
        logging.exception('error loading JSON db on %s' % mount)
        db = {}
    ddb = DeviceDatabase(db)
    DatabaseSaveManager(mount, ddb)
    return ddb

def write_database(mount, database):
    """
    Writes the given dictionary to the device.

    The database lives at [MOUNT]/.miro/json
    """
    try:
        os.makedirs(os.path.join(mount, '.miro'))
    except OSError:
        pass
    json.dump(database, file(os.path.join(mount, '.miro', 'json'), 'wb'))

def device_connected(info):
    """
    Helper for device trackers which sends a connected message for the device.
    """
    if info.mount:
        scan_device_for_files(info)
    message = messages.TabsChanged('devices',
                                   [info],
                                   [],
                                   [])
    message.send_to_frontend()

def device_changed(info):
    """
    Helper for device trackers which sends a changed message for the device.
    """
    if info.mount:
        scan_device_for_files(info)
    message = messages.TabsChanged('devices',
                                   [],
                                   [info],
                                   [])
    message.send_to_frontend()
    messages.DeviceChanged(info).send_to_frontend()


def device_disconnected(info):
    """
    Helper for device trackers which sends a disconnected message for the
    device.
    """
    message = messages.TabsChanged('devices',
                                  [],
                                  [],
                                  [info.id])
    message.send_to_frontend()

def clean_database(device):
    def _exists(item_path):
        return os.path.exists(os.path.join(device.mount,
                                           item_path))
    known_files = set()
    to_remove = []
    for item_type in ('video', 'audio', 'other'):
        device.database.setdefault(item_type, {})
        for item_path in device.database[item_type]:
            if _exists(item_path):
                known_files.add(os.path.normcase(item_path))
            else:
                to_remove.append((item_type, item_path))

    if to_remove:
        device.database.set_bulk_mode(True)
        for item_type, item_path in to_remove:
            del device.database[item_type][item_path]
        device.database.set_bulk_mode(False)

    return known_files

def scan_device_for_files(device):
    known_files = clean_database(device)

    device.database.set_bulk_mode(True)
    device.database.setdefault('sync', {})

    for filename in fileutil.miro_allfiles(device.mount):
        short_filename = filename[len(device.mount):]
        ufilename = filename_to_unicode(short_filename)
        if os.path.normcase(ufilename) in known_files: continue
        if filetypes.is_video_filename(ufilename):
            item_type = 'video'
        elif filetypes.is_audio_filename(ufilename):
            item_type = 'audio'
        else:
            continue
        device.database[item_type][ufilename] = {}

    device.database.set_bulk_mode(False)
