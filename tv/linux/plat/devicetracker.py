import logging
import os

import gio

from miro.plat.frontends.widgets import timer
from miro import devices
from miro import messages

class DeviceTracker(object):
    def __init__(self):
        self._disconnecting = {}

    def start_tracking(self):
        volume_monitor = gio.volume_monitor_get()
        volume_monitor.connect('drive-connected', self._drive_connected)
        volume_monitor.connect('drive-changed', self._drive_changed)
        volume_monitor.connect('drive-disconnected', self._drive_disconnected)

        for drive in volume_monitor.get_connected_drives():
            self._drive_connected(volume_monitor, drive)

    def _get_device_info(self, drive):
        name = drive.get_name()
        device_info = devices.device_manager.get_device(name)
        id = drive.get_identifier('unix-device')
        mount_path = size = remaining = None
        volumes = drive.get_volumes()
        if volumes:
            volume = drive.get_volumes()[0]
            mount = volume.get_mount()
            if mount:
                mount_path = mount.get_root().get_path()
                statinfo = os.statvfs(mount_path)
                size = statinfo.f_frsize * statinfo.f_blocks
                remaining = statinfo.f_frsize * statinfo.f_bavail
        return messages.DeviceInfo(id, device_info, mount_path,
                                   size, remaining)

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

    def _drive_disconnected(self, volume_monitor, drive):
        try:
            info = self._get_device_info(drive)
        except KeyError:
            return
        timeout_id = timer.add(0.5, self._drive_disconnected_timeout, info)
        self._disconnecting[info.id] = timeout_id

    def _drive_disconnected_timeout(self, info):
        del self._disconnecting[info.id]
        devices.device_disconnected(info)

tracker = DeviceTracker()
