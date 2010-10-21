import logging
import os

import gio

from miro.plat.frontends.widgets import timer
from miro import devices
from miro import messages

class DeviceTracker(object):
    def __init__(self):
        self._unix_device_to_drive = {}
        self._disconnecting = {}

    def start_tracking(self):
        volume_monitor = gio.volume_monitor_get()
        volume_monitor.connect('drive-connected', self._drive_connected)
        volume_monitor.connect('drive-changed', self._drive_changed)
        volume_monitor.connect('mount-added', self._mount_added)
        volume_monitor.connect('drive-disconnected', self._drive_disconnected)

        for drive in volume_monitor.get_connected_drives():
            self._drive_connected(volume_monitor, drive)

    def _get_device_info(self, drive):
        id_ = drive.get_identifier('unix-device')
        mount_path = size = remaining = None
        database = {}
        volumes = drive.get_volumes()
        if volumes:
            volume = volumes[0]
            mount = volume.get_mount()
            if mount:
                mount_path = mount.get_root().get_path()
                statinfo = os.statvfs(mount_path)
                size = statinfo.f_frsize * statinfo.f_blocks
                remaining = statinfo.f_frsize * statinfo.f_bavail
                database = devices.load_database(mount_path)

        device_info = devices.device_manager.get_device(
            drive.get_name(),
            database.get('device_name', None))

        self._unix_device_to_drive[id_] = drive

        return messages.DeviceInfo(id_, device_info, mount_path,
                                   database, size, remaining)

    def _drive_connected(self, volume_monitor, drive):
        try:
            info = self._get_device_info(drive)
        except KeyError:
            logging.debug('unknown device connected: %s' % drive.get_name())
            return
        if info.id in self._disconnecting:
            # Gio sends a disconnect/connect pair when the device is mounted so
            # we wait a little and check for spurious ones
            timeout_id = self._disconnecting.pop(info.id)
            timer.cancel(timeout_id)
            return
        devices.device_connected(info)

    def _drive_changed(self, volume_monitor, drive):
        try:
            info = self._get_device_info(drive)
        except KeyError:
            return
        devices.device_changed(info)

    def _mount_added(self, volume_monitor, mount):
        self._drive_changed(volume_monitor, mount.get_drive())

    def _drive_disconnected(self, volume_monitor, drive):
        try:
            info = self._get_device_info(drive)
        except KeyError:
            return
        timeout_id = timer.add(0.5, self._drive_disconnected_timeout, info)
        self._disconnecting[info.id] = timeout_id

    def _drive_disconnected_timeout(self, info):
        del self._disconnecting[info.id]
        try:
            del self._unix_device_to_drive[info.id]
        except KeyError:
            pass
        devices.device_disconnected(info)

    def eject(self, device):
        if device.id not in self._unix_device_to_drive:
            return
        drive = self._unix_device_to_drive[device.id]
        drive.eject(self._eject_callback,
                    gio.MOUNT_UNMOUNT_NONE, None, None)

    def _eject_callback(self, drive, result, user_info):
        if not drive.eject_finish(result):
            logging.warn('eject failed for %r' % drive)

tracker = DeviceTracker()
