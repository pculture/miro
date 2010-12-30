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

from miro import app
from miro import item
from miro import fileutil
from miro import filetypes
from miro.gtcache import gettext as _
from miro import messages
from miro import signals
from miro import conversions

from miro.plat import resources
from miro.plat.utils import filename_to_unicode, unicode_to_filename

class BaseDeviceInfo(object):
    """
    Base class for device information.
    """

    def update(self, kwargs):
        self.__dict__.update(kwargs)
        if 'audio_path' in kwargs:
            self.audio_path = unicode_to_filename(self.audio_path)
        if 'video_path' in kwargs:
            self.video_path = unicode_to_filename(self.video_path)

    def __getattr__(self, key):
        try:
            return self.__dict__[key]
        except (AttributeError, KeyError):
            if key == 'parent' or not hasattr(self, 'parent'):
                raise AttributeError(key)
            else:
                return getattr(self.parent, key)

    def validate(self):
        required = ['name', 'device_name', 'vendor_id', 'product_id',
                    'video_conversion', 'video_path',
                    'audio_conversion', 'audio_path', 'audio_types',
                    'mount_instructions']
        for key in required:
            getattr(self, key)


class DeviceInfo(BaseDeviceInfo):
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
    parent (optional): a MultipleDeviceInfo instance which has this device's
                       info
    """
    has_multiple_devices = False

    def __init__(self, name, **kwargs):
        self.name = name
        self.update(kwargs)

class MultipleDeviceInfo(BaseDeviceInfo):
    """
    Like DeviceInfo, but represents a device we can't figure out just from the
    USB information.
    """
    has_multiple_devices = True

    def __init__(self, device_name, children, **kwargs):
        self.device_name = self.name = device_name
        self.update(kwargs)
        self.devices = {}
        for info in children:
            self.add_device(info)

    def add_device(self, info):
        self.devices[info.name] = info
        info.parent = self

    def get_device(self, name):
        """
        Get a given device by the user-visible name.

        Returns a DeviceInfo object.
        """
        return self.devices[name]

    def validate(self):
        for child in self.devices.values():
            child.validate()

class GenericDeviceInfo(DeviceInfo):
    """
    DeviceInfo object used for generic USB Mass Storage devices.
    """
    def __init__(self, name):
        self.name = self.device_name = name
        self.update({
                'generic': True,
                'mount_instructions': _("Your drive must be mounted."),
                'audio_conversion': 'copy',
                'audio_types': '',
                'audio_path': u'Miro',
                'video_conversion': 'copy',
                'video_path': u'Miro',
                })

class DeviceManager(object):
    """
    Manages the list of devices that Miro knows about, as well as managing the
    current syncs for devices.
    """
    def __init__(self):
        self.device_by_name = {}
        self.device_by_id = {}
        self.connected = {}
        self.syncs_in_progress = {}
        self.startup()

    def _add_device(self, info):
        try:
            info.validate()
        except AttributeError:
            logging.exception('error validating device %s', info.name)
        else:
            self.device_by_name[info.device_name] = info
            self.device_by_id[(info.vendor_id, info.product_id)] = info

    def startup(self):
        # load devices
        self.load_devices(resources.path('devices/*.py'))

    def load_devices(self, path):
        devices = glob(path)
        for device_desc in devices:
            global_dict = {}
            execfile(device_desc, global_dict)
            if 'devices' in global_dict:
                for info in global_dict['devices']:
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


    def _set_connected(self, id_, kwargs):
        if kwargs.get('mount'):
            database = load_database(kwargs['mount'])
            device_name = database.get('device_name')
        else:
            device_name = None
            database = DeviceDatabase()
        if 'name' in kwargs:
            try:
                info = self.get_device(kwargs['name'],
                                       device_name)
            except KeyError:
                info = GenericDeviceInfo(kwargs.get('visible_name',
                                                   kwargs['name']))
        elif 'vendor_id' in kwargs and 'product_id' in kwargs:
            try:
                info = self.get_device_by_id(kwargs['vendor_id'],
                                             kwargs['product_id'],
                                             device_name)
            except KeyError:
                info = GenericDeviceInfo(_('USB Device'))
        else:
            raise RuntimeError('connect_device() requires either the device '
                               'name or vendor/product IDs')

        kwargs.update({
                'database': database,
                'device_name': device_name,
                'info': info})

        info = self.connected[id_] = messages.DeviceInfo(
            id_, info, kwargs.get('mount'), database,
            kwargs.get('size'), kwargs.get('remaining'))

        return info

    def device_connected(self, id_, **kwargs):
        if id_ in self.connected:
            raise RuntimeError('device_connected() called on connected device')

        info = self._set_connected(id_, kwargs)
        if hasattr(info.info, 'generic'):
            # ignore these for now
            logging.debug('ignoring %r' % info.name)
            return
        if info.mount:
            scan_device_for_files(info)
        messages.TabsChanged('devices', [info], [], []).send_to_frontend()

    def device_changed(self, id_, **kwargs):
        if id_ not in self.connected:
            raise RuntimeError('device_changed() called on unknown device')

        info = self.connected[id_]
        if hasattr(info.info, 'generic'):
            # ignore these for now
            return
        if info.mount:
            # turn off the autosaving on the old database
            info.database.disconnect_all()

        info = self._set_connected(id_, kwargs)
        if info.mount:
            scan_device_for_files(info)
        else:
            sync_manager = app.device_manager.get_sync_for_device(info,
                                                                  create=False)
            if sync_manager:
                sync_manager.cancel()
        messages.TabsChanged('devices', [], [info], []).send_to_frontend()
        messages.DeviceChanged(info).send_to_frontend()

    def device_disconnected(self, id_):
        if id_ not in self.connected:
            raise RuntimeError(
                'device_disconnected() called on unknown device')

        info = self.connected.pop(id_)
        if hasattr(info.info, 'generic'):
            # ignore these for now
            return
        sync_manager = app.device_manager.get_sync_for_device(info,
                                                              create=False)
        if sync_manager:
            sync_manager.cancel()

        messages.TabsChanged('devices', [], [], [id_]).send_to_frontend()

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
            return dsm
        else:
            dsm = self.syncs_in_progress[device.id]
            dsm.set_device(device)
            return dsm


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

        self.audio_target_folder = os.path.join(
            device.mount,
            self._get_path_from_setting('audio_path'))
        if not os.path.exists(self.audio_target_folder):
            os.makedirs(self.audio_target_folder)

        self.video_target_folder = os.path.join(
            device.mount,
            self._get_path_from_setting('video_path'))
        if not os.path.exists(self.video_target_folder):
            os.makedirs(self.video_target_folder)

    def _get_path_from_setting(self, setting):
        device_settings = self.device.database.setdefault('settings', {})
        device_path = device_settings.get(setting)
        if device_path is None:
            return getattr(self.device.info, setting)
        else:
            return unicode_to_filename(device_path)

    def set_device(self, device):
        self.device = device

    def add_items(self, item_infos):
        device_settings = self.device.database['settings']
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
                    self.start_conversion(
                        (device_settings.get('audio_conversion') or
                         device_info.audio_conversion),
                        info,
                        self.audio_target_folder)
            elif info.file_type == 'video':
                self.start_conversion(
                    (device_settings.get('video_conversion') or
                     device_info.video_conversion),
                    info,
                    self.video_target_folder)

        self._check_finished()

    def start_conversion(self, conversion, info, target):
        conversion_manager = conversions.conversion_manager
        start_conversion = conversion_manager.start_conversion

        if not self.waiting:
            for signal, callback in (
                ('task-changed', self._conversion_changed_callback),
                ('task-staged', self._conversion_staged_callback),
                ('task-removed', self._conversion_removed_callback),
                ('all-tasks-removed', self._conversion_removed_callback)):
                self.signal_handles.append(conversion_manager.connect(
                        signal, callback))

        task = start_conversion(conversion, info, target,
                                create_item=False)
        self.waiting.add(task.key)

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
                self.waiting.remove(task.key)
                del self.etas[task.key]
            except KeyError:
                pass
        else: # remove all tasks
            self.etas = {}
            self.waiting = set()
        self._check_finished()

    def _conversion_staged_callback(self, conversion_manager, task):
        try:
            self.waiting.remove(task.key)
            del self.etas[task.key]
        except KeyError:
            pass # missing for some reason
        else:
            if not task.error: # successful!
                self._add_item(task.final_output_path, task.item_info)
        self._check_finished()

    def _add_item(self, final_path, item_info):
        dirname, basename = os.path.split(final_path)
        _, extension = os.path.splitext(basename)
        new_basename = "%s%s" % (unicode_to_filename(item_info.name),
                                 extension)
        new_path = os.path.join(dirname, new_basename)
        os.rename(final_path, new_path)
        device_item = item.DeviceItem(
            device=self.device,
            file_type=item_info.file_type,
            video_path=new_path[len(self.device.mount):],
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
                conversions.conversion_manager.disconnect(handle)
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

    def cancel(self):
        for key in self.waiting:
            conversions.conversion_manager.cancel(key)


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


def load_database(mount):
    """
    Returns a dictionary of the JSON database that lives on the given device.

    The database lives at [MOUNT]/.miro/json
    """
    file_name = os.path.join(mount, '.miro', 'json')
    if not os.path.exists(file_name):
        db = {}
    else:
        try:
            db = json.load(file(file_name, 'rb'))
        except ValueError:
            logging.exception('error loading JSON db on %s' % mount)
            db = {}
    ddb = DeviceDatabase(db)
    ddb.connect('changed', write_database, mount)
    return ddb

def write_database(database, mount):
    """
    Writes the given dictionary to the device.

    The database lives at [MOUNT]/.miro/json
    """
    if not os.path.exists(mount):
        # device disappeared, so we can't write to it
        return
    try:
        os.makedirs(os.path.join(mount, '.miro'))
    except OSError:
        pass
    try:
        json.dump(database, file(os.path.join(mount, '.miro', 'json'), 'wb'))
    except IOError:
        # couldn't write to the device
        # XXX throw up an error?
        pass

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
        if os.path.normcase(ufilename) in known_files:
            continue
        if filetypes.is_video_filename(ufilename):
            item_type = 'video'
        elif filetypes.is_audio_filename(ufilename):
            item_type = 'audio'
        else:
            continue
        device.database[item_type][ufilename] = {}

    device.database.set_bulk_mode(False)
