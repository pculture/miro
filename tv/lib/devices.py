import time

from glob import glob
from ConfigParser import SafeConfigParser

import gio

from miro.plat.frontends.widgets import timer
from miro import messages
from miro import signals
from miro.plat import resources

class DeviceInfo(object):
    def __init__(self, name, parser):
        self.io_name = name
        self.name = parser.get(name, 'name')
        self.video_conversion = parser.get(name, 'video_conversion')
        self.video_path = parser.get(name, 'video_path')
        self.audio_conversion = parser.get(name, 'audio_conversion')
        self.audio_path = parser.get(name, 'audio_path')

class DeviceManager(signals.SignalEmitter):
    def __init__(self):
        signals.SignalEmitter.__init__(self, 'thread-will-start',
                                             'thread-started',
                                             'thread-did-start',
                                             'begin-loop',
                                             'end-loop')
        self.device_map = {}
        self._disconnecting = {}

    def startup(self):
        # load devices
        devices = glob(resources.path('devices/*.dev'))
        for device_desc in devices:
            parser = SafeConfigParser()
            parser.readfp(open(device_desc))
            for section in parser.sections():
                info = DeviceInfo(section, parser)
                self.device_map[section] = info

    def start_tracking(self):
        volume_monitor = gio.volume_monitor_get()
        volume_monitor.connect('drive-connected', self._drive_connected)
        volume_monitor.connect('drive-changed', self._drive_changed)
        volume_monitor.connect('drive-disconnected', self._drive_disconnected)

        for drive in volume_monitor.get_connected_drives():
            self._drive_connected(volume_monitor, drive)

    def _get_device_info(self, drive):
        id = drive.get_identifier('unix-device')
        name = drive.get_name()
        device_info = self.device_map[name]
        mount_path = None
        volumes = drive.get_volumes()
        if volumes:
            volume = drive.get_volumes()[0]
            mount = volume.get_mount()
            if mount:
                mount_path = mount.get_root().get_path()
        return messages.DeviceInfo(id, device_info, mount_path)

    def _drive_connected(self, volume_monitor, drive):
        if drive.get_name() not in self.device_map:
            return
        info = self._get_device_info(drive)
        if info.id in self._disconnecting:
            # Gio sends a disconnect/connect pair when the device is mounted so
            # we wait a little and check for spurious ones
            timeout_id = self._disconnecting.pop(info.id)
            timer.cancel(timeout_id)
            return
        print time.time(), 'drive connected!', drive
        message = messages.TabsChanged('devices',
                                       [self._get_device_info(drive)],
                                       [],
                                       [])
        message.send_to_frontend()

    def _drive_changed(self, volume_monitor, drive):
        if drive.get_name() not in self.device_map:
            return
        print time.time(), 'drive changed!', drive
        info = self._get_device_info(drive)
        message = messages.TabsChanged('devices',
                                       [],
                                       [info],
                                       [])
        message.send_to_frontend()

        messages.DeviceChanged(info).send_to_frontend()

    def _drive_disconnected(self, volume_monitor, drive):
        if drive.get_name() not in self.device_map:
            return
        info = self._get_device_info(drive)
        timeout_id = timer.add(0.5, self._drive_disconnected_timeout, info)
        self._disconnecting[info.id] = timeout_id

    def _drive_disconnected_timeout(self, info):
        print time.time(), 'drive disconnected!', info.id
        del self._disconnecting[info.id]
        message = messages.TabChanged('devices',
                                      [],
                                      []
                                      [info])
        message.send_to_frontend()

device_manager = DeviceManager()
